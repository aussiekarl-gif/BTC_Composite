"""Regression tests for the research-only below-200WMA carry allocator.

The rule uses the prior completed weekly MA, carries skipped weekly budget
forward, and never forces a purchase on a nonqualifying final observation.
"""
import unittest
import pandas as pd
from engines.research.research_model import apply_below_200wma_carry_allocator


class Below200WMACarryTests(unittest.TestCase):
    def data(self, prices, prior_mas):
        return pd.DataFrame({
            "price_usd": prices,
            "weekly_ma200_strict_prior": prior_mas,
            "btc_price_aud": prices,
        }, index=pd.date_range("2024-01-01", periods=len(prices), freq="W-MON"))

    def test_carries_cash_until_next_eligible_week(self):
        df, summary = apply_below_200wma_carry_allocator(
            self.data([120, 110, 90, 130], [100, 100, 100, 100]),
            total_budget_aud=400, fee_pct=0,
        )
        self.assertEqual(df["actual_buy_aud"].tolist(), [0, 0, 300, 0])
        self.assertAlmostEqual(summary["cash_remaining_aud"], 100)
        self.assertEqual(summary["buy_count"], 1)
        self.assertAlmostEqual(summary["total_invested_aud"] + summary["cash_remaining_aud"], 400)

    def test_final_eligible_week_spends_remaining_budget(self):
        df, summary = apply_below_200wma_carry_allocator(
            self.data([120, 110, 90], [100, 100, 100]),
            total_budget_aud=300,
        )
        self.assertEqual(df["actual_buy_aud"].tolist(), [0, 0, 300])
        self.assertAlmostEqual(summary["cash_remaining_aud"], 0)

    def test_final_ineligible_week_keeps_cash(self):
        df, summary = apply_below_200wma_carry_allocator(
            self.data([120, 110, 130], [100, 100, 100]),
            total_budget_aud=300,
        )
        self.assertTrue((df["actual_buy_aud"] == 0).all())
        self.assertAlmostEqual(summary["cash_remaining_aud"], 300)
        self.assertAlmostEqual(summary["total_value_including_cash_aud"], 300)

    def test_equal_to_ma_does_not_buy_and_missing_ma_does_not_buy(self):
        df, summary = apply_below_200wma_carry_allocator(
            self.data([100, 90, 80], [100, float("nan"), 100]),
            total_budget_aud=300,
        )
        self.assertEqual(df["actual_buy_aud"].tolist(), [0, 0, 300])
        self.assertEqual(summary["eligible_week_count"], 1)

    def test_fees_reduce_btc_not_budget_accounting(self):
        df, summary = apply_below_200wma_carry_allocator(
            self.data([80, 80], [100, 100]),
            total_budget_aud=200, fee_pct=0.01,
        )
        self.assertAlmostEqual(summary["total_invested_aud"], 200)
        self.assertAlmostEqual(summary["fees_aud"], 2)
        self.assertAlmostEqual(summary["btc_held"], 198 / 80)
        self.assertAlmostEqual(summary["total_value_including_cash_aud"], 198)


if __name__ == "__main__":
    unittest.main()
