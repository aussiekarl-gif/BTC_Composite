"""RESEARCH ONLY: verify and extend weekly BTC/AUD observations beyond master.

Never modify central BTC master, user portfolio, Production or stored risk scores.
Read public Blockchain.com BTC/USD chart and Frankfurter AUD-per-USD FX, align
only to the last available USD/BTC and FX observation ON OR BEFORE each Monday.
Require overlap agreement to historical AUD master, label all sources and dates.

Create an entirely *separate* aud-price-only causal walk-forward Power Law risk
candidate. This is NOT a reconstruction/certification of the original master
risk_score, nor the Production Research WF PL in USD. Pre-2026 prices are used
only to warm indicators. No data after a requested as-of date.
"""
from __future__ import annotations

import argparse
import json
import math
import datetime as dt

import numpy as np
import pandas as pd
import requests

from engines.research.full_cycle_reinvestment import validate_history
from engines.research.real_2026_deployment_audit import evaluate_cohorts

PRICE_ENDPOINT = "https://api.blockchain.info/charts/market-price"
FX_ENDPOINT = "https://api.frankfurter.app/"
MIN_OVERLAP = 4
MAX_MEDIAN_DEVIATION_PCT = 5.0
MAX_SINGLE_DEVIATION_PCT = 12.0
GENESIS = pd.Timestamp("2009-01-03", tz="UTC")
SOURCE_DATE = "2026-05-01"


def normalise_utc_index(points, *, name, numeric_field):
    result=pd.DataFrame(points)
    if not {"date",numeric_field}.issubset(result.columns):
        raise ValueError(f"{name}: missing required columns")
    result["date"]=pd.to_datetime(result["date"],utc=True,errors="coerce").dt.normalize()
    result[numeric_field]=pd.to_numeric(result[numeric_field],errors="coerce")
    result=result.dropna(subset=["date",numeric_field])
    result=result.loc[np.isfinite(result[numeric_field]) & result[numeric_field].gt(0)]
    if result.empty:
        raise ValueError(f"{name}: no valid dated prices")
    if result["date"].duplicated().any():
        raise ValueError(f"{name}: conflicting duplicate timestamps")
    return result.sort_values("date").set_index("date")[[numeric_field]]


def parse_blockchain_price(payload):
    if not isinstance(payload,dict) or not isinstance(payload.get("values"),list):
        raise ValueError("Invalid Blockchain.com chart response")
    pts=[]
    for p in payload["values"]:
        try:
            date=pd.Timestamp(float(p["x"]),unit="s",tz="UTC")
            price=float(p["y"])
        except (TypeError,ValueError,KeyError,OverflowError):
            continue
        pts.append({"date":date,"btc_usd":price})
    return normalise_utc_index(pts,name="Blockchain.com",numeric_field="btc_usd")


def parse_frankfurter_fx(payload):
    rates=payload.get("rates") if isinstance(payload,dict) else None
    if not isinstance(rates,dict):
        raise ValueError("Invalid Frankfurter API response")
    pts=[]
    for date,v in rates.items():
        try:
            aud_per_usd=float(v["AUD"])
            if aud_per_usd>0 and math.isfinite(aud_per_usd):
                pts.append({"date":date,"aud_per_usd":aud_per_usd})
        except (TypeError,ValueError,KeyError):
            continue
    return normalise_utc_index(pts,name="Frankfurter",numeric_field="aud_per_usd")


def fetch_public_series(*, asof, timeout=30):
    end=pd.Timestamp(asof)
    if end.tzinfo is None: end=end.tz_localize("UTC")
    else: end=end.tz_convert("UTC")
    end=end.normalize()
    now=pd.Timestamp.now(tz="UTC").normalize()
    if end>now:
        raise ValueError("Do not fetch future observations")
    price_response=requests.get(
        PRICE_ENDPOINT,
        params={"timespan":"all","format":"json","sampled":"false"},
        headers={"User-Agent":"BTC-Composite-Research-Audit/1.0"},
        timeout=timeout)
    price_response.raise_for_status()
    price=parse_blockchain_price(price_response.json())
    fx_response=requests.get(
        FX_ENDPOINT+f"{SOURCE_DATE}..{end.strftime('%Y-%m-%d')}",
        params={"from":"USD","to":"AUD"},
        headers={"User-Agent":"BTC-Composite-Research-Audit/1.0"},
        timeout=timeout)
    fx_response.raise_for_status()
    fx=parse_frankfurter_fx(fx_response.json())
    return price,fx


def asof_on_mondays(price, fx, *, start, end, max_price_lag_days=2,
                    max_fx_lag_days=7):
    """Never fill with later price or FX rates; reject stale observations."""
    if price.empty or fx.empty:
        raise ValueError("Cannot bridge missing price or FX")
    start=pd.Timestamp(start);end=pd.Timestamp(end)
    if start.tzinfo is None: start=start.tz_localize("UTC")
    if end.tzinfo is None: end=end.tz_localize("UTC")
    monday=pd.date_range(start.normalize(),end.normalize(),freq="W-MON",tz="UTC")
    if len(monday)<MIN_OVERLAP:
        raise ValueError("Need at least four overlapping Monday observations")
    q=pd.DataFrame({"date":monday})
    p=price.reset_index().rename(columns={"date":"price_source_date"})
    x=fx.reset_index().rename(columns={"date":"fx_source_date"})
    q=pd.merge_asof(q,p,left_on="date",right_on="price_source_date",direction="backward")
    q=pd.merge_asof(q,x,left_on="date",right_on="fx_source_date",direction="backward")
    q["price_lag_days"]=(q["date"]-q["price_source_date"]).dt.days
    q["fx_lag_days"]=(q["date"]-q["fx_source_date"]).dt.days
    bad=q["btc_usd"].isna()|q["aud_per_usd"].isna()|q["price_lag_days"].gt(max_price_lag_days)|q["fx_lag_days"].gt(max_fx_lag_days)
    if bad.any():
        failures=q.loc[bad,"date"].dt.strftime("%Y-%m-%d").tolist()
        raise ValueError(f"Missing/stale public price or FX for Mondays: {failures[:8]}")
    q["btc_price_aud"]=q["btc_usd"]*q["aud_per_usd"]
    return q.set_index("date")


def append_verified_prices(master, public, *, asof):
    """Make temporary in-memory price history, never insert into central CSV."""
    old=validate_history(master)
    cutoff=old.index[-1]
    asof_ts=pd.Timestamp(asof)
    if asof_ts.tzinfo is None: asof_ts=asof_ts.tz_localize("UTC")
    else: asof_ts=asof_ts.tz_convert("UTC")
    public=public.loc[public.index<=asof_ts].copy()
    intersect=old.index.intersection(public.index)
    if len(intersect)<MIN_OVERLAP:
        raise ValueError("Insufficient public/master overlap; don't splice providers blindly")
    overlap=100*(public.loc[intersect,"btc_price_aud"]/old.loc[intersect,"btc_price_aud"]-1).abs()
    median=float(overlap.median());worst=float(overlap.max())
    if median>MAX_MEDIAN_DEVIATION_PCT or worst>MAX_SINGLE_DEVIATION_PCT:
        raise ValueError(f"Provider overlap mismatch median={median:.2f}%, max={worst:.2f}%")
    additions=public.loc[public.index>cutoff,["btc_price_aud"]]
    if additions.empty:
        raise ValueError("Public provider supplies no verified weeks after existing research master")
    # The historical archived risk score is *NOT* carried forward, filled,
    # or misrepresented as a fresh daily score.
    combined=pd.concat([old[["btc_price_aud"]],
                        additions],axis=0).sort_index()
    if combined.index.has_duplicates or not np.isfinite(combined["btc_price_aud"]).all():
        raise ValueError("Invalid appended price history")
    return combined, {
        "master_last_price_date":str(cutoff),
        "new_public_weeks":len(additions),
        "new_first_week":str(additions.index[0]),
        "new_last_week":str(additions.index[-1]),
        "overlap_count":len(intersect),
        "median_abs_aud_price_deviation_pct":round(median,3),
        "maximum_abs_aud_price_deviation_pct":round(worst,3),
        "public_raw_final_week":str(public.index[-1]),
        "master_risk_score_not_extended":True,
    }


def expanding_aud_powerlaw_risk(weekly_prices, *, min_history_weeks=104,
                                refit_days=91, cheap=-.10, expensive=.20):
    """Strictly prior-data regression. Own candidate (not archived composite)."""
    if cheap>=expensive:
        raise ValueError("Risk scoring boundaries inverted")
    d=weekly_prices.sort_index().copy()
    dates=d.index
    if not isinstance(dates,pd.DatetimeIndex) or dates.has_duplicates:
        raise ValueError("Require unique timestamps")
    if dates.tz is None:
        raise ValueError("Require UTC-aware weekly dates")
    px=pd.to_numeric(d["btc_price_aud"],errors="coerce")
    if px.isna().any() or px.le(0).any():
        raise ValueError("Invalid prices")
    days=np.array([(x-GENESIS).days for x in dates],dtype=float)
    scores=np.full(len(d),np.nan)
    slope=intercept=None
    fitted_at=None
    for i in range(len(d)):
        # Require at least 104 PREVIOUS weekly samples and every fit uses
        # strictly j < i, even if model coefficients remain frozen.
        if i>=min_history_weeks and (fitted_at is None or
                                     (dates[i]-fitted_at).days>=refit_days):
            ok=(days[:i]>0)&np.isfinite(px.to_numpy()[:i])
            if int(ok.sum())>=min_history_weeks:
                slope,intercept=np.polyfit(np.log10(days[:i][ok]),
                                            np.log10(px.to_numpy()[:i][ok]),1)
                fitted_at=dates[i]
        if slope is not None and days[i]>0:
            relative=np.log10(float(px.iloc[i]))-(slope*np.log10(days[i])+intercept)
            scores[i]=min(1.0,max(0.0,(relative-cheap)/(expensive-cheap)))
    out=d.copy()
    out["risk_score"]=scores
    return out


def audit(master, *, asof):
    historical=validate_history(master)
    if historical.index.tz is None:
        raise ValueError("Source master must have UTC-aware weekly index")
    price,fx=fetch_public_series(asof=asof)
    period_start=historical.index[-1]-pd.Timedelta(weeks=10)
    public=asof_on_mondays(price,fx,start=period_start,end=asof)
    combined,quality=append_verified_prices(historical,public,asof=asof)
    candidate=expanding_aud_powerlaw_risk(combined)
    if candidate["risk_score"].isna().any():
        candidate=candidate.dropna(subset=["risk_score"])
    overlap=candidate.index.intersection(historical.index)
    # Compare only overlapping dates; MAE measures divergence but is not
    # permission to replace archived risk_score with our price-only signal.
    diffs=(candidate.loc[overlap,"risk_score"]-
           historical.loc[overlap,"risk_score"]).abs()
    risk_diagnostics={
        "both_risks_overlap_weeks":len(diffs),
        "mean_abs_difference":round(float(diffs.mean()),4),
        "max_abs_difference":round(float(diffs.max()),4),
        "weeks_disagree_by_over_0_20":int(diffs.gt(.20).sum()),
        "signals_are_not_equivalent":True,
    }
    cohorts=evaluate_cohorts(candidate)
    return {
        "research_only":True,
        "asof_requested":str(pd.Timestamp(asof).date()),
        "price_provider":"Blockchain.com chart market-price BTC/USD",
        "fx_provider":"Frankfurter AUD per USD from USD/AUD official historical series",
        "price_and_fx_alignment":"On/before Monday only; no future filled prices or FX",
        "data_quality":quality,
        "price_only_causal_risk":risk_diagnostics,
        "cohort_replay":cohorts,
        "warnings":[
            "AUD strict-prior Power Law candidate is NOT the existing proprietary/archived risk_score.",
            "All historical models are in-sample hypotheses; no untouched holdout.",
            "BTC USD 57,717 June 30 is a provisional reported low, not independently verified by weekly Monday closes.",
            "Public weekly BTC/AUD may differ from master since market snapshots/FX methods differ.",
            "No modification to portfolio, Production trading, or source master.",
            "Cash and positions are hypothetical fresh 2026 starts, not user's actual buys.",
            "No claims of complete cycle top/low 25% prediction accuracy.",
        ],
    }


def main():
    p=argparse.ArgumentParser()
    p.add_argument("--asof",default="2026-10-16")
    p.add_argument("--output",default="")
    args=p.parse_args()
    from engines.shared.central_data import load_master
    master=load_master(columns=["btc_price_aud","risk_score"])
    numeric=master[["btc_price_aud","risk_score"]].apply(pd.to_numeric,errors="coerce")
    valid=numeric["btc_price_aud"].gt(0)&numeric["risk_score"].between(0,1)
    result=audit(numeric.loc[valid],asof=args.asof)
    result["source_master_valid_rows"]=int(valid.sum())
    text=json.dumps(result,indent=2,allow_nan=False,
                    default=lambda obj:obj.item() if isinstance(obj,np.generic) else str(obj))
    if args.output:
        from pathlib import Path
        Path(args.output).write_text(text+"\n",encoding="utf-8")
    print(text)


if __name__=="__main__":
    main()
