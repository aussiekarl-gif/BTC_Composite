import unittest

import numpy as np
import pandas as pd

from engines.research.fixed_sell_sensitivity import fixed_threshold_matrix


class FixedSellSensitivityTests(unittest.TestCase):
    def test_baseline_identity_and_nonoverlapping_holdouts(self):
        n = 120
        weeks = pd.date_range("2018-01-01", periods=n, freq="W-MON")
        t = np.arange(n)
        data = pd.DataFrame({
            "btc_price_aud": 100 * np.exp(t * 0.009 + np.sin(t / 7) * 0.2),
            "risk_score": np.clip(0.5 + np.sin(t / 7) * 0.48, 0, 1),
        }, index=weeks)
        matrix = fixed_threshold_matrix(data)
        baseline = [r for r in matrix["results"]
                    if r["sell_threshold"] == 0.75]
        self.assertTrue(all(abs(r["edge_vs_baseline_aud"]) < 1e-8
                            for r in baseline))
        nfolds = len(set(r["fold"] for r in baseline))
        self.assertEqual(len(matrix["results"]), nfolds * 5 * 3)
        self.assertTrue(all(x["folds"] == nfolds for x in matrix["summary"]))

    def test_later_price_changes_do_not_change_first_holdout(self):
        n = 120
        weeks = pd.date_range("2018-01-01", periods=n, freq="W-MON")
        t = np.arange(n)
        data = pd.DataFrame({
            "btc_price_aud": 100 * np.exp(t * 0.009 + np.sin(t / 7) * 0.2),
            "risk_score": np.clip(0.5 + np.sin(t / 7) * 0.48, 0, 1),
        }, index=weeks)
        initial = fixed_threshold_matrix(data)["results"]
        changed = data.copy()
        changed.iloc[90:, 0] *= 200
        later = fixed_threshold_matrix(changed)["results"]
        first = [(r["sell_threshold"], r["cost_per_side"], r["ending_equity_aud"])
                 for r in initial if r["fold"] == 1]
        second = [(r["sell_threshold"], r["cost_per_side"], r["ending_equity_aud"])
                  for r in later if r["fold"] == 1]
        self.assertEqual(first, second)


if __name__ == "__main__":
    unittest.main()
