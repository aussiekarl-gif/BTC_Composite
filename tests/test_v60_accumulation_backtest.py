"""Tests for V6.0 matched accumulation ranking by BTC units and AUD value."""
import unittest

import pandas as pd

from engines.research.v60_accumulation_backtest import (
    build_ranking_results, summarise_ranking, add_rank_columns,
    reference_leaderboards, POLICY_CONFIGS, CASH_YIELDS, CASH_FLOORS,
    CUMULATIVE_CAPS, REFERENCE,
)


def sample_rows(discount_ratio=0.70, count=104):
    rows = []
    for i in range(count):
        sunday = pd.Timestamp("2020-01-05", tz="UTC") + pd.Timedelta(weeks=i)
        rows.append({
            "signal_date": sunday.date(),
            "execution_date": (sunday + pd.Timedelta(days=1)).date(),
            "btc_usd_signal_close": 50_000.0 + i * 100.0,
            "prior_200wma_usd": 100_000.0,
            "ratio_to_200wma": discount_ratio,
            "discount_below_200wma_pct": (1.0 - discount_ratio) * 100.0,
            "btc_price_aud": 70_000.0 + i * 50.0,
            "fx_date": sunday.date(),
            "usd_per_aud": 0.67,
        })
    return rows


class V60AccumulationRankingTests(unittest.TestCase):
    def test_results_are_matched_to_fixed_dca_by_cohort_and_limits(self):
        results = build_ranking_results(sample_rows())
        configs = len(POLICY_CONFIGS)
        settings = len(CASH_YIELDS) * len(CASH_FLOORS) * len(CUMULATIVE_CAPS)
        self.assertEqual(len(results), configs * settings)
        fixed = results.loc[results["policy"] == "fixed_weekly"]
        self.assertEqual(len(fixed), settings)
        for _, row in results.loc[results["policy"] != "fixed_weekly"].iterrows():
            peers = fixed.loc[
                (fixed["cash_yield"] == row["cash_yield"])
                & (fixed["protected_cash_floor_pct_initial_cash"]
                   == row["protected_cash_floor_pct_initial_cash"])
                & (fixed["max_cumulative_buy_spend_pct_initial_cash"].fillna(-1)
                   == (-1 if pd.isna(row["max_cumulative_buy_spend_pct_initial_cash"])
                       else row["max_cumulative_buy_spend_pct_initial_cash"]))
            ]
            self.assertEqual(len(peers), 1)

    def test_summary_reports_both_objectives_and_downside(self):
        summary = summarise_ranking(build_ranking_results(sample_rows()))
        self.assertEqual(len(summary), (len(POLICY_CONFIGS) - 1)
                         * len(CASH_YIELDS) * len(CASH_FLOORS) * len(CUMULATIVE_CAPS))
        self.assertTrue((summary["split"] == "train").all())
        self.assertTrue(summary["cohorts_overlap"].all())
        for column in (
            "median_btc_held", "median_final_equity_aud",
            "median_btc_uplift_vs_matched_fixed_pct",
            "median_final_equity_uplift_vs_matched_fixed_pct",
            "p10_btc_uplift_vs_matched_fixed_pct",
            "worst_final_equity_uplift_vs_matched_fixed_pct",
            "cohort_win_rate_btc_pct", "cohort_win_rate_final_equity_pct",
            "median_max_drawdown_difference_vs_fixed_pp",
        ):
            self.assertIn(column, summary.columns)

    def test_aggressive_spending_accumulates_more_btc_than_slower_policies(self):
        summary = summarise_ranking(build_ranking_results(sample_rows()))
        view = summary.loc[
            (summary["cash_yield_annual_pct"] == 0.0)
            & (summary["protected_cash_floor_pct_initial_cash"] == 0.0)
            & (summary["cumulative_spend_cap_pct_initial_cash"] == "uncapped")
        ].set_index("policy")
        self.assertGreater(
            view.loc["aggressive_20_25_30", "median_btc_held"],
            view.loc["measured_20_25_30", "median_btc_held"],
        )
        self.assertGreater(
            view.loc["measured_20_25_30", "median_btc_held"],
            view.loc["baseline_2_5pct", "median_btc_held"],
        )
        self.assertLess(
            view.loc["measured_0_5x_20_25_30", "median_btc_held"],
            view.loc["measured_20_25_30", "median_btc_held"],
        )

    def test_ranks_are_within_matched_setting_and_can_diverge(self):
        ranked = add_rank_columns(summarise_ranking(build_ranking_results(sample_rows())))
        keys = [
            "split", "cash_yield_annual_pct", "protected_cash_floor_pct_initial_cash",
            "cumulative_spend_cap_pct_initial_cash",
        ]
        for _, group in ranked.groupby(keys):
            self.assertEqual(int(group["btc_rank"].min()), 1)
            self.assertEqual(int(group["equity_rank"].min()), 1)
            by_btc = group.sort_values("median_btc_uplift_vs_matched_fixed_pct",
                                       ascending=False)
            self.assertTrue(by_btc["btc_rank"].is_monotonic_increasing)
            best_btc = group.loc[group["btc_rank"] == 1]
            self.assertAlmostEqual(
                float(best_btc["median_btc_uplift_vs_matched_fixed_pct"].max()),
                float(group["median_btc_uplift_vs_matched_fixed_pct"].max()),
                places=8,
            )
            by_equity = group.sort_values("median_final_equity_uplift_vs_matched_fixed_pct",
                                          ascending=False)
            self.assertTrue(by_equity["equity_rank"].is_monotonic_increasing)
        self.assertIn("rank_divergence", ranked.columns)

    def test_reference_leaderboards_cover_train_and_holdout_splits(self):
        summary = summarise_ranking(build_ranking_results(sample_rows()))
        ranked = add_rank_columns(summary)
        boards = reference_leaderboards(ranked, limit=3)
        self.assertEqual(set(boards), {"train"})
        self.assertEqual(len(boards["train"]["by_btc_uplift"]), 3)
        self.assertEqual(len(boards["train"]["by_equity_uplift"]), 3)

    def test_reference_setting_is_buy_only_and_research_only(self):
        self.assertEqual(REFERENCE["cash_yield_annual_pct"], 5.0)
        self.assertEqual(REFERENCE["protected_cash_floor_pct_initial_cash"], 0.0)
        self.assertEqual(REFERENCE["cumulative_spend_cap_pct_initial_cash"], "uncapped")
        results = build_ranking_results(sample_rows())
        self.assertTrue(results["research_only"].all())
        self.assertFalse(results["trade_executable"].any())
        self.assertNotIn("sell_pct_of_current_holdings", results.columns)

    def test_insufficient_history_fails_closed(self):
        with self.assertRaisesRegex(ValueError, "Insufficient"):
            build_ranking_results(sample_rows(count=103))


if __name__ == "__main__":
    unittest.main()
