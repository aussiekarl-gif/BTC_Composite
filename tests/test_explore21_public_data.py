import json
import tempfile
import unittest
from pathlib import Path

import pandas as pd

from engines.research.explore21_public_data import fetch_metric, save_metric


class FakeResponse:
    def __init__(self, text):
        self.text = text

    def raise_for_status(self):
        return None


class FakeSession:
    def __init__(self, text):
        self.text = text
        self.calls = []

    def get(self, url, timeout=60):
        self.calls.append((url, timeout))
        return FakeResponse(self.text)


class Explore21PublicDataTests(unittest.TestCase):
    def test_fetches_puell_csv_without_filling_missing_values(self):
        csv = (
            "date,puell_multiple,issuance_btc,issuance_usd,"
            "issuance_usd_365d_avg,btc_close_usd\n"
            "2026-01-01,0.8,450,40000000,50000000,90000\n"
            "2026-01-02,,450,41000000,50000000,91000\n"
        )
        session = FakeSession(csv)
        frame = fetch_metric("bitcoin-puell-multiple", session=session)
        self.assertEqual(len(session.calls), 1)
        self.assertEqual(frame.iloc[0]["puell_multiple"], 0.8)
        self.assertTrue(pd.isna(frame.iloc[1]["puell_multiple"]))
        self.assertEqual(frame.attrs["metric_id"], "bitcoin-puell-multiple")

    def test_rejects_unknown_metric(self):
        with self.assertRaises(ValueError):
            fetch_metric("bitcoin-terminal-price", session=FakeSession(""))

    def test_saves_attribution_method_version_and_hash(self):
        csv = (
            "date,mvrv_ratio,btc_close_usd\n"
            "2026-01-01,1.2,90000\n"
        )
        frame = fetch_metric(
            "bitcoin-mvrv-ratio", session=FakeSession(csv)
        )
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp) / "mvrv.csv"
            sidecar = save_metric(frame, output)
            metadata = json.loads(sidecar.read_text())
            self.assertEqual(metadata["method_version"], 2)
            self.assertEqual(metadata["license"], "CC BY 4.0")
            self.assertEqual(metadata["observations"], 1)
            self.assertTrue(metadata["sha256_csv"])
            self.assertIn("point-in-time vintages", metadata["historical_vintage_note"])


if __name__ == "__main__":
    unittest.main()
