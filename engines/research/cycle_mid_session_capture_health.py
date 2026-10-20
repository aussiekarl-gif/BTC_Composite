"""Research ONLY: independently audit whether prospective mid-session evidence exists.

This checker can run at 23:25 Sydney via the ALREADY EXISTING nightly research
workflow, even if the separate 11:30/12:30 Brisbane GitHub schedules never
started. Its output is an audit STATUS, not a BTC signal, an alert, a
buy/sell instruction, or permission to fill missing earlier trading days.

It reads the original SHA256-linked mid-session tape and can emit a
read-only CI JSON artifact; it never creates or updates the original CSV.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import os
from pathlib import Path
from zoneinfo import ZoneInfo

from engines.research.cycle_mid_session_signal_tape import (
    OUTPUT as MID_TAPE, FIRST_ELIGIBLE_DATE, WINDOW_END, read_tape,
)

SYDNEY = ZoneInfo("Australia/Sydney")
REPORT = Path("artifacts/research_mid_session_capture_health.json")

def latest_completed_sydney_weekday(local:dt.datetime) -> dt.date | None:
    """Use completed CAPTURE WINDOW, not runner wall-clock calendar date.

    A GitHub nightly 23:25 Sydney run can be delayed to 00:25 Wednesday
    or Saturday. It must still check Tuesday or Friday, respectively.
    """
    if (not isinstance(local,dt.datetime) or local.tzinfo is None
        or local.utcoffset() is None):
        raise ValueError("Timezone-aware Sydney audit timestamp required")
    local=local.astimezone(SYDNEY)
    candidate=(local.date() if local.time()>=WINDOW_END
               else local.date()-dt.timedelta(days=1))
    while candidate.weekday()>=5:
        candidate-=dt.timedelta(days=1)
    return candidate if candidate>=FIRST_ELIGIBLE_DATE else None


def audit_status(*, now:dt.datetime, rows:list[dict],
                 run_id:str="", workflow:str="", event:str="") -> dict:
    if not isinstance(now,dt.datetime) or now.tzinfo is None or now.utcoffset() is None:
        raise ValueError("Timezone-aware actual audit time required")
    local=now.astimezone(SYDNEY)
    day=local.date()
    eligible=(day>=FIRST_ELIGIBLE_DATE and day.weekday()<5)
    matched=[r for r in rows if r["research_sydney_date"]==day.isoformat()]
    if len(matched)>1:
        raise ValueError("Multiple different prospective rows for the same Sydney date")
    if not eligible:
        status="NO_WEEKDAY_RESEARCH_SESSION_EXPECTED"
    elif matched:
        stamp=dt.datetime.fromisoformat(matched[0]["captured_at_utc"])
        if stamp.tzinfo is None:
            raise ValueError("Mid-session source receipt lacks timezone")
        if stamp.astimezone(SYDNEY).date()!=day:
            raise ValueError("Mid-session source was backdated or future dated")
        status="GENUINE_VERIFIED_MID_SESSION_SOURCE_IN_CHECKOUT"
    elif local.time()<WINDOW_END:
        status="PENDING_CAPTURE_WINDOW_NOT_YET_CLOSED"
    else:
        status="MISSING_AFTER_WINDOW_ENDED_DO_NOT_BACKFILL"
    completed=latest_completed_sydney_weekday(local)
    completed_rows=([r for r in rows
                     if r["research_sydney_date"]==completed.isoformat()]
                    if completed is not None else [])
    if len(completed_rows)>1:
        raise ValueError("Duplicate most-recent completed Sydney weekday source")
    if completed_rows:
        stamp=dt.datetime.fromisoformat(completed_rows[0]["captured_at_utc"])
        if stamp.tzinfo is None or stamp.utcoffset() is None:
            raise ValueError("Completed source timestamp has no timezone")
        if stamp.astimezone(SYDNEY).date()!=completed:
            raise ValueError("Most recent completed source timestamp backdated")
    completed_status=(
        "NO_COMPLETED_WEEKDAY_SINCE_ENROLMENT" if completed is None
        else "VERIFIED_COMPLETED_WEEKDAY_SOURCE_IN_CHECKOUT" if completed_rows
        else "MISSING_COMPLETED_WEEKDAY_DO_NOT_BACKFILL"
    )
    return {
        "kind":"RESEARCH_MID_SESSION_CAPTURE_HEALTH_READ_ONLY",
        "audited_at_utc":now.astimezone(dt.timezone.utc).isoformat(),
        "audited_sydney_date":day.isoformat(),
        "audited_sydney_local_time":local.isoformat(),
        "expected_capture_window_end_sydney":WINDOW_END.isoformat(),
        "latest_completed_sydney_weekday_checked":(
            completed.isoformat() if completed is not None else None),
        "latest_completed_weekday_status":completed_status,
        "latest_completed_weekday_source_row_hash":(
            completed_rows[0]["row_hash"] if completed_rows else None),
        "latest_completed_weekday_source_captured_at_utc":(
            completed_rows[0]["captured_at_utc"] if completed_rows else None),
        "status":status,
        "verified_rows_in_existing_tape":len(rows),
        "current_date_source_capture_at_utc":(
            matched[0]["captured_at_utc"] if matched else None),
        "current_date_source_row_hash":(matched[0]["row_hash"] if matched else None),
        "github_run_id":str(run_id),
        "github_workflow":str(workflow),
        "github_event":str(event),
        "if_missing_reason_established":False,
        "late_observation_permitted":False,
        "missed_date_backfilled":False,
        "live_strategy_changed":False,
        "actual_orders_placed":0,
        "portfolio_writes":0,
        "new_ntfy_messages":0,
    }


def read_only_check(*,now=None,path=MID_TAPE) -> dict:
    now=now or dt.datetime.now(dt.timezone.utc)
    return audit_status(
        now=now,rows=read_tape(path),
        run_id=os.environ.get("GITHUB_RUN_ID",""),
        workflow=os.environ.get("GITHUB_WORKFLOW",""),
        event=os.environ.get("GITHUB_EVENT_NAME",""),
    )


def main(argv=None):
    parser=argparse.ArgumentParser(description="Read-only BTC Cycle mid-session capture health")
    parser.add_argument("--output",type=Path,default=REPORT)
    args=parser.parse_args(argv)
    result=read_only_check()
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps(result,indent=2,sort_keys=True)+"\n",encoding="utf-8")
    print("MID_SESSION_CAPTURE_HEALTH "+json.dumps(result,sort_keys=True))
    if result["latest_completed_weekday_status"]=="MISSING_COMPLETED_WEEKDAY_DO_NOT_BACKFILL":
        print("::warning::Scheduled BTC Cycle mid-session capture missing for completed Sydney weekday "+
              result["latest_completed_sydney_weekday_checked"]+
              ". No backfill. Check original scheduled Actions workflow run / source and push logs.")


if __name__=="__main__":
    main()
