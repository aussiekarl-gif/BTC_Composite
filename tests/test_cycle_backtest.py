import unittest

import pandas as pd

from engines.research.cycle_backtest import (
    simulate_buy_and_hold_benchmark,
    simulate_cycle_strategy,
    walk_forward_parameter_sweep,
)


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
        _, no_fee = simulate_cycle_strategy(data, starting_capital_aud=1000, fee_pct=0, min_trade_aud=1)
        _, with_fee = simulate_cycle_strategy(data, starting_capital_aud=1000, fee_pct=0.01, min_trade_aud=1)
        self.assertGreater(with_fee["fees_aud"], 0)
        self.assertLess(with_fee["ending_equity_aud"], no_fee["ending_equity_aud"])

    def test_invalid_rows_are_skipped_without_overspending(self):
        data = self.data([100, float("nan"), 90], [0.0, 0.0, 0.0])
        frame, summary = simulate_cycle_strategy(data, starting_capital_aud=1000)
        self.assertEqual(frame.iloc[1]["action"], "SKIP_INVALID_INPUT")
        self.assertTrue((frame["cash_aud"].dropna() >= -1e-9).all())
        self.assertLessEqual(frame["buy_gross_aud"].sum(), 1000)
        self.assertEqual(summary["observations"], 3)

    def test_buy_and_hold_benchmark_uses_same_initial_capital(self):
        result = simulate_buy_and_hold_benchmark(
            self.data([100, 150, 200], [0.5, 0.5, 0.5]),
            starting_capital_aud=1000, fee_pct=0,
        )
        self.assertAlmostEqual(result["btc_held"], 10.0)
        self.assertAlmostEqual(result["ending_equity_aud"], 2000.0)
        self.assertAlmostEqual(result["total_pnl_aud"], 1000.0)

    def test_sell_threshold_boundary_does_not_create_zero_size_sell(self):
        frame, _ = simulate_cycle_strategy(
            self.data([100, 100], [0.0, 0.75]),
            starting_capital_aud=1000, max_buy_pct_period=0.2,
            max_sell_pct_period=0.5, fee_pct=0,
        )
        self.assertEqual(frame.iloc[1]["action"], "HOLD")

    def test_walk_forward_sweep_tests_later_dates_separately(self):
        data = self.data(
            [100, 80, 90, 120, 150, 180, 160, 200, 220, 240],
            [0.0, 0.1, 0.2, 0.5, 0.8, 0.9, 0.7, 0.9, 0.4, 0.8],
        )
        leaderboard, winner, test_df, test_summary, benchmark = walk_forward_parameter_sweep(
            data,
            starting_capital_aud=1000,
            fee_pct=0,
            split_fraction=0.6,
            buy_thresholds=(0.25, 0.35),
            sell_thresholds=(0.65, 0.75),
            max_buy_pct_periods=(0.2,),
            max_sell_pct_periods=(0.2,),
            min_trade_aud=1,
        )
        self.assertEqual(len(leaderboard), 4)
        self.assertEqual(test_df.index.min(), data.index[6])
        self.assertIn("buy_threshold", winner)
        self.assertGreaterEqual(test_summary["observations"], 2)
        self.assertGreater(benchmark["observations"], 0)
        self.assertTrue((leaderboard["train_return_pct"].diff().dropna() <= 1e-9).all())

    def test_empty_input(self):
        empty = pd.DataFrame(columns=["btc_price_aud", "risk_score"])
        frame, summary = simulate_cycle_strategy(empty)
        self.assertTrue(frame.empty)
        self.assertEqual(summary, {})


if __name__ == "__main__":
    unittest.main()
