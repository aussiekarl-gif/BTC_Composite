"""Research-only bitcoin *major bear-cycle* grouped entry audit.

Distinct from first-crossing WMA events. 2020 COVID and 2023 retests are NOT
new four-year bottoms. True historical bottom dates are retrospective oracle
references, and cannot be assumed known in live trading.
"""
from __future__ import annotations

from datetime import date, timedelta
from statistics import median
import math

from engines.research import v59_17week_200wma_episode as episode

# Independent published reference pivots, not inferred by optimizing 17-week
# trades. Date differences of one or two days arise across price vendors.
# 2015 cannot be compared fairly with reconstructed R2 workflow that begins
# in 2017. 2026 still has an unfinished future follow-through window.
CYCLES=(
    {"id":"2014_15","previous_peak":date(2013,12,4),
     "retrospective_bottom":date(2015,1,14),
     "status":"R2_BASELINE_UNAVAILABLE_PRE_2017"},
    {"id":"2018","previous_peak":date(2017,12,17),
     "retrospective_bottom":date(2018,12,15),
     "status":"COMPLETE_HISTORICAL"},
    {"id":"2022","previous_peak":date(2021,11,8),
     "retrospective_bottom":date(2022,11,9),
     "status":"COMPLETE_HISTORICAL"},
    {"id":"2026","previous_peak":date(2025,10,6),
     "retrospective_bottom":None,
     "status":"UNCONFIRMED_LIVE_CYCLE_NO_104_WEEK_FUTURE"},
)
NEAR_RATIO=1.05
POLICIES=(
    "17_calendar_unrestricted",
    "17_calendar_capped",
    "20_calendar_capped",
    "17_eligible_below_unrestricted",
    "20_eligible_below_capped",
    "risk_1x",
    "risk_3x",
    "risk_3x_risk_le_020",
    "risk_3x_below_200wma",
)


def _full_horizon(rows: list[dict], monday:date) -> list[dict] | None:
    indexed={r["date"]:i for i,r in enumerate(rows)}
    ix=indexed.get(monday)
    if ix is None:return None
    block=rows[ix:ix+episode.HORIZON]
    if len(block)!=episode.HORIZON or any(
        row["date"] != monday+timedelta(weeks=i)
        for i,row in enumerate(block)):
        return None
    return block


def _causal_prior_peak_signal(rows:list[dict],cycle:dict) -> dict | None:
    """First PREVIOUS-SUNDAY cross <=1.05 between known prior top and trough.

    Peak-to-trough interval used ONLY for retrospective cohort association;
    live trigger rule is the same unconditional first cross <=1.05 after a
    previously recognised high-cycle region. Neither bottom nor future
    price picks the specific qualifying Monday.
    """
    if cycle["retrospective_bottom"] is None:return None
    cross=episode.historical_crossings(rows,threshold=NEAR_RATIO)
    candidates=[c for c in cross
        if c["sunday_signal"]>=cycle["previous_peak"]
        and c["sunday_signal"]<=cycle["retrospective_bottom"]+timedelta(days=7)]
    if not candidates:return None
    selected=candidates[0]
    return {
        "first_signal_sunday":selected["sunday_signal"].isoformat(),
        "first_buy_monday":selected["crossing_monday"].isoformat(),
        "ratio_to_200wma":selected["sunday_wma_ratio"],
        "anchor_selection":"FIRST_CROSS_IN_PAST_CYCLE_INTERVAL_POSTHOC_GROUPING",
    }


def _result_for_anchor(rows:list[dict], *, anchor:date) -> dict | None:
    period=_full_horizon(rows,anchor)
    if period is None:return None
    outcomes={}
    for label,capital,fraction in episode.CASES:
        runs={p:episode.replay(period,policy=p,capital=capital,
                               starting_btc_fraction=fraction,
                               cash_yield=.05) for p in POLICIES}
        reference=runs["risk_3x_risk_le_020"]
        outcomes[label]={
            p:{
                "btc_week17":r["btc_held_after_week17"],
                "btc_week104":r["btc_held_after_104w"],
                "cash_week104_aud":r["cash_after_104w_aud"],
                "spent_aud":r["spent_aud"],
                "portfolio_week104_aud":r["portfolio_after_104w_aud"],
                "portfolio_uplift_vs_strict3x_pct":100*(
                    r["portfolio_after_104w_aud"]/
                    reference["portfolio_after_104w_aud"]-1),
                "cap_violated":r["original_cap_violated"],
                "buys":r["number_of_buys"],
            } for p,r in runs.items()
        }
    return {
        "anchor_monday":anchor.isoformat(),
        "btc_usd_signal_to_wma":period[0].get("ratio_to_200wma"),
        "cash_reference_return":.05,
        "complete_104week_history":True,
        "cases":outcomes,
    }


def evaluate(rows:list[dict]) -> dict:
    if not rows:raise ValueError("Require actual matched source weekly data")
    group=[]
    for cycle in CYCLES:
        item={
            "cycle_id":cycle["id"],
            "cycle_previous_peak":cycle["previous_peak"].isoformat(),
            "ex_post_bottom_date":cycle["retrospective_bottom"].isoformat()
                if cycle["retrospective_bottom"] else None,
            "cycle_status":cycle["status"],
            "true_bottom_not_observable_in_advance":True,
            "2020_covid_not_independent_four_year_cycle":True,
        }
        if cycle["status"]=="COMPLETE_HISTORICAL":
            signal=_causal_prior_peak_signal(rows,cycle)
            item["near_200wma_causal_signal"]=signal
            # EX POST reference, to quantify bottom-detection delay only.
            # Finding the bottom in advance by reading future prices is forbidden.
            trough=cycle["retrospective_bottom"]
            bottom_first_monday=trough+timedelta(days=(7-trough.weekday())%7)
            item["oracle_hindsight_bottom_first_monday"]=bottom_first_monday.isoformat()
            item["oracle_hindsight_not_tradeable"]=True
            item["near_signal_cohort"]=(_result_for_anchor(rows,
                anchor=date.fromisoformat(signal["first_buy_monday"]))
                if signal else None)
            item["hindsight_oracle_cohort"]=_result_for_anchor(
                rows,anchor=bottom_first_monday)
            if signal is not None:
                item["signal_days_relative_to_hindsight_bottom"]=(
                    date.fromisoformat(signal["first_signal_sunday"])-trough).days
        group.append(item)
    completed=[x for x in group if x["cycle_status"]=="COMPLETE_HISTORICAL"
               and x.get("near_signal_cohort") and x.get("hindsight_oracle_cohort")]
    summaries={}
    for case,_,_ in episode.CASES:
        summaries[case]={}
        for name in POLICIES:
            a=[x["near_signal_cohort"]["cases"][case][name] for x in completed]
            b=[x["hindsight_oracle_cohort"]["cases"][case][name] for x in completed]
            if not a:continue
            summaries[case][name]={
                "cycle_count":len(a),
                "median_btc_after_17weeks_near_wma_entry":median(
                    p["btc_week17"] for p in a),
                "median_btc_after_104weeks_near_wma_entry":median(
                    p["btc_week104"] for p in a),
                "median_value_uplift_vs_strict3x_pct_near_entry":median(
                    p["portfolio_uplift_vs_strict3x_pct"] for p in a),
                "median_btc_after_104weeks_ORACLE_bottom_entry":median(
                    p["btc_week104"] for p in b),
                "important":"ONLY TWO mature market cycles. Medians not independent predictive evidence.",
            }
    return {
        "status":"RESEARCH_ONLY_NO_PRODUCTION_CHANGE",
        "cycle_count_complete":len(completed),
        "cycle_dates_from_independent_historical_references":True,
        "R2_risk_history_available_only_from_2017":True,
        "one_broad_bear_cycle_event_per_major_2018_2022_market_cycle":True,
        "2020_covid_is_stress_event_not_new_four_year_cycle":True,
        "2015_cycle_not_simulated_with_fabricated_research_R2":True,
        "2026_bottom_unconfirmed_and_right_censored":True,
        "comparison_model":"Near-WMA first completed Sunday trigger <=+5%, fixed 17/20 weeks, and V5.9 R2 with same 104-week span",
        "hindsight_oracle":"Purchases after actual low date are illustrative, NOT feasible perfect bottom calls",
        "near_threshold_is_posthoc_exploratory":True,
        "cycles":group,
        "two_cycle_descriptive_medians":summaries,
        "next_required_validation":"Hold policy frozen; prospective 2026/27 daily snapshots, actual ASX/IBIT executable prices; 2026 bottom not assertable now.",
        "not_an_executable_ibit_fill":True,
    }
