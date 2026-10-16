"""Deterministic regression: 25%-error SMSF scenarios."""
import unittest
from engines.research.price_error_sensitivity import compare

class PriceErrorSensitivityTests(unittest.TestCase):
    def test_25pct_scenarios(self):
        r=compare()
        expected={
            "conservative":(1453941.44,1154889.12),
            "middle":(2792670.12,989904.96),
            "strong":(5402232.60,1181136.60),
        }
        for name, (traded, held) in expected.items():
            with self.subTest(scenario=name):
                d=r["errors"]["25pct"][name]
                self.assertAlmostEqual(d["trading_terminal_value_aud"],traded,places=2)
                self.assertAlmostEqual(d["hold_terminal_value_aud"],held,places=2)
                self.assertAlmostEqual(d["total_brokerage_aud"],336)
                self.assertEqual(d["total_orders"],112)
                self.assertEqual(d["top_error"],.25)
                self.assertEqual(d["bottom_error"],.25)

    def test_better_errors_improve_each_scenario(self):
        r=compare()
        for name in ("conservative","middle","strong"):
            self.assertGreater(
                r["errors"]["25pct"][name]["trading_terminal_value_aud"],
                r["errors"]["40pct"][name]["trading_terminal_value_aud"])

if __name__ == "__main__": unittest.main()
