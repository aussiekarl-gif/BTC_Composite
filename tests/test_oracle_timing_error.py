import unittest
from engines.research.oracle_timing_error import oracle_turning_point_error_table


class OracleTimingErrorTests(unittest.TestCase):
    def test_chronological_buy_before_sell_and_monotone_error(self):
        result = oracle_turning_point_error_table([100, 70, 80, 200, 180])
        self.assertTrue((result["buy_index"] < result["sell_index"]).all())
        self.assertEqual(result["error_fraction"].tolist(), [0.0, .15, .30])
        self.assertTrue(result["ending_cash_aud"].is_monotonic_decreasing)
        self.assertTrue(result["hindsight_oracle"].all())

    def test_buy_fee_and_sell_fee_applied(self):
        result = oracle_turning_point_error_table(
            [100, 50, 200], error_fractions=(0,), capital_aud=1000, fee_pct=.01
        )
        self.assertAlmostEqual(result.iloc[0]["ending_cash_aud"], 1000 * .99 * 4 * .99)

    def test_reject_bad_prices(self):
        with self.assertRaises(ValueError):
            oracle_turning_point_error_table([100, float("nan"), 200])


if __name__ == "__main__":
    unittest.main()
