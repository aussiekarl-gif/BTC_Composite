"""Causal seven-day 200WMA depth-conditional BUY research, no live trading."""
import unittest

import numpy as np
import pandas as pd

from engines.research.cycle_conditional_deep_value_buy_audit import (
    BASELINE, FROZEN_CANDIDATES, _allocation, replay, compare_run,
)
from engines.research.live_weekly_buy_parity import replay_exact_live_market_buy

START=pd.Timestamp("2020-01-15",tz="UTC")
END=pd.Timestamp("2020-09-01",tz="UTC")


def inputs(kind="two_depths"):
    dates=pd.date_range("2015-01-01","2021-01-01",freq="D",tz="UTC")
    px=pd.Series(100.,index=dates)
    if kind=="two_depths":
        px.loc["2020-02-01":"2020-03-15"]=88.
        px.loc["2020-03-16":"2020-04-15"]=75.
        px.loc["2020-04-16":]=140.
    elif kind=="no_eligible":
        pass
    elif kind=="last_day_crash":
        px.loc[END]=50.
    elif kind=="deep_continues":
        px.loc["2020-02-01":]=75.
        for day in pd.date_range(pd.Timestamp("2020-02-02",tz="UTC"),END,freq="D"):
            px.loc[day]=max(10.,75.-.2*(day-pd.Timestamp(
                "2020-02-02",tz="UTC")).days)
    else:raise ValueError("Wrong fixture")
    fxidx=pd.date_range("2014-12-01","2021-01-01",tz="UTC",freq="D")
    return px,pd.DataFrame({"aud_per_usd":1.50},index=fxidx)


class ConditionalWeeklyBuyTests(unittest.TestCase):
    def test_unchanged_2p5_baseline_equals_previous_exact_weekly_replay(self):
        px,fx=inputs()
        a=replay(px,fx,start=START,terminal=END,capital_aud=40000.)
        b=replay_exact_live_market_buy(px,fx,start=START,terminal=END,
                                       fractions=(.025,),budget_aud=40000.)
        prior=b["wallets"][str(.025)]
        current=a["portfolios"][BASELINE]
        self.assertEqual(current["fills"],prior["fills"])
        self.assertEqual(current["cash_left_AUD"],prior["cash_left_aud"])
        self.assertEqual(current["BTC_held"],prior["btc_held"])
        self.assertEqual(current["after_illustrative_FIFO_SMSF_liquidation_AUD"],
                         prior["aftertax_aud"])
        self.assertEqual([o["date"] for o in current["paper_orders"]],
                         [o["date"] for o in prior["orders"]])
        self.assertTrue(a["actual_live_buy_rule_used_as_baseline"])

    def test_every_challenger_has_same_starting_aud_and_no_forced_buy(self):
        px,fx=inputs()
        x=replay(px,fx,start=START,terminal=END,capital_aud=40000.)
        self.assertFalse(x["terminal_cash_forced_to_BTC"])
        self.assertEqual(set(x["portfolios"]),set(FROZEN_CANDIDATES))
        self.assertTrue(all(v["hypothetical_AUD_cash_at_entry"]==40000
                            for v in x["portfolios"].values()))
        self.assertTrue(all(v["cash_left_AUD"]>0
                            for v in x["portfolios"].values()))
        self.assertTrue(x["hypothetical_daily_USD_close_not_ASX_eligible_fill"])

    def test_deep_discount_changes_allocation_not_eligible_trading_dates(self):
        px,fx=inputs()
        x=replay(px,fx,start=START,terminal=END,capital_aud=40000.)
        base=x["portfolios"][BASELINE]["paper_orders"]
        dates=[o["date"] for o in base]
        self.assertGreater(len(dates),6)
        self.assertGreater(x["eligible_prior_BTC_at_least_10pct_below_200WMA_days"],1)
        self.assertGreater(x["eligible_prior_BTC_at_least_20pct_below_200WMA_days"],1)
        for policy,account in x["portfolios"].items():
            orders=account["paper_orders"]
            self.assertEqual([o["date"] for o in orders],dates)
            for item in orders:
                self.assertEqual(item["actual_shared_market_pct"],2.5)
                ratio=item["prior_BTCUSD_over_prior_200WMA"]
                expected=round(100*_allocation(policy,ratio),2)
                self.assertEqual(item["fraction_of_remaining_cash_pct"],expected)
                self.assertLess(ratio,1.)
        tiered=x["portfolios"]["tiered_3p5_at_10pct_and_5p0_at_20pct"]["paper_orders"]
        self.assertIn(3.5,[o["fraction_of_remaining_cash_pct"] for o in tiered])
        self.assertIn(5.,[o["fraction_of_remaining_cash_pct"] for o in tiered])
        self.assertEqual([o["fraction_of_remaining_cash_pct"] for o in base],
                         [2.5]*len(base))

    def test_deep5_does_not_buy_more_when_ratio_above_80pct(self):
        for r in (.99,.95,.90,.81):
            self.assertEqual(_allocation("deep_5p0_only_if_20pct_below_WMA",r),.025)
        self.assertEqual(_allocation("deep_5p0_only_if_20pct_below_WMA",.8),.05)
        self.assertEqual(_allocation("tiered_3p5_at_10pct_and_5p0_at_20pct",.85),.035)
        self.assertEqual(_allocation("tiered_3p5_at_10pct_and_5p0_at_20pct",.78),.05)

    def test_no_discount_no_purchase_even_in_later_months(self):
        px,fx=inputs("no_eligible")
        out=replay(px,fx,start=START,terminal=END,capital_aud=40000.)
        self.assertEqual(out["eligible_prior_BTC_below_200WMA_days"],0)
        for r in out["portfolios"].values():
            self.assertEqual(r["fills"],0)
            self.assertEqual(r["cash_left_AUD"],40000.)
            self.assertEqual(r["after_illustrative_FIFO_SMSF_liquidation_AUD"],40000.)
            self.assertEqual(r["mean_daily_BTC_market_exposure_pct"],0.)

    def test_same_day_crash_cannot_trigger_same_close_buy(self):
        px,fx=inputs("last_day_crash")
        out=replay(px,fx,start=START,terminal=END)
        self.assertEqual(out["eligible_prior_BTC_below_200WMA_days"],0)
        self.assertTrue(all(v["fills"]==0 for v in out["portfolios"].values()))

    def test_seven_day_cooldown_kept_even_when_price_dips_deeper(self):
        px,fx=inputs("deep_continues")
        out=replay(px,fx,start=START,terminal=END,capital_aud=40000.)
        for result in out["portfolios"].values():
            timestamps=[pd.Timestamp(x["date"],tz="UTC")
                        for x in result["paper_orders"]]
            self.assertGreater(len(timestamps),10)
            self.assertTrue(all((timestamps[i]-timestamps[i-1]).days>=7
                                for i in range(1,len(timestamps))))

    def test_future_price_mutation_cannot_change_any_prefix_trade(self):
        px,fx=inputs()
        prefix=pd.Timestamp("2020-03-20",tz="UTC")
        a=replay(px,fx,start=START,terminal=prefix)
        altered=px.copy()
        altered.loc[altered.index>prefix]*=.17
        b=replay(altered,fx,start=START,terminal=prefix)
        self.assertEqual(a,b)
        future=replay(altered,fx,start=START,terminal=END)
        for name,rec in a["portfolios"].items():
            self.assertEqual(rec["paper_orders"],
                             [o for o in future["portfolios"][name]["paper_orders"]
                              if o["date"]<=str(prefix.date())])

    def test_additional_exposure_is_not_return_superiority_proof(self):
        px,fx=inputs("deep_continues")
        a=replay(px,fx,start=START,terminal=END,capital_aud=40000.)
        original=a["portfolios"][BASELINE]
        larger=a["portfolios"]["tiered_3p5_at_10pct_and_5p0_at_20pct"]
        self.assertLess(larger["cash_left_AUD"],original["cash_left_AUD"])
        self.assertGreater(larger["BTC_held"],original["BTC_held"])
        self.assertGreater(larger["mean_daily_BTC_market_exposure_pct"],
                           original["mean_daily_BTC_market_exposure_pct"])
        self.assertLessEqual(larger["max_account_drawdown_pct"],0.)
        pairs=compare_run(a,cycle="synthetic",entry_day=650)
        self.assertTrue(all("max_account_drawdown_pct" in r for r in pairs))
        self.assertTrue(all("vs_original_2p5_aftertax_pct" in r for r in pairs))

    def test_corrupt_prior_BTC_price_and_missing_fX_fail_closed(self):
        px,fx=inputs()
        price=px.drop(pd.Timestamp("2019-01-05",tz="UTC"))
        with self.assertRaisesRegex(ValueError,"warmup"):
            replay(price,fx,start=START,terminal=END)
        price=px.copy()
        price.loc["2020-03-01"]=np.nan
        with self.assertRaisesRegex(ValueError,"nonfinite"):
            replay(price,fx,start=START,terminal=END)
        with self.assertRaisesRegex(ValueError,"safely prior"):
            replay(px,fx.loc[:"2020-01-20"],start=START,terminal=END)

    def test_wrong_policy_or_cash_rejected(self):
        px,fx=inputs()
        with self.assertRaisesRegex(ValueError,"Invalid common"):
            replay(px,fx,start=START,terminal=END,capital_aud=0)
        with self.assertRaisesRegex(ValueError,"Invalid common"):
            replay(px,fx,start=START,terminal=END,policies=("invented",))
        with self.assertRaisesRegex(ValueError,"Unknown"):
            _allocation("invented",.80)
        with self.assertRaisesRegex(ValueError,"only for"):
            _allocation(BASELINE,1.)

    def test_percentage_difference_is_not_outofsample_model_winner(self):
        px,fx=inputs()
        a=replay(px,fx,start=START,terminal=END)
        rows=compare_run(a,cycle="synthetic",entry_day=750,synthetic=True)
        self.assertEqual(len(rows),5)
        baseline=next(r for r in rows if r["policy"]==BASELINE)
        self.assertEqual(baseline["vs_original_2p5_aftertax_pct"],0.)
        self.assertTrue(all(r["synthetic_delayed_bottom"] for r in rows))
        self.assertTrue(all(r["AUD_cash_remaining_pct"]<=100 for r in rows))


if __name__=="__main__":
    unittest.main()
