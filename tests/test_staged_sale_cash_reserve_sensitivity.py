"""Deterministic synthetic downside/upside trade-off for sale-proceeds cash reserves."""
import unittest
import numpy as np
import pandas as pd

from engines.research.staged_tax_aware_roundtrip import replay_roundtrip
from engines.research.staged_sale_cash_reserve_sensitivity import evaluate_cash_reserves

HALVING=pd.Timestamp("2020-05-11",tz="UTC")


def market():
    idx=pd.date_range(pd.Timestamp("2014-01-01",tz="UTC"),
                      HALVING+pd.Timedelta(days=1150),freq="D")
    days=np.asarray((idx-HALVING).days,dtype=float)
    vals=np.interp(days,[-2400,-1600,-1000,0,400,525,560,750,950,1150],
                   [100,120,140,210,440,600,500,240,155,420])
    px=pd.Series(vals,index=idx)
    fidx=pd.date_range(idx.min()-pd.Timedelta(days=10),idx.max(),freq="D")
    fx=pd.DataFrame({"aud_per_usd":np.full(len(fidx),1.5)},index=fidx)
    return px,fx


def fake_fx(_start,_end):
    return market()[1]


class NetProceedsReserveTests(unittest.TestCase):
    def test_legacy_zero_reserve_replay_is_bitwise_unchanged(self):
        p,fx=market()
        end=HALVING+pd.Timedelta(days=1150)
        a=replay_roundtrip(p,fx,HALVING,end,
                           seller="fixed_525_to_560",
                           buyer="staged_value_recovery")
        b=replay_roundtrip(p,fx,HALVING,end,
                           seller="fixed_525_to_560",
                           buyer="staged_value_recovery",
                           min_net_sale_proceeds_reserve_pct=0)
        self.assertEqual(a,b)

    def test_reserve_holds_net_sale_cash_and_same_sell_leg(self):
        p,fx=market()
        end=HALVING+pd.Timedelta(days=1150)
        a=replay_roundtrip(p,fx,HALVING,end,
                           seller="fixed_525_to_560",
                           buyer="staged_value_recovery",
                           min_net_sale_proceeds_reserve_pct=0)
        c25=replay_roundtrip(p,fx,HALVING,end,
                            seller="fixed_525_to_560",
                            buyer="staged_value_recovery",
                            min_net_sale_proceeds_reserve_pct=25)
        c40=replay_roundtrip(p,fx,HALVING,end,
                            seller="fixed_525_to_560",
                            buyer="staged_value_recovery",
                            min_net_sale_proceeds_reserve_pct=40)
        self.assertEqual(a["sales"],c25["sales"])
        self.assertEqual(a["sales"],c40["sales"])
        self.assertLessEqual(c25["net_sale_proceeds_reinvested_pct"],75.01)
        self.assertLessEqual(c40["net_sale_proceeds_reinvested_pct"],60.01)
        self.assertGreater(c40["cash_remaining_aud"],c25["cash_remaining_aud"])
        self.assertGreaterEqual(c40["cash_remaining_aud"],c40["net_sell_cash_after_tax_aud"]*.40-0.02)
        self.assertGreaterEqual(c25["cash_remaining_aud"],c25["net_sell_cash_after_tax_aud"]*.25-0.02)
        for x in (a,c25,c40):
            self.assertTrue(x["no_external_cash"])
            self.assertGreaterEqual(x["cash_remaining_aud"],0)

    def test_invalid_reserve_rejected_and_no_initial_cash_added(self):
        p,fx=market()
        for value in (-1,95,float("nan")):
            with self.assertRaisesRegex(ValueError,"Sale-proceeds reserve"):
                replay_roundtrip(p,fx,HALVING,HALVING+pd.Timedelta(days=1150),
                    seller="fixed_525_to_560",
                    buyer="staged_value_recovery",
                    min_net_sale_proceeds_reserve_pct=value)

    def test_one_matched_counterfactual_has_all_three_caps(self):
        px,fx=market()
        fake_history=pd.DataFrame({"price_usd":px})
        def pick_fx(_h,_end):
            return fx
        data=evaluate_cash_reserves(
            fake_history,fx_fetcher=pick_fx,cycles=("2021",),
            starts=(780,),losses=(.7,),recoveries=(.55,))
        self.assertEqual(len(data["stress_details"]),1)
        s=data["stress_details"][0]
        self.assertEqual(set(s["staged"]),{"0","25","40"})
        self.assertEqual(len(data["stress_reserve_summary"]),3)
        self.assertEqual(s["staged"]["40"]["minimum_net_sale_proceeds_reserve_pct"],40.)
        self.assertLessEqual(s["staged"]["40"]["spent_before_low_pct_of_net_sale_proceeds"],60.01)


if __name__=="__main__":
    unittest.main()
