"""Actual Sydney 17:00+ indicative AUD close from EXISTING BTC cron, no backfill."""
import datetime as dt
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from zoneinfo import ZoneInfo

from engines.research.asx_ibit_postclose_paired_backup import eligibility,attempt
from engines.research.ibit_asx_forward_close_tape import (
    COLUMNS,_read_rows,read_latest_close,
)
SYDNEY=ZoneInfo("Australia/Sydney")
WORKFLOW=Path(__file__).resolve().parents[1]/".github/workflows/research_btc_paired_microstructure.yml"


def syd(day,hour,minute=0):
    return dt.datetime(2026,10,day,hour,minute,tzinfo=SYDNEY)


def yahoo(day=22,*,symbol="IBIT.AX",currency="AUD"):
    stamp=int(syd(day,10).timestamp())
    return {"chart":{"result":[{
        "meta":{"symbol":symbol,"currency":currency,
                "exchangeTimezoneName":"Australia/Sydney"},
        "timestamp":[stamp],
        "indicators":{"quote":[{
            "close":[22.3],"low":[22.1],"high":[22.5],"volume":[8503]
        }]}
    }]}}


class ExistingPostcloseAsxFallbackTests(unittest.TestCase):
    def test_after_5pm_sydney_on_weekday_eligible(self):
        x=eligibility(syd(22,17,1))
        self.assertTrue(x["eligible"])
        self.assertEqual(x["research_sydney_session"],"2026-10-22")
        self.assertFalse(x["source_is_executable_broker_quote"])
        self.assertTrue(x["no_weekday_backfill"])
        self.assertEqual(x["ntfy_sent"],0)

    def test_sydney_close_boundaries_and_brief_midnight_delay(self):
        self.assertFalse(eligibility(syd(22,16,59))["eligible"])
        self.assertTrue(eligibility(syd(22,17,0))["eligible"])
        self.assertTrue(eligibility(syd(22,23,59))["eligible"])
        self.assertFalse(eligibility(syd(23,0,0))["eligible"])

    def test_after_midnight_GitHub_delay_never_claims_previous_session(self):
        with TemporaryDirectory() as d:
            path=Path(d)/"closes.csv"
            def must_not_fetch():
                raise AssertionError("No provider call after Sydney midnight")
            x=attempt(clock=lambda:syd(22,4),fetcher=must_not_fetch,path=path)
            self.assertEqual(x["status"],"skipped_actual_time_outside_session")
            self.assertFalse(path.exists())
            self.assertFalse(x["provider_requested"])

    def test_weekend_before_earliest_and_naive_time_fail_closed(self):
        for moment in (syd(19,19),syd(24,19),syd(25,19)):
            self.assertFalse(eligibility(moment)["eligible"])
        with self.assertRaisesRegex(ValueError,"timezone-aware"):
            eligibility(dt.datetime(2026,10,22,18))

    def test_same_day_yahoo_close_is_frozen_only_at_actual_provider_receipt(self):
        ticks=iter([syd(22,17,8),syd(22,17,9)])
        with TemporaryDirectory() as d:
            path=Path(d)/"closes.csv"
            x=attempt(clock=lambda:next(ticks),fetcher=yahoo,path=path)
            self.assertTrue(x["wrote_close"])
            self.assertEqual(x["status"],"captured")
            self.assertTrue(x["capture_instant_is_after_fetch"])
            rows=_read_rows(path.read_text(),COLUMNS,date_key="market_session_date_sydney")
            self.assertEqual(len(rows),1)
            self.assertEqual(rows[0]["market_session_date_sydney"],"2026-10-22")
            self.assertEqual(rows[0]["captured_at_utc"],syd(22,17,9).astimezone(dt.timezone.utc).isoformat())
            self.assertEqual(rows[0]["symbol"],"ASX:IBIT")
            self.assertEqual(rows[0]["currency"],"AUD")
            self.assertEqual(rows[0]["is_confirmed_broker_fill"],"False")
            self.assertEqual(x["ntfy_sent"],0)
            self.assertEqual(x["broker_orders"],0)

    def test_late_http_crosses_midnight_no_backdated_sydney_session(self):
        ticks=iter([syd(22,23,59),syd(23,0,1)])
        with TemporaryDirectory() as d:
            path=Path(d)/"closes.csv"
            x=attempt(clock=lambda:next(ticks),fetcher=yahoo,path=path)
            self.assertEqual(x["status"],"skipped_provider_receipt_crossed_sydney_date_or_window")
            self.assertFalse(x["wrote_close"])
            self.assertFalse(path.exists())

    def test_valid_schedule_time_never_selects_yesterdays_stale_yahoo_candle(self):
        ticks=iter([syd(22,17,8),syd(22,17,9)])
        with TemporaryDirectory() as d:
            path=Path(d)/"closes.csv"
            x=attempt(clock=lambda:next(ticks),fetcher=lambda:yahoo(21),path=path)
            self.assertEqual(x["status"],"skipped_no_same_day_verified_aud_candle")
            self.assertFalse(x["wrote_close"])
            self.assertFalse(path.exists())

    def test_skip_same_day_duplicate_at_second_capture(self):
        with TemporaryDirectory() as d:
            path=Path(d)/"closes.csv"
            steps=iter([syd(22,17,8),syd(22,17,9),syd(22,18,9),syd(22,18,10)])
            first=attempt(clock=lambda:next(steps),fetcher=yahoo,path=path)
            original=path.read_bytes()
            second=attempt(clock=lambda:next(steps),fetcher=yahoo,path=path)
            self.assertTrue(first["wrote_close"])
            self.assertEqual(second["status"],"already_frozen_no_change")
            self.assertEqual(original,path.read_bytes())

    def test_original_read_latest_close_refuses_wrong_currency_not_fabricated(self):
        ticks=iter([syd(22,18,8),syd(22,18,9)])
        with TemporaryDirectory() as d:
            path=Path(d)/"closes.csv"
            with self.assertRaisesRegex(ValueError,"non-Australian"):
                attempt(clock=lambda:next(ticks),
                        fetcher=lambda:yahoo(currency="USD"),path=path)
            self.assertFalse(path.exists())

    def test_existing_paired_workflow_unchanged_one_cron_and_no_message(self):
        c=WORKFLOW.read_text()
        self.assertEqual(c.count("cron:"),1)
        self.assertIn("17 1,7,13,19 * * *",c)
        self.assertIn("asx_ibit_postclose_paired_backup --is-window",c)
        self.assertIn("python -m engines.research.asx_ibit_postclose_paired_backup",c)
        self.assertNotIn("ntfy.sh",c)
        self.assertNotIn("requests.post",c)

    def test_asx_fallback_after_paired_source_and_mid_session_publisher(self):
        c=WORKFLOW.read_text()
        a=c.index("Best-effort strictly TIMESTAMPED Cycle mid-session")
        b=c.index("Best-effort strictly POSTCLOSE Sydney ASX:IBIT")
        self.assertGreater(b,a)
        x=c[b:]
        self.assertLess(x.index("asx_ibit_postclose_paired_backup --is-window"),
                        x.index("pip install -r requirements.txt"))
        self.assertLess(x.index("git fetch origin main"),x.index('git add -- "$path"'))
        self.assertLess(x.index('cmp -s "$out/checkout_source.csv" "$out/latest_remote_source.csv"'),
                        x.index('git add -- "$path"'))
        self.assertIn("git rebase origin/main",x)
        self.assertIn("git push origin HEAD:main",x)
        self.assertIn("if-no-files-found: warn",x)


if __name__=="__main__":
    unittest.main()
