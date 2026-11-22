import unittest

import pandas as pd

from engines.research.coinmetrics_community import (
    fetch_daily_btc_metrics,
    save_snapshot,
)


class FakeResponse:
    def __init__(self, payload):
        self.payload = payload

    def raise_for_status(self):
        return None

    def json(self):
        return self.payload


class FakeSession:
    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = []

    def get(self, url, params=None, timeout=60):
        self.calls.append((url, params, timeout))
        return FakeResponse(self.responses.pop(0))


class CoinMetricsCommunityTests(unittest.TestCase):
    def test_fetches_and_follows_pagination(self):
        session = FakeSession([
            {
                "data": [
                    {"asset": "btc", "time": "2020-01-01T00:00:00Z",
                     "CapMVRVCur": "1.2", "FeeTotUSD": "100"}
                ],
                "next_page_url": "https://community-api.coinmetrics.io/v4/next?page=2",
            },
            {
                "data": [
                    {"asset": "btc", "time": "2020-01-02T00:00:00Z",
                     "CapMVRVCur": "1.3", "FeeTotUSD": None}
                ]
            },
        ])
        frame = fetch_daily_btc_metrics(
            metrics=("CapMVRVCur", "FeeTotUSD"), session=session
        )
        self.assertEqual(len(session.calls), 2)
        self.assertEqual(frame.iloc[0]["CapMVRVCur"], 1.2)
        self.assertTrue(pd.isna(frame.iloc[1]["FeeTotUSD"]))
        self.assertEqual(frame.index[0], pd.Timestamp("2020-01-01", tz="UTC"))

    def test_rejects_untrusted_pagination_host(self):
        session = FakeSession([
            {"data": [], "next_page_url": "https://example.com/steal"}
        ])
        with self.assertRaises(ValueError):
            fetch_daily_btc_metrics(metrics=("FeeTotUSD",), session=session)

    def test_snapshot_writes_provenance_sidecar(self):
        import json
        import tempfile
        from pathlib import Path

        idx = pd.date_range("2020-01-01", periods=2, freq="D", tz="UTC")
        frame = pd.DataFrame({"FeeTotUSD": [1.0, None]}, index=idx)
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp) / "metrics.csv"
            sidecar = save_snapshot(frame, output, requested_metrics=("FeeTotUSD",))
            metadata = json.loads(sidecar.read_text())
            self.assertEqual(metadata["observations"], 2)
            self.assertEqual(metadata["missing_values_by_metric"]["FeeTotUSD"], 1)
            self.assertEqual(metadata["provider"], "Coin Metrics Community API")
            self.assertTrue(metadata["sha256_csv"])


if __name__ == "__main__":
    unittest.main()
