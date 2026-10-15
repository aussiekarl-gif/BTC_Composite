import unittest

import numpy as np
import pandas as pd

from engines.research.sell_threshold_robustness import run_probe, load_data


class SellThresholdRobustnessTests(unittest.TestCase):
    def fixture(self):
        weeks = 64
        index = pd.date_range("2020-01-06", periods=weeks, freq="W-MON")
        prices = 100 * np.exp(np.linspace(0, 1.2, weeks)
                              + 0.18 * np.sin(np.linspace(0, 5 * np.pi, weeks)))
        scores = np.clip(0.5 + 0.47 * np.sin(np.linspace(0, 5 * np.pi, weeks)), 0, 1)
        return pd.DataFrame({"btc_price_aud": prices, "risk_score": scores}, index=index)

    def test_holdout_uses_frozen_training_choice(self):
        data = self.fixture()
        original = run_probe(data)
        mutated = data.copy()
        mutated.iloc[45:, mutated.columns.get_loc("btc_price_aud")] *= 100
        altered = run_probe(mutated)
        self.assertEqual(original["selected_sell_threshold"],
                         altered["selected_sell_threshold"])
        self.assertEqual(len(original["holdout_scenarios"]), 6)

    def test_cost_sensitivity_never_increases_same_scenario_equity(self):
        report = run_probe(self.fixture())
        for scenario in ("selected", "baseline_075"):
            vals = [r["holdout_equity_aud"]
                    for r in report["holdout_scenarios"] if r["scenario"] == scenario]
            self.assertTrue(all(a >= b - 1e-6 for a, b in zip(vals, vals[1:])))

    def test_no_invalid_scores_sneak_into_probe(self):
        data = self.fixture()
        data.iloc[4, data.columns.get_loc("risk_score")] = float("nan")
        with self.assertRaises(ValueError):
            run_probe(load_data_from_frame_guard(data))


def load_data_from_frame_guard(data):
    # Validation in load_data is CSV-bound; reproduce input for the same path.
    import os
    import tempfile
    with tempfile.NamedTemporaryFile(suffix=".csv", delete=False) as out:
        path = out.name
    try:
        data.reset_index(names="date").to_csv(path, index=False)
        return load_data(path)
    finally:
        os.remove(path)


if __name__ == "__main__":
    unittest.main()
