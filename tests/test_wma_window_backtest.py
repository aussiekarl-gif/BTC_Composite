"""Synthetic regression checks for the staggered research-only WMA model."""
import unittest

import numpy as np
import pandas as pd

from engines.research.wma_window_backtest import (
    prepare_weekly_wma, simulate_wma_windows,
)


class WMAWindowTests(unittest.TestCase):
    def setUp(self):
        self.frame = pd.DataFrame({
            "btc_price_aud": [120, 110, 99, 95, 90, 100, 210, 220, 230] +
                             [230] * 20,
            "wma_200": [100] * 29,
        }, index=pd.date_range("2025-01-06", periods=29, freq="W-MON"))

    def test_lagged_entry(self):
        out, _ = simulate_wma_windows(self.frame, weeks=12)
        self.assertEqual(out.iloc[2]["action"], "HOLD")
        self.assertEqual(out.iloc[3]["action"], "BUY")
        self.assertEqual(out.iloc[7]["action"], "SELL")

    def test_window_length_and_accounting(self):
        for weeks in (12, 16):
            only_buys = self.frame.iloc[:6].copy()
            extra = pd.DataFrame(
                {"btc_price_aud": [90] * 20, "wma_200": [100] * 20},
                index=pd.date_range(only_buys.index[-1] + pd.Timedelta(weeks=1),
                                    periods=20, freq="W-MON"))
            d = pd.concat([only_buys, extra])
            out, summary = simulate_wma_windows(d, weeks=weeks, fee_pct=0.001)
            self.assertEqual(int((out.action == "BUY").sum()), weeks)
            self.assertAlmostEqual(float(out.fee_aud.sum()), summary["fees_aud"])
            np.testing.assert_allclose(
                out.equity_aud,
                out.cash_aud + out.btc_held * out.price,
                rtol=1e-12, atol=1e-7,
            )
            self.assertTrue((out.cash_aud >= -1e-7).all())
            self.assertTrue((out.btc_held >= -1e-12).all())

    def test_no_future_data_dependence(self):
        whole, _ = simulate_wma_windows(self.frame, weeks=16)
        for length in range(2, len(self.frame)):
            prefix, _ = simulate_wma_windows(self.frame.iloc[:length], weeks=16)
            self.assertEqual(
                whole.action.iloc[:length].tolist(), prefix.action.tolist()
            )
            np.testing.assert_allclose(
                whole.equity_aud.iloc[:length], prefix.equity_aud,
                rtol=1e-12, atol=1e-8
            )

    def test_prior_week_ma(self):
        weekly = pd.Series(
            np.arange(1.0, 203.0),
            index=pd.date_range("2020-01-06", periods=202, freq="W-MON")
        )
        result = prepare_weekly_wma(weekly)
        self.assertAlmostEqual(result.iloc[0].wma_200, 100.5)
        self.assertAlmostEqual(result.iloc[0].btc_price_aud, 201.0)


if __name__ == "__main__":
    unittest.main()
