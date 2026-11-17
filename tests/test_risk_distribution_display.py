import unittest
import pandas as pd

from engines.shared.risk_distribution_display import (
    add_lowest_risk_multiplier_label,
)


class LowestRiskChartLabelTests(unittest.TestCase):
    def test_research_chart_merges_zero_and_positive_sub_one_percent_into_16x_bar(self):
        source = pd.DataFrame([
            {"Risk range": "<0.00 (invalid)", "Weeks": 1, "Percent": 1.0},
            {"Risk range": "0.000 (floor)", "Weeks": 2, "Percent": 2.0},
            {"Risk range": "(0.00, 0.01)", "Weeks": 3, "Percent": 3.0},
            {"Risk range": "0.01–0.02", "Weeks": 4, "Percent": 4.0},
        ])
        chart = add_lowest_risk_multiplier_label(source)
        self.assertEqual(chart.loc[1, "Risk range"], "0.00–0.01 · 16×")
        self.assertEqual(chart.loc[1, "Weeks"], 5)
        self.assertEqual(chart.loc[1, "Percent"], 5.0)
        self.assertEqual(chart.loc[2, "Risk range"], "0.01–0.02")
        self.assertEqual(len(chart), 3)
        self.assertEqual(len(source), 4)  # source table is not mutated

    def test_production_chart_labels_first_risk_band_without_changing_counts(self):
        source = pd.DataFrame([
            {"Risk range": "0.00–0.01", "Weeks": 5, "Percent": 10.0},
            {"Risk range": "0.01–0.02", "Weeks": 4, "Percent": 8.0},
        ])
        chart = add_lowest_risk_multiplier_label(source)
        self.assertEqual(chart.loc[0, "Risk range"], "0.00–0.01 · 16×")
        self.assertEqual(chart["Weeks"].tolist(), [5, 4])
        self.assertEqual(chart["Percent"].tolist(), [10.0, 8.0])

    def test_unknown_layout_fails_instead_of_assigning_wrong_multiplier(self):
        source = pd.DataFrame([
            {"Risk range": "0.01–0.02", "Weeks": 5, "Percent": 10.0},
        ])
        with self.assertRaisesRegex(ValueError, "Unexpected risk occurrence"):
            add_lowest_risk_multiplier_label(source)


if __name__ == "__main__":
    unittest.main()
