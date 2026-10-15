import unittest
from engines.research.cgt_scenarios import illustrative_after_tax_sale, illustrative_cgt_on_gain


class CGTScenarioTests(unittest.TestCase):
    def test_first_cycle_example(self):
        result = illustrative_after_tax_sale(43476882.50, 500000, 1068)
        self.assertAlmostEqual(result["illustrative_cgt_aud"], 9669798.5625, places=2)
        self.assertAlmostEqual(result["reinvestment_cash_aud"], 33807083.9375, places=2)

    def test_no_discount_for_short_holding(self):
        self.assertAlmostEqual(illustrative_cgt_on_gain(1000, 200), 450)
        self.assertAlmostEqual(illustrative_cgt_on_gain(1000, 400), 225)

    def test_losses_not_immediately_refunded(self):
        self.assertEqual(illustrative_cgt_on_gain(-1000, 400), 0)

    def test_fee_reduces_gain_and_cash(self):
        result = illustrative_after_tax_sale(2000, 1000, 400, fee_aud=100)
        self.assertAlmostEqual(result["illustrative_cgt_aud"], 202.5)
        self.assertAlmostEqual(result["reinvestment_cash_aud"], 1697.5)


if __name__ == "__main__":
    unittest.main()
