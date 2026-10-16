"""Day-500 adaptive BTC DCA-out, independent numerical research (no live orders).

All experiments start with exactly ONE BTC already owned at halving day 500.
The user's real AUD500k portfolio begins in 2026 and is NOT represented.
No future price enters any decision; day-500 is a calendar-only 5% sale,
and subsequent weekly fractions are based strictly on completed PRIOR
daily close history.

Evaluate:
  (a) 5% at day500, then momentum/rollover variable sell-size weekly,
  (b) three parameter-freeze candidate speeds (slower/balanced/faster),
  (c) exact-day500 liquidation,
  (d) front-loaded BTC weekly fixed days 525/532/539/546/553/560,
  (e) no-sale hold.
All benchmark accounts marked on SAME post-halving day730. Dynamic
schedules NEVER force-liquidate leftovers at day730; account marks
residual BTC to fair market price. Both BTC disposal VWAP and fraction
of BTC sold are required: selling only 1% near a peak does not qualify.

This study is in-sample (pre-defined after inspection) and USD-gross;
AUD3 order charge recorded separately, not illegitimately subtracted
from USD cash. No SMSF annual CGT / real portfolio inputs.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd

from engines.research.halving_window_top_audit import make_day500_then_weekly_schedule
from engines.research.top_signal_horse_race import (
    HALVINGS, PEAK_WINDOWS, read_exported_history,
)

START_DAY=500
REVIEW_DAY=730
WEEK_DAYS=tuple(range(START_DAY+7,REVIEW_DAY+1,7))
# Fixed rule candidates, NOT tuned to the current results.
POLICIES={
    "cautious": {"initial":.05,"high":.035,"neutral":.010,"breakdown":.065},
    "balanced": {"initial":.05,"high":.060,"neutral":.018,"breakdown":.085},
    "faster": {"initial":.05,"high":.085,"neutral":.030,"breakdown":.110},
}


def _validate_price(price, start, end):
    if not isinstance(price.index,pd.DatetimeIndex) or price.index.tz is None:
        raise ValueError("Require timezone-aware daily prices")
    if price.index.has_duplicates or not price.index.is_monotonic_increasing:
        raise ValueError("Invalid duplicated/unsorted price history")
    if pd.to_numeric(price,errors="coerce").isna().any() or price.le(0).any():
        raise ValueError("Require positive numerical prices")
    expected=pd.date_range(start-pd.Timedelta(days=91),end,freq="D",tz="UTC")
    if not expected.isin(price.index).all():
        raise ValueError("Missing a required historical daily close")


def _prior_state(price, day):
    observed=price.loc[day-pd.Timedelta(days=90):day-pd.Timedelta(days=1)]
    assert len(observed)==90
    prior=float(observed.iloc[-1])
    hi=float(observed.max())
    ma50=float(observed.iloc[-50:].mean())
    prior_50=float(price.loc[
        day-pd.Timedelta(days=64):day-pd.Timedelta(days=15)].mean())
    drawdown=1-prior/hi
    # Two independent confirmations for hard riskoff. The first can
    # protect after a sharp break; the second avoids panic-only sell.
    if drawdown>=.15 and prior<ma50 and ma50<prior_50:
        regime="breakdown"
    elif prior>=.95*hi and prior>ma50:
        regime="high"
    else:
        regime="neutral"
    return regime,{"prior_close":prior,"trailing_high":hi,
                   "drawdown_from_prior_90d_high_pct":100*drawdown,
                   "prior_sma50":ma50,"prior_sma50_14days_ago":prior_50}


def adaptive_weekly_exit(price, halving, *, policy="balanced",
                         day500_fraction=None, review_day=REVIEW_DAY):
    if policy not in POLICIES:
        raise ValueError("Unknown predeclared policy")
    if review_day<=START_DAY:
        raise ValueError("Review date must follow day 500")
    params=POLICIES[policy]
    initial=params["initial"] if day500_fraction is None else day500_fraction
    if not 0<=initial<=.2:
        raise ValueError("Initial sale must be 0 to 20% of BTC")
    start=halving+pd.Timedelta(days=START_DAY)
    end=halving+pd.Timedelta(days=review_day)
    _validate_price(price,start,end)
    rows=[]
    left=1.0
    proceeds=0.0
    for d in [START_DAY]+list(range(START_DAY+7,review_day+1,7)):
        when=halving+pd.Timedelta(days=d)
        px=float(price.loc[when])
        if d==START_DAY:
            regime="maturity-start"
            sale=min(left,initial)
            information=None
        else:
            regime,information=_prior_state(price,when)
            # Target sales are percentages of ORIGINAL 1BTC, not
            # unknowingly shifting shares of still-available holdings.
            sale=min(left,params[regime])
        if sale<=1e-12:
            continue
        left-=sale
        proceeds+=sale*px
        rows.append({
            "date":str(when.date()),"halving_day":d,
            "signal_regime":regime,
            "btc_sold":round(sale,10),
            "execution_price_usd_per_btc":round(px,2),
            "cash_proceeds_usd":round(sale*px,4),
        })
        if left<1e-10:
            left=0.
            break
    sold=1-left
    return {
        "model":f"day500_weekly_dynamic_{policy}",
        "first_order_date":rows[0]["date"] if rows else None,
        "last_order_date":rows[-1]["date"] if rows else None,
        "btc_sold":round(sold,9),
        "btc_left":round(left,9),
        "gross_proceeds_usd":round(proceeds,4),
        "executed_btc_weighted_sale_price_usd":round(proceeds/sold,2) if sold>0 else None,
        "orders":len(rows),
        "brokerage_aud_3_per_order":3*len(rows),
        "ending_mark_usd":round(proceeds+left*float(price.loc[end]),4),
        "end_observation_date":str(end.date()),
        "sale_detail":rows,
    }


def baseline_exit(price,halving,*,policy="weekly_525"):
    date=halving+pd.Timedelta(days=REVIEW_DAY)
    _validate_price(price,halving+pd.Timedelta(days=START_DAY),date)
    if policy=="hold":
        return {"model":"hold","btc_sold":0.0,"btc_left":1.0,
                "gross_proceeds_usd":0.,"executed_btc_weighted_sale_price_usd":None,
                "orders":0,"brokerage_aud_3_per_order":0,
                "ending_mark_usd":round(float(price.loc[date]),4),
                "end_observation_date":str(date.date()),"sale_detail":[]}
    if policy=="day500":
        w=price.loc[halving+pd.Timedelta(days=START_DAY)]
        return {"model":"day500_all","btc_sold":1.0,"btc_left":0.0,
                "gross_proceeds_usd":round(float(w),4),
                "executed_btc_weighted_sale_price_usd":round(float(w),2),
                "orders":1,"brokerage_aud_3_per_order":3,
                "ending_mark_usd":round(float(w),4),
                "end_observation_date":str(date.date()),"sale_detail":[]}
    if policy=="weekly_525":
        data=make_day500_then_weekly_schedule(price,halving,day500_fraction=0.)
        return {"model":"six_weekly_frontloaded_525_560",
                "btc_sold":1.0,"btc_left":0.0,
                "gross_proceeds_usd":data["gross_vwap_usd_per_btc"],
                "executed_btc_weighted_sale_price_usd":data["gross_vwap_usd_per_btc"],
                "orders":data["sales"],
                "brokerage_aud_3_per_order":data["brokerage_aud_at_3_per_order"],
                "ending_mark_usd":data["gross_vwap_usd_per_btc"],
                "end_observation_date":str(date.date()),"sale_detail":[]}
    raise ValueError("Unknown baseline")


def evaluate_all(history):
    price=history.loc[:"2026-10-07","price_usd"]
    results=[]
    for halving,cycle in zip(HALVINGS,("2013","2017","2021","2025")):
        s,e=PEAK_WINDOWS[cycle]
        peak=price.loc[s:e]
        if peak.empty:
            raise ValueError("Missing designated scoring cycle")
        peak_close=float(peak.max())
        peak_date=peak.idxmax()
        start=halving+pd.Timedelta(days=START_DAY)
        review=halving+pd.Timedelta(days=REVIEW_DAY)
        scenarios=[
            baseline_exit(price,halving,policy="hold"),
            baseline_exit(price,halving,policy="day500"),
            baseline_exit(price,halving,policy="weekly_525"),
        ]
        scenarios.extend(adaptive_weekly_exit(price,halving,policy=p)
                         for p in POLICIES)
        for row in scenarios:
            soldprice=row["executed_btc_weighted_sale_price_usd"]
            row["sale_vwap_error_below_hindsight_top_pct"]=(
                round(100*(1-soldprice/peak_close),3)
                if soldprice is not None else None)
            # Day-730 same-horizon marked equity can be BETTER if
            # price later collapses, even if sold too far from peak.
            hold_at_review=scenarios[0]["ending_mark_usd"]
            row["relative_terminal_usd_wealth_vs_hold_pct"]=round(
                100*(row["ending_mark_usd"]/hold_at_review-1),3)
            row["btc_sold_at_least_75pct"]=row["btc_sold"]>=.75
            row["met_25pct_sale_price_and_75pct_deployed"]=bool(
                soldprice is not None
                and soldprice>=.75*peak_close
                and row["btc_sold"]>=.75)
            row.pop("sale_detail",None)
        results.append({
            "cycle":cycle,
            "halving_date":str(halving.date()),
            "start_day500":str(start.date()),
            "review_day730":str(review.date()),
            "hindsight_peak_date":str(peak_date.date()),
            "hindsight_peak_close_usd":round(peak_close,2),
            "mark_at_review_close_usd":round(float(price.loc[review]),2),
            "scenarios":scenarios,
        })
    summary=[]
    names=[r["model"] for r in results[0]["scenarios"]]
    for model in names:
        group=[next(v for v in x["scenarios"] if v["model"]==model)
               for x in results]
        summary.append({
            "model":model,
            "years_scored":len(group),
            "modern_2017_2021_2025_meet_25pct_with_75pct_sold":sum(
                x["met_25pct_sale_price_and_75pct_deployed"] for x in group[1:]),
            "all_cycles_meet":sum(x["met_25pct_sale_price_and_75pct_deployed"] for x in group),
            "mean_modern_ending_value_vs_hold_pct":round(float(np.mean(
                [x["relative_terminal_usd_wealth_vs_hold_pct"]
                 for x in group[1:]])),3),
            "worst_modern_relative_to_hold_pct":round(float(np.min(
                [x["relative_terminal_usd_wealth_vs_hold_pct"]
                 for x in group[1:]])),3),
        })
    return {
        "research_only":True,
        "comparison":"Same one-BTC stake at halving day 500, sell USD, mark unsold BTC and cash on day 730",
        "data_start":str(price.index[0]),
        "data_end":str(price.index[-1]),
        "rule_parameters":POLICIES,
        "cycle_results":results,
        "summary":summary,
        "warnings":[
            "The choice of day500 and policy parameters are RESEARCH hypotheses selected after historical cycles; NOT out of sample.",
            "Every sale fraction and date is based on the known halving plus prior completed BTC close history.",
            "The 2013 peak preceded day500, so no day500 exit can meet historic top proximity in that cycle.",
            "No policy is guaranteed to find every future peak or increase after-tax repurchase BTC.",
            "Terminal marked wealth on day730 equals sale cash + unsold BTC valued at day730 BTC/USD.",
            "Average price of sold BTC alone is not a success unless meaningful BTC proportion is sold; threshold 75% is reported separately.",
            "USD gross; AUD3 order fees displayed but NOT deducted from USD wealth, no FX/ETF costs or SMSF CGT.",
            "Historical source CSVs created in 2026; past vintage risk indicators are NOT used.",
            "User actual A$500k was deployed in 2026, so 2024 halving day500 in Sep 2025 has ALREADY PASSED.",
            "No changes to Production, user saved My Portfolio, or authoritative master.",
        ],
    }


def main():
    p=argparse.ArgumentParser()
    p.add_argument("--output",default="")
    args=p.parse_args()
    raw=read_exported_history()
    out=json.dumps(evaluate_all(raw),indent=2,allow_nan=False)
    if args.output:
        Path(args.output).write_text(out+"\n",encoding="utf-8")
    print(out)


if __name__=="__main__":
    main()
