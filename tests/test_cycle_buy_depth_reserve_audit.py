"""Causal reserve-for-deeper-200WMA BUY experiment safety invariants."""
import unittest

import numpy as np
import pandas as pd

from engines.research.cycle_buy_depth_reserve_audit import (
    replay_buy_reserve,RESERVE_FRACTION,DEEP_DISCOUNT_WMA_RATIO,
    _matched_pair,
)
from engines.research.cycle_chronological_wallet import (
    replay_chronological_wallet,
)

H=pd.Timestamp("2016-07-09",tz="UTC")
END=H+pd.Timedelta(days=920)


def market(*,deep=True):
    ix=pd.date_range("2012-01-01","2020-01-01",tz="UTC",freq="D")
    v=np.full(len(ix),100.,dtype=float)
    # Initial 200WMA entry after 770 without deep discount.
    v[ix>=H+pd.Timedelta(days=770)]=95.
    if deep:
        v[ix>=H+pd.Timedelta(days=850)]=70.
    p=pd.Series(v,index=ix)
    fx=pd.DataFrame({"aud_per_usd":np.full(len(ix),1.5)},index=ix)
    return p,fx


class DepthReserveWalletTests(unittest.TestCase):
    def test_unmodified_original_replay_parity_of_aftertax_wallet(self):
        p,fx=market()
        x=replay_buy_reserve(p,fx,H,END,reserve_policy=False)
        original=replay_chronological_wallet(p,fx,H,END)
        self.assertEqual(x["after_hypothetical_liquidation_cgt_aud"],
                         original["after_hypothetical_liquidation_cgt_aud"])
        self.assertEqual(x["cash_end_aud"],original["cash_remaining_aud"])
        self.assertEqual(x["btc_end"],original["btc_held"])
        self.assertEqual(x["buy_200wma_activation_date"],
                         original["buyback_activation_date"])
        self.assertEqual(x["sell_count"],original["sell_count"])
        self.assertEqual(x["buy_count"],original["buyback_count"])

    def test_reserve_frozen_till_weekly_deep_discount_then_latches_open(self):
        p,fx=market(deep=True)
        t=H+pd.Timedelta(days=839)
        short=replay_buy_reserve(p,fx,H,t,reserve_policy=True)
        standard=replay_buy_reserve(p,fx,H,t,reserve_policy=False)
        self.assertFalse(short["reserved_cash_unlocked"])
        self.assertIsNone(short["first_weekly_deep_discount_date"])
        self.assertEqual(short["buy_200wma_activation_date"],
                         standard["buy_200wma_activation_date"])
        self.assertGreater(short["cash_end_aud"],standard["cash_end_aud"])
        self.assertLess(short["buy_budget_deployed_pct"],
                        standard["buy_budget_deployed_pct"])
        full=replay_buy_reserve(p,fx,H,END,reserve_policy=True)
        self.assertTrue(full["reserved_cash_unlocked"])
        self.assertIsNotNone(full["first_weekly_deep_discount_date"])
        self.assertEqual(full["reserved_fraction_of_initial_cash"],50.)
        self.assertGreater(len(full["executed_buys"]),0)
        self.assertTrue(any(not b["reserved_tranche_locked"]
                            for b in full["executed_buys"]))

    def test_no_deep_discount_means_cash_reserve_not_magically_deployed(self):
        p,fx=market(deep=False)
        x=replay_buy_reserve(p,fx,H,END,reserve_policy=True)
        y=replay_buy_reserve(p,fx,H,END,reserve_policy=False)
        self.assertFalse(x["reserved_cash_unlocked"])
        self.assertGreater(x["cash_end_aud"],y["cash_end_aud"])
        self.assertLess(x["buy_count"]+1,500)
        self.assertGreater(x["initial_aftertax_buyback_budget_aud"],0)
        self.assertLessEqual(x["buy_budget_deployed_pct"],50.)

    def test_equal_sell_units_tax_budget_and_activation_between_policies(self):
        p,fx=market()
        result=_matched_pair(p,fx,H,END,scenario="synthetic_fixture")
        original=result["baseline_original"]
        reserve=result["half_cash_reserve_candidate"]
        for k in ("initial_btc_before_sell","sell_count","original_btc_sold_pct",
                  "buy_200wma_activation_date",
                  "initial_aftertax_buyback_budget_aud","executed_sells"):
            self.assertEqual(original[k],reserve[k])
        self.assertGreaterEqual(original["cash_end_aud"],0.)
        self.assertGreaterEqual(reserve["cash_end_aud"],0.)

    def test_hindsight_low_only_scores_not_selects_earlier_cash(self):
        p,fx=market()
        endpoint=H+pd.Timedelta(days=829)
        truncated=replay_buy_reserve(p,fx,H,endpoint,reserve_policy=True)
        changed=p.copy()
        changed.loc[changed.index>endpoint]=1e8
        future_mutation=replay_buy_reserve(
            changed,fx,H,endpoint,reserve_policy=True)
        self.assertEqual(truncated,future_mutation)
        self.assertGreaterEqual(truncated["cash_aud_on_hindsight_low"],0.)

    def test_no_200wma_cross_no_buy_and_never_unlocks_early(self):
        p,fx=market()
        p.loc[p.index>=H+pd.Timedelta(days=770)]=100.
        out=replay_buy_reserve(p,fx,H,END,reserve_policy=True)
        self.assertIsNone(out["buy_200wma_activation_date"])
        self.assertEqual(out["buy_count"],0)
        self.assertIsNone(out["initial_aftertax_buyback_budget_aud"])
        self.assertFalse(out["reserved_cash_unlocked"])
        self.assertIsNone(out["buy_budget_deployed_pct"])

    def test_missing_price_date_or_bad_policy_fail_closed(self):
        p,fx=market()
        with self.assertRaisesRegex(ValueError,"variant"):
            replay_buy_reserve(p,fx,H,END,reserve_policy=None)
        missing=p.drop(H+pd.Timedelta(days=600))
        with self.assertRaisesRegex(ValueError,"Missing daily"):
            replay_buy_reserve(missing,fx,H,END,reserve_policy=False)
        with self.assertRaisesRegex(ValueError,"horizon"):
            replay_buy_reserve(p,fx,END,H,reserve_policy=True)

    def test_original_weights_and_200week_not_200day(self):
        self.assertEqual(RESERVE_FRACTION,.50)
        self.assertEqual(DEEP_DISCOUNT_WMA_RATIO,.85)
        p,fx=market()
        candidate=replay_buy_reserve(p,fx,H,END,reserve_policy=True)
        for order in candidate["executed_buys"]:
            self.assertGreater(order["gross_aud"],100.)
            self.assertTrue(0<order["original_budget_pct"]<=15.)
        self.assertTrue(candidate["research_only"])
        self.assertFalse(candidate["live_parity_certified"])


if __name__=="__main__":
    unittest.main()
