import unittest

from engines.research.v60_200wma_backtest import simulate_weekly_cohort
from engines.research.v60_synthetic_stress import build_scenario_rows, scenario_price_paths


class V60DeploymentCapTests(unittest.TestCase):
    def test_deployment_cap_never_exceeds_initial_cash_percentage(self):
        rows = build_scenario_rows(scenario_price_paths()["prolonged_bear_70pct"]["prices"])
        for cap in (40.0, 50.0, 60.0, 70.0):
            with self.subTest(cap=cap):
                result = simulate_weekly_cohort(
                    rows, policy="measured",
                    max_cumulative_buy_spend_pct_initial_cash=cap,
                )
                initial_cash = 510_000.0 * 0.59
                self.assertLessEqual(result["total_buy_spend_aud"], initial_cash*cap/100 + 1e-6)

    def test_cap_is_not_exceeded_when_reserve_is_also_enabled(self):
        rows = build_scenario_rows(scenario_price_paths()["prolonged_bear_70pct"]["prices"])
        result = simulate_weekly_cohort(
            rows, policy="measured",
            protected_cash_floor_pct_initial_cash=30.0,
            max_cumulative_buy_spend_pct_initial_cash=50.0,
        )
        self.assertLessEqual(result["total_buy_spend_aud"], 150_450.0 + 1e-6)
        self.assertGreaterEqual(result["cash_remaining_aud"], result["protected_cash_floor_aud"] - 1e-6)

    def test_cumulative_cap_stops_later_buys_once_exhausted(self):
        rows = build_scenario_rows(scenario_price_paths()["prolonged_bear_70pct"]["prices"])
        result = simulate_weekly_cohort(
            rows, policy="aggressive",
            max_cumulative_buy_spend_pct_initial_cash=40.0,
        )
        self.assertLess(result["buy_count"], 104)
        self.assertLessEqual(result["total_buy_spend_aud"], 120_360.0 + 1e-6)


if __name__ == "__main__":
    unittest.main()
