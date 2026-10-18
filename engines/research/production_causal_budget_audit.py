"""Production V5.8.2 research audit: hindsight allocation vs deployable DCA.

Do not change Production; reproduce its exact SMART_DCA_POINTS and
current live sizing: remaining AUD cash / remaining weeks * risk_weight.
The historical 'equal capital allocator' computes weights for EVERY
future date then divides today’s cash using their total; it is
research-only and is NOT an executable strategy.

Historic MVRV chart exported in Oct 2026 is not a point-in-time vintage.
Fear & Greed isn't available in the onchain archive used here: explicitly
flag missing component, not impute a score. BTC/USD closes proxy spot.
Same BTC/USD, prior dated USD/AUD FX, A$3 fee and simplified FIFO SMSF
liquidation tax for all matched accounts. Strictly prior-day risk for T
trade, no 2025 historical sales, no real holdings.
"""
from __future__ import annotations
import argparse
import csv
import json
import math
from pathlib import Path

import numpy as np
import pandas as pd

from engines.production.production_model import (
    SMART_DCA_POINTS,DEFAULT_PL_CHEAP,DEFAULT_PL_EXPENSIVE,
    DEFAULT_RISK_CALIBRATION_MIN_PERIODS,DEFAULT_RISK_CALIBRATION_WINDOW,
    DEFAULT_RISK_CALIBRATION_BLEND,DEFAULT_ABSOLUTE_RISK_WEIGHT,
    DEFAULT_RELATIVE_RISK_WEIGHT,add_risk_indicators,interpolate,
    align_fx_to_dates,apply_equal_capital_allocator,
)
from engines.research.top_signal_horse_race import read_exported_history
from engines.research.day500_aftertax_reinvestment import (
    PRIMARY,SCORE_DAYS,fetch_fx_for_cycle,fx_before,
)
from engines.research.fresh_cash_200wma_matched_backtest import (
    START_DAYS,BUDGET_AUD,
)
from engines.research.smsf_self_financing_replay import AuditSmsfAccount

ARCHIVE_CUTOFF=pd.Timestamp("2026-10-05",tz="UTC")
FEE_AUD=3.
STRATEGIES=("causal_live_remaining_cash_weeks","historical_omniscient_equal_capital",
            "calendar_equal_weekly")
PARAMS={
    "pl_cheap":DEFAULT_PL_CHEAP,
    "pl_expensive":DEFAULT_PL_EXPENSIVE,
    "risk_calibration_min_periods":DEFAULT_RISK_CALIBRATION_MIN_PERIODS,
    "risk_calibration_window":DEFAULT_RISK_CALIBRATION_WINDOW,
    "risk_calibration_blend":DEFAULT_RISK_CALIBRATION_BLEND,
    "absolute_risk_weight":DEFAULT_ABSOLUTE_RISK_WEIGHT,
    "relative_risk_weight":DEFAULT_RELATIVE_RISK_WEIGHT,
    "min_risk_components":3,
}


def _utc(x):
    t=pd.Timestamp(x)
    return (t.tz_localize("UTC") if t.tzinfo is None
            else t.tz_convert("UTC")).normalize()


def build_production_risk_from_archived_provider(history):
    """Approximate same unchanged Production composite on dated CSV exports.

    Production uses live BGeometrics and Fear & Greed sources; this uses
    only historical exported MVRV Z plus price-derived components.
    Therefore this is an explicitly LIMITED proxy, not exact 5.8.2
    live historic scores or fully certified vintage data.
    """
    if not {"price_usd","mvrv_z"}.issubset(history):
        raise ValueError("Missing historical BTC/MVRV columns")
    observed=history.sort_index().loc[:ARCHIVE_CUTOFF]
    if len(observed)<1500 or observed.index.tz is None:
        raise ValueError("At least 1500 ordered UTC dated BTC closes required")
    if not observed.index.is_unique or not observed.index.is_monotonic_increasing:
        raise ValueError("Unordered/duplicate provider observations")
    price=observed["price_usd"].astype(float)
    z=observed["mvrv_z"].astype(float)
    if not np.isfinite(price).all() or not price.gt(0).all():
        raise ValueError("Invalid BTC closes")
    if not np.isfinite(z).all():
        raise ValueError("Invalid exported MVRV")
    if not pd.date_range(price.index[0],price.index[-1],freq="D",tz="UTC").equals(price.index):
        raise ValueError("Missing historical daily observations")
    # Onchain data vintages unavailable, Fear & Greed historical values
    # missing; do not invent those components.
    inputs=pd.DataFrame({
        "price":price,
        "mvrv_z":z,
        "fear_greed":np.nan,
        "regime_score":np.nan,
    },index=price.index)
    processed=add_risk_indicators(inputs,"Composite V3.6",PARAMS)
    out=processed[["price","risk_score","risk_components_available",
                   "raw_risk_score","mvrv_score","fear_greed_score"]].copy()
    if out["fear_greed_score"].notna().any():
        raise AssertionError("Unavailable Fear & Greed must stay missing")
    if not out["risk_score"].between(0,1).loc[out["risk_score"].notna()].all():
        raise AssertionError("Invalid production risk-score output")
    return out


def equal_capital_hindsight_weights(observed_weights,capital):
    """Exact retrospective proportional operation from Production's allocator.

    Adding a FUTURE observation changes allocations at previous dates,
    proving this is not an executable decision policy.
    """
    v=np.asarray(observed_weights,dtype=float)
    if (len(v)<1 or not np.isfinite(v).all() or (v<0).any()
            or v.sum()<=0 or not math.isfinite(float(capital))
            or capital<=0):
        raise ValueError("Invalid historical weights/cash")
    gross=v/v.sum()*float(capital)
    gross[-1]+=float(capital)-float(gross.sum())
    return gross


def matched_replay(risk,fx,*,start,terminal,budget_aud=BUDGET_AUD):
    start,end=_utc(start),_utc(terminal)
    if not (isinstance(risk,pd.DataFrame) and
            {"price","risk_score"}.issubset(risk.columns)
            and isinstance(risk.index,pd.DatetimeIndex) and
            risk.index.tz is not None and risk.index.is_monotonic_increasing
            and risk.index.is_unique and start in risk.index and end in risk.index
            and end>start):
        raise ValueError("Valid date-indexed Production risk history required")
    if not math.isfinite(float(budget_aud)) or budget_aud<=100:
        raise ValueError("Invalid initial investment budget")
    schedule=pd.date_range(start+pd.Timedelta(days=1),end,freq="7D",tz="UTC")
    if len(schedule)<1 or not schedule.isin(risk.index).all():
        raise ValueError("Missing exact eligible dates")
    previous=schedule-pd.Timedelta(days=1)
    if not previous.isin(risk.index).all():
        raise ValueError("No fully observed prior-day risk")
    scores=risk.loc[previous,"risk_score"].to_numpy(dtype=float)
    if not np.isfinite(scores).all() or (scores<0).any() or (scores>1).any():
        raise ValueError("Missing/invalid prior-production-risk composite")
    multipliers=np.array([interpolate(SMART_DCA_POINTS,float(x))
                          for x in scores],dtype=float)
    omniscient=equal_capital_hindsight_weights(multipliers,budget_aud)
    fixed=np.full(len(schedule),float(budget_aud)/len(schedule))
    acct={name:AuditSmsfAccount(float(budget_aud),fee=FEE_AUD,tax=True)
          for name in STRATEGIES}
    orders={name:[] for name in STRATEGIES}
    for i,date in enumerate(schedule):
        aud=float(risk.loc[date,"price"])*fx_before(fx,date)
        if not math.isfinite(aud) or aud<=0:
            raise ValueError("Bad AUD BTC execution proxy")
        for strategy,account in acct.items():
            if strategy=="historical_omniscient_equal_capital":
                gross=min(account.cash,float(omniscient[i]))
            elif strategy=="calendar_equal_weekly":
                gross=min(account.cash,float(fixed[i]))
            else:
                # Exact DCA Today formula with known calendar target:
                # remaining cash / remaining weeks * prior-known score weight.
                # This does NOT know future risk or price; 'remaining weeks'
                # counts scheduled calendar weeks (a user-entered deadline).
                remaining_weeks=len(schedule)-i
                gross=min(account.cash,max(0.,account.cash/
                           remaining_weeks*float(multipliers[i])))
            if gross>max(100.,2*FEE_AUD):
                if account.buy(date,aud,min(1.,gross/account.cash)):
                    o=account.orders[-1]
                    orders[strategy].append({
                        "date":str(date.date()),
                        "gross_aud":round(float(o["gross_aud"]),2),
                        "btc":round(float(o["btc"]),10),
                        "prior_risk_score":round(float(scores[i]),5),
                        "prior_smart_weight":round(float(multipliers[i]),5),
                        "calendar_weeks_remaining":len(schedule)-i,
                    })
        for account in acct.values():
            account.mark(aud)
    last_aud=float(risk.loc[end,"price"])*fx_before(fx,end)
    output={}
    for name,account in acct.items():
        output[name]={
            "aftertax_aud":round(account.liquidation_value(end,last_aud),2),
            "btc":round(account.btc,8),
            "cash_aud":round(account.cash,2),
            "cash_left_pct":round(100*account.cash/budget_aud,2),
            "fills":len(orders[name]),
            "max_drawdown_pct":round(100*account.drawdown,2),
            "total_fees_aud":round(account.total_fees,2),
            "orders":orders[name],
        }
    causal=output[STRATEGIES[0]]
    look=output[STRATEGIES[1]]
    plain=output[STRATEGIES[2]]
    return {
        "start":str(start.date()),"terminal":str(end.date()),
        "initial_cash_aud":float(budget_aud),
        "risk_components_last":int(risk.loc[previous[-1],"risk_components_available"])
                               if "risk_components_available" in risk else None,
        "causal_vs_hindsight_aftertax_pct":round(
            100*(causal["aftertax_aud"]/look["aftertax_aud"]-1),3),
        "causal_vs_calendar_equal_aftertax_pct":round(
            100*(causal["aftertax_aud"]/plain["aftertax_aud"]-1),3),
        "hindsight_vs_calendar_equal_aftertax_pct":round(
            100*(look["aftertax_aud"]/plain["aftertax_aud"]-1),3),
        "strategies":output,
    }


def audit(history,*,fx_fetcher=fetch_fx_for_cycle):
    risk=build_production_risk_from_archived_provider(history)
    results=[]
    for label,metadata in PRIMARY.items():
        h=_utc(metadata["halving"])
        end=min(h+pd.Timedelta(days=SCORE_DAYS),risk.index[-1])
        fx=fx_fetcher(h,end)
        for offset in START_DAYS:
            start=h+pd.Timedelta(days=int(offset))
            if start>=end:continue
            report=matched_replay(risk,fx,start=start,terminal=end)
            report.update({
                "cycle":label,"start_day_after_halving":int(offset),
                "complete":end==h+pd.Timedelta(days=SCORE_DAYS),
                "onchain_point_in_time_vintage_verified":False,
                "fear_greed_history_available":False,
                "uses_actual_user_portfolio":False,
                "is_exact_production_data_parity":False,
            })
            results.append(report)
    return {
        "study":"V5.8.2 Productive DCA: historical hindsight capital distribution vs deployable remaining-weeks sizing",
        "research_only":True,
        "production_code_or_settings_modified":False,
        "original_curve_used_unchanged":True,
        "actual_live_sizing_formula_reproduced":True,
        "exact_live_data_component_parity":False,
        "historic_risk_provider_vintage_verified":False,
        "price_observation_cutoff":str(risk.index[-1].date()),
        "risk_inputs_available":"BTC close & Oct-2026 exported MVRV; unavailable Fear & Greed omitted",
        "retrospective_budget_normalisation":"all future multipliers known",
        "cohort_rows":results,
        "limitations":[
            "Hindsight allocator uses entire future sum of weight values; not a real investment recommendation.",
            "DCA Today fraction uses remaining AUD cash / weeks remaining * current risk weight.",
            "Real DCA Today uses contemporaneous today's risk score, but this replay strictly lags it 1 day.",
            "Historical MVRV CSV data may be retrospectively revised and does not represent independently captured provider vintages.",
            "Omitted Fear & Greed history means risk composites are NOT the full contemporaneous Production risk score.",
            "Fee/tax outcomes are illustrative A$3 FIFO SMSF and BTC/USD close proxy, not ASX:IBIT fills or exact SMSF phase.",
            "The calendar end day1150 is a selected research horizon, not verified actual 2026 investment exit date.",
        ],
    }


def main(argv=None):
    p=argparse.ArgumentParser()
    p.add_argument("--out",type=Path,
                   default=Path("artifacts/production_causal_budget_audit"))
    opt=p.parse_args(argv)
    report=audit(read_exported_history())
    opt.out.mkdir(parents=True,exist_ok=True)
    (opt.out/"audit.json").write_text(json.dumps(report,indent=2))
    fields=("cycle","start_day_after_halving","start","terminal","complete",
            "causal_vs_hindsight_aftertax_pct",
            "causal_vs_calendar_equal_aftertax_pct",
            "hindsight_vs_calendar_equal_aftertax_pct")
    with (opt.out/"cohorts.csv").open("w",newline="") as f:
        writer=csv.DictWriter(f,fieldnames=fields,extrasaction="ignore")
        writer.writeheader()
        writer.writerows(report["cohort_rows"])
    for x in report["cohort_rows"]:
        print(json.dumps({
            "cycle":x["cycle"],"startday":x["start_day_after_halving"],
            "complete":x["complete"],
            "causal_vs_hindsight_aftertax_pct":
                x["causal_vs_hindsight_aftertax_pct"],
            "causal_vs_equal_aftertax_pct":
                x["causal_vs_calendar_equal_aftertax_pct"],
            "hindsight_vs_equal_aftertax_pct":
                x["hindsight_vs_calendar_equal_aftertax_pct"],
            "causal_btc":x["strategies"][
                "causal_live_remaining_cash_weeks"]["btc"],
            "hindsight_btc":x["strategies"][
                "historical_omniscient_equal_capital"]["btc"],
            "causal_unspent_pct":x["strategies"][
                "causal_live_remaining_cash_weeks"]["cash_left_pct"],
        },sort_keys=True))
    print("RESEARCH ONLY: NO LIVE PRODUCTION, NTFY OR PORTFOLIO CHANGE")


if __name__=="__main__":
    main()
