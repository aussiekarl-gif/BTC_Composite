"""Deterministic, network-free controls for the independent post-signal quote pilot."""
import datetime as dt
import unittest
from unittest.mock import patch

from engines.research import btc_post_signal_quote_probe as probe

UTC = dt.timezone.utc
START = dt.datetime(2026, 10, 25, 7, 17, 0, tzinfo=UTC)


def ticks(*seconds):
    return iter(START + dt.timedelta(seconds=value) for value in seconds).__next__


def book(raw, *, captured_at_utc):
    return {
        "best_bid_usd": "82000.000000",
        "best_ask_usd": "82000.100000",
        "provider_payload_sha256": raw["marker"],
    }


def trades(raw, *, captured_at_utc):
    return {
        "observed_trades": "100",
        "sample_duration_seconds": "15.000",
        "aggressor_buy_share_pct_sample": "50.0",
        "provider_payload_sha256": "coinbase-hash",
    }


class ReadOnlyCausalProbeTests(unittest.TestCase):
    def check(self, times=(0, 1, 1.2, 2, 2.2, 3), kraken=None, coinbase=None):
        seen = []
        def k():
            seen.append("kraken")
            return {"marker": "kraken-base" if len(seen) == 1 else "kraken-post"}
        def c():
            seen.append("coinbase")
            return {"marker": "coinbase"}
        with (patch.object(probe, "summarize_book", side_effect=book),
              patch.object(probe, "summarize_trades", side_effect=trades)):
            report = probe.collect_probe(
                kraken_fetcher=kraken or k,
                coinbase_fetcher=coinbase or c,
                clock=ticks(*times),
            )
        return report, seen

    def test_real_request_order_has_strict_causal_post_quote(self):
        r, seen = self.check()
        self.assertEqual(seen, ["kraken", "coinbase", "kraken"])
        self.assertTrue(r["eligible_quote"])
        self.assertEqual(r["status"], "CAUSAL_REST_QUOTE_OBSERVED_NOT_FILL")
        self.assertGreater(r["known_to_post_quote_seconds"], 0)
        self.assertNotEqual(r["original_baseline_quote"]["payload_sha256"],
                            r["separate_post_signal_rest_quote"]["payload_sha256"])
        self.assertEqual(r["recommendation"], "NONE")
        self.assertEqual(r["ntfy_messages"], 0)
        self.assertEqual(r["broker_orders"], 0)
        self.assertEqual(r["immutable_historical_source_tape_writes"], 0)

    def test_late_post_request_is_not_backfilled_as_entry(self):
        r, _ = self.check((0, 1, 2, 3, 305, 306))
        self.assertFalse(r["eligible_quote"])
        self.assertIn("POST_SIGNAL_QUOTE_OVER_FIVE_MINUTES", r["exclusion_reasons"])

    def test_baseline_and_coinbase_over_five_minutes_excluded(self):
        r, _ = self.check((0, 1, 301, 302, 303, 304))
        self.assertFalse(r["eligible_quote"])
        self.assertIn("BASELINE_TO_COINBASE_OVER_FIVE_MINUTES",
                      r["exclusion_reasons"])

    def test_quote_started_before_coinbase_finished_rejected(self):
        with self.assertRaisesRegex(ValueError, "causally"):
            self.check((0, 1, 2, 3, 2.9, 4))

    def test_coinbase_started_before_baseline_receipt_rejected(self):
        with self.assertRaisesRegex(ValueError, "Baseline/coinbase"):
            self.check((0, 1, 0.9, 2, 2.2, 3))

    def test_crossed_utc_slot_is_not_backfilled(self):
        r, _ = self.check((170, 171, 172, 173, 174, 175))
        self.assertTrue(r["eligible_quote"])
        midnight = dt.datetime(2026, 10, 25, 12, 0, 0, tzinfo=UTC)
        boundary = (midnight - START).total_seconds()
        r, _ = self.check((boundary-4, boundary-3, boundary-2,
                            boundary+1, boundary+2, boundary+3))
        self.assertFalse(r["eligible_quote"])
        self.assertIn("CROSSED_UTC_SIX_HOUR_SLOT", r["exclusion_reasons"])

    def test_missing_timezone_fails_closed(self):
        with self.assertRaisesRegex(ValueError, "UTC-aware"):
            probe._utc(dt.datetime(2026, 10, 25, 7, 0))

    def test_reverse_receipt_time_fails_closed(self):
        with self.assertRaisesRegex(ValueError, "HTTP receipt timing"):
            self.check((1, 0, 2, 3, 4, 5))

    def test_public_api_failure_cannot_be_passed_as_quote(self):
        def failed_kraken():
            raise ConnectionError("Kraken unavailable")
        with self.assertRaises(ConnectionError):
            self.check(kraken=failed_kraken)

    def test_unbounded_provider_request_cannot_pass(self):
        with self.assertRaisesRegex(ValueError, "HTTP receipt timing"):
            self.check((0, 121, 122, 123, 124, 125))


if __name__ == "__main__":
    unittest.main()
