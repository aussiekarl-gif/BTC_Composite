"""Capture priority and GitHub cron delay hedge: NO trading side effects.

A scheduled run may start HOURS after its declared cron. Capture ACTUAL
mid-session public source ASAP, but do not PUBLISH until pre-existing
source and allocation regressions pass. Earlier extra attempt never
treats its schedule time as the actual receipt.
"""
from pathlib import Path
import unittest

ROOT=Path(__file__).resolve().parents[1]
WF=ROOT/".github/workflows/research_cycle_mid_session_watch.yml"
CAPTURE=ROOT/"engines/research/cycle_mid_session_signal_tape.py"

class MidSessionWorkflowSchedulingTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.yaml=WF.read_text(encoding="utf-8")
        cls.capture=CAPTURE.read_text(encoding="utf-8")

    def test_early_hedge_and_same_two_original_slots(self):
        y=self.yaml
        self.assertEqual(y.count("- cron:"),2)
        self.assertIn("15 23 * * 0-4",y)
        self.assertIn("30 1,2 * * 1-5",y)
        self.assertIn("concurrency:",y)
        self.assertIn("cancel-in-progress: false",y)

    def test_clock_gate_first_and_pure_standard_library(self):
        y=self.yaml
        gate=y.index("name: Check ACTUAL Sydney collection window")
        minimal=y.index("name: Install only public-source capture dependencies")
        capture=y.index("name: Capture a NEW actual verified mid-session")
        full=y.index("name: Install complete dependencies for regression")
        tests=y.index("name: Validate shared Cycle allocation")
        save=y.index("name: Save only new immutable research source row")
        self.assertLess(gate,minimal)
        self.assertLess(minimal,capture)
        self.assertLess(capture,full)
        self.assertLess(full,tests)
        self.assertLess(tests,save)
        guard=y[gate:minimal]
        self.assertIn("cycle_microstructure_mid_session_backup --is-window",guard)
        self.assertIn('echo "eligible=false" >> "$GITHUB_OUTPUT"',guard)
        self.assertNotIn("pip install",guard)
        self.assertNotIn("fetch_",guard)
        self.assertNotIn("ntfy",guard.lower())

    def test_ineligible_date_does_not_fetch_even_a_public_BTC_source(self):
        y=self.yaml
        cap=y[y.index("name: Capture a NEW actual verified mid-session"):
              y.index("name: Install complete dependencies for regression")]
        self.assertIn("steps.capture_window.outputs.eligible == 'true'",cap)
        self.assertIn("refs/heads/main",cap)
        self.assertIn("github.event_name == 'schedule'",cap)
        self.assertIn("github.event_name == 'workflow_dispatch'",cap)
        self.assertIn("cycle_mid_session_signal_tape",cap)

    def test_capture_runtime_has_only_public_python_dependencies(self):
        y=self.yaml
        basic=y[y.index("name: Install only public-source capture dependencies"):
                y.index("name: Capture a NEW actual verified mid-session")]
        self.assertIn("'numpy>=1.26'",basic)
        self.assertIn("'pandas>=2'",basic)
        self.assertIn("'requests>=2.31'",basic)
        self.assertNotIn("streamlit",basic)
        self.assertIn("steps.capture_window.outputs.eligible == 'true'",basic)

    def test_full_original_regressions_run_after_attempt_and_before_git_commit(self):
        y=self.yaml
        a=y[y.index("name: Validate shared Cycle allocation"):
            y.index("name: Read-only probe ACTUAL public BTC")]
        for test in (
            "test_cycle_mid_session_signal_tape.py",
            "test_cycle_mid_session_capture_health.py",
            "test_cycle_trading_pct_allocation.py",
            "test_shared_cycle_live_completed_utc.py",
            "test_cycle_mid_session_capture_workflow_priority.py",
        ):
            self.assertIn(test,a)
        self.assertIn("--self-check-only",a)
        self.assertIn("id: full_validation",a)
        self.assertIn("steps.prospective_capture.outcome == 'success'",a)
        self.assertIn("github.event_name == 'pull_request'",a)

    def test_no_publish_without_valid_capture_AND_passed_original_test_suite(self):
        y=self.yaml
        part=y[y.index("name: Save only new immutable research source row"):]
        self.assertIn("steps.prospective_capture.outcome == 'success'",part)
        self.assertIn("steps.full_validation.outcome == 'success'",part)
        self.assertIn("success()",part)
        self.assertIn("python -m engines.research.cycle_mid_session_signal_tape --self-check-only",part)
        self.assertIn("git add -- \"$path\"",part)
        self.assertIn("git rebase origin/main",part)
        self.assertIn("git push origin HEAD:main",part)
        self.assertNotIn("ntfy.sh",part)
        self.assertNotIn("cycle_trading_daily_ntfy",part)

    def test_actual_receipt_not_scheduled_time_forms_source(self):
        c=self.capture
        self.assertIn("begun=_instant(clock())",c)
        self.assertIn("market,meta=market_fetcher(begun)",c)
        self.assertIn("captured=_instant(clock())",c)
        self.assertIn('if capture_window(captured)!=today:',c)
        self.assertIn("read_tape(path)",c)
        self.assertIn("append(path,row)",c)

    def test_missed_record_is_not_backfilled_and_current_file_is_immutable(self):
        y=self.yaml
        self.assertIn("git diff --cached --quiet",y)
        self.assertIn("if-no-files-found: ignore",y)
        self.assertIn("artifacts/mid_session_capture/",y)
        self.assertIn("capture_transcript.txt",y)
        self.assertIn("capture_exit.json",y)
        self.assertIn("actual_window_gate.json",y)
        self.assertIn("historical_backfills_allowed",y)
        self.assertIn("ntfy_posted",y)
        self.assertIn("orders_placed",y)

    def test_no_executing_app_or_single_daily_ntfy_in_research_capture(self):
        y=self.yaml
        self.assertNotIn("cycle_trading_daily_ntfy.py",y)
        self.assertNotIn("ntfy.sh",y)
        self.assertNotIn("portfolio_store.save_portfolio",y)
        self.assertNotIn("save_portfolio(",y)
        self.assertNotIn("send_to_broker",y)


if __name__=="__main__":
    unittest.main()
