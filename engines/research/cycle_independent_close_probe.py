"""Read-only live Coinbase/Kraken completed-close acceptance probe.

No trading, notifications, portfolio access, source fallback or persistent data.
Exit nonzero on provider failures, missing yesterday, or close disagreement.
"""
from __future__ import annotations

import datetime as dt
import json
import sys

from engines.research.cycle_coinbase_daily_reference import (
    compare_coinbase_kraken, fetch_completed_coinbase_daily,
)
from engines.research.cycle_forward_kraken_bridge import fetch_completed_kraken_daily


def main() -> int:
    today = dt.datetime.now(dt.timezone.utc).date().isoformat()
    report = {"research_only": True, "asof_utc": today,
              "trading_enabled": False, "notification_sent": False}
    try:
        coinbase = fetch_completed_coinbase_daily(utc_today=today)
        kraken = fetch_completed_kraken_daily(utc_today=today)
        report.update(compare_coinbase_kraken(coinbase, kraken, utc_today=today))
    except Exception as exc:
        report["status"] = "UNVERIFIED"
        report["error_type"] = type(exc).__name__
        report["error"] = str(exc)[:300]
        print(json.dumps(report, sort_keys=True))
        return 1
    print(json.dumps(report, sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())
