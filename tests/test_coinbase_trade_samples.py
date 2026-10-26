"""Point-in-time bounded public trade sample tests (no live network)."""
import csv
import datetime as dt
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from engines.research.coinbase_trade_samples import (
    GENESIS, LIMIT, COLUMNS, append, read_tape, run_once, signature, summarize,
)

UTC=dt.timezone.utc
NOW=dt.datetime(2026,10,19,2,30,tzinfo=UTC)

def sample(now=NOW):
    return {"trades":[
        {"trade_id":"103","product_id":"BTC-USD","price":"80001.0",
         "size":"0.4","side":"SELL", "time":(now-dt.timedelta(seconds=1)).isoformat()},
        {"trade_id":"102","product_id":"BTC-USD","price":"80000.0",
         "size":"0.6","side":"BUY", "time":(now-dt.timedelta(seconds=3)).isoformat()},
        {"trade_id":"101","product_id":"BTC-USD","price":"80000.5",
         "size":"0.3","side":"SELL", "time":(now-dt.timedelta(seconds=5)).isoformat()},
    ]}

class CoinbaseTradesTests(unittest.TestCase):
    def test_live_shape_and_maker_inverse(self):
        row=summarize(sample(),captured_at_utc=NOW)
        self.assertEqual(row["maker_sell_count_aggressor_buy"],"2")
        self.assertEqual(row["maker_buy_count_aggressor_sell"],"1")
        self.assertAlmostEqual(float(row["aggressor_buy_btc_sample"]),0.7)
        self.assertAlmostEqual(float(row["aggressor_sell_btc_sample"]),0.6)
        self.assertEqual(row["research_signal"],"OBSERVATION_ONLY_NO_TRADE")
        self.assertEqual(row["sample_only_not_continuous"],"True")
        self.assertEqual(row["slot_utc"],"2026-10-19T00:00:00+00:00")
    def test_subsecond_receipt_and_legacy_seconds_append_only(self):
        precise = NOW.replace(microsecond=654321)
        observation = summarize(sample(), captured_at_utc=precise)
        self.assertEqual(observation["captured_at_utc"],
                         precise.isoformat(timespec="microseconds"))
        with TemporaryDirectory() as folder:
            file = Path(folder)/"tape.csv"
            old = summarize(sample(), captured_at_utc=NOW)
            old["captured_at_utc"] = NOW.isoformat(timespec="seconds")
            self.assertTrue(append(file, old))
            old_hash = read_tape(file)[0]["row_hash"]
            later = NOW + dt.timedelta(hours=6, microseconds=654321)
            self.assertTrue(append(
                file, summarize(sample(now=later), captured_at_utc=later)))
            rows = read_tape(file)
            self.assertEqual(len(rows), 2)
            self.assertEqual(rows[0]["captured_at_utc"], NOW.isoformat(timespec="seconds"))
            self.assertEqual(rows[0]["row_hash"], old_hash)
            self.assertEqual(rows[1]["captured_at_utc"],
                             later.isoformat(timespec="microseconds"))
            self.assertEqual(rows[1]["previous_row_hash"], old_hash)

    def test_freshness(self):
        with self.assertRaisesRegex(ValueError,"stale"):
            summarize(sample(now=NOW-dt.timedelta(minutes=9)),captured_at_utc=NOW)
    def test_future_trade(self):
        with self.assertRaisesRegex(ValueError,"Future"):
            summarize(sample(now=NOW+dt.timedelta(seconds=180)),captured_at_utc=NOW)
    def test_duplicate_id(self):
        p=sample();p["trades"][1]["trade_id"]="103"
        with self.assertRaisesRegex(ValueError,"duplicated"):
            summarize(p,captured_at_utc=NOW)
    def test_unknown_side(self):
        p=sample();p["trades"][0]["side"]="b"
        with self.assertRaisesRegex(ValueError,"maker side"):
            summarize(p,captured_at_utc=NOW)
    def test_wrong_market(self):
        p=sample();p["trades"][0]["product_id"]="ETH-USD"
        with self.assertRaisesRegex(ValueError,"Different"):
            summarize(p,captured_at_utc=NOW)
    def test_invalid_price(self):
        p=sample();p["trades"][0]["price"]="-1"
        with self.assertRaisesRegex(ValueError,"finite"):
            summarize(p,captured_at_utc=NOW)
    def test_nan_size(self):
        p=sample();p["trades"][0]["size"]="nan"
        with self.assertRaises(ValueError):
            summarize(p,captured_at_utc=NOW)
    def test_missing_trades(self):
        with self.assertRaisesRegex(ValueError,"trades array"):
            summarize({"error":"access denied"},captured_at_utc=NOW)
    def test_empty_trades(self):
        with self.assertRaisesRegex(ValueError,"Unexpected number"):
            summarize({"trades":[]},captured_at_utc=NOW)
    def test_unsorted_trades(self):
        p=sample();p["trades"][0],p["trades"][2]=p["trades"][2],p["trades"][0]
        with self.assertRaisesRegex(ValueError,"chronological"):
            summarize(p,captured_at_utc=NOW)
    def test_naive_time(self):
        p=sample();p["trades"][0]["time"]="2026-10-19T02:30:00"
        with self.assertRaises(ValueError):
            summarize(p,captured_at_utc=NOW)
    def test_over_limit(self):
        p=sample();p["trades"]=p["trades"]*40
        with self.assertRaises(ValueError):
            summarize(p,captured_at_utc=NOW)
    def test_idempotent_and_tamper(self):
        with TemporaryDirectory() as folder:
            f=Path(folder)/"tape.csv"
            r=summarize(sample(),captured_at_utc=NOW)
            self.assertTrue(append(f,r));self.assertFalse(append(f,r))
            self.assertEqual(read_tape(f)[0]["previous_row_hash"],GENESIS)
            self.assertEqual(read_tape(f)[0]["row_hash"],signature(read_tape(f)[0]))
            f.write_text(f.read_text().replace("Coinbase_Advanced_Public_Market_Trades","FAKE_COINBASE"))
            with self.assertRaisesRegex(ValueError,"hash chain"):read_tape(f)
    def test_second_slot_and_no_backfill(self):
        with TemporaryDirectory() as folder:
            f=Path(folder)/"tape.csv"
            first=summarize(sample(),captured_at_utc=NOW)
            t=NOW+dt.timedelta(hours=6)
            second=summarize(sample(now=t),captured_at_utc=t)
            self.assertTrue(append(f,first));self.assertTrue(append(f,second))
            self.assertEqual(len(read_tape(f)),2)
            with self.assertRaisesRegex(ValueError,"backfill"):append(f,first)
    def test_run_capture_and_duplicate(self):
        with TemporaryDirectory() as folder:
            f=Path(folder)/"tape.csv"
            time=iter([NOW, NOW+dt.timedelta(seconds=1)])
            self.assertTrue(run_once(path=f,fetcher=lambda:sample(),clock=lambda:next(time)))
            self.assertEqual(read_tape(f)[0]["observed_trades"],"3")
            def no_fetch():raise AssertionError("Should never refetch duplicate slot")
            self.assertFalse(run_once(path=f,fetcher=no_fetch,clock=lambda:NOW))
    def test_network_error_no_file(self):
        with TemporaryDirectory() as folder:
            f=Path(folder)/"tape.csv"
            def fail():raise ConnectionError("connection failed")
            with self.assertRaises(ConnectionError):
                run_once(path=f,fetcher=fail,clock=lambda:NOW)
            self.assertFalse(f.exists())
    def test_cross_slot_no_write(self):
        with TemporaryDirectory() as folder:
            f=Path(folder)/"tape.csv"
            before=NOW.replace(hour=5,minute=59)
            after=NOW.replace(hour=6,minute=0)
            times=iter([before,after])
            with self.assertRaisesRegex(ValueError,"slot crossed"):
                run_once(path=f,fetcher=lambda:sample(now=before),clock=lambda:next(times))
            self.assertFalse(f.exists())
    def test_invalid_existing_tape_must_not_reset(self):
        with TemporaryDirectory() as folder:
            f=Path(folder)/"tape.csv"
            f.write_text(",".join(COLUMNS)+"\n")
            with self.assertRaisesRegex(ValueError,"Empty existing"):
                append(f,summarize(sample(),captured_at_utc=NOW))
    def test_tape_cannot_relabel_sample_continuous(self):
        with TemporaryDirectory() as folder:
            f=Path(folder)/"tape.csv"
            append(f,summarize(sample(),captured_at_utc=NOW))
            rows=read_tape(f)
            rows[0]["sample_only_not_continuous"]="False"
            rows[0]["row_hash"]=signature(rows[0])
            with f.open("w",newline="") as h:
                w=csv.DictWriter(h,fieldnames=COLUMNS);w.writeheader();w.writerows(rows)
            with self.assertRaisesRegex(ValueError,"chronology or metadata"):
                read_tape(f)

if __name__ == '__main__':
    unittest.main()
