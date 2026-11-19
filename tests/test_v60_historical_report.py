import unittest

from engines.research.v60_historical_report import (
    assign_validation_split, summarise,
)


class V60HistoricalReportTests(unittest.TestCase):
    def test_train_bridge_and_holdout_are_chronologically_separated(self):
        self.assertEqual(assign_validation_split({
            "cohort_start": "2019-01-07", "cohort_end": "2021-12-27",
        }), "train")
        self.assertEqual(assign_validation_split({
            "cohort_start": "2021-01-04", "cohort_end": "2023-01-02",
        }), "bridge_excluded")
        self.assertEqual(assign_validation_split({
            "cohort_start": "2022-01-03", "cohort_end": "2024-12-30",
        }), "holdout")

    def test_summary_compares_each_policy_with_same_cohort_fixed_weekly(self):
        common = {
            "cohort_start": "2022-01-03",
            "cohort_end": "2024-01-01",
            "cash_yield": 0.05,
            "threshold_set": "20_25_30",
            "protected_cash_floor_pct_initial_cash": 20.0,
            "observations": 104,
            "cash_remaining_aud": 100_000.0,
            "total_buy_spend_aud": 200_000.0,
            "buy_count": 40,
            "max_drawdown_pct": -20.0,
            "same_spend_same_count_btc_timing_uplift_pct_hindsight": 2.0,
        }
        rows = [
            {**common, "policy": "fixed_weekly", "final_equity_aud": 600_000.0, "btc_held": 5.0},
            {**common, "policy": "measured", "final_equity_aud": 630_000.0, "btc_held": 5.5},
        ]
        summary = summarise(rows)
        measured = summary.loc[summary["policy"] == "measured"].iloc[0]
        self.assertEqual(measured["split"], "holdout")
        self.assertAlmostEqual(measured["median_final_equity_uplift_vs_fixed_weekly_pct"], 5.0, places=8)
        self.assertAlmostEqual(measured["median_btc_uplift_vs_fixed_weekly_pct"], 10.0, places=8)
        self.assertEqual(measured["cohort_win_rate_final_equity_vs_fixed_weekly_pct"], 100.0)
        self.assertTrue(measured["cohorts_overlap"])


    def test_discount_activation_counts_report_sparse_valuation_events(self):
        from engines.research.v60_historical_report import discount_activation_counts
        rows = [
            {"execution_date": __import__("datetime").date(2021, 6, 7), "ratio_to_200wma": 0.70},
            {"execution_date": __import__("datetime").date(2022, 6, 6), "ratio_to_200wma": 0.79},
            {"execution_date": __import__("datetime").date(2022, 6, 13), "ratio_to_200wma": 0.74},
            {"execution_date": __import__("datetime").date(2023, 1, 2), "ratio_to_200wma": 0.69},
        ]
        result = discount_activation_counts(rows)
        self.assertEqual(result["pre_2022_train_era"]["at_least_10_pct_below_200wma"]["signal_week_count"], 1)
        self.assertEqual(result["pre_2022_train_era"]["at_least_15_pct_below_200wma"]["signal_week_count"], 1)
        self.assertEqual(result["pre_2022_train_era"]["at_least_20_pct_below_200wma"]["signal_week_count"], 1)
        self.assertEqual(result["2022_onward_holdout_era"]["at_least_10_pct_below_200wma"]["signal_week_count"], 3)
        self.assertEqual(result["2022_onward_holdout_era"]["at_least_15_pct_below_200wma"]["signal_week_count"], 3)
        self.assertEqual(result["2022_onward_holdout_era"]["at_least_20_pct_below_200wma"]["signal_week_count"], 3)
        self.assertEqual(result["2022_onward_holdout_era"]["at_least_25_pct_below_200wma"]["signal_week_count"], 2)
        self.assertEqual(result["2022_onward_holdout_era"]["at_least_30_pct_below_200wma"]["signal_week_count"], 1)
        self.assertEqual(result["2022_onward_holdout_era"]["at_least_35_pct_below_200wma"]["signal_week_count"], 1)

    def test_threshold_candidates_are_available_to_historical_replay(self):
        from engines.research.v60_200wma_policy import THRESHOLD_SETS
        self.assertEqual(THRESHOLD_SETS["10_15_20"], (10.0, 15.0, 20.0))
        self.assertEqual(THRESHOLD_SETS["15_20_30"], (15.0, 20.0, 30.0))
        self.assertEqual(THRESHOLD_SETS["20_25_30"], (20.0, 25.0, 30.0))
        self.assertEqual(THRESHOLD_SETS["20_25_35"], (20.0, 25.0, 35.0))

    def test_v60_report_has_no_v59_or_production_imports(self):
        from pathlib import Path
        import inspect
        import engines.research.v60_historical_report as report
        source = inspect.getsource(report)
        self.assertNotIn("v59_", source)
        self.assertNotIn("production_model", source)


if __name__ == "__main__":
    unittest.main()
