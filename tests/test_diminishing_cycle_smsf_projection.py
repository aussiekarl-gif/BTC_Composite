import unittest

from engines.research.diminishing_cycle_smsf_projection import SCENARIOS, model


class DiminishingCycleSMSFProjectionTests(unittest.TestCase):
    def test_brokerage_exactly_three_aud_per_order(self):
        r = model(SCENARIOS["middle"], fee_per_order_aud=3,
                  orders_per_leg=16, cgt_rate=.10)
        self.assertEqual(r["total_orders"], 112)
        self.assertEqual(r["total_brokerage_aud"], 336)

    def test_zero_fee_zero_tax_two_cycle_closed_form(self):
        r = model({"bull_multiples": [5.0, 4.0],
                   "drawdowns": [.7, .6]}, capital_aud=1000,
                  fee_per_order_aud=0, orders_per_leg=16, cgt_rate=0)
        self.assertAlmostEqual(
            r["trading_vs_hold_pct"] / 100 + 1,
            (.6*5/(1.4*5*(1-.7))) * (.6*4/(1.4*4*(1-.6))),
            places=5,
        )

    def test_tax_reduces_value_when_realised_gain_occurs(self):
        s = SCENARIOS["strong"]
        taxed = model(s, cgt_rate=.10)
        untaxed = model(s, cgt_rate=0)
        self.assertGreater(taxed["total_realised_cgt_paid_aud"], 0)
        self.assertLess(taxed["trading_terminal_value_aud"],
                        untaxed["trading_terminal_value_aud"])

    def test_predeclared_scenarios_match_current_research_report(self):
        expected = {
            "conservative": (560147.23, 1154889.12),
            "middle": (1079610.83, 989904.96),
            "strong": (2064840.99, 1181136.69),
        }
        for name, (trade, hold) in expected.items():
            with self.subTest(name=name):
                out = model(SCENARIOS[name])
                self.assertAlmostEqual(out["trading_terminal_value_aud"], trade, delta=2)
                self.assertAlmostEqual(out["hold_terminal_value_aud"], hold, delta=2)

    def test_input_checks(self):
        with self.assertRaises(ValueError):
            model({"bull_multiples":[3], "drawdowns":[]})
        with self.assertRaises(ValueError):
            model(SCENARIOS["middle"], top_error=1)
        with self.assertRaises(ValueError):
            model(SCENARIOS["middle"], capital_aud=1, orders_per_leg=16)


if __name__ == "__main__":
    unittest.main()
