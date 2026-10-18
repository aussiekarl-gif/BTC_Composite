"""Separate weekend carry-forward research hypothesis; not live Cycle policy."""
import unittest
import pandas as pd

from engines.research.cycle_asx_weekday_execution_proxy import replay_proxy
from engines.research.cycle_weekend_carry_audit import compare

START=pd.Timestamp("2020-01-15",tz="UTC")
END=pd.Timestamp("2020-05-01",tz="UTC")


def inputs(mode="weekend_rebound"):
    days=pd.date_range("2015-01-01","2021-01-01",tz="UTC",freq="D")
    p=pd.Series(100.,index=days)
    if mode=="weekend_rebound":
        p.loc["2020-02-01"]=65.  # Saturday low, Sunday action WATCH
        p.loc["2020-02-02":]=101. # Monday prior close ABOVE 200WMA
    elif mode=="weekend_rebound_too_far":
        p.loc["2020-02-01"]=65.
        p.loc["2020-02-02":]=106.
    elif mode=="sustained_bear":
        p.loc["2020-02-01":]=65.
    elif mode=="no_cross":
        pass
    else:
        raise ValueError("Invalid fixture")
    fx=pd.DataFrame({"aud_per_usd":1.5},index=pd.date_range(
        "2014-12-01","2021-01-01",freq="D",tz="UTC"))
    return p,fx


class WeekendCarryTests(unittest.TestCase):
    def test_only_sunday_wma_cross_generates_monday_new_buy(self):
        p,fx=inputs("weekend_rebound")
        old=replay_proxy(p,fx,start=START,terminal=END,
                         weekday_only=True,budget_aud=40000.)
        new=replay_proxy(p,fx,start=START,terminal=END,
                         weekday_only=True,carry_weekend=True,
                         budget_aud=40000.)
        self.assertEqual(old["market_buy_watch_dates"],
                         new["market_buy_watch_dates"])
        self.assertGreater(old["buy_watch_weekend_dates"],0)
        self.assertEqual(old["account"]["0.025"]["purchases"],0)
        self.assertEqual(new["account"]["0.025"]["purchases"],1)
        o=new["account"]["0.025"]["orders"][0]
        self.assertEqual(o["date"],"2020-02-03")
        self.assertEqual(o["weekend_signal_origin_date"],"2020-02-02")
        self.assertEqual(o["entry_reason"],
                         "last_weekend_prior_200wma_watch_carried")
        self.assertTrue(new["number_of_extra_carried_account_fills"]>=1)
        self.assertEqual(new["candidate_max_rebound_over_wma_pct"],3.)

    def test_rebound_more_than_3pct_blocks_post_weekend_chase(self):
        p,fx=inputs("weekend_rebound_too_far")
        new=replay_proxy(p,fx,start=START,terminal=END,
                         weekday_only=True,carry_weekend=True,
                         budget_aud=40000.)
        self.assertGreater(new["buy_watch_weekend_dates"],0)
        for a in new["account"].values():
            self.assertEqual(a["purchases"],0)
            self.assertEqual(a["remaining_cash_aud"],40000.)

    def test_friday_thursday_cooldown_and_one_weekday_consumption(self):
        p,fx=inputs("sustained_bear")
        new=replay_proxy(p,fx,start=START,terminal=END,
                         weekday_only=True,carry_weekend=True,
                         budget_aud=40000.)
        for a in new["account"].values():
            dates=[pd.Timestamp(o["date"]) for o in a["orders"]]
            self.assertTrue(all(d.weekday()<5 for d in dates))
            self.assertTrue(all((b-a).days>=7 for a,b in zip(dates,dates[1:])))
            self.assertEqual(len(dates),len(set(dates)))

    def test_market_without_cross_not_given_new_entry(self):
        p,fx=inputs("no_cross")
        new=replay_proxy(p,fx,start=START,terminal=END,
                         weekday_only=True,carry_weekend=True,
                         budget_aud=40000.)
        self.assertEqual(new["number_of_extra_carried_account_fills"],0)
        self.assertEqual(new["market_buy_watch_dates"],0)
        for a in new["account"].values():
            self.assertEqual(a["purchases"],0)

    def test_invalid_candidate_parameters_fail_closed(self):
        p,fx=inputs("weekend_rebound")
        for kwargs in (
            {"weekday_only":False,"carry_weekend":True},
            {"carry_weekend":True,"carry_max_days":4},
            {"carry_weekend":True,"rebound_cap_over_200wma":.11},
            {"carry_weekend":"yes"},
        ):
            with self.assertRaisesRegex(ValueError,"execution assumptions"):
                replay_proxy(p,fx,start=START,terminal=END,
                             budget_aud=40000.,**kwargs)

    def test_candidate_scoring_still_uses_one_shared_btc_market_watch(self):
        p,fx=inputs("weekend_rebound")
        result=compare(p,fx,start=START,terminal=END,
                       cycle="synthetic",cohort=650)
        self.assertEqual(len(result),6)
        for item in result:
            self.assertEqual(item["unmodified_weekday_buy_count"],0)
            self.assertEqual(item["carried_weekend_buy_count"],1)
            self.assertEqual(item["new_carried_buy_count"],1)
            self.assertEqual(item["new_carried_dates"],"2020-02-03")
            self.assertGreater(item["original_weekend_watches"],0)
            self.assertGreater(item["original_aftertax_aud"],0)


if __name__=="__main__":
    unittest.main()
