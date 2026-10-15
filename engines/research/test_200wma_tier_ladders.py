"""Research-only 200WMA tiered sales + staged repurchase.
Causal weekly signal: prior weekly BTC/USD close divided by the 200-week
average of closes ending one week BEFORE that signal. Next-bar execution.
Tranches are percentages of BTC at start of each sell cycle, not remaining BTC.
Three fixed ladder shapes, with optional permanent 20% BTC core.
This is exploratory in-sample research; not a validated trading rule.
"""
import json
from pathlib import Path
import numpy as np
import pandas as pd

CAP=500000.; FEE=.001
LADDERS={"earlier":[1.6+.2*i for i in range(10)],
         "original":[2.+.2*i for i in range(9)], # tier 10 Pi Top is NOT silently assumed
         "later":[2.4+.2*i for i in range(10)]}
BUY_LEVELS=[1.25,1.10,1.0,.90,.75]

def simulate(s,ma,start,ladder,core):
    btc=CAP*(1-FEE)/float(s.iloc[start+1]); cash=0.
    anchor=btc; sold=set();bought=set();sell_count=0;buy_count=1
    prev_ratio=None
    for i in range(start+2,len(s)):
        j=i-1; avg=float(ma.iloc[j])
        if not np.isfinite(avg) or avg<=0:continue
        ratio=float(s.iloc[j])/avg
        px=float(s.iloc[i])
        if prev_ratio is not None:
            # Sell one tenth of the STARTING cycle BTC at each crossed tier,
            # with 20% optional core; no fictional Pi-Cycle indicator.
            for tier,threshold in enumerate(ladder):
                if tier not in sold and prev_ratio<threshold<=ratio:
                    tranche=min(btc-core*anchor, .1*anchor)
                    if tranche>1e-10:
                        btc-=tranche;cash+=tranche*px*(1-FEE)
                        sold.add(tier);sell_count+=1
            # Buy progressively when crossing DOWN through valuation levels.
            for tier,threshold in enumerate(BUY_LEVELS):
                if tier not in bought and prev_ratio>threshold>=ratio and cash>1e-8:
                    spent=cash/(len(BUY_LEVELS)-len(bought))
                    cash-=spent;btc+=spent*(1-FEE)/px
                    bought.add(tier);buy_count+=1
            # Re-arm only when cash is mostly redeployed AND price has returned
            # to a lower valuation regime; prevents permanent one-cycle lock.
            if cash<1 and ratio<1.25 and sold:
                anchor=btc;sold=set();bought=set()
        prev_ratio=ratio
    return {"ending_usd":round(cash+btc*float(s.iloc[-1]),2),
            "btc":round(btc,6),"cash_usd":round(cash,2),
            "sell_trades":sell_count,"buy_trades":buy_count}

def main():
    d=pd.read_csv("data/price_200_week_moving_average_200wma__2026-10-07T21-20-24.csv")
    d["date"]=pd.to_datetime(d["timestamp"],unit="ms",utc=True)
    s=pd.Series(pd.to_numeric(d["Price"],errors="coerce").to_numpy(),index=d["date"]).sort_index().resample("W-MON").last().dropna()
    ma=s.shift(1).rolling(200,min_periods=200).mean()
    cohorts=[]
    for year in range(2017,2025):
        dates=s.index[(s.index.year==year)&(s.index.month==1)]
        if not len(dates):continue
        start=s.index.get_loc(dates[0])
        if start<201:continue
        hold=CAP*(1-FEE)/float(s.iloc[start+1])*float(s.iloc[-1])
        runs={}
        for name,ladder in LADDERS.items():
            for core in (0.,.2):
                key=f"{name}_core_{round(core*100)}pct"
                result=simulate(s,ma,start,ladder,core)
                result["vs_hold_pct"]=round(100*(result["ending_usd"]/hold-1),2)
                runs[key]=result
        cohorts.append({"year":year,"buy_hold_usd":round(hold,2),"strategies":runs})
    summary={}
    for name in LADDERS:
        for core in (0.,.2):
            key=f"{name}_core_{round(core*100)}pct"
            arr=[c["strategies"][key]["vs_hold_pct"] for c in cohorts]
            summary[key]={"beat_hold_years":sum(x>0 for x in arr),
                          "median_vs_hold_pct":round(float(np.median(arr)),2),
                          "worst_vs_hold_pct":round(min(arr),2),
                          "total_sells":sum(c["strategies"][key]["sell_trades"] for c in cohorts),
                          "total_buys":sum(c["strategies"][key]["buy_trades"] for c in cohorts)}
    out={"currency":"USD","capital":CAP,"fee":FEE,
         "ladders":LADDERS,"buy_levels":BUY_LEVELS,
         "notes":"Original tier 10 Pi Cycle Top intentionally omitted until a validated point-in-time signal exists; original model sells at most 90% BTC. Core 20% caps sellable BTC. Crossing-only signals may leave cash undeployed. Overlapping historical cohorts, not independent validation.",
         "summary":summary,"cohorts":cohorts}
    p=Path("research_outputs/200wma_tier_ladders.json")
    p.parent.mkdir(parents=True,exist_ok=True)
    p.write_text(json.dumps(out,indent=2))
    print(json.dumps(out,indent=2))
if __name__=="__main__":main()
