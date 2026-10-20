"""Static release gates for independence of the nightly mid-session source audit.

Separate health audit must not accidentally be gated by the very BTC
source checks it is supposed to provide observability for. No side effects.
"""
from pathlib import Path
import unittest

ROOT=Path(__file__).resolve().parents[1]
WORKFLOW=ROOT/".github/workflows/research_forward_cycle_tape.yml"

class IndependentNightlyHealthWorkflowTests(unittest.TestCase):
    def setUp(self):
        self.source=WORKFLOW.read_text(encoding="utf-8")

    def test_independent_source_audit_runs_before_model_tests(self):
        self.assertLess(
            self.source.index("name: Independent Sydney mid-session missing-source diagnostic"),
            self.source.index("name: Check frozen model equality, capture invariants"))
        self.assertLess(
            self.source.index("name: Install same research dependencies as Streamlit"),
            self.source.index("name: Independent Sydney mid-session missing-source diagnostic"))

    def test_independent_monitor_not_gated_by_btc_model_validation_result(self):
        pos=self.source.index("name: Independent Sydney mid-session missing-source diagnostic")
        content=self.source[pos:self.source.index("name: Preserve independent capture-health result",pos)]
        self.assertIn("github.event_name != 'pull_request'",content)
        self.assertIn("github.ref == 'refs/heads/main'",content)
        self.assertIn("!cancelled()",content)
        self.assertNotIn("steps.capture_validation",content)
        self.assertNotIn("steps.readiness",content)
        self.assertIn("cycle_mid_session_capture_health",content)

    def test_independent_read_only_artifact_does_not_wait_for_market_gate(self):
        pos=self.source.index("name: Preserve independent capture-health result")
        content=self.source[pos:self.source.index("name: Check frozen model equality",pos)]
        self.assertIn("actions/upload-artifact@v4",content)
        self.assertIn("cycle-independent-mid-session-capture-health",content)
        self.assertIn("artifacts/research_mid_session_capture_health.json",content)
        self.assertNotIn("steps.capture_validation",content)
        self.assertNotIn("steps.readiness",content)

    def test_existing_one_nightly_schedule_preserved_and_no_send(self):
        self.assertIn("cron: '25 12 * * *'",self.source)
        self.assertEqual(self.source.count("cron:"),1)
        self.assertNotIn("ntfy.sh",self.source)
        self.assertNotIn("requests.post",self.source)

    def test_existing_source_publication_still_requires_successful_validation(self):
        pos=self.source.index("name: Save only new immutable research observation")
        gating=self.source[pos:self.source.index("run: |",pos)]
        self.assertIn("steps.capture_validation.outcome == 'success'",gating)
        self.assertIn("steps.readiness.outcome == 'success'",gating)

if __name__=="__main__":
    unittest.main()
