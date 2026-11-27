import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock

from engines.research.aethereal_doh_fallback import (
    CSV_URL,
    HOST,
    download_csv,
    extract_ipv4_answer,
    resolve_aethereal_ipv4,
)


class FakeResponse:
    def __init__(self, payload):
        self.payload = payload

    def raise_for_status(self):
        return None

    def json(self):
        return self.payload


class AetherealDohFallbackTests(unittest.TestCase):
    def test_extracts_only_valid_ipv4_a_records(self):
        self.assertEqual(
            extract_ipv4_answer({
                "Status": 0,
                "Answer": [
                    {"type": 5, "data": "edge.example"},
                    {"type": 1, "data": "203.0.113.10"},
                ],
            }),
            "203.0.113.10",
        )
        self.assertIsNone(extract_ipv4_answer({"Status": 3, "Answer": []}))
        self.assertIsNone(extract_ipv4_answer({
            "Status": 0, "Answer": [{"type": 1, "data": "not-an-ip"}],
        }))

    def test_google_is_used_when_cloudflare_has_no_a_record(self):
        calls = []

        def fake_get(url, **kwargs):
            calls.append(url)
            if "cloudflare" in url:
                return FakeResponse({"Status": 0, "Answer": []})
            return FakeResponse({
                "Status": 0,
                "Answer": [{"type": 1, "data": "203.0.113.20"}],
            })

        resolver, address = resolve_aethereal_ipv4(get=fake_get)
        self.assertEqual(resolver, "Google")
        self.assertEqual(address, "203.0.113.20")
        self.assertEqual(len(calls), 2)

    def test_fails_explicitly_when_both_resolvers_have_no_a_record(self):
        fake_get = Mock(return_value=FakeResponse({"Status": 3, "Answer": []}))
        with self.assertRaisesRegex(RuntimeError, "Unable to resolve Aethereal"):
            resolve_aethereal_ipv4(get=fake_get)
        self.assertEqual(fake_get.call_count, 2)

    def test_download_pins_ip_but_keeps_verified_https_hostname(self):
        fake_get = Mock(return_value=FakeResponse({
            "Status": 0,
            "Answer": [{"type": 1, "data": "203.0.113.30"}],
        }))
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp) / "aethereal.csv"

            def fake_run(command, **kwargs):
                self.assertTrue(kwargs["check"])
                self.assertIn("--resolve", command)
                self.assertIn(f"{HOST}:443:203.0.113.30", command)
                self.assertIn(CSV_URL, command)
                self.assertNotIn("-k", command)
                self.assertNotIn("--insecure", command)
                output.write_text(
                    "date,price_usd,fees_btc,miners_revenue_usd,transactions\\n"
                    "2026-11-26,90000,2.5,100000,1000\\n",
                    encoding="utf-8",
                )

            result = download_csv(output, get=fake_get, run=fake_run)
            self.assertEqual(result["resolver"], "Cloudflare")
            self.assertTrue(output.is_file())
            self.assertGreater(output.stat().st_size, 0)


if __name__ == "__main__":
    unittest.main()
