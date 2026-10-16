"""Only exceptional, fresh, SAME-date 5.82/5.9 contradictions should show."""
import datetime as dt
import unittest
from unittest.mock import patch

from engines.research.cycle_model_redflags import (
    MODELS,evaluate_major_red_flags,fetch_reference_model_risks,
    model_agreement_statuses,
)
from cycle_trading_daily_ntfy import daily_message

TODAY=dt.date(2026,10,17)
MARKET_DATE="2026-10-16"


def models(production, research, *, prod_date="16/10/26", research_date="16/10/26"):
    return {
        MODELS[0]:{"risk":production,"risk_data_date":prod_date},
        MODELS[1]:{"risk":research,"risk_data_date":research_date},
    }


def check(buy=0.,sell=0.,snapshots=None,market_asof=MARKET_DATE,
          today=TODAY,halving_date="2024-04-20"):
    return evaluate_major_red_flags(
        buy_pct_cash=buy,sell_pct_held=sell,snapshots=snapshots,
        market_asof=market_asof,today=today,
        confirmed_halving_date=halving_date,
    )


def fake_market(*,buy=True):
    # Use actual existing calculation engine; never fake the allocation.
    import numpy as np
    import pandas as pd
    from engines.research.cycle_trading_dashboard_model import build_dashboard_market
    idx=pd.date_range("2022-06-01",periods=1600,freq="D",tz="UTC")
    series=pd.Series(np.linspace(40000.,100000.,len(idx)),index=idx)
    fx=pd.DataFrame({"aud_per_usd":np.full(len(idx),1.5)},index=idx)
    market=build_dashboard_market(series,fx)
    ratio=.8 if buy else 1.6
    market["prior_200wma_usd"]=market["previous_close_usd"]/ratio
    market["previous_close_below_200wma"]=buy
    if not buy:
        market["halving_day"]=525
    market["asof_date"]=MARKET_DATE
    return market


class MajorOnlyCrossCheckTests(unittest.TestCase):
    def test_extreme_both_high_is_major_buy_red_flag(self):
        result=check(buy=2.5,snapshots=models(.82,.93))
        self.assertEqual(result["status"],"checked")
        self.assertEqual(len(result["warnings"]),1)
        self.assertIn("BUY 2.50%",result["warnings"][0])
        self.assertIn("Production",result["warnings"][0])
        self.assertIn("Research",result["warnings"][0])

    def test_extreme_both_low_is_major_sell_red_flag(self):
        result=check(sell=24.,snapshots=models(.12,.18))
        self.assertEqual(len(result["warnings"]),1)
        self.assertIn("SELL 24.00%",result["warnings"][0])

    def test_extreme_model_split_is_major_only_during_nonzero_signal(self):
        result=check(buy=2.5,snapshots=models(.10,.90))
        self.assertEqual(len(result["warnings"]),1)
        self.assertIn("opposite extreme",result["warnings"][0])

    def test_small_to_medium_risk_disagreements_are_silent(self):
        for a,b in ((.20,.75),(.79,.80),(.60,.70),(.19,.78),(.25,.85)):
            with self.subTest(production=a,research=b):
                self.assertEqual(check(buy=2.5,snapshots=models(a,b))["warnings"],[])

    def test_opposite_extremes_without_direction_are_silent(self):
        self.assertEqual(check(snapshots=models(.05,.95))["warnings"],[])

    def test_missing_unavailable_or_stale_reference_is_not_false_pass(self):
        partial={MODELS[0]:{"risk":.9,"risk_data_date":"16/10/26"}}
        self.assertEqual(check(buy=2.5,snapshots=partial)["status"],"not_checked")
        self.assertEqual(check(buy=2.5,snapshots=None)["status"],"not_checked")
        self.assertEqual(check(buy=2.5,snapshots=models(.95,.90,research_date="09/10/26"))["status"],"not_checked")
        self.assertEqual(check(buy=2.5,snapshots=models(.95,.90,research_date="17/10/26"))["status"],"not_checked")
        self.assertEqual(check(buy=2.5,snapshots=models(.95,.90),
                               market_asof="2026-10-10")["status"],"not_checked")
        self.assertEqual(check(buy=2.5,snapshots=models(.95,.90),
                               today=dt.date(2026,10,22))["status"],"not_checked")

    def test_bad_risk_input_is_silent_and_not_verified(self):
        for bad in (-1,1.5,float("nan"),float("inf"),None):
            self.assertEqual(check(buy=2.5,snapshots=models(bad,.95))["status"],"not_checked")

    def test_future_cycle_reference_not_trusted_without_model_update(self):
        result=check(buy=2.5,snapshots=models(.95,.9),
                     halving_date="2028-04-19")
        self.assertEqual(result["status"],"unsupported_new_cycle")
        self.assertEqual(result["warnings"],[])

    @patch("dca_model_compare_notify.calculate_model_summary")
    def test_snapshot_source_uses_existing_actual_models_no_broker(self,calc):
        calc.side_effect=[
            ({"risk":.91,"risk_data_date":"16/10/26"},None,None),
            ({"risk":.84,"risk_data_date":"16/10/26"},None,None),
        ]
        source=fetch_reference_model_risks()
        self.assertEqual(set(source),set(MODELS))
        self.assertEqual(source[MODELS[0]]["risk"],.91)
        self.assertEqual(source[MODELS[1]]["risk"],.84)
        self.assertEqual(calc.call_count,2)

    def test_daily_summary_has_one_major_warning_or_none(self):
        quote={"price_aud":24.,"timestamp_utc":"2026-10-16T03:00:00+00:00"}
        market=fake_market(buy=True)
        kwargs=dict(now=dt.datetime(2026,10,17,tzinfo=dt.timezone.utc),
                    quote=quote,market=market)
        _,risky=daily_message(**kwargs,
                reference_snapshot_fetcher=lambda:models(.94,.91))
        self.assertEqual(risky.count("MAJOR RED FLAG"),1)
        self.assertIn("BUY allocation: 2.50%",risky)
        self.assertNotIn("A$500,000",risky)
        _,quiet=daily_message(**kwargs,
                reference_snapshot_fetcher=lambda:models(.60,.71))
        self.assertNotIn("RED FLAG",quiet)
        self.assertNotIn("Cross-check passed",quiet)
        _,broken=daily_message(**kwargs,
                reference_snapshot_fetcher=lambda:{})
        self.assertNotIn("RED FLAG",broken)
        # HOLD should not even request remote model scores.
        from engines.research.cycle_trade_allocation import calculate_allocation_signal
        hold=fake_market(buy=False)
        hold["halving_day"]=400
        self.assertEqual(calculate_allocation_signal(hold)["signal"],"HOLD")
        _,message=daily_message(**dict(kwargs,market=hold),
            reference_snapshot_fetcher=lambda:1/0)
        self.assertNotIn("RED FLAG",message)

    def test_daily_individual_agreement_matches_extreme_risk_conflicts(self):
        cases=[
            (.10,.15,2.5,0.,("agrees","agrees")),
            (.90,.85,2.5,0.,("disagrees","disagrees")),
            (.12,.93,2.5,0.,("agrees","disagrees")),
            (.25,.77,2.5,0.,("agrees","agrees")),
            (.12,.10,0.,24.,("disagrees","disagrees")),
            (.85,.90,0.,24.,("agrees","agrees")),
            (.10,.90,0.,24.,("disagrees","agrees")),
        ]
        for prod,res,buy,sell,expected in cases:
            with self.subTest(prod=prod,res=res,buy=buy,sell=sell):
                labels=model_agreement_statuses(
                    buy_pct_cash=buy,sell_pct_held=sell,
                    snapshots=models(prod,res),market_asof=MARKET_DATE,
                    today=TODAY,
                )
                self.assertEqual(tuple(labels[x] for x in MODELS),expected)

    def test_daily_independent_missing_stale_hold_and_future_cycle_are_no_data(self):
        base=dict(buy_pct_cash=2.5,sell_pct_held=0.,
                  market_asof=MARKET_DATE,today=TODAY)
        v=model_agreement_statuses(**base,snapshots={
            MODELS[0]:models(.30,.80)[MODELS[0]]
        })
        self.assertEqual(v[MODELS[0]],"agrees")
        self.assertEqual(v[MODELS[1]],"no data")
        v=model_agreement_statuses(**base,snapshots=models(
            .85,.9,research_date="01/10/26"))
        self.assertEqual(v[MODELS[0]],"disagrees")
        self.assertEqual(v[MODELS[1]],"no data")
        no_direction=model_agreement_statuses(
            buy_pct_cash=0.,sell_pct_held=0.,snapshots=models(.8,.9),
            market_asof=MARKET_DATE,today=TODAY)
        self.assertEqual(list(no_direction.values()),["no data","no data"])
        future=model_agreement_statuses(
            **base,snapshots=models(.85,.9),
            confirmed_halving_date="2028-04-25")
        self.assertEqual(list(future.values()),["no data","no data"])
        stale=model_agreement_statuses(
            **{**base,"today":dt.date(2026,10,21)},
            snapshots=models(.85,.9))
        self.assertEqual(list(stale.values()),["no data","no data"])

    def test_daily_message_individual_labels_and_one_warning(self):
        quote={"price_aud":24.,"timestamp_utc":"2026-10-16T03:00:00+00:00"}
        market=fake_market(buy=True)
        kwargs=dict(now=dt.datetime(2026,10,17,tzinfo=dt.timezone.utc),
                    quote=quote,market=market)
        _,report=daily_message(**kwargs,
            reference_snapshot_fetcher=lambda:models(.90,.55))
        self.assertIn("Production: disagrees",report)
        self.assertIn("Research: agrees",report)
        self.assertNotIn("MAJOR RED FLAG",report)
        _,both=daily_message(**kwargs,
            reference_snapshot_fetcher=lambda:models(.90,.92))
        self.assertIn("Production: disagrees",both)
        self.assertIn("Research: disagrees",both)
        self.assertEqual(both.count("MAJOR RED FLAG"),1)
        _,not_available=daily_message(**kwargs,
            reference_snapshot_fetcher=lambda:{})
        self.assertIn("Production: no data",not_available)
        self.assertIn("Research: no data",not_available)
        self.assertEqual(not_available.count("Production:"),1)
        self.assertEqual(not_available.count("Research:"),1)

    def test_streamlit_only_shows_warnings_with_no_success_badges(self):
        from pathlib import Path
        app=(Path(__file__).resolve().parents[1]/
             "engines/research/cycle_trading_app.py").read_text()
        self.assertIn('reference_risks=cached_cross_model_risks()',app)
        self.assertIn('for major in major_flags["warnings"]:',app)
        self.assertIn('st.error(major)',app)
        self.assertNotIn('Cross-model OK',app)


if __name__=="__main__":
    unittest.main()
