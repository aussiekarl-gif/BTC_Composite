import unittest

import pandas as pd

from engines.research.cycle_backtest import simulate_next_observation_strategy
from engines.research.execution_error_stress import execution_error_sweep


class ExecutionErrorStressTests(unittest.TestCase):
    def setUp(self):
        self.data = pd.DataFrame({
            "btc_price_aud": [100, 90, 80, 120, 160, 180, 100, 85],
            "risk_score": [0.1, 0.1, 0.1, 0.9, 0.95, 0.9, 0.1, 0.1],
        }, index=pd.date_range("2020-01-01", periods=8, freq="W"))

    def test_zero_error_matches_original_execution(self):
        _, original = simulate_next_observation_strategy(
            self.data, starting_capital_aud=1000, fee_pct=0.001, min_trade_aud=0
        )
        stressed = execution_error_sweep(
            self.data, error_fractions=(0,), starting_capital_aud=1000,
            fee_pct=0.001, min_trade_aud=0,
        ).iloc[0]
        self.assertAlmostEqual(stressed["ending_equity_aud"], original["ending_equity_aud"], places=7)
        self.assertAlmostEqual(stressed["btc_held"], original["btc_held"], places=9)

    def test_more_adverse_execution_cannot_improve_equity(self):
        result = execution_error_sweep(
            self.data, starting_capital_aud=1000, fee_pct=0.001, min_trade_aud=0
        )
        self.assertEqual(result["execution_error_fraction"].tolist(), [0, .15, .30])
        self.assertTrue(result["ending_equity_aud"].is_monotonic_decreasing)

    def test_invalid_price_rejected(self):
        bad = self.data.copy()
        bad.loc[bad.index[-1], "btc_price_aud"] = float("nan")
        with self.assertRaisesRegex(ValueError, "finite positive BTC/AUD price"):
            execution_error_sweep(bad)

    def test_invalid_error_rejected(self):
        with self.assertRaises(ValueError):
            execution_error_sweep(self.data, error_fractions=(1.0,))


if __name__ == "__main__":
    unittest.main()
