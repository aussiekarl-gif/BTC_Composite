"""Permanent cash floors are never unlocked at any 200WMA depth."""
import datetime as dt
import unittest
import numpy as np
import pandas as pd

from engines.research.cycle_deep_value_cash_reserve_audit import (
    REFERENCE, replay_reserves,
    requested_fraction_and_reserve,
)
from engines.research.cycle_permanent_cash_reserve_audit import (
    FROZEN_CASES, ORIGINAL_CASH_FLOORS, summarise_rows,
)
from engines.research.live_weekly_buy_parity import (
    replay_exact_live_market_buy,
)

START=pd.Timestamp("2020-01-15",tz="UTC")
END=pd.Timestamp("2021-03-15",tz="UTC")
CAP=40000.

def fixture(kind="persistently_cheap"):
    ix=pd.date_range("2015-01-01","2021-06-15",freq="D",tz="UTC")
    values=pd.Series(100.,index=ix,dtype=float)
    if kind=="persistently_cheap":
        values.loc["2020-02-01":"2020-02-14"]=88.
        values.loc["2020-02-15":"2020-03-01"]=75.
        values.loc["2020-03-02":]=65.
    elif kind=="recovery":
        values.loc["2020-02-01":"2020-06-01"]=75.
        values.loc["2020-06-02":]=180.
    elif kind=="never_cheap":
        pass
    elif kind=="today_crash":
        values.loc[END]=20.
    else:raise ValueError("fixture not recognised")
    fx=pd.DataFrame({"aud_per_usd":1.5},index=pd.date_range(
        "2014-12-01","2021-06-15",freq="D",tz="UTC"))
    return values,fx


class PermanentReserveResearchTests(unittest.TestCase):
    def test_strict_15_and_25_pct_initial_cash_never_releases_at_deepest_value(self):
        for ratio in (.999,.9,.85,.79,.69,.45,.1):
            for name,policy in ORIGINAL_CASH_FLOORS.items():
                pct,protected=requested_fraction_and_reserve(
                    name,ratio,CAP,policy_map=FROZEN_CASES)
                self.assertEqual(protected, (.15 if "15pct" in name else .25)*CAP)
                self.assertGreater(pct,0)
                self.assertLessEqual(pct,.05)

    def test_exact_original_no_floor_2p5_control_parity_with_prior_engine(self):
        px,fx=fixture()
        new=replay_reserves(px,fx,start=START,terminal=END,
                            capital_aud=CAP,policy_map=FROZEN_CASES)
        unchanged=replay_reserves(px,fx,start=START,terminal=END,
                                  capital_aud=CAP)
        a=new["accounts"][REFERENCE]
        b=unchanged["accounts"][REFERENCE]
        self.assertEqual(a,b)
        self.assertEqual(new["accounts"]["tiered_3p5_5p0_no_reserve"],
                         unchanged["accounts"]["tiered_3p5_5p0_no_reserve"])
        existing=replay_exact_live_market_buy(
            px,fx,start=START,terminal=END,fractions=(.025,),budget_aud=CAP)
        orig=existing["wallets"][str(.025)]
        self.assertEqual(a["fills"],orig["fills"])
        self.assertEqual(a["BTC_held"],orig["btc_held"])
        self.assertEqual(a["cash_left_AUD"],orig["cash_left_aud"])
        self.assertEqual(a["after_illustrative_FIFO_SMSF_liquidation_AUD"],
                         orig["aftertax_aud"])

    def test_permanent_floor_never_spent_during_prolonged_under_wma(self):
        px,fx=fixture()
        run=replay_reserves(px,fx,start=START,terminal=END,
                            capital_aud=CAP,policy_map=FROZEN_CASES)
        bound_at_least_once=False
        for name,plan in ORIGINAL_CASH_FLOORS.items():
            expected=(.15 if "15pct" in name else .25)*CAP
            account=run["accounts"][name]
            same_sizing_control=(REFERENCE if name.startswith("live_2p5_")
                                 else "tiered_3p5_5p0_no_reserve")
            original=run["accounts"][same_sizing_control]
            self.assertGreaterEqual(account["cash_left_AUD"],expected-0.01)
            # A reserve that never becomes binding MUST NOT pretend to
            # help performance or change the exact original trade path.
            self.assertGreaterEqual(account["cash_left_AUD"],
                                    original["cash_left_AUD"]-.01)
            self.assertLessEqual(account["BTC_held"],original["BTC_held"]+1e-8)
            if original["cash_left_AUD"]<expected-.01:
                bound_at_least_once=True
                self.assertGreater(account["cash_left_AUD"],
                                   original["cash_left_AUD"])
            self.assertTrue(all(o["cash_after_AUD"]>=expected-.01
                                for o in account["orders"]))
        self.assertTrue(bound_at_least_once,
                        "Test fixture must cause a REAL binding cash floor")
        self.assertFalse(run["terminal_cash_sweep_or_forced_date"])

    def test_floor_preserves_cash_even_in_very_deep_extra_decline(self):
        px,fx=fixture()
        later=px.copy()
        later.loc["2020-08-01":]=35.
        run=replay_reserves(later,fx,start=START,terminal=END,
                            capital_aud=CAP,policy_map=FROZEN_CASES)
        for name in ORIGINAL_CASH_FLOORS:
            expected=.15*CAP if "15pct" in name else .25*CAP
            self.assertGreaterEqual(run["accounts"][name]["cash_left_AUD"],
                                    expected-0.01)

    def test_recovery_cost_is_not_hidden_by_smaller_drawdown(self):
        px,fx=fixture("recovery")
        run=replay_reserves(px,fx,start=START,terminal=END,
                            capital_aud=CAP,policy_map=FROZEN_CASES)
        tiered=run["accounts"]["tiered_3p5_5p0_no_reserve"]
        c25=run["accounts"]["tiered_3p5_5p0_cash_floor_25pct_forever"]
        self.assertGreaterEqual(c25["cash_left_AUD"],CAP*.25-.01)
        # If the floor never binds, it should exactly match rather
        # than fabricating a supposed performance disadvantage.
        if c25["fills"]==tiered["fills"]:
            self.assertEqual(c25["cash_left_AUD"],tiered["cash_left_AUD"])
            self.assertEqual(c25["BTC_held"],tiered["BTC_held"])

    def test_no_price_discount_means_all_cash_into_2027(self):
        px,fx=fixture("never_cheap")
        run=replay_reserves(px,fx,start=START,terminal=END,
                            capital_aud=CAP,policy_map=FROZEN_CASES)
        for item in run["accounts"].values():
            self.assertEqual(item["fills"],0)
            self.assertEqual(item["cash_left_AUD"],CAP)
            self.assertEqual(item["BTC_held"],0.0)

    def test_today_price_fall_never_triggered_a_same_day_buy(self):
        px,fx=fixture("today_crash")
        run=replay_reserves(px,fx,start=START,terminal=END,
                            capital_aud=CAP,policy_map=FROZEN_CASES)
        self.assertTrue(all(x["fills"]==0 for x in run["accounts"].values()))

    def test_all_cooldowns_at_least_seven_days_and_same_watch(self):
        px,fx=fixture()
        run=replay_reserves(px,fx,start=START,terminal=END,
                            capital_aud=CAP,policy_map=FROZEN_CASES)
        watches={a["matched_current_market_BUY_WATCH_days"]
                 for a in run["accounts"].values()}
        self.assertEqual(len(watches),1)
        for name,account in run["accounts"].items():
            dates=[pd.Timestamp(o["date"],tz="UTC") for o in account["orders"]]
            self.assertTrue(all((b-a).days>=7 for a,b in zip(dates,dates[1:])))
            self.assertTrue(all(o["unchanged_live_market_buy_pct"]==2.5
                                for o in account["orders"]))

    def test_altering_prices_in_future_never_changes_past_orders(self):
        px,fx=fixture()
        cut=pd.Timestamp("2020-04-01",tz="UTC")
        first=replay_reserves(px,fx,start=START,terminal=cut,
                              capital_aud=CAP,policy_map=FROZEN_CASES)
        alt=px.copy()
        alt.loc[alt.index>cut]=15.
        future=replay_reserves(alt,fx,start=START,terminal=END,
                               capital_aud=CAP,policy_map=FROZEN_CASES)
        for name in FROZEN_CASES:
            self.assertEqual(first["accounts"][name]["orders"],
                 [x for x in future["accounts"][name]["orders"]
                  if x["date"]<=str(cut.date())])

    def test_invalid_policy_and_missing_history_and_missing_fx_refused(self):
        px,fx=fixture()
        with self.assertRaisesRegex(ValueError,"reserve policies"):
            replay_reserves(px,fx,start=START,terminal=END,
                            capital_aud=CAP,policies=("unknown",),
                            policy_map=FROZEN_CASES)
        with self.assertRaisesRegex(ValueError,"warmup"):
            replay_reserves(px.drop(pd.Timestamp("2019-07-01",tz="UTC")),fx,
                            start=START,terminal=END,policy_map=FROZEN_CASES)
        with self.assertRaisesRegex(ValueError,"prior"):
            replay_reserves(px,fx.loc[:"2020-01-20"],
                            start=START,terminal=END,policy_map=FROZEN_CASES)

    def test_summary_fails_when_reserved_floor_spent_or_control_missing(self):
        row={
            "cycle":"2021","halving_day_entry":650,
            "policy":REFERENCE,
            "vs_unmodified_live_2p5_total_AUD_pct":0.0,
            "max_drawdown_pct":-10.0,
            "AUD_cash_left_pct_of_original":30.0,
            "mean_daily_BTC_exposure_pct":50.0,
        }
        with self.assertRaisesRegex(AssertionError,"Missing matched"):
            summarise_rows([row],label="test")
        rows=[{**row,"policy":policy,
               "AUD_cash_left_pct_of_original":(0.0 if "25pct_forever" in policy else 50.0)}
              for policy in FROZEN_CASES]
        with self.assertRaisesRegex(AssertionError,"reserve was spent"):
            summarise_rows(rows,label="test")


if __name__=="__main__":
    unittest.main()
