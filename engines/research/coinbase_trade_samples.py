"""Prospective Coinbase BTC/USD executed-trade SAMPLE, strictly research-only.

Only a bounded recent response is observed; never claim continuous coverage,
full six-hour executed flow, entity attribution, or predictive accuracy.
Coinbase Advanced Trade 'side' denotes MAKER side (July 2025 change-log).
Consequently maker SELL -> buyer-initiated; maker BUY -> seller-initiated.
No broker, user data, production engine, live vote, or ntfy integration.
"""
from __future__ import annotations

import argparse
import csv
import datetime as dt
import hashlib
import io
import json
import math
import os
from pathlib import Path
import tempfile
from typing import Callable, Any

API_URL = "https://api.coinbase.com/api/v3/brokerage/market/products/BTC-USD/ticker"
PROVIDER = "Coinbase_Advanced_Public_Market_Trades"
PAIR = "BTC-USD"
LIMIT = 100
SLOT_HOURS = 6
MAX_LAST_TRADE_AGE = dt.timedelta(minutes=5)
GENESIS = "0"*64
OUTPUT = (Path(__file__).resolve().parents[2] / "data" /
          "research_forward_validation" / "coinbase_trade_samples_forward.csv")
COLUMNS = (
    "slot_utc", "captured_at_utc", "provider", "pair",
    "trade_side_semantics", "sample_only_not_continuous", "requested_limit",
    "observed_trades", "sample_first_trade_utc", "sample_last_trade_utc",
    "sample_duration_seconds", "last_trade_age_seconds",
    "maker_sell_count_aggressor_buy", "maker_buy_count_aggressor_sell",
    "aggressor_buy_btc_sample", "aggressor_sell_btc_sample",
    "aggressor_buy_usd_sample", "aggressor_sell_usd_sample",
    "aggressor_buy_share_pct_sample", "sample_vwap_usd",
    "first_trade_id", "last_trade_id", "research_signal",
    "provider_payload_sha256", "previous_row_hash", "row_hash",
)


def utc(value: dt.datetime) -> dt.datetime:
    if not isinstance(value, dt.datetime) or value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("timezone-aware instant required")
    return value.astimezone(dt.timezone.utc)


def parse_time(value: Any) -> dt.datetime:
    if not isinstance(value, str):
        raise ValueError("trade UTC timestamp must be text")
    try:
        return utc(dt.datetime.fromisoformat(value.replace("Z", "+00:00")))
    except ValueError as err:
        raise ValueError("trade timestamp malformed") from err


def positive(value: Any) -> float:
    try:
        x = float(value)
    except (ValueError, TypeError, OverflowError) as err:
        raise ValueError("price or size malformed") from err
    if not math.isfinite(x) or x <= 0:
        raise ValueError("price or size must be finite and positive")
    return x


def summarize(payload: dict[str, Any], *, captured_at_utc: dt.datetime) -> dict[str,str]:
    now=utc(captured_at_utc)
    if not isinstance(payload, dict) or not isinstance(payload.get("trades"), list):
        raise ValueError("Coinbase public response must contain trades array")
    trades=payload["trades"]
    if not 2 <= len(trades) <= LIMIT:
        raise ValueError("Unexpected number of public trades")
    ids=set()
    parsed=[]
    for trade in trades:
        if not isinstance(trade, dict):
            raise ValueError("Malformed public trade")
        product=trade.get("product_id", PAIR)
        if product != PAIR:
            raise ValueError("Different Coinbase market")
        ident=str(trade.get("trade_id", ""))
        if not ident.isdecimal() or int(ident) <= 0 or ident in ids:
            raise ValueError("Missing/duplicated trade id")
        ids.add(ident)
        side=trade.get("side")
        if side not in ("BUY", "SELL"):
            raise ValueError("Unknown Coinbase maker side")
        stamp=parse_time(trade.get("time"))
        if stamp>now+dt.timedelta(seconds=10):
            raise ValueError("Future Coinbase trade")
        parsed.append((stamp,int(ident),side,positive(trade.get("price")),positive(trade.get("size"))))
    if any((parsed[i][0],parsed[i][1]) < (parsed[i+1][0],parsed[i+1][1])
           for i in range(len(parsed)-1)):
        raise ValueError("Coinbase trades not reverse chronological")
    oldest,newest=parsed[-1][0],parsed[0][0]
    age=now-newest
    if age < -dt.timedelta(seconds=10) or age > MAX_LAST_TRADE_AGE:
        raise ValueError("Coinbase recent-trade feed stale")
    maker_sell=[(p,s) for _,_,side,p,s in parsed if side=="SELL"]
    maker_buy=[(p,s) for _,_,side,p,s in parsed if side=="BUY"]
    buys_btc=sum(s for p,s in maker_sell)
    sells_btc=sum(s for p,s in maker_buy)
    buys_usd=sum(p*s for p,s in maker_sell)
    sells_usd=sum(p*s for p,s in maker_buy)
    usd=buys_usd+sells_usd
    btc=buys_btc+sells_btc
    if usd<=0 or btc<=0:
        raise ValueError("No executed trade size")
    slot=now.replace(hour=now.hour//SLOT_HOURS*SLOT_HOURS,
                     minute=0,second=0,microsecond=0)
    payload_sha=hashlib.sha256(json.dumps(payload,sort_keys=True,separators=(",", ":"),
                                         allow_nan=False).encode("utf-8")).hexdigest()
    return {
       "slot_utc": slot.isoformat(),"captured_at_utc":now.isoformat(timespec="seconds"),
       "provider":PROVIDER,"pair":PAIR,
       "trade_side_semantics":"MAKER_SIDE_INVERTED_FOR_AGGRESSOR",
       "sample_only_not_continuous":"True","requested_limit":str(LIMIT),
       "observed_trades":str(len(parsed)),
       "sample_first_trade_utc":oldest.isoformat(),
       "sample_last_trade_utc":newest.isoformat(),
       "sample_duration_seconds":f"{(newest-oldest).total_seconds():.3f}",
       "last_trade_age_seconds":f"{max(age.total_seconds(),0):.3f}",
       "maker_sell_count_aggressor_buy":str(len(maker_sell)),
       "maker_buy_count_aggressor_sell":str(len(maker_buy)),
       "aggressor_buy_btc_sample":f"{buys_btc:.8f}",
       "aggressor_sell_btc_sample":f"{sells_btc:.8f}",
       "aggressor_buy_usd_sample":f"{buys_usd:.2f}",
       "aggressor_sell_usd_sample":f"{sells_usd:.2f}",
       "aggressor_buy_share_pct_sample":f"{100*buys_usd/usd:.6f}",
       "sample_vwap_usd":f"{usd/btc:.6f}",
       "first_trade_id":str(parsed[-1][1]),
       "last_trade_id":str(parsed[0][1]),
       "research_signal":"OBSERVATION_ONLY_NO_TRADE",
       "provider_payload_sha256":payload_sha,
    }


def signature(row: dict[str,str]) -> str:
    return hashlib.sha256(json.dumps({k:row[k] for k in COLUMNS if k!="row_hash"},
                        sort_keys=True,separators=(",", ":")).encode("utf-8")).hexdigest()


def read_tape(path: Path) -> list[dict[str,str]]:
    if not path.exists():
        return []
    with path.open(newline="", encoding="utf-8") as f:
        reader=csv.DictReader(f)
        if tuple(reader.fieldnames or ())!=COLUMNS:
            raise ValueError("Existing Coinbase tape schema differs")
        rows=list(reader)
    if not rows:
        raise ValueError("Empty existing tape refuses reset")
    last=GENESIS
    previous_slot=None
    for row in rows:
        if (set(row)!=set(COLUMNS) or row["previous_row_hash"]!=last
            or row["row_hash"]!=signature(row)):
            raise ValueError("Coinbase tape hash chain is invalid")
        slot=utc(dt.datetime.fromisoformat(row["slot_utc"]))
        captured=utc(dt.datetime.fromisoformat(row["captured_at_utc"]))
        if (slot.hour%SLOT_HOURS!=0 or slot.minute!=0 or slot.second!=0
            or not slot<=captured<slot+dt.timedelta(hours=SLOT_HOURS)
            or (previous_slot is not None and slot<=previous_slot)
            or row["provider"]!=PROVIDER or row["pair"]!=PAIR
            or row["trade_side_semantics"]!="MAKER_SIDE_INVERTED_FOR_AGGRESSOR"
            or row["sample_only_not_continuous"]!="True"
            or row["research_signal"]!="OBSERVATION_ONLY_NO_TRADE"):
            raise ValueError("Invalid Coinbase capture chronology or metadata")
        previous_slot,last=slot,row["row_hash"]
    return rows


def append(path: Path, row: dict[str,str]) -> bool:
    if set(row)!=set(COLUMNS)-{"previous_row_hash","row_hash"}:
        raise ValueError("Unexpected Coinbase row fields")
    rows=read_tape(path)
    if rows:
        old=utc(dt.datetime.fromisoformat(rows[-1]["slot_utc"]))
        new=utc(dt.datetime.fromisoformat(row["slot_utc"]))
        if new==old:
            return False
        if new<old:
            raise ValueError("Coinbase historical backfill forbidden")
    complete={**row,"previous_row_hash":rows[-1]["row_hash"] if rows else GENESIS}
    complete["row_hash"]=signature(complete)
    new_rows=rows+[complete]
    b=io.StringIO(newline="")
    writer=csv.DictWriter(b,fieldnames=COLUMNS,lineterminator="\n")
    writer.writeheader(); writer.writerows(new_rows)
    path.parent.mkdir(parents=True,exist_ok=True)
    with tempfile.NamedTemporaryFile(mode="w",dir=path.parent,encoding="utf-8",
                                     delete=False,newline="") as f:
        temp=f.name;f.write(b.getvalue())
    try:
        os.replace(temp,path)
    finally:
        if os.path.exists(temp):os.unlink(temp)
    if read_tape(path)!=new_rows:
        raise AssertionError("Coinbase appended tape validation failed")
    return True


def fetch_public_trades() -> dict[str,Any]:
    import requests
    response=requests.get(API_URL,params={"limit":LIMIT},timeout=12,
        headers={"User-Agent":"BTC-Composite-Research-Coinbase-Trades/1.0", "Accept":"application/json"})
    response.raise_for_status()
    return response.json()


def run_once(*,path:Path=OUTPUT, fetcher:Callable[[],dict[str,Any]]=fetch_public_trades,
             clock:Callable[[],dt.datetime]=lambda:dt.datetime.now(dt.timezone.utc)) -> bool:
    before=utc(clock())
    records=read_tape(path)
    slot=before.replace(hour=before.hour//SLOT_HOURS*SLOT_HOURS,
                        minute=0,second=0,microsecond=0)
    if records and records[-1]["slot_utc"]==slot.isoformat():
        return False
    response=fetcher()
    after=utc(clock())
    if not before<=after<=before+dt.timedelta(minutes=2):
        raise ValueError("Inconsistent HTTP request timing")
    after_slot=after.replace(hour=after.hour//SLOT_HOURS*SLOT_HOURS,
                            minute=0,second=0,microsecond=0)
    if after_slot!=slot:
        raise ValueError("Coinbase sampling slot crossed")
    return append(path,summarize(response,captured_at_utc=after))


def main() -> None:
    parser=argparse.ArgumentParser(description="Coinbase public trade samples: research-only")
    parser.add_argument("--probe-only",action="store_true",help="Read-only API check; no save")
    parser.add_argument("--self-check-only",action="store_true",help="Validate old tape; no network")
    args=parser.parse_args()
    if args.probe_only and args.self_check_only:
        parser.error("Choose only one probe/self-check mode")
    read_tape(OUTPUT)
    if args.probe_only:
        r=summarize(fetch_public_trades(),captured_at_utc=dt.datetime.now(dt.timezone.utc))
        print(json.dumps({k:r[k] for k in ("provider","captured_at_utc",
            "observed_trades","sample_duration_seconds", "aggressor_buy_share_pct_sample",
            "research_signal")},sort_keys=True))
    elif args.self_check_only:
        print("Existing Coinbase immutable tape valid; no network or changes")
    else:
        print("A new bounded sample captured" if run_once() else "This slot already captured")


if __name__=="__main__":
    main()
