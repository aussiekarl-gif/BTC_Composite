import json
import tempfile
import unittest
from pathlib import Path

import pandas as pd

from engines.research.aethereal_public_data import (
    fetch_daily_btc_network,
    save_snapshot,
)


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


class AetherealPublicDataTests(unittest.TestCase):
    def test_fetch_preserves_daily_btc_fee_values_and_missingness(self):
        csv = (
            "date,price_usd,fees_btc,miners_revenue_usd,transactions\n"
            "2020-01-01,7000,1.25,100000,1000\n"
            "2020-01-02,7200,,110000,1200\n"
        )
        session = FakeSession(csv)
        frame = fetch_daily_btc_network(session=session)
        self.assertEqual(len(frame), 2)
        self.assertEqual(str(frame.index.tz), "UTC")
        self.assertAlmostEqual(frame["fees_btc"].iloc[0], 1.25)
        self.assertTrue(pd.isna(frame["fees_btc"].iloc[1]))
        self.assertEqual(len(session.calls), 1)

    def test_fetch_rejects_duplicate_utc_dates(self):
        csv = (
            "date,price_usd,fees_btc,miners_revenue_usd,transactions\n"
            "2020-01-01,7000,1.25,100000,1000\n"
            "2020-01-01,7100,1.30,110000,1100\n"
        )
        with self.assertRaisesRegex(ValueError, "duplicate"):
            fetch_daily_btc_network(session=FakeSession(csv))

    def test_snapshot_writes_attribution_and_fee_unit_metadata(self):
        csv = (
            "date,price_usd,fees_btc,miners_revenue_usd,transactions\n"
            "2020-01-01,7000,1.25,100000,1000\n"
        )
        frame = fetch_daily_btc_network(session=FakeSession(csv))
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "fees.csv"
            sidecar = save_snapshot(frame, path)
            metadata = json.loads(sidecar.read_text())
            self.assertEqual(metadata["provider"], "Aethereal Data")
            self.assertIn("research and education", metadata["license"])
            self.assertIn("BTC per UTC day", metadata["fee_unit"])
            self.assertEqual(metadata["observations"], 1)
            self.assertTrue(metadata["sha256_csv"])


if __name__ == "__main__":
    unittest.main()
