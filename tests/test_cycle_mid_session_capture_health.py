"""A missing scheduled run must be detected without forging market data."""
import datetime as dt
from tempfile import TemporaryDirectory
from pathlib import Path
import unittest
from zoneinfo import ZoneInfo

from engines.research.cycle_mid_session_capture_health import (
    audit_status, read_only_check,
)
SYD=ZoneInfo("Australia/Sydney")

def at(day=20,hour=23,minute=30):
    return dt.datetime(2026,10,day,hour,minute,tzinfo=SYD)

def row(day=20):
    return {
        "research_sydney_date":f"2026-10-{day:02d}",
        "captured_at_utc":at(day,12,31).astimezone(dt.timezone.utc).isoformat(),
        "row_hash":"1"*64,
    }

class NightlyIndependentDetectionTests(unittest.TestCase):
    def test_failed_or_skipped_gitHub_cron_is_visible_after_window(self):
        x=audit_status(now=at(20),rows=[])
        self.assertEqual(x["status"],"MISSING_AFTER_WINDOW_ENDED_DO_NOT_BACKFILL")
        self.assertFalse(x["if_missing_reason_established"])
        self.assertFalse(x["late_observation_permitted"])
        self.assertFalse(x["missed_date_backfilled"])
        self.assertEqual(x["actual_orders_placed"],0)
        self.assertEqual(x["new_ntfy_messages"],0)

    def test_before_3pm_sydney_missing_is_not_an_alert(self):
        x=audit_status(now=at(20,13,59),rows=[])
        self.assertEqual(x["status"],"PENDING_CAPTURE_WINDOW_NOT_YET_CLOSED")

    def test_verified_on_time_actual_row_proves_capture_existed(self):
        x=audit_status(now=at(20,23),rows=[row(20)],run_id="39123",
                       workflow="research scheduled",event="schedule")
        self.assertEqual(x["status"],"GENUINE_VERIFIED_MID_SESSION_SOURCE_IN_CHECKOUT")
        self.assertEqual(x["current_date_source_row_hash"],"1"*64)
        self.assertEqual(x["github_run_id"],"39123")
        self.assertEqual(x["github_event"],"schedule")

    def test_previous_valid_friday_row_not_confused_with_tuesday(self):
        x=audit_status(now=at(20,23),rows=[row(19)])
        self.assertEqual(x["status"],"MISSING_AFTER_WINDOW_ENDED_DO_NOT_BACKFILL")
        self.assertIsNone(x["current_date_source_capture_at_utc"])

    def test_weekends_do_not_claim_missed_scheduled_market_session(self):
        x=audit_status(now=at(24,23),rows=[])
        self.assertEqual(x["status"],"NO_WEEKDAY_RESEARCH_SESSION_EXPECTED")

    def test_no_backfill_on_read_only_file_access(self):
        with TemporaryDirectory() as dir:
            p=Path(dir)/"source_missing.csv"
            r=read_only_check(now=at(20,23),path=p)
            self.assertEqual(r["status"],"MISSING_AFTER_WINDOW_ENDED_DO_NOT_BACKFILL")
            self.assertFalse(p.exists())

    def test_malformed_stale_source_date_is_rejected(self):
        bad=row(20)
        bad["captured_at_utc"]=at(19,12,31).astimezone(dt.timezone.utc).isoformat()
        with self.assertRaisesRegex(ValueError,"backdated"):
            audit_status(now=at(20),rows=[bad])

    def test_duplicate_rows_rejected_not_silently_deduplicated(self):
        with self.assertRaisesRegex(ValueError,"Multiple"):
            audit_status(now=at(20),rows=[row(20),row(20)])

    def test_invalid_naive_time_rejected(self):
        with self.assertRaisesRegex(ValueError,"Timezone-aware"):
            audit_status(now=at(20).replace(tzinfo=None),rows=[])

    def test_date_prior_enrollment_not_expected(self):
        x=audit_status(now=at(19,23),rows=[])
        self.assertEqual(x["status"],"NO_WEEKDAY_RESEARCH_SESSION_EXPECTED")

if __name__=="__main__":
    unittest.main()
