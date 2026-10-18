"""Live market BUY/watch + ledger 7-day cooldown matched cash-only test."""
import unittest
import pandas as pd
import numpy as np

from engines.research.live_weekly_buy_parity import (
    BASELINE_FRACTION,FROZEN_CHALLENGERS,match_rows,
    replay_exact_live_market_buy,
)

START=pd.Timestamp("2020-01-15",tz="UTC")
END=pd.Timestamp("2020-09-01",tz="UTC")


def make_inputs(kind="cross"):
    idx=pd.date_range("2015-01-01","2021-04-01",tz="UTC",freq="D")
    px=pd.Series(100.,index=idx)
    if kind=="cross":
        px.loc["2020-02-01":"2020-04-15"]=65.
        px.loc["2020-04-16":]=140.
    elif kind=="deep":
        px.loc["2020-02-01":]=65.
        for d in pd.date_range("2020-02-02",END,tz="UTC"):
            px.loc[d]=max(12.,65.-(d-pd.Timestamp(
                "2020-02-02",tz="UTC")).days*.23)
    elif kind=="no_cross":
        pass
    elif kind=="last_day_shock":
        px.loc[END]=50.
    else:
        raise ValueError("Unknown test scenario")
    fidx=pd.date_range("2014-12-01","2021-04-01",tz="UTC",freq="D")
    fx=pd.DataFrame({"aud_per_usd":1.50},index=fidx)
    return px,fx


class LiveWeeklyBuyParityTests(unittest.TestCase):
    def test_exact_2p5pct_signal_and_no_buy_stacking_during_bear(self):
        px,fx=make_inputs("deep")
        r=replay_exact_live_market_buy(px,fx,start=START,terminal=END,
                                       budget_aud=40000.)
        base=r["wallets"][str(BASELINE_FRACTION)]
        self.assertEqual(r["first_below_200wma_buy_watch"],"2020-02-02")
        self.assertGreater(base["fills"],12)
        self.assertGreater(r["eligible_daily_watch_count"],100)
        self.assertTrue(all(order["actual_same_day_live_market_pct"]==2.5
                            for order in base["orders"]))
        dates=[pd.Timestamp(x["date"],tz="UTC") for x in base["orders"]]
        self.assertTrue(all((dates[i]-dates[i-1]).days>=7
                            for i in range(1,len(dates))))
        self.assertAlmostEqual(base["orders"][0]["gross_aud"],1000.)
        self.assertEqual(base["first_executed_buy"],"2020-02-02")
        self.assertTrue(r["no_fabricated_historical_sale"])

    def test_immediate_recovery_stops_orders_without_fake_15pct_boost(self):
        px,fx=make_inputs("cross")
        r=replay_exact_live_market_buy(px,fx,start=START,terminal=END,
                                       budget_aud=40000.)
        base=r["wallets"][str(BASELINE_FRACTION)]
        self.assertGreater(base["fills"],1)
        self.assertLess(base["fills"],20)
        self.assertGreater(base["cash_left_pct"],60.)
        self.assertTrue(all(o["pct_remaining_cash"]==2.5
                            for o in base["orders"]))
        self.assertTrue(all(pd.Timestamp(o["date"],tz="UTC")<
                            pd.Timestamp("2020-04-16",tz="UTC")
                            for o in base["orders"]))

    def test_candidate_percentages_do_not_shift_buy_dates_or_eligibility(self):
        px,fx=make_inputs("cross")
        r=replay_exact_live_market_buy(px,fx,start=START,terminal=END,
                                       budget_aud=40000.)
        originals=[o["date"] for o in r["wallets"][
            str(BASELINE_FRACTION)]["orders"]]
        for pct in FROZEN_CHALLENGERS:
            item=r["wallets"][str(pct)]
            self.assertEqual([o["date"] for o in item["orders"]],originals)
            self.assertAlmostEqual(item["orders"][0]["gross_aud"],40000*pct)
            self.assertEqual(item["first_market_buy_watch"],
                             r["first_below_200wma_buy_watch"])

    def test_no_new_cross_means_no_fabricated_buys(self):
        px,fx=make_inputs("no_cross")
        r=replay_exact_live_market_buy(px,fx,start=START,terminal=END,
                                       budget_aud=40000.)
        self.assertIsNone(r["first_below_200wma_buy_watch"])
        for item in r["wallets"].values():
            self.assertEqual(item["btc_held"],0)
            self.assertEqual(item["cash_left_aud"],40000.)
            self.assertEqual(item["fills"],0)
            self.assertEqual(item["aftertax_aud"],40000.)

    def test_no_hindsight_on_same_day_crash(self):
        px,fx=make_inputs("last_day_shock")
        r=replay_exact_live_market_buy(px,fx,start=START,terminal=END,
                                       budget_aud=40000.)
        for item in r["wallets"].values():
            self.assertEqual(item["fills"],0)

    def test_prefix_invariance_earlier_buys_not_changed_by_late_price(self):
        px,fx=make_inputs("deep")
        earlier=pd.Timestamp("2020-05-01",tz="UTC")
        first=replay_exact_live_market_buy(px,fx,start=START,
                                           terminal=earlier,
                                           budget_aud=40000.)
        altered=px.copy()
        altered.loc[altered.index>earlier]*=4.
        second=replay_exact_live_market_buy(altered,fx,start=START,
                                            terminal=earlier,
                                            budget_aud=40000.)
        self.assertEqual(first,second)
        full=replay_exact_live_market_buy(px,fx,start=START,terminal=END,
                                          budget_aud=40000.)
        for fraction in (BASELINE_FRACTION,)+FROZEN_CHALLENGERS:
            k=str(fraction)
            self.assertEqual(first["wallets"][k]["orders"],
                             [o for o in full["wallets"][k]["orders"]
                              if o["date"]<=str(earlier.date())])

    def test_invalid_price_cash_fx_fail_closed(self):
        px,fx=make_inputs("deep")
        broken=px.drop(pd.Timestamp("2018-01-01",tz="UTC"))
        with self.assertRaisesRegex(ValueError,"warmup missing"):
            replay_exact_live_market_buy(broken,fx,start=START,terminal=END)
        bad=px.copy()
        bad.loc["2020-02-01"]=np.nan
        with self.assertRaisesRegex(ValueError,"Invalid BTC"):
            replay_exact_live_market_buy(bad,fx,start=START,terminal=END)
        with self.assertRaisesRegex(ValueError,"Invalid account"):
            replay_exact_live_market_buy(px,fx,start=START,terminal=END,
                                         fractions=(0.,))
        with self.assertRaisesRegex(ValueError,"No safely prior"):
            replay_exact_live_market_buy(px,fx.loc[:"2020-01-20"],
                                         start=START,terminal=END)

    def test_matched_cohort_aftertax_comparisons_and_cash_budget(self):
        px,fx=make_inputs("deep")
        r=replay_exact_live_market_buy(px,fx,start=START,terminal=END)
        scores=match_rows(r,cycle="synthetic",start_day=750,complete=False)
        self.assertEqual(len(scores),2)
        for row in scores:
            self.assertEqual(row["fraction_candidate_pct"] in (3.5,5.),True)
            self.assertLessEqual(row["cash_baseline_pct"],100.)
            self.assertLessEqual(row["cash_candidate_pct"],100.)
            self.assertGreaterEqual(row["candidate_fills"],1)
            self.assertEqual(row["first_below_200wma"],"2020-02-02")


if __name__=="__main__":
    unittest.main()
