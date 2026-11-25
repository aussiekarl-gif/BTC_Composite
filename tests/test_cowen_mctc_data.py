import unittest

import pandas as pd

from engines.cowen_risk_fetchers import BG_CANDIDATES, BG_SERIES, mctc_miner_ratio
from engines.cowen_risk_matrix_app import derive_series


class CowenMCTCDataTests(unittest.TestCase):
    def test_bgeometrics_usd_miner_reserve_endpoint_is_mapped(self):
        self.assertEqual(BG_SERIES.get("miner-reserve-usd"), "miner_cap_usd")
        self.assertIn("miner_reserve_usd", BG_CANDIDATES["miner-reserve-usd"])

    def test_ratio_is_usd_miner_cap_divided_by_usd_thermocap(self):
        dates = pd.date_range("2021-01-01", periods=3, freq="D")
        cap = pd.Series([100.0, 200.0, 300.0], index=dates)
        thermo = pd.Series([50.0, 100.0, 150.0], index=dates)
        result = mctc_miner_ratio(cap, thermo)
        self.assertEqual(result.tolist(), [2.0, 2.0, 2.0])

    def test_invalid_or_missing_thermocap_is_not_zero_filled(self):
        dates = pd.date_range("2021-01-01", periods=3, freq="D")
        cap = pd.Series([100.0, 200.0, 300.0], index=dates)
        thermo = pd.Series([50.0, 0.0, float("nan")], index=dates)
        result = mctc_miner_ratio(cap, thermo)
        self.assertEqual(result.tolist(), [2.0])
        self.assertEqual(result.index.tolist(), [dates[0]])

    def test_derive_series_uses_usd_units_for_mctc(self):
        dates = pd.date_range("2021-01-01", periods=2, freq="D")
        df = pd.DataFrame(
            {"miner_cap_usd": [100.0, 200.0], "thermo_cap": [50.0, 0.0]},
            index=dates,
        )
        series = derive_series(df)
        self.assertIn("mCTC", series)
        self.assertEqual(series["mCTC"].tolist(), [2.0])
        self.assertEqual(series["mCTC"].index.tolist(), [dates[0]])


if __name__ == "__main__":
    unittest.main()
