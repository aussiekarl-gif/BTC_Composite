import inspect
import math
import unittest
from datetime import date, timedelta

import pandas as pd

from engines.research import v60_200wma_sell_reentry_study as study_mod
from engines.research.v60_200wma_backtest import build_weekly_execution_rows
from engines.research.v60_200wma_policy import weekly_prior_200wma_signals
from engines.research.v60_200wma_sell_reentry_study import (
    STUDY_NAMES, simulate_sell_reentry, roll_sell_reentry_cohorts,
    summarise_study, study_spec,
)


def flat_rows(price=100_000.0, ratio=0.70, count=104, start=date(2020, 1, 6)):
    return [
        {
            "signal_date": start + timedelta(weeks=i) - timedelta(days=1),
            "execution_date": start + timedelta(weeks=i),
            "ratio_to_200wma": ratio,
            "btc_price_aud": price,
        }
        for i in range(count)
    ]


def study_rows(ratios, prices=None, start=date(2020, 1, 6)):
    rows = []
    for i, ratio in enumerate(ratios):
        execution = start + timedelta(weeks=i)
        rows.append({
            "signal_date": execution - timedelta(days=1),
            "execution_date": execution,
            "ratio_to_200wma": float(ratio),
            "btc_price_aud": float(prices[i]) if prices is not None else 100_000.0,
        })
    return rows


# Ratios: flat (ladder buys while flat) -> return to the prior WMA once ->
# re-entry gap -> ratio falls back to the discount gate -> later flat weeks.
SCENARIO_RATIOS = (
    [0.70] * 20
    + [1.05]
    + [0.95] * 20
    + [0.85] * 5
    + [0.95] * 3
    + [0.70] * 55
)


class V60SellReEntryStudyTests(unittest.TestCase):
    def test_study_spec_resolution(self):
        spec = study_spec("return_to_200wma_sell_then_discount_reentry")
        self.assertEqual(spec["sell_rule"], "return_to_200wma")
        self.assertEqual(spec["reentry_rule"], "discount_threshold")
        spec = study_spec("return_to_200wma_sell_then_immediate_reentry")
        self.assertEqual(spec["sell_rule"], "return_to_200wma")
        self.assertEqual(spec["reentry_rule"], "immediate")
        spec = study_spec("take_profit_sell_then_discount_reentry")
        self.assertEqual(spec["sell_rule"], "take_profit")
        self.assertEqual(spec["reentry_rule"], "discount_threshold")
        spec = study_spec("take_profit_sell_then_immediate_reentry")
        self.assertEqual(spec["sell_rule"], "take_profit")
        self.assertEqual(spec["reentry_rule"], "immediate")
        with self.assertRaises(ValueError):
            study_spec("v59_sell_study")

    def test_study_outputs_are_research_only_and_carry_benchmark(self):
        for study in STUDY_NAMES:
            with self.subTest(study=study):
                result = simulate_sell_reentry(flat_rows(), study=study)
                self.assertTrue(result["research_only"])
                self.assertFalse(result["trade_executable"])
                benchmark = result["benchmark_fixed_weekly"]
                self.assertEqual(benchmark["policy"], "fixed_weekly")
                self.assertEqual(benchmark["cohort_start"], result["cohort_start"])
                self.assertEqual(benchmark["cohort_end"], result["cohort_end"])
                self.assertTrue(benchmark["research_only"])
                self.assertFalse(benchmark["trade_executable"])
                self.assertIn("delta_total_return_pct", result)
                summary = summarise_study([result])
                self.assertEqual(len(summary), 1)
                self.assertTrue(summary[0]["research_only"])
                self.assertFalse(summary[0]["trade_executable"])

    def test_flat_rows_have_no_sales_and_guardrails_hold(self):
        result = simulate_sell_reentry(
            flat_rows(ratio=0.70),
            study="return_to_200wma_sell_then_discount_reentry",
        )
        self.assertEqual(result["sales_count"], 0)
        self.assertGreater(result["buy_count"], 0)
        self.assertGreaterEqual(result["cash_remaining_aud"], -1e-6)
        self.assertGreaterEqual(result["btc_held"], 0)
        self.assertLessEqual(result["max_drawdown_pct"], 1e-9)
        self.assertLessEqual(result["biggest_weekly_spend_aud"], 25_500.0 + 1e-6)

    def test_discount_gate_defers_reentry_after_sell_vs_immediate(self):
        rows = study_rows(SCENARIO_RATIOS)
        gated = simulate_sell_reentry(
            rows, study="return_to_200wma_sell_then_discount_reentry",
            reentry_ratio=0.90,
        )
        immediate = simulate_sell_reentry(
            rows, study="return_to_200wma_sell_then_immediate_reentry",
        )
        self.assertEqual(gated["sales_count"], 1)
        self.assertEqual(immediate["sales_count"], 1)
        self.assertEqual(gated["round_trips"], 1)
        self.assertEqual(immediate["round_trips"], 1)
        self.assertEqual(gated["median_reentry_weeks_after_sell"], 21.0)
        self.assertEqual(immediate["median_reentry_weeks_after_sell"], 0.0)
        self.assertEqual(gated["weeks_holding_fraction"], 81 / 104)
        self.assertEqual(immediate["weeks_holding_fraction"], 102 / 104)
        self.assertGreaterEqual(gated["cash_remaining_aud"], -1e-6)
        self.assertGreaterEqual(gated["btc_held"], 0)

    def test_take_profit_sell_and_reentry(self):
        prices = [50_000.0 * 1.10 ** i for i in range(104)]
        result = simulate_sell_reentry(
            study_rows([0.70] * 104, prices=prices),
            study="take_profit_sell_then_discount_reentry",
            take_profit_pct=20.0,
        )
        self.assertGreaterEqual(result["sales_count"], 1)
        realized = result["median_realized_sell_return_pct"]
        self.assertIsNotNone(realized)
        self.assertGreaterEqual(realized, 5.0)
        self.assertLessEqual(realized, 95.0)
        self.assertGreaterEqual(result["cash_remaining_aud"], -1e-6)
        self.assertGreaterEqual(result["btc_held"], 0)

    def test_roll_cohorts_are_matched_and_benchmark_is_fixed_weekly(self):
        rows = flat_rows(count=106)
        results = roll_sell_reentry_cohorts(
            rows, study="return_to_200wma_sell_then_discount_reentry",
            floors_pct=(0.0,), threshold_sets=("20_25_30",),
        )
        self.assertEqual(len(results), 3)
        for result in results:
            self.assertEqual(result["observations"], 104)
            self.assertEqual(result["benchmark_policy"], "fixed_weekly")
            self.assertEqual(
                result["benchmark_fixed_weekly"]["observations"], 104
            )
            self.assertEqual(
                result["benchmark_fixed_weekly"]["cohort_start"],
                result["cohort_start"],
            )
            self.assertEqual(
                result["benchmark_fixed_weekly"]["cohort_end"],
                result["cohort_end"],
            )
            self.assertEqual(result["sales_count"], 0)
        starts = {r["cohort_start"] for r in results}
        self.assertEqual(len(starts), 3)
        summary = summarise_study(results)
        self.assertEqual(len(summary), 1)
        entry = summary[0]
        self.assertEqual(entry["cohort_count"], 3)
        self.assertEqual(entry["study"], "return_to_200wma_sell_then_discount_reentry")
        self.assertIn("median_delta_total_return_vs_fixed_weekly_pct", entry)
        self.assertTrue(entry["overlapping_cohorts_not_independent"])
        self.assertTrue(entry["research_only"])
        self.assertFalse(entry["trade_executable"])

    def test_summary_discloses_overlap_and_marks_all_outputs(self):
        results = roll_sell_reentry_cohorts(
            flat_rows(count=106),
            study="take_profit_sell_then_discount_reentry",
        )
        summary = summarise_study(results)
        self.assertTrue(summary)
        for entry in summary:
            self.assertTrue(entry["overlapping_cohorts_not_independent"])
            self.assertGreater(entry["cohort_count"], 0)
            self.assertTrue(entry["research_only"])
            self.assertFalse(entry["trade_executable"])
            self.assertIsNotNone(entry["median_delta_total_return_vs_fixed_weekly_pct"])

    def test_invalid_inputs_fail_closed(self):
        rows = flat_rows()
        with self.subTest(case="unknown_study"):
            with self.assertRaises(ValueError):
                simulate_sell_reentry(rows, study="v59_study")
        with self.subTest(case="reentry_at_sell_ratio"):
            with self.assertRaises(ValueError):
                simulate_sell_reentry(
                    rows, study="return_to_200wma_sell_then_discount_reentry",
                    reentry_ratio=1.0,
                )
        with self.subTest(case="zero_reentry_ratio"):
            with self.assertRaises(ValueError):
                simulate_sell_reentry(
                    rows, study="return_to_200wma_sell_then_discount_reentry",
                    reentry_ratio=0.0,
                )
        with self.subTest(case="zero_sell_fraction"):
            with self.assertRaises(ValueError):
                simulate_sell_reentry(
                    rows, study="return_to_200wma_sell_then_discount_reentry",
                    sell_fraction=0.0,
                )
        with self.subTest(case="sell_fraction_above_one"):
            with self.assertRaises(ValueError):
                simulate_sell_reentry(
                    rows, study="return_to_200wma_sell_then_discount_reentry",
                    sell_fraction=1.5,
                )
        with self.subTest(case="take_profit_zero"):
            with self.assertRaises(ValueError):
                simulate_sell_reentry(
                    rows, study="take_profit_sell_then_discount_reentry",
                    take_profit_pct=0.0,
                )
        with self.subTest(case="take_profit_reentry_above_one"):
            with self.assertRaises(ValueError):
                simulate_sell_reentry(
                    rows, study="take_profit_sell_then_discount_reentry",
                    reentry_ratio=1.5,
                )
        with self.subTest(case="non_finite_ratio"):
            with self.assertRaises(ValueError):
                simulate_sell_reentry(
                    rows, study="return_to_200wma_sell_then_discount_reentry",
                    sell_ratio=float("nan"),
                )
        with self.subTest(case="zero_ratio_row"):
            bad_rows = flat_rows()
            bad_rows[3]["ratio_to_200wma"] = 0
            with self.assertRaises(ValueError):
                simulate_sell_reentry(
                    bad_rows, study="return_to_200wma_sell_then_discount_reentry",
                )
        with self.subTest(case="short_cohort"):
            with self.assertRaises(ValueError):
                simulate_sell_reentry(
                    flat_rows(count=50),
                    study="return_to_200wma_sell_then_discount_reentry",
                )
        with self.subTest(case="unknown_candidate"):
            with self.assertRaises(ValueError):
                simulate_sell_reentry(
                    rows, study="return_to_200wma_sell_then_discount_reentry",
                    candidate="v59",
                )
        with self.subTest(case="short_rows_roll"):
            with self.assertRaises(ValueError):
                roll_sell_reentry_cohorts(flat_rows(count=50))

    def test_study_signals_are_strictly_prior_from_policy_module(self):
        index = pd.date_range("2014-01-05", periods=400 * 7 + 1, freq="D", tz="UTC")
        prices = pd.Series([100.0 + i for i in range(len(index))], index=index)
        result = weekly_prior_200wma_signals(prices)
        last = result.iloc[-1]
        weekly = prices.resample("W-SUN").last()
        pos = weekly.index.get_loc(last["signal_date"])
        expected = weekly.iloc[pos - 200:pos].mean()
        self.assertAlmostEqual(last["prior_200wma_usd"], expected)
        self.assertNotEqual(
            last["prior_200wma_usd"], weekly.iloc[pos - 200:pos + 1].mean()
        )

    def test_execution_rows_are_signal_sunday_plus_one_day(self):
        index = pd.date_range("2015-01-01", periods=(210 + 120) * 7, freq="D", tz="UTC")
        base = 20_000.0
        prices = pd.Series(
            [base * (1.0 + 0.0005 * i) for i in range(len(index))], index=index
        )
        fx = pd.Series([1.5] * len(index), index=index)
        rows = build_weekly_execution_rows(prices, fx)
        self.assertGreaterEqual(len(rows), 104)
        for row in rows:
            self.assertEqual((row["execution_date"] - row["signal_date"]).days, 1)
            self.assertEqual(row["signal_date"].weekday(), 6)
            self.assertEqual(row["execution_date"].weekday(), 0)
            self.assertTrue(math.isfinite(row["ratio_to_200wma"]))

    def test_no_v59_or_production_imports(self):
        source = inspect.getsource(study_mod)
        self.assertNotIn("v59_", source)
        self.assertNotIn("production_model", source)
        self.assertIn("v60_200wma_backtest", source)
        self.assertIn("v60_200wma_policy", source)


if __name__ == "__main__":
    unittest.main()
