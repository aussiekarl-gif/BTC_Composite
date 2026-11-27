"""Regression tests for matched-budget historical V6.0 pacing analysis."""
from datetime import date, timedelta
import unittest
import pandas as pd

from engines.research.v60_historical_pacing_report import (
    build_pacing_results, summarise_pacing,
)


def sample_weekly_rows():
    rows = []
    sunday = date(2016, 12, 25)
    for i in range(104):
        signal = sunday + timedelta(days=7 * i)
        execution = signal + timedelta(days=1)
        rows.append({
            "signal_date": signal,
            "execution_date": execution,
            "btc_usd_signal_close": 50000.0 + i * 100.0,
            "prior_200wma_usd": 100000.0,
            "ratio_to_200wma": 0.70 if i % 4 == 0 else 0.90,
            "discount_below_200wma_pct": 30.0 if i % 4 == 0 else 10.0,
            "btc_price_aud": 70000.0 + i * 50.0,
            "fx_date": signal,
            "usd_per_aud": 0.67,
        })
    return rows


class V60HistoricalPacingTests(unittest.TestCase):
    def test_all_dynamic_policies_have_identical_cap_reserve_and_yield_benchmarks(self):
        results = build_pacing_results(sample_weekly_rows())
        self.assertEqual(len(results), 100)
        fixed = results.loc[results["policy"] == "fixed_weekly"]
        self.assertEqual(len(fixed), 20)
        for _, row in results.iterrows():
            if row["policy"] == "fixed_weekly":
                continue
            peers = fixed.loc[
                (fixed["cash_yield"] == row["cash_yield"])
                & (fixed["protected_cash_floor_pct_initial_cash"] == row["protected_cash_floor_pct_initial_cash"])
                & (
                    fixed["max_cumulative_buy_spend_pct_initial_cash"].fillna(-1)
                    == (-1 if pd.isna(row["max_cumulative_buy_spend_pct_initial_cash"])
                        else row["max_cumulative_buy_spend_pct_initial_cash"])
                )
            ]
            self.assertEqual(len(peers), 1)

    def test_summary_reports_matched_holdout_and_train_cohorts(self):
        results = build_pacing_results(sample_weekly_rows())
        summary = summarise_pacing(results)
        self.assertTrue((summary["split"] == "train").all())
        self.assertEqual(set(summary["policy"]), {
            "baseline", "measured_20_25_30", "measured_10_15_20", "stepped_20_25_30"
        })
        self.assertTrue(summary["cohorts_overlap"].all())
        self.assertIn("median_spend_difference_vs_matched_fixed_pct", summary.columns)
        self.assertIn("p10_final_equity_uplift_vs_matched_fixed_pct", summary.columns)
        self.assertIn("median_max_drawdown_difference_vs_fixed_pp", summary.columns)\n        self.assertIn("median_equal_buy_amount_uniform_dates_btc_uplift_pct", summary.columns)\n        self.assertIn("median_actual_spend_distribution_uniform_dates_btc_timing_only_pct", summary.columns)

    def test_cumulative_caps_are_enforced_in_each_replay(self):
        results = build_pacing_results(sample_weekly_rows())
        capped = results.loc[results["max_cumulative_buy_spend_pct_initial_cash"].notna()]
        for _, row in capped.iterrows():
            budget = row["max_cumulative_buy_budget_aud"]
            self.assertLessEqual(row["total_buy_spend_aud"], budget + 1e-6)


if __name__ == "__main__":
    unittest.main()
