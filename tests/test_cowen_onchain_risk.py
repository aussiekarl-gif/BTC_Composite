import unittest

import numpy as np
import pandas as pd

from engines.research.cowen_onchain_risk import (
    ACTIVE_METRICS,
    build_seven_metric_composite,
    prior_only_percentile_risk,
)


class CowenOnchainRiskTests(unittest.TestCase):
    def test_percentile_uses_only_prior_observations(self):
        idx = pd.date_range("2020-01-01", periods=6, freq="D", tz="UTC")
        values = pd.Series([1, 2, 3, 4, 5, 100], index=idx)
        result = prior_only_percentile_risk(
            values, window_observations=5, min_prior_observations=5
        )
        self.assertTrue(np.isnan(result.iloc[4]))
        self.assertEqual(result.iloc[5], 1.0)

    def test_lower_is_riskier_inverts_percentile(self):
        idx = pd.date_range("2020-01-01", periods=4, freq="D", tz="UTC")
        values = pd.Series([1, 2, 3, 0], index=idx)
        high = prior_only_percentile_risk(
            values, window_observations=3, min_prior_observations=3
        )
        low = prior_only_percentile_risk(
            values, window_observations=3, min_prior_observations=3,
            higher_is_riskier=False,
        )
        self.assertEqual(high.iloc[-1], 0.0)
        self.assertEqual(low.iloc[-1], 1.0)

    def test_six_of_seven_never_becomes_composite(self):
        idx = pd.date_range("2020-01-01", periods=2, freq="D", tz="UTC")
        frame = pd.DataFrame(0.5, index=idx, columns=ACTIVE_METRICS)
        frame.loc[idx[-1], "mctc_miner"] = np.nan
        result = build_seven_metric_composite(frame)
        self.assertTrue(np.isnan(result.loc[idx[-1], "composite_risk"]))
        self.assertEqual(result.loc[idx[-1], "available_component_count"], 6)
        self.assertEqual(result.loc[idx[-1], "status"], "INCOMPLETE — NOT INVESTABLE")
        self.assertEqual(result.loc[idx[-1], "partial_mean_diagnostic_only"], 0.5)

    def test_seven_of_seven_returns_equal_weight_mean(self):
        idx = pd.date_range("2020-01-01", periods=1, freq="D", tz="UTC")
        frame = pd.DataFrame([[0, .1, .2, .3, .4, .5, .6]], index=idx,
                             columns=ACTIVE_METRICS)
        result = build_seven_metric_composite(frame)
        self.assertAlmostEqual(result.iloc[0]["composite_risk"], .3)
        self.assertEqual(result.iloc[0]["status"], "COMPLETE — RESEARCH ONLY")

    def test_rejects_unsorted_or_duplicate_dates(self):
        idx = pd.to_datetime(["2020-01-02", "2020-01-01"], utc=True)
        values = pd.Series([1, 2], index=idx)
        with self.assertRaises(ValueError):
            prior_only_percentile_risk(
                values, window_observations=2, min_prior_observations=2
            )


if __name__ == "__main__":
    unittest.main()
