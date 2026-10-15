import unittest

import pandas as pd

from engines.research.benchmark_harness import compare_lagged_cycle_to_benchmarks


class CausalBenchmarkRobustnessTests(unittest.TestCase):
    def test_future_risk_does_not_affect_prior_cycle_actions(self):
        dates = pd.date_range("2020-01-06", periods=8, freq="W-MON")
        data = pd.DataFrame({
            "btc_price_aud": [100, 95, 90, 110, 130, 150, 120, 140],
            "risk_score": [0.1, 0.1, 0.1, 0.9, 0.9, 0.1, 0.1, 0.1],
        }, index=dates)
        from engines.research.cycle_backtest import simulate_next_observation_strategy
        before, _ = simulate_next_observation_strategy(data, starting_capital_aud=1000, min_trade_aud=0)
        changed = data.copy()
        changed.loc[dates[-1], "risk_score"] = 1.0
        after, _ = simulate_next_observation_strategy(changed, starting_capital_aud=1000, min_trade_aud=0)
        pd.testing.assert_frame_equal(before.iloc[:-1], after.iloc[:-1])

    def test_zero_fee_constant_price_has_no_benchmark_profit(self):
        dates = pd.date_range("2020-01-06", periods=6, freq="W-MON")
        data = pd.DataFrame({
            "btc_price_aud": [100] * 6,
            "risk_score": [0.5] * 6,
        }, index=dates)
        result = compare_lagged_cycle_to_benchmarks(
            data, starting_capital_aud=500_000, fee_pct=0,
        )
        self.assertAlmostEqual(result["buy_and_hold_next_bar"]["ending_equity_aud"], 500_000)
        self.assertAlmostEqual(result["fixed_dca_next_bar"]["ending_equity_aud"], 500_000)
        self.assertAlmostEqual(result["cycle_lagged"]["ending_equity_aud"], 500_000)


if __name__ == "__main__":
    unittest.main()
