import unittest

import pandas as pd

from engines.research.research_model import risk_occurrence_table


class RiskOccurrenceTableTests(unittest.TestCase):
    def test_bucket_counts_and_percentages_cover_all_valid_scores(self):
        scores = [0.0, 0.005, 0.01, 0.2, 0.8, 1.0, -0.1, 1.2, None, "bad"]
        result = risk_occurrence_table(scores)

        self.assertEqual(int(result["Weeks"].sum()), 8)
        self.assertAlmostEqual(float(result["Percent"].sum()), 100.0)
        self.assertEqual(int(result.loc[result["Risk range"] == "<0.00 (out of range)", "Weeks"].iloc[0]), 1)
        self.assertEqual(int(result.loc[result["Risk range"] == "0.80–1.00+", "Weeks"].iloc[0]), 2)

    def test_empty_input_returns_zero_percentages(self):
        result = risk_occurrence_table([None, "bad", float("nan")])
        self.assertEqual(int(result["Weeks"].sum()), 0)
        self.assertEqual(float(result["Percent"].sum()), 0.0)

    def test_exact_boundaries_are_counted_once(self):
        result = risk_occurrence_table([0.0, 0.01, 0.02, 0.05, 0.1, 0.2, 0.4, 0.6, 0.8, 1.0])
        self.assertEqual(int(result["Weeks"].sum()), 10)
        self.assertAlmostEqual(float(result["Percent"].sum()), 100.0)


if __name__ == "__main__":
    unittest.main()
