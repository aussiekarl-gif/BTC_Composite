import unittest
import numpy as np
import pandas as pd

from engines.research.prospective_adaptive_recovery_replay import (
    run_cohort,quarterly_enrolment_dates,_prior_200wma_ratio,_aud_prices,
    summary_table,run_all_cohorts,
)


def synthetic(start="2010-01-01",end="2019-01-01",dip_date="2016-01-04",dip=50.):
    idx=pd.date_range(start,end,freq="D",tz="UTC")
    btc=pd.Series(100.,index=idx)
    btc.loc[idx>=pd.Timestamp(dip_date,tz="UTC")]=dip
    fx=pd.Series(.70,index=idx) # USD per AUD
    return btc,fx


class ProspectiveAdaptiveReplayTests(unittest.TestCase):
    def test_predeclared_quarterly_dates_not_cycle_low_dates(self):
        dates=quarterly_enrolment_dates()
        self.assertTrue(dates)
        self.assertEqual(dates[0],pd.Timestamp("2017-01-02").date())
        self.assertTrue(all(pd.Timestamp(d).weekday()==0 for d in dates))
        self.assertTrue(all(d.month in (1,4,7,10) for d in dates))

    def test_adaptive_waits_until_prior_close_below_200wma(self):
        btc,fx=synthetic(dip_date="2016-01-04",dip=50.)
        result=run_cohort(btc,fx,enrolment_date="2016-01-04")
        self.assertEqual(result["trigger_date"],"2016-01-05")
        adaptive=next(r for r in result["results"] if r["policy"]=="adaptive_recovery")
        self.assertGreater(adaptive["buy_count"],0)
        self.assertGreater(adaptive["btc_accumulated"],0)

    def test_flat_price_no_below_200wma_trigger(self):
        btc,fx=synthetic(dip_date="2019-01-01",dip=100.)
        result=run_cohort(btc,fx,enrolment_date="2016-01-04")
        self.assertIsNone(result["trigger_date"])
        adaptive=next(r for r in result["results"] if r["policy"]=="adaptive_recovery")
        self.assertEqual(adaptive["buy_count"],0)
        self.assertEqual(adaptive["btc_accumulated"],0.)
        self.assertEqual(adaptive["cash_budget_deployed_pct"],0.)

    def test_all_policy_purchases_respect_weekly_cap_and_cash(self):
        btc,fx=synthetic(dip_date="2016-01-04",dip=50.)
        result=run_cohort(btc,fx,enrolment_date="2016-01-04")
        for row in result["results"]:
            self.assertLessEqual(row["total_cash_outlay_aud"],292383.*1.02)
            self.assertGreaterEqual(row["cash_remaining_aud"],0.)
            self.assertLessEqual(row["cash_budget_deployed_pct"],100.01)
        self.assertAlmostEqual(result["weekly_cap_aud"],25500.)

    def test_cash_yield_is_accrued_on_waiting_cash(self):
        btc,fx=synthetic(dip_date="2019-01-01",dip=100.)
        result=run_cohort(btc,fx,enrolment_date="2016-01-04",cash_yield=.05)
        adaptive=next(r for r in result["results"] if r["policy"]=="adaptive_recovery")
        expected=292383.*(1.05**(728/365.25))
        self.assertAlmostEqual(adaptive["cash_remaining_aud"],expected,delta=5.)

    def test_weekly_dca_is_not_affected_by_wma_trigger(self):
        btc,fx=synthetic(dip_date="2019-01-01",dip=100.)
        result=run_cohort(btc,fx,enrolment_date="2016-01-04")
        fixed=next(r for r in result["results"] if r["policy"]=="fixed_weekly")
        below=next(r for r in result["results"] if r["policy"]=="remaining_cash_2_5pct_below_200wma")
        self.assertEqual(fixed["buy_count"],104)
        self.assertEqual(below["buy_count"],0)

    def test_summary_uses_paired_fixed_weekly_cohort(self):
        rows=[]
        for enrol in ("2020-01-06","2022-01-03"):
            for policy,btc,equity in (("fixed_weekly",1.,100.),("adaptive_recovery",1.1,110.)):
                rows.append({"enrolment_date":enrol,"validation_split":"train" if enrol<"2022-01-01" else "holdout",
                            "policy":policy,"btc_accumulated":btc,"terminal_equity_aud":equity,
                            "effective_vwap_aud_per_btc":100.,"cash_remaining_aud":10.,
                            "cash_budget_deployed_pct":90.,"vwap_premium_to_cohort_low_pct":10.})
        s=summary_table(pd.DataFrame(rows))
        a=s.loc[s.policy=="adaptive_recovery"].iloc[0]
        self.assertAlmostEqual(a["median_paired_btc_uplift_vs_fixed_weekly_pct"],10.)
        self.assertEqual(a["cohort_win_rate_btc_vs_fixed_weekly_pct"],100.)

    def test_invalid_cash_inputs_fail_closed(self):
        btc,fx=synthetic(dip_date="2016-01-04",dip=50.)
        with self.assertRaises(ValueError):
            run_cohort(btc,fx,enrolment_date="2016-01-04",budget_aud=-1)
        with self.assertRaises(ValueError):
            run_cohort(btc,fx,enrolment_date="2016-01-04",weekly_cap_pct=0)

if __name__=="__main__":
    unittest.main()
