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
        self.assertEqual(measured["median_final_equity_uplift_vs_fixed_weekly_pct"], 5.0)
        self.assertEqual(measured["median_btc_uplift_vs_fixed_weekly_pct"], 10.0)
        self.assertEqual(measured["cohort_win_rate_final_equity_vs_fixed_weekly_pct"], 100.0)
        self.assertTrue(measured["cohorts_overlap"])

    def test_v60_report_has_no_v59_or_production_imports(self):
        from pathlib import Path
        import inspect
        import engines.research.v60_historical_report as report
        source = inspect.getsource(report)
        self.assertNotIn("v59_", source)
        self.assertNotIn("production_model", source)


if __name__ == "__main__":
    unittest.main()
