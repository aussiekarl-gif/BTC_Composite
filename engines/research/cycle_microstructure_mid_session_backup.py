"""Standard-library ONLY guard for a best-effort research mid-session backup.

Called by the ALREADY SCHEDULED paired Kraken/Coinbase microstructure
research workflow. GitHub's nominal cron is NOT evidence of when it ran.
Only actual local Sydney time between 11:00 and 15:00 on weekdays qualifies.

Market validation/capture/publishing live in the separate, existing,
SHA256-chain-protected Cycle research module and GitHub workflow steps.
This guard itself fetches no provider, reads no portfolio, and sends no ntfy.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
from zoneinfo import ZoneInfo

SYDNEY = ZoneInfo("Australia/Sydney")
FIRST_DATE = dt.date(2026,10,20)
EARLIEST = dt.time(11,0)
LATEST_EXCLUSIVE = dt.time(15,0)


def eligibility(now:dt.datetime) -> dict:
    if not isinstance(now,dt.datetime) or now.tzinfo is None or now.utcoffset() is None:
        raise ValueError("Actual timezone-aware now required for research capture")
    utc = now.astimezone(dt.timezone.utc)
    local = utc.astimezone(SYDNEY)
    eligible = (
        local.date() >= FIRST_DATE
        and local.weekday() < 5
        and EARLIEST <= local.time() < LATEST_EXCLUSIVE
    )
    return {
        "kind":"EXISTING_PAIRED_RESEARCH_WORKFLOW_OPTIONAL_CYCLE_MID_SESSION_GUARD",
        "checked_at_utc":utc.isoformat(),
        "actual_sydney_local_time":local.isoformat(),
        "sydney_date":local.date().isoformat(),
        "eligible":eligible,
        "decision":"ATTEMPT_STRICT_EXISTING_RESEARCH_CAPTURE" if eligible
                   else "SKIP_ACTUAL_TIME_OUTSIDE_FROZEN_CAPTURE_WINDOW",
        "planned_github_schedule_proves_capture_time":False,
        "extra_scheduled_workflows":0,
        "new_ntfy_messages":0,
        "broker_orders":0,
        "portfolio_reads_or_writes":0,
        "backfill_allowed":False,
        "first_record_of_sydney_date_must_win":True,
    }


def main(argv=None) -> int:
    p=argparse.ArgumentParser(description="No-IO actual Sydney weekday Cycle timing gate")
    p.add_argument("--is-window",action="store_true",
                   help="Exit 0 if currently within Sydney 11:00-15:00 eligible window, 1 otherwise")
    args=p.parse_args(argv)
    x=eligibility(dt.datetime.now(dt.timezone.utc))
    print(json.dumps(x,sort_keys=True))
    return 0 if not args.is_window or x["eligible"] else 1


if __name__=="__main__":
    raise SystemExit(main())
