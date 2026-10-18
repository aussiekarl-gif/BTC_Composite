"""Research-only evidence that V5.8.2 historical budget normalization knows future."""
import unittest

import numpy as np
import pandas as pd

from engines.production.production_model import (
    SMART_DCA_POINTS,apply_equal_capital_allocator,
    align_fx_to_dates,interpolate,
)
from engines.research.production_causal_budget_audit import (
    equal_capital_hindsight_weights,matched_replay,
    build_production_risk_from_archived_provider,
)

START=pd.Timestamp("2020-01-15",tz="UTC")
END=pd.Timestamp("2020-09-01",tz="UTC")


def fixture():
    dates=pd.date_range("2013-01-01","2021-01-01",freq="D",tz="UTC")
    values=100.*np.exp(np.arange(len(dates))*.0004)
    score=np.clip(.45 + .18*np.sin(np.arange(len(dates))/29),0,1)
    risk=pd.DataFrame({
        "price":values,"risk_score":score,
        "risk_components_available":5,
    },index=dates)
    fx=pd.DataFrame({"aud_per_usd":1.5},index=pd.date_range(
        "2012-12-01","2021-01-01",freq="D",tz="UTC"))
    return risk,fx


class ProductionCausalAuditTests(unittest.TestCase):
    def test_actual_production_allocator_uses_total_future_weights(self):
        # Tomorrow's unknown high multiplier changes the HISTORICAL spend.
        rows=pd.DataFrame({
            "actual_buy_aud":[1.,2.,3.],
            "btc_price_aud":[100.,110.,120.]
        })
        prior,_=apply_equal_capital_allocator(
            rows.iloc[:2],total_budget_aud=1200.)
        expanded,_=apply_equal_capital_allocator(
            rows,total_budget_aud=1200.)
        self.assertAlmostEqual(float(prior["actual_buy_aud"].iloc[0]),400.)
        self.assertAlmostEqual(float(expanded["actual_buy_aud"].iloc[0]),200.)
        self.assertNotEqual(float(prior["btc_bought"].iloc[0]),
                            float(expanded["btc_bought"].iloc[0]))
        self.assertAlmostEqual(float(expanded["actual_buy_aud"].sum()),1200.)

    def test_fixed_hindsight_allocation_reproduces_actual_production_allocator(self):
        weights=np.array([2.75,1.0,.05,1.5])
        actual,_=apply_equal_capital_allocator(
            pd.DataFrame({"actual_buy_aud":weights,
                          "btc_price_aud":np.ones(4)*120.}),
            total_budget_aud=400000.)
        frozen=equal_capital_hindsight_weights(weights,400000.)
        np.testing.assert_allclose(
            actual["actual_buy_aud"].to_numpy(float),
            frozen,rtol=0,atol=1e-8)

    def test_causal_weekly_sizing_changes_only_future_not_prior_orders(self):
        risk,fx=fixture()
        original=matched_replay(
            risk,fx,start=START,terminal=END,budget_aud=40000.)
        updated=risk.copy()
        switch=pd.Timestamp("2020-06-01",tz="UTC")
        updated.loc[updated.index>=switch,"risk_score"]=.95
        altered=matched_replay(
            updated,fx,start=START,terminal=END,budget_aud=40000.)
        for policy in ("causal_live_remaining_cash_weeks",
                       "historical_omniscient_equal_capital"):
            earlier=lambda x: [o for o in x["strategies"][policy]["orders"]
                    if o["date"]<str(switch.date())]
            if policy=="causal_live_remaining_cash_weeks":
                self.assertEqual(earlier(original),earlier(altered))
            else:
                self.assertNotEqual(earlier(original),earlier(altered))

    def test_no_fabricated_buy_if_weekly_risk_missing(self):
        risk,fx=fixture()
        risk.loc["2020-01-15","risk_score"]=np.nan
        with self.assertRaisesRegex(ValueError,"prior-production-risk"):
            matched_replay(risk,fx,start=pd.Timestamp(
                "2020-01-14",tz="UTC"),terminal=END)

    def test_all_scenarios_cannot_exceed_initial_AUD_cash(self):
        risk,fx=fixture()
        row=matched_replay(risk,fx,start=START,terminal=END)
        for policy,x in row["strategies"].items():
            self.assertGreaterEqual(x["cash_aud"],0.)
            self.assertLessEqual(x["cash_aud"],400000.)
            self.assertGreaterEqual(x["btc"],0.)
            self.assertLessEqual(x["fills"],len(pd.date_range(
                START+pd.Timedelta(days=1),END,freq="7D")))
            self.assertTrue(x["orders"])
        self.assertEqual(len(row["strategies"]),3)
        self.assertEqual(row["initial_cash_aud"],400000.)

    def test_exact_multiplier_curve_points_not_tuned(self):
        for risk,expected in SMART_DCA_POINTS:
            self.assertAlmostEqual(interpolate(SMART_DCA_POINTS,risk),expected)

    def test_original_production_fx_fallback_is_nonverified_constant(self):
        risk,_=fixture()
        sample=risk.head(3)[["price"]]
        converted=align_fx_to_dates(sample,None)
        self.assertTrue((converted["usd_per_aud"]==.70).all())
        # Clearly document as DATA-SAFETY GAP; we do NOT use this
        # fallback in our AUD matched audit: it requires prior dated FX.

    def test_matched_aud_replay_rejects_stale_fx_source(self):
        risk,fx=fixture()
        with self.assertRaisesRegex(ValueError,"No safely prior"):
            matched_replay(risk,fx.loc[:"2019-12-01"],start=START,
                           terminal=END)

    def test_archived_mvrv_not_replaced_by_fabricated_fear_greed(self):
        dates=pd.date_range("2013-01-01","2020-01-01",freq="D",tz="UTC")
        sample=pd.DataFrame({
            "price_usd":100*np.exp(np.arange(len(dates))*.0004),
            "mvrv_z":np.linspace(0,3,len(dates)),
        },index=dates)
        out=build_production_risk_from_archived_provider(sample)
        self.assertTrue(out["fear_greed_score"].isna().all())
        self.assertTrue(out["risk_score"].iloc[-1]>=0)
        self.assertGreaterEqual(out["risk_components_available"].iloc[-1],4)

    def test_reject_duplicate_missing_history_and_bad_capital(self):
        risk,fx=fixture()
        duplicate=pd.concat([risk,risk.loc[[START]]])
        with self.assertRaisesRegex(ValueError,"Valid date-indexed"):
            matched_replay(duplicate,fx,start=START,terminal=END)
        with self.assertRaisesRegex(ValueError,"Invalid initial"):
            matched_replay(risk,fx,start=START,terminal=END,budget_aud=0)
        with self.assertRaisesRegex(ValueError,"Missing exact"):
            matched_replay(risk.drop(START+pd.Timedelta(days=1)),
                           fx,start=START,terminal=END)


if __name__=="__main__":
    unittest.main()
