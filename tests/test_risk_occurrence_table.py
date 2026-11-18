import unittest

from engines.research.research_model import (
    continuous_valuation_risk_label, risk_occurrence_table,
)


class RiskOccurrenceTableTests(unittest.TestCase):
    def test_all_numeric_scores_counted_once(self):
        values = [0, 0.005, 0.01, 0.2, 0.8, 1.0, -0.1, 1.2, float("inf"), float("-inf"), None, "bad"]
        result = risk_occurrence_table(values)
        by_label = result.set_index("Risk range")
        self.assertEqual(result["Weeks"].sum(), 10)
        self.assertAlmostEqual(result["Percent"].sum(), 100)
        self.assertEqual(by_label.loc["0.00–0.01", "Weeks"], 2)
        self.assertEqual(by_label.loc["1.000 (cap)", "Weeks"], 1)
        self.assertEqual(by_label.loc[">1.00 (invalid)", "Weeks"], 2)
        self.assertEqual(by_label.loc["<0.00 (invalid)", "Weeks"], 2)

    def test_completed_weekly_last_excludes_partial_future_label(self):
        import pandas as pd
        from engines.research.research_model import completed_weekly_last

        dates = pd.to_datetime([
            "2026-11-09", "2026-11-10", "2026-11-11", "2026-11-17", "2026-11-23"
        ], utc=True)
        values = pd.Series([1.0, 2.0, 3.0, 4.0, 5.0], index=dates)
        weekly = completed_weekly_last(values, as_of=dates[-2])

        # Nov 10–16 is a partial Tuesday–Monday bucket because the source has
        # no actual Nov 16 endpoint. Nov 17 belongs to the next future bucket.
        self.assertEqual(list(weekly.index), [pd.Timestamp("2026-11-09", tz="UTC")])
        self.assertEqual(float(weekly.iloc[0]), 1.0)

        # Once an actual Monday 23 Nov observation exists and is the as-of date,
        # that weekly endpoint is valid and its own value is retained.
        completed = completed_weekly_last(values, as_of=dates[-1])
        self.assertEqual(list(completed.index), [
            pd.Timestamp("2026-11-09", tz="UTC"),
            pd.Timestamp("2026-11-23", tz="UTC"),
        ])
        self.assertEqual(float(completed.iloc[-1]), 5.0)

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
        residual = pd.Series([-0.35, -0.05, -0.33, -0.08, -0.40, -0.34, -0.31, -0.04, None], index=dates)
        result = power_law_floor_diagnostics(risk, residual, zero_risk_threshold=-0.32)
        by_cycle = result.set_index("Cycle")
        self.assertEqual(by_cycle.loc["All history", "Weeks"], 9)
        self.assertEqual(by_cycle.loc["All history", "Floor weeks"], 5)
        self.assertEqual(by_cycle.loc["All history", "Residual weeks"], 8)
        self.assertEqual(by_cycle.loc["All history", "Residual missing weeks"], 1)
        self.assertEqual(by_cycle.loc["All history", "Aligned floor %"], 62.5)
        self.assertEqual(by_cycle.loc["All history", "Floor %"], 55.6)
        self.assertEqual(by_cycle.loc["All history", "Active mapping mismatches"], 1)
        self.assertEqual(by_cycle.loc["2016–2020 cycle", "Floor weeks"], 1)
        self.assertEqual(by_cycle.loc["2020–2024 cycle", "Floor weeks"], 2)
        self.assertEqual(by_cycle.loc["2024–current cycle", "Floor weeks"], 1)
        self.assertEqual(by_cycle.loc["All history", "Residual ≤-0.20 %"], 50.0)
        self.assertEqual(by_cycle.loc["All history", "Residual ≤-0.15 weeks"], 4)
        self.assertEqual(by_cycle.loc["All history", "Residual ≤-0.20 weeks"], 4)
        self.assertEqual(by_cycle.loc["All history", "Residual ≤-0.25 weeks"], 4)
        self.assertEqual(by_cycle.loc["All history", "Residual ≤-0.30 weeks"], 4)
        self.assertEqual(by_cycle.loc["All history", "Residual ≤-0.35 weeks"], 2)
        self.assertEqual(by_cycle.loc["All history", "Residual ≤-0.40 weeks"], 1)


    def test_walk_forward_power_law_uses_completed_weeks_only(self):
        import numpy as np
        import pandas as pd
        from engines.research.research_model import GENESIS_DATE, walk_forward_power_law

        dates = pd.date_range("2020-01-01", "2020-03-01", freq="D", tz="UTC")
        elapsed = np.array([(d - GENESIS_DATE).days for d in dates], dtype=float)
        prices = 5000.0 + np.arange(len(dates), dtype=float) * 37.0
        data = pd.DataFrame({"price": prices}, index=dates)
        target = pd.Timestamp("2020-02-09", tz="UTC")  # Sunday: current W-MON bucket is incomplete.

        _, fair, residual, _, _ = walk_forward_power_law(
            data.loc[:target], cheap=-0.10, expensive=0.20,
            min_weeks=2, refit_days=1,
        )

        history = data.loc[data.index < target, "price"]
        completed = history.resample("W-MON").last().dropna()
        completed = completed.loc[completed.index < target]
        days = np.array([(d - GENESIS_DATE).days for d in completed.index], dtype=float)
        slope, intercept = np.polyfit(np.log10(days), np.log10(completed.to_numpy()), 1)
        target_days = (target - GENESIS_DATE).days
        expected_fair = 10 ** (slope * np.log10(target_days) + intercept)
        expected_residual = np.log10(float(data.loc[target, "price"])) - np.log10(expected_fair)

        self.assertAlmostEqual(float(fair.loc[target]), float(expected_fair), places=8)
        self.assertAlmostEqual(float(residual.loc[target]), float(expected_residual), places=10)

    def test_continuous_valuation_label_uses_its_own_score(self):
        self.assertEqual(continuous_valuation_risk_label(0.030), "VERY LOW")
        self.assertEqual(continuous_valuation_risk_label(0.50), "NEUTRAL")
        self.assertEqual(continuous_valuation_risk_label(float("nan")), "n/a")

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
