import unittest
import numpy as np
import pandas as pd

from engines.research.hybrid_calendar_adaptive_dca import (
    run_hybrid_cohort,hybrid_summary_table,BASE_ALLOCATIONS,
)


def synthetic(start="2010-01-01",end="2019-01-01",enrol="2016-01-04",rally_date=None,drop=True):
    idx=pd.date_range(start,end,freq="D",tz="UTC")
    btc=pd.Series(100.,index=idx)
    if drop:
        btc.loc[idx>=pd.Timestamp(enrol,tz="UTC")]=50.
    if rally_date:
        btc.loc[idx>=pd.Timestamp(rally_date,tz="UTC")]=110.
    fx=pd.Series(.70,index=idx)
    return btc,fx


class HybridCalendarAdaptiveTests(unittest.TestCase):
    def test_predeclared_base_leg_buys_without_adaptive_trigger(self):
        btc,fx=synthetic(rally_date=None,drop=False)
        results=[run_hybrid_cohort(btc,fx,enrolment_date="2016-01-04",
                    base_allocation_pct=p) for p in BASE_ALLOCATIONS]
        for r in results:
            self.assertIsNone(r["trigger_date"])
            self.assertEqual(r["adaptive_buy_count"],0)
            self.assertEqual(r["base_buy_count"],104)
            self.assertGreater(r["btc_accumulated"],0)
            self.assertGreater(r["adaptive_cash_remaining_aud"],0)
            self.assertTrue(r["weekly_cap_compliant"] if "weekly_cap_compliant" in r else
                           r["largest_weekly_combined_outlay_aud"]<=r["weekly_cap_aud"]+1e-6)

    def test_triggered_reserve_buys_and_shared_weekly_cap_holds(self):
        btc,fx=synthetic(rally_date="2016-03-15")
        r=run_hybrid_cohort(btc,fx,enrolment_date="2016-01-04",base_allocation_pct=25)
        self.assertEqual(r["trigger_date"],"2016-01-05")
        self.assertGreater(r["adaptive_buy_count"],0)
        self.assertEqual(r["base_buy_count"],104)
        self.assertLessEqual(r["largest_weekly_combined_outlay_aud"],r["weekly_cap_aud"]+1e-6)
        self.assertGreater(r["adaptive_reserve_btc"],0)
        self.assertAlmostEqual(r["base_allocation_pct"],25.)

    def test_budget_split_and_weekly_cap_for_all_variants(self):
        btc,fx=synthetic(rally_date="2016-03-15")
        for pct in BASE_ALLOCATIONS:
            r=run_hybrid_cohort(btc,fx,enrolment_date="2016-01-04",base_allocation_pct=pct)
            self.assertAlmostEqual(r["base_budget_aud"],292383.*pct/100.)
            self.assertAlmostEqual(r["adaptive_reserve_budget_aud"],292383.*(1-pct/100.))
            self.assertLessEqual(r["largest_weekly_combined_outlay_aud"],25500.+1e-6)
            self.assertGreaterEqual(r["cash_remaining_aud"],0.)

    def test_hybrid_summary_pairs_same_calendar_cohort(self):
        fixed=pd.DataFrame([
            {"enrolment_date":"2020-01-06","policy":"fixed_weekly","btc_accumulated":1.,"terminal_equity_aud":100.},
            {"enrolment_date":"2022-01-03","policy":"fixed_weekly","btc_accumulated":1.,"terminal_equity_aud":100.},
        ])
        hybrid=pd.DataFrame([
            {"enrolment_date":"2020-01-06","entry_period":"pre_2022_calendar_entry","policy":"hybrid_base_25_adaptive_reserve_75","base_allocation_pct":25,"btc_accumulated":1.1,"terminal_equity_aud":110.,"fixed_weekly_btc":1.,"fixed_weekly_terminal_equity_aud":100.,"trigger_date":"2020-01-10","weeks_until_trigger":4.,"effective_vwap_aud_per_btc":100.,"cash_remaining_aud":10.,"cash_budget_deployed_pct":90.,"vwap_premium_to_cohort_low_pct":10.,"largest_weekly_combined_outlay_aud":25000.,"weekly_cap_aud":25500.},
            {"enrolment_date":"2022-01-03","entry_period":"2022plus_calendar_entry","policy":"hybrid_base_25_adaptive_reserve_75","base_allocation_pct":25,"btc_accumulated":1.1,"terminal_equity_aud":110.,"trigger_date":"2022-01-10","weeks_until_trigger":1.,"effective_vwap_aud_per_btc":100.,"cash_remaining_aud":10.,"cash_budget_deployed_pct":90.,"vwap_premium_to_cohort_low_pct":10.,"largest_weekly_combined_outlay_aud":25000.,"weekly_cap_aud":25500.},
        ])
        s=hybrid_summary_table(hybrid)
        self.assertEqual(len(s),2)
        self.assertEqual(s["weekly_cap_compliant"].all(),True)
        self.assertAlmostEqual(s["median_paired_btc_uplift_vs_fixed_weekly_pct"].iloc[0],10.)
        self.assertEqual(s["cohort_btc_win_rate_vs_fixed_weekly_pct"].iloc[0],100.)

    def test_invalid_base_allocation_rejected(self):
        btc,fx=synthetic()
        with self.assertRaises(ValueError):
            run_hybrid_cohort(btc,fx,enrolment_date="2016-01-04",base_allocation_pct=0)


if __name__=="__main__":
    unittest.main()
