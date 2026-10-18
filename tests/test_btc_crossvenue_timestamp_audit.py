"""Research source comparison never becomes a trade or independent AI vote."""
import datetime as dt
import unittest
from unittest.mock import patch

from engines.research import btc_crossvenue_timestamp_audit as mod

UTC=dt.timezone.utc
NOW=dt.datetime(2026,10,19,3,0,tzinfo=UTC)


def book(at=NOW-dt.timedelta(minutes=2),slot="2026-10-19T00:00:00+00:00"):
    return {"slot_utc":slot,"captured_at_utc":at.isoformat(),
            "mid_usd":"82000.000000", "bid_depth_share_pct_25bps":"49.5",
            "complete_25bps_band":"True"}

def fills(at=NOW-dt.timedelta(minutes=1),slot="2026-10-19T00:00:00+00:00"):
    return {"slot_utc":slot,"captured_at_utc":at.isoformat(),
            "sample_vwap_usd":"82010.000000",
            "aggressor_buy_share_pct_sample":"60.0",
            "sample_duration_seconds":"20.000","observed_trades":"100"}

def check(books=None,trades=None, now=NOW):
    with patch.object(mod,"read_kraken",return_value=books if books is not None else [book()]):
        with patch.object(mod,"read_coinbase",return_value=trades if trades is not None else [fills()]):
            return mod.compare(as_of_utc=now)


class ResearchCrossVenueTests(unittest.TestCase):
    def test_near_time_not_trade(self):
        r=check()
        self.assertEqual(r["status"],"NEAR_TIME_RESEARCH_OBSERVATION")
        self.assertEqual(r["consensus_agent_votes"],0)
        self.assertFalse(r["is_trade_signal"])
        self.assertFalse(r["coinbase_sample_is_complete_interval"])
        self.assertFalse(r["kraken_depth_is_executed_volume"])
        self.assertEqual(r["executable_order_aud"],0.0)
    def test_missing_venue(self):
        self.assertEqual(check(books=[])["status"],"NOT_COMPARABLE")
    def test_no_common_slot(self):
        self.assertEqual(check(trades=[fills(slot="2026-10-18T18:00:00+00:00")])["status"],"NOT_COMPARABLE")
    def test_unequal_capture_times(self):
        r=check(trades=[fills(at=NOW-dt.timedelta(minutes=10))])
        self.assertEqual(r["status"],"NOT_COMPARABLE")
        self.assertNotIn("coinbase_vwap_vs_kraken_mid_pct",r)
    def test_stale(self):
        r=check(now=NOW+dt.timedelta(hours=13))
        self.assertEqual(r["status"],"NOT_COMPARABLE")
    def test_future(self):
        self.assertEqual(check(trades=[fills(at=NOW+dt.timedelta(minutes=1))])["status"],"NOT_COMPARABLE")
    def test_incomplete_depth(self):
        b=book();b["complete_25bps_band"]="False"
        self.assertEqual(check(books=[b])["status"],"NOT_COMPARABLE")
    def test_invalid_share(self):
        f=fills();f["aggressor_buy_share_pct_sample"]="nan"
        self.assertEqual(check(trades=[f])["status"],"NOT_COMPARABLE")
    def test_large_difference(self):
        f=fills();f["sample_vwap_usd"]="90000"
        self.assertEqual(check(trades=[f])["status"],"PRICE_DIVERGENCE_REVIEW")
    def test_invalid_asof(self):
        with self.assertRaises(ValueError):check(now=NOW.replace(tzinfo=None))


if __name__=="__main__":
    unittest.main()
