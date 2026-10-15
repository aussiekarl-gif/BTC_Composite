"""Research-only causal BTC 200WMA sell/rebuy round-trip.

Weekly BTC/USD closes, 200-week SMA from strictly previous 200 weeks.
Signals evaluated using last completed week, trades executed next week.
Sell when price > 200WMA * sell_ratio AND price falls below 30-week SMA,
then repurchase when price <= 200WMA * buy_ratio OR recovers above
30-week SMA. No perfect top/bottom knowledge. Fees on each trade.
Historical cohorts start with BTC at next-week price; USD 500k each.
"""
import json
from pathlib import Path
import numpy as np
import pandas as pd

CAP=500000.; FEE=.001
def simulate(s, ma200, ma30, start, sell_ratio, buy_ratio):
    cash=0.;btc=CAP*(1-FEE)/float(s.iloc[start+1]);sells=0;buys=1
    for i in range(start+2,len(s)):
        prev=i-1
        p=float(s.iloc[prev]); a=float(ma200.iloc[prev]); b=float(ma30.iloc[prev])
        if not np.isfinite(a) or not np.isfinite(b):continue
        execution=float(s.iloc[i])
        if btc>0 and p>=sell_ratio*a and p<b:
            cash=btc*execution*(1-FEE);btc=0.;sells+=1
        elif cash>0 and (p<=buy_ratio*a or p>b):
            btc=cash*(1-FEE)/execution;cash=0.;buys+=1
    final=cash+btc*float(s.iloc[-1])
    return {"ending_usd":round(final,2),"btc":round(btc,6),"cash_usd":round(cash,2),"sells":sells,"buys":buys}
def main():
    df=pd.read_csv("data/price_200_week_moving_average_200wma__2026-10-07T21-20-24.csv")
    df["date"]=pd.to_datetime(df["timestamp"],unit="ms",utc=True)
    s=pd.Series(pd.to_numeric(df["Price"],errors="coerce").to_numpy(),index=df["date"]).sort_index().resample("W-MON").last().dropna()
    ma200=s.shift(1).rolling(200,min_periods=200).mean()
    ma30=s.shift(1).rolling(30,min_periods=30).mean()
    configs=[(sell,buy) for sell in (2.,3.,4.) for buy in (1.,1.25)]
    cohorts=[]
    for year in range(2017,2025):
        d=s.index[(s.index.year==year)&(s.index.month==1)]
        if len(d)==0:continue
        start=s.index.get_loc(d[0])
        if start<201:continue
        hold=CAP*(1-FEE)/float(s.iloc[start+1])*float(s.iloc[-1])
        runs={}
        for sell,buy in configs:
            name=f"sell_{sell:g}x_buy_{buy:g}x"
            res=simulate(s,ma200,ma30,start,sell,buy)
            res["vs_hold_pct"]=round(100*(res["ending_usd"]/hold-1),2)
            runs[name]=res
        cohorts.append({"year":year,"hold_usd":round(hold,2),"runs":runs})
    summary={}
    for sell,buy in configs:
        name=f"sell_{sell:g}x_buy_{buy:g}x"
        arr=[c["runs"][name]["vs_hold_pct"] for c in cohorts]
        summary[name]={"beat_hold_years":sum(x>0 for x in arr),
                       "median_vs_hold_pct":round(float(np.median(arr)),2),
                       "worst_vs_hold_pct":round(min(arr),2),
                       "total_sells":sum(c["runs"][name]["sells"] for c in cohorts)}
    result={"currency":"USD","starting_capital":CAP,"fee":FEE,
            "end":str(s.index[-1].date()),"source":"archived BlockHorizon BTC/USD price",
            "signal":"200WMA and 30WMA lagged one weekly bar; next-bar execution",
            "limitations":"Overlapping start-year cohorts, not independent. Same sample used to compare parameters; no tax/slippage beyond 0.1% fee.",
            "summary":summary,"cohorts":cohorts}
    p=Path("research_outputs/200wma_roundtrip.json");p.parent.mkdir(parents=True,exist_ok=True)
    p.write_text(json.dumps(result,indent=2))
    print(json.dumps(result,indent=2))
if __name__=="__main__":main()
