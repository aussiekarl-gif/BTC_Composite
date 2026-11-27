"""Regression tests for the daily on-chain source refresh schedule."""
from pathlib import Path
import unittest

WORKFLOW = Path(__file__).resolve().parents[1] / ".github" / "workflows" / "cowen_onchain_daily_refresh.yml"


class CowenOnchainScheduleTests(unittest.TestCase):
    def test_three_daily_slots_are_off_hour_and_brisbane_morning(self):
        text = WORKFLOW.read_text(encoding="utf-8")
        cron_lines = [line.strip() for line in text.splitlines() if "- cron:" in line]
        self.assertEqual(
            cron_lines,
            [
                '- cron: "17 23 * * *"',
                '- cron: "17 0 * * *"',
                '- cron: "17 1 * * *"',
            ],
        )
        self.assertTrue(all(line.startswith('- cron: "17 ') for line in cron_lines))

    def test_manual_dispatch_remains_available(self):
        text = WORKFLOW.read_text(encoding="utf-8")
        self.assertIn("workflow_dispatch:", text)


if __name__ == "__main__":
    unittest.main()
