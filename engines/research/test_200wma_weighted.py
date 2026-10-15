"""Research-only 200WMA-weighted accumulation with multi-start cohorts.

USD archived daily BTC price. Each cohort starts with 500k USD cash.
For each week, signal uses prior weekly close and prior 200 weekly closes.
Execution is next weekly close. No sell, 0.1% buy fee, no CGT.
No threshold optimization or claim of independent walk-forward validation.
"""
import json
from pathlib import Path
import pandas as pd
import numpy as np

INITIAL=500000.
FEE=.001
def run(s, ma, start, method):
    cash=INITIAL;btc=0.; buys=0
    first=start+1
    last=min(start+104,len(s)-1)
    # Equal deployment horizon: 104 weeks; accelerated purchases consume
    # remaining cash. Any residual is invested at the final deadline.
    for i in range(first,len(s)):
        if cash<=1e-8:break
        signal_i=i-1
        ratio=float(s.iloc[signal_i]/ma.iloc[signal_i])
        if not np.isfinite(ratio):continue
        if method=="hold":
            fraction=1.
        elif method=="fixed_104w":
            fraction=min(1.,1./max(1,last-i+1))
        else:
            base=1./max(1,last-i+1)
            if method=="weighted":
                mult=4. if ratio<=1 else 2. if ratio<=1.25 else 1. if ratio<=1.75 else .5
            elif method=="frontload":
                mult=4. if ratio<=1 else 2. if ratio<=1.25 else 1.
            else:raise ValueError(method)
            fraction=min(1.,base*mult)
        if i>=last:fraction=1.
        spent=cash*fraction
        btc+=spent*(1-FEE)/float(s.iloc[i])
        cash-=spent
        buys+=1
    return {"final_usd":round(cash+btc*float(s.iloc[-1]),2),"btc":round(btc,6),
            "cash_usd":round(cash,2),"buy_count":buys}

def main():
    data=pd.read_csv("data/price_200_week_moving_average_200wma__2026-10-07T21-20-24.csv")
    data["date"]=pd.to_datetime(data["timestamp"],unit="ms",utc=True)
    s=pd.Series(pd.to_numeric(data["Price"],errors="coerce").to_numpy(),index=data["date"]).sort_index().resample("W-MON").last().dropna()
    ma=s.shift(1).rolling(200,min_periods=200).mean()
    methods=["hold","fixed_104w","weighted","frontload"]
    cohorts=[]
    for year in range(2017,2025):
        dates=s.index[(s.index.year==year)&(s.index.month==1)]
        if len(dates)==0:continue
        start=s.index.get_loc(dates[0])
        if start<201:continue
        values={m:run(s,ma,start,m) for m in methods}
        cohorts.append({"year":year,"start":str(s.index[start].date()),"results":values,
                        "weighted_vs_hold_pct":round(100*(values["weighted"]["final_usd"]/values["hold"]["final_usd"]-1),2),
                        "frontload_vs_hold_pct":round(100*(values["frontload"]["final_usd"]/values["hold"]["final_usd"]-1),2)})
    report={"currency":"USD","capital":INITIAL,"fee":FEE,"end":str(s.index[-1].date()),
            "source":"Archived BTC/USD historical price; research-only",
            "caution":"All cohorts share final date; overlapping periods, not independent; no taxes or additional slippage.",
            "cohorts":cohorts,
            "weighted_beat_hold":sum(c["weighted_vs_hold_pct"]>0 for c in cohorts),
            "frontload_beat_hold":sum(c["frontload_vs_hold_pct"]>0 for c in cohorts),
            "cohort_count":len(cohorts)}
    out=Path("research_outputs/200wma_weighted_cohorts.json")
    out.parent.mkdir(parents=True,exist_ok=True)
    out.write_text(json.dumps(report,indent=2))
    print(json.dumps(report,indent=2))
if __name__=="__main__":main()
