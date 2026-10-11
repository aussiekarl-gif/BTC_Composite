import unittest

from engines.research.research_model import risk_occurrence_table


class RiskOccurrenceTableTests(unittest.TestCase):
    def test_all_numeric_scores_are_accounted_for_and_endpoints_separated(self):
        scores = [0.0, 0.005, 0.01, 0.2, 0.8, 1.0, -0.1, 1.2, None, "bad"]
        result = risk_occurrence_table(scores)
        by_label = result.set_index("Risk range")

        self.assertEqual(int(result["Weeks"].sum()), 8)
        self.assertAlmostEqual(float(result["Percent"].sum()), 100.0)
        self.assertEqual(int(by_label.loc["0.000 (floor)", "Weeks"]), 1)
        self.assertEqual(int(by_label.loc["1.000 (cap)", "Weeks"]), 1)
        self.assertEqual(int(by_label.loc["<0.00 (invalid)", "Weeks"]), 1)
        self.assertEqual(int(by_label.loc[">1.00 (invalid)", "Weeks"]), 1)

    def test_empty_input_returns_zero_percentages(self):
        result = risk_occurrence_table([None, "bad", float("nan")])
        self.assertEqual(int(result["Weeks"].sum()), 0)
        self.assertEqual(float(result["Percent"].sum()), 0.0)

    def test_exact_boundaries_are_counted_once(self):
        scores = [0.0, 0.01, 0.02, 0.05, 0.1, 0.2, 0.4, 0.6, 0.8, 1.0]
        result = risk_occurrence_table(scores)
        by_label = result.set_index("Risk range")
        self.assertEqual(int(result["Weeks"].sum()), len(scores))
        self.assertAlmostEqual(float(result["Percent"].sum()), 100.0)
        self.assertEqual(int(by_label.loc["0.000 (floor)", "Weeks"]), 1)
        self.assertEqual(int(by_label.loc["1.000 (cap)", "Weeks"]), 1)
        self.assertEqual(int(by_label.loc["0.01–0.02", "Weeks"]), 1)
        self.assertEqual(int(by_label.loc["(0.80, 1.00)", "Weeks"]), 1)


if __name__ == "__main__":
    unittest.main()
