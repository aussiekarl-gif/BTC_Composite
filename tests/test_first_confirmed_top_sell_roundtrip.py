"""First confirmed mature top one-tranche sell: causal matched-wallet tests."""
import copy
import unittest

import numpy as np
import pandas as pd

from engines.research.first_confirmed_top_sell_roundtrip import (
    compile_sell_plan,chronological_sell_rebuy,
    PREDECLARED_ACCELERATOR_FRACTION_ORIGINAL,
)
from engines.research.cycle_chronological_wallet import (
    replay_chronological_wallet,
)

H=pd.Timestamp("2016-07-09",tz="UTC")
END=H+pd.Timedelta(days=840)


def sample():
    ix=pd.date_range("2012-01-01","2020-01-01",tz="UTC",freq="D")
    values=np.full(len(ix),100.,dtype=float)
    # Pre-high original sell regime; then actual below WMA after day780.
    values[(ix>=H+pd.Timedelta(days=490))&
           (ix<H+pd.Timedelta(days=560))]=180.
    values[(ix>=H+pd.Timedelta(days=560))&
           (ix<H+pd.Timedelta(days=780))]=140.
    values[ix>=H+pd.Timedelta(days=780)]=60.
    price=pd.Series(values,index=ix)
    fx=pd.DataFrame({"aud_per_usd":np.full(len(ix),1.5)},index=ix)
    alerts=pd.Series(False,index=ix)
    return price,fx,alerts


def flag(alert,day):
    c=alert.copy()
    c.loc[H+pd.Timedelta(days=day)]=True
    return c


class FirstConfirmedSellTests(unittest.TestCase):
    def test_frozen_baseline_sell_buy_wallet_parity(self):
        p,fx,a=sample()
        first=chronological_sell_rebuy(p,fx,a,H,END,candidate=False)
        known=replay_chronological_wallet(p,fx,H,END)
        self.assertAlmostEqual(
            first["after_hypothetical_liquidation_cgt_aud"],
            known["after_hypothetical_liquidation_cgt_aud"],places=2)
        self.assertEqual(first["first_wma_buy_activation_date"],
                         known["buyback_activation_date"])
        self.assertEqual(first["sell_count"],known["sell_count"])
        self.assertEqual(first["buy_count"],known["buyback_count"])

    def test_first_fresh_alert_not_latest_near_peak(self):
        p,fx,a=sample()
        a=flag(a,505)
        a=flag(a,610)
        plan=compile_sell_plan(p,a,H,END,candidate=True)
        self.assertEqual(plan["first_fresh_confirmation_date"],
                         str((H+pd.Timedelta(days=505)).date()))
        extra=[x for x in plan["sell_decisions"]
               if x["reason"]=="first_maturity_confirmed_reversal"]
        self.assertEqual(len(extra),1)
        self.assertLessEqual(extra[0]["fraction_original"],
                             PREDECLARED_ACCELERATOR_FRACTION_ORIGINAL)
        self.assertLessEqual(plan["fraction_original_scheduled"],1.)

    def test_alert_at_499_does_not_become_fresh_day500(self):
        p,_,a=sample()
        for i in range(498,502):
            a.loc[H+pd.Timedelta(days=i)]=True
        out=compile_sell_plan(p,a,H,END,candidate=True)
        self.assertIsNone(out["first_fresh_confirmation_date"])
        self.assertFalse(out["confirmation_seen_during_window"])

    def test_alert_at_731_is_too_late_and_not_backdated(self):
        p,_,a=sample()
        plan=compile_sell_plan(p,flag(a,731),H,END,candidate=True)
        control=compile_sell_plan(p,a,H,END,candidate=False)
        self.assertEqual(plan["sell_decisions"],control["sell_decisions"])
        self.assertIsNone(plan["first_fresh_confirmation_date"])

    def test_no_warning_is_identical_to_original_aftertax_with_delays(self):
        p,fx,a=sample()
        for lag in (0,1,3,7):
            first=chronological_sell_rebuy(
                p,fx,a,H,END,candidate=False,sale_delay_days=lag)
            challenger=chronological_sell_rebuy(
                p,fx,a,H,END,candidate=True,sale_delay_days=lag)
            for k in ("after_hypothetical_liquidation_cgt_aud",
                      "btc_end","cash_end_aud","buy_count","sell_count",
                      "estimated_cgt_paid_during_roundtrip_aud"):
                self.assertEqual(first[k],challenger[k])
            self.assertEqual(challenger["fraction_original_sold"],
                             first["fraction_original_sold"])

    def test_delay_never_moves_indicator_decision_date(self):
        p,fx,a=sample()
        a=flag(a,501)
        early=chronological_sell_rebuy(
            p,fx,a,H,END,candidate=True,sale_delay_days=0)
        delayed=chronological_sell_rebuy(
            p,fx,a,H,END,candidate=True,sale_delay_days=3)
        d=str((H+pd.Timedelta(days=501)).date())
        self.assertEqual(early["first_fresh_confirmation_date"],d)
        self.assertEqual(delayed["first_fresh_confirmation_date"],d)
        extra=[x for x in delayed["executed_sells"]
               if x["reason"]=="first_maturity_confirmed_reversal"]
        self.assertEqual(len(extra),1)
        self.assertEqual(extra[0]["decision_date"],d)
        self.assertEqual(extra[0]["execution_date"],
                         str((H+pd.Timedelta(days=504)).date()))
        self.assertLessEqual(delayed["fraction_original_sold"],1.)
        self.assertEqual(delayed["first_wma_buy_activation_date"],
                         early["first_wma_buy_activation_date"])

    def test_historical_future_prices_do_not_rewrite_prior_plan(self):
        p,fx,a=sample()
        endpoint=H+pd.Timedelta(days=620)
        flagday=H+pd.Timedelta(days=500)
        a.loc[flagday]=True
        before=compile_sell_plan(
            p.loc[:endpoint],a.loc[:endpoint],H,endpoint,candidate=True)
        p2=p.copy()
        p2.loc[p2.index>endpoint]=999999.
        a2=a.copy()
        a2.loc[a2.index>endpoint]=~a2.loc[a2.index>endpoint]
        after=compile_sell_plan(
            p2,a2,H,endpoint,candidate=True)
        self.assertEqual(before,after)

    def test_cannot_use_missing_or_invalid_daily_prices(self):
        p,fx,a=sample()
        p=p.drop(H+pd.Timedelta(days=600))
        with self.assertRaisesRegex(ValueError,"Missing daily"):
            compile_sell_plan(p,a,H,END,candidate=True)
        p,fx,a=sample()
        with self.assertRaisesRegex(ValueError,"Unexpected"):
            chronological_sell_rebuy(
                p,fx,a,H,END,candidate=True,sale_delay_days=365)

    def test_no_borrowing_btc_and_cgt_after_predeclared_selling(self):
        p,fx,a=sample()
        a=flag(a,501)
        a=flag(a,600)
        out=chronological_sell_rebuy(
            p,fx,a,H,END,candidate=True)
        self.assertGreater(out["after_hypothetical_liquidation_cgt_aud"],0.)
        self.assertGreaterEqual(out["cash_end_aud"],0.)
        self.assertGreaterEqual(out["btc_end"],0.)
        self.assertLessEqual(out["fraction_original_sold"],1.)
        self.assertLessEqual(out["first_fresh_confirmation_date"],
                             str((H+pd.Timedelta(days=600)).date()))


if __name__=="__main__":
    unittest.main()
