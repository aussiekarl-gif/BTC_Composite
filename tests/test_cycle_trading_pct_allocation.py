"""Shared percent sizing checks: Streamlit and ntfy must not disagree."""
import datetime as dt
import unittest

import numpy as np
import pandas as pd

from cycle_trading_daily_ntfy import daily_message
from engines.research.cycle_trade_allocation import (
    SELL_REVIEW_DAY_WEIGHTS,calculate_allocation_signal,
)
from engines.research.cycle_trade_decision import make_current_decision
from engines.research.cycle_trading_dashboard_model import build_dashboard_market


NOW=dt.datetime(2026,10,17,0,0,tzinfo=dt.timezone.utc)


def fixture():
    idx=pd.date_range("2022-06-01",periods=1600,freq="D",tz="UTC")
    series=pd.Series(np.linspace(40000.,100000.,len(idx)),index=idx)
    fx=pd.DataFrame({"aud_per_usd":np.full(len(idx),1.5)},index=idx)
    market=build_dashboard_market(series,fx)
    market["asof_date"]="2026-10-16"
    return market


def saved():
    return {"starting_capital_aud":500000.,"rows":[{
        "Date":"01/08/26","Asset":"ASX:IBIT",
        "AUD Spent":150000.,"Brokerage / Fee AUD":3.,
        "Units / BTC Received":9000.,
        "BTC AUD Price":150000.,
    }]}


def set_buy(m,ratio=.8):
    x=m.copy()
    x["prior_200wma_usd"]=x["previous_close_usd"]/ratio
    x["previous_close_below_200wma"]=True
    x["prior_close_vs_200wma_pct"]=100*(ratio-1)
    return x


def set_sell(m,cycle_day=500):
    x=m.copy()
    x["prior_200wma_usd"]=x["previous_close_usd"]/1.6
    x["previous_close_below_200wma"]=False
    x["prior_close_vs_200wma_pct"]=60.
    x["halving_day"]=cycle_day
    return x


class UnifiedCycleAllocations(unittest.TestCase):
    def test_buy_recovery_is_2_5_percent_of_remaining_cash(self):
        m=set_buy(fixture())
        market=calculate_allocation_signal(m)
        self.assertEqual(market["signal"],"BUY WATCH")
        self.assertEqual(market["buy_pct_cash"],2.5)
        self.assertEqual(market["sell_pct_held"],0)
        d=make_current_decision(
            m,saved(),today=NOW.date(),usable_cash_aud=10000.,
            ibit_price_aud=20.,feed_verified=True)
        self.assertEqual(d["action"],"BUY")
        self.assertEqual(d["buy_pct_total_cash"],2.5)
        self.assertEqual(d["sell_pct_total_holdings"],0.)
        self.assertEqual(d["action_aud"],250.)
        self.assertEqual(d["suggested_ibit_units"],12)
        self.assertEqual(d["estimated_gross_ibit_aud"],243.)
        self.assertEqual(d["trade_percentage_denominator"],
                         "remaining available AUD cash")

    def test_value_rule_buy_percent_tracks_discount(self):
        for ratio,expected in ((.8,10.),(.9,3.5)):
            m=set_buy(fixture(),ratio=ratio)
            p=calculate_allocation_signal(m,buy_style="adaptive_value")
            self.assertEqual(p["buy_pct_cash"],expected)
            d=make_current_decision(m,saved(),today=NOW.date(),
                buy_style="adaptive_value",usable_cash_aud=10000.,
                ibit_price_aud=20.)
            self.assertEqual(d["action"],"BUY")
            self.assertEqual(d["buy_pct_total_cash"],expected)
            self.assertEqual(d["action_aud"],10000*expected/100)

    def test_sell_is_percent_of_current_net_holdings(self):
        for day,pct in SELL_REVIEW_DAY_WEIGHTS.items():
            m=set_sell(fixture(),day)
            p=calculate_allocation_signal(m)
            self.assertEqual(p["signal"],"SELL WATCH")
            self.assertEqual(p["buy_pct_cash"],0)
            self.assertEqual(p["sell_pct_held"],100*pct)
            d=make_current_decision(
                m,saved(),today=NOW.date(),
                ibit_price_aud=21.,
                verified_current_ibit_units=9000.,
            )
            self.assertEqual(d["action"],"SELL")
            self.assertAlmostEqual(d["sell_pct_total_holdings"],100*pct)
            self.assertEqual(d["suggested_ibit_units"],int(9000*pct))
            self.assertAlmostEqual(d["effective_ibit_pct_held_after_rounding"],
                                   100*int(9000*pct)/9000,places=3)

    def test_rounded_down_actual_sell_percent_is_disclosed(self):
        m=set_sell(fixture(),500)
        p=saved()
        p["rows"][0]["Units / BTC Received"]=105.
        d=make_current_decision(m,p,today=NOW.date(),ibit_price_aud=100.,
                                verified_current_ibit_units=105.)
        self.assertEqual(d["action"],"SELL")
        self.assertEqual(d["sell_pct_total_holdings"],5.)
        self.assertEqual(d["suggested_ibit_units"],5)
        self.assertEqual(d["effective_ibit_pct_held_after_rounding"],4.762)

    def test_hold_both_percentages_zero(self):
        m=set_sell(fixture(),700)
        signal=calculate_allocation_signal(m)
        self.assertEqual(signal["signal"],"HOLD")
        self.assertEqual((signal["buy_pct_cash"],signal["sell_pct_held"]), (0.,0.))

    def test_notify_and_dashboard_use_same_percent_and_no_private_amount(self):
        m=set_buy(fixture())
        q={"symbol":"ASX:IBIT","price_aud":22.42,
           "timestamp_utc":"2026-10-16T05:00:00+00:00"}
        date,msg=daily_message(now=NOW,quote=q,market=m)
        self.assertEqual(date,"2026-10-17")
        self.assertIn("BUY allocation: 2.50% of available AUD cash",msg)
        self.assertIn("SELL allocation: 0.00% of current BTC/IBIT holdings",msg)
        self.assertIn("Cycle signal: BUY WATCH",msg)
        self.assertIn("no Google Sheets/broker access",msg)
        self.assertNotIn("A$500,000",msg)
        self.assertNotIn("9000 units",msg)

    def test_sell_watch_notification_is_not_actual_order(self):
        m=set_sell(fixture(),525)
        date,msg=daily_message(now=NOW,
            quote={"price_aud":22.,"timestamp_utc":"2026-10-16T05:00:00+00:00"},
            market=m)
        self.assertIn("Cycle signal: SELL WATCH",msg)
        self.assertIn("SELL allocation: 24.00% of current BTC/IBIT holdings",msg)
        self.assertIn("BUY allocation: 0.00% of available AUD cash",msg)
        self.assertIn("not a broker order",msg)

    def test_incomplete_or_inconsistent_prices_fail_closed(self):
        m=set_buy(fixture())
        m["previous_close_below_200wma"]=False
        with self.assertRaisesRegex(ValueError,"Inconsistent"):
            calculate_allocation_signal(m)
        d=make_current_decision(m,saved(),today=NOW.date(),ibit_price_aud=20.)
        self.assertEqual(d["action"],"HOLD")
        self.assertEqual(d["market_signal"],"UNAVAILABLE")
        _,body=daily_message(now=NOW,
            quote={"price_aud":22.,"timestamp_utc":"2026-10-16T05:00:00+00:00"},
            market=m)
        self.assertIn("BUY allocation: unavailable",body)

    def test_later_or_same_day_price_cannot_change_percent(self):
        m=set_sell(fixture(),500)
        old=calculate_allocation_signal(m)
        changed=m.copy()
        prices=m["price_history"].copy()
        prices.iloc[-1]=1e9
        changed["price_history"]=prices
        self.assertEqual(old,calculate_allocation_signal(changed))

    def test_valid_sell_proceeds_reinvestable_after_existing_sales(self):
        p=saved()
        # The original AUD capital need not exceed lifetime purchases
        # once previously completed SELLs have replenished liquid cash.
        p["rows"][0]["AUD Spent"]=500000.
        p["rows"][0]["Brokerage / Fee AUD"]=0.
        p["sales"]=[{
            "Date":"15/09/26","Asset":"ASX:IBIT","Units Sold":1000,
            "AUD Proceeds":25000.,"Brokerage / Fee AUD":3.
        }]
        d=make_current_decision(set_buy(fixture()),p,
            today=NOW.date(),ibit_price_aud=20.,usable_cash_aud=10000.)
        self.assertEqual(d["action"],"BUY")
        self.assertEqual(d["buy_pct_total_cash"],2.5)
        self.assertEqual(d["action_aud"],250.)


if __name__=="__main__":
    unittest.main()
