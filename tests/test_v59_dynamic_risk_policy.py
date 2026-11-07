import unittest
from datetime import date, timedelta
from engines.research.v59_dynamic_risk_policy import (
    risk_buy_multiplier, risk_sell_fraction, replay_dynamic_dca
)


class DynamicRiskPolicyTests(unittest.TestCase):
    def setUp(self):
        self.day = date(2026, 11, 9)
        self.opts = dict(capital_aud=500000, reserve_aud=100000,
                         review_date=date(2027, 11, 9))

    def rows(self, risks):
        return [dict(date=self.day+timedelta(days=i*7),
                     btc_price_aud=100000, risk_score=r)
                for i, r in enumerate(risks)]

    def test_low_risk_buys_more(self):
        low = replay_dynamic_dca(self.rows([0.05]), **self.opts)
        high = replay_dynamic_dca(self.rows([0.55]), **self.opts)
        self.assertGreater(low["btc_held"], high["btc_held"])

    def test_expensive_market_pauses(self):
        x = replay_dynamic_dca(self.rows([0.51]), **self.opts)
        self.assertEqual(x["btc_held"], 0)
        self.assertEqual(x["cash_aud"], 500000)

    def test_exact_050_buys_but_above_050_pauses(self):
        at = replay_dynamic_dca(self.rows([0.50]), **self.opts)
        above = replay_dynamic_dca(self.rows([0.50001]), **self.opts)
        self.assertGreater(at["btc_held"], 0)
        self.assertEqual(above["btc_held"], 0)

    def test_weekly_ceiling_prevents_low_risk_overspend(self):
        x = replay_dynamic_dca(self.rows([0.01]), **self.opts)
        self.assertAlmostEqual(x["orders"][0]["buy_aud"], 25000.0)

    def test_ceiling_is_configurable(self):
        x = replay_dynamic_dca(self.rows([0.01]), max_weekly_fraction=0.02, **self.opts)
        self.assertAlmostEqual(x["orders"][0]["buy_aud"], 10000.0)

    def test_invalid_ceiling_rejected(self):
        with self.assertRaises(ValueError):
            replay_dynamic_dca(self.rows([0.01]), max_weekly_fraction=0, **self.opts)

    def test_reserve_protected(self):
        x = replay_dynamic_dca(self.rows([0.01]*60), **self.opts)
        self.assertGreaterEqual(x["cash_aud"], 100000)

    def test_selling_disabled_by_default(self):
        x = replay_dynamic_dca(self.rows([0.01, 0.95, 0.95]), **self.opts)
        self.assertEqual(sum(o["sell_btc"] for o in x["orders"]), 0)

    def test_staged_selling_requires_confirmation(self):
        x = replay_dynamic_dca(self.rows([0.01, 0.95, 0.95]), enable_selling=True, **self.opts)
        self.assertEqual(x["orders"][1]["sell_btc"], 0)
        self.assertGreater(x["orders"][2]["sell_btc"], 0)

    def test_invalid_risk_rejected(self):
        with self.assertRaises(ValueError):
            risk_buy_multiplier(float("nan"))

    def test_monotonic_buy_bands(self):
        self.assertGreater(risk_buy_multiplier(0.05), risk_buy_multiplier(0.3))
        self.assertGreater(risk_buy_multiplier(0.3), risk_buy_multiplier(0.7))

    def test_sell_fraction_rises_with_risk(self):
        self.assertLess(risk_sell_fraction(0.85), risk_sell_fraction(0.95))


if __name__ == "__main__":
    unittest.main()
