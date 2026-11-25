"""Puell source calendar diagnostics: synthetic data only, no network."""
import csv
import tempfile
import unittest
from datetime import date, timedelta
from pathlib import Path

from engines.audit.puell_archive_date_alignment_audit import (
    _status, _metric_pair_stats, load_archive, report,
)


class PuellArchiveAlignmentTests(unittest.TestCase):
    def test_detects_following_day_not_as_equivalent_today(self):
        self.assertEqual(_status(.745, 1.678, .7453), "matches_following_day")
        self.assertEqual(_status(.745, .7453, 1.678), "matches_same_day")
        self.assertEqual(_status(.9, .9, .9), "ambiguous")
        self.assertEqual(_status(.8, 1.6, 1.7), "unresolved")

    def test_pair_statistics_show_threshold_disagreement(self):
        score = _metric_pair_stats([(0.9, 1.1), (1.2, 1.2), (0.5, 0.5)])
        self.assertEqual(score["n"], 3)
        self.assertEqual(score["below_1_disagreements"], 1)
        self.assertGreater(score["mean_absolute_error"], 0)

    def test_empty_metrics_do_not_manufacture_validity(self):
        x = report({date(2026, 1, 1): {
            "self": None, "raw": None,
            "issuance_native": None, "price_usd": None,
        }})
        self.assertEqual(x["calendar_complete_cm_puell_rows"], 0)
        self.assertEqual(x["raw_vs_derived_same_day"]["n"], 0)
        self.assertFalse(x["ready_for_trading"])
        self.assertFalse(x["ready_for_production"])
        self.assertTrue(x["raw_time_shift_not_applied"])

    def test_365_calendar_day_warmup_and_missing_source_day(self):
        start = date(2024, 1, 1)
        entries = {}
        for k in range(366):
            day = start + timedelta(days=k)
            entries[day] = {
                "self": None, "raw": None,
                "issuance_native": 400. + (k % 7) * 20,
                "price_usd": 60000.,
            }
        x = report(entries)
        self.assertEqual(x["calendar_complete_cm_puell_rows"], 2)
        del entries[start + timedelta(days=2)]
        y = report(entries)
        self.assertEqual(y["calendar_complete_cm_puell_rows"], 0)

    def test_raw_same_and_next_day_counts_and_streak(self):
        start = date(2024, 1, 1)
        entries = {}
        for k in range(370):
            day = start + timedelta(days=k)
            entries[day] = {
                "self": None, "raw": None,
                "issuance_native": 300. + (k % 13) * 40,
                "price_usd": 60000.,
            }
        # Derive source values only in test fixture, not using future
        # in any trading logic: the detector must show source misalignment.
        rolling = {}
        for k in range(364, 370):
            cur = start + timedelta(days=k)
            vals = [entries[cur-timedelta(days=i)]["issuance_native"]
                    for i in range(365)]
            rolling[cur] = vals[0] / (sum(vals)/365)
        signal = start + timedelta(days=365)
        entries[signal]["raw"] = rolling[signal + timedelta(days=1)]
        entries[signal + timedelta(days=1)]["raw"] = rolling[signal + timedelta(days=2)]
        r = report(entries)
        self.assertEqual(r["raw_vs_derived_following_day"]["n"], 2)
        self.assertEqual(r["alignment_classification"].get(
            "matches_following_day"), 2)
        self.assertTrue(r["longest_consecutive_alignment_streaks"])
        self.assertFalse(r["ready_for_trading"])

    def test_csv_loader_preserves_raw_column_and_rejects_duplicates(self):
        columns = ["date", "Puell Multiple",
                   "raw__puell_multiple__puellmultiple",
                   "cm__IssTotNtv", "cm__PriceUSD"]
        items = [
            dict(zip(columns, ["2024-04-19 00:00:00+00:00", "1.678", ".745",
                               "931.25", "63762.63"])),
            dict(zip(columns, ["2024-04-20 00:00:00+00:00", ".745", ".803",
                               "406.25", "64907.99"])),
        ]
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "audit.csv"
            def write(records):
                with p.open("w", newline="", encoding="utf-8") as stream:
                    w = csv.DictWriter(stream, fieldnames=columns)
                    w.writeheader()
                    w.writerows(records)
            write(items)
            rows = load_archive(p)
            self.assertEqual(rows[date(2024, 4, 19)]["raw"], .745)
            write(items[:1] + items[:1])
            with self.assertRaises(ValueError):
                load_archive(p)


if __name__ == "__main__":
    unittest.main()
