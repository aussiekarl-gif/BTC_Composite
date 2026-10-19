"""No-network tests: ASX provider probe never fabricates or writes data."""
import datetime as dt
import unittest
from zoneinfo import ZoneInfo

from engines.research.ibit_asx_public_probe import probe

SYD=ZoneInfo("Australia/Sydney")

def local(day=19,hour=20):
    return dt.datetime(2026,10,day,hour,30,tzinfo=SYD)

def yahoo(day=19,*,symbol="IBIT.AX",currency="AUD"):
    stamp=int(dt.datetime(2026,10,day,10,0,tzinfo=SYD).timestamp())
    return {"chart":{"result":[{
      "meta":{"symbol":symbol,"currency":currency,
              "exchangeTimezoneName":"Australia/Sydney"},
      "timestamp":[stamp],
      "indicators":{"quote":[{"close":[22.44],"low":[22.1],
                             "high":[22.67],"volume":[15537]}]},
    }]}}


class AsxSourceProbeTests(unittest.TestCase):
    def test_real_shape_valid_stamped_aud_daily(self):
        r=probe(now=local(),fetcher=lambda:yahoo())
        self.assertEqual(r["status"],"READY_REAL_COMPLETED_SYDNEY_AUD_CANDLE")
        self.assertEqual(r["market_session_sydney"],"2026-10-19")
        self.assertEqual(r["symbol"],"ASX:IBIT")
        self.assertEqual(r["currency"],"AUD")
        self.assertEqual(r["AUD_IBIT_indicative_close"],22.44)
        self.assertFalse(r["is_confirmed_broker_fill"])
        self.assertEqual(r["existing_ASX_tape_writes"],0)
        self.assertEqual(r["ntfy_messages"],0)
        self.assertEqual(r["broker_orders"],0)

    def test_before_17_sydney_no_provider_fetch(self):
        def fail():raise AssertionError("Should not fetch preclose")
        r=probe(now=local(hour=16),fetcher=fail)
        self.assertEqual(r["status"],"NO_ELIGIBLE_COMPLETED_LOCAL_SESSION")

    def test_weekend_never_fetches_even_after_21(self):
        def fail():raise AssertionError("Never fetch weekend")
        r=probe(now=dt.datetime(2026,10,18,22,tzinfo=SYD),fetcher=fail)
        self.assertEqual(r["status"],"NO_ELIGIBLE_COMPLETED_LOCAL_SESSION")

    def test_stale_friday_on_monday_is_not_backfilled(self):
        r=probe(now=local(),fetcher=lambda:yahoo(day=16))
        self.assertEqual(r["status"],"PROVIDER_NOT_READY_OR_REJECTED")
        self.assertFalse(r["late_Sydney_provider_problem"])
        self.assertIn("CURRENT Sydney",r["source_error_reason"])
        self.assertEqual(r["existing_ASX_tape_writes"],0)

    def test_stale_candle_after_nine_is_problem_not_price(self):
        r=probe(now=local(hour=22),fetcher=lambda:yahoo(day=16))
        self.assertEqual(r["status"],"PROVIDER_NOT_READY_OR_REJECTED")
        self.assertTrue(r["late_Sydney_provider_problem"])
        self.assertNotIn("AUD_IBIT_indicative_close",r)

    def test_wrong_us_ibit_does_not_pass(self):
        r=probe(now=local(),fetcher=lambda:yahoo(symbol="IBIT",currency="USD"))
        self.assertEqual(r["status"],"PROVIDER_NOT_READY_OR_REJECTED")
        self.assertEqual(r["source_error_type"],"ValueError")

    def test_explicit_provider_failure_leaves_no_fake_price(self):
        def fail():raise ValueError("403 provider rejection")
        r=probe(now=local(),fetcher=fail)
        self.assertEqual(r["status"],"PROVIDER_NOT_READY_OR_REJECTED")
        self.assertNotIn("AUD_IBIT_indicative_close",r)
        self.assertEqual(r["existing_ASX_tape_writes"],0)

    def test_timezone_required(self):
        with self.assertRaisesRegex(ValueError,"timezone-aware"):
            probe(now=dt.datetime(2026,10,19,20,30),fetcher=lambda:yahoo())

if __name__=="__main__":
    unittest.main()
