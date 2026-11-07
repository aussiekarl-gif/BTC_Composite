"""Read-only UTC six-hour slot coverage for immutable prospective BTC market tapes.

No signal generation, backfill, live execution, portfolio, or notification writes.
CLI validates both source hash chains with the repository's official readers.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
from pathlib import Path
from typing import Any

UTC = dt.timezone.utc
SLOT_HOURS = 6
MAX_PAIR_SKEW_SECONDS = 300


def _instant(value: str | dt.datetime) -> dt.datetime:
    instant = dt.datetime.fromisoformat(value) if isinstance(value, str) else value
    if not isinstance(instant, dt.datetime) or instant.tzinfo is None or instant.utcoffset() is None:
        raise ValueError("Timestamp must have a UTC offset")
    return instant.astimezone(UTC)


def _index(rows: list[dict[str, str]], *, as_of_utc: dt.datetime, source: str) -> dict[dt.datetime, dt.datetime]:
    found: dict[dt.datetime, dt.datetime] = {}
    previous = None
    for row in rows:
        slot = _instant(row["slot_utc"])
        receipt = _instant(row["captured_at_utc"])
        if (slot.minute or slot.second or slot.microsecond or slot.hour % SLOT_HOURS
                or not slot <= receipt < slot + dt.timedelta(hours=SLOT_HOURS)
                or receipt > as_of_utc or (previous is not None and slot <= previous)
                or row["research_signal"] != "OBSERVATION_ONLY_NO_TRADE"):
            raise ValueError(f"Invalid {source} chronology or paper-only metadata")
        if slot in found:
            raise ValueError(f"Duplicate {source} UTC slot")
        found[slot] = receipt
        previous = slot
    return found


def summarize_slots(
    kraken_rows: list[dict[str, str]],
    coinbase_rows: list[dict[str, str]],
    *,
    as_of_utc: dt.datetime,
) -> dict[str, Any]:
    """Compare actual receipt-based slots; never fabricate a missed observation."""
    now = _instant(as_of_utc)
    books = _index(kraken_rows, as_of_utc=now, source="Kraken")
    trades = _index(coinbase_rows, as_of_utc=now, source="Coinbase")
    observed = set(books) | set(trades)
    if not observed:
        return {
            "kind": "read_only_prospective_coverage_not_trading_alpha",
            "audit_at_utc": now.isoformat(),
            "status": "NO_OBSERVATIONS",
            "kraken_rows": 0,
            "coinbase_rows": 0,
            "expected_slots_between_first_and_last": 0,
        }
    start, end = min(observed), max(observed)
    expected = []
    cursor = start
    while cursor <= end:
        expected.append(cursor)
        cursor += dt.timedelta(hours=SLOT_HOURS)
    both_missing = [s.isoformat() for s in expected if s not in books and s not in trades]
    kraken_missing = [s.isoformat() for s in expected if s not in books]
    coinbase_missing = [s.isoformat() for s in expected if s not in trades]
    paired = sorted(set(books) & set(trades))
    skews = {s: abs((books[s] - trades[s]).total_seconds()) for s in paired}
    within = [s for s in paired if skews[s] <= MAX_PAIR_SKEW_SECONDS]
    equal = [s for s in paired if books[s] == trades[s]]
    return {
        "kind": "read_only_prospective_coverage_not_trading_alpha",
        "audit_at_utc": now.isoformat(),
        "status": "OBSERVED_WITH_GAPS" if kraken_missing or coinbase_missing else "COMPLETE_WITHIN_OBSERVED_RANGE",
        "first_observed_slot_utc": start.isoformat(),
        "last_observed_slot_utc": end.isoformat(),
        "expected_slots_between_first_and_last": len(expected),
        "kraken_rows": len(books),
        "coinbase_rows": len(trades),
        "both_providers_missing_slots_utc": both_missing,
        "kraken_missing_slots_utc": kraken_missing,
        "coinbase_missing_slots_utc": coinbase_missing,
        "paired_slots": len(paired),
        "paired_within_five_minutes": len(within),
        "paired_outside_five_minutes_slots_utc": [s.isoformat() for s in paired if s not in within],
        "identical_stored_receipt_timestamps": len(equal),
        "max_paired_skew_seconds": max(skews.values()) if skews else None,
        "after_cost_trade_advantage_proven": False,
        "missed_slots_backfilled": False,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Read-only actual-time BTC slot coverage audit")
    parser.add_argument("--kraken", type=Path, default=Path("data/research_forward_validation/kraken_spot_depth_forward.csv"))
    parser.add_argument("--coinbase", type=Path, default=Path("data/research_forward_validation/coinbase_trade_samples_forward.csv"))
    parser.add_argument("--output", type=Path, default=None)
    args = parser.parse_args()
    from engines.research.btc_spot_depth_forward import read_verified_tape
    from engines.research.coinbase_trade_samples import read_tape
    report = summarize_slots(read_verified_tape(args.kraken), read_tape(args.coinbase), as_of_utc=dt.datetime.now(UTC))
    rendered = json.dumps(report, indent=2, sort_keys=True) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered, encoding="utf-8")
    print(rendered, end="")


if __name__ == "__main__":
    main()
