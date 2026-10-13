import unittest

import pandas as pd

from engines.research.cycle_backtest import simulate_cycle_strategy


class CycleBacktestTests(unittest.TestCase):
    def data(self, prices, risks):
        return pd.DataFrame(
            {"btc_price_aud": prices, "risk_score": risks},
            index=pd.date_range("2020-01-06", periods=len(prices), freq="W-MON"),
        )

    def test_buys_only_in_low_risk_zone_and_respects_cash(self):
        frame, summary = simulate_cycle_strategy(
            self.data([100, 80, 120], [0.0, 0.1, 0.5]),
            starting_capital_aud=1000, max_buy_pct_period=0.2, fee_pct=0,
        )
        self.assertEqual(list(frame["action"]), ["BUY", "BUY", "HOLD"])
        self.assertTrue((frame["cash_aud"] >= -1e-9).all())
        self.assertLessEqual(frame["buy_gross_aud"].sum(), 1000)
        self.assertAlmostEqual(
            summary["ending_equity_aud"],
            summary["cash_remaining_aud"] + summary["btc_value_aud"],
        )

    def test_sells_only_at_or_above_sell_threshold_and_tracks_realized_pnl(self):
        frame, summary = simulate_cycle_strategy(
            self.data([100, 80, 160], [0.0, 0.0, 1.0]),
            starting_capital_aud=1000, max_buy_pct_period=0.2,
            max_sell_pct_period=0.5, fee_pct=0,
        )
        self.assertEqual(list(frame["action"]), ["BUY", "BUY", "SELL"])
        self.assertGreater(summary["realized_pnl_aud"], 0)
        self.assertGreater(summary["sell_count"], 0)
        self.assertGreater(summary["cash_remaining_aud"], 0)

    def test_fees_reduce_equity_and_are_reported(self):
        data = self.data([100, 100], [0.0, 0.0])
        _, no_fee = simulate_cycle_strategy(data, starting_capital_aud=1000, fee_pct=0)
        _, with_fee = simulate_cycle_strategy(data, starting_capital_aud=1000, fee_pct=0.01)
        self.assertGreater(with_fee["fees_aud"], 0)
        self.assertLess(with_fee["ending_equity_aud"], no_fee["ending_equity_aud"])

    def test_invalid_rows_are_skipped_without_overspending(self):
        data = self.data([100, float("nan"), 90], [0.0, 0.0, 0.0])
        frame, summary = simulate_cycle_strategy(data, starting_capital_aud=1000)
        self.assertEqual(frame.iloc[1]["action"], "SKIP_INVALID_INPUT")
        self.assertTrue((frame["cash_aud"].dropna() >= -1e-9).all())
        self.assertLessEqual(frame["buy_gross_aud"].sum(), 1000)
        self.assertEqual(summary["observations"], 3)

    def test_empty_input(self):
        empty = pd.DataFrame(columns=["btc_price_aud", "risk_score"])
        frame, summary = simulate_cycle_strategy(empty)
        self.assertTrue(frame.empty)
        self.assertEqual(summary, {})


if __name__ == "__main__":
    unittest.main()
