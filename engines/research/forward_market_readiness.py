"""Read-only integrity and prospective sample-count report for BTC / ASX:IBIT.

A passing unit test is NOT a live-trading edge. Records may be sparse
and the first original BTC record was backdated by three days.
All new observations are verified against the existing hash chain.
No backfills, no source requests, no BUY/SELL, no ntfy, no portfolio edits.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
from pathlib import Path
from zoneinfo import ZoneInfo

from engines.research.cycle_forward_signal_tape import (
    _read_rows, SIGNAL_COLUMNS, OUTCOME_COLUMNS, _was_captured_prospectively,
    TARGET_DIR, SIGNAL_TAPE, OUTCOME_TAPE,
)
from engines.research.ibit_asx_forward_close_tape import COLUMNS as IBIT_COLUMNS

SYDNEY=ZoneInfo("Australia/Sydney")
BTC_PIPELINE_SAMPLE_TARGET=30
ASX_PIPELINE_SAMPLE_TARGET=20
BTC_CROSSCHECK_MANUAL_REVIEW_THRESHOLD_PCT=5.0


def _load(path):
    p=Path(path)
    return p.read_text() if p.exists() else ""


def _strictly_ordered(records,key):
    days=[dt.date.fromisoformat(r[key]) for r in records]
    if any(a>=b for a,b in zip(days,days[1:])):
        raise ValueError("Out-of-order/duplicate prospective records")
    return days


def inspect_forward_tapes(btc_text,ibit_text,outcome_text="",*,now):
    """Verify contents, separate sample pipeline health from model efficacy."""
    if not isinstance(now,dt.datetime) or now.tzinfo is None:
        raise ValueError("Timezone-aware audit time required")
    t=now.astimezone(dt.timezone.utc)
    btc=_read_rows(btc_text,SIGNAL_COLUMNS,date_key="observation_date_utc")
    ibit=_read_rows(ibit_text,IBIT_COLUMNS,
                    date_key="market_session_date_sydney")
    results=_read_rows(outcome_text,OUTCOME_COLUMNS)
    btc_days=_strictly_ordered(btc,"observation_date_utc")
    asx_days=_strictly_ordered(ibit,"market_session_date_sydney")
    seen_outcomes=set()
    btc_hashes={x["row_hash"]:x for x in btc}
    for outcome in results:
        base=(outcome["base_observation_date_utc"],
              outcome["horizon_days"])
        if base in seen_outcomes:
            raise ValueError("Duplicate forward outcome horizon")
        seen_outcomes.add(base)
        if outcome["source_base_row_hash"] not in btc_hashes or (
            outcome["source_future_row_hash"] not in btc_hashes
        ):
            raise ValueError("Forward score references unobserved/fake BTC row")
    stale_rows=[r["observation_date_utc"] for r in btc
                if not _was_captured_prospectively(r)]
    valid=[r for r in btc if _was_captured_prospectively(r)]
    quote_after_market_days=[]
    for row in ibit:
        date=dt.date.fromisoformat(row["market_session_date_sydney"])
        stamp=dt.datetime.fromisoformat(row["captured_at_utc"])
        if stamp.tzinfo is None or stamp.astimezone(SYDNEY).date()!=date:
            raise ValueError("Invalid Sydney date against recorded capture instant")
        if stamp.astimezone(SYDNEY).time()<dt.time(17) or date.weekday()>=5:
            raise ValueError("Non-prospective ASX quote in immutable research tape")
        if row["symbol"]!="ASX:IBIT" or row["currency"]!="AUD" or (
            row["is_confirmed_broker_fill"]!="False"
        ):
            raise ValueError("Wrong ETF/currency or fabricated broker execution")
        quote_after_market_days.append(date)
    gaps=(int((btc_days[-1]-btc_days[0]).days+1-len(btc_days))
          if btc_days else 0)
    max_diff=None
    if btc:
        try:
            max_diff=max(float(x["source_crosscheck_max_diff_pct"]) for x in btc)
        except (ValueError,TypeError):
            raise ValueError("Unparseable BTC source crosscheck diagnostic")
        if not 0<=max_diff<=100:
            raise ValueError("Invalid public BTC source crosscheck diagnostic")
    # Do not mistake the immutable 15/17-Oct legacy 6.29% date-alignment
    # audit for the quality of the most recently SAVED prospective data.
    # This is a subset of preserved tape rows, NOT an unrecorded spot tick
    # or a broker executable quote. Retain original all-history warning.
    last_five=btc[-5:]
    latest_saved_diff=(float(btc[-1]["source_crosscheck_max_diff_pct"])
                       if btc else None)
    last_five_max=(max(float(row["source_crosscheck_max_diff_pct"])
                       for row in last_five) if last_five else None)
    recent_window_all_prospective=bool(last_five) and all(
        _was_captured_prospectively(row) for row in last_five
    )
    last_five_dates=[row["observation_date_utc"] for row in last_five]
    freshness=(t.date()-btc_days[-1]).days if btc_days else None
    asx_freshness=(t.astimezone(SYDNEY).date()-asx_days[-1]).days if asx_days else None
    return {
        "audit_at_utc":t.isoformat(),
        "report_type":"read_only_data_quality_not_investment_validation",
        "active_cycle_buy_sell_changes":False,
        "new_ntfy_messages":0,
        "total_frozen_BTC_market_snapshots":len(btc),
        "genuine_following_day_UTC_BTC_snapshots":len(valid),
        "historical_not_prospective_BTC_snapshot_dates":stale_rows,
        "BTC_snapshot_missing_calendar_days_between_endpoints":gaps,
        "latest_observed_BTC_UTC_day":str(btc_days[-1]) if btc_days else None,
        "BTC_close_age_calendar_days":freshness,
        "recorded_forward_7_30_90d_outcomes":len(results),
        "frozen_ASX_IBIT_Sydney_session_quotes":len(ibit),
        "latest_ASX_IBIT_Sydney_date":str(asx_days[-1]) if asx_days else None,
        "ASX_session_close_age_calendar_days":asx_freshness,
        "ASX_close_is_executable_broker_quote":False,
        "max_historical_BTC_source_crosscheck_dispersion_pct":max_diff,
        "latest_saved_BTC_source_crosscheck_dispersion_pct":latest_saved_diff,
        "last_five_saved_BTC_source_crosscheck_max_dispersion_pct":last_five_max,
        "last_five_saved_BTC_source_dates_utc":last_five_dates,
        "last_five_saved_BTC_sources_all_prospective":recent_window_all_prospective,
        "historical_source_crosscheck_peak_outside_last_five":(
            max_diff is not None and last_five_max is not None
            and max_diff>last_five_max
        ),
        "public_provider_dispersion_requires_review":(
            max_diff is not None and
            max_diff>=BTC_CROSSCHECK_MANUAL_REVIEW_THRESHOLD_PCT),
        "pipeline_smoke_test_targets":{
            "prospective_BTC_UTC_snapshots":BTC_PIPELINE_SAMPLE_TARGET,
            "distinct_ASX_session_closes":ASX_PIPELINE_SAMPLE_TARGET,
        },
        "pipeline_sample_counts_met":(
            len(valid)>=BTC_PIPELINE_SAMPLE_TARGET and
            len(ibit)>=ASX_PIPELINE_SAMPLE_TARGET),
        "can_claim_out_of_sample_trading_edge":False,
        "eligible_for_automatic_live_rule_promotion":False,
        "readiness_status":"NOT_READY_FOR_LIVE_STRATEGY_PROMOTION",
    }


def main(argv=None):
    p=argparse.ArgumentParser()
    p.add_argument("--data-dir",type=Path,default=TARGET_DIR)
    p.add_argument("--output",type=Path,default=Path(
        "artifacts/forward_readiness.json"))
    args=p.parse_args(argv)
    data=args.data_dir
    result=inspect_forward_tapes(
        _load(data/SIGNAL_TAPE),
        _load(data/"asx_ibit_closes_forward.csv"),
        _load(data/OUTCOME_TAPE),
        now=dt.datetime.now(dt.timezone.utc))
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps(result,indent=2,sort_keys=True)+"\n")
    print(json.dumps(result,sort_keys=True))


if __name__=="__main__":
    main()
