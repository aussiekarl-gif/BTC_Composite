import unittest
import pandas as pd
from engines.research.strategy_selection_report import optimize_and_compare


class StrategySelectionReportTests(unittest.TestCase):
    def test_reports_out_of_sample_profit_against_benchmarks(self):
        prices = [100 + 20 * (i % 11) for i in range(80)]
        risks = [(i % 11) / 10 for i in range(80)]
        data = pd.DataFrame({"btc_price_aud": prices, "risk_score": risks},
                            index=pd.date_range("2020-01-01", periods=80, freq="W"))
        report = optimize_and_compare(
            data, splits=(.65,), buy_thresholds=(.25,),
            sell_thresholds=(.75,), max_buy_pct_periods=(.05,),
            max_sell_pct_periods=(.20,),
        )
        self.assertEqual(len(report), 1)
        row = report.iloc[0]
        self.assertAlmostEqual(row["cycle_minus_hold_aud"],
                               row["cycle_equity_aud"] - row["hold_equity_aud"])
        self.assertAlmostEqual(row["cycle_minus_dca_aud"],
                               row["cycle_equity_aud"] - row["fixed_dca_equity_aud"])

    def test_duplicate_dates_rejected(self):
        data = pd.DataFrame({"btc_price_aud": [100, 120],
                             "risk_score": [.1, .2]}, index=[0, 0])
        with self.assertRaisesRegex(ValueError, "Duplicate"):
            optimize_and_compare(data)


if __name__ == "__main__":
    unittest.main()
