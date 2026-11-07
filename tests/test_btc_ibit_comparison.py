import unittest
import pandas as pd
from engines.shared.btc_ibit_comparison import build_indexed_comparison, parse_daily_closes


class TestComparison(unittest.TestCase):
    def test_indexed_common_dates(self):
        btc = pd.Series([100., 110., 120.], index=pd.to_datetime(["2026-11-02", "2026-11-03", "2026-11-04"]).date)
        ibit = pd.Series([20., 22., 21.], index=pd.to_datetime(["2026-11-02", "2026-11-03", "2026-11-04"]).date)
        actual, indexed = build_indexed_comparison(btc, ibit)
        self.assertEqual(len(actual), 3)
        self.assertAlmostEqual(indexed.iloc[0]["BTC/AUD"], 100)
        self.assertAlmostEqual(indexed.iloc[-1]["BTC/AUD"], 120)
        self.assertAlmostEqual(indexed.iloc[-1]["ASX:IBIT"], 105)

    def test_reject_wrong_currency(self):
        payload = {"chart": {"result": [{"meta": {"symbol": "IBIT.AX", "currency": "USD"},
            "timestamp": [1793577600], "indicators": {"quote": [{"close": [20.81]}]}}]}}
        with self.assertRaises(ValueError):
            parse_daily_closes(payload, "IBIT.AX", "AUD")


if __name__ == "__main__":
    unittest.main()
