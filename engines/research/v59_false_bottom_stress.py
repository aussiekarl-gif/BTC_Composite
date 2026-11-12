"""Read-only BTC false-bottom and price-timing study extending PR #259.

REAL history: recomputed V5.9 WF risk from parent runner, prior-Sunday gates,
next-Monday BTC/AUD proxy buys. SYNTHETIC paths: deliberately FIXED risk,
not a refitted signal forecast. All results are research-only and non-tradable.
"""
from __future__ import annotations

from datetime import date, timedelta
import math
import statistics

from engines.research import v59_causal_timing_horse_race as prior

POLICIES = (
    "risk_1x",
    "risk_3x",
    "risk_3x_risk_le_020",
    "strict_confirm_2w",
    "strict_confirm_4w",
    "strict_stage_1x_drop10",
    "strict_stage_1x_drop20",
    "strict_stage_2x_drop10",
    "strict_risk_and_365d_drawdown25",
)
SHOCK_POLICIES = tuple(x for x in POLICIES if x != "strict_risk_and_365d_drawdown25")
SOURCE = "Walk-forward Power Law"


def candidate_multiplier(policy: str, row: dict, state: dict) -> float:
    """Decide before Monday price is supplied; use Sunday risk and lagged Monday price.

    state.prev_monday_price is LAST WEEK's executed proxy price, never this
    Monday's price. First-cheap anchor is created only after first Monday fills.
    """
    if policy not in POLICIES:
        raise ValueError("Unknown locked research candidate")
    risk = float(row["risk_score"])
    if row.get("risk_score_source") != SOURCE or not math.isfinite(risk) or not 0 <= risk <= 1:
        raise ValueError("Missing validated prior-Sunday historical WF risk")
    if policy in prior.POLICIES:
        return prior.policy_multiplier(policy, row)
    if risk > .20:
        state["cheap_streak"] = 0
        state["anchor_price"] = None
        state["drop10_latched"] = False
        state["drop20_latched"] = False
        return 0.
    state["cheap_streak"] += 1
    base = prior.policy_multiplier("risk_3x", row)
    if policy == "strict_confirm_2w":
        return base if state["cheap_streak"] >= 2 else 0.
    if policy == "strict_confirm_4w":
        return base if state["cheap_streak"] >= 4 else 0.
    if policy == "strict_risk_and_365d_drawdown25":
        dd = float(row.get("drawdown_365", float("nan")))
        return base if math.isfinite(dd) and dd <= -.25 else 0.
    if policy.startswith("strict_stage_"):
        prev = state["prev_monday_price"]
        anchor = state["anchor_price"]
        # Lagged observations may only trigger on NEXT Monday's buy decision.
        if anchor is not None and prev is not None:
            if prev <= .90 * anchor:
                state["drop10_latched"] = True
            if prev <= .80 * anchor:
                state["drop20_latched"] = True
        if policy == "strict_stage_1x_drop10":
            return base if state["drop10_latched"] else min(1., base)
        if policy == "strict_stage_2x_drop10":
            return base if state["drop10_latched"] else min(2., base)
        if policy == "strict_stage_1x_drop20":
            return base if state["drop20_latched"] else min(1., base)
    raise ValueError("Unimplemented candidate")


def replay(rows: list[dict], *, policy: str, initial_btc_fraction: float=.41,
           cash_yield: float=.05, capital: float=prior.CAPITAL_AUD,
           review_date: date | None=None) -> dict:
    """Matched-price, matched-budget simulator with causal policy state."""
    if not rows or policy not in POLICIES or not 0 <= initial_btc_fraction <= 1:
        raise ValueError("Invalid rows, policy or initial holdings")
    if not 0 <= cash_yield < 1 or not capital > 0:
        raise ValueError("Invalid capital or return")
    first = rows[0]["date"]
    end = review_date or first + timedelta(weeks=prior.WEEKS)
    cash = capital * (1. - initial_btc_fraction)
    btc = capital * initial_btc_fraction / float(rows[0]["btc_price_aud"])
    reserve = 0.
    invested = interest = cost = new_btc_undragged = 0.
    buys = 0
    peak = capital
    drawdown = 0.
    early_spend = 0.
    state = dict(cheap_streak=0,anchor_price=None,
                 prev_monday_price=None,drop10_latched=False,drop20_latched=False)
    prior_day = first
    for ix,row in enumerate(rows):
        day = row["date"]
        if day != first + timedelta(weeks=ix) or (day-row["signal_date"]).days != 1:
            raise ValueError("Noncausal or missing weekly signal/execution")
        price = float(row["btc_price_aud"])
        if not math.isfinite(price) or price <= 0:
            raise ValueError("Missing tradable price proxy")
        elapsed = (day-prior_day).days if ix else 0
        gained = cash * ((1+cash_yield)**(elapsed/365.25)-1)
        cash += gained
        interest += gained
        btc *= (1-prior.ANNUAL_ETF_DRAG)**(elapsed/365.25)
        prior_day = day
        weight = candidate_multiplier(policy,row,state) if day <= end else 0.
        remaining_weeks = max((end-day).days/7., 1.)
        spend = min(max(0.,cash-reserve),
                    max(0.,cash-reserve)/remaining_weeks*weight,
                    capital * prior.MAX_WEEKLY_FRACTION)
        if spend > prior.FIXED_FEE_AUD + .01:
            net=(spend-prior.FIXED_FEE_AUD)*(1-prior.VARIABLE_BUY_FRICTION)
            cash -= spend
            btc += net/price
            new_btc_undragged += net/price
            invested += spend
            cost += spend-net
            buys += 1
            if ix < 26:
                early_spend += spend
        # Update anchor only after Monday reference has been settled.
        # A prior risk-streak reset allows a new independent cheap episode.
        if float(row["risk_score"]) <= .20 and state["anchor_price"] is None:
            state["anchor_price"] = price
        state["prev_monday_price"] = price
        mark=cash+btc*price
        peak=max(peak,mark)
        drawdown=min(drawdown,mark/peak-1)
        if cash < -1e-5 or spend > capital*.05 + 1e-6:
            raise AssertionError("Budget, no-leverage or weekly cap violation")
    prices=[float(x["btc_price_aud"]) for x in rows]
    # Diagnostic ONLY: hindsight-equal total deployed dollars & exact same net
    # entry-cost budget spread uniformly over the SAME 104 calendar weeks.
    # This is NOT a deployable algorithm (total spend only known ex post).
    net_total=invested-cost
    uniform_btc=(net_total/len(prices))*sum(1/p for p in prices) if net_total else 0.
    return {
        "policy":policy, "equity_aud":cash+btc*prices[-1],
        "btc_units":btc,"new_btc_units_before_drag":new_btc_undragged,
        "uniform_spend_same_net_dollars_btc":uniform_btc,
        "entry_price_selection_vs_uniform_pct":(
            100*(new_btc_undragged/uniform_btc-1) if uniform_btc else None),
        "cash_aud":cash,"interest_aud":interest,
        "invested_aud":invested,"cost_aud":cost,"buys":buys,
        "max_drawdown_pct":100*drawdown,
        "spent_first_26w_pct_initial":100*early_spend/capital,
        "net_deployed_pct_initial":100*invested/capital,
    }


def _summarise(records: list[dict], reference: str) -> list[dict]:
    groups={}
    for r in records:
        groups.setdefault(r["anchor"],{})[r["policy"]]=r
    out=[]
    for policy in POLICIES:
        comparable=[(v[policy],v[reference]) for v in groups.values()
                    if policy in v and reference in v]
        if not comparable:
            continue
        uplifts=[100*(a["equity_aud"]/b["equity_aud"]-1) for a,b in comparable]
        skill=[a["entry_price_selection_vs_uniform_pct"] for a,b in comparable
               if a["entry_price_selection_vs_uniform_pct"] is not None]
        out.append({
            "policy":policy,"baseline":reference,"cohorts":len(comparable),
            "median_total_value_uplift_pct":statistics.median(uplifts),
            "worst_total_value_uplift_pct":min(uplifts),
            "win_cohorts":sum(v>0 for v in uplifts),
            "median_extra_drawdown_pp":statistics.median(
                [a["max_drawdown_pct"]-b["max_drawdown_pct"] for a,b in comparable]),
            "median_deployed_pct_original_capital":statistics.median(
                [a["net_deployed_pct_initial"] for a,b in comparable]),
            "median_first26w_spend_pct_initial":statistics.median(
                [a["spent_first_26w_pct_initial"] for a,b in comparable]),
            "median_price_selection_vs_uniform_pct":statistics.median(skill) if skill else None,
        })
    return out


def historical_experiment(rows: list[dict]) -> dict:
    windows=prior.cohort_windows(rows)
    records=[]
    for window in windows:
        for policy in POLICIES:
            outcome=replay(window["rows"],policy=policy,review_date=window["review_date"])
            records.append({"anchor":window["anchor"],"split":window["split"],**outcome})
    holdout=[r for r in records if r["split"]=="HISTORICAL_HOLDOUT"]
    train=[r for r in records if r["split"]=="TRAIN"]
    return {
        "historical_cohorts":len(windows),
        "historical_holdout_cohorts":len({r["anchor"] for r in holdout}),
        "holdout_vs_risk1x":_summarise(holdout,"risk_1x"),
        "holdout_vs_strict3x":_summarise(holdout,"risk_3x_risk_le_020"),
        "train_vs_strict3x":_summarise(train,"risk_3x_risk_le_020"),
        "holdout_per_cohort":holdout,
        "known_limitations":(
            "Cohorts overlap; market signal is retrospectively refitted in 2026; "
            "no as-published historical risk vintages or ASX:IBIT fills. "
            "Same-net-spend uniform price comparator uses hindsight total spend "
            "ONLY as diagnostic, not a deployable control."
        ),
    }


def cheap_signal_episode_study(rows: list[dict]) -> dict:
    """Real paths following first weekly return to <=.20; no future in decisions."""
    events=[]
    prev_cheap=None  # No prior observation: cannot infer a threshold crossing.
    prev_day=None
    last=None
    for ix,row in enumerate(rows):
        cheap=row["risk_score_source"]==SOURCE and 0 <= float(row["risk_score"]) <= .20
        contiguous_before=(prev_day is not None and (row["date"]-prev_day).days==7)
        next12=rows[ix+1:ix+13]
        contiguous_after=(len(next12)==12 and all(
            z["date"]==row["date"]+timedelta(weeks=j+1)
            for j,z in enumerate(next12)))
        if (cheap and prev_cheap is False and contiguous_before and
                contiguous_after and
                (last is None or (row["date"]-last).days>=26*7)):
            anchor=float(row["btc_price_aud"])
            future=[float(z["btc_price_aud"]) for z in next12]
            if all(math.isfinite(p) and p>0 for p in future):
                events.append({
                    "signal_date":row["signal_date"].isoformat(),
                    "next_monday":row["date"].isoformat(),
                    "risk":float(row["risk_score"]),
                    "min_next_12w_pct":100*(min(future)/anchor-1),
                    "max_next_12w_pct":100*(max(future)/anchor-1),
                    "fell_20pct":min(future)<=.8*anchor,
                    "fell_35pct":min(future)<=.65*anchor,
                    "fell_50pct":min(future)<=.5*anchor,
                })
                last=row["date"]
        prev_cheap=cheap
        prev_day=row["date"]
    return {
        "events_count":len(events),
        "episodes_not_independent":True,
        "selection":"Observed contiguous >0.20 to <=0.20 crossing, >=26w between starts, full contiguous next 12w only",
        "falls_20pct":sum(e["fell_20pct"] for e in events),
        "falls_35pct":sum(e["fell_35pct"] for e in events),
        "falls_50pct":sum(e["fell_50pct"] for e in events),
        "events":events,
    }


def synthetic_path(*, drop: float, recover: bool=False, rally: bool=False) -> list[dict]:
    """Deterministic fixed-risk path, NOT historical prices or coupled risk rebuild."""
    if not 0 <= drop <= .50 or rally and recover:
        raise ValueError("Invalid synthetic shock")
    rows=[]
    start=date(2021,1,4)
    for ix in range(prior.WEEKS):
        if rally:
            price=100000.*(1+drop*min(ix,12)/12)
        else:
            price=100000.*(1-drop*min(ix,12)/12)
            if recover and ix>12:
                price=100000.*(1-drop+drop*min(ix-12,12)/12)
        day=start+timedelta(weeks=ix)
        rows.append({
            "date":day,"signal_date":day-timedelta(days=1),
            "btc_price_aud":price,
            "risk_score":.05 if ix<16 else .70,
            "risk_score_source":SOURCE,
            "drawdown_365":float("nan"),
        })
    return rows


def synthetic_stress() -> list[dict]:
    setups=[("flat",0.,False,False),("rally_25pct",.25,False,True)]
    for d in (.20,.35,.50):
        setups += [(f"fall_{int(100*d)}pct_stay_low",d,False,False),
                   (f"fall_{int(100*d)}pct_then_recover",d,True,False)]
    out=[]
    for name,d,recover,rally in setups:
        rows=synthetic_path(drop=d,recover=recover,rally=rally)
        runs={p:replay(rows,policy=p) for p in SHOCK_POLICIES}
        bench=runs["risk_3x_risk_le_020"]
        for policy in SHOCK_POLICIES:
            r=runs[policy]
            out.append({
                "path":name,"policy":policy,
                "total_value_vs_strict3x_pct":100*(r["equity_aud"]/bench["equity_aud"]-1),
                "btc_units_vs_strict3x_pct":100*(r["btc_units"]/bench["btc_units"]-1),
                "equity_aud":round(r["equity_aud"],2),
                "cash_aud":round(r["cash_aud"],2),
                "max_drawdown_pct":round(r["max_drawdown_pct"],3),
                "net_deployed_pct_initial":round(r["net_deployed_pct_initial"],3),
            })
    return out


def evaluate(rows: list[dict]) -> dict:
    history=historical_experiment(rows)
    return {
        "status":"RESEARCH_ONLY_NO_PROMOTION",
        "reference":"PR #259 historical reconstructed WF risk and Monday proxy execution",
        "initial_capital_aud":prior.CAPITAL_AUD,
        "existing_btc_fraction":.41,
        "cash_yield_annual_illustrative":.05,
        "weekly_max_aud":prior.CAPITAL_AUD*prior.MAX_WEEKLY_FRACTION,
        "all_policies_stop_above_risk":.50,
        "strict_candidates_stop_above_risk":.20,
        "prices_execution_not_historical_ibit":True,
        "risk_vintages_unattested":True,
        "production_cycle_ntfy_unchanged":True,
        "historical":history,
        "cheap_signal_episode_study":cheap_signal_episode_study(rows),
        "synthetic_fixed_risk_stress":synthetic_stress(),
    }
