"""Weekday-only BTC proxy execution is not actual historical ASX:IBIT."""
import unittest
import numpy as np
import pandas as pd

from engines.research.cycle_asx_weekday_execution_proxy import (
    FRACTIONS,replay_proxy,compare_modes,
)
from engines.research.live_weekly_buy_parity import replay_exact_live_market_buy

START=pd.Timestamp("2020-01-15",tz="UTC")
END=pd.Timestamp("2020-09-01",tz="UTC")


def sample(case="winter"):
    idx=pd.date_range("2015-01-01","2021-01-01",tz="UTC",freq="D")
    p=pd.Series(100.,index=idx)
    if case=="winter":
        p.loc["2020-02-01":"2020-04-20"]=65.
        p.loc["2020-04-21":]=130.
    elif case=="deep":
        p.loc["2020-02-01":]=65.
    elif case=="no_cross":
        pass
    elif case=="late_shock":
        p.loc[END]=50.
    else:
        raise ValueError("Invalid fixture")
    fx=pd.DataFrame({"aud_per_usd":1.5},
                    index=pd.date_range("2014-12-01","2021-01-01",tz="UTC",freq="D"))
    return p,fx


class WeekdayExecutionProxyTests(unittest.TestCase):
    def test_calendar_zero_fee_identical_to_old_replay(self):
        p,fx=sample("winter")
        current=replay_exact_live_market_buy(
            p,fx,start=START,terminal=END,
            fractions=FRACTIONS,budget_aud=40000.)
        proxy=replay_proxy(
            p,fx,start=START,terminal=END,fractions=FRACTIONS,
            budget_aud=40000.,weekday_only=False,
            one_side_cost_bps=0,annual_nav_fee=0.)
        for frac in FRACTIONS:
            expected=current["wallets"][str(frac)]
            actual=proxy["account"][str(frac)]
            self.assertEqual(actual["btc_equivalent"],expected["btc_held"])
            self.assertEqual(actual["remaining_cash_aud"],expected["cash_left_aud"])
            self.assertEqual(actual["purchases"],expected["fills"])
            self.assertEqual(actual["hypothetical_aud_aftertax_liquidation"],
                             expected["aftertax_aud"])

    def test_weekends_excluded_without_shifting_first_eligible_signal(self):
        p,fx=sample("winter")
        a=replay_proxy(
            p,fx,start=START,terminal=END,fractions=FRACTIONS,
            budget_aud=40000.,weekday_only=False)
        b=replay_proxy(
            p,fx,start=START,terminal=END,fractions=FRACTIONS,
            budget_aud=40000.,weekday_only=True)
        self.assertEqual(a["market_buy_watch_dates"],b["market_buy_watch_dates"])
        self.assertGreater(a["buy_watch_weekend_dates"],0)
        for key in map(str,FRACTIONS):
            self.assertEqual(b["account"][key]["orders"][0]["date"],"2020-02-03")
            for order in b["account"][key]["orders"]:
                self.assertLess(pd.Timestamp(order["date"]).weekday(),5)
                self.assertLess(order["prior_usd_close"],
                                order["prior_weekly_200wma"])

    def test_extra_spread_and_nav_fee_cannot_improve_same_buy_dates(self):
        p,fx=sample("winter")
        free=replay_proxy(p,fx,start=START,terminal=END,fractions=FRACTIONS,
                          budget_aud=40000.,weekday_only=True)
        expensive=replay_proxy(p,fx,start=START,terminal=END,fractions=FRACTIONS,
                          budget_aud=40000.,weekday_only=True,
                          one_side_cost_bps=50,annual_nav_fee=.0039)
        for frac in FRACTIONS:
            c=free["account"][str(frac)]
            d=expensive["account"][str(frac)]
            self.assertEqual([o["date"] for o in c["orders"]],
                             [o["date"] for o in d["orders"]])
            self.assertLess(d["btc_equivalent"],c["btc_equivalent"])
            self.assertLess(d["hypothetical_aud_aftertax_liquidation"],
                            c["hypothetical_aud_aftertax_liquidation"])
            self.assertEqual(d["remaining_cash_aud"],c["remaining_cash_aud"])

    def test_same_day_crash_cannot_make_prior_market_buy_watch(self):
        p,fx=sample("late_shock")
        result=replay_proxy(
            p,fx,start=START,terminal=END,fractions=FRACTIONS,
            budget_aud=40000.,weekday_only=True)
        self.assertEqual(result["market_buy_watch_dates"],0)
        for r in result["account"].values():
            self.assertEqual(r["purchases"],0)
            self.assertEqual(r["remaining_cash_aud"],40000.)

    def test_no_cross_all_fractions_stay_cash_no_false_performance(self):
        p,fx=sample("no_cross")
        row=compare_modes(p,fx,start=START,terminal=END,
                          cycle="synthetic",startday=850)
        self.assertEqual(len(row),2*5)
        for x in row:
            self.assertEqual(x["baseline_buy_count"],0)
            self.assertEqual(x["candidate_buy_count"],0)
            self.assertEqual(x["baseline_aftertax_aud"],400000.)
            self.assertEqual(x["candidate_aftertax_aud"],400000.)
            self.assertEqual(x["candidate_relative_aftertax_pct"],0.)

    def test_prefix_future_path_does_not_revise_old_orders(self):
        p,fx=sample("deep")
        early=pd.Timestamp("2020-05-02",tz="UTC")
        a=replay_proxy(p,fx,start=START,terminal=early,
                       budget_aud=40000.,weekday_only=True)
        changed=p.copy()
        changed.loc[changed.index>early]*=15.
        b=replay_proxy(changed,fx,start=START,terminal=early,
                       budget_aud=40000.,weekday_only=True)
        self.assertEqual(a,b)
        final=replay_proxy(p,fx,start=START,terminal=END,
                           budget_aud=40000.,weekday_only=True)
        for frac in FRACTIONS:
            past=a["account"][str(frac)]["orders"]
            self.assertEqual(past,[x for x in final["account"][
                str(frac)]["orders"] if x["date"]<=str(early.date())])

    def test_bad_prices_fx_cash_assumptions_fail_closed(self):
        p,fx=sample("deep")
        with self.assertRaisesRegex(ValueError,"execution assumptions"):
            replay_proxy(p,fx,start=START,terminal=END,
                         one_side_cost_bps=-1)
        with self.assertRaisesRegex(ValueError,"execution assumptions"):
            replay_proxy(p,fx,start=START,terminal=END,
                         annual_nav_fee=1.)
        with self.assertRaisesRegex(ValueError,"execution assumptions"):
            replay_proxy(p,fx,start=START,terminal=END,
                         budget_aud=-1.)
        with self.assertRaisesRegex(ValueError,"warmup"):
            replay_proxy(p.drop(pd.Timestamp("2018-01-01",tz="UTC")),fx,
                         start=START,terminal=END)
        with self.assertRaisesRegex(ValueError,"No safely prior"):
            replay_proxy(p,fx.loc[:"2020-02-01"],
                         start=START,terminal=END)

    def test_metadata_explicitly_disclaims_asx_price_parity(self):
        p,fx=sample("winter")
        a=replay_proxy(p,fx,start=START,terminal=END,
                       weekday_only=True,budget_aud=40000.)
        self.assertTrue(a["no_verified_asx_ibit_prices_before_listing"])
        self.assertTrue(a["reference_fill_is_usd_btc_close_not_ibit"])
        self.assertEqual(a["real_asx_ibit_listing_date"],"2025-11-14")
        self.assertGreater(a["buy_watch_weekend_dates"],0)


if __name__=="__main__":
    unittest.main()
