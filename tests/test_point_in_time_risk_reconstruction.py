"""Regression checks: Power Law fit must use observed dates, not future weekly labels."""
import unittest
from unittest.mock import patch

import numpy as np
import pandas as pd

from engines.research.run_point_in_time_risk_comparison import (
    GENESIS, causal_power_law,
)


class PointInTimePowerLawTests(unittest.TestCase):
    def test_partial_week_fit_uses_actual_friday_observation_not_future_monday(self):
        fridays = pd.date_range("2023-01-06", periods=53, freq="W-FRI", tz="UTC")
        sunday = fridays[-1] + pd.Timedelta(days=2)
        prices = pd.Series(
            np.linspace(10000.0, 30000.0, len(fridays) + 1),
            index=fridays.append(pd.DatetimeIndex([sunday])),
        )
        actual_polyfit = np.polyfit
        fits = []

        def capture(x, y, degree):
            fits.append(np.asarray(x).copy())
            return actual_polyfit(x, y, degree)

        with patch("engines.research.run_point_in_time_risk_comparison.np.polyfit", side_effect=capture):
            result = causal_power_law(prices)

        self.assertTrue(fits, "Expected a fit after 52 observed weeks")
        expected_last = np.log10((fridays[-1] - GENESIS).days)
        self.assertAlmostEqual(fits[-1][-1], expected_last, places=10)
        self.assertLess(fits[-1][-1], np.log10((sunday - GENESIS).days))
        self.assertTrue(np.isfinite(result.loc[sunday]))

    def test_future_prices_do_not_change_earlier_risk_score(self):
        dates = pd.date_range("2023-01-06", periods=60, freq="W-FRI", tz="UTC")
        prices = pd.Series(np.linspace(10000.0, 30000.0, len(dates)), index=dates)
        original = causal_power_law(prices)
        changed = prices.copy()
        changed.iloc[-1] *= 10
        revised = causal_power_law(changed)
        pd.testing.assert_series_equal(original.iloc[:-1], revised.iloc[:-1])


if __name__ == "__main__":
    unittest.main()
