"""Reserve floors preserve fresh AUD and never alter original 2.5% baseline."""
import unittest
import numpy as np
import pandas as pd
from engines.research.cycle_deep_value_cash_reserve_audit import (
    RESERVE_POLICIES,REFERENCE,requested_fraction_and_reserve,
    replay_reserves,compare,
)
from engines.research.cycle_conditional_deep_value_buy_audit import (
    replay as old_deep_replay,BASELINE,
)
from engines.research.live_weekly_buy_parity import replay_exact_live_market_buy

START=pd.Timestamp("2020-01-15",tz="UTC")
END=pd.Timestamp("2020-09-01",tz="UTC")
CAPITAL=40000.0


def series(kind="low"):
    ix=pd.date_range("2015-01-01","2021-04-01",freq="D",tz="UTC")
    px=pd.Series(100.,index=ix)
    if kind=="low":
        px.loc["2020-02-01":"2020-03-01"]=88.
        px.loc["2020-03-02":"2020-04-15"]=75.
        px.loc["2020-04-16":]=140.
    elif kind=="very_low":
        px.loc["2020-02-01":"2020-02-14"]=88.
        px.loc["2020-02-15":"2020-03-01"]=75.
        px.loc["2020-03-02":"2020-05-15"]=65.
        px.loc["2020-05-16":]=125.
    elif kind=="no_cross":
        pass
    elif kind=="last_day_only":
        px.loc[END]=40.
    else:raise ValueError("bad fixture")
    fx=pd.DataFrame({"aud_per_usd":1.5},
                    index=pd.date_range("2014-12-01","2021-04-01",freq="D",tz="UTC"))
    return px,fx


class CashReserveGatingTests(unittest.TestCase):
    def test_exact_live_baseline_replays_identically_to_existing_2p5(self):
        px,fx=series()
        new=replay_reserves(px,fx,start=START,terminal=END,capital_aud=CAPITAL)
        old=replay_exact_live_market_buy(px,fx,start=START,terminal=END,
                                         fractions=(.025,),budget_aud=CAPITAL)
        account=new["accounts"][REFERENCE]
        original=old["wallets"][str(.025)]
        self.assertEqual(account["fills"],original["fills"])
        self.assertEqual(account["cash_left_AUD"],original["cash_left_aud"])
        self.assertEqual(account["BTC_held"],original["btc_held"])
        self.assertEqual(account["after_illustrative_FIFO_SMSF_liquidation_AUD"],
                         original["aftertax_aud"])
        self.assertEqual([o["date"] for o in account["orders"]],
                         [o["date"] for o in original["orders"]])
        self.assertTrue(all(o["unchanged_live_market_buy_pct"]==2.5
                            for o in account["orders"]))

    def test_tiered_unreserved_is_exact_previous_deep_value_candidate(self):
        px,fx=series("very_low")
        result=replay_reserves(px,fx,start=START,terminal=END,capital_aud=CAPITAL)
        old=old_deep_replay(px,fx,start=START,terminal=END,capital_aud=CAPITAL)
        p="tiered_3p5_5p0_no_reserve"
        prev="tiered_3p5_at_10pct_and_5p0_at_20pct"
        a,b=result["accounts"][p],old["portfolios"][prev]
        self.assertEqual(a["fills"],b["fills"])
        self.assertEqual(a["BTC_held"],b["BTC_held"])
        self.assertEqual(a["cash_left_AUD"],b["cash_left_AUD"])
        self.assertEqual(a["after_illustrative_FIFO_SMSF_liquidation_AUD"],
                         b["after_illustrative_FIFO_SMSF_liquidation_AUD"])

    def test_reserves_are_floors_of_initial_cash_not_live_portfolio_value(self):
        frac,protected=requested_fraction_and_reserve(
            "tiered_hold_40pct_25pct_10pct",.95,CAPITAL)
        self.assertEqual(frac,.025)
        self.assertEqual(protected,16000)
        self.assertEqual(requested_fraction_and_reserve(
            "tiered_hold_40pct_25pct_10pct",.85,CAPITAL)[1],10000)
        self.assertEqual(requested_fraction_and_reserve(
            "tiered_hold_40pct_25pct_10pct",.78,CAPITAL)[1],4000)
        self.assertEqual(requested_fraction_and_reserve(
            "tiered_hold_40pct_25pct_10pct",.69,CAPITAL)[1],0)

    def test_two_deeper_discount_thresholds_unfreeze_cash_without_final_sweep(self):
        px,fx=series("very_low")
        x=replay_reserves(px,fx,start=START,terminal=END,capital_aud=CAPITAL)
        self.assertFalse(x["terminal_cash_sweep_or_forced_date"])
        reserved=x["accounts"]["tiered_hold_40pct_25pct_10pct"]
        uncovered=x["accounts"]["tiered_3p5_5p0_no_reserve"]
        self.assertGreater(reserved["cash_left_AUD"],uncovered["cash_left_AUD"])
        self.assertLess(reserved["BTC_held"],uncovered["BTC_held"])
        self.assertGreater(reserved["cash_left_AUD"],0)
        for o in reserved["orders"]:
            self.assertGreaterEqual(o["cash_after_AUD"],
                                    o["protected_original_cash_AUD"]-1e-6)

    def test_higher_reserve_does_not_force_later_buy_even_when_cheap(self):
        px,fx=series("very_low")
        x=replay_reserves(px,fx,start=START,terminal=END,capital_aud=CAPITAL)
        self.assertTrue(x["candidate_cash_floors_of_initial_AUD_only"])
        self.assertGreater(x["accounts"]["tiered_hold_50pct_until_20pct_discount"]
                           ["cash_left_AUD"],0)
        self.assertTrue(all(v["cash_left_AUD"]>=0 for v in x["accounts"].values()))

    def test_no_valid_market_signal_keeps_whole_cash_even_if_calendar_passes(self):
        px,fx=series("no_cross")
        x=replay_reserves(px,fx,start=START,terminal=END,capital_aud=CAPITAL)
        for account in x["accounts"].values():
            self.assertEqual(account["cash_left_AUD"],CAPITAL)
            self.assertEqual(account["BTC_held"],0)
            self.assertEqual(account["fills"],0)
            self.assertEqual(account["after_illustrative_FIFO_SMSF_liquidation_AUD"],
                             CAPITAL)

    def test_end_of_day_crash_does_not_backdate_that_days_trade(self):
        px,fx=series("last_day_only")
        x=replay_reserves(px,fx,start=START,terminal=END,capital_aud=CAPITAL)
        self.assertEqual(x["accounts"][REFERENCE]["fills"],0)
        self.assertEqual(x["accounts"][REFERENCE]["BTC_held"],0)

    def test_active_accounts_observe_same_watch_and_seven_day_ledger_cooldown(self):
        px,fx=series("very_low")
        x=replay_reserves(px,fx,start=START,terminal=END,capital_aud=CAPITAL)
        watches={a["matched_current_market_BUY_WATCH_days"]
                 for a in x["accounts"].values()}
        self.assertEqual(len(watches),1)
        for account in x["accounts"].values():
            stamps=[pd.Timestamp(t["date"],tz="UTC") for t in account["orders"]]
            self.assertTrue(all((stamps[i]-stamps[i-1]).days>=7
                                for i in range(1,len(stamps))))
            self.assertTrue(all(x["unchanged_live_market_buy_pct"]==2.5
                                for x in account["orders"]))

    def test_prefix_invariance_last_prices_can_change_without_changing_past(self):
        px,fx=series("very_low")
        prefix=pd.Timestamp("2020-03-21",tz="UTC")
        first=replay_reserves(px,fx,start=START,terminal=prefix,capital_aud=CAPITAL)
        changed=px.copy()
        changed.loc[changed.index>prefix]*=.2
        second=replay_reserves(changed,fx,start=START,terminal=prefix,capital_aud=CAPITAL)
        self.assertEqual(first,second)
        late=replay_reserves(changed,fx,start=START,terminal=END,capital_aud=CAPITAL)
        for name,rec in first["accounts"].items():
            original=rec["orders"]
            new_prefix=[o for o in late["accounts"][name]["orders"]
                        if o["date"]<=str(prefix.date())]
            self.assertEqual(original,new_prefix)

    def test_realistic_account_drawdown_and_terminal_aftertax_are_not_alpha(self):
        px,fx=series("very_low")
        x=replay_reserves(px,fx,start=START,terminal=END,capital_aud=CAPITAL)
        scored=compare(x,cycle="SYNTHETIC",day=750,synthetic=True)
        self.assertEqual(len(scored),len(RESERVE_POLICIES))
        base=next(t for t in scored if t["policy"]==REFERENCE)
        self.assertEqual(base["vs_unmodified_live_2p5_total_AUD_pct"],0)
        for t in scored:
            self.assertGreater(t["AUD_cash_left"],0)
            self.assertLessEqual(t["max_drawdown_pct"],0)
            self.assertGreaterEqual(t["mean_daily_BTC_exposure_pct"],0)
            self.assertIn("paper_orders",t)

    def test_insufficient_price_warmup_or_missing_prior_fx_never_buys(self):
        px,fx=series("low")
        with self.assertRaisesRegex(ValueError,"warmup"):
            replay_reserves(px.drop(pd.Timestamp("2019-05-01",tz="UTC")),fx,
                            start=START,terminal=END)
        with self.assertRaisesRegex(ValueError,"prior"):
            replay_reserves(px,fx.loc[:"2020-01-20"],start=START,terminal=END)
        bad=px.copy()
        bad.loc["2020-03-15"]=np.nan
        with self.assertRaisesRegex(ValueError,"Nonfinite"):
            replay_reserves(bad,fx,start=START,terminal=END)

    def test_reject_unknown_candidate_nonfinite_ratio_no_valid_min_aud(self):
        for call in (
            lambda:requested_fraction_and_reserve("invented",.79,CAPITAL),
            lambda:requested_fraction_and_reserve(REFERENCE,float("nan"),CAPITAL),
            lambda:requested_fraction_and_reserve(REFERENCE,.80,0),
        ):
            with self.assertRaises(ValueError):call()
        px,fx=series()
        with self.assertRaisesRegex(ValueError,"Invalid original"):
            replay_reserves(px,fx,start=START,terminal=END,capital_aud=0)

    def test_fixed_cash_floor_thresholds_do_not_spend_previously_earned_returns(self):
        a=requested_fraction_and_reserve("tiered_hold_25pct_until_20pct_discount",
                                         .81,CAPITAL)[1]
        b=requested_fraction_and_reserve("tiered_hold_25pct_until_20pct_discount",
                                         .79,CAPITAL)[1]
        c=requested_fraction_and_reserve("tiered_hold_25pct_until_20pct_discount",
                                         .69,CAPITAL)[1]
        self.assertEqual((a,b,c),(10000,4000,0))


if __name__=="__main__":
    unittest.main()
