"""No future-only performance assertions; test exact 3.0% live weekly mechanics."""
import unittest
import numpy as np
import pandas as pd

from engines.research.cycle_three_percent_audit import (
    FRACTIONS,analyse_wallets,
)
from engines.research.live_weekly_buy_parity import replay_exact_live_market_buy


class ThreePercentResearchTests(unittest.TestCase):
    def fixture(self,*,cross=True):
        idx=pd.date_range("2015-01-01","2021-01-01",tz="UTC",freq="D")
        data=pd.Series(100.,index=idx)
        if cross:
            data.loc["2020-02-01":"2020-07-01"]=65.
            data.loc["2020-07-02":]=120.
        fx=pd.DataFrame({"aud_per_usd":1.5},index=idx)
        return data,fx

    def test_three_percent_is_between_current_and_3p5_per_first_buy(self):
        p,fx=self.fixture()
        report=replay_exact_live_market_buy(p,fx,
                 start="2020-01-15",terminal="2020-09-01",
                 fractions=FRACTIONS,budget_aud=40000.)
        firsts=[report["wallets"][str(f)]["orders"][0]["gross_aud"]
                for f in FRACTIONS]
        self.assertEqual(firsts,[1000.,1200.,1400.])
        dates=[[o["date"] for o in report["wallets"][str(f)]["orders"]]
               for f in FRACTIONS]
        self.assertEqual(dates[0],dates[1])
        self.assertEqual(dates[1],dates[2])
        for actual in dates:
            self.assertTrue(all(
                (pd.Timestamp(actual[i])-pd.Timestamp(actual[i-1])).days>=7
                for i in range(1,len(actual))))

    def test_all_scoring_uses_same_initial_capital_and_aftertax_aud(self):
        p,fx=self.fixture()
        replay=replay_exact_live_market_buy(
            p,fx,start="2020-01-15",terminal="2020-09-01",
            fractions=FRACTIONS,budget_aud=40000.)
        rows=analyse_wallets(replay,cycle="synthetic",start_day=750,
                             complete=False)
        self.assertEqual([r["candidate_weekly_fraction_pct"] for r in rows],
                         [3.,3.5])
        for row in rows:
            self.assertGreater(row["reference_aftertax_aud"],0)
            self.assertGreater(row["candidate_aftertax_aud"],0)
            self.assertEqual(row["reference_fills"],row["candidate_fills"])
            self.assertGreater(row["reference_cash_left_aud"],0.)

    def test_no_new_wma_cross_no_buy_and_no_fake_gains(self):
        p,fx=self.fixture(cross=False)
        replay=replay_exact_live_market_buy(
            p,fx,start="2020-01-15",terminal="2020-09-01",
            fractions=FRACTIONS,budget_aud=40000.)
        for r in analyse_wallets(replay,cycle="synthetic",
                                 start_day=850,complete=False):
            self.assertEqual(r["candidate_btc"],0)
            self.assertEqual(r["reference_btc"],0)
            self.assertEqual(r["delta_aftertax_pct"],0.)
            self.assertEqual(r["reference_cash_left_aud"],40000.)
            self.assertEqual(r["candidate_cash_left_aud"],40000.)


if __name__=="__main__":
    unittest.main()
