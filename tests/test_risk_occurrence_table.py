import unittest

from engines.research.research_model import risk_occurrence_table


class RiskOccurrenceTableTests(unittest.TestCase):
    def test_all_numeric_scores_counted_once(self):
        values = [0, 0.005, 0.01, 0.2, 0.8, 1.0, -0.1, 1.2, float("inf"), float("-inf"), None, "bad"]
        result = risk_occurrence_table(values)
        by_label = result.set_index("Risk range")
        self.assertEqual(result["Weeks"].sum(), 10)
        self.assertAlmostEqual(result["Percent"].sum(), 100)
        self.assertEqual(by_label.loc["0.000 (floor)", "Weeks"], 1)
        self.assertEqual(by_label.loc["1.000 (cap)", "Weeks"], 1)
        self.assertEqual(by_label.loc[">1.00 (invalid)", "Weeks"], 2)
        self.assertEqual(by_label.loc["<0.00 (invalid)", "Weeks"], 2)

    def test_boundaries_and_empty(self):
        values = [0, .01, .02, .05, .1, .2, .4, .6, .8, 1.]
        result = risk_occurrence_table(values)
        self.assertEqual(result["Weeks"].sum(), len(values))
        self.assertAlmostEqual(result["Percent"].sum(), 100)
        empty = risk_occurrence_table([None, "bad", float("nan")])
        self.assertEqual(empty["Weeks"].sum(), 0)
        self.assertEqual(empty["Percent"].sum(), 0)


if __name__ == "__main__":
    unittest.main()
