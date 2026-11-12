"""Deterministic timing horse-race safety, causal input and budget tests."""
from __future__ import annotations

from datetime import date, timedelta
import unittest
import pandas as pd
import numpy as np

from engines.research.v59_causal_timing_horse_race import (
    CAPITAL_AUD, POLICIES, policy_multiplier, simulate, build_weekly_rows,
    cohort_windows, evaluate, horizon_sensitivity, existing_btc_exposure_sensitivity, WEEKS,
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

    def test_review_date_pauses_buying_instead_of_forcing_deployment(self):
        weeks=[row(i,risk=.05) for i in range(WEEKS)]
        early=simulate(weeks,policy="risk_3x",cash_yield=.05,reserve_fraction=0,
                       review_date=date(2021,4,1))
        later=simulate(weeks,policy="risk_3x",cash_yield=.05,reserve_fraction=0,
                       review_date=date(2023,4,1))
        self.assertLess(early["buy_count"],later["buy_count"])
        self.assertLess(early["net_invested_aud"],later["net_invested_aud"])
        self.assertGreater(early["cash_aud"],later["cash_aud"])

    def test_review_horizon_reports_matched_capital_and_holdout_split(self):
        fake={"anchor":"2021-01-01","split":"TRAIN","rows":[row(i) for i in range(104)]}
        summaries=horizon_sensitivity([fake])
        self.assertEqual(len(summaries),5*6*2*2)
        sample=[r for r in summaries if r["policy"]=="risk_3x"
                and r["cash_yield"]==.05 and r["reserve_fraction"]==0]
        self.assertEqual(set(x["review_after_weeks"] for x in sample),{39,52,60,78,104,130})
        self.assertTrue(all(x["cohorts"]==1 for x in sample))

    def test_existing_btc_is_not_purchased_twice(self):
        rows=[row(i,risk=.99) for i in range(WEEKS)]
        r=simulate(rows,policy="risk_3x",cash_yield=.05,reserve_fraction=0,
                   initial_btc_fraction=.41)
        self.assertEqual(r["buy_count"],0)
        self.assertEqual(r["net_invested_aud"],0.)
        self.assertEqual(r["initial_btc_fraction"],.41)
        self.assertGreater(r["btc_units"],2.)
        self.assertGreater(r["cash_aud"],CAPITAL_AUD*.59)
        self.assertLess(r["btc_units"],CAPITAL_AUD*.41/100000.)

    def test_existing_btc_sensitivity_is_same_cohort_and_base(self):
        win={"anchor":"2021-01-01","split":"TRAIN",
             "rows":[row(i,risk=.05) for i in range(104)],
             "review_date":date(2023,1,1)}
        reports=existing_btc_exposure_sensitivity([win])
        self.assertEqual(len(reports),len(POLICIES)*len((0,.05))*len((0,.1)))
        self.assertEqual(set(r["initial_btc_fraction"] for r in reports),{.41})

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




class FalseBottomResearchTests(unittest.TestCase):
    def test_new_replay_matches_pr259_baselines_without_parameter_drift(self):
        from engines.research import v59_false_bottom_stress as study
        rows=study.synthetic_path(drop=.35,recover=True)
        for policy in ("risk_1x","risk_3x","risk_3x_risk_le_020"):
            with self.subTest(policy=policy):
                a=study.replay(rows,policy=policy)
                b=simulate(rows,policy=policy,cash_yield=.05,
                           reserve_fraction=0.,initial_btc_fraction=.41)
                self.assertAlmostEqual(a["equity_aud"],b["equity_aud"],places=5)
                self.assertAlmostEqual(a["btc_units"],b["btc_units"],places=8)
                self.assertAlmostEqual(a["cash_aud"],b["cash_aud"],places=5)

    def test_stage_cannot_see_current_monday_fill(self):
        from engines.research import v59_false_bottom_stress as study
        state=dict(cheap_streak=0,anchor_price=None,prev_monday_price=90000.,
                   drop10_latched=False,drop20_latched=False)
        x=row(1,risk=.05,aud=90000.)
        y=dict(x,btc_price_aud=1000.)
        state["anchor_price"]=100000.
        a=study.candidate_multiplier("strict_stage_1x_drop10",x,dict(state))
        b=study.candidate_multiplier("strict_stage_1x_drop10",y,dict(state))
        self.assertEqual(a,b)
        self.assertEqual(a,3.)

    def test_new_policies_stop_when_score_high_and_reject_fallback(self):
        from engines.research import v59_false_bottom_stress as study
        for p in study.POLICIES:
            s=dict(cheap_streak=0,anchor_price=None,prev_monday_price=None,
                   drop10_latched=False,drop20_latched=False)
            self.assertEqual(study.candidate_multiplier(p,row(1,risk=.70),s),0.)
            with self.assertRaises(ValueError):
                study.candidate_multiplier(p,dict(row(1),risk_score_source="Neutral fallback"),s)

    def test_stress_is_explicitly_synthetic_and_completes(self):
        from engines.research import v59_false_bottom_stress as study
        shocks=study.synthetic_stress()
        self.assertEqual(len(shocks),8*len(study.SHOCK_POLICIES))
        self.assertEqual(set(x["path"] for x in shocks),{
            "flat","rally_25pct","fall_20pct_stay_low",
            "fall_20pct_then_recover","fall_35pct_stay_low",
            "fall_35pct_then_recover","fall_50pct_stay_low",
            "fall_50pct_then_recover"})
        for x in shocks:
            self.assertGreaterEqual(x["cash_aud"],0.)
            self.assertLessEqual(x["net_deployed_pct_initial"],59.0+11.0)

    def test_very_high_risk_keeps_cash_and_earns_interest(self):
        from engines.research import v59_false_bottom_stress as study
        rows=[row(i,risk=.90) for i in range(WEEKS)]
        for policy in study.POLICIES:
            r=study.replay(rows,policy=policy)
            self.assertEqual(r["buys"],0)
            self.assertEqual(r["invested_aud"],0.)
            self.assertGreater(r["interest_aud"],10000.)

    def test_episode_requires_observed_transition_and_full_twelve_weeks(self):
        from engines.research import v59_false_bottom_stress as study
        all_cheap=[row(i,risk=.05) for i in range(20)]
        self.assertEqual(study.cheap_signal_episode_study(all_cheap)["events_count"],0)
        crossing=[row(i,risk=.70 if i<2 else .05) for i in range(20)]
        self.assertEqual(study.cheap_signal_episode_study(crossing)["events_count"],1)
        with_missing_week=crossing[:3]+crossing[4:]
        self.assertEqual(study.cheap_signal_episode_study(with_missing_week)["events_count"],0)

    def test_two_week_confirmation_does_not_buy_first_signal(self):
        from engines.research import v59_false_bottom_stress as study
        rows=study.synthetic_path(drop=.20)
        one=study.replay(rows,policy="strict_confirm_2w")
        immediate=study.replay(rows,policy="risk_3x_risk_le_020")
        self.assertEqual(one["buys"],15)
        self.assertEqual(immediate["buys"],16)
        self.assertGreater(immediate["net_deployed_pct_initial"],
                           one["net_deployed_pct_initial"])



class WmaProximityResearchTests(unittest.TestCase):
    def test_200wma_bands_only_prior_sunday_ratio_and_risk(self):
        from engines.research.v59_200wma_proximity_study import GATES,gate_weight
        near=next(g for g in GATES if g.name=="within_10pct")
        below=next(g for g in GATES if g.name=="below_to_plus10")
        near_row=row(0,risk=.05,ratio=1.04)
        self.assertEqual(gate_weight(near_row,near),3.)
        self.assertEqual(gate_weight(dict(near_row,btc_price_aud=200.),near),3.)
        self.assertEqual(gate_weight(dict(near_row,ratio_to_200wma=.80),near),0.)
        self.assertEqual(gate_weight(dict(near_row,ratio_to_200wma=.80),below),3.)
        self.assertEqual(gate_weight(dict(near_row,ratio_to_200wma=1.11),near),0.)
        self.assertEqual(gate_weight(dict(near_row,risk=.51),near),0.)
        self.assertEqual(gate_weight(dict(near_row,ratio_to_200wma=float("nan")),near),0.)
        with self.assertRaises(ValueError):
            gate_weight(dict(near_row,risk_score_source="Neutral fallback"),near)

    def test_no_ratio_gate_fails_closed_and_allows_deep_discount_only_when_specified(self):
        from engines.research.v59_200wma_proximity_study import GATES,gate_weight
        r=row(0,risk=.05)
        for gate in GATES:
            self.assertEqual(gate_weight(dict(r,ratio_to_200wma=float("nan")),gate),0.)
        under=next(x for x in GATES if x.name=="ten_pct_below")
        within=next(x for x in GATES if x.name=="within_5pct")
        self.assertEqual(gate_weight(dict(r,ratio_to_200wma=.70),under),3.)
        self.assertEqual(gate_weight(dict(r,ratio_to_200wma=.70),within),0.)

    def test_wma_research_injection_matches_original_when_unrestricted(self):
        rows=[row(i,risk=.05,ratio=.96) for i in range(104)]
        ordinary=simulate(rows,policy="risk_3x",cash_yield=.05,
                          reserve_fraction=0.,initial_btc_fraction=.41)
        overridden=simulate(rows,policy="risk_3x",cash_yield=.05,
                            reserve_fraction=0.,initial_btc_fraction=.41,
                            weight_fn=lambda r:policy_multiplier("risk_3x",r))
        for k in ("cash_aud","btc_units","equity_aud","new_btc_avg_entry_aud"):
            self.assertAlmostEqual(ordinary[k],overridden[k],places=7)
        self.assertEqual(ordinary["buy_count"],overridden["buy_count"])
        self.assertGreater(ordinary["new_btc_before_drag"],0)
        self.assertAlmostEqual(ordinary["price_selection_vs_uniform_pct"],0.,places=7)

    def test_wma_buys_rejected_risk_and_invalid_size(self):
        rows=[row(i,risk=.70,ratio=1.0) for i in range(104)]
        from engines.research.v59_200wma_proximity_study import GATES,gate_weight
        for gate in GATES:
            result=simulate(rows,policy="risk_3x",cash_yield=.05,
                            reserve_fraction=0.,initial_btc_fraction=.41,
                            weight_fn=lambda r,g=gate:gate_weight(r,g))
            self.assertEqual(result["buy_count"],0)
        with self.assertRaises(ValueError):
            simulate(rows,policy="risk_3x",cash_yield=.05,reserve_fraction=0.,
                     weight_fn=lambda r:float("nan"))

    def test_summary_from_matched_historical_windows(self):
        from engines.research import v59_200wma_proximity_study as study
        rows=[row(i,risk=.05,ratio=.99) for i in range(104)]
        # A real 104-week cohort requires a Jan/July anchor; our generated
        # row series starts 2021-01-04 and aligns the full 104-week 2021 cohort.
        results=study._matched_historical(rows,yield_rate=.05)
        self.assertEqual(set(x["policy"] for x in results),set(study.POLICIES))
        selected=next(x for x in results if x["policy"]=="below_200wma")
        control=next(x for x in results if x["policy"]=="risk_3x")
        self.assertAlmostEqual(selected["equity_aud"],control["equity_aud"],places=5)


if __name__ == "__main__":
    unittest.main()
