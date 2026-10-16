"""Deterministic research-only checks for the continuous-cycle accounting."""
import unittest

import pandas as pd

from engines.research.full_cycle_reinvestment import (
    evaluate, matched_hold, simulate, validate_history,
)


def fixture(prices, risks):
    return pd.DataFrame({
        "btc_price_aud": prices, "risk_score": risks,
    }, index=pd.date_range("2020-01-06", periods=len(prices), freq="W-MON"))


class FullCycleReinvestmentTests(unittest.TestCase):
    def test_recycles_actual_sale_proceeds_into_later_btc_purchase(self):
        # Prior week's signal enters at observation 1, sells at 3, rebuys at 5.
        data = fixture([100, 100, 100, 300, 300, 100, 300],
                       [0, 0.5, 1, .5, 0, .5, .5])
        result = simulate(data, initial_cash=1000, fee_rate=0,
                          buy_weeks=1, sell_weeks=1)
        self.assertEqual(result["buy_plans"], 2)
        self.assertEqual(result["sell_plans"], 1)
        self.assertAlmostEqual(result["btc_held"], 30)
        self.assertAlmostEqual(result["ending_equity_aud"], 9000)
        self.assertAlmostEqual(result["cash_remaining_aud"], 0)

    def test_signal_lag_prevents_trading_on_first_observation(self):
        data = fixture([10, 20, 30], [.9, .1, .1])
        result = simulate(data, initial_cash=100, fee_rate=0,
                          buy_weeks=1, sell_weeks=1)
        self.assertEqual(result["equity_path"][0]["action"], "HOLD")
        self.assertEqual(result["equity_path"][1]["action"], "BUY")
        self.assertEqual(result["equity_path"][1]["prior_risk"], .1)

    def test_windows_execute_equal_tranches_even_during_reversal(self):
        data = fixture([100, 100, 100, 100, 100, 200],
                       [0, 1, 1, 1, 1, 1])
        result = simulate(data, initial_cash=1000, fee_rate=0,
                          buy_weeks=3, sell_weeks=2)
        self.assertEqual([x["action"] for x in result["equity_path"][:3]],
                         ["BUY", "BUY", "BUY"])
        self.assertEqual(result["equity_path"][3]["action"], "SELL")
        self.assertEqual(result["equity_path"][4]["action"], "SELL")
        self.assertEqual(result["sell_plans"], 1)
        self.assertEqual(result["cash_remaining_aud"], 1000)

    def test_fees_preserve_accounting_and_reduce_value(self):
        data = fixture([100, 100, 100, 200, 200],
                       [0, 0.5, 1, .5, .5])
        no_fee = simulate(data, initial_cash=1000, fee_rate=0,
                          buy_weeks=1, sell_weeks=1)
        fee = simulate(data, initial_cash=1000, fee_rate=.01,
                       buy_weeks=1, sell_weeks=1)
        self.assertLess(fee["ending_equity_aud"], no_fee["ending_equity_aud"])
        self.assertGreater(fee["total_fees_aud"], 0)
        for row in fee["equity_path"]:
            self.assertGreaterEqual(row["cash_aud"], 0)
            self.assertGreaterEqual(row["btc_held"], 0)
            self.assertAlmostEqual(
                row["equity_aud"],
                row["cash_aud"] + row["btc_held"] * row["price_aud"])

    def test_buy_hold_buys_at_same_first_eligible_week(self):
        data = fixture([50, 100, 200], [0, 1, 1])
        b = matched_hold(data, initial_cash=1000, fee_rate=.01)
        self.assertAlmostEqual(b["ending_equity_aud"], 1980)
        self.assertEqual(b["entry_date"], str(data.index[1]))

    def test_incomplete_terminal_plan_is_marked_to_market(self):
        data = fixture([100, 100, 200], [0, 0, 0])
        result = simulate(data, initial_cash=1000, fee_rate=0,
                          buy_weeks=4, sell_weeks=4)
        self.assertTrue(result["incomplete_terminal_plan"])
        self.assertAlmostEqual(result["cash_remaining_aud"], 500)
        self.assertAlmostEqual(result["btc_held"], 3.75)
        self.assertAlmostEqual(result["ending_equity_aud"], 1250)

    def test_invalid_inputs_are_rejected_not_imputed(self):
        data = fixture([100, 110, 120], [0, float("nan"), 1])
        with self.assertRaises(ValueError):
            validate_history(data)
        with self.assertRaises(ValueError):
            simulate(fixture([100, 0, 120], [0, 0, 1]))
        with self.assertRaises(ValueError):
            simulate(fixture([100, 110, 120], [0, 0, 1]),
                     buy_weeks=0)
        with self.assertRaises(ValueError):
            simulate(fixture([100, 110, 120], [0, 0, 1]),
                     buy_risk=.9, sell_risk=.7)

    def test_report_is_one_continuous_account_not_fold_resets(self):
        data = fixture([100, 100, 200, 200, 100, 100, 250],
                       [0, 1, 1, 0, 0, 1, .5])
        summary = evaluate(data, initial_cash=1000, fee_rate=0)
        self.assertEqual(summary["observations"], 7)
        self.assertEqual(summary["capital_aud"], 1000)
        self.assertEqual(len(summary["scenarios"]), 7)
        self.assertEqual(summary["benchmark"]["entry_date"],
                         str(data.index[1]))
        self.assertTrue(all(row["ending_equity_aud"] > 0
                            for row in summary["scenarios"]))


if __name__ == "__main__":
    unittest.main()
