"""Audit staged BTC 200WMA execution under repeated tier crossings and slippage."""
import json
from pathlib import Path
import numpy as np
import pandas as pd
from engines.research.test_200wma_12week_execution import staged
def main():
 d=pd.read_csv("data/price_200_week_moving_average_200wma__2026-10-07T21-20-24.csv")
 d["date"]=pd.to_datetime(d["timestamp"],unit="ms",utc=True)
 s=pd.Series(pd.to_numeric(d["Price"],errors="coerce").to_numpy(),index=d["date"]).sort_index().resample("W-MON").last().dropna()
 ma=s.shift(1).rolling(200,min_periods=200).mean()
 starts=[i for i in range(201,len(s)-1) if pd.Timestamp("2018-01-01",tz="UTC")<=s.index[i]<=pd.Timestamp("2024-12-31",tz="UTC")][::4]
 results={}
 for block in (False,True):
  for slip in (0,0.0025,0.005,0.01):
   vals=[];pending=[];cash=[];turnover=[]
   for i in starts:
    r=staged(s,ma,i,shape="bell",reverse_cancel=False,buy_weeks=12,sell_weeks=16,block_overlap=block,slippage=slip)
    vals.append(r["vs_hold_pct"]);pending.append(r["pending_jobs"]);cash.append(r["cash_usd"]);turnover.append(r["transactions"])
   key=f"block_overlap_{block}_slippage_{slip}"
   results[key]={"cohorts":len(vals),"wins":sum(v>0 for v in vals),"median_pct":round(float(np.median(vals)),3),"worst_pct":round(float(min(vals)),3),"median_transactions":float(np.median(turnover)),"median_final_cash_usd":round(float(np.median(cash)),2),"max_pending_jobs":max(pending)}
 p=Path("research_outputs/200wma_overlap_slippage.json");p.parent.mkdir(exist_ok=True,parents=True)
 p.write_text(json.dumps(results,indent=2))
 print(json.dumps(results,indent=2))
if __name__=="__main__":main()
