"""Research-only regression tests for execution timing and accounting.

Run: python -m unittest tests.test_cycle_execution_safety
No live data, portfolio writes, or Production imports.
"""
import unittest

import numpy as np
import pandas as pd

from engines.research.cycle_backtest import (
    simulate_cycle_strategy,
    simulate_next_observation_strategy,
)


class CycleExecutionSafetyTests(unittest.TestCase):
    def setUp(self):
        self.data = pd.DataFrame(
            {
                "btc_price_aud": [100.0, 120.0, 140.0, 160.0, 180.0, 200.0],
                "risk_score": [0.0, 1.0, 0.0, 1.0, 0.5, 0.0],
            },
            index=pd.date_range("2025-01-06", periods=6, freq="W-MON"),
        )
        self.kwargs = dict(
            starting_capital_aud=10000.0, buy_threshold=0.25,
            sell_threshold=0.75, max_buy_pct_period=0.5,
            max_sell_pct_period=0.5, fee_pct=0.001, min_trade_aud=1.0,
        )

    def test_first_bar_cannot_trade_without_prior_signal(self):
        history, _ = simulate_next_observation_strategy(self.data, **self.kwargs)
        self.assertEqual(history.loc[0, "action"], "SKIP_INVALID_INPUT")
        self.assertEqual(history.loc[1, "action"], "BUY")
        self.assertAlmostEqual(history.loc[1, "btc_price_aud"], 120.0)

    def test_lag_changes_trade_direction(self):
        same, _ = simulate_cycle_strategy(self.data, **self.kwargs)
        lagged, _ = simulate_next_observation_strategy(self.data, **self.kwargs)
        self.assertEqual(same.loc[0, "action"], "BUY")
        self.assertEqual(same.loc[1, "action"], "SELL")
        self.assertEqual(lagged.loc[1, "action"], "BUY")
        self.assertEqual(lagged.loc[2, "action"], "SELL")

    def test_prefix_invariance_of_executed_history(self):
        full, _ = simulate_next_observation_strategy(self.data, **self.kwargs)
        for n in range(2, len(self.data)):
            short, _ = simulate_next_observation_strategy(
                self.data.iloc[:n], **self.kwargs
            )
            for name in ("action", "cash_aud", "btc_held", "equity_aud",
                         "cumulative_fees_aud"):
                a = full[name].iloc[:n].to_numpy()
                b = short[name].to_numpy()
                if name == "action":
                    self.assertListEqual(list(a), list(b))
                else:
                    np.testing.assert_allclose(a, b, rtol=1e-12, atol=1e-9,
                                               equal_nan=True)

    def test_cash_btc_and_fee_accounting(self):
        result, summary = simulate_next_observation_strategy(
            self.data, **self.kwargs
        )
        self.assertTrue((result["cash_aud"] >= -1e-8).all())
        self.assertTrue((result["btc_held"] >= -1e-10).all())
        np.testing.assert_allclose(
            result["equity_aud"],
            result["cash_aud"] + result["btc_held"] * result["btc_price_aud"],
            rtol=1e-12, atol=1e-8,
        )
        np.testing.assert_allclose(
            result["cumulative_fees_aud"],
            result["fees_aud"].cumsum(), rtol=1e-12, atol=1e-8,
        )
        self.assertAlmostEqual(summary["fees_aud"],
                               float(result["fees_aud"].sum()))

    def test_no_trade_on_invalid_signal(self):
        bad = self.data.copy()
        bad.loc[bad.index[1], "risk_score"] = np.nan
        result, _ = simulate_next_observation_strategy(bad, **self.kwargs)
        self.assertEqual(result.loc[2, "action"], "SKIP_INVALID_INPUT")
        self.assertEqual(float(result.loc[2, "buy_gross_aud"]), 0.0)
        self.assertEqual(float(result.loc[2, "sell_gross_aud"]), 0.0)


if __name__ == "__main__":
    unittest.main()
