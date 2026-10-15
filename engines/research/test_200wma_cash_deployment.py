"""Cash-first BTC accumulation diagnostic: 20% BTC / 80% uninvested at entry.

Benchmarks immediate 100%-BTC and fixed 12/26/52 week DCA; all cohorts close
after the same fixed 104/208 week horizon, with causal prior-week risk signal.
These schedules do NOT execute sell tiers; isolate cash-deployment decisions.
"""
import json
from pathlib import Path
import numpy as np
import pandas as pd

CAP=500000.0
FEE=0.001
SLIPPAGE=0.005
INITIAL_BTC_FRACTION=0.20

def weight(dev):
 if dev<=0:return 4.
 if dev<=25:return 2.
 if dev<=100:return 1.
 if dev<=200:return 0.5
 return 0.25

def run(s,ma,start,end,weeks,weighted,only_below=False,signal_price=None):
 if signal_price is None:signal_price=s
 if not s.index.equals(signal_price.index):raise ValueError("Signal and execution dates differ")
 px=float(s.iloc[start+1])
 btc=CAP*INITIAL_BTC_FRACTION*(1-FEE)*(1-SLIPPAGE)/px
 cash=CAP*(1-INITIAL_BTC_FRACTION)
 for k in range(weeks):
  i=start+2+k
  j=i-1
  remaining=weeks-k
  dev=100*(signal_price.iloc[j]/ma.iloc[j]-1)
  if only_below and (not np.isfinite(dev) or dev>0):continue
  w=weight(dev) if weighted and np.isfinite(dev) else 1.
  spend=cash if remaining==1 else min(cash,cash/remaining*w)
  btc+=spend*(1-FEE)*(1-SLIPPAGE)/float(s.iloc[i])
  cash-=spend
 terminal=float(s.iloc[end])
 value=cash+btc*terminal
 immediate=CAP*(1-FEE)*(1-SLIPPAGE)/float(s.iloc[start+1])*terminal
 return {"vs_immediate_pct":round((value/immediate-1)*100,3),
         "btc":round(btc,8),"value_usd":round(value,2),"cash_usd":round(cash,2)}
def summarise(rows):
 arr=np.array([x["vs_immediate_pct"] for x in rows])
 return {"starts":len(rows),"wins_vs_immediate":int((arr>0).sum()),
         "median_vs_immediate_pct":round(float(np.median(arr)),3),
         "worst_pct":round(float(np.min(arr)),3),
         "median_uninvested_cash_usd":round(float(np.median([x["cash_usd"] for x in rows])),2),
         "cohorts_with_cash_left":sum(x["cash_usd"]>1 for x in rows),
         "by_start_year":{str(y):{"n":sum(x["start_year"]==y for x in rows),
            "median_pct":round(float(np.median([x["vs_immediate_pct"] for x in rows if x["start_year"]==y])),3)}
            for y in sorted(set(x["start_year"] for x in rows))}}
def main():
 d=pd.read_csv("data/price_200_week_moving_average_200wma__2026-10-07T21-20-24.csv")
 d["date"]=pd.to_datetime(d["timestamp"],unit="ms",utc=True)
 s=pd.Series(pd.to_numeric(d["Price"],errors="coerce").to_numpy(),index=d["date"]).sort_index().resample("W-MON").last().dropna()
 ma=s.shift(1).rolling(200,min_periods=200).mean()
 starts=[i for i in range(201,len(s)-1) if pd.Timestamp("2018-01-01",tz="UTC")<=s.index[i]<=pd.Timestamp("2024-12-31",tz="UTC")][::4]
 out={}
 for horizon in (104,208):
  eligible=[i for i in starts if i+horizon<len(s)]
  tests={}
  for weeks in (12,26,52):
   for weighted in (False,True):
    name=f"{'risk_weighted' if weighted else 'equal'}_{weeks}week"
    rows=[]
    for i in eligible:
     r=run(s,ma,i,i+horizon,weeks,weighted)
     rows.append({"start":str(s.index[i].date()),"start_year":int(s.index[i].year),**r})
    tests[name]={"summary":summarise(rows),"rows":rows}
  for weeks in (12,26,52):
   rows=[]
   for i in eligible:
    r=run(s,ma,i,i+horizon,weeks,weighted=True,only_below=True)
    rows.append({"start":str(s.index[i].date()),"start_year":int(s.index[i].year),**r})
   tests[f"buy_only_below_200wma_{weeks}week"]={"summary":summarise(rows),"rows":rows}
  out[f"{horizon}week_horizon"]={"tests":tests}
 p=Path("research_outputs/200wma_cash_deployment.json")
 p.parent.mkdir(parents=True,exist_ok=True)
 p.write_text(json.dumps({"initial_fraction_btc":INITIAL_BTC_FRACTION,"fee":FEE,
     "slippage":SLIPPAGE,"results":out,"limitations":"No selling; all rolling starts overlap; heuristic weight brackets not optimised. Strict below-200WMA rule never forces remaining cash to invest when deviation >0, so uninvested cash can be large. USD price only, no FX/tax."},indent=2))
 print(json.dumps({h:{n:res["summary"] for n,res in entry["tests"].items()} for h,entry in out.items()},indent=2))
if __name__=="__main__":main()
