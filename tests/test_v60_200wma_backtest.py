import unittest
from datetime import date, timedelta

from engines.research.v60_200wma_backtest import (
    simulate_weekly_cohort, rolling_104_week_comparison,
    summarise_matched_cohorts, validate_weekly_cohort,
)


def flat_rows(price=100_000.0, ratio=0.70, count=104):
    start = date(2020, 1, 6)
    return [
        {
            "signal_date": start + timedelta(weeks=i) - timedelta(days=1),
            "execution_date": start + timedelta(weeks=i),
            "ratio_to_200wma": ratio,
            "btc_price_aud": price,
        }
        for i in range(count)
    ]


class V60BacktestTests(unittest.TestCase):
    def test_fixed_weekly_and_dynamic_run_same_cohort(self):
        rows = flat_rows()
        fixed = simulate_weekly_cohort(rows, policy="fixed_weekly")
        measured = simulate_weekly_cohort(rows, policy="measured")
        self.assertEqual(fixed["cohort_start"], measured["cohort_start"])
        self.assertEqual(fixed["observations"], 104)
        self.assertTrue(fixed["research_only"])
        self.assertFalse(fixed["trade_executable"])

    def test_constant_price_same_spend_timing_diagnostic_is_zero(self):
        result = simulate_weekly_cohort(flat_rows(price=100_000), policy="aggressive")
        self.assertAlmostEqual(
            result["same_spend_same_count_btc_timing_uplift_pct_hindsight"], 0.0, places=8
        )

    def test_weekly_cap_is_never_exceeded(self):
        result = simulate_weekly_cohort(
            flat_rows(price=10_000, ratio=0.70), policy="aggressive"
        )
        self.assertLessEqual(result["biggest_buy_pct_original_capital"], 5.0 + 1e-9)
        self.assertLessEqual(result["biggest_buy_aud"], 25_500.0 + 1e-6)

    def test_protected_cash_floor_is_never_spent(self):
        result = simulate_weekly_cohort(
            flat_rows(price=10_000, ratio=0.70), policy="aggressive",
            protected_cash_floor_pct_initial_cash=30.0,
        )
        self.assertGreaterEqual(
            result["cash_remaining_aud"], result["protected_cash_floor_aud"] - 1e-6
        )

    def test_weekly_gaps_are_rejected(self):
        rows = flat_rows()
        rows[50]["execution_date"] += timedelta(days=1)
        with self.assertRaisesRegex(ValueError, "strictly prior Sunday|missing or irregular"):
            validate_weekly_cohort(rows)

    def test_rolling_comparison_is_matched_and_reports_overlap(self):
        rows = flat_rows(count=106)
        results = rolling_104_week_comparison(
            rows, floors_pct=(0.0,), threshold_sets=("20_25_30", "10_15_20")
        )
        self.assertEqual(len(results), 3 * 8)
        summary = summarise_matched_cohorts(results)
        self.assertEqual(len(summary), 8)
        self.assertTrue(all(x["overlapping_cohorts_not_independent"] for x in summary))

    def test_invalid_inputs_fail_closed(self):
        rows = flat_rows()
        rows[3]["ratio_to_200wma"] = 0
        with self.assertRaises(ValueError):
            simulate_weekly_cohort(rows, policy="measured")
        with self.assertRaises(ValueError):
            simulate_weekly_cohort(flat_rows(), policy="v59")


if __name__ == "__main__":
    unittest.main()
