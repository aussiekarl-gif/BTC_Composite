import unittest
import pandas as pd
from engines.research.signal_delay_stress import signal_delay_sweep


class SignalDelayStressTests(unittest.TestCase):
    def setUp(self):
        self.data = pd.DataFrame({
            "btc_price_aud": [100, 90, 80, 100, 150, 180, 140, 100, 80, 90],
            "risk_score": [0.1, 0.1, 0.1, 0.4, 0.9, 0.95, 0.9, 0.4, 0.1, 0.1],
        }, index=pd.date_range("2020-01-01", periods=10, freq="W"))

    def test_delays_generate_finite_results(self):
        results = signal_delay_sweep(self.data, delays=(1, 2, 4), min_trade_aud=0)
        self.assertEqual(results["delay_observations"].tolist(), [1, 2, 4])
        self.assertTrue(results["ending_equity_aud"].gt(0).all())

    def test_future_signal_change_does_not_change_earlier_delay_results(self):
        first = self.data.copy()
        second = first.copy()
        second.iloc[-1, second.columns.get_loc("risk_score")] = 1.0
        a = signal_delay_sweep(first, delays=(1, 2), min_trade_aud=0)
        b = signal_delay_sweep(second, delays=(1, 2), min_trade_aud=0)
        pd.testing.assert_frame_equal(a, b)

    def test_reject_same_bar_execution(self):
        with self.assertRaises(ValueError):
            signal_delay_sweep(self.data, delays=(0,))


if __name__ == "__main__":
    unittest.main()
