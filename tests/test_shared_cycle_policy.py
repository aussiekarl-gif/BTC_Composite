"""Independent golden parity checks: original-BTC EXIT and initial-cash BUY.

Tests preserve exact historical signal semantics while moving the
single causal state transition into a shared Research engine. They
are NOT validation of predictive performance or user 2026 returns.
"""
from __future__ import annotations
import unittest
import numpy as np
import pandas as pd

from engines.research.shared_cycle_policy import (
    STAGED_POLICIES,ANCHORS,ANCHOR_WEIGHTS,START_DAY,REVIEW_DAY,
    staged_exit_decision,exit_review_days,prior_price_regime,
    recovery_buy_budget_fraction,cycle_exit_stage_status,
)
from engines.research.day500_dynamic_dca_out import staged_day500_dynamic_exit
from engines.research.top_signal_horse_race import read_exported_history


def legacy_regime(price,day):
    o=price.loc[day-pd.Timedelta(days=90):day-pd.Timedelta(days=1)]
    prev=float(o.iloc[-1])
    hi=float(o.max())
    sma=float(o.iloc[-50:].mean())
    old=float(price.loc[day-pd.Timedelta(days=64):day-pd.Timedelta(days=15)].mean())
    if 1-prev/hi>=.15 and prev<sma and sma<old:return "breakdown"
    return "high" if prev>=.95*hi and prev>sma else "neutral"


def pre_refactor_exit(price,halving,policy,*,review_day):
    """Minimal independent translation of BEFORE-REFACTOR day500 algorithm."""
    params={
        "maturity_80pct":(.05,.80,1.,False),
        "maturity_90pct":(.05,.90,1.,False),
        "maturity_90pct_holdback20pct":(.05,.90,.80,True),
    }
    initial,core,cap,tail_only=params[policy]
    anchors=dict(zip((525,532,539,546,553,560),(6,5,4,3,2,1)))
    calendar=sorted(set([500]+list(range(500+7,review_day+1,7))+list(anchors)))
    left=1.
    rows=[]
    for d in calendar:
        if d>review_day or left<=1e-10:break
        day=halving+pd.Timedelta(days=d)
        if d==500:
            regime="maturity-start"
            portion=min(left,initial)
        elif d in anchors:
            regime=legacy_regime(price,day)
            factor={"high":1.2,"neutral":.75,"breakdown":1.3}[regime]
            portion=min(left,core*anchors[d]/21*factor)
        elif d<525:
            regime=legacy_regime(price,day)
            portion=min(left,.025) if regime=="breakdown" else 0.
        elif d>560:
            regime=legacy_regime(price,day)
            portion=(min(left,.07) if regime=="breakdown" else 0.) if tail_only else min(
                left,{"high":.045,"neutral":.012,"breakdown":.070}[regime])
        else:continue
        if d<=560:
            portion=min(portion,max(0.,cap-(1-left)))
        if portion<=1e-12:continue
        left-=portion
        rows.append((str(day.date()),round(portion,10),regime))
    return rows,round(1-left,9),round(left,9)


class OriginalBTCExitParity(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.historical=read_exported_history()["price_usd"]

    def test_exact_refactor_parity_three_recent_full_exit_windows(self):
        halvings=("2016-07-09","2020-05-11","2024-04-20")
        for halving in halvings:
            h=pd.Timestamp(halving,tz="UTC")
            with self.subTest(halving=halving):
                for policy in STAGED_POLICIES:
                    for review in (561,600,730):
                        if h+pd.Timedelta(days=review)>self.historical.index[-1]:
                            continue
                        expected,sold,left=pre_refactor_exit(
                            self.historical,h,policy,review_day=review)
                        actual=staged_day500_dynamic_exit(
                            self.historical,h,policy=policy,review_day=review)
                        rows=[(r["date"],r["btc_sold"],r["signal_regime"])
                              for r in actual["sale_detail"]]
                        self.assertEqual(rows,expected)
                        self.assertEqual(actual["btc_sold"],sold)
                        self.assertEqual(actual["btc_left"],left)

    def test_twenty_percent_holdback_applies_only_until_day560(self):
        price=self.historical
        h=pd.Timestamp("2020-05-11",tz="UTC")
        model=staged_day500_dynamic_exit(price,h,
            policy="maturity_90pct_holdback20pct",review_day=561)
        self.assertLessEqual(model["btc_sold"],.800000001)
        # The holdback is a CAP before day560, not permanently protected.
        result=staged_exit_decision(price,h,day=561,
            sold_original_fraction=.80,
            policy="maturity_90pct_holdback20pct")
        self.assertTrue(result["holdback_can_sell_after_day560"])
        self.assertEqual(result["pre560_sold_cap_original_pct"],80.)

    def test_no_sale_before_day500_or_if_original_btc_already_exhausted(self):
        h=pd.Timestamp("2024-04-20",tz="UTC")
        with self.assertRaisesRegex(ValueError,">=500"):
            staged_exit_decision(self.historical,h,day=499,
                sold_original_fraction=0.)
        no_sale=staged_exit_decision(self.historical,h,day=525,
            sold_original_fraction=1.)
        self.assertEqual(no_sale["fraction_original"],0.)

    def test_historical_regime_never_uses_current_execution_close(self):
        h=pd.Timestamp("2024-04-20",tz="UTC")
        day=h+pd.Timedelta(days=532)
        seen=self.historical.copy()
        orig=staged_exit_decision(seen,h,day=532,
            sold_original_fraction=.05)
        seen.loc[day]=1e9
        later=staged_exit_decision(seen,h,day=532,
            sold_original_fraction=.05)
        self.assertEqual(orig,later)

    def test_2024_halving_day500_is_past_in_real_2026(self):
        state=cycle_exit_stage_status(
            "2024-04-20","2026-10-17")
        self.assertTrue(state["exit_window_expired"])
        self.assertIsNone(state["next_exit_review_date"])
        self.assertTrue(state["historical_context_only"])


class OriginalBudgetRecoveryParity(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.historical=read_exported_history()["price_usd"]

    def test_shared_recovery_fraction_matches_prior_inline_historical(self):
        history=self.historical
        for style in ("adaptive_value","adaptive_recovery"):
            for date in pd.date_range("2019-01-15","2026-04-15",freq="37D",tz="UTC"):
                if date not in history.index:continue
                with self.subTest(style=style,date=str(date.date())):
                    t=int(history.index.get_loc(date))
                    previous=float(history.iloc[t-1])
                    ma=float(history.iloc[t-1-7*np.arange(200)].mean())
                    ratio=previous/ma
                    if style=="adaptive_value":
                        expected=(.10 if ratio<=.85 else
                                  .035 if ratio<=1 else
                                  .12 if ratio<=1.25 else
                                  .04 if ratio<=1.5 else .01)
                    else:
                        recent=float(history.iloc[t-50:t].mean())
                        old=float(history.iloc[t-64:t-14].mean())
                        strong=previous>recent and recent>old
                        expected=(.025 if ratio<=1 else
                                  .15 if ratio<=1.25 and strong else
                                  .045 if ratio<=1.5 else .01)
                    actual=recovery_buy_budget_fraction(
                        history,date,style=style)
                    self.assertAlmostEqual(
                        actual["fraction_of_initial_buyback_cash"],
                        expected,places=12)

    def test_recovery_has_strength_tranche_and_rising_200wma_stage(self):
        idx=pd.date_range("2018-01-01",periods=2400,freq="D",tz="UTC")
        vals=np.full(len(idx),100.,dtype=float)
        vals[-70:]=np.linspace(100,130,70)
        px=pd.Series(vals,index=idx)
        d=idx[-1]
        result=recovery_buy_budget_fraction(
            px,d,style="adaptive_recovery")
        self.assertIn(result["pct_of_initial_buyback_cash"],
                      (2.5,15.,4.5,1.))
        self.assertTrue(result["requires_active_buyback_phase"])

    def test_recovery_uses_no_future_day_and_rejects_missing_week(self):
        price=self.historical.copy()
        date=pd.Timestamp("2025-01-15",tz="UTC")
        a=recovery_buy_budget_fraction(price,date,style="adaptive_recovery")
        price.loc[date]=9e9
        b=recovery_buy_budget_fraction(price,date,style="adaptive_recovery")
        self.assertEqual(a,b)
        price=price.drop(date-pd.Timedelta(days=50))
        with self.assertRaises(ValueError):
            # Explicitly missing weekly-point validation date.
            miss=price.drop(date-pd.Timedelta(days=1))
            recovery_buy_budget_fraction(miss,date,style="adaptive_recovery")


if __name__=="__main__":
    unittest.main()
