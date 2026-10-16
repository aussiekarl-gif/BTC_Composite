"""Read-only BTC halving-clock sell-window audit (historically FITTED idea).

Days since known fixed halvings are available causally. Date bands
[525,560], [500,575] and front-loaded 525-560 are PREDECLARED within this
file, but *were chosen after inspecting 2017/2021/2025 peaks*. Their
backtest is entirely in-sample and 2013 is a crucial transfer-failure case.

Scoring assumes a 1 BTC stake held before each halving and disposes
100% of that BTC across available daily USD closes. This is NOT a
self-financing buy/sell portfolio, nor an SMSF tax-adjusted test.
Terminal results for user's real AUD500k starting in 2026 not implied.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd

from engines.research.top_signal_horse_race import (
    HALVINGS, PEAK_WINDOWS, read_exported_history,
)

# Distinct research controls; all parameter choices are in-sample
WINDOWS=(
    ("narrow_equal",525,560,"equal"),
    ("narrow_frontloaded",525,560,"frontloaded"),
    ("narrow_trend_weighted",525,560,"trend_weighted"),
    ("broad_equal",500,575,"equal"),
)


def make_sale_schedule(price, halving, *, day_start, day_end,
                       method="equal"):
    """Sell precommitted fractions of 1 BTC on fixed days after halving.

    A sell at date t does not use any price t+1..future to determine size
    or date. Fractions sum to 1 across the predefined window.
    """
    if day_end<day_start or day_start<0:
        raise ValueError("Invalid day band")
    if method not in ("equal","frontloaded","trend_weighted"):
        raise ValueError("Invalid method")
    dates=[halving+pd.Timedelta(days=i)
           for i in range(day_start,day_end+1)]
    series=price.reindex(dates)
    if series.isna().any():
        raise ValueError("Price missing in full scheduled execution window")
    n=len(dates)
    if method=="trend_weighted":
        # Sequential and causal: dynamic sizing uses only *prior* daily
        # BTC/USD prices. Strong relative position near observed 90-day
        # high accelerates distribution, but all remaining BTC must sell
        # by fixed window expiry (that expiry remains a major risk).
        weights=[]
        left=1.
        for j,day in enumerate(dates):
            remaining_days=n-j
            if j==n-1:
                sold=left
            else:
                observed=price.loc[
                    (price.index<day)&(price.index>=day-pd.Timedelta(days=90))]
                if len(observed)<21 or observed.isna().any():
                    raise ValueError("Insufficient strictly prior momentum history")
                prev=float(observed.iloc[-1])
                rolling_high=float(observed.max())
                ma21=float(observed.iloc[-21:].mean())
                strength=(1.80 if prev>=.98*rolling_high and prev>ma21
                          else .75)
                sold=min(left,left/remaining_days*strength)
            left-=sold
            weights.append(sold)
        w=np.asarray(weights,dtype=float)
    else:
        w=(np.ones(n,dtype=float) if method=="equal"
           else np.arange(n,0,-1,dtype=float))
        w=w/w.sum()
    if not np.isclose(w.sum(),1.):
        raise AssertionError("Sale fractions don't sum to 1 BTC")
    vwap=float(np.dot(series.to_numpy(dtype=float),w))
    return {
        "first_sale_day":str(dates[0].date()),
        "last_sale_day":str(dates[-1].date()),
        "sales":n,
        "gross_vwap_usd_per_btc":round(vwap,2),
        "total_fraction_sold":round(float(w.sum()),8),
    }


def compare_windows(history,*,peak_windows=PEAK_WINDOWS):
    data=history.loc[:"2026-10-07","price_usd"]
    if data.empty:raise ValueError("Empty date-price source")
    scores=[]
    for halving,label in zip(HALVINGS,("2013","2017","2021","2025")):
        s,e=peak_windows[label]
        segment=data.loc[s:e]
        if segment.empty:
            raise ValueError(f"No source price data for {label}")
        top_date=segment.idxmax()
        top_price=float(segment.max())
        scenario=[]
        for name,start,end,method in WINDOWS:
            outcome=make_sale_schedule(data,halving,
                                       day_start=start,day_end=end,
                                       method=method)
            outcome["name"]=name
            outcome["error_below_hindsight_peak_pct"]=round(
                100*(1-outcome["gross_vwap_usd_per_btc"]/top_price),3)
            outcome["met_25pct_average_selling_error"]=bool(
                outcome["gross_vwap_usd_per_btc"]>=.75*top_price)
            scenario.append(outcome)
        scores.append({
            "cycle":label,
            "halving":str(halving.date()),
            "actual_peak_close_date_hindsight":str(top_date.date()),
            "actual_peak_close_usd_hindsight":round(top_price,2),
            "actual_days_from_halving_to_peak":int((top_date-halving).days),
            "sell_windows":scenario,
        })
    summary=[]
    for name,_,_,_ in WINDOWS:
        scores_for=[next(x for x in r["sell_windows"] if x["name"]==name)
                    for r in scores]
        summary.append({
            "rule":name,
            "all_four_cycles_within_25pct":sum(
                x["met_25pct_average_selling_error"] for x in scores_for),
            "modern_2017_2021_2025_within_25pct":sum(
                x["met_25pct_average_selling_error"]
                for x in scores_for[1:]),
            "mean_modern_error_pct":round(float(np.mean([
                x["error_below_hindsight_peak_pct"]
                for x in scores_for[1:]])),3),
        })
    return {
        "research_only":True,
        "price_observations":len(data),
        "last_price_date":str(data.index[-1].date()),
        "schedules":list(WINDOWS),
        "hindsight_scored_cycles":scores,
        "summary":summary,
        "warnings":[
            "This is in-sample time-window curve fitting after known 2017/2021/2025 peak clustering, not proven generalization.",
            "2013 top occurred much earlier after halving: test exposes structural break.",
            "Pre-set calendar sell fractions are actually tradeable; top dates are hindsight ONLY for score.",
            "Selling over multiple days reduces precise top dependency but can exit prematurely if top timing moves.",
            "Trend-weighted window reacts only to previous daily BTC/USD prices, with 1.8x remaining-day sale near observed 90-day highs and 0.75x otherwise.",
            "A trend-dependent sales model was proposed after observing previous patterns and has no untouched historical holdout.",
            "Values gross USD/BTC excluding AUD 3 brokerage, ETF spreads and SMSF realized CGT.",
            "One BTC stake already owned before halving. The user's actual A$500k started in 2026 and is not represented.",
            "No sell/rebuy cycles, after-tax terminal capital, drawdown or future market regime validation.",
            "No Production, user Portfolio or master data changes.",
        ],
    }


def main():
    p=argparse.ArgumentParser()
    p.add_argument("--output",default="")
    args=p.parse_args()
    src=read_exported_history()
    result=compare_windows(src)
    out=json.dumps(result,indent=2,allow_nan=False)
    if args.output:
        Path(args.output).write_text(out+"\n",encoding="utf-8")
    print(out)


if __name__=="__main__":
    main()
