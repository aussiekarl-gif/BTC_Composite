"""BTC realized-price valuation study: point-in-time *decision* but historical revised data.

Research-only exploration, NOT proof of historical real-time availability.
A BlockHorizon/PlanB CSV exported 2026-10-07 has dated past realized-price
values, but its past provider *publication vintages* are unverified. For
actual forward validation use new first-captured source/date observations.
No Production, live V5.9/Cycle Trading, broker, ntfy or portfolio modification.
"""
from __future__ import annotations

from datetime import date, timedelta
from pathlib import Path
import math
import statistics

import pandas as pd

from engines.research import v59_causal_timing_horse_race as causal
from engines.research import v59_three_cycle_entry as cycle

HISTORY_PATH=Path("data/planb_realized_prices_2026-10-07T21-19-48.csv")
HISTORICAL_SOURCE="BlockHorizon export of PlanB Realized Prices (unverified provider methodology)"
HISTORICAL_SOURCE_EXPORT="2026-10-07"
MAX_SUNDAY_METRIC_AGE_DAYS=0  # strict exact prior-Sunday date, never interpolated
BANDS=(1.00,1.10,1.25)
RISK_POLICY_NAMES=(
    "risk_3x_risk_le_020","risk_3x",
    "realized_100_risk050","realized_110_risk050","realized_125_risk050",
    "realized_110_AND_risk020","realized_110_OR_risk020",
    "realized_125_AND_risk020",
)


def load_archive(path:Path=HISTORY_PATH) -> pd.DataFrame:
    """Parse immutable historical export. Never silently swap in manual JSON."""
    df=pd.read_csv(path)
    expected=["timestamp","Price","Realized Price"]
    if any(c not in df.columns for c in expected):
        raise ValueError("Missing canonical BlockHorizon realized price fields")
    if df.empty or df.shape[0]<365*10:
        raise ValueError("Insufficient 2015/2018/2022 realized-price history")
    dates=pd.to_datetime(df["timestamp"],unit="ms",utc=True,errors="raise")
    if not dates.dt.hour.eq(0).all() or not dates.dt.minute.eq(0).all():
        raise ValueError("Realized data must have UTC-midnight date labels")
    if dates.duplicated().any() or not dates.is_monotonic_increasing:
        raise ValueError("Invalid realized chronological dates")
    if not dates.diff().dropna().eq(pd.Timedelta(days=1)).all():
        raise ValueError("Realized date gaps (no interpolation permitted)")
    for c in ("Price","Realized Price"):
        df[c]=pd.to_numeric(df[c],errors="raise")
        if not df[c].map(lambda x:math.isfinite(float(x)) and x>0).all():
            raise ValueError("Nonfinite/nonpositive realized or provider spot")
    df.index=dates
    if df.index.max().date()!=date(2026,10,6):
        raise ValueError("Unexpected static export end; review source provenance")
    return df


def attach_sunday_metric(rows:list[dict], archive:pd.DataFrame) -> list[dict]:
    """Join dated on-chain metric as of prior Sunday, NEVER Monday settlement."""
    out=[]
    for row in rows:
        sunday=pd.Timestamp(row["signal_date"],tz="UTC")
        value=None; provider_spot=None
        if sunday in archive.index:
            value=float(archive.loc[sunday,"Realized Price"])
            provider_spot=float(archive.loc[sunday,"Price"])
        obs=dict(row)
        obs["realized_price_usd_previous_sunday"]=value
        obs["ratio_to_realized_price"]=(
            float(row.get("spot_sunday_usd",float("nan")))/value
            if value is not None and "spot_sunday_usd" in row else None
        )
        # For R2 weekly rows (where no spot_sunday_usd was retained), reconstruct
        # the signal's BTC spot from the *previous-Sunday WMA ratio* and
        # strictly dated Sunday weekly average, if supplied externally.
        obs["realized_provider_spot_usd"]=provider_spot
        obs["realized_source_date_utc"]=row["signal_date"].isoformat() if value else None
        obs["realized_metric_validation"]="HISTORICAL_CSV_PROVIDER_VINTAGE_UNVERIFIED"
        out.append(obs)
    return out


def attach_sunday_market_price(rows:list[dict], btc:pd.DataFrame,
                               archive:pd.DataFrame) -> list[dict]:
    """Exactly Sunday-close independent market price, not Monday fill."""
    price=btc["price"].copy()
    price.index=pd.to_datetime(price.index,utc=True).normalize()
    out=[]
    for row in rows:
        sunday=pd.Timestamp(row["signal_date"],tz="UTC")
        r=dict(row)
        r["spot_sunday_usd"]=(float(price.loc[sunday]) if sunday in price.index else float("nan"))
        out.append(r)
    return attach_sunday_metric(out,archive)


def _checked_ratio(row:dict) -> float | None:
    r=row.get("ratio_to_realized_price")
    if r is None:return None
    value=float(r)
    if not math.isfinite(value) or value<=0:
        return None
    if row.get("realized_source_date_utc")!=row["signal_date"].isoformat():
        return None
    return value


def risk_weight(row:dict,policy:str) -> float:
    """Risk must remain <=0.50; a realized-price gate cannot override stop."""
    if policy not in RISK_POLICY_NAMES:
        raise ValueError("Unknown registered research candidate")
    if row.get("risk_score_source")!="Walk-forward Power Law":
        raise ValueError("Research risk fallback cannot authorise a candidate buy")
    risk=float(row["risk_score"])
    if not math.isfinite(risk) or not 0<=risk<=1:
        raise ValueError("Invalid historical R2 risk")
    if policy in ("risk_3x","risk_3x_risk_le_020"):
        return causal.policy_multiplier(policy,row)
    if risk>.50:
        return 0.
    ratio=_checked_ratio(row)
    if ratio is None:return 0.
    aggressive=float(causal.policy_multiplier("risk_3x",row))
    near100=ratio<=1.
    near110=ratio<=1.10
    near125=ratio<=1.25
    if policy=="realized_100_risk050":passed=near100
    elif policy=="realized_110_risk050":passed=near110
    elif policy=="realized_125_risk050":passed=near125
    elif policy=="realized_110_AND_risk020":passed=near110 and risk<=.20
    elif policy=="realized_110_OR_risk020":passed=near110 or risk<=.20
    elif policy=="realized_125_AND_risk020":passed=near125 and risk<=.20
    else:raise ValueError("Undeclared policy")
    return aggressive if passed else 0.


def risk_cohort_comparison(rows:list[dict]) -> dict:
    """Same 104-week holding dates, 41% BTC already held, 5% cash interest."""
    windows=causal.cohort_windows(rows)
    detail=[]
    for cohort in windows:
        for p in RISK_POLICY_NAMES:
            result=causal.simulate(
                cohort["rows"],policy="risk_3x",cash_yield=.05,
                reserve_fraction=0.,initial_btc_fraction=.41,
                review_date=cohort["review_date"],
                weight_fn=lambda r,p=p:risk_weight(r,p))
            detail.append({
                "anchor":cohort["anchor"],"split":cohort["split"],
                "policy":p,"execution_count":result["buy_count"],
                "cash_aud":result["cash_aud"],
                "btc_units":result["btc_units"],
                "portfolio_aud":result["equity_aud"],
                "invested_aud":result["net_invested_aud"],
                "max_drawdown_pct":result["drawdown_pct"],
                "same_net_spend_price_selection_pct":result["price_selection_vs_uniform_pct"],
                "unavailable_realized_sundays":sum(
                    _checked_ratio(r) is None for r in cohort["rows"]),
            })
    by={}
    for x in detail:by.setdefault(x["anchor"],{})[x["policy"]]=x
    summary=[]
    for p in RISK_POLICY_NAMES:
        selected=[(v[p],v["risk_3x_risk_le_020"]) for anchor,v in by.items()
                  if v[p]["split"]=="HISTORICAL_HOLDOUT"]
        if not selected:continue
        relative=[100*(a["portfolio_aud"]/b["portfolio_aud"]-1)
                  for a,b in selected]
        summary.append({
            "policy":p,"comparator":"risk_3x_risk_le_020",
            "cohorts":len(selected),
            "median_total_portfolio_gap_pct":statistics.median(relative),
            "worst_cohort_gap_pct":min(relative),
            "positive_cohorts":sum(x>0 for x in relative),
            "median_btc_units":statistics.median(a["btc_units"] for a,b in selected),
            "median_cash_aud":statistics.median(a["cash_aud"] for a,b in selected),
            "median_unavailable_metric_weeks":statistics.median(
                a["unavailable_realized_sundays"] for a,b in selected),
            "median_price_selection_vs_uniform_pct":(
                statistics.median(v for a,b in selected
                                  if (v:=a["same_net_spend_price_selection_pct"]) is not None)
                if any(a["same_net_spend_price_selection_pct"] is not None
                       for a,b in selected) else None),
        })
    return {"cohorts":len(windows),"holdout_summary":summary,"per_cohort":detail,
        "provider_vintages_unverified":True,
        "cross_cohort_independence":False}


def _fixed20_realized(rows:list[dict],threshold:float,capital:float=500000.,
                      initial_btc_fraction:float=0.) -> dict:
    """Staged 20-week causal realized-price entry, sharing cycle's common terminal."""
    if threshold not in BANDS:raise ValueError("Unregistered realized-price threshold")
    if not rows:raise ValueError("Missing full cycle data")
    anchor=next((r["date"] for r in rows if
                 r["halving_age_days"]>=cycle.FIRST_PHASE_DAY and
                 (ratio:=_checked_ratio(r)) is not None and ratio<=threshold),None)
    starting=rows[0]["date"]
    initial_cash=capital*(1-initial_btc_fraction)
    cash=initial_cash
    btc=capital*initial_btc_fraction/float(rows[0]["btc_price_aud"])
    spent=0.;orders=0
    peak=capital;dd=0.
    previous=starting
    for i,r in enumerate(rows):
        day=r["date"]
        if day!=starting+timedelta(weeks=i) or (day-r["signal_date"]).days!=1:
            raise ValueError("Missing signal or Monday execution")
        days=(day-previous).days if i else 0
        cash*=(1+cycle.CASH_YIELD)**(days/365.25)
        btc*=(1-cycle.ETF_DRAG)**(days/365.25)
        previous=day
        if anchor is not None and 0<=(day-anchor).days<20*7:
            amount=min(initial_cash/20.,cycle.WEEKLY_CAP,cash,initial_cash-spent)
            if amount>cycle.FEE+.01:
                btc+=(amount-cycle.FEE)*(1-cycle.SPREAD)/float(r["btc_price_aud"])
                cash-=amount
                spent+=amount;orders+=1
        equity=cash+btc*float(r["btc_price_aud"])
        peak=max(peak,equity);dd=min(dd,equity/peak-1)
        if cash<-1e-5 or btc<0:raise AssertionError("Cash and BTC must not be negative")
    return {
        "policy":f"realized_{round(threshold*100)}_20week",
        "first_buy_monday":anchor.isoformat() if anchor else None,
        "btc_units_at_terminal":btc,
        "cash_aud_at_terminal":cash,
        "portfolio_aud_at_terminal":cash+btc*float(rows[-1]["btc_price_aud"]),
        "spent_aud":spent,"buy_count":orders,"max_drawdown_pct":100*dd,
    }


def three_major_cycle_comparison(price_rows:list[dict]) -> dict:
    output=[]
    for season in cycle.cycle_periods(price_rows):
        info={k:v for k,v in season.items() if k!="rows"}
        if season["not_simulated"]:
            output.append(info);continue
        horizon=season["rows"]
        baseline=cycle.replay(horizon,policy="wma_near_20week")
        arms={f"realized_{int(k*100)}_20week":_fixed20_realized(horizon,k)
              for k in BANDS}
        output.append({
            **info,"benchmark_wma20":baseline,
            "realized_price_policy_arms":arms,
            "realized_metric_observed_weeks":sum(_checked_ratio(r) is not None
                  for r in horizon),
            "first_realized_ratio":_checked_ratio(horizon[0]),
            "retrospective_bottom_date_not_used_to_trade":True,
        })
    return {"cycles":output,
            "comparison":"20 week from first prior-Sunday realized-price threshold after halving age 600 vs 20 week +5% 200WMA",
            "not_fully_point_in_time":True}


def evaluate(price_rows:list[dict],risk_rows:list[dict],
             raw_btc:pd.DataFrame,archive:pd.DataFrame) -> dict:
    price_input=attach_sunday_metric(price_rows,archive)
    risk_input=attach_sunday_market_price(risk_rows,raw_btc,archive)
    recent=archive.iloc[-1]
    latest_date=archive.index[-1].date().isoformat()
    return {
        "status":"RESEARCH_ONLY_NOT_VALIDATED",
        "source":HISTORICAL_SOURCE,
        "source_export_date":HISTORICAL_SOURCE_EXPORT,
        "latest_archive_date":latest_date,
        "latest_archive_btc_realized_price_usd":float(recent["Realized Price"]),
        "latest_archive_btc_provider_price_usd":float(recent["Price"]),
        "not_live_quote_or_recommendation":True,
        "provider_methodology_and_historical_vintages_unverified":True,
        "strict_sunday_metric_join":True,
        "historical_six_overlap_holdouts":risk_cohort_comparison(risk_input),
        "three_major_cycles_price_only":three_major_cycle_comparison(price_input),
        "new_forecast_confidence_claimed":False,
        "important_limits":[
            "Realized Price is an on-chain aggregate last-movement cost basis, not guaranteed market floor",
            "BlockHorizon PlanB daily export is retrospectively calculated, not time-stamped as available on those historical Sundays",
            "2015 V5.9 risk data cannot be constructed from this export; price/FX only",
            "BGeometrics/Glassnode may use different realized supply treatments; independent cross-provider parity required",
            "After 2026-10-06 no new metric vintage in this static archive; fail closed rather than carry forward",
            "Five percent idle cash yield and broker/ETF costs are illustrative; all historical ASX:IBIT executions unverified",
            "Six post-2022 104-week holdouts overlap; only 2 completed risk comparable major cycles",
            "No production, live recommendation, Cycle Trading, ntfy, portfolio or actual orders changed",
        ],
    }
