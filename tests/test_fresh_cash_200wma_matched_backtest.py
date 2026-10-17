"""Matched 2026-style cash-only DCA: causal timing and self-financing tests."""
import copy
import unittest

import numpy as np
import pandas as pd

from engines.research.fresh_cash_200wma_matched_backtest import (
    POLICIES,matched_fresh_cash_replay,evaluate_fresh_cash_matched_starts,
)

START=pd.Timestamp("2020-01-15",tz="UTC")
END=pd.Timestamp("2020-11-15",tz="UTC")


def synthetic(*,drop=True,rise=True):
    dates=pd.date_range(pd.Timestamp("2015-01-01",tz="UTC"),
                        pd.Timestamp("2021-04-01",tz="UTC"),freq="D")
    prices=pd.Series(np.full(len(dates),100.),index=dates)
    if drop:
        prices.loc[prices.index>=pd.Timestamp("2020-02-01",tz="UTC")]=65.
        if rise:
            prices.loc[prices.index>=pd.Timestamp("2020-05-01",tz="UTC")]=125.
    fx_dates=pd.date_range(dates[0]-pd.Timedelta(days=8),
                           dates[-1],freq="D")
    fx=pd.DataFrame({"aud_per_usd":np.full(len(fx_dates),1.5)},index=fx_dates)
    return prices,fx


class MatchedFreshCashTests(unittest.TestCase):
    def test_equal_initial_cash_and_frozen_original_weekly_allocation(self):
        price,fx=synthetic()
        results={
            name:matched_fresh_cash_replay(
                price,fx,start=START,terminal=END,policy=name,budget_aud=40000.)
            for name in POLICIES
        }
        for r in results.values():
            self.assertEqual(r["initial_cash_aud"],40000.)
            self.assertTrue(r["no_legacy_sell_or_historical_btc"])
            self.assertGreaterEqual(r["cash_left_aud"],0)
            self.assertGreaterEqual(r["btc_purchased_and_held"],0)
            self.assertGreater(
                r["after_hypothetical_liquidation_cgt_aud"],0.)
        staged=results["forward_original_budget_weekly"]
        self.assertEqual(staged["first_valid_200wma_activation_date"],"2020-02-02")
        self.assertTrue(staged["orders"])
        self.assertEqual(staged["orders"][0]["pct_original_budget"],2.5)
        self.assertAlmostEqual(staged["orders"][0]["gross_aud"],1000.,places=2)
        self.assertEqual(staged["orders"][0]["date"],"2020-02-02")
        remaining=results["current_2p5_remaining_cash_daily"]
        self.assertTrue(
            all(pd.Timestamp(v["date"],tz="UTC")>=
                pd.Timestamp("2020-02-02",tz="UTC")
                for v in remaining["orders"])
        )
        self.assertEqual(results["immediate_lump_sum"]["fill_count"],1)
        self.assertEqual(
            results["immediate_lump_sum"]["orders"][0]["date"],"2020-01-16")

    def test_no_below_wma_crossing_keeps_both_gate_models_in_cash(self):
        price,fx=synthetic(drop=False)
        for name in ("forward_original_budget_weekly",
                     "current_2p5_remaining_cash_daily"):
            r=matched_fresh_cash_replay(
                price,fx,start=START,terminal=END,policy=name,budget_aud=40000.)
            self.assertEqual(r["fill_count"],0)
            self.assertEqual(r["btc_purchased_and_held"],0.)
            self.assertEqual(r["cash_left_pct"],100.)
            self.assertEqual(r["after_hypothetical_liquidation_cgt_aud"],40000.)
            self.assertIsNone(r["average_buy_error_above_observed_future_low_pct"])
        lump=matched_fresh_cash_replay(
            price,fx,start=START,terminal=END,
            policy="immediate_lump_sum",budget_aud=40000.)
        self.assertGreater(lump["btc_purchased_and_held"],0)

    def test_future_prices_cannot_change_earlier_completed_trades(self):
        price,fx=synthetic()
        cutoff=pd.Timestamp("2020-04-01",tz="UTC")
        later=price.copy()
        later.loc[later.index>cutoff]=1e8
        for name in POLICIES:
            a=matched_fresh_cash_replay(
                price,fx,start=START,terminal=cutoff,policy=name,budget_aud=40000.)
            b=matched_fresh_cash_replay(
                later,fx,start=START,terminal=cutoff,policy=name,budget_aud=40000.)
            self.assertEqual(a,b)

    def test_terminal_extension_does_not_change_prior_buy_ledger(self):
        price,fx=synthetic()
        earlier=pd.Timestamp("2020-03-31",tz="UTC")
        for name in POLICIES:
            a=matched_fresh_cash_replay(
                price,fx,start=START,terminal=earlier,
                policy=name,budget_aud=40000.)
            b=matched_fresh_cash_replay(
                price,fx,start=START,terminal=END,
                policy=name,budget_aud=40000.)
            early_orders=[v for v in b["orders"]
                          if v["date"]<=str(earlier.date())]
            self.assertEqual(a["orders"],early_orders)

    def test_gates_use_prior_completed_price_not_today_price(self):
        price,fx=synthetic()
        trigger=pd.Timestamp("2020-02-02",tz="UTC")
        # A new low on Feb 1 drives Feb 2 purchase, NOT Feb 1 purchase.
        staged=matched_fresh_cash_replay(
            price,fx,start=START,terminal=trigger,
            policy="forward_original_budget_weekly",budget_aud=40000.)
        self.assertEqual(staged["orders"][0]["date"],"2020-02-02")
        live=matched_fresh_cash_replay(
            price,fx,start=START,terminal=trigger,
            policy="current_2p5_remaining_cash_daily",budget_aud=40000.)
        self.assertEqual(live["orders"][0]["date"],"2020-02-02")

    def test_missing_exact_weekly_history_or_fx_fails_closed(self):
        price,fx=synthetic()
        corrupted=price.drop(pd.Timestamp("2018-01-20",tz="UTC"))
        with self.assertRaisesRegex(ValueError,"Missing continuous"):
            matched_fresh_cash_replay(corrupted,fx,start=START,terminal=END,
                policy="forward_original_budget_weekly",budget_aud=40000.)
        fx=fx.loc[:pd.Timestamp("2020-02-02",tz="UTC")]
        with self.assertRaisesRegex(ValueError,"No safely prior"):
            matched_fresh_cash_replay(price,fx,start=START,terminal=END,
                policy="forward_original_budget_weekly",budget_aud=40000.)

    def test_initial_budget_and_unknown_policy_fail_closed(self):
        price,fx=synthetic()
        with self.assertRaisesRegex(ValueError,"Unknown fresh cash"):
            matched_fresh_cash_replay(price,fx,start=START,terminal=END,
                policy="latest_secret_model",budget_aud=40000.)
        with self.assertRaisesRegex(ValueError,"Invalid initial cash"):
            matched_fresh_cash_replay(price,fx,start=START,terminal=END,
                policy=POLICIES[0],budget_aud=0)
        with self.assertRaisesRegex(ValueError,"Start and terminal"):
            matched_fresh_cash_replay(price,fx,start=END,terminal=END,
                policy=POLICIES[0],budget_aud=40000.)

    def test_four_way_equal_start_cohort_is_right_censored_when_incomplete(self):
        price,fx=synthetic()
        from unittest.mock import patch
        from engines.research.fresh_cash_200wma_matched_backtest import PRIMARY
        with patch.dict(PRIMARY,{"2025":{"halving":"2020-01-01"}},clear=True):
            history={"price_usd":price}
            results=evaluate_fresh_cash_matched_starts(
                history,fx_fetcher=lambda _h,_e:fx,
                start_days=(50,180),cycles=("2025",),budget_aud=40000.)
        self.assertEqual(len(results["cohorts"]),2)
        for row in results["cohorts"]:
            self.assertFalse(row["complete_score_window"])
            self.assertEqual(set(row["variants"]),set(POLICIES))
            self.assertIn("aftertax_forward_vs_current_live_buy_pct",row)
            self.assertEqual(len(row["trade_audit"]),4)
            self.assertTrue(
                row["variants"]["forward_original_budget_weekly"][
                    "cash_left_aud"]>=0
            )


if __name__=="__main__":
    unittest.main()
