import unittest
from engines.shared.ibit_dca_display import estimate_ibit_units


class TestIbitDcaDisplay(unittest.TestCase):
    def test_whole_units(self):
        self.assertEqual(estimate_ibit_units(24933, 22.41), 1112)
        self.assertEqual(estimate_ibit_units(24933, 22.41, brokerage_aud=3), 1112)

    def test_zero_and_small_budget(self):
        self.assertEqual(estimate_ibit_units(0, 22.41), 0)
        self.assertEqual(estimate_ibit_units(10, 22.41), 0)

    def test_invalid_quote_fails_closed(self):
        for price in (0, -1, float("nan"), None):
            self.assertIsNone(estimate_ibit_units(1000, price))
        self.assertIsNone(estimate_ibit_units(-100, 22))
        self.assertIsNone(estimate_ibit_units(1000, 22, brokerage_aud=-3))


if __name__ == "__main__":
    unittest.main()
