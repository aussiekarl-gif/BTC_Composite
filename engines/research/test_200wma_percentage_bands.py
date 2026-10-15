"""Research-only BTC buy/sell using percentage deviation from 200WMA.

Prior completed weekly close / prior trailing 200-week mean sets signal.
Next weekly close executes. No 30-week MA or hindsight peaks.
Fixed bands and fractions, initial full BTC investment, 0.1% fee.
"""
import json
from pathlib import Path
import numpy as np
import pandas as pd

CAP=500000.; FEE=.001

def run(s, ma, start, sell_at, buy_at, sell_fraction=.25, buy_fraction=.5):
    btc=CAP*(1-FEE)/float(s.iloc[start+1]); cash=0.; buys=1;sells=0
    # Trade on crossings, not every week in the same zone.
    prev_dev=None
    for i in range(start+2,len(s)):
        idx=i-1
        ref=float(ma.iloc[idx])
        if not np.isfinite(ref) or ref<=0:continue
        dev=float(s.iloc[idx]/ref-1)
        px=float(s.iloc[i])
        if prev_dev is not None:
            if dev>=sell_at and prev_dev<sell_at and btc>0:
                sold=btc*sell_fraction;btc-=sold;cash+=sold*px*(1-FEE);sells+=1
            elif dev<=buy_at and prev_dev>buy_at and cash>0:
                spent=cash*buy_fraction;cash-=spent;btc+=spent*(1-FEE)/px;buys+=1
        prev_dev=dev
    return {"final_usd":round(btc*float(s.iloc[-1])+cash,2),
            "btc":round(btc,6),"cash_usd":round(cash,2),"sells":sells,"buys":buys}

def main():
    df=pd.read_csv("data/price_200_week_moving_average_200wma__2026-10-07T21-20-24.csv")
    df["date"]=pd.to_datetime(df["timestamp"],unit="ms",utc=True)
    s=pd.Series(pd.to_numeric(df["Price"],errors="coerce").to_numpy(),index=df["date"]).sort_index().resample("W-MON").last().dropna()
    ma=s.shift(1).rolling(200,min_periods=200).mean()
    configs=[(sell,buy) for sell in (.5,1.,2.) for buy in (-.3,-.1,0.,.1)]
    cohorts=[]
    for year in range(2017,2025):
        d=s.index[(s.index.year==year)&(s.index.month==1)]
        if len(d)==0:continue
        start=s.index.get_loc(d[0])
        if start<201:continue
        hold=CAP*(1-FEE)/float(s.iloc[start+1])*float(s.iloc[-1])
        runs={}
        for sell,buy in configs:
            key=f"sell_plus_{round(sell*100)}pct_buy_{round(buy*100):+d}pct"
            result=run(s,ma,start,sell,buy)
            result["vs_hold_pct"]=round(100*(result["final_usd"]/hold-1),2)
            runs[key]=result
        cohorts.append({"year":year,"hold_usd":round(hold,2),"runs":runs})
    summary={}
    for sell,buy in configs:
        key=f"sell_plus_{round(sell*100)}pct_buy_{round(buy*100):+d}pct"
        arr=[c["runs"][key]["vs_hold_pct"] for c in cohorts]
        summary[key]={"beat_hold_years":sum(x>0 for x in arr),
                      "median_vs_hold_pct":round(float(np.median(arr)),2),
                      "worst_vs_hold_pct":round(min(arr),2),
                      "total_sell_trades":sum(c["runs"][key]["sells"] for c in cohorts),
                      "total_rebuys":sum(c["runs"][key]["buys"]-1 for c in cohorts)}
    out={"currency":"USD","initial_capital":CAP,"fee":FEE,
         "signal":"Prior close deviation from trailing 200-week SMA; next-week execution",
         "trade_policy":"25% of BTC sold at upward crossing of upper band; 50% of cash reinvested at downward crossing of lower band",
         "limitations":"Historical overlapping cohorts; not out-of-sample, no tax or additional slippage; zero-crossing entries can miss signals when starting already beyond band.",
         "summary":summary,"cohorts":cohorts}
    p=Path("research_outputs/200wma_percentage_bands.json");p.parent.mkdir(parents=True,exist_ok=True)
    p.write_text(json.dumps(out,indent=2))
    print(json.dumps(out,indent=2))
if __name__=="__main__":main()
