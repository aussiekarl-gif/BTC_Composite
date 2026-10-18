"""Prospective ASX:IBIT AUD daily CLOSE observation (NOT an executable trade).

Free Yahoo IBIT.AX daily candle can support *future* ASX weekday research.
It is NOT an official broker fill, ASX bid/ask or second independent data
provider (query1/query2 are the SAME Yahoo source). No historical 2017/21
IBIT can exist: Australia-listed IBIT began on 14-Nov-2025.

Append only a newly completed Sydney-market-date close captured AFTER
17:00 Australia/Sydney on that exact local market weekday. Never backfill
missing dates, duplicate a previous day, treat weekend/ASX holidays as
zero returns, misread USD NASDAQ IBIT, or present the daily candle
timestamp as the final trade timestamp. Immutable SHA256 chain records
price provider and capture-at time. One additional optional step in the
EXISTING forward signal daily workflow; deliberately no ntfy, personal
portfolio, broker or other job/schedule.
"""
from __future__ import annotations

import argparse
import csv
import datetime as dt
import json
import math
from pathlib import Path
from zoneinfo import ZoneInfo

import requests

from engines.research.ibit_quote import URL,FALLBACK_URL
from engines.research.cycle_forward_signal_tape import (
    GENESIS,_read_rows,_dump_rows,_signature,_clean_input,
)

ROOT=Path(__file__).resolve().parents[2]
OUTPUT=ROOT/"data"/"research_forward_validation"/"asx_ibit_closes_forward.csv"
SYDNEY=ZoneInfo("Australia/Sydney")
PROVIDER="Yahoo_Finance_IBIT.AX_daily_candle_indicative"
COLUMNS=(
    "market_session_date_sydney",
    "captured_at_utc",
    "provider_daily_candle_timestamp_utc",
    "symbol",
    "currency",
    "reported_close_aud",
    "daily_low_aud",
    "daily_high_aud",
    "daily_volume",
    "provider",
    "single_provider_unverified_execution",
    "is_confirmed_broker_fill",
    "prior_row_hash",
    "row_hash",
)


class NonTradingOrMissingClose(ValueError):
    """ASX did not have a completed same-day IBIT candle, or provider late."""


def _utc_instant(now):
    if not isinstance(now,dt.datetime) or now.tzinfo is None:
        raise ValueError("Capture time must be timezone-aware datetime")
    return now.astimezone(dt.timezone.utc)


def read_latest_close(payload,*,captured_at_utc):
    """Freeze a NEW Sydney-dated completed session at least 1h after close."""
    now=_utc_instant(captured_at_utc)
    local=now.astimezone(SYDNEY)
    if local.weekday()>=5 or local.time()<dt.time(17,0):
        raise NonTradingOrMissingClose("Not past Sydney-market weekday close")
    try:
        item=payload["chart"]["result"][0]
        meta=item["meta"]
        symbol=str(meta["symbol"]).upper()
        currency=str(meta["currency"]).upper()
        tz=str(meta["exchangeTimezoneName"])
        epochs=item["timestamp"]
        quotes=item["indicators"]["quote"][0]
        closes=quotes["close"]
        lows=quotes["low"]
        highs=quotes["high"]
        volumes=quotes["volume"]
    except (KeyError,IndexError,ValueError,TypeError,AttributeError) as e:
        raise ValueError("Missing required Yahoo IBIT daily AUD candle fields") from e
    if symbol not in ("IBIT.AX","IBIT.AU") or currency!="AUD" or tz!="Australia/Sydney":
        raise ValueError("Refuse non-Australian/non-AUD IBIT or wrong timezone")
    if not epochs or any(len(x)!=len(epochs)
                         for x in (closes,lows,highs,volumes)):
        raise ValueError("Malformed Yahoo IBIT daily candle vector lengths")
    valid=[]
    for epoch,close,low,high,volume in zip(
        epochs,closes,lows,highs,volumes
    ):
        if None in (epoch,close,low,high,volume):
            continue
        try:
            stamp=dt.datetime.fromtimestamp(int(epoch),dt.timezone.utc)
            local_session=stamp.astimezone(SYDNEY).date()
            c,l,h=float(close),float(low),float(high)
            v=int(volume)
        except (OSError,OverflowError,ValueError,TypeError):
            continue
        if (local_session!=local.date()
            or stamp>now
            or stamp.date()<dt.date(2025,11,14)
            or not all(math.isfinite(x) and x>0 for x in (c,l,h))
            or h<l or not l-0.02<=c<=h+0.02 or v<0):
            continue
        valid.append((stamp,c,l,h,v))
    if not valid:
        raise NonTradingOrMissingClose(
            "No completed IBIT.AX AUD candle dated CURRENT Sydney session")
    stamp,close,low,high,volume=max(valid,key=lambda row:row[0])
    return {
        "market_session_date_sydney":local.date().isoformat(),
        "captured_at_utc":now.isoformat(),
        "provider_daily_candle_timestamp_utc":stamp.isoformat(),
        "symbol":"ASX:IBIT",
        "currency":"AUD",
        "reported_close_aud":f"{close:.6f}",
        "daily_low_aud":f"{low:.6f}",
        "daily_high_aud":f"{high:.6f}",
        "daily_volume":str(volume),
        "provider":PROVIDER,
        "single_provider_unverified_execution":"True",
        "is_confirmed_broker_fill":"False",
    }


def append_market_observation(content,new):
    """Tamper-evident add-only; no same-session revisions or older backfills."""
    rows=_read_rows(content,COLUMNS,date_key="market_session_date_sydney")
    clean=_clean_input(new,COLUMNS)
    d=dt.date.fromisoformat(clean["market_session_date_sydney"])
    if rows:
        last=dt.date.fromisoformat(rows[-1]["market_session_date_sydney"])
        if d==last:
            return content,False
        if d<last:
            raise ValueError("Historical IBIT close backfill forbidden")
    clean["prior_row_hash"]=rows[-1]["row_hash"] if rows else GENESIS
    clean["row_hash"]=_signature(clean,COLUMNS)
    rows.append(clean)
    return _dump_rows(rows,COLUMNS),True


def fetch_yahoo_asx_daily_candle(*,timeout=12):
    """Yahoo host redundancy is NOT independent historical corroboration."""
    errors=[]
    for url in (URL,FALLBACK_URL):
        try:
            response=requests.get(
                url,params={"interval":"1d","range":"10d"},
                headers={"User-Agent":"Mozilla/5.0 (public ASX IBIT read only)"},
                timeout=timeout,
            )
            response.raise_for_status()
            payload=response.json()
            if not isinstance(payload,dict):
                raise ValueError("Non-object provider response")
            return payload
        except (requests.RequestException,ValueError) as err:
            errors.append(type(err).__name__)
    raise NonTradingOrMissingClose(
        "Yahoo IBIT.AX daily series unavailable; "+";".join(errors))


def capture_once(*,path=OUTPUT,now=None,fetcher=fetch_yahoo_asx_daily_candle):
    now=_utc_instant(now or dt.datetime.now(dt.timezone.utc))
    current=now.astimezone(SYDNEY)
    # Never query Yahoo / invent artificial weekend session prices.
    if current.weekday()>=5 or current.time()<dt.time(17,0):
        return {"status":"skipped_no_completed_sydney_weekday",
                "wrote_close":False}
    try:
        observation=read_latest_close(fetcher(),captured_at_utc=now)
    except NonTradingOrMissingClose as exc:
        return {"status":"skipped_no_same_day_verified_aud_candle",
                "reason":str(exc),"wrote_close":False}
    target=Path(path)
    prior=target.read_text() if target.exists() else ""
    updated,wrote=append_market_observation(prior,observation)
    if wrote:
        target.parent.mkdir(parents=True,exist_ok=True)
        target.write_text(updated)
    return {
        "status":"captured" if wrote else "already_frozen_no_change",
        "observation_date_sydney":observation["market_session_date_sydney"],
        "indicative_close_aud":observation["reported_close_aud"],
        "single_yahoo_provider_only":True,
        "not_broker_executable":True,
        "wrote_close":wrote,
    }


def main(argv=None):
    parser=argparse.ArgumentParser()
    parser.add_argument("--output",type=Path,default=OUTPUT)
    cfg=parser.parse_args(argv)
    try:
        record=capture_once(path=cfg.output)
    except (ValueError,requests.RequestException) as exc:
        # This optional ASX observation MUST NOT prevent the independent
        # verified Bitcoin signal tape from being saved in same workflow.
        record={"status":"skipped_source_or_schema_error",
                "reason":str(exc),"wrote_close":False}
    print(json.dumps(record,sort_keys=True))
    print("READ ONLY research: never an IBIT broker quote or ntfy signal")


if __name__=="__main__":
    main()
