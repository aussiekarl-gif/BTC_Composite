"""Prospective MID-SESSION Cycle Trading market WATCH research tape.

SEPARATE from original nightly market tape and the once-daily ntfy. The
timestamp refers to *actual successful capture*, never the intended cron.
No real account/portfolio/ASX fills/orders/ntfy POST or delivery marker.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import math
from pathlib import Path
from typing import Callable
from zoneinfo import ZoneInfo

import pandas as pd

from engines.research.cycle_forward_signal_tape import (
    TARGET_DIR, _read_rows, _dump_rows, _signature, _code_hash, GENESIS,
    STRATEGY_LABEL,
)
from engines.research.cycle_live_completed_utc_prices import (
    fetch_cycle_live_sources, merge_verified_live_cycle_prices,
)
from engines.research.cycle_halving_countdown import fetch_halving_countdown
from engines.research.cycle_trading_dashboard_model import build_dashboard_market
from engines.research.cycle_trade_allocation import (
    calculate_allocation_signal, DEFAULT_BUY_STYLE,
)
from engines.research.top_signal_horse_race import read_exported_history

SYDNEY=ZoneInfo("Australia/Sydney")
FIRST_ELIGIBLE_DATE=dt.date(2026,10,20)
WINDOW_START=dt.time(11,0)
WINDOW_END=dt.time(15,0)  # pre-close; not a verified ASX trading session
NAME="cycle_mid_session_market_watch.csv"
OUTPUT=TARGET_DIR/NAME
COLUMNS=(
    "research_sydney_date","captured_at_utc","source_btc_close_utc_date",
    "btc_usd_verified_completed_close","prior_200wma_usd",
    "prior_fx_aud_per_usd","fx_source_date_utc","halving_date",
    "model_name","model_code_sha256","buy_style",
    "market_signal","buy_pct_remaining_cash","sell_pct_current_holdings",
    "kraken_blockchain_max_overlap_diff_pct",
    "strict_close_date_verified","provider_archive_prices_preserved",
    "asx_order_executable","independent_notification_delivery_verified",
    "prior_row_hash","row_hash",
)


def _instant(value:dt.datetime)->dt.datetime:
    if not isinstance(value,dt.datetime) or value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("Timezone-aware actual capture instant required")
    return value.astimezone(dt.timezone.utc)


def capture_window(now:dt.datetime)->dt.date:
    local=_instant(now).astimezone(SYDNEY)
    if (local.date()<FIRST_ELIGIBLE_DATE or local.weekday()>=5
        or not WINDOW_START<=local.time()<WINDOW_END):
        raise ValueError("Not in eligible Sydney weekday 11:00-15:00 mid-session window")
    return local.date()


def build_observation(*,market:dict,verified:dict,captured_at_utc:dt.datetime,
                      code_hash:str)->dict:
    today=capture_window(captured_at_utc)
    if not isinstance(market,dict) or not isinstance(verified,dict):
        raise ValueError("Exact live shared market and verification required")
    expected_close=dt.date.fromisoformat(str(market["asof_date"]))
    if expected_close != _instant(captured_at_utc).date()-dt.timedelta(days=1):
        raise ValueError("Must use ONLY previous completed UTC BTC close")
    if not verified.get("strict_close_date_verified") or not verified.get("archive_raw_prices_preserved"):
        raise ValueError("BTC source date or original archive not independently verified")
    overlap=float(verified["recent_kraken_blockchain_max_diff_pct"])
    if not math.isfinite(overlap) or not 0<=overlap<=1.0:
        raise ValueError("BTC cross-provider disagreement >1%")
    if market.get("usd_aud_prior") is None:
        raise ValueError("Previous AUD FX missing")
    fx_day=dt.date.fromisoformat(str(market["fx_source_date"]))
    if fx_day>=expected_close or (expected_close-fx_day).days>7:
        raise ValueError("Historical FX source is future or stale")
    if (not isinstance(code_hash,str) or len(code_hash)!=64
        or any(c not in "0123456789abcdef" for c in code_hash)):
        raise ValueError("Exact model implementation fingerprint required")
    halving=dt.date.fromisoformat(str(market["halving_date"]))
    if halving>expected_close:
        raise ValueError("Future halving information")
    vote=calculate_allocation_signal(market,buy_style=DEFAULT_BUY_STYLE)
    signal=vote["signal"]
    buy=float(vote["buy_pct_cash"])
    sell=float(vote["sell_pct_held"])
    if (signal not in ("BUY WATCH","SELL WATCH","HOLD")
        or not 0<=buy<=100 or not 0<=sell<=100
        or (signal=="HOLD" and (buy or sell))
        or (signal=="BUY WATCH" and (buy<=0 or sell))
        or (signal=="SELL WATCH" and (sell<=0 or buy))):
        raise ValueError("Market-level allocation internally inconsistent")
    close=float(market["btc_price_usd"])
    wma=float(market["prior_200wma_usd"])
    fx=float(market["usd_aud_prior"])
    if not all(math.isfinite(x) and x>0 for x in (close,wma,fx)):
        raise ValueError("Nonfinite or invalid BTC, prior WMA or FX")
    return {
        "research_sydney_date":today.isoformat(),
        "captured_at_utc":_instant(captured_at_utc).isoformat(),
        "source_btc_close_utc_date":expected_close.isoformat(),
        "btc_usd_verified_completed_close":f"{close:.6f}",
        "prior_200wma_usd":f"{wma:.6f}",
        "prior_fx_aud_per_usd":f"{fx:.8f}",
        "fx_source_date_utc":fx_day.isoformat(),
        "halving_date":halving.isoformat(),
        "model_name":STRATEGY_LABEL,
        "model_code_sha256":code_hash,
        "buy_style":DEFAULT_BUY_STYLE,
        "market_signal":signal,
        "buy_pct_remaining_cash":f"{buy:.4f}",
        "sell_pct_current_holdings":f"{sell:.4f}",
        "kraken_blockchain_max_overlap_diff_pct":f"{overlap:.4f}",
        "strict_close_date_verified":"True",
        "provider_archive_prices_preserved":"True",
        "asx_order_executable":"False",
        "independent_notification_delivery_verified":"False",
    }


def read_tape(path:Path=OUTPUT)->list[dict]:
    content=path.read_text(encoding="utf-8") if path.exists() else ""
    rows=_read_rows(content,COLUMNS,date_key="research_sydney_date")
    last_day=None
    for row in rows:
        stamp=_instant(dt.datetime.fromisoformat(row["captured_at_utc"]))
        day=capture_window(stamp)
        if day.isoformat()!=row["research_sydney_date"] or (last_day and day<=last_day):
            raise ValueError("Research tape captured outside eligible Sydney chronology")
        last_day=day
        if (row["asx_order_executable"]!="False"
            or row["independent_notification_delivery_verified"]!="False"
            or row["strict_close_date_verified"]!="True"
            or row["provider_archive_prices_preserved"]!="True"):
            raise ValueError("Research-only capture provenance mutated")
        if dt.date.fromisoformat(row["source_btc_close_utc_date"]) != stamp.date()-dt.timedelta(days=1):
            raise ValueError("Capture uses future/incomplete BTC date")
    return rows


def append(path:Path,row:dict)->bool:
    rows=read_tape(path)
    if set(row)!=set(COLUMNS)-{"prior_row_hash","row_hash"}:
        raise ValueError("Unexpected market tape schema")
    day=capture_window(dt.datetime.fromisoformat(row["captured_at_utc"]))
    if row["research_sydney_date"]!=day.isoformat():
        raise ValueError("Mid-session row Sydney date mismatch")
    if rows:
        prev=dt.date.fromisoformat(rows[-1]["research_sydney_date"])
        if day==prev:return False
        if day<prev:raise ValueError("Mid-session prior day backfill forbidden")
    new={k:str(row[k]) for k in COLUMNS if k not in ("prior_row_hash","row_hash")}
    new["prior_row_hash"]=rows[-1]["row_hash"] if rows else GENESIS
    new["row_hash"]=_signature(new,COLUMNS)
    rows.append(new)
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(_dump_rows(rows,COLUMNS),encoding="utf-8")
    read_tape(path)
    return True


def fetch_exact_live_market(now:dt.datetime)->tuple[dict,dict]:
    """Uses identical external BTC/FX/halving source and market math as ntfy."""
    today=_instant(now).date()
    source=read_exported_history()
    archive=source if isinstance(source,pd.DataFrame) else pd.DataFrame({"price_usd":source})
    raw,fx,kraken=fetch_cycle_live_sources(asof=today.isoformat())
    combined,meta=merge_verified_live_cycle_prices(archive,raw,kraken,utc_today=today)
    halving=fetch_halving_countdown(now=now)
    verified=halving.get("last_halving_date") if halving.get("halving_date_verified") else None
    if not verified or dt.date.fromisoformat(verified)>combined.index[-1].date():
        raise ValueError("Halving date unavailable or newer than current verified close")
    market=build_dashboard_market(
        combined,fx,asof=today.isoformat(),confirmed_halving_date=verified)
    return market,meta


def capture(*,path:Path=OUTPUT,clock:Callable=lambda:dt.datetime.now(dt.timezone.utc),
            market_fetcher:Callable=fetch_exact_live_market)->dict:
    begun=_instant(clock())
    today=capture_window(begun)
    previous=read_tape(path)
    if previous and previous[-1]["research_sydney_date"]==today.isoformat():
        return {"status":"EXISTING_SYDNEY_DATE_NO_REWRITE","date":today.isoformat()}
    market,meta=market_fetcher(begun)
    captured=_instant(clock())
    if capture_window(captured)!=today:
        raise ValueError("Source retrieval crossed eligible ASX research capture window")
    row=build_observation(market=market,verified=meta,captured_at_utc=captured,
                          code_hash=_code_hash())
    added=append(path,row)
    return {
        "status":"NEW_PROSPECTIVE_MID_SESSION_RESEARCH_OBSERVATION" if added else "EXISTING_SYDNEY_DATE_NO_REWRITE",
        "date":today.isoformat(),
        "actual_capture_at_utc":captured.isoformat(),
        "market_watch":row["market_signal"],
        "model_code_sha256":row["model_code_sha256"],
        "source_btc_completed_close_utc":row["source_btc_close_utc_date"],
        "live_ntfy_delivery_matched":False,
        "real_broker_orders":0,
        "new_ntfy_messages":0,
        "portfolio_access":False,
    }


def main():
    p=argparse.ArgumentParser(description="Mid-session public BTC market tape, independent of ntfy")
    p.add_argument("--self-check-only",action="store_true")
    args=p.parse_args()
    if args.self_check_only:
        print(json.dumps({"status":"CHAIN_VALIDATED","observations":len(read_tape())}))
    else:
        print(json.dumps(capture(),sort_keys=True))


if __name__=="__main__":
    main()
