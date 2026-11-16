"""Read-only 7/14-day audit of PR #267 actual midnight receipt coverage.

Counts only immutable Kraken/Coinbase source rows whose actual HTTP receipt
instants are in 00:00-05:59 UTC. Schedule launches are never observations.
No backfill, source write, trading signal, portfolio access, or notification.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
from pathlib import Path

from engines.research.btc_spot_depth_forward import (
    OUTPUT as KRAKEN_TAPE,
    read_verified_tape as read_kraken_tape,
)
from engines.research.coinbase_trade_samples import (
    OUTPUT as COINBASE_TAPE,
    read_tape as read_coinbase_tape,
)

UTC = dt.timezone.utc
MERGED_AT = dt.datetime.fromisoformat("2026-11-13T10:06:20+00:00")
BASELINE_PAIRED_OBSERVATIONS = 68
BASELINE_MIDNIGHT_PAIRS = 3
MAX_PAIR_SKEW = dt.timedelta(minutes=5)
CHECKPOINT_DAYS = (7, 14)


def _utc(value: dt.datetime | str, label: str) -> dt.datetime:
    try:
        stamp = value if isinstance(value, dt.datetime) else dt.datetime.fromisoformat(str(value))
    except (TypeError, ValueError) as exc:
        raise ValueError(f"Invalid {label}") from exc
    if stamp.tzinfo is None or stamp.utcoffset() is None:
        raise ValueError(f"{label} must be timezone-aware")
    return stamp.astimezone(UTC)


def _slot_floor(receipt: dt.datetime) -> dt.datetime:
    return receipt.replace(
        hour=(receipt.hour // 6) * 6,
        minute=0,
        second=0,
        microsecond=0,
    )


def _receipt_map(rows: list[dict[str, str]], source: str, as_of: dt.datetime):
    result: dict[dt.datetime, dt.datetime] = {}
    for row in rows:
        if not isinstance(row, dict) or not row.get("slot_utc") or not row.get("captured_at_utc"):
            raise ValueError(f"{source} row lacks its slot or actual receipt timestamp")
        slot = _utc(row["slot_utc"], f"{source} slot")
        receipt = _utc(row["captured_at_utc"], f"{source} receipt")
        if receipt > as_of:
            raise ValueError(f"{source} contains a future receipt")
        if slot != _slot_floor(receipt):
            raise ValueError(f"{source} slot does not match actual receipt time")
        if slot in result:
            raise ValueError(f"{source} contains a duplicate six-hour slot")
        result[slot] = receipt
    return result


def _window_metrics(
    kraken: dict[dt.datetime, dt.datetime],
    coinbase: dict[dt.datetime, dt.datetime],
    *,
    cutoff: dt.datetime,
) -> dict:
    k = {
        slot: receipt for slot, receipt in kraken.items()
        if MERGED_AT <= receipt < cutoff
    }
    c = {
        slot: receipt for slot, receipt in coinbase.items()
        if MERGED_AT <= receipt < cutoff
    }
    shared = sorted(set(k) & set(c))
    pairs = [(slot, k[slot], c[slot]) for slot in shared]
    midnight = [
        item for item in pairs
        if item[1].hour < 6 and item[2].hour < 6
    ]
    within_five = [
        item for item in pairs
        if abs(item[1] - item[2]) <= MAX_PAIR_SKEW
    ]
    midnight_within_five = [
        item for item in midnight
        if abs(item[1] - item[2]) <= MAX_PAIR_SKEW
    ]
    baseline_rate = BASELINE_MIDNIGHT_PAIRS / BASELINE_PAIRED_OBSERVATIONS
    observed_rate = len(midnight) / len(pairs) if pairs else None
    return {
        "paired_observations": len(pairs),
        "paired_within_5_minutes": len(within_five),
        "midnight_receipt_time_pairs": len(midnight),
        "midnight_pairs_within_5_minutes": len(midnight_within_five),
        "midnight_pairs_over_5_minutes": len(midnight) - len(midnight_within_five),
        "kraken_only_slots": len(set(k) - set(c)),
        "coinbase_only_slots": len(set(c) - set(k)),
        "baseline": {
            "paired_observations": BASELINE_PAIRED_OBSERVATIONS,
            "midnight_receipt_time_pairs": BASELINE_MIDNIGHT_PAIRS,
            "midnight_coverage_pct": round(baseline_rate * 100, 6),
        },
        "observed_midnight_coverage_pct": (
            round(observed_rate * 100, 6) if observed_rate is not None else None
        ),
        "coverage_change_vs_baseline_percentage_points": (
            round((observed_rate - baseline_rate) * 100, 6)
            if observed_rate is not None else None
        ),
        "midnight_pairs": [
            {
                "slot_utc": slot.isoformat(),
                "kraken_receipt_utc": kraken_receipt.isoformat(),
                "coinbase_receipt_utc": coinbase_receipt.isoformat(),
                "receipt_skew_seconds": abs(
                    (kraken_receipt - coinbase_receipt).total_seconds()
                ),
            }
            for slot, kraken_receipt, coinbase_receipt in midnight
        ],
    }


def audit_midnight_checkpoints(
    kraken_rows: list[dict[str, str]],
    coinbase_rows: list[dict[str, str]],
    *,
    as_of_utc: dt.datetime,
) -> dict:
    """Audit fixed cumulative windows using validated rows and receipt instants."""
    as_of = _utc(as_of_utc, "audit time")
    kraken = _receipt_map(kraken_rows, "Kraken", as_of)
    coinbase = _receipt_map(coinbase_rows, "Coinbase", as_of)

    checkpoints = []
    for days in CHECKPOINT_DAYS:
        due_at = MERGED_AT + dt.timedelta(days=days)
        if as_of < due_at:
            checkpoints.append({
                "days_after_merge": days,
                "status": "CHECKPOINT_NOT_DUE",
                "due_at_utc": due_at.isoformat(),
                "metrics": None,
            })
        else:
            checkpoints.append({
                "days_after_merge": days,
                "status": "COMPLETE_OBSERVED_WINDOW",
                "due_at_utc": due_at.isoformat(),
                "window_start_utc": MERGED_AT.isoformat(),
                "window_end_exclusive_utc": due_at.isoformat(),
                "metrics": _window_metrics(kraken, coinbase, cutoff=due_at),
            })

    interim = _window_metrics(kraken, coinbase, cutoff=as_of)
    return {
        "kind": "PR267_ACTUAL_RECEIPT_TIME_MIDNIGHT_COVERAGE_AUDIT_V1",
        "as_of_utc": as_of.isoformat(),
        "merge": {
            "pull_request": 267,
            "merged_at_utc": MERGED_AT.isoformat(),
            "tracking_issue": 205,
        },
        "status": (
            "CHECKPOINTS_PENDING"
            if all(item["status"] == "CHECKPOINT_NOT_DUE" for item in checkpoints)
            else "AT_LEAST_ONE_CHECKPOINT_DUE"
        ),
        "interim_to_date_not_a_checkpoint": interim,
        "checkpoints": checkpoints,
        "method": {
            "midnight_window_utc": "00:00:00 inclusive to 06:00:00 exclusive",
            "slot_membership_source": "captured_at_utc actual HTTP response receipt",
            "paired_definition": "same six-hour slot present in both independently hash-verified source tapes",
            "baseline_definition": "3 midnight pairs among 68 paired source observations",
            "receipt_skew_quality_limit_minutes": 5,
            "schedule_launches_counted_as_captures": False,
            "rows_after_each_checkpoint_excluded": True,
            "backfill_or_reconstruction": False,
            "source_tapes_modified": False,
            "trading_signals_or_portfolio_modified": False,
            "broker_orders": 0,
            "ntfy_messages": 0,
            "interpretation": "Descriptive capture coverage only; not evidence of market alpha or executable liquidity.",
        },
    }


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        description="Read-only actual-receipt midnight coverage audit for PR #267"
    )
    parser.add_argument(
        "--output", type=Path,
        default=Path("artifacts/btc_midnight_checkpoint_audit.json"),
    )
    parser.add_argument(
        "--as-of-utc",
        help="Optional timezone-aware ISO timestamp for deterministic replay",
    )
    args = parser.parse_args(argv)
    as_of = _utc(args.as_of_utc, "audit time") if args.as_of_utc else dt.datetime.now(UTC)

    # These readers validate each source's immutable schema, chronology and
    # hash chain before any receipt-time coverage calculation is attempted.
    kraken_rows = read_kraken_tape(KRAKEN_TAPE)
    coinbase_rows = read_coinbase_tape(COINBASE_TAPE)
    report = audit_midnight_checkpoints(
        kraken_rows, coinbase_rows, as_of_utc=as_of
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    print(json.dumps(report, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
