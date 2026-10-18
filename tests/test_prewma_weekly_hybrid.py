"""Causal frozen 1%-weekly/10%-cap pre-200WMA hybrid execution tests."""
import unittest

import numpy as np
import pandas as pd

from engines.research.fresh_cash_200wma_matched_backtest import (
    matched_fresh_cash_replay,
)
from engines.research.prewma_weekly_hybrid import (
    replay_capped_pre_gate_hybrid, comparison,
)

START=pd.Timestamp("2020-01-15",tz="UTC")
END=pd.Timestamp("2020-06-15",tz="UTC")


def market(*,variant="flat"):
    dates=pd.date_range(pd.Timestamp("2015-01-01",tz="UTC"),
                        pd.Timestamp("2021-04-01",tz="UTC"),freq="D")
    price=pd.Series(100.,index=dates)
    if variant=="first_gate":
        price.loc[START:]=65.
    elif variant=="later_gate":
        price.loc[START+pd.Timedelta(days=80):]=60.
    elif variant=="shallow_rise":
        for i in range(1,240):
            date=START+pd.Timedelta(days=i)
            price.loc[date]=100.*(1+.25*i/239)
        price.loc[START+pd.Timedelta(days=240):]=125.
    elif variant=="late_end_crash":
        # A drop only at terminal cannot retroactively create a prior
        # 200WMA signal on that same day.
        price.loc[END]=50.
    elif variant!="flat":
        raise ValueError("Unknown test fixture")
    fx_index=pd.date_range(dates[0]-pd.Timedelta(days=10),
                           dates[-1],freq="D")
    fx=pd.DataFrame({"aud_per_usd":1.5},index=fx_index)
    return price,fx


class PreWmaWeeklyHybridTests(unittest.TestCase):
    def test_flat_no_gate_uses_only_ten_percent_without_chasing(self):
        prices,fx=market()
        end=START+pd.Timedelta(days=105)
        r=replay_capped_pre_gate_hybrid(
            prices,fx,start=START,terminal=end,budget_aud=40000.)
        self.assertIsNone(r["first_wma_gate_date"])
        self.assertEqual(r["pre_gate_fills"],10)
        self.assertEqual(r["post_gate_fills"],0)
        self.assertEqual(r["pre_gate_gross_aud"],4000.)
        self.assertEqual(r["pre_gate_spent_pct_original"],10.)
        self.assertEqual(r["cash_left_pct"],90.)
        self.assertTrue(all(x["mode"]=="capped_pre_gate"
                            for x in r["orders"]))
        self.assertEqual(r["orders"][0]["date"],"2020-01-16")
        self.assertTrue(r["research_only"])
        self.assertFalse(r["live_ibit_parity_verified"])

    def test_first_day_below_gate_excludes_starter_and_matches_original(self):
        prices,fx=market(variant="first_gate")
        h=replay_capped_pre_gate_hybrid(
            prices,fx,start=START,terminal=END,budget_aud=40000.)
        orig=matched_fresh_cash_replay(
            prices,fx,start=START,terminal=END,
            policy="forward_original_budget_weekly",budget_aud=40000.)
        self.assertEqual(h["first_wma_gate_date"],"2020-01-16")
        self.assertEqual(h["pre_gate_fills"],0)
        self.assertEqual(h["orders"][0]["mode"],"unchanged_post_gate")
        self.assertEqual(h["orders"][0]["gross_aud"],1000.)
        self.assertEqual(h["btc_purchased_and_held"],
                         orig["btc_purchased_and_held"])
        self.assertEqual(h["cash_left_aud"],orig["cash_left_aud"])
        self.assertEqual(h["ending_after_illustrative_cgt_aud"],
                         orig["after_hypothetical_liquidation_cgt_aud"])

    def test_later_gate_stops_starter_and_uses_identical_original_recovery(self):
        prices,fx=market(variant="later_gate")
        out=replay_capped_pre_gate_hybrid(
            prices,fx,start=START,terminal=END,budget_aud=40000.)
        self.assertEqual(out["pre_gate_fills"],10)
        self.assertEqual(out["pre_gate_gross_aud"],4000.)
        self.assertEqual(out["first_wma_gate_date"],
                         str((START+pd.Timedelta(days=81)).date()))
        self.assertTrue(out["post_gate_fills"])
        first=next(x for x in out["orders"]
                   if x["mode"]=="unchanged_post_gate")
        self.assertEqual(first["date"],out["first_wma_gate_date"])
        self.assertEqual(first["gross_aud"],1000.)
        self.assertTrue(all(pd.Timestamp(o["date"],tz="UTC")<
                            pd.Timestamp(out["first_wma_gate_date"],tz="UTC")
                            for o in out["orders"]
                            if o["mode"]=="capped_pre_gate"))

    def test_no_gate_rising_market_has_measured_opportunity_benefit(self):
        prices,fx=market(variant="shallow_rise")
        h=comparison(prices,fx,start=START,terminal=END)
        self.assertIsNone(h["first_gate"])
        self.assertEqual(h["pre_gate_spent_pct"],10.)
        self.assertGreater(h["hybrid_vs_original_pct"],0)
        self.assertEqual(h["original_aftertax_aud"],400000.)
        self.assertGreater(h["hybrid_btc"],0.)

    def test_no_gate_terminal_crash_exposes_opposite_downside(self):
        prices,fx=market(variant="late_end_crash")
        h=comparison(prices,fx,start=START,terminal=END)
        self.assertIsNone(h["first_gate"])
        self.assertEqual(h["original_aftertax_aud"],400000.)
        self.assertLess(h["hybrid_vs_original_pct"],0)
        self.assertGreater(h["pre_gate_spent_pct"],0.)
        self.assertGreater(h["hybrid_cash_pct"],80.)

    def test_prefix_invariance_no_future_prices_or_fx_in_past_orders(self):
        prices,fx=market(variant="later_gate")
        early=START+pd.Timedelta(days=60)
        a=replay_capped_pre_gate_hybrid(
            prices,fx,start=START,terminal=early,budget_aud=40000.)
        changed=prices.copy()
        changed.loc[changed.index>early]*=4.
        b=replay_capped_pre_gate_hybrid(
            changed,fx,start=START,terminal=early,budget_aud=40000.)
        self.assertEqual(a,b)
        long=replay_capped_pre_gate_hybrid(
            prices,fx,start=START,terminal=END,budget_aud=40000.)
        self.assertEqual(a["orders"],
                         [x for x in long["orders"] if x["date"]<=str(early.date())])

    def test_missing_price_bad_cash_and_missing_fx_fail_closed(self):
        prices,fx=market()
        missing=prices.drop(pd.Timestamp("2018-03-01",tz="UTC"))
        with self.assertRaisesRegex(ValueError,"Missing continuous"):
            replay_capped_pre_gate_hybrid(
                missing,fx,start=START,terminal=END)
        corrupt=prices.copy()
        corrupt.loc["2020-02-01"]=np.nan
        with self.assertRaisesRegex(ValueError,"nonfinite"):
            replay_capped_pre_gate_hybrid(
                corrupt,fx,start=START,terminal=END)
        with self.assertRaisesRegex(ValueError,"Invalid cash"):
            replay_capped_pre_gate_hybrid(
                prices,fx,start=START,terminal=END,budget_aud=0)
        with self.assertRaisesRegex(ValueError,"Invalid chronological"):
            replay_capped_pre_gate_hybrid(
                prices,fx,start=END,terminal=END)
        with self.assertRaisesRegex(ValueError,"No safely prior"):
            replay_capped_pre_gate_hybrid(
                prices,fx.loc[:"2020-01-17"],start=START,terminal=END)

    def test_matched_comparison_checks_same_200wma_gate(self):
        prices,fx=market(variant="later_gate")
        r=comparison(prices,fx,start=START,terminal=END)
        self.assertEqual(r["first_gate"],
                         str((START+pd.Timedelta(days=81)).date()))
        self.assertIn("hybrid_vs_current_daily_pct",r)
        self.assertIn("hybrid_vs_lump_pct",r)
        self.assertLessEqual(r["pre_gate_spent_pct"],10.)


if __name__=="__main__":
    unittest.main()
