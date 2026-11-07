"""Research-only continuity audit: exchange agreement is not historical coverage.

This probe deliberately never merges, interpolates, backfills or trades.
"""
from __future__ import annotations

import datetime as dt
import json
import sys
import pandas as pd

from engines.research.top_signal_horse_race import read_exported_history
from engines.research.cycle_coinbase_daily_reference import (
    fetch_completed_coinbase_daily, compare_coinbase_kraken,
)
from engines.research.cycle_forward_kraken_bridge import fetch_completed_kraken_daily


def audit_continuity(archive, coinbase, kraken, *, utc_today):
    verified = compare_coinbase_kraken(coinbase, kraken, utc_today=utc_today)
    cutoff = archive.index.max()
    if cutoff.tzinfo is None:
        cutoff = cutoff.tz_localize("UTC")
    else:
        cutoff = cutoff.tz_convert("UTC")
    cutoff = cutoff.normalize()
    common = coinbase.index.intersection(kraken.index)
    missing = pd.date_range(cutoff + pd.Timedelta(days=1),
                            pd.Timestamp(utc_today).tz_localize("UTC") - pd.Timedelta(days=1),
                            freq="D", tz="UTC").difference(common)
    return {
        "research_only": True,
        "archive_last_utc": str(cutoff.date()),
        "first_common_exchange_utc": str(common.min().date()),
        "last_common_exchange_utc": str(common.max().date()),
        "exchange_agreement": verified["status"],
        "uncovered_days_after_archive": len(missing),
        "first_uncovered_utc": str(missing.min().date()) if len(missing) else None,
        "last_uncovered_utc": str(missing.max().date()) if len(missing) else None,
        "full_continuity_verified": len(missing) == 0,
        "trading_enabled": False,
    }


def main():
    today = dt.datetime.now(dt.timezone.utc).date().isoformat()
    try:
        archive = read_exported_history()
        coinbase = fetch_completed_coinbase_daily(utc_today=today)
        kraken = fetch_completed_kraken_daily(utc_today=today)
        report = audit_continuity(archive, coinbase, kraken, utc_today=today)
    except Exception as exc:
        print(json.dumps({"research_only": True, "status": "UNVERIFIED",
                          "error_type": type(exc).__name__, "error": str(exc)[:300],
                          "trading_enabled": False}, sort_keys=True))
        return 1
    print(json.dumps(report, sort_keys=True))
    # Gap is a research finding, not a broken probe: report it without authorizing fallback.
    return 0


if __name__ == "__main__":
    sys.exit(main())
