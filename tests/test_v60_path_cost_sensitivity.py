import unittest

from engines.research.v60_200wma_backtest import _prior_week_momentum_nonnegative
from engines.research.v60_path_cost_sensitivity import (
    run_allocation_scale_sensitivity,
    run_execution_cost_sensitivity,
    run_momentum_confirmation_sensitivity,
    run_path_comparison,
)


class V60PathCostSensitivityTests(unittest.TestCase):
    def test_path_comparison_covers_delayed_bottom_severity_and_fast_recovery(self):
        rows = run_path_comparison()
        names = {row["scenario"] for row in rows}
        self.assertEqual(names, {
            "delayed_bottom_extra_30pct",
            "delayed_bottom_extra_40pct",
            "delayed_bottom_extra_50pct",
            "rapid_v_recovery",
        })
        self.assertTrue(all(row["research_only"] for row in rows))
        self.assertTrue(all(row["fixed_btc"] > 0 and row["dynamic_btc"] > 0 for row in rows))

    def test_allocation_scales_are_compared_on_each_path(self):
        rows = run_allocation_scale_sensitivity()
        self.assertEqual(len(rows), 12)
        self.assertEqual({row["dynamic_scale"] for row in rows}, {0.50, 0.75, 1.00})
        self.assertEqual({row["scenario"] for row in rows}, {
            "delayed_bottom_extra_30pct",
            "delayed_bottom_extra_40pct",
            "delayed_bottom_extra_50pct",
            "rapid_v_recovery",
        })
        self.assertTrue(all(row["research_only"] for row in rows))
        self.assertTrue(all(row["fixed_btc"] > 0 and row["dynamic_btc"] > 0 for row in rows))
    def test_momentum_gate_uses_only_two_completed_weeks_before_execution(self):
        rows = [
            {"btc_price_aud": 100.0},
            {"btc_price_aud": 90.0},
            {"btc_price_aud": 95.0},
            {"btc_price_aud": 1.0},
        ]
        # No signal until two completed weekly observations exist.
        self.assertFalse(_prior_week_momentum_nonnegative(rows, 0))
        self.assertFalse(_prior_week_momentum_nonnegative(rows, 1))
        # At execution index 2, the prior completed week was negative.
        self.assertFalse(_prior_week_momentum_nonnegative(rows, 2))
        # At index 3, the two completed prior weeks confirm non-negative momentum.
        self.assertTrue(_prior_week_momentum_nonnegative(rows, 3))
        # Altering the current execution price cannot change the decision.
        rows[3]["btc_price_aud"] = 10000.0
        self.assertTrue(_prior_week_momentum_nonnegative(rows, 3))
        # Altering the last completed week does change the next decision.
        rows[2]["btc_price_aud"] = 89.0
        self.assertFalse(_prior_week_momentum_nonnegative(rows, 3))

    def test_momentum_confirmation_covers_every_path_and_scale(self):
        rows = run_momentum_confirmation_sensitivity()
        self.assertEqual(len(rows), 24)
        self.assertEqual({row["dynamic_scale"] for row in rows}, {0.50, 0.75, 1.00})
        self.assertEqual({row["weekly_momentum_confirmation"] for row in rows}, {True, False})
        self.assertEqual({row["scenario"] for row in rows}, {
            "delayed_bottom_extra_30pct",
            "delayed_bottom_extra_40pct",
            "delayed_bottom_extra_50pct",
            "rapid_v_recovery",
        })
        self.assertTrue(all(row["research_only"] for row in rows))
        self.assertTrue(all(row["dynamic_btc"] > 0 for row in rows))
    def test_execution_cost_grid_is_complete_and_keeps_outputs_finite(self):
        rows = run_execution_cost_sensitivity()
        self.assertEqual(len(rows), 18)
        self.assertEqual({row["buy_friction_pct"] for row in rows}, {0.3, 0.6, 1.0})
        self.assertEqual({row["fixed_fee_aud"] for row in rows}, {3.0, 5.0})
        self.assertEqual({row["annual_btc_drag_pct"] for row in rows}, {0.25, 0.5, 1.0})
        self.assertTrue(all(row["dynamic_btc"] > 0 and row["fixed_btc"] > 0 for row in rows))
        self.assertTrue(all(row["research_only"] for row in rows))


if __name__ == "__main__":
    unittest.main()
