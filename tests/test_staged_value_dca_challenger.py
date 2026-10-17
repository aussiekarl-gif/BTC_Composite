"""Deterministic guardrails for research-only staged DCA challenger."""
import unittest
import numpy as np
import pandas as pd
from engines.research.staged_value_dca_challenger import (
    START_DAY,candidate_buy_signal,simulate_cash_cohort,
)
from engines.research.cycle_trading_dashboard_model import build_dashboard_market

HALVING=pd.Timestamp("2024-04-20",tz="UTC")


def history(last="2026-10-15",*,profile="down"):
    dates=pd.date_range(pd.Timestamp("2018-01-01",tz="UTC"),pd.Timestamp(last,tz="UTC"),freq="D")
    t=np.arange(len(dates),dtype=float)
    if profile=="down":
        vals=np.maximum(20000.,110000.-24.0*t)
    elif profile=="flat":
        vals=np.full(len(dates),65000.)
    else:
        vals=50000.+np.maximum(0,t-1500)*8.
    return pd.Series(vals,index=dates)


def make_market(price,asof=None):
    date=price.index[-1] if asof is None else pd.Timestamp(asof)
    return build_dashboard_market(
        price.loc[:date],pd.DataFrame(),
        confirmed_halving_date="2024-04-20")


def with_wma(market,ratio):
    x=market.copy()
    x["prior_200wma_usd"]=float(x["previous_close_usd"])/ratio
    x["previous_close_below_200wma"]=ratio<1.
    return x


class StagedResearchTests(unittest.TestCase):
    def test_value_tiers_are_materially_above_existing_two_point_five(self):
        p=history(profile="flat")
        m=make_market(p)
        self.assertEqual(candidate_buy_signal(with_wma(m,.80))["buy_pct_cash"],20.)
        self.assertEqual(candidate_buy_signal(with_wma(m,.92))["buy_pct_cash"],14.)

    def test_drawdown_above_200wma_can_trigger_early_buy(self):
        p=history(profile="flat")
        # Simulated prior 365-day peak followed by lower recent regime.
        p.iloc[-270:-200]=100000.
        m=make_market(p)
        signal=candidate_buy_signal(with_wma(m,1.25))
        self.assertEqual(signal["buy_pct_cash"],3.)
        self.assertIn("early severe drawdown",signal["zone"])
        self.assertFalse(signal["prior_recovery_confirmed"])

    def test_no_early_buy_without_large_drawdown(self):
        p=history(profile="flat")
        m=make_market(p)
        self.assertEqual(candidate_buy_signal(with_wma(m,1.25))["buy_pct_cash"],0.)

    def test_only_yesterday_can_drive_threshold_decision(self):
        p=history(profile="flat")
        p.iloc[-270:-200]=100000.
        m=with_wma(make_market(p),1.25)
        first=candidate_buy_signal(m)
        q=m.copy()
        changed=p.copy()
        changed.iloc[-1]=1e8
        q["price_history"]=changed
        second=candidate_buy_signal(q)
        self.assertEqual(first,second)

    def test_no_negative_cash_or_unbounded_daily_buy_spree(self):
        p=history()
        answer=simulate_cash_cohort(p,halving=HALVING,policy="staged_value_recovery",
                                    asof="2026-10-15",start_day=START_DAY)
        self.assertGreaterEqual(answer["cash_left_usd"],0)
        self.assertLessEqual(answer["cash_deployed_pct"],98.01)
        self.assertTrue(answer["buy_count"]<=80)
        self.assertFalse(answer["complete_window"])
        self.assertIsNone(answer["meets_25pct_target_with_50pct_deployment"])
        self.assertIsNone(answer["meets_20pct_stretch_with_50pct_deployment"])
        if answer["buy_count"]:
            d=[pd.Timestamp(x["date"]) for x in answer["trades"]]
            self.assertTrue(all((b-a).days>=7 for a,b in zip(d,d[1:])))

    def test_baseline_rule_same_signal_two_point_five(self):
        p=history(profile="down")
        answer=simulate_cash_cohort(p,halving=HALVING,policy="current_2p5pct",
                                    asof="2026-10-15")
        if answer["trades"]:
            self.assertEqual(set(x["buy_pct_remaining_cash"] for x in answer["trades"]),{2.5})

    def test_scoring_does_not_expose_future_bottom_to_signal(self):
        p=history(profile="down")
        first=simulate_cash_cohort(p,halving=HALVING,policy="staged_value_recovery",
                                   asof="2026-09-30")
        q=p.copy()
        q.loc[q.index>pd.Timestamp("2026-09-30",tz="UTC")]=1.0
        second=simulate_cash_cohort(q,halving=HALVING,policy="staged_value_recovery",
                                    asof="2026-09-30")
        self.assertEqual(first,second)

    def test_no_fake_success_without_deployment(self):
        p=history(profile="flat")
        a=simulate_cash_cohort(p,halving=HALVING,policy="staged_value_recovery",
                               asof="2026-10-15")
        self.assertEqual(a["buy_count"],0)
        self.assertIsNone(a["meets_20pct_stretch_with_50pct_deployment"])
        self.assertIsNone(a["meets_25pct_target_with_50pct_deployment"])
        self.assertEqual(a["btc_units"],0.)

    def test_reject_bad_policy(self):
        with self.assertRaises(ValueError):
            simulate_cash_cohort(history(),halving=HALVING,policy="tomorrow_knows_bottom")


if __name__=="__main__":
    unittest.main()
