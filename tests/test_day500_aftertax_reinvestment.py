"""Independent synthetic tests: no fake early user portfolio and no lookahead."""
import unittest

import numpy as np
import pandas as pd

from engines.research.day500_aftertax_reinvestment import (
    PRIMARY, SELLERS, GATES, causal_buyback_dates, simulate_roundtrip,
    fx_before, sell_orders,
)


def market(*,n=1260):
    halving=pd.Timestamp("2020-05-11",tz="UTC")
    days=pd.date_range(halving,periods=n,freq="D",tz="UTC")
    i=np.arange(n)
    x=np.interp(i,[0,400,500,560,650,800,1000,1259],
                [100.,300.,550.,800.,450.,220.,300.,350.])
    price=pd.Series(x,index=days)
    fx=pd.DataFrame({"aud_per_usd":np.full(n,1.5)},index=days)
    return halving,price,fx


class AfterTaxBuybackTests(unittest.TestCase):
    def test_only_modern_cycles_primary(self):
        self.assertEqual(set(PRIMARY),{"2017","2021","2025"})
        self.assertNotIn("2013",PRIMARY)

    def test_fx_must_come_from_previous_date(self):
        halving,p,fx=market()
        d=halving+pd.Timedelta(days=501)
        fx.loc[d,"aud_per_usd"]=20
        self.assertEqual(fx_before(fx,d),1.5)
        fx.loc[d-pd.Timedelta(days=1),"aud_per_usd"]=2.
        self.assertEqual(fx_before(fx,d),2.)

    def test_causal_buyback_does_not_use_future_low(self):
        h,p,fx=market()
        start=h+pd.Timedelta(days=600)
        terminal=h+pd.Timedelta(days=1150)
        date,buys=causal_buyback_dates(p,start=start,gate=.4,terminal=terminal)
        self.assertIsNotNone(date)
        self.assertGreaterEqual(date,start)
        altered=p.copy()
        altered.loc[date+pd.Timedelta(days=1):]*=.1
        other,_=causal_buyback_dates(altered,start=start,gate=.4,
                                    terminal=terminal)
        self.assertEqual(date,other)
        self.assertEqual(buys[0]["day"],date)
        self.assertTrue(all(x["day"]<=terminal for x in buys))

    def test_selling_schedule_only_after_day500_and_never_overdrawn(self):
        h,p,fx=market()
        for name in SELLERS:
            events=sell_orders(p,h,name)
            self.assertTrue(events)
            self.assertGreaterEqual(events[0]["day"],h+pd.Timedelta(days=500))
            self.assertLessEqual(sum(e["fraction"] for e in events),1.0000001)
            self.assertTrue(all(0<e["fraction"]<=1 for e in events))

    def test_smsf_tax_and_self_financing_btc_cash(self):
        h,p,fx=market()
        terminal=h+pd.Timedelta(days=1150)
        for seller in SELLERS:
            for gate in GATES:
                result=simulate_roundtrip(p,fx,h,terminal,
                                           seller=seller,gate=gate)
                self.assertGreaterEqual(result["btc_held_after_buyback"],0)
                self.assertGreaterEqual(result["cash_remaining_aud"],0)
                self.assertGreaterEqual(result["sell_count"],1)
                self.assertGreaterEqual(result["brokerage_aud"],3)
                self.assertAlmostEqual(result["brokerage_aud"],
                                       3*result["orders_total"])
                self.assertGreaterEqual(result["realised_smsf_cgt_paid_est_aud"],0)
                self.assertGreaterEqual(result["initial_btc_before_selling"],0)
                self.assertGreaterEqual(
                    result["btc_equivalent_at_terminal_including_cash"],0)
                self.assertEqual(
                    result["marked_account_value_aud"]>0,True)

    def test_no_signal_does_not_fake_buys_or_25pct_target(self):
        h,p,fx=market()
        changed=pd.Series(1000.+np.arange(len(p)),index=p.index)
        t=h+pd.Timedelta(days=1150)
        res=simulate_roundtrip(changed,fx,h,t,
                               seller="fixed_525_to_560",gate=.65)
        self.assertEqual(res["buyback_buy_count"],0)
        self.assertIsNone(res["buyback_trigger_date"])
        self.assertGreater(res["cash_remaining_aud"],0)
        self.assertLess(res["btc_held_after_buyback"],res["initial_btc_before_selling"])

    def test_short_censored_observation_not_labelled_complete(self):
        h,p,fx=market(n=840)
        t=p.index[-1]
        res=simulate_roundtrip(p,fx,h,t,
                               seller="dynamic_90pct_holdback20pct",gate=.55)
        self.assertGreaterEqual(res["orders_total"],2)
        self.assertGreaterEqual(res["cash_remaining_aud"],0)

    def test_invalid_fx_fails_closed(self):
        h,p,fx=market()
        fx=fx.loc[:h+pd.Timedelta(days=3)]
        with self.assertRaisesRegex(ValueError,"No safely prior"):
            simulate_roundtrip(p,fx,h,h+pd.Timedelta(days=1150),
                               seller="dynamic_90pct",gate=.4)


if __name__=="__main__":
    unittest.main()
