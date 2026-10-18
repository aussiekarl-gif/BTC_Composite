"""Read-only numerical impact of correcting Production historical score warmup.

Not a strategy backtest, not a claim of point-in-time provider validity.
Reproduce the old and draft-corrected price/risk-component history
on identical October-2026 exported BTC/USD and MVRV-Z data. Missing
Fear&Greed is explicitly kept absent. Report only SCORE and V5.8.2
DCA risk-multiplier differences; do NOT mislabel the retrospective
budget-normalized cash allocator as live-executable return.
"""
from __future__ import annotations
import json
import pandas as pd
import numpy as np
from engines.production.production_model import (
    SMART_DCA_POINTS,add_risk_indicators,interpolate,
)
from engines.research.production_causal_budget_audit import PARAMS
from engines.research.top_signal_horse_race import read_exported_history

WINDOWS=("2017-01-01","2021-01-01","2025-01-01")
DAYS=180
WARMUP_DAYS=300

def score_inputs(history,start,end):
    pre=start-pd.Timedelta(days=WARMUP_DAYS)
    source=history.loc[pre:end]
    if source.empty or start not in source.index or end not in source.index:
        raise ValueError("Insufficient actual provider history")
    return pd.DataFrame({
        "price":source["price_usd"],
        "mvrv_z":source["mvrv_z"],
        "fear_greed":np.nan,
        "regime_score":np.nan,
    },index=source.index)

def calculate_impact(history):
    results=[]
    for st in WINDOWS:
        start=pd.Timestamp(st,tz="UTC")
        end=start+pd.Timedelta(days=DAYS)
        source=score_inputs(history,start,end)
        old=add_risk_indicators(
            source.loc[start:end].copy(),"Composite V3.6",PARAMS)
        new=add_risk_indicators(
            source.copy(),"Composite V3.6",PARAMS).loc[start:end]
        if not old.index.equals(new.index):
            raise AssertionError("Different trading dates")
        old_score=old["risk_score"].to_numpy(dtype=float)
        new_score=new["risk_score"].to_numpy(dtype=float)
        # Legacy truncated warmup often has NO valid risk-score
        # at all on early days. Do not silently convert missing risk
        # to 1x then call it a model-derived score. Report each missing
        # count and compare only the actual paired finite observations.
        paired=np.isfinite(old_score)&np.isfinite(new_score)
        if not paired.any():
            raise ValueError("No paired valid proxy risk days")
        old_mult=np.array([interpolate(SMART_DCA_POINTS,float(v))
                           if np.isfinite(v) else float("nan")
                           for v in old_score],dtype=float)
        new_mult=np.array([interpolate(SMART_DCA_POINTS,float(v))
                           if np.isfinite(v) else float("nan")
                           for v in new_score],dtype=float)
        differences=np.abs(new_score[paired]-old_score[paired])
        first=int(np.flatnonzero(paired)[0])
        results.append({
            "start_date":st,
            "old_initial_score_missing":bool(not np.isfinite(old_score[0])),
            "corrected_initial_score_missing":bool(not np.isfinite(new_score[0])),
            "old_missing_score_dates":int((~np.isfinite(old_score)).sum()),
            "corrected_missing_score_dates":int((~np.isfinite(new_score)).sum()),
            "first_day_with_both_valid":str(old.index[first].date()),
            "old_first_paired_day_score":round(float(old_score[first]),6),
            "corrected_first_paired_day_score":round(float(new_score[first]),6),
            "old_first_paired_day_multiplier":round(float(old_mult[first]),6),
            "corrected_first_paired_day_multiplier":round(float(new_mult[first]),6),
            "max_absolute_risk_score_difference":round(float(differences.max()),6),
            "median_absolute_risk_score_difference":round(float(np.median(differences)),6),
            "paired_dates_with_different_score":int((differences>1e-6).sum()),
            "valid_paired_dates":int(paired.sum()),
            "calendar_dates_checked":len(old),
            "median_multiplier_ratio_corrected_over_old":round(
                float(np.median(new_mult[paired]/old_mult[paired])),6),
        })
    return {
        "scope":"READ-ONLY old start-truncated versus draft warmup corrected risk only",
        "historical_FearGreed_missing":True,
        "archived_MVRV_vintage_not_independently_verifiable":True,
        "fixed_historic_FX_not_used":True,
        "NO_backtested_investment_returns":True,
        "NO_live_production_rule_changes":True,
        "rows":results,
    }

def main():
    print(json.dumps(calculate_impact(read_exported_history()),sort_keys=True))

if __name__=="__main__":
    main()
