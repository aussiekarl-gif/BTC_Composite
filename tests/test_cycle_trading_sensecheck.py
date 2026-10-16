"""Safety: a daily WATCH must not become a repeat DCA trade."""
import datetime as dt
import unittest
from unittest.mock import Mock,patch

import numpy as np
import pandas as pd

from engines.research.cycle_trade_execution_safety import (
    cooldown_check,last_executed_transaction,historical_btc_aud_reference,
)
from engines.research.cycle_trade_decision import make_current_decision
from engines.research.cycle_trading_dashboard_model import build_dashboard_market
from engines.research.ibit_quote import fetch_ibit_quote,URL,FALLBACK_URL


def fixture():
    idx=pd.date_range("2022-06-01",periods=1600,freq="D",tz="UTC")
    prices=pd.Series(50_000.+np.arange(len(idx))*40.,index=idx)
    fx=pd.DataFrame({"aud_per_usd":np.full(len(idx),1.5)},index=idx)
    m=build_dashboard_market(prices,fx)
    m["prior_200wma_usd"]=m["previous_close_usd"]/.80
    m["previous_close_below_200wma"]=True
    return m,idx[-1].date()


def portfolio(*,last_buy="01/08/26",sale=None):
    p={"starting_capital_aud":500_000.,
       "rows":[{"Date":last_buy,"Asset":"ASX:IBIT",
                "AUD Spent":150_000.,"Brokerage / Fee AUD":3.,
                "Units / BTC Received":9000.,"BTC AUD Price":150000.}]}
    if sale:
        p["sales"]=[{"Date":sale,"Asset":"ASX:IBIT",
                     "Units Sold":500.,"AUD Proceeds":10000.,
                     "Brokerage / Fee AUD":3.}]
    return p


class DailyVersusWeeklySafetyTests(unittest.TestCase):
    def test_market_watch_persists_but_repeated_recent_buy_is_blocked(self):
        m,today=fixture()
        one_day_ago=today-dt.timedelta(days=1)
        p=portfolio(last_buy=one_day_ago.strftime("%d/%m/%y"))
        d=make_current_decision(m,p,today=today,ibit_price_aud=22.)
        self.assertEqual(d["market_signal"],"BUY WATCH")
        self.assertEqual(d["action"],"HOLD")
        self.assertEqual(d["action_aud"],0.)
        self.assertEqual(d["buy_pct_total_cash"],2.5)
        self.assertTrue(any("next weekly DCA tranche" in x for x in d["why"]))
        self.assertEqual(d["next_dca_eligible_date"],str(one_day_ago+dt.timedelta(days=7)))

    def test_sales_also_count_as_executed_trades_during_week(self):
        m,today=fixture()
        p=portfolio(sale=(today-dt.timedelta(days=2)).strftime("%d/%m/%y"))
        d=make_current_decision(m,p,today=today,ibit_price_aud=22.)
        self.assertEqual(d["market_signal"],"BUY WATCH")
        self.assertEqual(d["action"],"HOLD")

    def test_weekly_signal_unlocks_at_exactly_seven_days(self):
        m,today=fixture()
        p=portfolio(last_buy=(today-dt.timedelta(days=7)).strftime("%d/%m/%y"))
        check=cooldown_check(p,today=today)
        self.assertTrue(check["allowed"])
        d=make_current_decision(m,p,today=today,ibit_price_aud=22.)
        self.assertEqual(d["action"],"BUY")
        self.assertGreater(d["estimated_ibit_units"],0)

    def test_missing_etf_quote_produces_watch_not_actionable_buy(self):
        m,today=fixture()
        d=make_current_decision(m,portfolio(),today=today,ibit_price_aud=None)
        self.assertEqual(d["market_signal"],"BUY WATCH")
        self.assertEqual(d["action"],"HOLD")
        self.assertEqual(d["action_aud"],0.)
        self.assertTrue(any("ASX:IBIT AUD quote" in x for x in d["why"]))

    def test_corrupt_future_trade_date_blocks_trading(self):
        m,today=fixture()
        p=portfolio(last_buy=(today+dt.timedelta(days=1)).strftime("%d/%m/%y"))
        d=make_current_decision(m,p,today=today,ibit_price_aud=22.)
        self.assertEqual(d["action"],"HOLD")
        self.assertTrue(any("transaction" in x.lower() for x in d["why"]))

    def test_missing_cash_positions_never_fall_back_to_synthetic_50000(self):
        m,today=fixture()
        d=make_current_decision(m,None,today=today,ibit_price_aud=22.)
        self.assertEqual(d["action"],"HOLD")
        self.assertEqual(d["action_aud"],0.)

    def test_last_trade_includes_sales_and_tracks_date(self):
        today=dt.date(2026,10,17)
        p=portfolio(sale="16/10/26")
        recent=last_executed_transaction(p)
        self.assertEqual(recent["side"],"SELL")
        self.assertEqual(recent["date"],today-dt.timedelta(days=1))
        c=cooldown_check(p,today=today)
        self.assertFalse(c["allowed"])
        self.assertEqual(c["next_eligible_date"],"2026-10-23")


class DateAwareReferenceTests(unittest.TestCase):
    def setUp(self):
        self.prices=pd.Series(
            [100.,110.,120.,130.,140.,150.],
            index=pd.date_range("2026-10-10",periods=6,freq="D",tz="UTC"))
        self.fx=pd.DataFrame({"aud_per_usd":[1.50,1.60,1.70]},
            index=pd.DatetimeIndex(["2026-10-09","2026-10-13","2026-10-16"],tz="UTC"))

    def test_historical_fx_and_btc_close_not_latest(self):
        old=historical_btc_aud_reference(
            self.prices,self.fx,trade_date="2026-10-12")
        self.assertEqual(old["btc_aud_reference"],180.)
        self.assertEqual(old["price_date"],"2026-10-12")
        self.assertEqual(old["fx_date"],"2026-10-09")
        now=historical_btc_aud_reference(
            self.prices,self.fx,trade_date="2026-10-15")
        self.assertEqual(now["btc_aud_reference"],240.)
        self.assertEqual(now["fx_date"],"2026-10-13")

    def test_future_prices_cannot_change_past_historical_reference(self):
        old=historical_btc_aud_reference(
            self.prices,self.fx,trade_date="2026-10-12")
        p=self.prices.copy()
        p.iloc[-1]=1e9
        other=historical_btc_aud_reference(p,self.fx,trade_date="2026-10-12")
        self.assertEqual(old,other)

    def test_unavailable_fx_or_price_is_unavailable_not_current_quote(self):
        fx=self.fx.loc["2026-10-16":]
        self.assertIsNone(historical_btc_aud_reference(
            self.prices,fx,trade_date="2026-10-12"))
        self.assertIsNone(historical_btc_aud_reference(
            self.prices,self.fx,trade_date="2026-10-01"))
        self.assertIsNone(historical_btc_aud_reference(
            self.prices,self.fx,trade_date="2026-11-01",max_price_lag_days=2))


class AutoQuoteFallbackTests(unittest.TestCase):
    def test_falls_back_to_second_aud_asx_quote_host(self):
        now=dt.datetime(2026,10,17,tzinfo=dt.timezone.utc)
        stamp=int((now-dt.timedelta(hours=5)).timestamp())
        response=Mock()
        response.raise_for_status.return_value=None
        response.json.return_value={"chart":{"result":[{"meta":{
            "symbol":"IBIT.AX","currency":"AUD","regularMarketPrice":22.45,
            "regularMarketTime":stamp,
        }}]}}
        import requests
        with patch("engines.research.ibit_quote.requests.get",
                   side_effect=[requests.RequestException("unavailable"),response]) as getter:
            quote=fetch_ibit_quote(now=now)
        self.assertEqual(quote["price_aud"],22.45)
        self.assertEqual(getter.call_count,2)
        self.assertEqual(getter.call_args[0][0],FALLBACK_URL)

    def test_rejects_us_ticker_on_both_sources(self):
        now=dt.datetime(2026,10,17,tzinfo=dt.timezone.utc)
        response=Mock()
        response.raise_for_status.return_value=None
        response.json.return_value={"chart":{"result":[{"meta":{
            "symbol":"IBIT","currency":"USD","regularMarketPrice":22.45,
            "regularMarketTime":int(now.timestamp()),
        }}]}}
        with patch("engines.research.ibit_quote.requests.get",return_value=response):
            with self.assertRaisesRegex(ValueError,"quote unavailable"):
                fetch_ibit_quote(now=now)


if __name__=="__main__":
    unittest.main()
