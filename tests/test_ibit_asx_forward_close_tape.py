"""ASX:IBIT AUD *prospective* daily candle frozen at Sydney session close."""
import datetime as dt
import tempfile
import unittest
from pathlib import Path
from zoneinfo import ZoneInfo

from engines.research.ibit_asx_forward_close_tape import (
    read_latest_close,append_market_observation,capture_once,
    COLUMNS,_read_rows,NonTradingOrMissingClose,
)

SYD=ZoneInfo("Australia/Sydney")
UTC=dt.timezone.utc
OPEN=dt.datetime(2026,10,19,10,0,tzinfo=SYD)
AFTER=dt.datetime(2026,10,19,18,40,tzinfo=SYD)


def yahoo(symbol="IBIT.AX",currency="AUD",asx_day=OPEN,
          close=22.51,low=22.3,high=22.75,volume=12023):
    stamp=int(asx_day.timestamp())
    return {
        "chart":{"result":[{
            "meta":{"symbol":symbol,"currency":currency,
                    "exchangeTimezoneName":"Australia/Sydney"},
            "timestamp":[stamp],
            "indicators":{"quote":[{
                "close":[close],"low":[low],
                "high":[high],"volume":[volume],
            }]},
        }]}
    }


class IbitSydneyProspectiveCloseTests(unittest.TestCase):
    def test_same_day_completed_aud_asx_candle_records_price_and_source(self):
        row=read_latest_close(yahoo(),captured_at_utc=AFTER)
        self.assertEqual(row["market_session_date_sydney"],"2026-10-19")
        self.assertEqual(row["symbol"],"ASX:IBIT")
        self.assertEqual(row["currency"],"AUD")
        self.assertEqual(row["reported_close_aud"],"22.510000")
        self.assertEqual(row["daily_volume"],"12023")
        self.assertEqual(row["single_provider_unverified_execution"],"True")
        self.assertEqual(row["is_confirmed_broker_fill"],"False")

    def test_weekend_and_same_morning_cannot_generate_fake_executable_price(self):
        with self.assertRaisesRegex(NonTradingOrMissingClose,"weekday"):
            read_latest_close(yahoo(),captured_at_utc=dt.datetime(
                2026,10,18,18,tzinfo=SYD))
        with self.assertRaisesRegex(NonTradingOrMissingClose,"weekday close"):
            read_latest_close(yahoo(),captured_at_utc=dt.datetime(
                2026,10,19,14,tzinfo=SYD))

    def test_stale_holiday_or_previous_session_is_skipped(self):
        old=dt.datetime(2026,10,16,10,tzinfo=SYD)
        with self.assertRaisesRegex(NonTradingOrMissingClose,"CURRENT Sydney"):
            read_latest_close(yahoo(asx_day=old),captured_at_utc=AFTER)

    def test_refuse_us_ibit_and_wrong_timezone(self):
        with self.assertRaisesRegex(ValueError,"non-Australian"):
            read_latest_close(yahoo(symbol="IBIT",currency="USD"),
                              captured_at_utc=AFTER)
        with self.assertRaisesRegex(ValueError,"non-Australian"):
            read_latest_close(yahoo(symbol="IBIT.AX",currency="USD"),
                              captured_at_utc=AFTER)
        other=yahoo()
        other["chart"]["result"][0]["meta"]["exchangeTimezoneName"]="America/New_York"
        with self.assertRaisesRegex(ValueError,"wrong timezone"):
            read_latest_close(other,captured_at_utc=AFTER)

    def test_provider_future_bar_invalid_ohlc_and_null_are_not_recorded(self):
        with self.assertRaisesRegex(NonTradingOrMissingClose,"CURRENT Sydney"):
            read_latest_close(yahoo(close=30.,low=22.,high=23.),
                              captured_at_utc=AFTER)
        with self.assertRaisesRegex(NonTradingOrMissingClose,"CURRENT Sydney"):
            read_latest_close(yahoo(asx_day=dt.datetime(
                2026,10,20,10,tzinfo=SYD)),captured_at_utc=AFTER)
        with self.assertRaisesRegex(NonTradingOrMissingClose,"CURRENT Sydney"):
            read_latest_close(yahoo(close=None),captured_at_utc=AFTER)

    def test_hash_chain_duplicate_freeze_and_fraudulent_rewrite_failure(self):
        row=read_latest_close(yahoo(),captured_at_utc=AFTER)
        content,added=append_market_observation("",row)
        self.assertTrue(added)
        self.assertEqual(len(_read_rows(
            content,COLUMNS,date_key="market_session_date_sydney")),1)
        second,added=append_market_observation(content,row)
        self.assertFalse(added)
        self.assertEqual(second,content)
        tampered=content.replace("22.510000","12.510000")
        with self.assertRaisesRegex(ValueError,"Modified"):
            append_market_observation(tampered,row)
        old={**row,"market_session_date_sydney":"2026-10-17"}
        with self.assertRaisesRegex(ValueError,"backfill"):
            append_market_observation(content,old)

    def test_next_trading_day_can_append_with_hash_link(self):
        row=read_latest_close(yahoo(),captured_at_utc=AFTER)
        current,_=append_market_observation("",row)
        nov=dt.datetime(2026,10,20,10,tzinfo=SYD)
        at=dt.datetime(2026,10,20,18,tzinfo=SYD)
        nxt=read_latest_close(yahoo(asx_day=nov),captured_at_utc=at)
        current,added=append_market_observation(current,nxt)
        self.assertTrue(added)
        rs=_read_rows(current,COLUMNS,date_key="market_session_date_sydney")
        self.assertEqual(len(rs),2)
        self.assertEqual(rs[1]["prior_row_hash"],rs[0]["row_hash"])

    def test_skip_weekend_without_network_and_capture_once_independently(self):
        with tempfile.TemporaryDirectory() as directory:
            target=Path(directory)/"research"/"ibit.csv"
            def never_call():
                raise AssertionError("Weekend must not call quote API")
            status=capture_once(
                path=target,now=dt.datetime(
                    2026,10,18,18,tzinfo=SYD),fetcher=never_call)
            self.assertEqual(status["status"],
                             "skipped_no_completed_sydney_weekday")
            self.assertFalse(target.exists())
            call=lambda:yahoo()
            data=capture_once(path=target,now=AFTER,fetcher=call)
            self.assertTrue(data["wrote_close"])
            self.assertEqual(data["status"],"captured")
            again=capture_once(path=target,now=AFTER,fetcher=call)
            self.assertFalse(again["wrote_close"])
            self.assertEqual(again["status"],"already_frozen_no_change")
            self.assertEqual(len(_read_rows(target.read_text(),COLUMNS)),1)

    def test_missing_current_quote_does_not_create_file(self):
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/"close.csv"
            out=capture_once(path=path,now=AFTER,
                fetcher=lambda:yahoo(asx_day=dt.datetime(
                    2026,10,16,10,tzinfo=SYD)))
            self.assertEqual(out["status"],
                             "skipped_no_same_day_verified_aud_candle")
            self.assertFalse(out["wrote_close"])
            self.assertFalse(path.exists())

    def test_capture_instant_requires_timezone(self):
        with self.assertRaisesRegex(ValueError,"timezone-aware"):
            read_latest_close(yahoo(),captured_at_utc=dt.datetime(
                2026,10,19,18,30))
        with self.assertRaisesRegex(ValueError,"timezone-aware"):
            capture_once(now=dt.datetime(2026,10,19,18,30))


if __name__=="__main__":
    unittest.main()
