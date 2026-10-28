"""Offline forward causal-quote SHA chain, actual-receipt and no-lookahead tests."""
import datetime as dt
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from engines.research import btc_post_signal_forward as m

UTC = dt.timezone.utc
T = dt.datetime(2026, 10, 25, 6, 0, tzinfo=UTC)
H = "a" * 64


def make_observation(offset_hours=0, *, hypothesis="PAPER_BULL", bid=99, ask=100):
    base = T + dt.timedelta(hours=offset_hours)
    slot = m.slot(base)
    return {
        "slot_utc": slot.isoformat(),
        "baseline_kraken_receipt_utc": (base + dt.timedelta(seconds=1)).isoformat(),
        "coinbase_receipt_utc": (base + dt.timedelta(seconds=2)).isoformat(),
        "post_kraken_request_started_utc": (base + dt.timedelta(seconds=2, microseconds=100)).isoformat(),
        "post_kraken_receipt_utc": (base + dt.timedelta(seconds=3)).isoformat(),
        "baseline_kraken_row_hash": "b"*64,
        "coinbase_row_hash": "c"*64,
        "frozen_policy_sha256": "d"*64,
        "frozen_hypothesis": hypothesis,
        "best_bid_usd": str(bid),
        "best_ask_usd": str(ask),
        "provider_payload_sha256": "e"*64,
    }


class PostQuoteForwardTests(unittest.TestCase):
    def test_chain_and_append_only_and_tamper(self):
        with tempfile.TemporaryDirectory() as work:
            p = Path(work)/"quotes.csv"
            m.append(p, make_observation())
            m.append(p, make_observation(6))
            rows = m.read_tape(p)
            self.assertEqual(len(rows), 2)
            self.assertEqual(rows[0]["previous_row_hash"], m.GENESIS)
            self.assertEqual(rows[1]["previous_row_hash"], rows[0]["row_hash"])
            with self.assertRaisesRegex(ValueError, "Duplicate or backdated"):
                m.append(p, make_observation(6))
            before = p.read_text()
            p.write_text(before.replace("99,", "999,", 1))
            with self.assertRaisesRegex(ValueError, "SHA-chain"):
                m.read_tape(p)

    def test_causal_sequence_checked_on_read(self):
        with tempfile.TemporaryDirectory() as work:
            p = Path(work)/"quotes.csv"
            row = make_observation()
            row["post_kraken_request_started_utc"] = row["baseline_kraken_receipt_utc"]
            with self.assertRaisesRegex(ValueError, "chronology"):
                m.append(p, row)

    def test_only_new_pair_allows_future_probe(self):
        with patch.object(m, "read_kraken", side_effect=AssertionError("Must not read")):
            r = m.collect(output=Path("/nonexistent/read-only-quote-tape.csv"),
                          status={"kraken_status":"EXISTING_SLOT",
                                  "coinbase_status":"NEW_SNAPSHOT"})
        self.assertFalse(r["appended"])
        self.assertEqual(r["status"], "SKIP_NO_TWO_NEW_ORIGINAL_SOURCE_RECEIPTS")

    def test_real_new_request_after_known_receipt(self):
        original_book = {
            "slot_utc": T.isoformat(),
            "captured_at_utc": (T+dt.timedelta(seconds=1)).isoformat(),
            "row_hash": "b"*64,
        }
        original_coinbase = {
            "slot_utc": T.isoformat(),
            "captured_at_utc": (T+dt.timedelta(seconds=2)).isoformat(),
            "row_hash": "c"*64,
        }
        clock_values = iter([T+dt.timedelta(seconds=2, microseconds=100),
                             T+dt.timedelta(seconds=3)]).__next__
        frozen = {"policy_sha256": "d"*64, "observations":[{
            "slot_utc": T.isoformat(), "kraken_source_hash": "b"*64,
            "coinbase_source_hash": "c"*64, "hypothesis": "PAPER_BULL"
        }]}
        fake_quote = {"best_bid_usd": "99.000000", "best_ask_usd": "100.000000",
                      "provider_payload_sha256": "e"*64}
        with tempfile.TemporaryDirectory() as work:
            p = Path(work)/"quotes.csv"
            with patch.object(m, "read_kraken", return_value=[original_book]), \
                 patch.object(m, "read_coinbase", return_value=[original_coinbase]), \
                 patch.object(m, "frozen_scorecard", return_value=frozen), \
                 patch.object(m, "summarize_book", return_value=fake_quote):
                r = m.collect(output=p,
                    status={"kraken_status":"NEW_SNAPSHOT", "coinbase_status":"NEW_SNAPSHOT"},
                    fetcher=lambda: {"real_network": False}, clock=clock_values)
            self.assertTrue(r["appended"])
            self.assertEqual(m.read_tape(p)[0]["frozen_hypothesis"], "PAPER_BULL")
            self.assertEqual(r["broker_orders"], 0)
            self.assertEqual(r["original_source_tape_writes"], 0)

    def test_same_whole_second_but_true_microsecond_order_is_causal(self):
        # The real Oct 25/26 tapes repeatedly rounded BOTH HTTP receipts
        # to the same second, making this strict gate reject fresh pairs.
        book_receipt = T + dt.timedelta(seconds=1, microseconds=100000)
        coinbase_receipt = T + dt.timedelta(seconds=1, microseconds=200000)
        request_start = T + dt.timedelta(seconds=1, microseconds=300000)
        quote_receipt = T + dt.timedelta(seconds=1, microseconds=400000)
        self.assertEqual(book_receipt.isoformat(timespec="seconds"),
                         coinbase_receipt.isoformat(timespec="seconds"))
        book = {"slot_utc": T.isoformat(),
                "captured_at_utc": book_receipt.isoformat(timespec="microseconds"),
                "row_hash": "b"*64}
        coinbase = {"slot_utc": T.isoformat(),
                    "captured_at_utc": coinbase_receipt.isoformat(timespec="microseconds"),
                    "row_hash": "c"*64}
        frozen = {"policy_sha256": "d"*64, "observations": [{
            "slot_utc": T.isoformat(), "kraken_source_hash": "b"*64,
            "coinbase_source_hash": "c"*64, "hypothesis": "PAPER_NEUTRAL"
        }]}
        quote = {"best_bid_usd": "99.000000", "best_ask_usd": "100.000000",
                 "provider_payload_sha256": "e"*64}
        with tempfile.TemporaryDirectory() as work:
            p = Path(work)/"quotes.csv"
            with patch.object(m, "read_kraken", return_value=[book]), \
                 patch.object(m, "read_coinbase", return_value=[coinbase]), \
                 patch.object(m, "frozen_scorecard", return_value=frozen), \
                 patch.object(m, "summarize_book", return_value=quote):
                r = m.collect(output=p,
                    status={"kraken_status": "NEW_SNAPSHOT",
                            "coinbase_status": "NEW_SNAPSHOT"},
                    fetcher=lambda: {"synthetic_offline_test": True},
                    clock=iter([request_start, quote_receipt]).__next__)
            self.assertTrue(r["appended"])
            self.assertEqual(r["frozen_hypothesis"], "PAPER_NEUTRAL")
            row = m.read_tape(p)[0]
            self.assertLess(m.instant(row["baseline_kraken_receipt_utc"]),
                            m.instant(row["coinbase_receipt_utc"]))
            self.assertLess(m.instant(row["coinbase_receipt_utc"]),
                            m.instant(row["post_kraken_request_started_utc"]))
            self.assertFalse(m.score([row], as_of=quote_receipt)[
                "after_cost_ASX_IBIT_AUD_outperformance_validated"])

    def test_equal_second_legacy_receipts_still_fail_closed_no_fake_quote(self):
        same = (T + dt.timedelta(seconds=1)).isoformat(timespec="seconds")
        book = {"slot_utc": T.isoformat(), "captured_at_utc": same}
        coinbase = {"slot_utc": T.isoformat(), "captured_at_utc": same}
        with patch.object(m, "read_kraken", return_value=[book]), \
             patch.object(m, "read_coinbase", return_value=[coinbase]):
            r = m.collect(output=Path("/nonexistent/legacy-quote-tape.csv"),
                status={"kraken_status": "NEW_SNAPSHOT",
                        "coinbase_status": "NEW_SNAPSHOT"},
                fetcher=lambda: self.fail("Never infer strict order from rounded receipts"),
                clock=lambda: T + dt.timedelta(seconds=1, microseconds=300000))
        self.assertFalse(r["appended"])
        self.assertEqual(r["status"], "SKIP_STALE_ORIGINAL_PAIR")

    def test_stale_pair_never_fetches(self):
        original_book = {"slot_utc": T.isoformat(),
            "captured_at_utc": (T+dt.timedelta(seconds=1)).isoformat()}
        original_coinbase = {"slot_utc": T.isoformat(),
            "captured_at_utc": (T+dt.timedelta(seconds=2)).isoformat()}
        with patch.object(m, "read_kraken", return_value=[original_book]), \
             patch.object(m, "read_coinbase", return_value=[original_coinbase]):
            r = m.collect(output=Path("/nonexistent/read-only-quote-tape.csv"),
                          status={"kraken_status":"NEW_SNAPSHOT",
                                  "coinbase_status":"NEW_SNAPSHOT"},
                          fetcher=lambda: self.fail("No fetch on stale pair"),
                          clock=lambda: T+dt.timedelta(minutes=7))
        self.assertFalse(r["appended"])

    def test_horizons_require_real_later_quote_and_apply_two_sided_costs(self):
        with tempfile.TemporaryDirectory() as work:
            p=Path(work)/"quotes.csv"
            m.append(p, make_observation(0, hypothesis="PAPER_BULL"))
            m.append(p, make_observation(6, hypothesis="PAPER_NEUTRAL",bid=104,ask=105))
            m.append(p, make_observation(24,hypothesis="PAPER_NEUTRAL",bid=108,ask=109))
            m.append(p, make_observation(168,hypothesis="PAPER_NEUTRAL",bid=112,ask=113))
            r=m.score(m.read_tape(p),as_of=T+dt.timedelta(hours=169))
            self.assertEqual(r["prospective_causal_quote_rows"],4)
            o=r["observations"][0]
            self.assertEqual(o["horizons"]["6"]["status"],
                             "OBSERVED_REST_QUOTES_NOT_EXECUTABLE")
            gains=o["horizons"]["6"]["hypothetical_spot_long_return_pct_by_fee_bps"]
            self.assertGreater(gains["5"],gains["10"])
            self.assertGreater(gains["10"],gains["25"])
            self.assertAlmostEqual(gains["10"],
                100*(104*.999/(100*1.001)-1),places=5)
            self.assertEqual(o["horizons"]["24"]["status"],
                             "OBSERVED_REST_QUOTES_NOT_EXECUTABLE")
            self.assertEqual(o["horizons"]["168"]["status"],
                             "OBSERVED_REST_QUOTES_NOT_EXECUTABLE")
            self.assertFalse(r["after_cost_ASX_IBIT_AUD_outperformance_validated"])

    def test_future_quote_never_leaks_into_prior_report(self):
        with tempfile.TemporaryDirectory() as work:
            p=Path(work)/"quotes.csv"
            m.append(p, make_observation(0))
            m.append(p, make_observation(6, bid=200, ask=201))
            m.append(p, make_observation(24, bid=300, ask=301))
            r=m.score(m.read_tape(p),as_of=T+dt.timedelta(hours=5))
            self.assertEqual(r["prospective_causal_quote_rows"], 1)
            self.assertEqual(r["observations"][0]["horizons"]["6"]["status"],
                             "NOT_YET_MATURED")
            later=m.score(m.read_tape(p),as_of=T+dt.timedelta(hours=7))
            self.assertEqual(later["prospective_causal_quote_rows"], 2)
            self.assertEqual(later["observations"][0]["horizons"]["24"]["status"],
                             "NOT_YET_MATURED")

    def test_bear_and_neutral_have_no_ibt_long_entries(self):
        with tempfile.TemporaryDirectory() as work:
            p=Path(work)/"quotes.csv"
            m.append(p, make_observation(0,hypothesis="PAPER_BEAR"))
            m.append(p, make_observation(6,hypothesis="PAPER_NEUTRAL"))
            r=m.score(m.read_tape(p),as_of=T+dt.timedelta(hours=7))
            self.assertIsNone(r["observations"][0]["horizons"]["6"]
                              ["hypothetical_spot_long_return_pct_by_fee_bps"])
            self.assertEqual(r["market_trade_recommendation"],"NONE")


    def test_source_provenance_must_link_to_original_immutable_tapes(self):
        original = make_observation()
        original["frozen_policy_sha256"] = m.frozen_policy_hash()
        b = {"slot_utc": original["slot_utc"],
             "row_hash": original["baseline_kraken_row_hash"],
             "captured_at_utc": original["baseline_kraken_receipt_utc"]}
        c = {"slot_utc": original["slot_utc"],
             "row_hash": original["coinbase_row_hash"],
             "captured_at_utc": original["coinbase_receipt_utc"]}
        self.assertEqual(m.verify_source_links([original], [b], [c]), 1)
        with self.assertRaisesRegex(ValueError, "provenance"):
            m.verify_source_links([original], [dict(b,row_hash="z"*64)], [c])
        with self.assertRaisesRegex(ValueError, "provenance"):
            m.verify_source_links([original], [b], [])
        old_policy = dict(original, frozen_policy_sha256="x"*64)
        with self.assertRaisesRegex(ValueError, "provenance"):
            m.verify_source_links([old_policy], [b], [c])

    def test_unexpired_future_quote_window_is_waiting_not_missing(self):
        with tempfile.TemporaryDirectory() as work:
            p=Path(work)/"quotes.csv"
            m.append(p, make_observation())
            r=m.score(m.read_tape(p), as_of=T+dt.timedelta(hours=6,minutes=20))
            self.assertEqual(r["observations"][0]["horizons"]["6"]["status"],
                             "AWAITING_POSSIBLE_LATER_QUOTE")
            after=m.score(m.read_tape(p),as_of=T+dt.timedelta(hours=9))
            self.assertEqual(after["observations"][0]["horizons"]["6"]["status"],
                             "NO_TIMELY_LATER_OBSERVED_QUOTE")



if __name__ == "__main__":
    unittest.main()
