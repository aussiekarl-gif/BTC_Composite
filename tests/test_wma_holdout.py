"""Guard against training/holdout leakage in the AUD WMA comparison."""
import unittest
import numpy as np
import pandas as pd
from engines.research.compare_wma_windows import chronological_holdout


class HoldoutTests(unittest.TestCase):
    def test_future_prices_cannot_change_training_selection(self):
        dates = pd.date_range("2020-01-06", periods=100, freq="W-MON")
        x = np.arange(100, dtype=float)
        price = 100 * (1.0 + 0.7 * np.sin(x / 9))
        frame = pd.DataFrame({"btc_price_aud": price,
                              "wma_200_aud": np.full(100, 100.0)},
                             index=dates)
        original = chronological_holdout(frame)
        changed = frame.copy()
        changed.iloc[70:, changed.columns.get_loc("btc_price_aud")] *= 3
        altered = chronological_holdout(changed)
        self.assertEqual(original["selected_parameters"],
                         altered["selected_parameters"])
        self.assertEqual(original["train_end"], altered["train_end"])
        self.assertEqual(original["test_start"], altered["test_start"])

    def test_usd_column_not_accepted(self):
        dates = pd.date_range("2020-01-06", periods=100, freq="W-MON")
        frame = pd.DataFrame({"btc_price_aud": [100.] * 100,
                              "wma_200_usd": [100.] * 100}, index=dates)
        with self.assertRaises(ValueError):
            chronological_holdout(frame)


if __name__ == "__main__":
    unittest.main()
