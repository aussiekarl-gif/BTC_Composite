"""Research-only ASX:IBIT after-close capture fallback on EXISTING paired BTC job.

No additional workflow schedule, notification, trading or personal portfolio.
Allows an ACTUAL future Sydney weekday 17:00-23:59 close retrieval.
The provider MUST return that very Sydney date's completed Yahoo IBIT.AX
daily candle, which is NOT an executable ASX bid, offer or broker fill.

Unlike the original capture helper, the capture instant is recorded AFTER
provider receipt; this forbids a slow cross-midnight HTTP fetch from being
backdated to the previous market session.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
from pathlib import Path
from zoneinfo import ZoneInfo

from engines.research.ibit_asx_forward_close_tape import (
    OUTPUT, capture_once, fetch_yahoo_asx_daily_candle,
)

UTC=dt.timezone.utc
SYDNEY=ZoneInfo("Australia/Sydney")
FIRST=dt.date(2026,10,20)
START=dt.time(17,0)


def eligibility(now:dt.datetime)->dict:
    if not isinstance(now,dt.datetime) or now.tzinfo is None or now.utcoffset() is None:
        raise ValueError("Actual timezone-aware public-candle receipt timestamp required")
    instant=now.astimezone(UTC)
    local=instant.astimezone(SYDNEY)
    permitted=local.date()>=FIRST and local.weekday()<5 and local.time()>=START
    return {
        "kind":"ASX_IBIT_EXISTING_PAIRED_BTC_SCHEDULE_OPTIONAL_AFTER_CLOSE_RESEARCH",
        "checked_actual_utc":instant.isoformat(),
        "actual_sydney_local_time":local.isoformat(),
        "research_sydney_session":local.date().isoformat(),
        "eligible":permitted,
        "reason":"eligible_post_17_sydney_completed_same_day_only" if permitted
                 else "no_eligible_completed_same_sydney_weekday",
        "no_weekday_backfill":True,
        "no_new_schedule":True,
        "source_is_executable_broker_quote":False,
        "broker_orders":0,"ntfy_sent":0,"portfolio_writes":0,
    }


def attempt(*,clock=lambda:dt.datetime.now(UTC),
            fetcher=fetch_yahoo_asx_daily_candle,
            path=OUTPUT)->dict:
    begin=clock()
    gate=eligibility(begin)
    if not gate["eligible"]:
        return {"status":"skipped_actual_time_outside_session","gate":gate,
                "provider_requested":False,"wrote_close":False,
                "broker_orders":0,"ntfy_sent":0}
    # Fetch once; the actual receipt, not GitHub's scheduled date or
    # beginning of the request, must determine the source-vintage clock.
    payload=fetcher()
    received=clock()
    end_gate=eligibility(received)
    if (not end_gate["eligible"]
            or end_gate["research_sydney_session"]!=gate["research_sydney_session"]):
        return {"status":"skipped_provider_receipt_crossed_sydney_date_or_window",
                "gate":gate,"received_gate":end_gate,"provider_requested":True,
                "wrote_close":False,"broker_orders":0,"ntfy_sent":0}
    # Reuse the ORIGINAL same-Sydney-day OHLC, symbol/currency, SHA-chain
    # and no-duplicate/no-backfill validation with a pre-fetched payload.
    report=capture_once(path=path,now=received,fetcher=lambda:payload)
    return {**report,"gate":gate,"received_gate":end_gate,
            "provider_requested":True,"capture_instant_is_after_fetch":True,
            "broker_orders":0,"ntfy_sent":0,"portfolio_writes":0}


def main(argv=None):
    p=argparse.ArgumentParser(description="Existing paired BTC job ASX AUD research fallback, no trading")
    p.add_argument("--is-window",action="store_true",
                   help="Pure time probe (no provider call or file write), exit 1 if outside")
    p.add_argument("--output",type=Path,default=OUTPUT)
    p.add_argument("--report",type=Path,default=Path("artifacts/optional_asx_close_from_paired.json"))
    args=p.parse_args(argv)
    if args.is_window:
        r=eligibility(dt.datetime.now(UTC))
        print(json.dumps(r,sort_keys=True))
        return 0 if r["eligible"] else 1
    r=attempt(path=args.output)
    args.report.parent.mkdir(parents=True,exist_ok=True)
    args.report.write_text(json.dumps(r,sort_keys=True,indent=2)+"\n")
    print(json.dumps(r,sort_keys=True))
    if r.get("status","").startswith("skipped"):
        print("::notice::No NEW actual same-Sydney-day verified ASX indicative candle; do not backfill")
    return 0


if __name__=="__main__":
    raise SystemExit(main())
