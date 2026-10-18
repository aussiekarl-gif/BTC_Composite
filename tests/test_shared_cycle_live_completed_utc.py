"""STRICT shared Cycle Streamlit/one daily ntfy completed UTC BTC close.

BTC provider daily label 00:00 on D refers to CLOSE D-1, Kraken
daily OHLC label D refers to D close. Testing unchanged market 200WMA,
BUY/SELL % and no trading recommendation if providers are incomplete.
"""
import datetime as dt
import unittest
from unittest.mock import patch

import numpy as np
import pandas as pd

from engines.research.cycle_live_completed_utc_prices import (
    aligned_blockchain_completed_utc_closes,
    merge_verified_live_cycle_prices,
)
from engines.research.cycle_trading_dashboard_model import build_dashboard_market
from engines.research.cycle_trade_allocation import calculate_allocation_signal
from cycle_trading_daily_ntfy import daily_message

TODAY=pd.Timestamp("2026-10-18",tz="UTC")


def fixtures(*,close_day="2026-10-17",last_raw_day="2026-10-16"):
    hist=pd.date_range("2021-01-01","2026-10-05",freq="D",tz="UTC")
    archive=pd.DataFrame({"price_usd":np.full(len(hist),100.)},index=hist)
    public_idx=pd.date_range("2026-09-24",last_raw_day,freq="D",tz="UTC")
    raw=pd.DataFrame({"btc_usd":np.full(len(public_idx),100.)},
                     index=public_idx)
    kraken_idx=pd.date_range("2026-09-19",close_day,freq="D",tz="UTC")
    kraken=pd.DataFrame({"btc_usd":np.full(len(kraken_idx),100.)},
                        index=kraken_idx)
    fx_idx=pd.date_range("2026-09-01","2026-10-20",freq="D",tz="UTC")
    fx=pd.DataFrame({"aud_per_usd":np.full(len(fx_idx),1.5)},index=fx_idx)
    return archive,raw,kraken,fx


class SharedCorrectedCycleCloseTests(unittest.TestCase):
    def test_raw_chart_utc_midnight_tick_relabels_close_to_yesterday_only(self):
        _,raw,_,_=fixtures()
        original=raw.copy(deep=True)
        adjusted=aligned_blockchain_completed_utc_closes(
            raw,utc_today=TODAY)
        self.assertEqual(adjusted.index[-1].date(),dt.date(2026,10,15))
        self.assertEqual(raw.index[-1].date(),dt.date(2026,10,16))
        pd.testing.assert_frame_equal(raw,original)
        self.assertEqual(len(adjusted),len(raw))

    def test_completed_kraken_bridge_fills_two_dates_never_current(self):
        a,b,k,fx=fixtures()
        original=a.copy(deep=True)
        merged,v=merge_verified_live_cycle_prices(
            a,b,k,utc_today=TODAY)
        self.assertEqual(str(merged.index[-1].date()),"2026-10-17")
        self.assertNotIn(TODAY,merged.index)
        self.assertEqual(v["kraken_contiguous_completed_day_bridge"],[
            "2026-10-16","2026-10-17"])
        self.assertTrue(v["strict_close_date_verified"])
        self.assertLessEqual(v["recent_kraken_blockchain_max_diff_pct"],1.)
        self.assertEqual(v["max_overlap_difference_pct"],0.)
        pd.testing.assert_frame_equal(a,original)
        self.assertTrue(v["archive_raw_prices_preserved"])

    def test_chart_same_calendar_day_label_cannot_be_substituted(self):
        a,b,k,fx=fixtures()
        b.loc[pd.Timestamp("2026-10-10",tz="UTC"),"btc_usd"]=200.
        with self.assertRaisesRegex(ValueError,"disagreement"):
            merge_verified_live_cycle_prices(a,b,k,utc_today=TODAY)

    def test_large_next_day_price_move_does_not_change_prior_gate(self):
        a,b,k,fx=fixtures(close_day="2026-10-18",
                           last_raw_day="2026-10-17")
        k.loc[pd.Timestamp("2026-10-17",tz="UTC"),"btc_usd"]=60.
        k.loc[pd.Timestamp("2026-10-18",tz="UTC"),"btc_usd"]=150.
        merged,report=merge_verified_live_cycle_prices(
            a,b,k,utc_today="2026-10-19")
        self.assertEqual(merged.iloc[-1],150.)
        m=build_dashboard_market(merged,fx,asof="2026-10-19",
                                  confirmed_halving_date="2024-04-20")
        self.assertEqual(m["previous_close_usd"],60.)
        s=calculate_allocation_signal(m)
        self.assertEqual(s["signal"],"BUY WATCH")
        self.assertEqual(s["buy_pct_cash"],2.5)
        self.assertEqual(s["sell_pct_held"],0.)

    def test_current_incomplete_kraken_candle_is_never_used(self):
        a,b,k,fx=fixtures()
        k.loc[TODAY]=1000000.
        r,meta=merge_verified_live_cycle_prices(a,b,k,utc_today=TODAY)
        self.assertEqual(str(r.index[-1].date()),"2026-10-17")
        self.assertEqual(r.iloc[-1],100.)

    def test_no_latest_completed_close_fails_closed_not_stale_hold(self):
        a,b,k,fx=fixtures(close_day="2026-10-16")
        with self.assertRaisesRegex(ValueError,"yesterday"):
            merge_verified_live_cycle_prices(a,b,k,utc_today=TODAY)

    def test_publication_gap_over_3_days_fails_closed(self):
        a,b,k,fx=fixtures(last_raw_day="2026-10-12")
        with self.assertRaisesRegex(ValueError,"short safe"):
            merge_verified_live_cycle_prices(a,b,k,utc_today=TODAY)

    def test_missing_consecutive_exchange_day_fails_closed(self):
        a,b,k,fx=fixtures()
        k=k.drop(pd.Timestamp("2026-10-16",tz="UTC"))
        with self.assertRaisesRegex(ValueError,"consecutive"):
            merge_verified_live_cycle_prices(a,b,k,utc_today=TODAY)

    def test_bad_publication_timestamp_and_missing_overlap_fail_closed(self):
        a,b,k,fx=fixtures()
        bad=b.copy(deep=True)
        bad.index=bad.index+pd.Timedelta(hours=12)
        with self.assertRaisesRegex(ValueError,"midnight"):
            merge_verified_live_cycle_prices(a,bad,k,utc_today=TODAY)
        bad=b.loc["2026-10-16":]
        with self.assertRaisesRegex(ValueError,"Insufficient"):
            merge_verified_live_cycle_prices(a,bad,k,utc_today=TODAY)

    def test_historical_archive_must_not_get_rewritten_by_public_chart(self):
        a,b,k,fx=fixtures()
        b.loc[pd.Timestamp("2026-09-28",tz="UTC"),"btc_usd"]=300.
        with self.assertRaisesRegex(ValueError,"conflicts"):
            merge_verified_live_cycle_prices(a,b,k,utc_today=TODAY)
        pd.testing.assert_frame_equal(
            a,fixtures()[0])

    def test_source_verified_without_kraken_fails_not_fallback_to_raw(self):
        a,b,k,fx=fixtures()
        with self.assertRaisesRegex(ValueError,"Malformed"):
            merge_verified_live_cycle_prices(a,b,None,utc_today=TODAY)

    def test_daily_ntfy_uses_exact_same_series_date_and_decision(self):
        a,b,k,fx=fixtures()
        series,check=merge_verified_live_cycle_prices(
            a,b,k,utc_today=TODAY)
        m=build_dashboard_market(series,fx,
            asof=str(TODAY.date()),confirmed_halving_date="2024-04-20")
        self.assertEqual(calculate_allocation_signal(m)["signal"],"HOLD")
        quote={"price_aud":22.4,"timestamp_utc":"2026-10-17T07:00:00Z"}
        now=dt.datetime(2026,10,18,10,1,tzinfo=dt.timezone.utc)
        with (
            patch("cycle_trading_daily_ntfy.read_exported_history",
                  return_value=a),
            patch("cycle_trading_daily_ntfy.fetch_cycle_live_sources",
                  return_value=(b,fx,k)),
            patch("cycle_trading_daily_ntfy.fetch_halving_countdown",
                  return_value={"last_halving_date":"2024-04-20",
                                "halving_date_verified":True}),
        ):
            day,body=daily_message(now=now,quote=quote)
        self.assertIn("HOLD",body)
        self.assertIn("2026-10-17",body)
        self.assertIn("US$100",body)
        self.assertIn("0.00%",body)

    def test_daily_ntfy_missing_completed_data_reports_unavailable_not_buy(self):
        a,b,k,fx=fixtures(close_day="2026-10-16")
        now=dt.datetime(2026,10,18,10,1,tzinfo=dt.timezone.utc)
        quote={"price_aud":22.4,"timestamp_utc":"2026-10-17T07:00:00Z"}
        with (
            patch("cycle_trading_daily_ntfy.read_exported_history",
                  return_value=a),
            patch("cycle_trading_daily_ntfy.fetch_cycle_live_sources",
                  return_value=(b,fx,k)),
        ):
            day,body=daily_message(now=now,quote=quote)
        self.assertIn("DATA UNAVAILABLE",body)
        self.assertIn("BUY allocation: unavailable",body)
        self.assertNotIn("BUY WATCH",body)

    def test_future_dated_chart_point_rejected_even_if_kraken_valid(self):
        a,b,k,fx=fixtures()
        b.loc[pd.Timestamp("2026-10-19",tz="UTC")]=100.
        with self.assertRaisesRegex(ValueError,"Future-dated"):
            merge_verified_live_cycle_prices(a,b,k,utc_today=TODAY)


if __name__=="__main__":
    unittest.main()
