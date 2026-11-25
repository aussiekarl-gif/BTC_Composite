"""Read-only integrity guard for the Cowen research source snapshots.

The daily refresh is allowed to publish only complete, hash-consistent source
snapshots whose observation coverage and retrieval timestamps do not regress
against the last committed version. Provider delays are reported, not treated
as alpha or silently filled.
"""
from __future__ import annotations

import argparse
import csv
import datetime as dt
import hashlib
import json
from pathlib import Path
import sys

UTC = dt.timezone.utc
SOURCE_FILES = (
    "explore21/bitcoin-puell-multiple.csv",
    "explore21/bitcoin-mvrv-ratio.csv",
    "explore21/bitcoin-mvrv-z-score.csv",
    "coinmetrics_btc_daily_community.csv",
    "bitcoin_network_daily_aethereal.csv",
    "obm_cdd_btcxdays_daily.csv",
)


class SnapshotGuardError(ValueError):
    """A source snapshot is incomplete, inconsistent, or regresses coverage."""


def _parse_date(value: str, label: str) -> dt.date:
    try:
        return dt.date.fromisoformat(str(value).strip()[:10])
    except (TypeError, ValueError) as exc:
        raise SnapshotGuardError(f"{label}: invalid ISO date {value!r}") from exc


def _parse_instant(value: str, label: str) -> dt.datetime:
    try:
        stamp = dt.datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except (TypeError, ValueError) as exc:
        raise SnapshotGuardError(f"{label}: invalid ISO timestamp") from exc
    if stamp.tzinfo is None or stamp.utcoffset() is None:
        raise SnapshotGuardError(f"{label}: timestamp must include timezone")
    return stamp.astimezone(UTC)


def inspect_snapshot(root: Path, relative: str, *, as_of_utc: dt.datetime) -> dict:
    """Validate CSV, sidecar, hash, row count, dates and receipt timestamp."""
    root = Path(root)
    path = root / relative
    sidecar = path.with_suffix(".metadata.json")
    if not path.is_file() or not sidecar.is_file():
        raise SnapshotGuardError(f"{relative}: CSV or metadata sidecar is missing")
    raw = path.read_bytes()
    try:
        metadata = json.loads(sidecar.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise SnapshotGuardError(f"{relative}: invalid metadata sidecar") from exc
    if metadata.get("sha256_csv") != hashlib.sha256(raw).hexdigest():
        raise SnapshotGuardError(f"{relative}: CSV SHA-256 does not match metadata")

    try:
        with path.open("r", encoding="utf-8", newline="") as handle:
            reader = csv.DictReader(handle)
            headers = reader.fieldnames or []
            if not headers or headers[0] not in ("date_utc", "date"):
                raise SnapshotGuardError(f"{relative}: first CSV column must be date_utc/date")
            rows = list(reader)
    except (OSError, UnicodeDecodeError, csv.Error) as exc:
        raise SnapshotGuardError(f"{relative}: CSV cannot be read") from exc
    if not rows or any(None in row or any(v is None for v in row.values()) for row in rows):
        raise SnapshotGuardError(f"{relative}: empty or malformed CSV rows")
    dates = [_parse_date(row[headers[0]], f"{relative} row date") for row in rows]
    if any(a >= b for a, b in zip(dates, dates[1:])):
        raise SnapshotGuardError(f"{relative}: duplicate or non-monotonic dates")
    if int(metadata.get("observations", -1)) != len(rows):
        raise SnapshotGuardError(f"{relative}: metadata observation count disagrees with CSV")
    if metadata.get("first_date_utc") != dates[0].isoformat():
        raise SnapshotGuardError(f"{relative}: metadata first date disagrees with CSV")
    if metadata.get("last_date_utc") != dates[-1].isoformat():
        raise SnapshotGuardError(f"{relative}: metadata last date disagrees with CSV")
    retrieved = _parse_instant(metadata.get("retrieved_at_utc"), f"{relative} retrieval")
    now = as_of_utc.astimezone(UTC)
    if retrieved > now + dt.timedelta(minutes=5):
        raise SnapshotGuardError(f"{relative}: metadata retrieval timestamp is in the future")
    if dates[-1] > now.date() + dt.timedelta(days=1):
        raise SnapshotGuardError(f"{relative}: source observation date is in the future")
    return {
        "path": relative,
        "first_date_utc": dates[0].isoformat(),
        "last_date_utc": dates[-1].isoformat(),
        "observations": len(rows),
        "retrieved_at_utc": retrieved.isoformat(),
        "source_lag_days": (now.date() - dates[-1]).days,
        "sha256_csv": metadata["sha256_csv"],
    }


def validate_snapshot_set(
    baseline_root: Path,
    candidate_root: Path,
    *,
    as_of_utc: dt.datetime | None = None,
) -> dict:
    """Reject corruption/truncation/regression before the workflow publishes."""
    if as_of_utc is None:
        as_of_utc = dt.datetime.now(UTC)
    if as_of_utc.tzinfo is None or as_of_utc.utcoffset() is None:
        raise SnapshotGuardError("As-of timestamp must be timezone-aware")
    report = []
    for relative in SOURCE_FILES:
        previous = inspect_snapshot(Path(baseline_root), relative, as_of_utc=as_of_utc)
        current = inspect_snapshot(Path(candidate_root), relative, as_of_utc=as_of_utc)
        if current["first_date_utc"] > previous["first_date_utc"]:
            raise SnapshotGuardError(f"{relative}: historical coverage start regressed")
        if current["last_date_utc"] < previous["last_date_utc"]:
            raise SnapshotGuardError(f"{relative}: latest observation date regressed")
        if current["observations"] < previous["observations"]:
            raise SnapshotGuardError(f"{relative}: observation count regressed")
        if current["retrieved_at_utc"] < previous["retrieved_at_utc"]:
            raise SnapshotGuardError(f"{relative}: retrieval timestamp regressed")
        report.append(current)
    return {
        "status": "PASS",
        "snapshot_count": len(report),
        "sources": report,
        "interpretation": (
            "Integrity and monotonic-coverage checks passed. Source lag is reported "
            "for research context; this does not validate component formulas, "
            "point-in-time history, the composite, or investment alpha."
        ),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--baseline", type=Path, required=True)
    parser.add_argument("--candidate", type=Path, required=True)
    args = parser.parse_args()
    try:
        report = validate_snapshot_set(args.baseline, args.candidate)
    except SnapshotGuardError as exc:
        print(json.dumps({"status": "REJECTED", "reason": str(exc)}, sort_keys=True))
        return 2
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())
