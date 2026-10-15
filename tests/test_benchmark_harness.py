import unittest

import pandas as pd

from engines.research.benchmark_harness import compare_lagged_cycle_to_benchmarks


class BenchmarkHarnessTests(unittest.TestCase):
    def data(self, prices, risks):
        return pd.DataFrame(
            {"btc_price_aud": prices, "risk_score": risks},
            index=pd.date_range("2020-01-06", periods=len(prices), freq="W-MON"),
        )

    def test_invalid_final_price_is_rejected(self):
        data = self.data([1, 2, float("nan")], [0.1, 0.2, 0.3])
        with self.assertRaisesRegex(ValueError, "Final observation"):
            compare_lagged_cycle_to_benchmarks(data)

    def test_duplicate_dates_are_rejected(self):
        data = self.data([1, 2, 3], [0.1, 0.2, 0.3])
        data.index = [data.index[0], data.index[0], data.index[2]]
        with self.assertRaisesRegex(ValueError, "Duplicate observation dates"):
            compare_lagged_cycle_to_benchmarks(data)

    def test_same_execution_date_and_fee(self):
        result = compare_lagged_cycle_to_benchmarks(
            self.data([1, 2, 4], [0.5, 0.5, 0.5]),
            starting_capital_aud=100, fee_pct=0.01,
        )
        hold = result["buy_and_hold_next_bar"]
        self.assertAlmostEqual(hold["btc_held"], 49.5)
        self.assertAlmostEqual(hold["ending_equity_aud"], 198)
        dca = result["fixed_dca_next_bar"]
        self.assertAlmostEqual(dca["btc_held"], 37.125)
        self.assertAlmostEqual(dca["ending_equity_aud"], 148.5)

    def test_dca_cash_and_holdings_conservation(self):
        result = compare_lagged_cycle_to_benchmarks(
            self.data([1, 2, 4, 8], [0.5] * 4),
            starting_capital_aud=90, fee_pct=0.0,
            fixed_dca_periods=2,
        )
        dca = result["fixed_dca_next_bar"]
        self.assertAlmostEqual(dca["cash_remaining_aud"], 0)
        self.assertAlmostEqual(dca["btc_held"], 45 / 2 + 45 / 4)
        self.assertAlmostEqual(dca["ending_equity_aud"], 270)


if __name__ == "__main__":
    unittest.main()
