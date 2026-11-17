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

    def test_power_law_floor_diagnostics_by_halving_cycle(self):
        import pandas as pd
        from engines.research.research_model import power_law_floor_diagnostics

        dates = pd.to_datetime([
            "2015-01-05", "2015-02-05",
            "2017-01-05", "2017-02-05",
            "2021-01-05", "2021-02-05",
            "2025-01-05", "2025-02-05", "2025-03-05",
        ], utc=True)
        risk = pd.Series([0.0, 0.2, 0.0, 0.1, 0.0, 0.0, 0.0, 0.3, 0.5], index=dates)
        residual = pd.Series([-0.12, -0.05, -0.18, -0.08, -0.25, -0.16, -0.11, -0.04, None], index=dates)
        result = power_law_floor_diagnostics(risk, residual, cheap_threshold=-0.10)
        by_cycle = result.set_index("Cycle")
        self.assertEqual(by_cycle.loc["All history", "Weeks"], 9)
        self.assertEqual(by_cycle.loc["All history", "Floor weeks"], 5)
        self.assertEqual(by_cycle.loc["All history", "Residual weeks"], 8)
        self.assertEqual(by_cycle.loc["All history", "Floor %"], 55.6)
        self.assertEqual(by_cycle.loc["All history", "Score/residual mismatches"], 0)
        self.assertEqual(by_cycle.loc["2016–2020 cycle", "Floor weeks"], 1)
        self.assertEqual(by_cycle.loc["2020–2024 cycle", "Floor weeks"], 2)
        self.assertEqual(by_cycle.loc["2024–current cycle", "Floor weeks"], 1)
        self.assertEqual(by_cycle.loc["All history", "Residual ≤−0.20 %"], 12.5)

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
