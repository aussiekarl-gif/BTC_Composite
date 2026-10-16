"""Tests that A$500k only becomes tradeable in 2026, never in 2016."""
import unittest

import pandas as pd

from engines.research.adaptive_dca_execution import simulate_adaptive
from engines.research.real_2026_deployment_audit import (
    adaptive_account, benchmark_account, evaluate_cohorts,
)


def fixture():
    dates=pd.date_range("2025-01-06",periods=92,freq="W-MON",tz="UTC")
    prices=[100. + .5*j for j in range(92)]
    risks=[.10]*92
    return pd.DataFrame({"btc_price_aud":prices,"risk_score":risks},index=dates)


class Actual2026StartTests(unittest.TestCase):
    def test_older_market_data_warms_indicators_but_does_not_spend_cash(self):
        data=fixture()
        start="2026-01-01"
        result=simulate_adaptive(data,initial_cash=500000,
                                 deployment_start=start,
                                 confirm_drawdown=.10)
        self.assertTrue(result["trades"])
        self.assertTrue(all(pd.Timestamp(x["date"])>=pd.Timestamp(start,tz="UTC")
                            for x in result["trades"]))
        self.assertTrue(all(v==500000 for v in result["equity_path"][:50]))
        self.assertAlmostEqual(result["equity_path"][0],500000)

    def test_deployment_start_after_data_is_rejected(self):
        with self.assertRaises(ValueError):
            simulate_adaptive(fixture(),deployment_start="2030-01-01")

    def test_june_2026_start_not_january_or_2016(self):
        data=fixture()
        cohort=adaptive_account(data,"2026-06-19",confirm_drawdown=.10)
        first=pd.Timestamp(cohort["first_weekly_execution"])
        self.assertGreaterEqual(first,pd.Timestamp("2026-06-19",tz="UTC"))
        self.assertIsNone(cohort["first_order_date"] if cohort["actual_orders"]==0 else None)
        if cohort["first_order_date"]:
            self.assertGreaterEqual(pd.Timestamp(cohort["first_order_date"]),first)

    def test_immediate_buy_uses_first_observed_date_and_charges_3(self):
        data=fixture()
        result=benchmark_account(data,"2026-01-01","immediate_buy")
        self.assertEqual(result["buy_orders"],1)
        self.assertEqual(result["brokerage_aud"],3.)
        self.assertAlmostEqual(result["cash_left_aud"],0)
        self.assertGreater(result["btc_equivalent_held"],0)
        self.assertEqual(result["first_order_date"],
                         result["first_weekly_execution"])

    def test_equal_dca_is_baseline_only_and_does_not_buy_before_start(self):
        d=fixture()
        data=benchmark_account(d,"2026-06-19","equal_12week_buy")
        self.assertGreater(data["buy_orders"],1)
        self.assertLessEqual(data["buy_orders"],12)
        self.assertGreaterEqual(pd.Timestamp(data["first_order_date"]),
                                pd.Timestamp("2026-06-19",tz="UTC"))
        self.assertEqual(data["brokerage_aud"],3*data["actual_orders"])

    def test_cash_only_remains_unchanged_and_cgt_zero(self):
        result=benchmark_account(fixture(),"2026-01-01","cash_only")
        self.assertEqual(result["cash_left_aud"],500000)
        self.assertEqual(result["btc_equivalent_held"],0)
        self.assertEqual(result["actual_orders"],0)
        self.assertEqual(result["hypothetical_liquidation_value_after_cgt_aud"],500000)

    def test_all_policies_share_cohort_start_and_same_data_endpoint(self):
        data=fixture()
        r=evaluate_cohorts(data,dates=("2026-01-01","2026-06-19"))
        self.assertEqual(len(r["cohorts"]),2)
        for c in r["cohorts"]:
            self.assertEqual(len(c["results"]),7)
            starts={x["first_weekly_execution"] for x in c["results"]}
            ends={x["last_observed_date"] for x in c["results"]}
            self.assertEqual(len(starts),1)
            self.assertEqual(ends,{str(data.index[-1])})
            for x in c["results"]:
                self.assertGreaterEqual(x["cash_left_aud"],0)
                self.assertGreaterEqual(x["btc_equivalent_held"],0)
                self.assertGreaterEqual(x["actual_orders"],0)

    def test_prefix_invariance_of_orders_prior_to_modified_future(self):
        d=fixture()
        prefix=d.iloc[:76].copy()
        full=simulate_adaptive(d,deployment_start="2026-01-01",
                               confirm_drawdown=.10)
        changed=d.copy()
        changed.iloc[76:]=[100000., .99]
        updated=simulate_adaptive(changed,deployment_start="2026-01-01",
                                  confirm_drawdown=.10)
        before=[(x["date"],x["side"],x["gross_notional_aud"]) for x in full["trades"]
                if pd.Timestamp(x["date"])<d.index[76]]
        after=[(x["date"],x["side"],x["gross_notional_aud"]) for x in updated["trades"]
               if pd.Timestamp(x["date"])<d.index[76]]
        self.assertEqual(before,after)


if __name__=="__main__":
    unittest.main()
