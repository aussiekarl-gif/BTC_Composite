"""Synthetic offline timing tests; no live-source writes."""
import datetime as dt
import unittest

from engines.research.btc_microstructure_capture_coverage import summarize_slots

UTC = dt.timezone.utc


def row(slot, receipt=None):
    s = dt.datetime.fromisoformat(slot)
    r = dt.datetime.fromisoformat(receipt or slot)
    return {
        "slot_utc": s.isoformat(),
        "captured_at_utc": r.isoformat(),
        "research_signal": "OBSERVATION_ONLY_NO_TRADE",
    }


class CoverageTests(unittest.TestCase):
    def setUp(self):
        self.now = dt.datetime(2026, 11, 1, tzinfo=UTC)

    def test_missing_midnight_not_backfilled_from_later_capture(self):
        first = row("2026-10-30T18:00:00+00:00", "2026-10-30T22:27:54+00:00")
        later = row("2026-10-31T06:00:00+00:00", "2026-10-31T06:58:43+00:00")
        report = summarize_slots([first, later], [first, later], as_of_utc=self.now)
        self.assertEqual(report["expected_slots_between_first_and_last"], 3)
        self.assertEqual(report["both_providers_missing_slots_utc"], ["2026-10-31T00:00:00+00:00"])
        self.assertFalse(report["missed_slots_backfilled"])

    def test_skewed_pair_not_counted_as_valid(self):
        k = row("2026-10-31T12:00:00+00:00", "2026-10-31T12:01:00+00:00")
        c = row("2026-10-31T12:00:00+00:00", "2026-10-31T12:07:01+00:00")
        report = summarize_slots([k], [c], as_of_utc=self.now)
        self.assertEqual(report["paired_slots"], 1)
        self.assertEqual(report["paired_within_five_minutes"], 0)
        self.assertEqual(len(report["paired_outside_five_minutes_slots_utc"]), 1)

    def test_equal_rounded_receipts_not_causal_execution(self):
        k = row("2026-10-31T12:00:00+00:00", "2026-10-31T12:01:00+00:00")
        report = summarize_slots([k], [k], as_of_utc=self.now)
        self.assertEqual(report["identical_stored_receipt_timestamps"], 1)
        self.assertFalse(report["after_cost_trade_advantage_proven"])

    def test_provider_only_gap(self):
        a = row("2026-10-31T06:00:00+00:00")
        b = row("2026-10-31T12:00:00+00:00")
        report = summarize_slots([a, b], [b], as_of_utc=self.now)
        self.assertEqual(report["kraken_missing_slots_utc"], [])
        self.assertEqual(report["coinbase_missing_slots_utc"], ["2026-10-31T06:00:00+00:00"])

    def test_reject_duplicate_or_out_of_order(self):
        a = row("2026-10-31T06:00:00+00:00")
        b = row("2026-10-31T12:00:00+00:00")
        for records in ([a, a], [b, a]):
            with self.subTest(records=records), self.assertRaises(ValueError):
                summarize_slots(records, [], as_of_utc=self.now)

    def test_reject_wrong_slot_or_future_receipt(self):
        wrong = row("2026-10-31T00:00:00+00:00", "2026-10-31T06:58:43+00:00")
        future = row("2026-11-01T00:00:00+00:00")
        for record in (wrong, future):
            with self.subTest(record=record), self.assertRaises(ValueError):
                summarize_slots([record], [], as_of_utc=self.now - dt.timedelta(hours=1))

    def test_empty_data_not_false_success(self):
        report = summarize_slots([], [], as_of_utc=self.now)
        self.assertEqual(report["status"], "NO_OBSERVATIONS")


if __name__ == "__main__":
    unittest.main()
