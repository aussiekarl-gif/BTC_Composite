"""Review-only Production historical calculation correction; no DCA Today changes."""
import unittest
import datetime as dt

import numpy as np
import pandas as pd

from engines.production.production_model import (
    align_historical_fx_strict, align_fx_to_dates,
    simulate_dca_backtest,add_risk_indicators,
    SMART_DCA_POINTS,
)
from engines.research.production_causal_budget_audit import PARAMS

START=pd.Timestamp("2020-01-15",tz="UTC")
END=pd.Timestamp("2020-09-01",tz="UTC")


def input_history():
    dates=pd.date_range("2015-01-01","2021-01-01",freq="D",tz="UTC")
    prices=100*np.exp(np.arange(len(dates))*.0009+
                      .16*np.sin(np.arange(len(dates))/70.))
    data=pd.DataFrame({
        "price":prices,
        "mvrv_z":.5+1.5*(np.sin(np.arange(len(dates))/130.)+1)/2,
        "fear_greed":50+20*np.sin(np.arange(len(dates))/20.),
        "regime_score":np.nan,
        "usd_per_aud":.70,
    },index=dates)
    params={
        **PARAMS,
        "risk_model":"Composite V3.6",
        "start_date":START,
        "end_date":END,
        "day_of_week":0,
        "fee_pct":0,
    }
    return data,params


class HistoricalProductionIntegrityTests(unittest.TestCase):
    def test_strict_fx_prior_not_same_day_or_future(self):
        dates=pd.date_range("2020-01-06","2020-01-09",freq="D",tz="UTC")
        data=pd.DataFrame({"price":100},index=dates)
        fx=pd.Series([.60,.62,.65],index=pd.DatetimeIndex([
            pd.Timestamp("2020-01-03",tz="UTC"),
            pd.Timestamp("2020-01-07",tz="UTC"),
            pd.Timestamp("2020-01-09",tz="UTC")]))
        aligned=align_historical_fx_strict(data,fx)
        self.assertEqual(list(aligned["usd_per_aud"]),[.60,.60,.62,.62])
        self.assertTrue(aligned["price"].eq(100).all())

    def test_first_fx_after_price_cannot_bfill(self):
        dates=pd.date_range("2020-01-06","2020-01-08",freq="D",tz="UTC")
        p=pd.DataFrame({"price":100},index=dates)
        fx=pd.Series([.75],index=pd.DatetimeIndex([
            pd.Timestamp("2020-01-07",tz="UTC")]))
        self.assertEqual(float(align_fx_to_dates(
            p,fx).loc[dates[0],"usd_per_aud"]),.75)
        with self.assertRaisesRegex(ValueError,"strictly before"):
            align_historical_fx_strict(p,fx)

    def test_stale_or_missing_fx_is_visible_error_not_flat_070(self):
        p=pd.DataFrame({"price":[100]},index=pd.DatetimeIndex([
            pd.Timestamp("2020-04-01",tz="UTC")]))
        with self.assertRaisesRegex(ValueError,"unavailable"):
            align_historical_fx_strict(p,None)
        fx=pd.Series([.70],index=pd.DatetimeIndex([
            pd.Timestamp("2020-03-01",tz="UTC")]))
        with self.assertRaisesRegex(ValueError,"older"):
            align_historical_fx_strict(p,fx)
        self.assertEqual(align_fx_to_dates(
            p,None).iloc[0]["usd_per_aud"],.70)

    def test_fx_zero_missing_duplicates_or_inverted_history_fails_closed(self):
        p=pd.DataFrame({"price":100},index=pd.date_range(
            "2020-01-06","2020-01-07",freq="D",tz="UTC"))
        idx=pd.DatetimeIndex([pd.Timestamp("2020-01-03",tz="UTC")])
        for value in (0,np.nan,-.01):
            with self.assertRaisesRegex(ValueError,"invalid"):
                align_historical_fx_strict(p,pd.Series([value],index=idx))
        with self.assertRaisesRegex(ValueError,"unavailable"):
            align_historical_fx_strict(p,pd.Series(
                [.7,.8],index=idx.repeat(2)))
        with self.assertRaisesRegex(ValueError,"maximum age"):
            align_historical_fx_strict(p,pd.Series([.7],index=idx),
                                       max_age_days=99)

    def test_backtest_warms_prior_risk_before_start(self):
        df,params=input_history()
        historical,_=simulate_dca_backtest(
            df,params,1000.,"Weekly","Risk-Scaled DCA",
            risk_curve=SMART_DCA_POINTS)
        self.assertFalse(historical.empty)
        first=pd.Timestamp(historical.iloc[0]["date"])
        target=add_risk_indicators(
            df.loc[:END],"Composite V3.6",params)
        self.assertAlmostEqual(
            float(historical.iloc[0]["risk_score"]),
            float(target.loc[first,"risk_score"]),places=10)
        self.assertAlmostEqual(
            float(historical.iloc[0]["dca_multiplier"]),
            float(np.interp(
                historical.iloc[0]["risk_score"],
                *zip(*SMART_DCA_POINTS))),places=7)

    def test_later_deployment_start_does_not_rewrite_same_date_risk(self):
        df,params=input_history()
        short,_=simulate_dca_backtest(
            df,{**params,"start_date":pd.Timestamp(
                "2020-04-15",tz="UTC")},1000.,"Daily","Risk-Scaled DCA",
            risk_curve=SMART_DCA_POINTS)
        long,_=simulate_dca_backtest(
            df,params,1000.,"Daily","Risk-Scaled DCA",
            risk_curve=SMART_DCA_POINTS)
        overlap=long.set_index("date").loc[short["date"]]
        np.testing.assert_allclose(
            short["risk_score"].to_numpy(float),
            overlap["risk_score"].to_numpy(float),
            rtol=0,atol=1e-12)
        np.testing.assert_allclose(
            short["dca_multiplier"].to_numpy(float),
            overlap["dca_multiplier"].to_numpy(float),
            rtol=0,atol=1e-12)

    def test_future_price_or_mvrv_cannot_revise_preterminal_trades(self):
        df,params=input_history()
        first,_=simulate_dca_backtest(
            df,params,1000.,"Weekly","Risk-Scaled DCA",
            risk_curve=SMART_DCA_POINTS)
        changed=df.copy()
        changed.loc[changed.index>END,"price"]*=25.
        changed.loc[changed.index>END,"mvrv_z"]=10.
        other,_=simulate_dca_backtest(
            changed,params,1000.,"Weekly","Risk-Scaled DCA",
            risk_curve=SMART_DCA_POINTS)
        pd.testing.assert_frame_equal(
            first.reset_index(drop=True),other.reset_index(drop=True))

    def test_plain_and_smart_share_exact_execution_dates(self):
        df,params=input_history()
        plain,_=simulate_dca_backtest(
            df,params,1000.,"Weekly","Plain DCA")
        smart,_=simulate_dca_backtest(
            df,params,1000.,"Weekly","Risk-Scaled DCA",
            risk_curve=SMART_DCA_POINTS)
        self.assertEqual(list(plain["date"]),list(smart["date"]))
        self.assertTrue(plain["actual_buy_aud"].eq(1000).all())
        self.assertTrue(smart["dca_multiplier"].ge(.05).all())
        self.assertTrue(smart["dca_multiplier"].le(2.75).all())


if __name__=="__main__":
    unittest.main()
