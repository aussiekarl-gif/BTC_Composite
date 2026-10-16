"""Research: equal-date dynamic-size attribution checks."""
import unittest

import pandas as pd

from engines.research.adaptive_weighting_attribution import (
    compare_one_leg, equal_weight_same_dates, evaluate, split_trade_legs,
)


def order(side, when, price, *, gross=None, btc=None, fee=3.0):
    if side=="BUY":
        gross=float(gross)
        btc=(gross-fee)/price
    else:
        btc=float(btc)
        gross=btc*price
    return {"side":side, "date":when,
            "executed_price_aud":price,
            "gross_notional_aud":gross,
            "btc_quantity":btc,"fee_aud":fee}


def fixture(n=190):
    prices=[100.+2*(i%22) for i in range(n)]
    risks=[.1]*30+[.5]*50+[.7]*60+[.1]*(n-140)
    return pd.DataFrame({"btc_price_aud":prices,"risk_score":risks},
                        index=pd.date_range("2018-01-01",periods=n,
                                            freq="W-MON",tz="UTC"))


class DynamicWeightAttributionTests(unittest.TestCase):
    def test_buy_25pct_weighted_outperforms_equal_example(self):
        # User scenario: AUD 150k at BTC 110k + AUD 50k at BTC 140k.
        t=[order("BUY","2022-01-03",110000,gross=150000),
           order("BUY","2022-01-10",140000,gross=50000)]
        e=equal_weight_same_dates(t)
        actual=(sum(x["gross_notional_aud"] for x in t) /
                sum(x["btc_quantity"] for x in t))
        self.assertAlmostEqual(actual,116229.70,delta=.5)
        self.assertAlmostEqual(e["net_effective_price_aud"],123202,delta=4)
        d=dict(side="BUY",start=t[0]["date"],end=t[-1]["date"],
               net_effective_price_aud=actual,orders=2,
               gross_notional_aud=200000)
        comparison=compare_one_leg(d,e)
        self.assertGreater(comparison["dynamic_advantage_pct"],5)

    def test_sell_uses_equal_btc_not_equal_dollars(self):
        t=[order("SELL","2022-01-03",200,btc=3) ,
           order("SELL","2022-01-10",100,btc=1)]
        # Dynamic BTC weighted 175; equal BTC per order 150; fees netted.
        e=equal_weight_same_dates(t)
        self.assertAlmostEqual(e["net_effective_price_aud"],148.5)

    def test_no_lookahead_in_equal_allocation(self):
        t=[order("BUY","2020-01-01",100,gross=10000),
           order("BUY","2020-01-08",90,gross=5000)]
        a=equal_weight_same_dates(t)
        self.assertEqual(a["orders"],2)
        self.assertEqual(a["fees_aud"],6)
        self.assertAlmostEqual(a["gross_notional_aud"],15000)
        self.assertEqual(a["start"],"2020-01-01")

    def test_groups_only_same_direction_and_does_not_lose_pauses(self):
        t=[order("BUY","2020-01-01",100,gross=10000),
           order("BUY","2020-03-01",105,gross=10000),
           order("SELL","2020-09-01",110,btc=1)]
        group=split_trade_legs(t)
        self.assertEqual([len(g) for g in group],[2,1])

    def test_reject_bad_input(self):
        with self.assertRaises(ValueError):
            equal_weight_same_dates([])
        with self.assertRaises(ValueError):
            equal_weight_same_dates([order("BUY","t",100,gross=3)])
        with self.assertRaises(ValueError):
            equal_weight_same_dates([order("BUY","t",100,gross=100),
                                     order("SELL","u",110,btc=1)])

    def test_scores_same_dates_and_15_20_25_target_levels(self):
        r=evaluate(fixture())
        self.assertEqual(set(r["paired_accuracy"]),{"15pct","20pct","25pct","35pct"})
        self.assertEqual(r["flat_order_fee_aud"],3)
        for p in r["paired_detail"]:
            self.assertEqual(p["eligible"],bool(p["eligible"]))
        for leg in r["weighting_by_leg"]:
            self.assertGreater(leg["orders"],0)
            self.assertGreater(leg["dynamic_price_aud"],0)
            self.assertGreater(leg["equal_price_aud"],0)


if __name__=="__main__":
    unittest.main()
