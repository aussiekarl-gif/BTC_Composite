"""Deterministic offline acceptance checks for the isolated v2 validator."""
from datetime import datetime, timezone
from engines.research.forward_paper_200wma_v2 import (
    load_config, validate_observation, validate_append, last_completed_monday
)

def test():
    config, _ = load_config()
    now = "2026-11-04T05:00:00Z"
    assert last_completed_monday(now) == "2026-11-02"
    row = {
        "week_end": "2026-11-02",
        "observed_at_utc": "2026-11-04T04:00:00Z",
        "btc_source_at_utc": "2026-11-03T00:01:00Z",
        "vbtc_market_date": "2026-11-02",
        "btc_usd_close": 80000,
        "btc_200wma_usd": 67000,
        "vbtc_trade_reference_aud": 21.4,
        "vbtc_issuer_workbook_sha256": "a" * 64,
    }
    assert validate_append([], row, config, now)
    cases = [
        ({**row, "week_end": "2026-11-09"}, "future week"),
        ({**row, "week_end": "2026-10-26"}, "pre-inception"),
        ({**row, "btc_source_at_utc": "2026-11-01T00:00:00Z"}, "stale BTC"),
        ({**row, "vbtc_market_date": "2026-10-28"}, "stale VBTC"),
        ({**row, "btc_usd_close": -1}, "negative BTC"),
        ({**row, "observed_at_utc": "2026-11-12T00:00:00Z"}, "late capture"),
        ({**row, "vbtc_issuer_workbook_sha256": ""}, "missing digest"),
    ]
    for invalid, name in cases:
        try:
            validate_observation(invalid, config, now)
        except ValueError:
            pass
        else:
            raise AssertionError("Accepted " + name)
    for previous in ("2026-11-02", "2026-10-19"):
        try:
            validate_append([{"week_end": previous}], row, config, now)
        except ValueError:
            pass
        else:
            raise AssertionError("Accepted duplicate or missing week")
    print("VBTC_V2_OFFLINE_VALIDATION_PASS")

if __name__ == "__main__":
    test()
