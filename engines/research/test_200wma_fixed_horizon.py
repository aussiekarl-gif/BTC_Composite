"""Fixed-horizon, realisable BTC DCA strategy tests.

All signals use the previous completed weekly close. Each cohort exits at a
fixed 104-, 156- or 208-week horizon rather than sharing October 2026 as exit.
Rolling cohorts are correlated; results are diagnostic rather than OOS proof.
"""
import json
from pathlib import Path
import numpy as np
import pandas as pd
from engines.research.test_200wma_12week_execution import staged
from engines.research.test_200wma_exact_10x10 import simulate

def summarize(rows):
 vals=np.array([r["advantage_pct"] for r in rows])
 return {"cohorts":len(rows),"wins":int((vals>0).sum()),"median_pct":round(float(np.median(vals)),3),
         "worst_pct":round(float(vals.min()),3),"p25_pct":round(float(np.percentile(vals,25)),3),
         "median_btc_equivalent":round(float(np.median([r["btc_equivalent"] for r in rows])),6),
         "median_cash_usd":round(float(np.median([r["cash_usd"] for r in rows])),2)}
def main():
 d=pd.read_csv("data/price_200_week_moving_average_200wma__2026-10-07T21-20-24.csv")
 d["date"]=pd.to_datetime(d["timestamp"],unit="ms",utc=True)
 s=pd.Series(pd.to_numeric(d["Price"],errors="coerce").to_numpy(),index=d["date"]).sort_index().resample("W-MON").last().dropna()
 ma=s.shift(1).rolling(200,min_periods=200).mean()
 eligible=[i for i in range(201,len(s)-1) if pd.Timestamp("2018-01-01",tz="UTC")<=s.index[i]<=pd.Timestamp("2024-12-31",tz="UTC")][::4]
 out={}
 for horizon in (104,156,208):
  valid=[i for i in eligible if i+horizon<len(s)]
  strategies={
   "immediate":lambda i,e:simulate(s,ma,i,end=e),
   "12buy_16sell_bell_no_overlap_0_slippage":lambda i,e:staged(s,ma,i,shape="bell",buy_weeks=12,sell_weeks=16,block_overlap=True,end_index=e),
   "12buy_16sell_bell_no_overlap_0.5pct_slippage":lambda i,e:staged(s,ma,i,shape="bell",buy_weeks=12,sell_weeks=16,block_overlap=True,slippage=0.005,end_index=e),
   "12buy_16sell_bell_overlap_0_slippage":lambda i,e:staged(s,ma,i,shape="bell",buy_weeks=12,sell_weeks=16,end_index=e)}
  results={}
  for name,fn in strategies.items():
   rows=[]
   for i in valid:
    r=fn(i,i+horizon)
    rows.append({"start":str(s.index[i].date()),"end":str(s.index[i+horizon].date()),
                 "advantage_pct":r["vs_hold_pct"],"btc_equivalent":r["btc_equivalent"],
                 "cash_usd":r["cash_usd"]})
   results[name]={"aggregate":summarize(rows),
      "by_start_year":{str(y):summarize([r for r in rows if r["start"].startswith(str(y))])
            for y in sorted(set(int(r["start"][:4]) for r in rows))},"rows":rows}
  out[str(horizon)+"_weeks"]={"first_start":str(s.index[valid[0]].date()),"last_start":str(s.index[valid[-1]].date()),"results":results}
 p=Path("research_outputs/200wma_fixed_horizon_robustness.json");p.parent.mkdir(parents=True,exist_ok=True)
 p.write_text(json.dumps(out,indent=2))
 print(json.dumps({h:{k:{"aggregate":v["aggregate"],"by_start_year":v["by_start_year"]} for k,v in z["results"].items()} for h,z in out.items()},indent=2))
if __name__=="__main__":main()
