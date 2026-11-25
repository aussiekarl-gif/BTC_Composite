"""Regression tests for the Cowen research source-snapshot integrity guard."""
from __future__ import annotations

import csv
import datetime as dt
import hashlib
import json
from pathlib import Path
import tempfile
import unittest

from engines.research.cowen_onchain_snapshot_guard import (
    SOURCE_FILES,
    SnapshotGuardError,
    validate_snapshot_set,
)

UTC = dt.timezone.utc
AS_OF = dt.datetime.fromisoformat("2026-11-26T00:00:00+00:00")


def write_snapshot(root: Path, relative: str, dates, retrieved, *, metadata_override=None, corrupt_hash=False):
    path = root / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle, lineterminator="\n")
        writer.writerow(["date_utc", "metric"])
        for i, day in enumerate(dates):
            writer.writerow([day, i + 1])
    raw = path.read_bytes()
    metadata = {
        "first_date_utc": dates[0],
        "last_date_utc": dates[-1],
        "observations": len(dates),
        "retrieved_at_utc": retrieved,
        "sha256_csv": hashlib.sha256(raw).hexdigest(),
    }
    if corrupt_hash:
        metadata["sha256_csv"] = "0" * 64
    if metadata_override:
        metadata.update(metadata_override)
    path.with_suffix(".metadata.json").write_text(
        json.dumps(metadata), encoding="utf-8"
    )


class SnapshotGuardTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.base = Path(self.temp.name) / "base"
        self.candidate = Path(self.temp.name) / "candidate"
        self.base.mkdir()
        self.candidate.mkdir()
        for relative in SOURCE_FILES:
            write_snapshot(
                self.base, relative, ["2026-11-22", "2026-11-23"],
                "2026-11-24T14:00:00+00:00",
            )
            write_snapshot(
                self.candidate, relative, ["2026-11-22", "2026-11-23", "2026-11-24"],
                "2026-11-25T14:00:00+00:00",
            )

    def tearDown(self):
        self.temp.cleanup()

    def test_accepts_complete_non_regressing_sources_and_reports_lag(self):
        result = validate_snapshot_set(self.base, self.candidate, as_of_utc=AS_OF)
        self.assertEqual(result["status"], "PASS")
        self.assertEqual(result["snapshot_count"], 6)
        self.assertTrue(all(source["observations"] == 3 for source in result["sources"]))

    def test_rejects_hash_mismatch(self):
        write_snapshot(
            self.candidate, SOURCE_FILES[0], ["2026-11-22", "2026-11-23", "2026-11-24"],
            "2026-11-25T14:00:00+00:00", corrupt_hash=True,
        )
        with self.assertRaisesRegex(SnapshotGuardError, "SHA-256"):
            validate_snapshot_set(self.base, self.candidate, as_of_utc=AS_OF)

    def test_rejects_metadata_row_count_mismatch(self):
        write_snapshot(
            self.candidate, SOURCE_FILES[0], ["2026-11-22", "2026-11-23", "2026-11-24"],
            "2026-11-25T14:00:00+00:00", metadata_override={"observations": 4},
        )
        with self.assertRaisesRegex(SnapshotGuardError, "observation count"):
            validate_snapshot_set(self.base, self.candidate, as_of_utc=AS_OF)

    def test_rejects_latest_date_regression(self):
        write_snapshot(
            self.candidate, SOURCE_FILES[0], ["2026-11-22"],
            "2026-11-25T14:00:00+00:00",
        )
        with self.assertRaisesRegex(SnapshotGuardError, "latest observation date regressed"):
            validate_snapshot_set(self.base, self.candidate, as_of_utc=AS_OF)

    def test_rejects_observation_count_regression(self):
        write_snapshot(
            self.candidate, SOURCE_FILES[0], ["2026-11-22", "2026-11-23"],
            "2026-11-25T14:00:00+00:00",
        )
        with self.assertRaisesRegex(SnapshotGuardError, "observation count regressed"):
            validate_snapshot_set(self.base, self.candidate, as_of_utc=AS_OF)

    def test_rejects_retrieval_timestamp_regression(self):
        write_snapshot(
            self.candidate, SOURCE_FILES[0], ["2026-11-22", "2026-11-23", "2026-11-24"],
            "2026-11-23T14:00:00+00:00",
        )
        with self.assertRaisesRegex(SnapshotGuardError, "retrieval timestamp regressed"):
            validate_snapshot_set(self.base, self.candidate, as_of_utc=AS_OF)

    def test_rejects_duplicate_or_unsorted_dates(self):
        write_snapshot(
            self.candidate, SOURCE_FILES[0], ["2026-11-23", "2026-11-23", "2026-11-24"],
            "2026-11-25T14:00:00+00:00",
        )
        with self.assertRaisesRegex(SnapshotGuardError, "duplicate or non-monotonic"):
            validate_snapshot_set(self.base, self.candidate, as_of_utc=AS_OF)

    def test_rejects_future_retrieval_timestamp(self):
        write_snapshot(
            self.candidate, SOURCE_FILES[0], ["2026-11-22", "2026-11-23", "2026-11-24"],
            "2026-11-26T00:06:00+00:00",
        )
        with self.assertRaisesRegex(SnapshotGuardError, "future"):
            validate_snapshot_set(self.base, self.candidate, as_of_utc=AS_OF)

    def test_rejects_future_observation_date(self):
        write_snapshot(
            self.candidate, SOURCE_FILES[0], ["2026-11-22", "2026-11-23", "2026-11-27"],
            "2026-11-25T14:00:00+00:00",
        )
        with self.assertRaisesRegex(SnapshotGuardError, "source observation date is in the future"):
            validate_snapshot_set(self.base, self.candidate, as_of_utc=AS_OF)


if __name__ == "__main__":
    unittest.main()
