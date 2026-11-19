"""Tests for V6.0 allocation-scale synthetic stress report."""
import tempfile
import unittest
from pathlib import Path

import pandas as pd

from engines.research.v60_allocation_scale_stress_report import build_report


class V60AllocationScaleStressReportTests(unittest.TestCase):
    def test_report_covers_all_synthetic_paths_and_matched_cap_variants(self):
        with tempfile.TemporaryDirectory() as directory:
            metadata = build_report(Path(directory))
            frame = pd.read_csv(Path(directory) / "v60_allocation_scale_synthetic_stress.csv")
            self.assertEqual(metadata["result_rows"], 100)
            self.assertEqual(len(frame), 100)
            self.assertEqual(set(frame["scenario"]), {
                "prolonged_bear_70pct", "false_bottom_recovery",
                "extended_bear_then_recovery", "rapid_v_recovery",
                "extended_above_wma_rally",
            })
            self.assertEqual(set(frame["dynamic_allocation_scale"]), {0.5, 0.75, 1.0, 1.25})
            self.assertTrue(frame["research_only"].all())
            self.assertFalse(frame["trade_executable"].any())

    def test_prolonged_bear_comparison_includes_fixed_and_measured_outcomes(self):
        with tempfile.TemporaryDirectory() as directory:
            build_report(Path(directory))
            frame = pd.read_csv(Path(directory) / "v60_allocation_scale_synthetic_stress.csv")
        bear = frame.loc[frame["scenario"] == "prolonged_bear_70pct"]
        self.assertEqual(len(bear), 20)
        self.assertTrue(bear["fixed_return_pct"].notna().all())
        self.assertTrue(bear["measured_return_pct"].notna().all())
        self.assertTrue(bear["measured_minus_fixed_return_pp"].notna().all())


if __name__ == "__main__":
    unittest.main()
