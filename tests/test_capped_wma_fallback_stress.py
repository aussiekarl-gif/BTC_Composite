"""One frozen 10% fallback entry, causal price gate and stress invariants."""
import unittest
from unittest.mock import patch
import numpy as np
import pandas as pd

from engines.research.capped_wma_fallback_stress import (
    fallback_fresh_cash_replay,run_fallback_audit,
    FALLBACK_REVIEW_DAYS,FALLBACK_MAX_TOTAL_PCT_ORIGINAL,
)
from engines.research.fresh_cash_200wma_matched_backtest import (
    matched_fresh_cash_replay,
)

START=pd.Timestamp("2020-01-15",tz="UTC")
END=pd.Timestamp("2020-10-10",tz="UTC")


def market(*,trend="flat"):
    idx=pd.date_range(pd.Timestamp("2014-01-01",tz="UTC"),
                      pd.Timestamp("2023-12-31",tz="UTC"),freq="D")
    values=np.full(len(idx),100.,dtype=float)
    if trend=="early_gate":
        values[idx>=START+pd.Timedelta(days=19)]=70.
    if trend=="late_gate":
        values[idx>=START+pd.Timedelta(days=90)]=70.
    if trend=="too_expensive":
        values[idx>=START+pd.Timedelta(days=1)]=200.
    if trend=="crash":
        values[idx>=START+pd.Timedelta(days=90)]=40.
    price=pd.Series(values,index=idx)
    fidx=pd.date_range(idx[0]-pd.Timedelta(days=14),idx[-1],freq="D")
    fx=pd.DataFrame({"aud_per_usd":np.full(len(fidx),1.5)},index=fidx)
    return price,fx


class TenPercentFallbackTests(unittest.TestCase):
    def test_never_buy_before_eight_weeks_or_after_ten_pct_without_gate(self):
        price,fx=market()
        first=fallback_fresh_cash_replay(
            price,fx,start=START,terminal=START+pd.Timedelta(days=55),
            budget_aud=40000)
        self.assertEqual(first["fill_count"],0)
        account=fallback_fresh_cash_replay(
            price,fx,start=START,terminal=END,budget_aud=40000)
        self.assertIsNone(account["original_200wma_gate_date"])
        self.assertEqual(account["fallback_fills"],4)
        self.assertEqual(account["fallback_cash_spent_pct_original"],10.)
        self.assertEqual(account["cash_left_pct"],90.)
        self.assertEqual(len(account["orders"]),4)
        self.assertEqual([pd.Timestamp(x["date"])-START for x in account["orders"]],
                         [pd.Timedelta(days=n) for n in FALLBACK_REVIEW_DAYS])
        self.assertTrue(all(x["kind"]=="limited_starter" for x in account["orders"]))
        self.assertEqual(account["after_gate_fills"],0)
        self.assertLessEqual(account["fallback_cash_spent_pct_original"],
                             FALLBACK_MAX_TOTAL_PCT_ORIGINAL)

    def test_too_high_above_1p5wma_does_not_chase_and_preserves_cash(self):
        price,fx=market(trend="too_expensive")
        candidate=fallback_fresh_cash_replay(
            price,fx,start=START,terminal=END,budget_aud=40000)
        self.assertEqual(candidate["fill_count"],0)
        self.assertEqual(candidate["cash_left_aud"],40000.)
        current=matched_fresh_cash_replay(
            price,fx,start=START,terminal=END,
            policy="current_2p5_remaining_cash_daily",budget_aud=40000.)
        self.assertEqual(current["fill_count"],0)

    def test_early_gate_uses_original_only_and_no_fallback(self):
        price,fx=market(trend="early_gate")
        out=fallback_fresh_cash_replay(
            price,fx,start=START,terminal=END,budget_aud=40000)
        self.assertEqual(out["original_200wma_gate_date"],
                         str((START+pd.Timedelta(days=20)).date()))
        self.assertEqual(out["fallback_fills"],0)
        self.assertGreater(out["after_gate_fills"],0)
        self.assertTrue(all(x["kind"]=="original_after_gate"
                            for x in out["orders"]))
        self.assertAlmostEqual(out["orders"][0]["gross_aud"],1000,places=2)

    def test_late_gate_keeps_starter_history_no_backdating(self):
        price,fx=market(trend="late_gate")
        out=fallback_fresh_cash_replay(
            price,fx,start=START,terminal=END,budget_aud=40000)
        self.assertEqual(out["fallback_fills"],4)
        self.assertEqual(out["fallback_cash_spent_aud"],4000.)
        self.assertGreater(out["after_gate_fills"],1)
        first_gate=START+pd.Timedelta(days=91)
        self.assertEqual(out["original_200wma_gate_date"],
                         str(first_gate.date()))
        before=[x for x in out["orders"] if x["kind"]=="limited_starter"]
        self.assertTrue(all(pd.Timestamp(x["date"],tz="UTC")<first_gate
                            for x in before))

    def test_prefix_no_lookahead_for_prices_and_fx(self):
        p,fx=market(trend="late_gate")
        end=START+pd.Timedelta(days=77)
        a=fallback_fresh_cash_replay(
            p,fx,start=START,terminal=end,budget_aud=40000)
        changed=p.copy()
        changed.loc[changed.index>end]=1e7
        b=fallback_fresh_cash_replay(
            changed,fx,start=START,terminal=end,budget_aud=40000)
        self.assertEqual(a,b)
        full=fallback_fresh_cash_replay(
            p,fx,start=START,terminal=END,budget_aud=40000)
        old=[x for x in full["orders"] if x["date"]<=str(end.date())]
        self.assertEqual(a["orders"],old)

    def test_delayed_crash_risk_is_real_even_with_capped_starter(self):
        p,fx=market(trend="crash")
        end=START+pd.Timedelta(days=101)
        out=fallback_fresh_cash_replay(
            p,fx,start=START,terminal=end,budget_aud=40000)
        current=matched_fresh_cash_replay(
            p,fx,start=START,terminal=end,
            policy="current_2p5_remaining_cash_daily",budget_aud=40000)
        self.assertGreater(out["fallback_cash_spent_aud"],0)
        self.assertGreaterEqual(out["cash_left_aud"],0)
        self.assertGreater(current["after_hypothetical_liquidation_cgt_aud"],0)
        self.assertGreater(out["fill_count"],0)
        # No claim of *outperformance*: the starter BTC immediately loses
        # money if the market falls severely before the 200WMA crossing.
        self.assertLess(out["marked_terminal_aud"],40000.)

    def test_unfunded_cyclic_data_and_invalid_state_fail_closed(self):
        price,fx=market()
        with self.assertRaisesRegex(ValueError,"Invalid funded"):
            fallback_fresh_cash_replay(
                price,fx,start=START,terminal=END,budget_aud=0)
        with self.assertRaisesRegex(ValueError,"Continuous 200WMA"):
            fallback_fresh_cash_replay(
                price.loc["2019-01-01":],fx,start=START,terminal=END,
                budget_aud=40000)
        with self.assertRaisesRegex(ValueError,"Missing ordered"):
            fallback_fresh_cash_replay(
                price,fx,start=END,terminal=START,budget_aud=40000)

    def test_same_cycle_same_synthetic_future_and_equal_cash_comparators(self):
        p,fx=market()
        with patch(
            "engines.research.capped_wma_fallback_stress.PRIMARY",
            {"2017":{"halving":"2016-07-09"}}):
            with patch(
                "engines.research.capped_wma_fallback_stress.OBSERVATION_CUTOFF",
                pd.Timestamp("2023-12-31",tz="UTC")):
                result=run_fallback_audit(
                    {"price_usd":p},
                    fx_fetcher=lambda h,end:fx,
                    cycles=("2017",),starts=(750,),
                    stress_cycles=("2017",),
                    stress_pairs=((750,900),),
                    drops=(.70,),terminals=(.55,))
        self.assertEqual(len(result["historical_matched_entries"]),1)
        self.assertEqual(len(result["synthetic_stress"]),1)
        stress=result["synthetic_stress"][0]
        self.assertTrue(stress["synthetic_not_history"])
        self.assertEqual(set(stress["comparators"]),{
            "forward_original_budget_weekly",
            "current_2p5_remaining_cash_daily",
            "fixed_52_week_equal_cash","immediate_lump_sum",
        })
        self.assertEqual(result["budget_aud"],400000.)
        self.assertGreaterEqual(
            stress["fallback_10pct"]["cash_left_aud"],0.)
        self.assertGreaterEqual(
            stress["fallback_cash_spent_before_forced_low_pct"],0.)
        self.assertLessEqual(
            stress["fallback_cash_spent_before_forced_low_pct"],100.)


if __name__=="__main__":
    unittest.main()
