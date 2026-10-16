import unittest

import numpy as np
import pandas as pd

from engines.research.verified_recent_price_bridge import (
    append_verified_prices, asof_on_mondays, expanding_aud_powerlaw_risk,
    parse_blockchain_price, parse_frankfurter_fx,
    weighted_entry_from_synthetic_orders, nearest_historical_fx,
    first_causal_gate_week, evaluate_causal_drawdown_entry_gates,
    historical_entry_gate_transfer,
)


def master():
    idx=pd.date_range("2026-07-06", periods=12, freq="W-MON", tz="UTC")
    vals=np.array([100_000.+i*100 for i in range(12)])
    return pd.DataFrame({"btc_price_aud":vals,
                         "risk_score":[.3]*12},index=idx)


class PublicPriceBridgeTests(unittest.TestCase):
    def test_parse_source_chart_and_fx(self):
        prices=parse_blockchain_price({"values":[{"x":1783296000,"y":60000},
                                                      {"x":1783382400,"y":61000}]})
        self.assertEqual(len(prices),2)
        self.assertEqual(float(prices.iloc[0,0]),60000.)
        fx=parse_frankfurter_fx({"rates":{"2026-07-06":{"AUD":1.5},
                                          "2026-07-07":{"AUD":1.6}}})
        self.assertAlmostEqual(float(fx.iloc[0,0]),1.5)

    def test_asof_never_uses_future_fx_or_price(self):
        days=pd.date_range("2026-07-06",periods=36,freq="D",tz="UTC")
        price=pd.DataFrame({"btc_usd":[60000.]*len(days)},index=days)
        fx=pd.DataFrame({"aud_per_usd":[1.5,1.6,1.7,1.8,1.9]},
                        index=pd.to_datetime([
                          "2026-07-06","2026-07-13","2026-07-20",
                          "2026-07-27","2026-08-03"],utc=True))
        w=asof_on_mondays(price,fx,start="2026-07-06",end="2026-08-03")
        self.assertEqual(len(w),5)
        self.assertAlmostEqual(w.iloc[0]["btc_price_aud"],90000.)
        self.assertTrue((w["fx_source_date"]<=w.index).all())
        self.assertTrue((w["price_source_date"]<=w.index).all())

    def test_stale_fx_rejected_not_silently_forwardfilled(self):
        days=pd.date_range("2026-07-06",periods=40,freq="D",tz="UTC")
        price=pd.DataFrame({"btc_usd":[60000.]*len(days)},index=days)
        fx=pd.DataFrame({"aud_per_usd":[1.5]},
                        index=pd.to_datetime(["2026-07-06"],utc=True))
        with self.assertRaisesRegex(ValueError,"Missing/stale"):
            asof_on_mondays(price,fx,start="2026-07-06",end="2026-08-03")

    def test_no_append_when_overlap_mismatch(self):
        d=master()
        p=pd.DataFrame({"btc_price_aud":d["btc_price_aud"]*1.4},index=d.index)
        ix=d.index[-1]+pd.Timedelta(weeks=1)
        p.loc[ix,"btc_price_aud"]=115000
        with self.assertRaisesRegex(ValueError,"overlap mismatch"):
            append_verified_prices(d,p,asof=ix)

    def test_append_keeps_all_original_prices_and_never_extends_old_risk(self):
        d=master()
        p=pd.DataFrame({"btc_price_aud":d["btc_price_aud"]*1.01},
                       index=d.index)
        monday=d.index[-1]+pd.Timedelta(weeks=1)
        p.loc[monday,"btc_price_aud"]=95000.
        merged,audit=append_verified_prices(d,p,asof=monday)
        self.assertEqual(len(merged),len(d)+1)
        self.assertTrue(np.array_equal(merged.loc[d.index,"btc_price_aud"].to_numpy(),
                                      d["btc_price_aud"].to_numpy()))
        self.assertNotIn("risk_score",merged.columns)
        self.assertEqual(audit["new_public_weeks"],1)

    def test_weighted_2026_dca_error_targets_are_not_arithmetic_average(self):
        fx=pd.DataFrame({"aud_per_usd":[1.0,1.0]},
                        index=pd.to_datetime(["2026-06-01","2026-06-08"],utc=True))
        o=[
            {"date":"2026-06-01 00:00:00+00:00","side":"BUY",
             "gross_aud":150003.,"btc":150000./110000.},
            {"date":"2026-06-08 00:00:00+00:00","side":"BUY",
             "gross_aud":50003.,"btc":50000./140000.}
        ]
        a=weighted_entry_from_synthetic_orders(o,fx,low_usd=100000)
        self.assertAlmostEqual(a["average_entry_usd_per_btc"],116229.90,places=1)
        self.assertAlmostEqual(a["error_from_observed_low_pct"],16.23,places=1)
        self.assertTrue(a["within_25pct"])
        self.assertAlmostEqual(a["aud_capital_deployed_pct"],40.001,delta=.002)

    def test_weighted_entry_uses_transaction_day_fx_and_rejects_stale(self):
        fx=pd.DataFrame({"aud_per_usd":[2.,4.]},
                        index=pd.to_datetime(["2026-06-01","2026-06-08"],utc=True))
        o=[
            {"date":"2026-06-01 00:00:00+00:00","side":"BUY",
             "gross_aud":200000.,"btc":1.},
            {"date":"2026-06-08 00:00:00+00:00","side":"BUY",
             "gross_aud":200000.,"btc":1.}
        ]
        a=weighted_entry_from_synthetic_orders(o,fx,low_usd=60000)
        self.assertAlmostEqual(a["average_entry_usd_per_btc"],75000.)
        self.assertAlmostEqual(a["error_from_observed_low_pct"],25.)
        bad=[{"date":"2026-06-20 00:00:00+00:00","side":"BUY",
              "gross_aud":1000,"btc":.01}]
        with self.assertRaisesRegex(ValueError,"unavailable"):
            weighted_entry_from_synthetic_orders(bad,fx)
        self.assertAlmostEqual(
            nearest_historical_fx(fx,"2026-06-07 00:00:00+00:00"),2.)

    def test_entry_gate_is_next_week_of_past_only_drawdown(self):
        idx=pd.date_range("2025-01-06",periods=90,freq="W-MON",tz="UTC")
        price=np.array([100000.]*55 + [100000.-2000*i for i in range(35)])
        frame=pd.DataFrame({"btc_price_aud":price,"risk_score":[.1]*90},index=idx)
        trigger,drop=first_causal_gate_week(frame,drawdown=.30,
                                             start_date="2026-01-01")
        self.assertIsNotNone(trigger)
        self.assertGreaterEqual(trigger,pd.Timestamp("2026-01-01",tz="UTC"))
        before=np.where(idx==trigger)[0][0]
        prev_price=price[before-1]
        trailing_max=float(price[before-52:before].max())
        self.assertGreaterEqual(1-prev_price/trailing_max,.30)
        # Any future price change cannot cause an earlier gate to move.
        later=frame.copy()
        later.iloc[before+2:,0]=999999.
        t2,_=first_causal_gate_week(later,drawdown=.30,
                                    start_date="2026-01-01")
        self.assertEqual(trigger,t2)
        empty,_=first_causal_gate_week(
            frame.assign(btc_price_aud=100000.),
            drawdown=.50,start_date="2026-01-01")
        self.assertIsNone(empty)

    def test_drawdown_gates_can_miss_a_full_rising_market(self):
        # Explicit negative control: no deep correction at all in 2020.
        idx=pd.date_range("2018-01-01",periods=160,freq="W-MON",tz="UTC")
        vals=[100000. if i<104 else 100000.+1000*(i-104) for i in range(160)]
        history=pd.DataFrame({"btc_price_aud":vals,
                              "risk_score":[.2]*160},index=idx)
        out=historical_entry_gate_transfer(history,years=(2020,))
        self.assertEqual(len(out["fixed_one_year_eras"]),1)
        rows=out["fixed_one_year_eras"][0]["scenarios"]
        self.assertEqual(len(rows),4)
        for row in rows[1:]:
            self.assertFalse(row["triggered"])
            self.assertEqual(row["BTC_held"],0)
            self.assertEqual(row["ending_equity_aud"],500000)
            self.assertLess(row["relative_to_matched_hold_pct"],0)

    def test_predeclared_gates_keep_full_capital_until_activation(self):
        idx=pd.date_range("2024-01-01",periods=142,freq="W-MON",tz="UTC")
        prices=np.array([100000.]*110+
                        [max(35000.,100000.-3000*i) for i in range(32)])
        frame=pd.DataFrame({"btc_price_aud":prices,
                            "risk_score":[.1]*142},index=idx)
        fx=pd.DataFrame({"aud_per_usd":[1.5]*len(idx)},
                        index=idx)
        rows=evaluate_causal_drawdown_entry_gates(frame,fx)
        self.assertEqual(len(rows),3)
        for x in rows:
            self.assertIn("triggered",x)
            if x["triggered"]:
                self.assertGreaterEqual(pd.Timestamp(x["gate_execution_date"]),
                                        pd.Timestamp("2026-01-01",tz="UTC"))
                self.assertGreaterEqual(x["cash_remaining_aud"],0)
                self.assertLessEqual(x["entry_vs_reported_low"]["aud_capital_deployed_pct"],100.0001)

    def test_no_orders_never_claims_25pct_success(self):
        empty=weighted_entry_from_synthetic_orders([],pd.DataFrame())
        self.assertIsNone(empty["within_25pct"])
        self.assertIsNone(empty["error_from_observed_low_pct"])

    def test_powerlaw_uses_only_prefix_price_information(self):
        idx=pd.date_range("2021-01-04",periods=220,freq="W-MON",tz="UTC")
        vals=np.array([12000.*(1+.01*i) for i in range(len(idx))])
        base=pd.DataFrame({"btc_price_aud":vals},index=idx)
        original=expanding_aud_powerlaw_risk(base)
        revised=base.copy()
        revised.iloc[180:]=1_000_000.
        changed=expanding_aud_powerlaw_risk(revised)
        np.testing.assert_allclose(
            original["risk_score"].iloc[:180].to_numpy(),
            changed["risk_score"].iloc[:180].to_numpy(),
            equal_nan=True)
        self.assertTrue(original["risk_score"].iloc[:104].isna().all())
        self.assertTrue(original["risk_score"].iloc[120:].notna().all())


if __name__ == "__main__":
    unittest.main()
