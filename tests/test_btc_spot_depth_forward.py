"""Offline validation for research Kraken order-book observations."""
import csv
import datetime as dt
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from engines.research.btc_spot_depth_forward import (
    COLUMNS, GENESIS, append_snapshot,
    read_verified_tape, run_once, summarize_book, _signature,
)

UTC = dt.timezone.utc
NOW = dt.datetime(2026, 10, 19, 1, 20, tzinfo=UTC)


def sample_book(now=NOW, bid_units=1, ask_units=3):
    stamp = int(now.timestamp()) - 4
    return {"error": [], "result": {"XXBTZUSD": {
        "bids": [["79999.00", str(bid_units), stamp],
                 ["79950.00", str(bid_units), stamp],
                 ["79790.00", "2", stamp],
                 ["79500.00", "2", stamp]],
        "asks": [["80001.00", str(ask_units), stamp],
                 ["80050.00", str(ask_units), stamp],
                 ["80210.00", "2", stamp],
                 ["80500.00", "2", stamp]],
    }}}


class KrakenDepthTests(unittest.TestCase):
    def test_valid_book_observation_only_with_coverage(self):
        r = summarize_book(sample_book(), captured_at_utc=NOW)
        self.assertEqual(r["market"], "XBT/USD")
        self.assertEqual(r["complete_25bps_band"], "True")
        self.assertEqual(r["research_signal"], "OBSERVATION_ONLY_NO_TRADE")
        self.assertAlmostEqual(float(r["mid_usd"]), 80000.0)
        self.assertAlmostEqual(float(r["spread_bps"]), 0.25)
        self.assertLess(float(r["bid_depth_share_pct_25bps"]), 50.0)
        self.assertEqual(r["slot_utc"], "2026-10-19T00:00:00+00:00")

    def test_subsecond_receipt_and_legacy_seconds_append_only(self):
        precise = NOW.replace(microsecond=123456)
        observation = summarize_book(sample_book(), captured_at_utc=precise)
        self.assertEqual(observation["captured_at_utc"],
                         precise.isoformat(timespec="microseconds"))
        with TemporaryDirectory() as folder:
            file = Path(folder)/"tape.csv"
            old = summarize_book(sample_book(), captured_at_utc=NOW)
            old["captured_at_utc"] = NOW.isoformat(timespec="seconds")
            self.assertTrue(append_snapshot(file, old))
            old_hash = read_verified_tape(file)[0]["row_hash"]
            later = NOW + dt.timedelta(hours=6, microseconds=123456)
            self.assertTrue(append_snapshot(
                file, summarize_book(sample_book(later), captured_at_utc=later)))
            rows = read_verified_tape(file)
            self.assertEqual(len(rows), 2)
            self.assertEqual(rows[0]["captured_at_utc"], NOW.isoformat(timespec="seconds"))
            self.assertEqual(rows[0]["row_hash"], old_hash)
            self.assertEqual(rows[1]["captured_at_utc"],
                             later.isoformat(timespec="microseconds"))
            self.assertEqual(rows[1]["previous_row_hash"], old_hash)

    def test_stale_top_quote_rejected(self):
        p=sample_book()
        p["result"]["XXBTZUSD"]["bids"][0][2]=NOW.timestamp()-3600
        with self.assertRaisesRegex(ValueError,"Stale"):
            summarize_book(p,captured_at_utc=NOW)

    def test_partial_depth_share_unknown(self):
        p = sample_book()
        p["result"]["XXBTZUSD"]["bids"] = p["result"]["XXBTZUSD"]["bids"][:2]
        r = summarize_book(p, captured_at_utc=NOW)
        self.assertEqual(r["complete_25bps_band"], "False")
        self.assertEqual(r["bid_depth_share_pct_25bps"], "")

    def test_wrong_market_rejected(self):
        p = sample_book()
        p["result"]["XETHZUSD"] = p["result"].pop("XXBTZUSD")
        with self.assertRaisesRegex(ValueError, "non-XBT"):
            summarize_book(p, captured_at_utc=NOW)

    def test_provider_error_rejected(self):
        p = sample_book()
        p["error"] = ["EAPI:General"]
        with self.assertRaises(ValueError):
            summarize_book(p, captured_at_utc=NOW)

    def test_crossed_book_rejected(self):
        p = sample_book()
        p["result"]["XXBTZUSD"]["bids"][0][0] = "80002.00"
        with self.assertRaisesRegex(ValueError, "Crossed"):
            summarize_book(p, captured_at_utc=NOW)

    def test_unsorted_levels_rejected(self):
        p = sample_book()
        p["result"]["XXBTZUSD"]["asks"][1][0] = "80000.00"
        with self.assertRaises(ValueError):
            summarize_book(p, captured_at_utc=NOW)

    def test_negative_volume_rejected(self):
        p = sample_book()
        p["result"]["XXBTZUSD"]["bids"][0][1] = "-5"
        with self.assertRaises(ValueError):
            summarize_book(p, captured_at_utc=NOW)

    def test_future_level_timestamp_rejected(self):
        p = sample_book()
        p["result"]["XXBTZUSD"]["asks"][0][2] = NOW.timestamp() + 100
        with self.assertRaisesRegex(ValueError, "Future"):
            summarize_book(p, captured_at_utc=NOW)

    def test_old_resting_level_is_not_stale_capture(self):
        p = sample_book()
        p["result"]["XXBTZUSD"]["bids"][3][2] = NOW.timestamp() - 30*86400
        self.assertEqual(summarize_book(p, captured_at_utc=NOW)["complete_25bps_band"],
                         "True")

    def test_nan_invalid(self):
        p = sample_book()
        p["result"]["XXBTZUSD"]["bids"][0][0] = "nan"
        with self.assertRaises(ValueError):
            summarize_book(p, captured_at_utc=NOW)

    def test_timestamp_must_be_aware(self):
        with self.assertRaises(ValueError):
            summarize_book(sample_book(),captured_at_utc=NOW.replace(tzinfo=None))

    def test_append_idempotence_and_tamper_block(self):
        with TemporaryDirectory() as tmp:
            file = Path(tmp) / "depth.csv"
            first = summarize_book(sample_book(), captured_at_utc=NOW)
            self.assertTrue(append_snapshot(file, first))
            self.assertFalse(append_snapshot(file, first))
            rows = read_verified_tape(file)
            self.assertEqual(len(rows), 1)
            self.assertEqual(rows[0]["previous_row_hash"], GENESIS)
            self.assertEqual(rows[0]["row_hash"], _signature(rows[0]))
            text = file.read_text().replace("80000.000000", "90000.000000")
            file.write_text(text)
            with self.assertRaisesRegex(ValueError, "hash-chain"):
                read_verified_tape(file)

    def test_append_new_slot_no_older_backfill(self):
        with TemporaryDirectory() as tmp:
            file = Path(tmp)/"depth.csv"
            first = summarize_book(sample_book(), captured_at_utc=NOW)
            later = NOW + dt.timedelta(hours=6)
            second = summarize_book(sample_book(later), captured_at_utc=later)
            self.assertTrue(append_snapshot(file, first))
            self.assertTrue(append_snapshot(file, second))
            self.assertEqual(len(read_verified_tape(file)), 2)
            with self.assertRaisesRegex(ValueError, "backfill"):
                append_snapshot(file, first)

    def test_run_once_is_network_free_when_slot_present(self):
        with TemporaryDirectory() as tmp:
            file = Path(tmp)/"depth.csv"
            append_snapshot(file, summarize_book(sample_book(), captured_at_utc=NOW))
            def cannot_fetch():
                raise AssertionError("Duplicate slot should skip public fetch")
            self.assertFalse(run_once(path=file, fetcher=cannot_fetch, clock=lambda: NOW))

    def test_mock_end_to_end_capture(self):
        with TemporaryDirectory() as tmp:
            file = Path(tmp)/"depth.csv"
            captures = iter([NOW, NOW + dt.timedelta(seconds=2)])
            self.assertTrue(run_once(path=file,fetcher=lambda: sample_book(),
                                     clock=lambda: next(captures)))
            self.assertEqual(len(read_verified_tape(file)),1)
            self.assertEqual(read_verified_tape(file)[0]["research_signal"],
                             "OBSERVATION_ONLY_NO_TRADE")

    def test_crossing_slot_blocks_write(self):
        with TemporaryDirectory() as tmp:
            file = Path(tmp)/"depth.csv"
            crossing = iter([NOW.replace(hour=5,minute=59),
                             NOW.replace(hour=6,minute=0)])
            with self.assertRaisesRegex(ValueError, "Crossed capture slot"):
                run_once(path=file,fetcher=lambda: sample_book(),clock=lambda:next(crossing))
            self.assertFalse(file.exists())

    def test_api_failure_never_writes(self):
        with TemporaryDirectory() as tmp:
            file=Path(tmp)/"depth.csv"
            def fail():
                raise ConnectionError("no venue access")
            with self.assertRaises(ConnectionError):
                run_once(path=file,fetcher=fail,clock=lambda:NOW)
            self.assertFalse(file.exists())

    def test_empty_existing_tape_not_reset(self):
        with TemporaryDirectory() as tmp:
            file=Path(tmp)/"depth.csv"
            file.write_text(",".join(COLUMNS)+"\n")
            with self.assertRaisesRegex(ValueError,"empty/tampered"):
                append_snapshot(file,summarize_book(sample_book(),captured_at_utc=NOW))

    def test_invalid_spread_rejected(self):
        p=sample_book()
        p["result"]["XXBTZUSD"]["asks"]=[
            ["85000", "1", NOW.timestamp()-1],["86000", "1", NOW.timestamp()-1]]
        with self.assertRaisesRegex(ValueError,"Implausibly"):
            summarize_book(p,captured_at_utc=NOW)

    def test_bad_tape_partial_depth_has_no_share(self):
        with TemporaryDirectory() as tmp:
            file=Path(tmp)/"depth.csv"
            r=summarize_book(sample_book(), captured_at_utc=NOW)
            append_snapshot(file,r)
            rows=read_verified_tape(file)
            rows[0]["complete_25bps_band"]="False"
            rows[0]["row_hash"]=_signature(rows[0])
            with file.open("w",newline="") as f:
                w=csv.DictWriter(f,fieldnames=COLUMNS)
                w.writeheader();w.writerows(rows)
            with self.assertRaisesRegex(ValueError,"fabricated"):
                read_verified_tape(file)


if __name__=="__main__":
    unittest.main()
