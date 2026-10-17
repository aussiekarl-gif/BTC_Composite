import unittest

import numpy as np
import pandas as pd

from engines.research.sell_threshold_walkforward import (
    expanding_walk_forward, fixed_dca_benchmark,
)


class WalkForwardThresholdTests(unittest.TestCase):
    def sample(self, n=120):
        idx = pd.date_range("2018-01-01", periods=n, freq="W-MON")
        t = np.arange(n)
        price = 100 * np.exp(0.009 * t + 0.22 * np.sin(t / 7))
        risk = np.clip(0.5 + 0.48 * np.sin(t / 7), 0, 1)
        return pd.DataFrame({"btc_price_aud": price, "risk_score": risk}, index=idx)

    def test_dca_math(self):
        sample = pd.DataFrame({"btc_price_aud": [100, 200]})
        result = fixed_dca_benchmark(sample, starting_capital_aud=1000, fee_pct=0)
        self.assertAlmostEqual(result["btc_held"], 7.5)
        self.assertAlmostEqual(result["ending_equity_aud"], 1500)

    def test_no_future_prices_change_prior_fold_choices(self):
        sample = self.sample()
        first = expanding_walk_forward(sample)
        modified = sample.copy()
        modified.iloc[85:, modified.columns.get_loc("btc_price_aud")] *= 100
        second = expanding_walk_forward(modified)
        self.assertEqual(first["folds"][0]["sell_threshold"],
                         second["folds"][0]["sell_threshold"])
        self.assertEqual(first["folds"][0]["candidate_equity_aud"],
                         second["folds"][0]["candidate_equity_aud"])

    def test_disjoint_holdout_windows_and_cost_scenarios(self):
        result = expanding_walk_forward(self.sample())
        dates = [(r["test_start"], r["test_end"]) for r in result["folds"]
                 if r["cost_per_side"] == 0.001]
        self.assertGreaterEqual(len(dates), 3)
        self.assertEqual(len(result["folds"]), len(dates) * 3)
        self.assertTrue(all(dates[i][1] < dates[i+1][0]
                            for i in range(len(dates)-1)))
        self.assertEqual(len(result["summary_by_cost"]), 3)
        self.assertTrue(all(s["folds"] == len(dates)
                            for s in result["summary_by_cost"]))

    def test_nonfinite_input_rejected(self):
        frame = self.sample()
        frame.iloc[3, 1] = np.nan
        with self.assertRaises(ValueError):
            expanding_walk_forward(frame)


if __name__ == "__main__":
    unittest.main()
