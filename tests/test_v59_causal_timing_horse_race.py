"""Deterministic timing horse-race safety, causal input and budget tests."""
from __future__ import annotations

from datetime import date, timedelta
import unittest
import pandas as pd
import numpy as np

from engines.research.v59_causal_timing_horse_race import (
    CAPITAL_AUD, POLICIES, policy_multiplier, simulate, build_weekly_rows,
    cohort_windows, evaluate, WEEKS,
)


def row(i, *, risk=.05, aud=100000., dd=-.5, ratio=.8, rising=True):
    monday = date(2021, 1, 4) + timedelta(weeks=i)
    return {
        "date":monday,"signal_date":monday-timedelta(days=1),
        "btc_price_aud":aud,"risk_score":risk,
        "risk_score_source":"Walk-forward Power Law",
        "ratio_to_200wma":ratio,"drawdown_365":dd,
        "ratio_to_50dma":1.02,"sma50_rising":rising,
    }


class CausalTimingTests(unittest.TestCase):
    def test_risk_band_and_timing_candidate_gates(self):
        good=row(0)
        self.assertEqual(policy_multiplier("risk_3x", good), 3.)
        self.assertEqual(policy_multiplier("risk_1x", good), 1.)
        self.assertEqual(policy_multiplier("risk_2x", good), 2.)
        self.assertEqual(policy_multiplier("risk_3x_below_200wma", good), 3.)
        self.assertEqual(policy_multiplier("risk_3x_drawdown_40pct", good), 3.)
        self.assertEqual(policy_multiplier("risk_3x_50dma_rising", good), 3.)
        high=row(0, risk=.51)
        self.assertEqual(policy_multiplier("risk_3x", high), 0.)
        self.assertEqual(policy_multiplier("risk_1x", high), 0.)
        lesscheap=row(0, risk=.33, ratio=1.2, dd=-.15, rising=False)
        self.assertEqual(policy_multiplier("risk_3x_below_200wma", lesscheap), 0.)
        self.assertEqual(policy_multiplier("risk_3x_drawdown_25pct", lesscheap), 0.)
        self.assertEqual(policy_multiplier("risk_3x_50dma_rising", lesscheap), 0.)
        self.assertEqual(policy_multiplier("risk_3x_risk_le_020", lesscheap), 0.)
        with self.assertRaises(ValueError):
            policy_multiplier("risk_3x",dict(good,risk_score_source="Neutral fallback"))

    def test_cash_interest_accrues_when_not_buying(self):
        rows=[row(i,risk=.99) for i in range(104)]
        no_int=simulate(rows, policy="risk_3x", cash_yield=0.,reserve_fraction=0.)
        yes_int=simulate(rows, policy="risk_3x", cash_yield=.05,reserve_fraction=0.)
        self.assertEqual(no_int["buy_count"],0)
        self.assertEqual(yes_int["buy_count"],0)
        self.assertAlmostEqual(no_int["cash_aud"],CAPITAL_AUD)
        self.assertGreater(yes_int["cash_aud"],CAPITAL_AUD*1.10)
        self.assertGreater(yes_int["interest_earned_aud"],50000)

    def test_all_risk_scenarios_never_exceed_5pct_each_week(self):
        cohort=[row(i) for i in range(104)]
        for p in POLICIES:
            with self.subTest(policy=p):
                res=simulate(cohort,policy=p,cash_yield=.05,reserve_fraction=.10)
                self.assertGreaterEqual(res["cash_aud"], .10*CAPITAL_AUD-1.e-6)
                self.assertGreaterEqual(res["btc_units"],0)
                self.assertLessEqual(res["net_invested_aud"],104*CAPITAL_AUD*.05+1.e-6)
                self.assertGreaterEqual(res["btc_50pct_shock_equity_aud"],0)

    def test_future_price_can_change_fill_but_not_prior_risk_gate(self):
        one=row(0, risk=.03, aud=50000.)
        two=dict(one, btc_price_aud=90000.)
        self.assertEqual(policy_multiplier("risk_3x",one),policy_multiplier("risk_3x",two))
        self.assertEqual(policy_multiplier("risk_3x_below_200wma",one),
                         policy_multiplier("risk_3x_below_200wma",two))

    def test_same_day_signal_is_rejected(self):
        r=row(0);r["signal_date"]=r["date"]
        with self.assertRaisesRegex(ValueError,"previous daily signal"):
            simulate([r],policy="risk_3x",cash_yield=.05,reserve_fraction=0.)

    def test_missing_week_is_rejected(self):
        with self.assertRaisesRegex(ValueError,"missing execution"):
            simulate([row(0),row(2)],policy="risk_3x",cash_yield=.05,reserve_fraction=0.)

    def test_build_weekly_uses_sunday_signal_and_prior_fx(self):
        idx=pd.date_range("2015-01-01","2021-02-15",freq="D",tz="UTC")
        data=pd.DataFrame({
            "price":np.linspace(10000.,55000.,len(idx)),
            "risk_score":np.repeat(.05,len(idx)),
            "risk_score_source":["Walk-forward Power Law"]*len(idx),
        },index=idx)
        fx_idx=pd.date_range("2015-01-01","2021-02-15",freq="B",tz="UTC")
        fx=pd.Series(.7,index=fx_idx)
        # Monday FX differs from Friday. It cannot enter the current trade.
        fx.at[pd.Timestamp("2021-02-08",tz="UTC")]=.99
        fx.at[pd.Timestamp("2021-02-05",tz="UTC")]=.66
        rows=build_weekly_rows(data,fx)
        lookup={r["date"]:r for r in rows}
        target=lookup[date(2021,2,8)]
        self.assertEqual(target["signal_date"],date(2021,2,7))
        self.assertEqual(target["fx_date"],date(2021,2,5))
        self.assertAlmostEqual(target["usd_per_aud"],.66)
        self.assertEqual(target["risk_score"],.05)

    def test_completed_cohorts_do_not_use_future_or_partial_windows(self):
        rows=[row(i) for i in range(52)]
        with self.assertRaisesRegex(ValueError, "No fully supported"):
            cohort_windows(rows)

    def test_no_data_in_report_is_not_silently_assumed(self):
        with self.assertRaises(ValueError):
            build_weekly_rows(pd.DataFrame(),pd.Series(dtype=float))


if __name__ == "__main__":
    unittest.main()
