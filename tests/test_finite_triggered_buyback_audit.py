"""Regress finite 24/52 trade buyback hypotheses against unchanged live BUY."""
import unittest
import numpy as np
import pandas as pd

from engines.research.live_cycle_self_financing_roundtrip import (
    BUY_STYLES,simulate_full_roundtrip,day,
)
from engines.research.finite_triggered_buyback_audit import (
    compare_buyback_modes,
)

H=pd.Timestamp("2018-01-01",tz="UTC")
E=H+pd.Timedelta(days=1150)


def setup_prices(mode="deep"):
    dates=pd.date_range("2013-01-01","2024-01-01",freq="D",tz="UTC")
    p=pd.Series(100.,index=dates,dtype=float)
    p.loc[H+pd.Timedelta(days=450):]=240.
    if mode=="deep":
        p.loc[H+pd.Timedelta(days=900):]=70.
    elif mode=="fast_rebound":
        p.loc[H+pd.Timedelta(days=900):
              H+pd.Timedelta(days=928)]=70.
        p.loc[H+pd.Timedelta(days=929):]=240.
    elif mode=="no_gate":
        pass
    else:
        raise ValueError(mode)
    fx=pd.DataFrame({"aud_per_usd":np.full(len(dates),1.5)},
                    index=dates)
    return p,fx


class FiniteTriggeredBuybackTests(unittest.TestCase):
    def test_existing_default_is_same_explicit_original_2p5(self):
        px,fx=setup_prices("fast_rebound")
        a=simulate_full_roundtrip(
            px,fx,halving=H,terminal=E,starting_cash=40000.)
        b=simulate_full_roundtrip(
            px,fx,halving=H,terminal=E,starting_cash=40000.,
            buyback_mode=BUY_STYLES[0])
        self.assertEqual(a,b)
        self.assertFalse(a["finite_plan_can_buy_above_wma_after_original_first_gate"])

    def test_no_initial_200wma_gate_means_no_cash_reinvestment(self):
        px,fx=setup_prices("no_gate")
        for mode in BUY_STYLES:
            r=simulate_full_roundtrip(px,fx,halving=H,terminal=E,
                    starting_cash=40000.,buyback_mode=mode)
            self.assertEqual(r["accounts"]["buy_and_hold"][
                "actual_buyback_orders"],0)
            self.assertTrue(all(
                x["actual_buyback_orders"]==0
                for x in r["accounts"].values()))
            for v in r["accounts"].values():
                self.assertIsNone(v["first_200wma_funded_buyback_trigger"])

    def test_finite24_must_first_buy_on_original_watch_and_never_leverage(self):
        px,fx=setup_prices("deep")
        r=simulate_full_roundtrip(
            px,fx,halving=H,terminal=E,starting_cash=40000.,
            buyback_mode=BUY_STYLES[1])
        self.assertTrue(r["finite_plan_can_buy_above_wma_after_original_first_gate"])
        for name,acct in r["accounts"].items():
            buys=[o for o in acct["dated_orders"] if o["side"]=="BUY"]
            self.assertLessEqual(len(buys),24)
            self.assertGreaterEqual(acct["cash_remaining_aud"],0.)
            self.assertGreaterEqual(acct["btc_left_after_buybacks"],0.)
            if buys:
                self.assertEqual(buys[0]["signal_origin"],
                                 "initial_original_200wma_watch")
                self.assertEqual(acct["first_200wma_funded_buyback_trigger"],
                                 buys[0]["date"])
                for t in buys[1:]:
                    self.assertEqual(t["signal_origin"],
                                     "planned_weekly_reinvestment")
                self.assertTrue(any(o["side"]=="SELL" for o in acct["dated_orders"]))
                self.assertTrue(all((day(b["date"])-day(a["date"])).days>=7
                    for a,b in zip(acct["dated_orders"],acct["dated_orders"][1:])))
        self.assertEqual(
            r["accounts"]["research_original_btc_90pct"]["actual_buyback_orders"],24)

    def test_weekly_buyback_can_continue_above_200wma_after_funded_first_gate(self):
        px,fx=setup_prices("fast_rebound")
        original=simulate_full_roundtrip(
            px,fx,halving=H,terminal=E,starting_cash=40000.)
        planned=simulate_full_roundtrip(
            px,fx,halving=H,terminal=E,starting_cash=40000.,
            buyback_mode=BUY_STYLES[1])
        base=original["accounts"]["research_original_btc_90pct"]
        alt=planned["accounts"]["research_original_btc_90pct"]
        self.assertGreater(alt["actual_buyback_orders"],
                           base["actual_buyback_orders"])
        self.assertLess(alt["cash_remaining_aud"],base["cash_remaining_aud"])
        later=[o for o in alt["dated_orders"] if o["side"]=="BUY"
               and day(o["date"])>H+pd.Timedelta(days=929)]
        self.assertTrue(later)
        self.assertTrue(all(o["signal_origin"]=="planned_weekly_reinvestment"
                            for o in later))

    def test_52_week_cannot_redeem_future_unavailable_cash(self):
        px,fx=setup_prices("deep")
        r=simulate_full_roundtrip(
            px,fx,halving=H,terminal=E,starting_cash=40000.,
            buyback_mode=BUY_STYLES[2],weekday_only=True)
        self.assertTrue(r["weekday_only_BTC_AUD_proxy"])
        for acct in r["accounts"].values():
            self.assertLessEqual(acct["actual_buyback_orders"],52)
            self.assertGreaterEqual(acct["cash_remaining_aud"],0.)
            self.assertTrue(all(day(x["date"]).weekday()<5
                                for x in acct["dated_orders"]))

    def test_same_sell_policy_cash_and_btc_origins_matched_across_modes(self):
        px,fx=setup_prices("deep")
        all_rows=compare_buyback_modes(px,fx,halving=H,terminal=E,
                           cycle="synthetic",case="test",weekday_only=False)
        self.assertEqual(len(all_rows),5*3)
        for name in sorted({x["SELL_strategy"] for x in all_rows}):
            matches=[x for x in all_rows if x["SELL_strategy"]==name]
            self.assertEqual([x["BUYBACK_strategy"] for x in matches],
                             list(BUY_STYLES))
            self.assertEqual(len({x["original_position_BTC"]
                                  for x in matches}),1)
            self.assertEqual(matches[0]["terminal_aftertax_AUD_vs_live_buyback_pct"],0.)
            self.assertEqual(matches[0]["BTC_equivalent_vs_live_buyback_pct"],0.)

    def test_prices_after_early_terminal_do_not_rewrite_completed_buys(self):
        px,fx=setup_prices("deep")
        early=H+pd.Timedelta(days=975)
        for mode in BUY_STYLES:
            r=simulate_full_roundtrip(
                px,fx,halving=H,terminal=early,
                starting_cash=40000.,buyback_mode=mode)
            other=px.copy()
            other.loc[other.index>early]*=9.
            changed=simulate_full_roundtrip(
                other,fx,halving=H,terminal=early,
                starting_cash=40000.,buyback_mode=mode)
            self.assertEqual(r,changed)

    def test_invalid_mode_fails_without_fallback(self):
        px,fx=setup_prices("deep")
        with self.assertRaisesRegex(ValueError,"buyback policy"):
            simulate_full_roundtrip(px,fx,halving=H,terminal=E,
                                    buyback_mode="any future low")
        with self.assertRaisesRegex(ValueError,"No safely prior"):
            simulate_full_roundtrip(px,fx.loc[:"2018-02-01"],halving=H,
                                    terminal=E,buyback_mode=BUY_STYLES[1])


if __name__=="__main__":
    unittest.main()
