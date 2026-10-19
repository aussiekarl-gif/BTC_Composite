"""Offline paired BTC feed collection invariants; no network or portfolio."""
import datetime as dt
from pathlib import Path
from unittest import TestCase
from unittest.mock import patch

from engines.research import btc_coordinated_capture as c

A="2026-10-19T07:17:05+00:00"
B="2026-10-19T07:17:07+00:00"
SLOT="2026-10-19T06:00:00+00:00"

def kraken(stamp=A,slot=SLOT):
    return {"slot_utc":slot,"captured_at_utc":stamp}

def coinbase(stamp=B,slot=SLOT):
    return {"slot_utc":slot,"captured_at_utc":stamp}


def run(*, kraken_record=None, coinbase_record=None,
        k_runner=None,c_runner=None):
    ks=[] if kraken_record is False else [kraken_record or kraken()]
    cs=[] if coinbase_record is False else [coinbase_record or coinbase()]
    with patch.object(c,"read_verified_tape",return_value=ks) as rk:
        with patch.object(c,"read_tape",return_value=cs) as rc:
            result=c.collect(
                kraken_path=Path("/shadow/kraken.csv"),
                coinbase_path=Path("/shadow/coinbase.csv"),
                kraken_runner=k_runner or (lambda *,path: True),
                coinbase_runner=c_runner or (lambda *,path: True))
            return result,rk.call_count,rc.call_count

class PairedCaptureTests(TestCase):
    def test_new_pair_with_seconds_skew(self):
        r,a,b=run()
        self.assertEqual(r["latest_capture_skew_seconds"],2)
        self.assertTrue(r["latest_pair_within_5_min"])
        self.assertEqual(r["kraken_status"],"NEW_SNAPSHOT")
        self.assertEqual(r["coinbase_status"],"NEW_SNAPSHOT")
        self.assertEqual((a,b),(2,2))
        self.assertEqual(r["new_trading_signals"],0)
    def test_five_min_boundary_inclusive(self):
        s=(dt.datetime.fromisoformat(A)+dt.timedelta(minutes=5)).isoformat()
        self.assertTrue(run(coinbase_record=coinbase(s))[0]["latest_pair_within_5_min"])
    def test_outside_five_min_unpaired(self):
        s=(dt.datetime.fromisoformat(A)+dt.timedelta(minutes=7)).isoformat()
        r,_,_=run(coinbase_record=coinbase(s))
        self.assertFalse(r["latest_pair_within_5_min"])
        self.assertEqual(r["latest_capture_skew_seconds"],420)
    def test_other_market_slot_cannot_pair(self):
        r,_,_=run(coinbase_record=coinbase(slot="2026-10-19T00:00:00+00:00"))
        self.assertFalse(r["latest_same_utc_slot"])
    def test_one_provider_failure_does_not_suppress_other(self):
        def fail(*,path):raise ConnectionError("Kraken outage")
        r,_,_=run(k_runner=fail)
        self.assertEqual(r["kraken_status"],"PROVIDER_CAPTURE_FAILED")
        self.assertEqual(r["coinbase_status"],"NEW_SNAPSHOT")
        self.assertFalse(r["all_providers_ok"])
        self.assertEqual(r["provider_capture_failures"],["kraken: ConnectionError"])
    def test_unrelated_coinbase_outage_does_not_suppress_kraken(self):
        def fail(*,path):raise TimeoutError("Coinbase outage")
        r,_,_=run(c_runner=fail)
        self.assertEqual(r["kraken_status"],"NEW_SNAPSHOT")
        self.assertEqual(r["coinbase_status"],"PROVIDER_CAPTURE_FAILED")
    def test_both_archives_missing_does_not_fabricate_pair(self):
        r,_,_=run(kraken_record=False,coinbase_record=False)
        self.assertFalse(r["latest_pair_within_5_min"])
        self.assertEqual(r["kraken_tape_rows"],0)
    def test_idempotent_existing_slot(self):
        r,_,_=run(k_runner=lambda *,path:False,c_runner=lambda *,path:False)
        self.assertEqual(r["kraken_status"],"EXISTING_SLOT")
        self.assertEqual(r["coinbase_status"],"EXISTING_SLOT")
    def test_corrupt_prior_tape_aborts_before_collectors(self):
        with patch.object(c,"read_verified_tape",side_effect=ValueError("tampered")):
            with self.assertRaisesRegex(ValueError,"tampered"):
                c.collect(kraken_runner=lambda *,path:self.fail("called"),
                          coinbase_runner=lambda *,path:self.fail("called"))
    def test_timestamp_without_timezone_rejected(self):
        with self.assertRaisesRegex(ValueError,"timezone"):
            c._stamp("2026-10-19T07:17:05")
    def test_no_scheduled_extra_notification(self):
        self.assertEqual(run()[0]["new_ntfy_messages"],0)
        self.assertEqual(run()[0]["scheduled_runner_jobs_per_day"],4)

if __name__=="__main__":
    import unittest
    unittest.main()
