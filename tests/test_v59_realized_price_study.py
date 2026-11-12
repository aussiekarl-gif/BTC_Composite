"""Offline safety tests for historical realized-price research gates."""
from datetime import date,timedelta
import math
import tempfile
import unittest
from pathlib import Path

import pandas as pd

from engines.research import v59_realized_price_study as rp


def row(i=0,risk=.05,price=100000.,date0=date(2022,1,3)):
    d=date0+timedelta(weeks=i)
    return {"date":d,"signal_date":d-timedelta(days=1),
            "risk_score":risk,"risk_score_source":"Walk-forward Power Law",
            "btc_price_aud":price/.70,"price_usd":price,
            "usd_per_aud":.70,"spot_sunday_usd":price,
            "ratio_to_200wma":1.,"halving_age_days":600+7*i,
            "drawdown_365":-.4,"ratio_to_50dma":.98,
            "sma50_rising":False}


def attached(i=0,risk=.05,ratio=1.05):
    x=row(i,risk=risk)
    x.update({
        "realized_price_usd_previous_sunday":x["spot_sunday_usd"]/ratio,
        "ratio_to_realized_price":ratio,
        "realized_source_date_utc":x["signal_date"].isoformat(),
        "realized_metric_validation":"HISTORICAL_CSV_PROVIDER_VINTAGE_UNVERIFIED",
    })
    return x


class RealizedPriceStudyTests(unittest.TestCase):
    def test_real_archive_is_historical_and_has_2015_no_future_backfill(self):
        df=rp.load_archive()
        self.assertEqual(df.index.min().date(),date(2011,12,31))
        self.assertEqual(df.index.max().date(),date(2026,10,6))
        self.assertGreater(len(df),5300)
        self.assertAlmostEqual(float(df.iloc[-1]["Realized Price"]),53761.98,places=2)
        self.assertTrue(df["Realized Price"].gt(0).all())

    def test_no_silent_gap_or_wrong_header(self):
        df=rp.load_archive()
        with tempfile.TemporaryDirectory() as directory:
            p=Path(directory)/"input.csv"
            broken=df.iloc[:3000].drop(df.index[48]).copy()
            broken.to_csv(p,index=False)
            with self.assertRaises(ValueError):
                rp.load_archive(p)
            p.write_text("day,value\n2022-01-01,5\n")
            with self.assertRaisesRegex(ValueError,"canonical"):
                rp.load_archive(p)

    def test_gate_does_not_see_monday_price_and_respects_risk_stop(self):
        x=attached(ratio=1.05,risk=.05)
        changed=dict(x,btc_price_aud=1.)
        self.assertEqual(rp.risk_weight(x,"realized_110_risk050"),
                         rp.risk_weight(changed,"realized_110_risk050"))
        self.assertGreater(rp.risk_weight(x,"realized_110_risk050"),0.)
        self.assertEqual(rp.risk_weight(x,"realized_100_risk050"),0.)
        self.assertEqual(rp.risk_weight(attached(risk=.51),"realized_110_OR_risk020"),0.)
        self.assertEqual(rp.risk_weight(attached(risk=.30,ratio=1.30),"realized_110_AND_risk020"),0.)
        self.assertGreater(rp.risk_weight(attached(risk=.05,ratio=1.30),"realized_110_OR_risk020"),0.)

    def test_source_date_mismatch_missing_source_and_neutral_risk_fail_closed(self):
        x=attached()
        self.assertEqual(rp.risk_weight(dict(x,realized_source_date_utc="2022-01-01"),
                                         "realized_125_risk050"),0.)
        self.assertEqual(rp.risk_weight(dict(x,ratio_to_realized_price=None),
                                         "realized_125_risk050"),0.)
        with self.assertRaisesRegex(ValueError,"fallback"):
            rp.risk_weight(dict(x,risk_score_source="Neutral fallback"),
                           "realized_125_risk050")
        with self.assertRaises(ValueError):
            rp.risk_weight(x,"invented_policy")

    def test_archive_stops_without_latest_date_no_future_fill(self):
        df=rp.load_archive()
        sun=date(2026,11,8)
        single=rp.attach_sunday_metric([row(0,date0=sun+timedelta(days=1))],df)[0]
        self.assertIsNone(single["realized_price_usd_previous_sunday"])
        self.assertIsNone(single["ratio_to_realized_price"])

    def test_realized_20_week_buy_is_capped_and_common_calendar(self):
        arr=[attached(i,ratio=1.05) for i in range(105)]
        got=rp._fixed20_realized(arr,1.10)
        self.assertEqual(got["buy_count"],20)
        self.assertAlmostEqual(got["spent_aud"],500000.,places=2)
        self.assertEqual(got["first_buy_monday"],arr[0]["date"].isoformat())
        self.assertGreater(got["btc_units_at_terminal"],0)
        self.assertGreater(got["cash_aud_at_terminal"],0)
        not_cheap=[dict(x,ratio_to_realized_price=1.60) for x in arr]
        hold=rp._fixed20_realized(not_cheap,1.)
        self.assertEqual(hold["buy_count"],0)
        self.assertGreater(hold["cash_aud_at_terminal"],500000.)

    def test_historical_risk_baseline_matches_unchanged_existing_policy(self):
        from engines.research import v59_causal_timing_horse_race as original
        rows=[attached(i,risk=.05,ratio=1.03) for i in range(104)]
        reference=original.simulate(rows,policy="risk_3x_risk_le_020",
                  cash_yield=.05,reserve_fraction=0.,initial_btc_fraction=.41)
        compared=original.simulate(rows,policy="risk_3x",
                  cash_yield=.05,reserve_fraction=0.,initial_btc_fraction=.41,
                  weight_fn=lambda r:rp.risk_weight(r,"risk_3x_risk_le_020"))
        self.assertAlmostEqual(reference["btc_units"],compared["btc_units"],places=7)
        self.assertAlmostEqual(reference["cash_aud"],compared["cash_aud"],places=5)


if __name__=="__main__":
    unittest.main()
