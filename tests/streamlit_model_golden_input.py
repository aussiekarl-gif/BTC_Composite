"""Offline golden-fixture input cases for Streamlit Production and Research models.

Production V5.8.2 and Research V5.9 must not silently change when we later
extract duplicate helpers. Only deterministic synthetic BTC history; no
API calls, no Streamlit UI, Google Sheets, or portfolio storage writes.
"""
import datetime as dt
import json
import math
from pathlib import Path

import numpy as np
import pandas as pd

from engines.production import production_model as prod
from engines.research import research_model as research

GOLDEN=Path("tests/fixtures/streamlit_model_golden_v1.json")
FLOAT_DIGITS=10


def synthetic_btc_history():
    idx=pd.date_range("2020-01-01",periods=460,freq="D",tz="UTC")
    t=np.arange(len(idx),dtype=float)
    # Every observation is deterministic, reproducible and financial-data-free.
    usd=17000.*np.exp(.0013*t)*(1.+.13*np.sin(t/24.))
    mvrv=.7+2.6*(.5+.5*np.sin(t/38.))
    fg=np.clip(50+37*np.cos(t/19.),3.,96.)
    regime=np.clip(50+19*np.sin(t/30.),0.,100.)
    return pd.DataFrame({"price":usd,"mvrv_z":mvrv,
                         "fear_greed":fg,"regime_score":regime},index=idx)


def parameters(model):
    return {
        "pl_cheap":model.DEFAULT_PL_CHEAP,
        "pl_expensive":model.DEFAULT_PL_EXPENSIVE,
        "valuation_strength":model.DEFAULT_VALUATION_STRENGTH,
        "min_valuation_mult":model.DEFAULT_MIN_VALUATION_MULT,
        "max_valuation_mult":model.DEFAULT_MAX_VALUATION_MULT,
        "min_risk_components":model.DEFAULT_MIN_RISK_COMPONENTS,
        "price_position_window":model.DEFAULT_PRICE_POSITION_WINDOW,
        "risk_calibration_min_periods":model.DEFAULT_RISK_CALIBRATION_MIN_PERIODS,
        "risk_calibration_window":model.DEFAULT_RISK_CALIBRATION_WINDOW,
        "risk_calibration_blend":model.DEFAULT_RISK_CALIBRATION_BLEND,
        "absolute_risk_weight":model.DEFAULT_ABSOLUTE_RISK_WEIGHT,
        "relative_risk_weight":model.DEFAULT_RELATIVE_RISK_WEIGHT,
        "trend_er_period":model.DEFAULT_TREND_ER_PERIOD,
        "trend_fast":model.DEFAULT_TREND_FAST,
        "trend_slow":model.DEFAULT_TREND_SLOW,
        "trend_range_period":model.DEFAULT_TREND_RANGE_PERIOD,
        "trend_band_mult":model.DEFAULT_TREND_BAND_MULT,
    }


def number(v):
    if isinstance(v,(np.integer,int)):return int(v)
    x=float(v)
    return round(x,FLOAT_DIGITS) if math.isfinite(x) else None


def collect_model_snapshot(model):
    source=synthetic_btc_history()
    result=model.add_risk_indicators(source,"Composite V3.6",parameters(model))
    columns=["price","risk_score","raw_risk_score","risk_percentile",
             "mvrv_score","mayer_score","power_law_score",
             "price_position_score","valuation_multiplier",
             "absolute_risk_anchor"]
    snapshot={}
    for i in (200,320,459):
        row=result.iloc[i]
        snapshot[str(result.index[i].date())]={
            key:number(row[key]) for key in columns
        }|{"risk_zone":str(row["risk_zone"])}
    weights=pd.DataFrame({
        "actual_buy_aud":[125.,475.,0.,250.,90.],
        "btc_price_aud":[42000.,49000.,52000.,44500.,61000.],
    })
    replay,summary=model.apply_equal_capital_allocator(weights,500000.,fee_pct=.002)
    snapshot_allocator={
        "summary":{k:number(v) for k,v in summary.items()},
        "contributions":[number(v) for v in replay["actual_buy_aud"]],
        "units_by_purchase":[number(v) for v in replay["btc_bought"]],
        "cumulative_btc":[number(v) for v in replay["btc_held"]],
    }
    dates=pd.DataFrame(index=pd.date_range("2026-01-05",periods=42,freq="D"))
    dates["price"]=np.arange(len(dates),dtype=float)
    schedule={key:[d.strftime("%Y-%m-%d") for d in
       model.select_execution_dates(dates,key,2).index]
       for key in ("Daily","Weekly","Monthly")}
    return {
        "risk":snapshot,
        "allocator":snapshot_allocator,
        "schedule":schedule,
        "helpers":{
            "clamp":[number(model.clamp(x,0,1)) for x in (-1,.125,.85,2)],
            "interpolate":[number(model.interpolate([(0,3),(.3,1.5),(1,.25)],x))
                           for x in (0,.1,.3,.55,1)],
            "power_law_score":[number(v) for v in
                model.power_law_score(pd.Timestamp("2026-09-30",tz="UTC"),65000.)],
        }
    }


def collect_active_research_snapshot():
    # Research App fixes its risk_model to "Research WF Power Law".
    # This independent fixture protects that *actual Streamlit UI path*.
    source=synthetic_btc_history()
    result=research.add_risk_indicators(source,"Research WF Power Law",parameters(research))
    cols=["price","risk_score","raw_risk_score","risk_percentile",
          "power_law_score","fair_value","power_law_residual",
          "power_law_slope","power_law_intercept","valuation_multiplier"]
    snapshots={}
    for i in (200,390,459):
        row=result.iloc[i]
        snapshots[str(result.index[i].date())]={
            key:number(row[key]) for key in cols
        }|{"risk_zone":str(row["risk_zone"])}
    return snapshots


def make_fixture():
    return {"schema":"streamlit-model-golden-v1",
            "production_sha_policy":"frozen Production V5.8.2",
            "research_version":"V5.9 separate strategy, not required to equal Production",
            "production":collect_model_snapshot(prod),
            "research":collect_model_snapshot(research),
            "research_active_power_law":collect_active_research_snapshot()}


if __name__=="__main__":
    print(json.dumps(make_fixture(),sort_keys=True,indent=2))
