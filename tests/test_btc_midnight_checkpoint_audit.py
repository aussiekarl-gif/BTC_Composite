import datetime as dt
import unittest

from engines.research.btc_midnight_checkpoint_audit import (
    MERGED_AT,
    audit_midnight_checkpoints,
)

UTC = dt.timezone.utc


def stamp(value):
    return dt.datetime.fromisoformat(value.replace("Z", "+00:00"))


def row(receipt):
    captured = stamp(receipt)
    slot = captured.replace(
        hour=(captured.hour // 6) * 6,
        minute=0, second=0, microsecond=0,
    )
    return {
        "slot_utc": slot.isoformat(),
        "captured_at_utc": captured.isoformat(),
    }


def pair(k, c):
    return [row(k)], [row(c)]


class MidnightCheckpointAuditTests(unittest.TestCase):
    def test_checkpoints_are_not_reported_before_seven_days(self):
        report = audit_midnight_checkpoints(
            [], [], as_of_utc=MERGED_AT + dt.timedelta(days=6, hours=23)
        )
        self.assertEqual(report["status"], "CHECKPOINTS_PENDING")
        self.assertEqual(
            [x["status"] for x in report["checkpoints"]],
            ["CHECKPOINT_NOT_DUE", "CHECKPOINT_NOT_DUE"],
        )
        self.assertIsNone(report["checkpoints"][0]["metrics"])

    def test_actual_midnight_receipts_not_nominal_schedule_are_counted(self):
        k = [
            row("2026-11-14T00:17:00Z"),
            row("2026-11-14T06:17:00Z"),
        ]
        c = [
            row("2026-11-14T00:18:00Z"),
            row("2026-11-14T06:18:00Z"),
        ]
        report = audit_midnight_checkpoints(
            k, c, as_of_utc=MERGED_AT + dt.timedelta(days=8)
        )
        metrics = report["checkpoints"][0]["metrics"]
        self.assertEqual(metrics["paired_observations"], 2)
        self.assertEqual(metrics["midnight_receipt_time_pairs"], 1)
        self.assertEqual(metrics["midnight_pairs_within_5_minutes"], 1)
        self.assertAlmostEqual(metrics["baseline"]["midnight_coverage_pct"], 3 / 68 * 100, places=5)

    def test_six_am_is_outside_midnight_window(self):
        k, c = pair("2026-11-14T06:00:00Z", "2026-11-14T06:01:00Z")
        report = audit_midnight_checkpoints(
            k, c, as_of_utc=MERGED_AT + dt.timedelta(days=8)
        )
        metrics = report["checkpoints"][0]["metrics"]
        self.assertEqual(metrics["paired_observations"], 1)
        self.assertEqual(metrics["midnight_receipt_time_pairs"], 0)

    def test_055959_is_inside_midnight_window(self):
        k, c = pair("2026-11-14T05:59:59Z", "2026-11-14T05:59:58Z")
        report = audit_midnight_checkpoints(
            k, c, as_of_utc=MERGED_AT + dt.timedelta(days=8)
        )
        self.assertEqual(
            report["checkpoints"][0]["metrics"]["midnight_receipt_time_pairs"], 1
        )

    def test_six_minute_skew_is_reported_but_not_quality_matched(self):
        k, c = pair("2026-11-14T00:17:00Z", "2026-11-14T00:23:00Z")
        report = audit_midnight_checkpoints(
            k, c, as_of_utc=MERGED_AT + dt.timedelta(days=8)
        )
        metrics = report["checkpoints"][0]["metrics"]
        self.assertEqual(metrics["paired_observations"], 1)
        self.assertEqual(metrics["midnight_receipt_time_pairs"], 1)
        self.assertEqual(metrics["midnight_pairs_within_5_minutes"], 0)
        self.assertEqual(metrics["midnight_pairs_over_5_minutes"], 1)

    def test_one_sided_source_capture_is_not_a_pair(self):
        k = [row("2026-11-14T00:17:00Z")]
        report = audit_midnight_checkpoints(
            k, [], as_of_utc=MERGED_AT + dt.timedelta(days=8)
        )
        metrics = report["checkpoints"][0]["metrics"]
        self.assertEqual(metrics["paired_observations"], 0)
        self.assertEqual(metrics["midnight_receipt_time_pairs"], 0)
        self.assertEqual(metrics["kraken_only_slots"], 1)

    def test_both_sources_must_be_received_after_merge(self):
        k, c = pair("2026-11-13T09:55:00Z", "2026-11-13T10:07:00Z")
        report = audit_midnight_checkpoints(
            k, c, as_of_utc=MERGED_AT + dt.timedelta(days=8)
        )
        self.assertEqual(report["checkpoints"][0]["metrics"]["paired_observations"], 0)

    def test_seven_day_window_excludes_later_observations(self):
        k = [
            row("2026-11-14T00:17:00Z"),
            row("2026-11-22T00:17:00Z"),
        ]
        c = [
            row("2026-11-14T00:18:00Z"),
            row("2026-11-22T00:18:00Z"),
        ]
        report = audit_midnight_checkpoints(
            k, c, as_of_utc=MERGED_AT + dt.timedelta(days=15)
        )
        seven = report["checkpoints"][0]["metrics"]
        fourteen = report["checkpoints"][1]["metrics"]
        self.assertEqual(seven["paired_observations"], 1)
        self.assertEqual(seven["midnight_receipt_time_pairs"], 1)
        self.assertEqual(fourteen["paired_observations"], 2)
        self.assertEqual(fourteen["midnight_receipt_time_pairs"], 2)

    def test_checkpoint_is_due_at_exact_seven_day_boundary(self):
        report = audit_midnight_checkpoints(
            [], [], as_of_utc=MERGED_AT + dt.timedelta(days=7)
        )
        self.assertEqual(
            report["checkpoints"][0]["status"], "COMPLETE_OBSERVED_WINDOW"
        )
        self.assertEqual(
            report["checkpoints"][1]["status"], "CHECKPOINT_NOT_DUE"
        )

    def test_duplicate_slots_are_rejected_not_silently_deduplicated(self):
        k = [
            row("2026-11-14T00:17:00Z"),
            row("2026-11-14T00:18:00Z"),
        ]
        c = [row("2026-11-14T00:19:00Z")]
        with self.assertRaisesRegex(ValueError, "duplicate"):
            audit_midnight_checkpoints(
                k, c, as_of_utc=MERGED_AT + dt.timedelta(days=8)
            )

    def test_slot_label_cannot_override_actual_receipt_time(self):
        k = [row("2026-11-14T06:17:00Z")]
        c = [row("2026-11-14T06:18:00Z")]
        k[0]["slot_utc"] = "2026-11-14T00:00:00+00:00"
        with self.assertRaisesRegex(ValueError, "does not match actual receipt"):
            audit_midnight_checkpoints(
                k, c, as_of_utc=MERGED_AT + dt.timedelta(days=8)
            )

    def test_future_receipt_is_rejected(self):
        k, c = pair("2026-11-14T00:17:00Z", "2026-11-14T00:18:00Z")
        with self.assertRaisesRegex(ValueError, "future receipt"):
            audit_midnight_checkpoints(
                k, c, as_of_utc=MERGED_AT + dt.timedelta(hours=1)
            )

    def test_naive_audit_time_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "timezone-aware"):
            audit_midnight_checkpoints([], [], as_of_utc=dt.datetime(2026, 11, 20))

    def test_no_schedule_or_side_effect_claims(self):
        report = audit_midnight_checkpoints(
            [], [], as_of_utc=MERGED_AT + dt.timedelta(days=1)
        )
        method = report["method"]
        self.assertFalse(method["schedule_launches_counted_as_captures"])
        self.assertFalse(method["backfill_or_reconstruction"])
        self.assertFalse(method["source_tapes_modified"])
        self.assertFalse(method["trading_signals_or_portfolio_modified"])
        self.assertEqual(method["broker_orders"], 0)
        self.assertEqual(method["ntfy_messages"], 0)


if __name__ == "__main__":
    unittest.main()
