"""Unit tests for causal day500 weekly dynamic DCA-out simulation."""
import unittest

import numpy as np
import pandas as pd

from engines.research.day500_dynamic_dca_out import (
    adaptive_weekly_exit, baseline_exit, staged_day500_dynamic_exit,
    _prior_state, POLICIES, STAGED_POLICIES,
)


class Day500DynamicDcaOutTests(unittest.TestCase):
    def setUp(self):
        self.halving=pd.Timestamp("2020-05-11",tz="UTC")
        self.idx=pd.date_range("2020-05-11",periods=800,freq="D",tz="UTC")
        self.up=pd.Series(np.linspace(1000.,5000.,800),index=self.idx)

    def test_start_with_exactly_five_percent_on_halving_day500(self):
        for rule in POLICIES:
            x=adaptive_weekly_exit(self.up,self.halving,policy=rule)
            self.assertEqual(x["first_order_date"],"2021-09-23")
            self.assertAlmostEqual(x["sale_detail"][0]["btc_sold"],.05)
            self.assertEqual(x["sale_detail"][0]["halving_day"],500)
            self.assertEqual(x["sale_detail"][0]["signal_regime"],"maturity-start")
            self.assertTrue(all(r["halving_day"]==500 or
                                (r["halving_day"]-500)%7==0
                                for r in x["sale_detail"]))
            self.assertAlmostEqual(x["btc_sold"]+x["btc_left"],1.,places=8)

    def test_prior_week_fraction_does_not_depend_on_that_days_price(self):
        modified=self.up.copy()
        day507=self.halving+pd.Timedelta(days=507)
        # Modify the EXECUTION close at 507; changes proceeds, not
        # prior-observation sizing at this date.
        modified.loc[day507]=100000.
        old=adaptive_weekly_exit(self.up,self.halving,policy="balanced")
        new=adaptive_weekly_exit(modified,self.halving,policy="balanced")
        old_trade=next(r for r in old["sale_detail"] if r["halving_day"]==507)
        new_trade=next(r for r in new["sale_detail"] if r["halving_day"]==507)
        self.assertEqual(old_trade["btc_sold"],new_trade["btc_sold"])
        self.assertNotEqual(old_trade["cash_proceeds_usd"],new_trade["cash_proceeds_usd"])

    def test_future_prices_do_not_change_past_orders(self):
        cutoff=self.halving+pd.Timedelta(days=630)
        modified=self.up.copy()
        modified.loc[cutoff:]=1e6
        original=adaptive_weekly_exit(self.up,self.halving,policy="balanced")
        new=adaptive_weekly_exit(modified,self.halving,policy="balanced")
        earlier=lambda trades:[(t["date"],t["btc_sold"],t["signal_regime"])
                               for t in trades if t["date"]<str(cutoff.date())]
        self.assertEqual(earlier(original["sale_detail"]),
                         earlier(new["sale_detail"]))

    def test_declining_price_sets_defensive_regime_after_confirmation(self):
        px=pd.Series([4000.]*570+
                     [max(800.,4000.-20*(j-569)) for j in range(570,800)],
                     index=self.idx)
        day=self.halving+pd.Timedelta(days=620)
        regime,metrics=_prior_state(px,day)
        self.assertEqual(regime,"breakdown")
        self.assertGreaterEqual(metrics["drawdown_from_prior_90d_high_pct"],15)
        x=adaptive_weekly_exit(px,self.halving,policy="balanced")
        self.assertTrue(any(t["signal_regime"]=="breakdown" for t in x["sale_detail"]))

    def test_more_aggressive_policy_cannot_sell_more_than_one_btc(self):
        for name in POLICIES:
            x=adaptive_weekly_exit(self.up,self.halving,policy=name)
            self.assertGreaterEqual(x["btc_left"],0.)
            self.assertLessEqual(x["btc_sold"],1.)
            self.assertAlmostEqual(
                x["brokerage_aud_3_per_order"],3*x["orders"])
            self.assertAlmostEqual(
                x["ending_mark_usd"],
                x["gross_proceeds_usd"]+x["btc_left"]*float(
                    self.up.loc[self.halving+pd.Timedelta(days=730)]),
                delta=.003)

    def test_models_use_identical_day730_mark(self):
        hold=baseline_exit(self.up,self.halving,policy="hold")
        one=baseline_exit(self.up,self.halving,policy="day500")
        six=baseline_exit(self.up,self.halving,policy="weekly_525")
        self.assertEqual(hold["end_observation_date"],one["end_observation_date"])
        self.assertEqual(hold["end_observation_date"],six["end_observation_date"])
        self.assertAlmostEqual(hold["btc_left"],1.)
        self.assertEqual(one["orders"],1)
        self.assertEqual(six["orders"],6)
        self.assertGreater(hold["ending_mark_usd"],one["ending_mark_usd"])

    def test_staged_dca_sells_five_percent_day500_then_maturity_anchor(self):
        for policy in STAGED_POLICIES:
            q=staged_day500_dynamic_exit(self.up,self.halving,policy=policy)
            self.assertEqual(q["sale_detail"][0]["halving_day"],500)
            self.assertAlmostEqual(q["sale_detail"][0]["btc_sold"],.05)
            anchor={525,532,539,546,553,560}
            self.assertTrue(anchor.issubset({x["halving_day"] for x in q["sale_detail"]}))
            self.assertTrue(all(x["halving_day"] in anchor
                                or x["halving_day"]==500
                                or x["halving_day"]>=560
                                for x in q["sale_detail"]))
            self.assertAlmostEqual(q["btc_sold"]+q["btc_left"],1.,delta=1e-8)
            self.assertEqual(q["brokerage_aud_3_per_order"],3*q["orders"])

    def test_staged_anchor_sizing_uses_prior_close_not_execution_close(self):
        day=self.halving+pd.Timedelta(days=525)
        mutated=self.up.copy()
        mutated.loc[day]=1e7
        a=staged_day500_dynamic_exit(self.up,self.halving,policy="maturity_80pct")
        b=staged_day500_dynamic_exit(mutated,self.halving,policy="maturity_80pct")
        x=next(t for t in a["sale_detail"] if t["halving_day"]==525)
        y=next(t for t in b["sale_detail"] if t["halving_day"]==525)
        self.assertEqual(x["btc_sold"],y["btc_sold"])
        self.assertNotEqual(x["cash_proceeds_usd"],y["cash_proceeds_usd"])

    def test_staged_no_future_price_dependence_for_earlier_trades(self):
        modified=self.up.copy()
        cutoff=self.halving+pd.Timedelta(days=580)
        modified.loc[cutoff:]=1e6
        a=staged_day500_dynamic_exit(self.up,self.halving,policy="maturity_90pct")
        b=staged_day500_dynamic_exit(modified,self.halving,policy="maturity_90pct")
        before=lambda records:[
            (r["date"],r["btc_sold"],r["signal_regime"])
            for r in records if r["date"]<str(cutoff.date())]
        self.assertEqual(before(a["sale_detail"]),before(b["sale_detail"]))

    def test_staged_full_equity_includes_unsold_btc_at_day730(self):
        x=staged_day500_dynamic_exit(self.up,self.halving,policy="maturity_80pct")
        self.assertAlmostEqual(
            x["ending_mark_usd"],
            x["gross_proceeds_usd"]+x["btc_left"]*float(self.up.iloc[730]),
            delta=.002)
        self.assertGreater(x["btc_sold"],0)
        self.assertGreaterEqual(x["btc_left"],0)
        self.assertLessEqual(x["btc_sold"],1)
        with self.assertRaisesRegex(ValueError,"Unknown"):
            staged_day500_dynamic_exit(self.up,self.halving,policy="future")
        with self.assertRaisesRegex(ValueError,"Insufficient"):
            staged_day500_dynamic_exit(self.up,self.halving,review_day=550)

    def test_fail_closed_when_missing_price_or_invalid_parameters(self):
        with self.assertRaises(ValueError):
            adaptive_weekly_exit(self.up,self.halving,policy="unknown")
        with self.assertRaises(ValueError):
            adaptive_weekly_exit(self.up,self.halving,day500_fraction=.5)
        with self.assertRaises(ValueError):
            adaptive_weekly_exit(self.up,self.halving,review_day=499)
        missing=self.up.drop(self.halving+pd.Timedelta(days=507))
        with self.assertRaisesRegex(ValueError,"Missing"):
            adaptive_weekly_exit(missing,self.halving,policy="balanced")


if __name__=="__main__":
    unittest.main()
