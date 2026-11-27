"""Tests for V6.0 proportional base-allocation sensitivity."""
from datetime import date, timedelta
import unittest

from engines.research.v60_200wma_policy import THRESHOLD_SETS
from engines.research.v60_allocation_scale_report import (
    build_scale_results, summarise_scale_results,
)


def sample_rows():
    start = date(2016, 12, 25)
    rows = []
    for i in range(104):
        sunday = start + timedelta(weeks=i)
        rows.append({
            "signal_date": sunday,
            "execution_date": sunday + timedelta(days=1),
            "btc_usd_signal_close": 50000.0 + i * 100.0,
            "prior_200wma_usd": 100000.0,
            "ratio_to_200wma": 0.70 if i % 5 == 0 else 0.90,
            "discount_below_200wma_pct": 30.0 if i % 5 == 0 else 10.0,
            "btc_price_aud": 70000.0 + i * 50.0,
            "fx_date": sunday,
            "usd_per_aud": 0.67,
        })
    return rows


class V60AllocationScaleReportTests(unittest.TestCase):
    def test_scales_are_matched_to_fixed_dca_by_cap_and_reserve(self):
        results = build_scale_results(sample_rows())
        self.assertEqual(len(results), 420)
        fixed = results.loc[results["policy"] == "fixed_weekly"]
        self.assertEqual(len(fixed), 20)
        for _, row in results.loc[results["policy"] == "measured"].iterrows():
            peers = fixed.loc[
                (fixed["cash_yield"] == row["cash_yield"])
                & (fixed["protected_cash_floor_pct_initial_cash"] == row["protected_cash_floor_pct_initial_cash"])
                & (
                    fixed["max_cumulative_buy_spend_pct_initial_cash"].fillna(-1)
                    == (-1 if __import__("pandas").isna(row["max_cumulative_buy_spend_pct_initial_cash"])
                        else row["max_cumulative_buy_spend_pct_initial_cash"])
                )
            ]
            self.assertEqual(len(peers), 1)

    def test_summary_reports_scale_and_downside_metrics(self):
        summary = summarise_scale_results(build_scale_results(sample_rows()))
        self.assertEqual(len(summary), 400)
        self.assertTrue((summary["split"] == "train").all())
        self.assertEqual(set(summary["cash_yield_annual_pct"]), {0.0, 5.0})
        self.assertEqual(set(summary["dynamic_allocation_scale"]), {0.5, 0.75, 1.0, 1.25, 1.5})
        self.assertIn("p10_final_equity_uplift_vs_matched_fixed_pct", summary.columns)
        self.assertIn("median_equal_buy_amount_uniform_dates_btc_uplift_pct", summary.columns)
        self.assertIn("median_actual_spend_distribution_uniform_dates_btc_timing_only_pct", summary.columns)
        self.assertEqual(set(summary["threshold_set"]), set(THRESHOLD_SETS))
        self.assertTrue(summary["cohorts_overlap"].all())


if __name__ == "__main__":
    unittest.main()
