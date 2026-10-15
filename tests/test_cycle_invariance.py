"""Independent research benchmark checks for causal execution and accounting."""
import unittest

import pandas as pd

from engines.research.cycle_backtest import (
    simulate_cycle_strategy,
    simulate_next_observation_strategy,
)


class CycleInvarianceTests(unittest.TestCase):
    def sample(self, risks):
        return pd.DataFrame(
            {"btc_price_aud": [100.0] * len(risks), "risk_score": risks},
            index=pd.date_range("2021-01-04", periods=len(risks), freq="W-MON"),
        )

    def test_first_observation_does_not_trade_using_same_bar_signal(self):
        trades, _ = simulate_next_observation_strategy(
            self.sample([0.0, 0.5, 0.5]),
            starting_capital_aud=1000, min_trade_aud=0,
        )
        self.assertEqual(trades.iloc[0]["action"], "HOLD")
        self.assertEqual(trades.iloc[1]["action"], "BUY")

    def test_future_signal_change_cannot_change_earlier_trades(self):
        base = self.sample([0.0, 0.0, 0.0, 0.0, 0.0])
        altered = base.copy()
        altered.iloc[-1, altered.columns.get_loc("risk_score")] = 1.0
        a, _ = simulate_next_observation_strategy(base, starting_capital_aud=1000, min_trade_aud=0)
        b, _ = simulate_next_observation_strategy(altered, starting_capital_aud=1000, min_trade_aud=0)
        pd.testing.assert_frame_equal(a.iloc[:-1], b.iloc[:-1])

    def test_accounting_identity_and_nonnegative_positions(self):
        trades, summary = simulate_cycle_strategy(
            self.sample([0, 0, 1, 1, 0, 1]),
            starting_capital_aud=1000, min_trade_aud=0, fee_pct=0.001,
        )
        self.assertTrue((trades["cash_aud"] >= -1e-8).all())
        self.assertTrue((trades["btc_held"] >= -1e-8).all())
        self.assertTrue(
            ((trades["equity_aud"] - trades["cash_aud"] -
              trades["btc_held"] * trades["btc_price_aud"]).abs() < 1e-7).all()
        )
        self.assertAlmostEqual(
            summary["ending_equity_aud"],
            float(trades.iloc[-1]["equity_aud"]),
        )


if __name__ == "__main__":
    unittest.main()
