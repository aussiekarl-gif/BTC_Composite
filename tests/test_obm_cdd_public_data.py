import json
import tempfile
import unittest
from pathlib import Path

import pandas as pd

from engines.research.obm_cdd_public_data import fetch_daily_cdd, save_snapshot


class FakeResponse:
    def __init__(self, text):
        self.text = text

    def raise_for_status(self):
        return None


class FakeSession:
    def __init__(self, text):
        self.text = text

    def get(self, url, timeout=60):
        return FakeResponse(self.text)


class OpenBitcoinMetricsCDDTests(unittest.TestCase):
    def test_fetch_preserves_valid_zero_cdd_and_daily_coverage(self):
        csv = (
            "date,series_id,value,unit,frequency,release_version\n"
            "2009-01-03,obm_cdd_btcxdays_daily,0,BTC-days,daily,OBM v0.1.0\n"
            "2009-01-04,obm_cdd_btcxdays_daily,1.5,BTC-days,daily,OBM v0.1.0\n"
        )
        frame = fetch_daily_cdd(session=FakeSession(csv))
        self.assertEqual(len(frame), 2)
        self.assertEqual(str(frame.index.tz), "UTC")
        self.assertEqual(frame["cdd_btc_days"].iloc[0], 0.0)
        self.assertEqual(frame["cdd_btc_days"].iloc[1], 1.5)
        self.assertEqual(frame.attrs["release_version"], "OBM v0.1.0")

    def test_fetch_rejects_gaps_and_wrong_units(self):
        gap_csv = (
            "date,series_id,value,unit,frequency,release_version\n"
            "2009-01-03,obm_cdd_btcxdays_daily,0,BTC-days,daily,OBM v0.1.0\n"
            "2009-01-05,obm_cdd_btcxdays_daily,1.5,BTC-days,daily,OBM v0.1.0\n"
        )
        with self.assertRaisesRegex(ValueError, "missing calendar"):
            fetch_daily_cdd(session=FakeSession(gap_csv))
        wrong_unit = gap_csv.replace("2009-01-05", "2009-01-04").replace("BTC-days,daily", "BTC,daily")
        with self.assertRaisesRegex(ValueError, "unit"):
            fetch_daily_cdd(session=FakeSession(wrong_unit))

    def test_snapshot_writes_cc_by_attribution_and_hash(self):
        csv = (
            "date,series_id,value,unit,frequency,release_version\n"
            "2009-01-03,obm_cdd_btcxdays_daily,0,BTC-days,daily,OBM v0.1.0\n"
        )
        frame = fetch_daily_cdd(session=FakeSession(csv))
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "cdd.csv"
            sidecar = save_snapshot(frame, path)
            meta = json.loads(sidecar.read_text())
            self.assertEqual(meta["license"], "CC BY 4.0")
            self.assertEqual(meta["unit"], "BTC-days")
            self.assertTrue(meta["sha256_csv"])


if __name__ == "__main__":
    unittest.main()
