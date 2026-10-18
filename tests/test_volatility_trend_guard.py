"""Frozen BTC prior-volatility/downtrend 200WMA cash-wallet tests."""
import unittest

import numpy as np
import pandas as pd

from engines.research.fresh_cash_200wma_matched_backtest import (
    matched_fresh_cash_replay,
)
from engines.research.volatility_trend_guard import (
    CUTOFF, CAUTIOUS_MULTIPLIER, VOL_ANNUALISED_THRESHOLD,
    lagged_volatility_trend, replay_guarded_cash, compare,
)

START=pd.Timestamp("2020-01-15",tz="UTC")
END=pd.Timestamp("2020-09-01",tz="UTC")


def make_inputs(kind="flat"):
    dates=pd.date_range(pd.Timestamp("2015-01-01",tz="UTC"),
                        pd.Timestamp("2021-04-01",tz="UTC"),freq="D")
    price=pd.Series(100.,index=dates)
    if kind in ("break","volatile_down"):
        price.loc["2020-02-01":]=65.
        if kind=="volatile_down":
            for i,day in enumerate(pd.date_range("2020-02-02","2020-06-30",tz="UTC")):
                price.loc[day]=max(15.,65.-i*.20+(10 if i%2 else -10))
    elif kind=="late_rebound":
        price.loc["2020-02-01":"2020-03-15"]=65.
        price.loc["2020-03-16":]=145.
    elif kind=="flat":
        pass
    else:
        raise ValueError("Unexpected synthetic case")
    fx_dates=pd.date_range(dates[0]-pd.Timedelta(days=12),
                           dates[-1],freq="D")
    fx=pd.DataFrame({"aud_per_usd":1.5},index=fx_dates)
    return price,fx


class GuardedRecoveryTests(unittest.TestCase):
    def test_signal_has_only_64_priors_and_detects_volatile_decline(self):
        price,_=make_inputs("flat")
        day=pd.Timestamp("2020-05-01",tz="UTC")
        previous=pd.date_range(day-pd.Timedelta(days=64),
                               day-pd.Timedelta(days=1),freq="D")
        for i,d in enumerate(previous):
            price.loc[d]=110.-i*.65+(12 if i%2==0 else -12)
        first=lagged_volatility_trend(price,day)
        self.assertTrue(first["downtrend"])
        self.assertGreaterEqual(first["annual_volatility_30d_pct"],
                                100*VOL_ANNUALISED_THRESHOLD)
        self.assertTrue(first["guard_active"])
        copied=price.copy()
        copied.loc[day:]*=10.
        self.assertEqual(first,lagged_volatility_trend(copied,day))
        self.assertTrue(first["uses_only_prior_closes"])

    def test_guard_only_halves_existing_weekly_sizing_not_gate_date(self):
        price,fx=make_inputs("volatile_down")
        base=replay_guarded_cash(price,fx,start=START,terminal=END,
                                budget_aud=40000.,guard=False)
        tested=replay_guarded_cash(price,fx,start=START,terminal=END,
                                  budget_aud=40000.,guard=True)
        self.assertEqual(base["first_200wma_gate"],
                         tested["first_200wma_gate"])
        self.assertGreater(tested["guard_affected_executed_buys"],0)
        bought_days={o["date"] for o in base["orders"]}
        for order in tested["orders"]:
            self.assertIn(order["date"],bought_days)
            if order["guard_active"]:
                self.assertAlmostEqual(
                    order["actual_weekly_pct_budget"],
                    order["original_weekly_pct_budget"]*CAUTIOUS_MULTIPLIER,
                    places=6)
        self.assertGreaterEqual(tested["cash_left_aud"],base["cash_left_aud"])

    def test_independent_existing_plain_matches_original_engine(self):
        price,fx=make_inputs("break")
        normal=replay_guarded_cash(price,fx,start=START,terminal=END,
                                  budget_aud=40000.,guard=False)
        original=matched_fresh_cash_replay(
            price,fx,start=START,terminal=END,
            policy="forward_original_budget_weekly",budget_aud=40000.)
        self.assertEqual(normal["first_200wma_gate"],
                         original["first_valid_200wma_activation_date"])
        for x,y in (("fill_count","fill_count"),
                    ("btc_held","btc_purchased_and_held"),
                    ("cash_left_aud","cash_left_aud"),
                    ("aftertax_liquidation_aud",
                     "after_hypothetical_liquidation_cgt_aud"),
                    ("total_fees_aud","fee_total_aud")):
            self.assertEqual(normal[x],original[y])
        self.assertTrue(normal["no_historical_btc_lots_or_sales"])

    def test_no_cross_no_trades_for_both_policies(self):
        price,fx=make_inputs("flat")
        for guarded in (True,False):
            r=replay_guarded_cash(price,fx,start=START,terminal=END,
                                  guard=guarded,budget_aud=40000.)
            self.assertIsNone(r["first_200wma_gate"])
            self.assertEqual(r["fill_count"],0)
            self.assertEqual(r["aftertax_liquidation_aud"],40000.)
            self.assertEqual(r["cash_left_pct"],100.)

    def test_if_no_trigger_guard_is_identical_during_rebound(self):
        price,fx=make_inputs("late_rebound")
        original=replay_guarded_cash(
            price,fx,start=START,terminal=END,budget_aud=40000.,guard=False)
        guarded=replay_guarded_cash(
            price,fx,start=START,terminal=END,budget_aud=40000.,guard=True)
        self.assertEqual(original["first_200wma_gate"],
                         guarded["first_200wma_gate"])
        if guarded["guard_active_weekly_reviews"]==0:
            self.assertEqual(original["btc_held"],guarded["btc_held"])
            self.assertEqual(original["cash_left_aud"],guarded["cash_left_aud"])

    def test_future_repainting_does_not_change_earlier_fills(self):
        price,fx=make_inputs("volatile_down")
        earlier=pd.Timestamp("2020-05-10",tz="UTC")
        a=replay_guarded_cash(price,fx,start=START,terminal=earlier,
                              guard=True,budget_aud=40000.)
        altered=price.copy()
        altered.loc[altered.index>earlier]*=3.
        b=replay_guarded_cash(altered,fx,start=START,terminal=earlier,
                              guard=True,budget_aud=40000.)
        self.assertEqual(a,b)
        full=replay_guarded_cash(price,fx,start=START,terminal=END,
                                guard=True,budget_aud=40000.)
        self.assertEqual(a["orders"],[
            o for o in full["orders"] if o["date"]<=str(earlier.date())])

    def test_corrupted_price_index_cash_or_fx_fails_closed(self):
        price,fx=make_inputs("break")
        with self.assertRaisesRegex(ValueError,"Continuous"):
            replay_guarded_cash(price.drop(pd.Timestamp(
                "2018-01-15",tz="UTC")),fx,start=START,terminal=END)
        broken=price.copy()
        broken.loc["2020-05-01"]=np.nan
        with self.assertRaisesRegex(ValueError,"Nonfinite"):
            replay_guarded_cash(broken,fx,start=START,terminal=END)
        with self.assertRaisesRegex(ValueError,"Invalid original"):
            replay_guarded_cash(price,fx,start=START,terminal=END,
                                budget_aud=0)
        with self.assertRaisesRegex(ValueError,"explicit Boolean"):
            replay_guarded_cash(price,fx,start=START,terminal=END,guard="yes")
        with self.assertRaisesRegex(ValueError,"No safely prior"):
            replay_guarded_cash(price,fx.loc[:"2020-02-01"],
                                start=START,terminal=END)
        with self.assertRaisesRegex(ValueError,"64 exact prior"):
            lagged_volatility_trend(price.loc["2020-04-20":],
                                    pd.Timestamp("2020-05-01",tz="UTC"))

    def test_default_four_benchmark_comparison_all_accounting_matches(self):
        price,fx=make_inputs("volatile_down")
        result=compare(price,fx,start=START,terminal=END)
        self.assertIn("guard_vs_original_aftertax_pct",result)
        self.assertIn("guard_vs_current_daily_aftertax_pct",result)
        self.assertEqual(result["guard"]["initial_cash_aud"],400000.)
        self.assertEqual(result["first_gate"],
                         result["benchmarks"][
                             "forward_original_budget_weekly"][
                                 "first_valid_200wma_activation_date"])


if __name__=="__main__":
    unittest.main()
