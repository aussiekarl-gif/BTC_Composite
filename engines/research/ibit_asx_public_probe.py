"""Real read-only public ASX:IBIT AUD Yahoo daily-candle preflight.

Complements (never replaces) immutable prospective ASX close collector.
Reports real provider shape and exact capture/session age. Does NOT save
source observations, access brokers, send ntfy, or substitute US IBIT.

A provider can be temporarily late after market close. A missing completed
same-day candle remains MISSING, never copied from Friday or backfilled.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
from typing import Callable
from zoneinfo import ZoneInfo

from engines.research.ibit_asx_forward_close_tape import (
    read_latest_close,fetch_yahoo_asx_daily_candle,
    NonTradingOrMissingClose,
)

SYDNEY=ZoneInfo("Australia/Sydney")
MIN_OBSERVATION_TIME=dt.time(17,0)
LATE_CHECK_TIME=dt.time(21,0)


def probe(*,now:dt.datetime, fetcher:Callable=fetch_yahoo_asx_daily_candle):
    if (not isinstance(now,dt.datetime) or now.tzinfo is None
        or now.utcoffset() is None):
        raise ValueError("timezone-aware observation instant required")
    utc=now.astimezone(dt.timezone.utc)
    local=utc.astimezone(SYDNEY)
    result={
        "kind":"READ_ONLY_YAHOO_ASX_IBIT_DAILY_AUD_PROVIDER_PROBE",
        "checked_at_utc":utc.isoformat(),
        "sydney_calendar_date":local.date().isoformat(),
        "expected_postclose_session":local.weekday()<5 and local.time()>=MIN_OBSERVATION_TIME,
        "yahoo_is_not_independent_or_executable_broker_quote":True,
        "no_archived_backfills":True,
        "existing_ASX_tape_writes":0,
        "broker_orders":0,
        "ntfy_messages":0,
        "status":"NO_ELIGIBLE_COMPLETED_LOCAL_SESSION",
    }
    if not result["expected_postclose_session"]:
        return result
    try:
        payload=fetcher()
        obs=read_latest_close(payload,captured_at_utc=utc)
    except (NonTradingOrMissingClose,ValueError,KeyError,IndexError,
            TypeError, OSError, RuntimeError) as err:
        result.update({
            "status":"PROVIDER_NOT_READY_OR_REJECTED",
            "source_error_type":type(err).__name__,
            "source_error_reason":str(err)[:250],
            "late_Sydney_provider_problem":local.time()>=LATE_CHECK_TIME,
        })
        return result
    result.update({
        "status":"READY_REAL_COMPLETED_SYDNEY_AUD_CANDLE",
        "market_session_sydney":obs["market_session_date_sydney"],
        "AUD_IBIT_indicative_close":float(obs["reported_close_aud"]),
        "provider_candle_timestamp_utc":obs["provider_daily_candle_timestamp_utc"],
        "capture_at_utc":obs["captured_at_utc"],
        "provider":obs["provider"],
        "symbol":obs["symbol"],
        "currency":obs["currency"],
        "is_confirmed_broker_fill":False,
    })
    return result


def main(argv=None):
    p=argparse.ArgumentParser(description="No-write ASX IBIT public daily candle probe")
    p.add_argument("--fail-after-sydney-21",action="store_true",
                   help="Fail if Sydney weekday after 9pm has no same-day candle")
    args=p.parse_args(argv)
    now=dt.datetime.now(dt.timezone.utc)
    result=probe(now=now)
    print("ASX_IBIT_PUBLIC_PROBE "+json.dumps(result,sort_keys=True))
    if result["status"]=="PROVIDER_NOT_READY_OR_REJECTED":
        print("::warning::Public ASX:IBIT AUD same-day candle unavailable; no fabricated source row")
        if args.fail_after_sydney_21 and result["late_Sydney_provider_problem"]:
            raise SystemExit("Public ASX source still unavailable after 21:00 Sydney")


if __name__=="__main__":
    main()
