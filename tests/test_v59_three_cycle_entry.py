"""Self-contained regression tests for first pre-2018 cycle and price-only timing."""
from datetime import date,timedelta
import math
import unittest

import pandas as pd

from engines.research import v59_three_cycle_entry as study


def mock_cycle_rows(*,halving=date(2012,11,28),weeks=100,trend=.0,
                    risk=False,move=None):
    first=study.next_monday(halving+timedelta(days=600))
    out=[]
    for i in range(weeks):
        day=first+timedelta(weeks=i)
        signal=day-timedelta(days=1)
        price=10000*(1+trend*i)
        if move is not None:
            price*=move(i)
        score=.05 if risk else None
        out.append({
            "date":day,"signal_date":signal,
            "halving_age_days":(signal-halving).days,
            "spot_sunday_usd":price,"btc_price_aud":price/.7,
            "ratio_to_200wma":1.10 if i<10 else .99,
            "risk_score":score,
            "risk_score_source":"Walk-forward Power Law" if risk else "UNAVAILABLE_PRICE_ONLY",
        })
    return out


class ThreeCycleEntryTests(unittest.TestCase):
    def test_full_daily_build_2015_uses_200_actual_sundays(self):
        dates=pd.date_range("2011-03-07","2016-11-01",freq="D",tz="UTC")
        prices=pd.DataFrame({"price":[200.+i for i in range(len(dates))]},index=dates)
        fixdays=pd.date_range("2011-03-07","2016-11-01",freq="B",tz="UTC")
        fx=pd.Series(.7,index=fixdays)
        rows=study.build_price_only_rows(prices,fx)
        self.assertEqual(rows[0]["signal_date"],date(2015,1,4))
        seasons=study.cycle_periods(rows)
        first=seasons[0]
        self.assertEqual(first["cycle"],"2014_15")
        self.assertFalse(first["not_simulated"])
        self.assertTrue(first["wma_warmup_left_truncated"])
        self.assertEqual(first["first_phase_monday"],"2015-01-05")
        self.assertEqual(first["status"],"COMPLETE_PRICE_FX_ONLY")
        self.assertIsNone(first["rows"][0]["risk_score"])
        self.assertIsNotNone(first["rows"][0]["wma_usd"])

    def test_future_prices_do_not_change_prior_sunday_ratios(self):
        dates=pd.date_range("2011-03-07","2016-01-31",freq="D",tz="UTC")
        p=pd.DataFrame({"price":[10+i*.1 for i in range(len(dates))]},index=dates)
        fix=pd.Series(.7,index=pd.date_range("2011-03-07","2016-01-31",freq="B",tz="UTC"))
        a=study.build_price_only_rows(p,fix)
        changed=p.copy()
        changed.loc[pd.Timestamp("2015-07-01",tz="UTC"):,"price"]*=1000
        b=study.build_price_only_rows(changed,fix)
        early=date(2015,6,29)
        self.assertEqual(
            next(x for x in a if x["date"]==early)["ratio_to_200wma"],
            next(x for x in b if x["date"]==early)["ratio_to_200wma"])

    def test_2015_must_not_fabricate_v59_scores(self):
        rows=mock_cycle_rows(risk=False)
        unavailable=study.replay(rows,policy="v59_risk3x")
        self.assertEqual(unavailable["status"],"UNAVAILABLE_NO_VERIFIED_R2_HISTORY")
        self.assertIsNone(study.first_entry(rows,"hold_cash"))
        self.assertEqual(study.first_entry(rows,"wma_near_20week")["date"],rows[10]["date"])

    def test_20week_buys_respect_25500_cap_and_total_budget(self):
        rows=mock_cycle_rows(weeks=101)
        a=study.replay(rows,policy="wma_near_20week")
        self.assertEqual(a["buy_count"],20)
        self.assertAlmostEqual(a["total_purchases_aud"],500000.)
        self.assertGreater(a["btc_units_at_terminal"],0.)
        self.assertGreater(a["cash_aud_at_terminal"],0.)
        b=study.replay(rows,policy="wma_near_25week")
        self.assertEqual(b["buy_count"],25)
        self.assertAlmostEqual(b["total_purchases_aud"],500000.)
        self.assertAlmostEqual(
            study.replay(rows,policy="hold_cash")["cash_aud_at_terminal"],
            500000.*(1.05)**(700./365.25),places=2)

    def test_lookahead_and_missing_weeks_fail(self):
        rows=mock_cycle_rows(weeks=101)
        x=[dict(z) for z in rows]
        x[4]["signal_date"]=x[4]["date"]
        with self.assertRaisesRegex(ValueError,"causal"):
            study.replay(x,policy="wma_near_20week")
        x=[dict(z) for z in rows]
        x[4]["date"]+=timedelta(days=1)
        with self.assertRaisesRegex(ValueError,"Missing weekly"):
            study.replay(x,policy="wma_near_20week")

    def test_synthetic_stress_paths_include_20_35_50_and_no_leverage(self):
        stress=study.synthetic_false_bottom_stress()
        self.assertEqual(len(stress),8*2*5)
        for r in stress:
            self.assertGreaterEqual(r["uninvested_cash_aud"],-1e-5)
            self.assertGreaterEqual(r["btc_units_at_terminal"],0)
            self.assertFalse(r["risk_is_recomputed"])
        self.assertIn("fall_50pct_then_recover",{r["scenario"] for r in stress})
        self.assertIn("rally_25pct",{r["scenario"] for r in stress})
        self.assertIn("flat",{r["scenario"] for r in stress})
        fall=next(x for x in stress if x["scenario"]=="fall_50pct_then_stay_low"
                  and x["policy"]=="wma_near_stage20drop"
                  and x["initial_btc_fraction"]==0.)
        rally=next(x for x in stress if x["scenario"]=="rally_25pct"
                   and x["policy"]=="wma_near_stage20drop"
                   and x["initial_btc_fraction"]==0.)
        self.assertIsNotNone(fall["first_dip_acceleration_signal"])
        self.assertIsNone(rally["first_dip_acceleration_signal"])

    def test_unconfirmed_2026_not_assumed_future_cycle_bottom(self):
        r=study.cycle_periods(mock_cycle_rows(weeks=101))
        self.assertEqual(r[-1]["status"],"UNCONFIRMED_AND_RIGHT_CENSORED")
        self.assertTrue(r[-1]["not_simulated"])


if __name__=="__main__":
    unittest.main()
