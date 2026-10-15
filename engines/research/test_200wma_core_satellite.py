"""Research-only core BTC + 200WMA cash-reserve strategy, USD historical cohorts.

Core allocation executes next weekly bar. Satellite reserve deploys using
prior-week price / trailing 200WMA. Remaining reserve deploys by 104-week
deadline. Fee 0.1%, no taxes, no additional slippage. No sales.
"""
import json
from pathlib import Path
import numpy as np
import pandas as pd

CAPITAL=500000.; FEE=.001
def test(s,ma,start,core,trigger):
    buy_at=start+1
    price=float(s.iloc[buy_at])
    btc=CAPITAL*core*(1-FEE)/price
    cash=CAPITAL*(1-core)
    reserve_initial=cash
    deadline=min(start+104,len(s)-1)
    for i in range(buy_at+1,len(s)):
        if cash<=1e-8:break
        ratio=float(s.iloc[i-1]/ma.iloc[i-1])
        if not np.isfinite(ratio):continue
        if i>=deadline or ratio<=trigger:
            spent=cash
        else:
            # Scheduled deployment: 1/104th of initial reserve per week.
            spent=min(cash,reserve_initial/104)
        btc+=spent*(1-FEE)/float(s.iloc[i])
        cash-=spent
    return round(btc*float(s.iloc[-1])+cash,2)

def main():
    df=pd.read_csv("data/price_200_week_moving_average_200wma__2026-10-07T21-20-24.csv")
    df["date"]=pd.to_datetime(df["timestamp"],unit="ms",utc=True)
    s=pd.Series(pd.to_numeric(df["Price"],errors="coerce").to_numpy(),index=df["date"]).sort_index().resample("W-MON").last().dropna()
    ma=s.shift(1).rolling(200,min_periods=200).mean()
    configs=[(core,trigger) for core in (.5,.75,.9) for trigger in (1.,1.1,1.25)]
    cohorts=[]
    for year in range(2017,2025):
        d=s.index[(s.index.year==year)&(s.index.month==1)]
        if len(d)==0:continue
        start=s.index.get_loc(d[0])
        if start<201:continue
        hold=CAPITAL*(1-FEE)/float(s.iloc[start+1])*float(s.iloc[-1])
        scores={}
        for core,trigger in configs:
            name=f"core_{int(core*100)}_trigger_{trigger:.2f}"
            v=test(s,ma,start,core,trigger)
            scores[name]={"ending_usd":v,"vs_hold_pct":round((v/hold-1)*100,2)}
        cohorts.append({"year":year,"hold_usd":round(hold,2),"strategies":scores})
    summaries={}
    for core,trigger in configs:
        name=f"core_{int(core*100)}_trigger_{trigger:.2f}"
        values=[c["strategies"][name]["vs_hold_pct"] for c in cohorts]
        summaries[name]={"beat_hold_years":sum(x>0 for x in values),
                         "median_vs_hold_pct":round(float(np.median(values)),2),
                         "worst_vs_hold_pct":round(min(values),2)}
    out={"currency":"USD","capital":CAPITAL,"start_years":[c["year"] for c in cohorts],
         "end":str(s.index[-1].date()),"fee":FEE,
         "limitations":"Overlapping cohorts; historical sample only; fixed thresholds; no sales; no CGT or extra slippage",
         "summary":summaries,"cohorts":cohorts}
    p=Path("research_outputs/200wma_core_satellite.json")
    p.parent.mkdir(parents=True,exist_ok=True)
    p.write_text(json.dumps(out,indent=2))
    print(json.dumps(out,indent=2))
if __name__=="__main__":main()
