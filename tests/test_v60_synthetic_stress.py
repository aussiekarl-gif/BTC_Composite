import unittest

from engines.research.v60_synthetic_stress import (
    build_scenario_rows, scenario_price_paths,
)
from engines.research.v60_200wma_backtest import simulate_weekly_cohort


class V60SyntheticStressTests(unittest.TestCase):
    def test_all_scenarios_have_104_weeks_and_causal_wma(self):
        for name, scenario in scenario_price_paths().items():
            with self.subTest(scenario=name):
                rows = build_scenario_rows(scenario["prices"])
                self.assertEqual(len(rows), 104)
                self.assertEqual(rows[0]["prior_200wma_aud"], 100_000.0)
                self.assertAlmostEqual(
                    rows[1]["prior_200wma_aud"],
                    (199 * 100_000.0 + scenario["prices"][0]) / 200,
                )
                self.assertEqual(rows[0]["signal_date"].weekday(), 6)
                self.assertEqual(rows[0]["execution_date"].weekday(), 0)

    def test_prolonged_bear_respects_all_cash_reserve_levels_and_weekly_cap(self):
        rows = build_scenario_rows(scenario_price_paths()["prolonged_bear_70pct"]["prices"])
        for floor in (30.0, 40.0, 50.0, 60.0):
            with self.subTest(floor=floor):
                result = simulate_weekly_cohort(
                    rows, policy="aggressive",
                    protected_cash_floor_pct_initial_cash=floor,
                )
                self.assertGreaterEqual(
                    result["cash_remaining_aud"], result["protected_cash_floor_aud"] - 1e-6
                )
                self.assertLessEqual(result["biggest_buy_pct_original_capital"], 5.0 + 1e-9)
                self.assertGreater(result["buy_count"], 0)

    def test_higher_reserve_never_increases_spend_in_same_bear_scenario(self):
        rows = build_scenario_rows(scenario_price_paths()["prolonged_bear_70pct"]["prices"])
        spends = [
            simulate_weekly_cohort(
                rows, policy="measured",
                protected_cash_floor_pct_initial_cash=floor,
            )["total_buy_spend_aud"]
            for floor in (0.0, 30.0, 40.0, 50.0, 60.0)
        ]
        self.assertEqual(spends, sorted(spends, reverse=True))


    def test_slower_measured_scale_preserves_cash_in_prolonged_bear(self):
        rows = build_scenario_rows(scenario_price_paths()["prolonged_bear_70pct"]["prices"])
        normal = simulate_weekly_cohort(
            rows, policy="measured", cash_yield=0.05,
            protected_cash_floor_pct_initial_cash=30.0,
            dynamic_allocation_scale=1.0,
        )
        slower = simulate_weekly_cohort(
            rows, policy="measured", cash_yield=0.05,
            protected_cash_floor_pct_initial_cash=30.0,
            dynamic_allocation_scale=0.5,
        )
        self.assertLess(slower["total_buy_spend_aud"], normal["total_buy_spend_aud"])
        self.assertGreater(slower["cash_remaining_aud"], normal["cash_remaining_aud"])
        self.assertGreaterEqual(
            slower["cash_remaining_aud"], slower["protected_cash_floor_aud"] - 1e-6
        )

    def test_false_bottom_does_not_break_guardrails(self):
        rows = build_scenario_rows(scenario_price_paths()["false_bottom_recovery"]["prices"])
        for policy in ("baseline", "measured", "stepped", "aggressive"):
            with self.subTest(policy=policy):
                result = simulate_weekly_cohort(rows, policy=policy)
                self.assertGreaterEqual(result["cash_remaining_aud"], -1e-6)
                self.assertLessEqual(result["biggest_buy_pct_original_capital"], 5.0 + 1e-9)

    def test_above_wma_rally_keeps_base_dca_active(self):
        rows = build_scenario_rows(scenario_price_paths()["extended_above_wma_rally"]["prices"])
        result = simulate_weekly_cohort(rows, policy="measured")
        self.assertEqual(result["buy_count"], 104)
        self.assertTrue(all(r["ratio_to_200wma"] >= 1.0 for r in rows))

    def test_scenario_paths_have_expected_endpoints(self):
        scenarios = scenario_price_paths()
        self.assertEqual(scenarios["prolonged_bear_70pct"]["prices"][-1], 30_000.0)
        self.assertEqual(scenarios["false_bottom_recovery"]["prices"][-1], 120_000.0)
        self.assertEqual(scenarios["rapid_v_recovery"]["prices"][-1], 130_000.0)


if __name__ == "__main__":
    unittest.main()
