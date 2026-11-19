import unittest
from datetime import date, timedelta

import pandas as pd

from engines.research import v60_200wma_policy as policy


class V60PolicyTests(unittest.TestCase):
    def test_base_dca_remains_active_above_and_near_200wma(self):
        for ratio in (1.50, 1.00, 0.90, 0.800001):
            self.assertEqual(policy.allocation_for_discount(ratio), 2.5)

    def test_discount_tier_boundaries_are_inclusive(self):
        expected = {
            0.800001: 2.5,
            0.80: 3.5,
            0.75: 5.0,
            0.70: 7.5,
        }
        for ratio, amount in expected.items():
            self.assertEqual(policy.allocation_for_discount(ratio), amount)

    def test_all_candidates_are_monotonic(self):
        ratios = (1.2, 1.0, 0.9, 0.8, 0.75, 0.7, 0.6)
        for candidate in policy.CANDIDATE_LADDERS:
            values = [policy.allocation_for_discount(x, candidate=candidate)
                      for x in ratios]
            self.assertEqual(values, sorted(values))

    def test_invalid_ratios_and_candidates_fail_closed(self):
        for ratio in (0, -1, float("nan"), float("inf")):
            with self.assertRaises(ValueError):
                policy.allocation_for_discount(ratio)
        with self.assertRaises(ValueError):
            policy.allocation_for_discount(0.7, candidate="v59")

    def test_cash_reserve_is_not_spent(self):
        plan = policy.calculate_buy_plan(
            ratio_to_200wma=0.70, available_cash_aud=100_000,
            original_capital_aud=510_000, initial_cash_aud=200_000,
            protected_cash_floor_pct_initial_cash=30.0,
        )
        self.assertEqual(plan["protected_cash_floor_aud"], 60_000)
        self.assertEqual(plan["deployable_cash_aud"], 40_000)
        self.assertEqual(plan["buy_pct_deployable_cash"], 7.5)
        self.assertEqual(plan["buy_aud"], 3_000)

    def test_weekly_hard_cap_is_independent_of_cash_percentage(self):
        plan = policy.calculate_buy_plan(
            ratio_to_200wma=0.70, available_cash_aud=1_000_000,
            original_capital_aud=510_000, initial_cash_aud=1_000_000,
        )
        self.assertEqual(plan["buy_aud"], 25_500)
        self.assertLessEqual(plan["buy_aud"], plan["weekly_hard_cap_aud"])

    def test_plan_is_non_executable_and_percentage_first(self):
        plan = policy.calculate_buy_plan(
            ratio_to_200wma=0.75, available_cash_aud=200_000,
            original_capital_aud=510_000, initial_cash_aud=200_000,
        )
        self.assertEqual(plan["buy_pct_deployable_cash"], 5.0)
        self.assertEqual(plan["buy_aud"], 10_000)
        self.assertFalse(plan["trade_executable"])
        self.assertTrue(plan["research_only"])

    def test_wma_uses_previous_200_completed_sundays_only(self):
        index = pd.date_range("2014-01-05", periods=400*7+1, freq="D", tz="UTC")
        prices = pd.Series([100.0+i for i in range(len(index))], index=index)
        result = policy.weekly_prior_200wma_signals(prices)
        last = result.iloc[-1]
        weekly = prices.resample("W-SUN").last()
        pos = weekly.index.get_loc(last["signal_date"])
        expected = weekly.iloc[pos-200:pos].mean()
        self.assertAlmostEqual(last["prior_200wma_usd"], expected)
        self.assertNotEqual(last["prior_200wma_usd"],
                            weekly.iloc[pos-199:pos+1].mean())

    def test_no_v59_or_production_imports(self):
        import inspect
        source = inspect.getsource(policy)
        self.assertNotIn("v59_", source)
        self.assertNotIn("production_model", source)


if __name__ == "__main__":
    unittest.main()
