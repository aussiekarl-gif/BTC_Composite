"""Research-only 200WMA proximity entry test, preserving PR #259's cohort engine.

Risk and moving average are calculated on PRIOR Sunday. Monday USD/AUD reference
is a hypothetical execution and not an ASX:IBIT trade. Bands declared before
inspecting numerical run. Do not alter live policies.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date
import math
from statistics import median

from engines.research import v59_causal_timing_horse_race as base

@dataclass(frozen=True)
class WmaGate:
    name: str
    min_ratio: float
    max_ratio: float
    risk_ceiling: float = .50
    fixed_3x: bool = False

# A ratio of 1.00 is exactly BTC/USD's PRIOR-SUNDAY 200-week simple moving average.
# Note the distinction: +10% from average INCLUDES all deeply-below-average
# trades, while "within 10%" EXCLUDES prices more than 10% below average.
GATES = (
    WmaGate("below_200wma", 0., 1.),
    WmaGate("below_to_plus5", 0., 1.05),
    WmaGate("below_to_plus10", 0., 1.10),
    WmaGate("below_to_plus20", 0., 1.20),
    WmaGate("within_5pct", .95, 1.05),
    WmaGate("within_10pct", .90, 1.10),
    WmaGate("within_20pct", .80, 1.20),
    WmaGate("ten_pct_below", 0., .90),
    WmaGate("below_to_plus10_risk020", 0., 1.10, .20),
    WmaGate("within_10pct_fixed3x", .90, 1.10, .50, True),
)
CONTROLS=("risk_1x","risk_3x","risk_3x_risk_le_020")
POLICIES=CONTROLS+tuple(x.name for x in GATES)


def gate_weight(row: dict, gate: WmaGate) -> float:
    """Prior-Sunday price, risk source and ratio ONLY; no Monday fill leakage."""
    risk=float(row.get("risk_score",float("nan")))
    ratio=float(row.get("ratio_to_200wma",float("nan")))
    if row.get("risk_score_source")!="Walk-forward Power Law":
        raise ValueError("Cannot size buys from fallback/unattested risk")
    if not math.isfinite(risk) or not 0 <= risk <= 1:
        raise ValueError("Invalid risk reading")
    if not math.isfinite(ratio) or ratio <= 0:
        # Until 200 weeks of BTC observations exist, do not assume a WMA gate.
        return 0.
    if not (gate.min_ratio <= ratio <= gate.max_ratio and risk <= gate.risk_ceiling):
        return 0.
    return 3. if gate.fixed_3x else base.policy_multiplier("risk_3x",row)


def _matched_historical(rows: list[dict], *, yield_rate: float) -> list[dict]:
    windows=base.cohort_windows(rows)
    outcome=[]
    for cohort in windows:
        for policy in POLICIES:
            if policy in CONTROLS:
                result=base.simulate(cohort["rows"],policy=policy,cash_yield=yield_rate,
                                     reserve_fraction=0.,initial_btc_fraction=.41,
                                     review_date=cohort["review_date"])
            else:
                gate=next(g for g in GATES if g.name==policy)
                result=base.simulate(cohort["rows"],policy="risk_3x",
                                     weight_fn=lambda row,g=gate:gate_weight(row,g),
                                     cash_yield=yield_rate,reserve_fraction=0.,
                                     initial_btc_fraction=.41,
                                     review_date=cohort["review_date"])
            if policy in CONTROLS:
                elig=sum(base.policy_multiplier(policy,r)>0 for r in cohort["rows"])
            else:
                elig=sum(gate_weight(r,gate)>0 for r in cohort["rows"])
            outcome.append({
                "anchor":cohort["anchor"],"split":cohort["split"],"policy":policy,
                "cash_yield":yield_rate,
                "eligible_signal_weeks":elig,
                **result
            })
    return outcome


def _stats(outcome: list[dict], split: str, annual_yield: float, reference: str) -> list[dict]:
    subset=[x for x in outcome if x["split"]==split and x["cash_yield"]==annual_yield]
    grouped={}
    for r in subset:
        grouped.setdefault(r["anchor"],{})[r["policy"]]=r
    report=[]
    for name in POLICIES:
        pairs=[(v[name],v[reference]) for v in grouped.values()
               if name in v and reference in v]
        if not pairs: continue
        diffs=[100*(a["equity_aud"]/b["equity_aud"]-1) for a,b in pairs]
        timing=[a["price_selection_vs_uniform_pct"] for a,b in pairs
                if a["price_selection_vs_uniform_pct"] is not None]
        entry=[a["new_btc_avg_entry_aud"] for a,b in pairs
               if a["new_btc_avg_entry_aud"] is not None]
        report.append({
            "policy":name,"reference":reference,"split":split,
            "cash_yield":annual_yield,"cohorts":len(pairs),
            "median_portfolio_uplift_pct":median(diffs),
            "worst_cohort_uplift_pct":min(diffs),
            "positive_cohorts":sum(z>0 for z in diffs),
            "median_drawdown_change_pp":median(
                [a["drawdown_pct"]-b["drawdown_pct"] for a,b in pairs]),
            "median_cash_aud":median(a["cash_aud"] for a,b in pairs),
            "median_buy_count":median(a["buy_count"] for a,b in pairs),
            "median_eligible_weeks":median(a["eligible_signal_weeks"] for a,b in pairs),
            "median_deployed_pct_initial":100*median(
                a["deployed_fraction_of_initial"] for a,b in pairs),
            "median_new_btc_aud_entry":median(entry) if entry else None,
            "median_price_selection_vs_uniform_pct":median(timing) if timing else None,
        })
    return report


def current_week_diagnostic(rows:list[dict]) -> dict:
    last=rows[-1]
    return {
        "signal_asof_sunday_utc":last["signal_date"].isoformat(),
        "monday_spot_proxy_execution":last["date"].isoformat(),
        "sunday_btc_usd_to_sunday_200wma_ratio":float(last["ratio_to_200wma"]),
        "r2_risk":float(last["risk_score"]),
        "monday_btc_usd_spot_proxy":float(last["price_usd"]),
        "not_live_quote":True,
        "price_currency_note":"200WMA ratio on BTC/USD; Monday execution uses BTC/USD divided by PREVIOUS FX fixing",
    }


def evaluate(rows:list[dict]) -> dict:
    if not rows:
        raise ValueError("Real matched PR259 weekly rows required")
    records=[]
    for annual_yield in (0.,.05):
        records.extend(_matched_historical(rows,yield_rate=annual_yield))
    stats=[]
    for split in ("TRAIN","HISTORICAL_HOLDOUT"):
        for annual_yield in (0.,.05):
            for reference in ("risk_1x","risk_3x_risk_le_020"):
                stats.extend(_stats(records,split,annual_yield,reference))
    return {
        "status":"RESEARCH_ONLY_RETROSPECTIVE_NOT_FORECAST",
        "policy_predeclared":True,
        "risk_source":"Reconstructed V5.9 WF Power Law / prior Sunday",
        "initial_btc_fraction":.41,
        "cash_rate_scenarios":(0.,.05),
        "weekly_cap_aud":base.CAPITAL_AUD*.05,
        "200wma_lookback":"200 W-SUN closes on BTC/USD, not 200 daily candles",
        "execution_prices":"Hypothetical Monday UTC BTC/AUD proxy, not ASX:IBIT fills",
        "bands":[vars(g) for g in GATES],
        "current_reference":current_week_diagnostic(rows),
        "completed_historical_cohorts":len(base.cohort_windows(rows)),
        "number_matched_weekly_rows":len(rows),
        "summary":stats,
        "cohort_results":records,
        "limitations":(
            "Six historical holdout cohorts overlap and do not form independent cycles.",
            "Retrospective risk refits and researched-on-the-same-history thresholds cause selection bias.",
            "ETF costs and 5% pretax cash yield illustrative, no real ASX fills or verified historical market vintages.",
            "The same-net-spend uniform calendar diagnostic is hindsight only.",
            "A simple 200WMA gate may leave most cash uninvested across the full review horizon.",
            "No live policy, ntfy, portfolio, orders or alerts changed."
        ),
    }
