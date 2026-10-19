"""BTC Cycle market mid-session vs next ASX closing-price timing audit.

Pure observational prospective study. A public ASX daily close is NOT
an executable price at the time a mid-session Cycle signal is observed.
Zero broker orders, no model promotion, no ntfy, no portfolio I/O.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import math
from pathlib import Path
from zoneinfo import ZoneInfo

from engines.research.cycle_forward_signal_tape import (
    _read_rows,
    TARGET_DIR,
    STRATEGY_LABEL,
)
from engines.research.cycle_mid_session_signal_tape import (
    COLUMNS as MID_COLUMNS, NAME as MID_NAME, capture_window,
)
from engines.research.ibit_asx_forward_close_tape import (
    COLUMNS as ASX_COLUMNS, OUTPUT as ASX_TAPE, PROVIDER as ASX_PROVIDER,
)
from engines.research.forward_ibit_matched_benchmark import (
    FROZEN_CYCLE_MODEL_CODE_SHA256, EPOCH, _number,
)

SYDNEY=ZoneInfo("Australia/Sydney")
MAX_NEXT_ASX_SESSION_GAP_DAYS=4  # includes Fri->Mon; never interpolate missing
MIN_COMPLETED_NON_HOLD_PAIRS=30
OUTPUT=Path("artifacts/cycle_mid_session_asx_timing_audit.json")


def _utc(value):
    date=dt.datetime.fromisoformat(value)
    if date.tzinfo is None or date.utcoffset() is None:
        raise ValueError("Capture evidence needs timezone-aware timestamp")
    return date.astimezone(dt.timezone.utc)


def report(mid_csv:str,asx_csv:str,*,as_of_utc:dt.datetime)->dict:
    if not isinstance(as_of_utc,dt.datetime) or as_of_utc.tzinfo is None or as_of_utc.utcoffset() is None:
        raise ValueError("Timezone-aware as-of required")
    now=as_of_utc.astimezone(dt.timezone.utc)
    mids=_read_rows(mid_csv,MID_COLUMNS,date_key="research_sydney_date")
    auds=_read_rows(asx_csv,ASX_COLUMNS,date_key="market_session_date_sydney")
    sessions={}
    for c in auds:
        day=dt.date.fromisoformat(c["market_session_date_sydney"])
        receipt=_utc(c["captured_at_utc"])
        if receipt>now:raise ValueError("Future ASX source receipt")
        local=receipt.astimezone(SYDNEY)
        if (local.date()!=day or day.weekday()>=5 or local.time()<dt.time(17)
            or c["symbol"]!="ASX:IBIT" or c["currency"]!="AUD"
            or c["provider"]!=ASX_PROVIDER
            or c["single_provider_unverified_execution"]!="True"
            or c["is_confirmed_broker_fill"]!="False"):
            raise ValueError("ASX source was not a completed indicative Sydney AUD candle")
        price=_number(c["reported_close_aud"],positive=True)
        low=_number(c["daily_low_aud"],positive=True)
        high=_number(c["daily_high_aud"],positive=True)
        if low>high or price<low-.02 or price>high+.02:
            raise ValueError("Inconsistent ASX daily OHLC")
        if day in sessions:raise ValueError("Duplicate ASX Sydney session")
        sessions[day]=(price,receipt,c["row_hash"])
    records=[]
    excluded={}
    def skip(reason):
        excluded[reason]=excluded.get(reason,0)+1
    prior=None
    for m in mids:
        day=dt.date.fromisoformat(m["research_sydney_date"])
        receipt=_utc(m["captured_at_utc"])
        if receipt>now:raise ValueError("Future mid-session evidence")
        if prior and day<=prior:raise ValueError("Unordered mid-session tape")
        prior=day
        if day<EPOCH:
            skip("predates_20_oct_paper_enrolment")
            continue
        if capture_window(receipt)!=day or dt.date.fromisoformat(
            m["source_btc_close_utc_date"])!=receipt.date()-dt.timedelta(days=1):
            raise ValueError("Mid-session source time was not genuinely available")
        if (m["model_name"]!=STRATEGY_LABEL or m["buy_style"]!="adaptive_recovery"
            or m["asx_order_executable"]!="False"
            or m["independent_notification_delivery_verified"]!="False"
            or m["strict_close_date_verified"]!="True"
            or m["provider_archive_prices_preserved"]!="True"):
            raise ValueError("Misrepresented mid-session source evidence")
        if m["model_code_sha256"]!=FROZEN_CYCLE_MODEL_CODE_SHA256:
            skip("cycle_market_model_code_vintage_changed")
            continue
        if not 0<=_number(m["kraken_blockchain_max_overlap_diff_pct"])<=1.:
            skip("source_disagreement_gt_1pct")
            continue
        signal=m["market_signal"]
        buy=_number(m["buy_pct_remaining_cash"])
        sell=_number(m["sell_pct_current_holdings"])
        if not (0<=buy<=100 and 0<=sell<=100) or (
            signal=="HOLD" and (buy or sell)) or (
            signal=="BUY WATCH" and (buy<=0 or sell)) or (
            signal=="SELL WATCH" and (sell<=0 or buy)) or signal not in (
                "HOLD","BUY WATCH","SELL WATCH"):
            raise ValueError("Malformed frozen market-level percent")
        record={
            "research_sydney_date":day.isoformat(),
            "actual_mid_session_capture_utc":receipt.isoformat(),
            "market_watch":signal,
            "model_sha256":m["model_code_sha256"],
            "source_mid_session_row_hash":m["row_hash"],
            "same_session_asx_indicative_close_aud":None,
            "following_session_asx_indicative_close_aud":None,
            "next_real_recorded_session_date":None,
            "same_vs_next_close_pct":None,
            "directional_cost_of_waiting_next_close_pct":None,
            "outcome_status":"MISSING_SAME_DAY_ASX_CLOSE",
        }
        first=sessions.get(day)
        if first is None:
            records.append(record)
            continue
        mid_price,mid_at,mid_hash=first
        if mid_at<=receipt:
            raise ValueError("Same-session close was captured before research market signal")
        record.update({
            "same_session_asx_indicative_close_aud":round(mid_price,6),
            "same_session_asx_source_hash":mid_hash,
            "outcome_status":"WAITING_NEXT_ASX_SESSION_CLOSE",
        })
        following=sorted(d for d in sessions if d>day)
        if not following:
            records.append(record)
            continue
        next_day=following[0]
        days=(next_day-day).days
        # Require the next calendar weekday, not merely the next SAVED
        # Yahoo quote. A missing Wednesday must never be passed off as
        # a Tuesday->Thursday "next-session" execution. Exchange holidays
        # also remain unscored without independently validated calendar data.
        expected=day+dt.timedelta(days=1)
        while expected.weekday()>=5:
            expected+=dt.timedelta(days=1)
        if days>MAX_NEXT_ASX_SESSION_GAP_DAYS:
            record["outcome_status"]="NEXT_SOURCE_DATE_TOO_FAR_OR_MISSING"
            records.append(record)
            continue
        if next_day!=expected:
            record["outcome_status"]="NEXT_BUSINESS_DAY_NOT_CONFIRMED_NO_BACKFILL"
            records.append(record)
            continue
        later_price,later_at,later_hash=sessions[next_day]
        if later_at<=mid_at:raise ValueError("Following ASX price receipt predates base close")
        diff=100*(later_price/mid_price-1)
        # +: after a prospective BUY WATCH, waiting for next day cost MORE
        # than same-day-close reference; after SELL WATCH, waiting yielded
        # LESS than same-day-close reference. This is NOT investable P&L.
        delay=(diff if signal=="BUY WATCH" else -diff if signal=="SELL WATCH" else None)
        record.update({
            "following_session_asx_indicative_close_aud":round(later_price,6),
            "following_session_asx_source_hash":later_hash,
            "next_real_recorded_session_date":next_day.isoformat(),
            "elapsed_calendar_days_to_next":days,
            "same_vs_next_close_pct":round(diff,6),
            "directional_cost_of_waiting_next_close_pct":round(delay,6) if delay is not None else None,
            "outcome_status":"OBSERVED_CLOSE_TO_CLOSE_NOT_EXECUTABLE",
        })
        records.append(record)
    completed=[r for r in records if r["outcome_status"]=="OBSERVED_CLOSE_TO_CLOSE_NOT_EXECUTABLE"]
    active=[r for r in completed if r["market_watch"]!="HOLD"]
    returns=[r["directional_cost_of_waiting_next_close_pct"] for r in active]
    return {
        "kind":"FROZEN_CYCLE_MID_SESSION_TO_ASX_FOLLOWING_CLOSE_OBSERVATIONAL_TIMING_NOT_ORDER",
        "research_as_of_utc":now.isoformat(),
        "fixed_start_session_sydney":EPOCH.isoformat(),
        "paired_same_and_next_actual_ASX_closes":len(completed),
        "paired_non_hold_events":len(active),
        "verified_mid_session_events_in_tape":len(mids),
        "verified_asx_indicative_closes_in_tape":len(auds),
        "excluded_research_rows":dict(sorted(excluded.items())),
        "mean_directional_close_delay_pct_exploratory":(
            round(sum(returns)/len(returns),6) if returns else None),
        "minimum_30_non_hold_events_met":len(active)>=MIN_COMPLETED_NON_HOLD_PAIRS,
        "is_an_ASX_buy_or_sell_at_actual_intraday_bid_ask":False,
        "ntfy_delivery_payload_or_time_confirmed":False,
        "closing_price_trade_fills_demonstrated":False,
        "new_strategy_outperformance_or_better_execution_proven":False,
        "new_trading_recommendation":"NONE",
        "real_trades":0,"portfolio_writes":0,"ntfy_sent":0,
        "observations":records,
    }


def main(argv=None):
    p=argparse.ArgumentParser(description="Research-only BTC mid-session-to-ASX-close timing audit")
    p.add_argument("--data-dir",type=Path,default=TARGET_DIR)
    p.add_argument("--output",type=Path,default=OUTPUT)
    args=p.parse_args(argv)
    m=args.data_dir/MID_NAME
    a=args.data_dir/ASX_TAPE.name
    result=report(m.read_text(encoding="utf-8") if m.exists() else "",
                  a.read_text(encoding="utf-8") if a.exists() else "",
                  as_of_utc=dt.datetime.now(dt.timezone.utc))
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps(result,sort_keys=True,indent=2)+"\n",encoding="utf-8")
    print(json.dumps({k:v for k,v in result.items() if k!="observations"},sort_keys=True))


if __name__=="__main__":
    main()
