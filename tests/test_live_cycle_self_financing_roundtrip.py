"""Causal live SELL+BUYBACK parity tests: original BTC, no free cash or foresight."""
import unittest
import numpy as np
import pandas as pd

from engines.research.live_cycle_self_financing_roundtrip import (
    POLICIES, BUY_PCT_OF_REMAINING, MIN_TRADE_GAP_DAYS,
    rising_bull_path, simulate_full_roundtrip, day,
)

HALVING=pd.Timestamp("2018-01-01",tz="UTC")
END=HALVING+pd.Timedelta(days=1150)


def input_market(mode="recover"):
    dates=pd.date_range("2013-01-01","2024-01-01",freq="D",tz="UTC")
    p=pd.Series(100.,index=dates,dtype=float)
    if mode in ("recover","down"):
        p.loc[HALVING+pd.Timedelta(days=450):]=240.
        p.loc[HALVING+pd.Timedelta(days=900):]=70.
        if mode=="recover":
            p.loc[HALVING+pd.Timedelta(days=1100):]=140.
    elif mode=="never_below":
        p.loc[HALVING+pd.Timedelta(days=450):]=240.
    elif mode=="flat":
        pass
    else:
        raise ValueError("Invalid historical BTC sample mode")
    fx=pd.DataFrame({"aud_per_usd":np.full(len(dates),1.5)},index=dates)
    return p,fx


class SelfFinancingCycleRoundtripTests(unittest.TestCase):
    def test_all_five_cash_funded_same_historic_start(self):
        p,fx=input_market()
        r=simulate_full_roundtrip(p,fx,halving=HALVING,
                                   terminal=END,starting_cash=40000.)
        self.assertEqual(set(r["accounts"]),set(POLICIES))
        self.assertTrue(r["no_external_cash_for_reinvestment"])
        self.assertEqual(r["shared_live_buy_fraction_of_remaining_cash_pct"],2.5)
        self.assertEqual(r["accounts"]["buy_and_hold"]["actual_sell_orders"],0)
        self.assertEqual(r["accounts"]["buy_and_hold"]["actual_buyback_orders"],0)
        self.assertEqual(r["accounts"]["buy_and_hold"]["cash_remaining_aud"],0.)
        originals=[x["original_btc"] for x in r["accounts"].values()]
        self.assertEqual(len(set(originals)),1)
        for record in r["accounts"].values():
            self.assertGreater(record["hypothetical_aftertax_liquidation_aud"],0)
            self.assertGreaterEqual(record["cash_remaining_aud"],0)
            self.assertGreaterEqual(record["btc_left_after_buybacks"],0)
            self.assertGreaterEqual(record["total_brokerage_aud"],3.)

    def test_no_buyback_before_actual_realized_sell_proceeds(self):
        p,fx=input_market()
        r=simulate_full_roundtrip(p,fx,halving=HALVING,
                                   terminal=END,starting_cash=40000.)
        saw_buyback=False
        for name,record in r["accounts"].items():
            orders=record["dated_orders"]
            sells=[x for x in orders if x["side"]=="SELL"]
            buys=[x for x in orders if x["side"]=="BUY"]
            self.assertEqual(len(sells),record["actual_sell_orders"])
            self.assertEqual(len(buys),record["actual_buyback_orders"])
            if buys:
                saw_buyback=True
                self.assertTrue(sells, f"{name}: bought without selling")
                self.assertGreater(day(buys[0]["date"]),
                                   day(sells[0]["date"]))
                for buy in buys:
                    self.assertEqual(buy["signal_origin"],
                                     "shared_live_200wma_watch")
                    self.assertGreater(buy["btc"],0.)
                    self.assertGreater(buy["gross_aud"],100.)
            for prior,later in zip(orders,orders[1:]):
                self.assertGreaterEqual(
                    (day(later["date"])-day(prior["date"])).days,7)
        self.assertTrue(saw_buyback)

    def test_hold_no_sale_and_no_external_buy_even_when_price_cheap(self):
        p,fx=input_market(mode="flat")
        r=simulate_full_roundtrip(p,fx,halving=HALVING,
                                   terminal=END,starting_cash=40000.)
        for name in ("live_with_experimental_late_rollover",
                     "live_scheduled_only","buy_and_hold"):
            record=r["accounts"][name]
            self.assertEqual(record["actual_sell_orders"],0)
            self.assertEqual(record["actual_buyback_orders"],0)
            self.assertEqual(record["cash_remaining_aud"],0.)
            self.assertEqual(record["btc_equivalent_vs_hold_pct"],0.)

    def test_weekday_proxy_has_no_weekend_realized_sell_or_buy(self):
        p,fx=input_market()
        r=simulate_full_roundtrip(p,fx,halving=HALVING,
                                   terminal=END,starting_cash=40000.,
                                   weekday_only=True)
        self.assertTrue(r["weekday_only_BTC_AUD_proxy"])
        for record in r["accounts"].values():
            for order in record["dated_orders"]:
                self.assertLess(day(order["date"]).weekday(),5)

    def test_bull_extra_two_and_four_x_preserves_all_prior_closes(self):
        p,fx=input_market()
        prefix=HALVING+pd.Timedelta(days=600)
        for multiple in (2.,4.):
            new=rising_bull_path(p,HALVING,ending_multiple=multiple)
            self.assertTrue(new.loc[:prefix].equals(p.loc[:prefix]))
            self.assertAlmostEqual(
                new.loc[END]/new.loc[prefix],multiple,places=6)
            self.assertTrue((new.loc[prefix:] > 0).all())
            result=simulate_full_roundtrip(
                new,fx,halving=HALVING,terminal=END,
                starting_cash=40000.,weekday_only=True)
            self.assertEqual(result["cycle_day"],1150)
            self.assertEqual(result["accounts"]["buy_and_hold"][
                "actual_buyback_orders"],0)

    def test_hindsight_future_path_does_not_revise_previous_fills(self):
        p,fx=input_market()
        e=HALVING+pd.Timedelta(days=730)
        prefix=simulate_full_roundtrip(p,fx,halving=HALVING,terminal=e,
                                        starting_cash=40000.)
        full=simulate_full_roundtrip(p,fx,halving=HALVING,terminal=END,
                                     starting_cash=40000.)
        for key in POLICIES:
            hist=prefix["accounts"][key]["dated_orders"]
            future=[x for x in full["accounts"][key]["dated_orders"]
                    if x["date"]<=str(e.date())]
            self.assertEqual(hist,future)
        changed=p.copy()
        changed.loc[changed.index>e]*=5.
        altered=simulate_full_roundtrip(changed,fx,halving=HALVING,
                                         terminal=e,starting_cash=40000.)
        for key in POLICIES:
            self.assertEqual(
                prefix["accounts"][key]["dated_orders"],
                altered["accounts"][key]["dated_orders"])

    def test_missing_day_fx_and_invalid_inputs_reject_not_impute(self):
        p,fx=input_market()
        with self.assertRaisesRegex(ValueError,"consecutive"):
            simulate_full_roundtrip(
                p.drop(HALVING+pd.Timedelta(days=800)),fx,
                halving=HALVING,terminal=END,starting_cash=40000.)
        with self.assertRaisesRegex(ValueError,"No safely prior"):
            simulate_full_roundtrip(
                p,fx.loc[:"2018-03-01"],halving=HALVING,
                terminal=END,starting_cash=40000.)
        with self.assertRaisesRegex(ValueError,"Invalid cash"):
            simulate_full_roundtrip(
                p,fx,halving=HALVING,terminal=END,starting_cash=0)
        with self.assertRaisesRegex(ValueError,"Invalid cash"):
            simulate_full_roundtrip(
                p,fx,halving=HALVING,terminal=END,weekday_only="yes")

    def test_original_staged_sell_denom_does_not_exceed_original_units(self):
        p,fx=input_market()
        r=simulate_full_roundtrip(p,fx,halving=HALVING,terminal=END,
                                   starting_cash=40000.)
        for key in ("research_original_btc_90pct",
                    "research_original_btc_20pct_holdback"):
            item=r["accounts"][key]
            self.assertGreater(item["actual_sell_orders"],0)
            self.assertLessEqual(item["original_btc_sold_pct"],100.)
            self.assertGreater(item["total_brokerage_aud"],3.)
        self.assertNotEqual(
            r["accounts"]["research_original_btc_90pct"]["actual_sell_orders"],
            r["accounts"]["live_scheduled_only"]["actual_sell_orders"])


if __name__=="__main__":
    unittest.main()
