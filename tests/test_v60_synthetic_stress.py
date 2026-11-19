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

    def test_prolonged_bear_respects_cash_reserve_and_weekly_cap(self):
        rows = build_scenario_rows(scenario_price_paths()["prolonged_bear_70pct"]["prices"])
        result = simulate_weekly_cohort(
            rows, policy="aggressive", protected_cash_floor_pct_initial_cash=30.0,
        )
        self.assertGreaterEqual(
            result["cash_remaining_aud"], result["protected_cash_floor_aud"] - 1e-6
        )
        self.assertLessEqual(result["biggest_buy_pct_original_capital"], 5.0 + 1e-9)
        self.assertEqual(result["buy_count"], 104)

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
