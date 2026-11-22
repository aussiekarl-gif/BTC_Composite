import unittest

import numpy as np
import pandas as pd

from engines.research.cowen_onchain_risk import (
    ACTIVE_METRICS,
    build_seven_metric_composite,
    calculate_terminal_price,
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


    def test_existing_raw_candidates_preserve_missing_and_provenance_labels(self):
        import tempfile
        from pathlib import Path
        from engines.research.cowen_onchain_risk import build_existing_raw_candidates

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            dates = pd.date_range("2020-01-01", periods=366, freq="D", tz="UTC")
            ts = (dates.view("int64") // 10**6).astype("int64")
            pd.DataFrame({
                "timestamp": ts,
                "Miner Revenue: Total (Daily)": np.arange(1, 367, dtype=float),
            }).to_csv(root / "miner_revenue_total_daily__2026-10-07T21-26-46.csv", index=False)
            pd.DataFrame({
                "timestamp": ts,
                "Price": np.full(366, 20.0),
                "Realized Price": np.full(366, 10.0),
            }).to_csv(root / "planb_realized_prices_2026-10-07T21-19-48.csv", index=False)
            pd.DataFrame({
                "timestamp": ts,
                "MVRV Z-Score": np.linspace(-1, 2, 366),
            }).to_csv(root / "mvrv_z_score_2026-10-06T21-46-14.csv", index=False)

            candidates = build_existing_raw_candidates(root)
            self.assertTrue(np.isnan(candidates["puell_multiple_candidate"].iloc[363]))
            self.assertTrue(np.isfinite(candidates["puell_multiple_candidate"].iloc[364]))
            self.assertTrue(np.isfinite(candidates["puell_multiple_candidate"].iloc[365]))
            self.assertAlmostEqual(candidates["mvrv_planb_realized_price_proxy"].iloc[-1], 2.0)
            self.assertAlmostEqual(candidates["mvrv_z_score_provider_export"].iloc[-1], 2.0)
            self.assertTrue(candidates.index.is_monotonic_increasing)


    def test_terminal_price_matches_cumulative_vdd_formula(self):
        idx = pd.date_range("2020-01-01", periods=3, freq="D", tz="UTC")
        inputs = pd.DataFrame({
            "cdd_btc_days": [1.0, 2.0, 3.0],
            "price_usd": [10.0, 20.0, 30.0],
            "supply_btc": [10.0, 10.0, 10.0],
        }, index=idx)
        result = calculate_terminal_price(inputs)
        self.assertEqual(result["market_age_days"].tolist(), [1, 2, 3])
        self.assertAlmostEqual(result.iloc[-1]["cumulative_value_days_destroyed_usd"], 140.0)
        self.assertAlmostEqual(result.iloc[-1]["transferred_price_usd"], 140.0 / 30.0)
        self.assertAlmostEqual(result.iloc[-1]["terminal_price_usd"], 21.0 * 140.0 / 30.0)
        self.assertAlmostEqual(result.iloc[-1]["price_to_terminal_price"], 30.0 / (21.0 * 140.0 / 30.0))

    def test_terminal_price_rejects_missing_or_gapped_daily_inputs(self):
        idx = pd.date_range("2020-01-01", periods=3, freq="D", tz="UTC")
        inputs = pd.DataFrame({
            "cdd_btc_days": [1.0, 2.0, 3.0],
            "price_usd": [10.0, 20.0, 30.0],
            "supply_btc": [10.0, 10.0, 10.0],
        }, index=idx)
        missing = inputs.copy()
        missing.loc[idx[1], "cdd_btc_days"] = np.nan
        with self.assertRaises(ValueError):
            calculate_terminal_price(missing)
        gapped = inputs.iloc[[0, 2]]
        with self.assertRaises(ValueError):
            calculate_terminal_price(gapped)


if __name__ == "__main__":
    unittest.main()
