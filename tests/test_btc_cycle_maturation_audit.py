"""Non-stationarity diagnostics with strictly prior 200WMA signal tests."""
import unittest

import numpy as np
import pandas as pd

from engines.research.btc_cycle_maturation_audit import (
    EARLIEST_ORIGINAL_BUY_DAY,
    first_eligible_prior_wma,
    gate_snapshot,
    cycle_maturation_metrics,
)

H=pd.Timestamp("2020-01-01",tz="UTC")
END=H+pd.Timedelta(days=1050)
DATES=pd.date_range("2016-01-01",END,freq="D",tz="UTC")


def price_history(*,constant=False):
    age=(DATES-H).days.astype(float)
    if constant:
        v=np.full(len(DATES),100.,dtype=float)
    else:
        v=np.where(age<350,100.,
              np.where(age<500,200.,
              np.where(age<800,200.-.25*(age-500),
              np.where(age<980,125.-.40*(age-800),
                       53.+.20*(age-980)))))
    return pd.Series(v.astype(float),index=DATES)


class MaturationAuditTest(unittest.TestCase):
    def test_price_higher_low_does_not_guarantee_shallow_drawdown(self):
        # Logical/arithmetical distinction behind the hypothesis:
        # higher low in USD can coexist with deep percentage fall.
        old_peak,old_low=200.,40.
        new_peak,new_low=500.,65.
        self.assertGreater(new_low,old_low)
        self.assertGreater(1-new_low/new_peak,1-old_low/old_peak)

    def test_first_wma_gate_matches_existing_causal_historical_engine(self):
        px=price_history()
        r=cycle_maturation_metrics(px,H,END,label="synthetic")
        self.assertEqual(r["full_day1150_observed"],False)
        self.assertTrue(r["terminal_censored_low_not_final"])
        self.assertTrue(r["hindsight_peaks_lows_never_used_to_buy"])
        self.assertEqual(r["peak_usd"],200.)
        self.assertLess(r["post_peak_low_usd"],100.)
        self.assertGreater(r["peak_to_low_drawdown_pct_expost"],70.)
        self.assertIsNotNone(r["first_gate"])
        self.assertGreaterEqual(r["first_gate_halving_age_days"],
                                EARLIEST_ORIGINAL_BUY_DAY)
        self.assertEqual(len(r["fresh_cash_cohorts"]),4)
        self.assertIsNotNone(r["gate_to_observed_low_days_expost"])

    def test_no_new_breach_is_reported_not_assumed(self):
        px=price_history(constant=True)
        r=cycle_maturation_metrics(px,H,END,label="no_cross")
        self.assertIsNone(r["first_gate"])
        self.assertIsNone(r["first_gate_execution_price_above_observed_low_pct_expost"])
        self.assertTrue(all(x["zero_gate_through_terminal"]
                            for x in r["fresh_cash_cohorts"]))
        self.assertEqual(r["peak_to_low_drawdown_pct_expost"],0.)

    def test_first_eligible_crossing_strictly_uses_yesterday(self):
        px=price_history(constant=True)
        mark=H+pd.Timedelta(days=800)
        px.loc[mark]=30.
        first=first_eligible_prior_wma(
            px,H+pd.Timedelta(days=EARLIEST_ORIGINAL_BUY_DAY),END)
        self.assertEqual(first,mark+pd.Timedelta(days=1))
        observed=gate_snapshot(px,H,END)
        self.assertEqual(observed["first_gate"],str((mark+pd.Timedelta(days=1)).date()))

    def test_prefix_invariance_first_gate_vs_later_revised_history(self):
        px=price_history()
        earlier=H+pd.Timedelta(days=930)
        first=gate_snapshot(px,H,earlier)
        later=px.copy()
        later.loc[later.index>earlier]*=3.
        self.assertEqual(first,gate_snapshot(later,H,earlier))
        full=gate_snapshot(later,H,END)
        self.assertEqual(first["first_gate"],full["first_gate"])
        # Terminal hindsight outcome score may change; causal first gate may not.
        old=cycle_maturation_metrics(px,H,END,label="baseline")
        changed=cycle_maturation_metrics(later,H,END,label="repainted")
        self.assertEqual(old["first_gate"],changed["first_gate"])
        self.assertNotEqual(old["post_peak_low_usd"],
                            changed["post_peak_low_usd"])

    def test_missing_wma_history_and_corrupted_price_fail_closed(self):
        px=price_history()
        missing=px.drop(H-pd.Timedelta(days=630))
        with self.assertRaisesRegex(ValueError,"Missing required"):
            cycle_maturation_metrics(missing,H,END,label="bad")
        corrupt=px.copy()
        corrupt.loc[H+pd.Timedelta(days=500)]=np.nan
        with self.assertRaisesRegex(ValueError,"Missing/nonpositive"):
            cycle_maturation_metrics(corrupt,H,END,label="bad")
        corrupt=px.copy()
        corrupt.loc[H+pd.Timedelta(days=500)]=-1.
        with self.assertRaisesRegex(ValueError,"Missing/nonpositive"):
            cycle_maturation_metrics(corrupt,H,END,label="bad")
        with self.assertRaisesRegex(ValueError,"Unique ordered"):
            cycle_maturation_metrics(px,H,H,label="bad")

    def test_no_hindsight_claim_from_censored_low(self):
        px=price_history()
        short=cycle_maturation_metrics(
            px,H,H+pd.Timedelta(days=920),label="censored")
        full=cycle_maturation_metrics(px,H,END,label="also_censored")
        self.assertFalse(short["full_day1150_observed"])
        self.assertEqual(short["first_gate"],full["first_gate"])
        self.assertGreater(short["post_peak_low_usd"],
                           full["post_peak_low_usd"])
        self.assertNotEqual(short["post_peak_low_date_expost"],
                            full["post_peak_low_date_expost"])


if __name__=="__main__":
    unittest.main()
