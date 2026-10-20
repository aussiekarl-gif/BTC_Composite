"""Existing paired Kraken/Coinbase job is only an optional research fallback."""
import datetime as dt
from pathlib import Path
import unittest
from zoneinfo import ZoneInfo

from engines.research.cycle_microstructure_mid_session_backup import eligibility

UTC=dt.timezone.utc
SYDNEY=ZoneInfo("Australia/Sydney")
ROOT=Path(__file__).resolve().parents[1]
WORKFLOW=ROOT/".github/workflows/research_btc_paired_microstructure.yml"
MAIN_MODULE=ROOT/"engines/research/cycle_mid_session_signal_tape.py"


def at(day,hour,minute=0):
    return dt.datetime(2026,10,day,hour,minute,tzinfo=SYDNEY)


class PairedWorkflowBestEffortCycleTests(unittest.TestCase):
    def test_middle_of_sydney_day_is_eligible(self):
        x=eligibility(at(21,12,17))
        self.assertTrue(x["eligible"])
        self.assertEqual(x["sydney_date"],"2026-10-21")
        self.assertFalse(x["backfill_allowed"])
        self.assertFalse(x["planned_github_schedule_proves_capture_time"])
        self.assertEqual(x["new_ntfy_messages"],0)
        self.assertEqual(x["broker_orders"],0)

    def test_mid_session_window_exact_boundaries(self):
        self.assertFalse(eligibility(at(21,10,59))["eligible"])
        self.assertTrue(eligibility(at(21,11,0))["eligible"])
        self.assertTrue(eligibility(at(21,14,59))["eligible"])
        self.assertFalse(eligibility(at(21,15,0))["eligible"])

    def test_github_delayed_2026_oct20_slot_at_16_59_sydney_cannot_backfill(self):
        x=eligibility(dt.datetime(2026,10,20,5,59,tzinfo=UTC))
        self.assertFalse(x["eligible"])
        self.assertEqual(x["actual_sydney_local_time"][:16],"2026-10-20T16:59")
        self.assertEqual(x["decision"],"SKIP_ACTUAL_TIME_OUTSIDE_FROZEN_CAPTURE_WINDOW")

    def test_tomorrow_before_window_not_treated_as_yesterdays_early_signal(self):
        x=eligibility(at(22,8,0))
        self.assertFalse(x["eligible"])
        self.assertEqual(x["sydney_date"],"2026-10-22")

    def test_utc_timezone_rollover_matches_sydney_summer(self):
        x=eligibility(dt.datetime(2026,10,21,1,17,tzinfo=UTC))
        self.assertTrue(x["eligible"])
        self.assertEqual(x["actual_sydney_local_time"][:16],"2026-10-21T12:17")

    def test_weekend_and_before_enrolment_skip(self):
        self.assertFalse(eligibility(at(19,12,0))["eligible"])
        self.assertFalse(eligibility(at(24,12,0))["eligible"])
        self.assertFalse(eligibility(at(25,12,0))["eligible"])

    def test_bad_timezone_is_refused(self):
        with self.assertRaisesRegex(ValueError,"timezone-aware"):
            eligibility(dt.datetime(2026,10,21,1,17))

    def test_dst_winter_local_11_am_is_supported(self):
        local=dt.datetime(2027,4,7,11,17,tzinfo=SYDNEY)
        self.assertTrue(eligibility(local)["eligible"])
        self.assertEqual(eligibility(local)["checked_at_utc"][:16],"2027-04-07T01:17")

    def test_cannot_have_two_independent_cron_schedules(self):
        s=WORKFLOW.read_text(encoding="utf-8")
        self.assertEqual(s.count("cron:"),1)
        self.assertIn("17 1,7,13,19 * * *",s)
        self.assertIn("github.event_name == 'schedule'",s)
        self.assertIn("cycle_microstructure_mid_session_backup --is-window",s)
        self.assertIn("python -m engines.research.cycle_mid_session_signal_tape",s)
        self.assertNotIn(r"\${{",s)
        self.assertNotIn("ntfy.sh",s)
        self.assertNotIn("requests.post",s)

    def test_paired_source_publish_runs_before_optional_cycle_sidecar(self):
        s=WORKFLOW.read_text(encoding="utf-8")
        self.assertLess(s.index("Commit ONLY valid new immutable source records"),
                        s.index("Best-effort strictly TIMESTAMPED Cycle mid-session"))
        self.assertLess(s.index("Surface source outages AFTER saving any valid independent records"),
                        s.index("Best-effort strictly TIMESTAMPED Cycle mid-session"))
        self.assertIn("git add -- data/research_forward_validation/kraken_spot_depth_forward.csv "
                      "data/research_forward_validation/coinbase_trade_samples_forward.csv",s)

    def test_late_runner_skips_sources_and_does_not_fabricate_signal(self):
        s=WORKFLOW.read_text(encoding="utf-8")
        p=s.index("name: Best-effort strictly TIMESTAMPED Cycle")
        x=s[p:]
        self.assertLess(x.index("--is-window"),x.index("pip install -r requirements.txt"))
        self.assertLess(x.index("--is-window"),x.index("python -m engines.research.cycle_mid_session_signal_tape >"))
        self.assertIn("if ! cmp -s",x)
        self.assertLess(x.index("if ! cmp -s"),x.index("git add -- \"$path\""))
        self.assertIn("git fetch origin main",x)
        self.assertIn("git rebase origin/main",x)
        self.assertIn("git push origin HEAD:main",x)
        self.assertIn("if-no-files-found: warn",x)

    def test_backup_window_never_extends_original_required_capture_window(self):
        s=MAIN_MODULE.read_text(encoding="utf-8")
        self.assertIn('WINDOW_START=dt.time(11,0)',s)
        self.assertIn('WINDOW_END=dt.time(15,0)',s)
        self.assertIn('FIRST_ELIGIBLE_DATE=dt.date(2026,10,20)',s)


if __name__=="__main__":
    unittest.main()
