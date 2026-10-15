"""Sensitivity: lower 200WMA sell thresholds, friction, and 2022+ holdout.
Do not use holdout results to pick parameters; diagnostic only.
"""
import json
from pathlib import Path
import numpy as np
import pandas as pd
from engines.research.test_200wma_12week_execution import staged
from engines.research.test_200wma_exact_10x10 import BUYS,SELLS

def main():
    d=pd.read_csv("data/price_200_week_moving_average_200wma__2026-10-07T21-20-24.csv")
    d["date"]=pd.to_datetime(d["timestamp"],unit="ms",utc=True)
    s=pd.Series(pd.to_numeric(d["Price"],errors="coerce").to_numpy(),index=d["date"]).sort_index().resample("W-MON").last().dropna()
    ma=s.shift(1).rolling(200,min_periods=200).mean()
    starts=[i for i in range(201,len(s)-1) if pd.Timestamp("2018-01-01",tz="UTC")<=s.index[i]<=pd.Timestamp("2024-12-31",tz="UTC")][::4]
    ladders={"existing_100_280":SELLS,
             "lower_50_200":[50,65,80,95,110,125,145,165,185,200],
             "lower_25_160":[25,40,55,70,85,100,115,130,145,160]}
    results={}
    for name,levels in ladders.items():
        for fee in (0.001,0.003,0.006):
            rows=[]
            for i in starts:
                r=staged(s,ma,i,shape="bell",reverse_cancel=False,buy_weeks=12,sell_weeks=16,
                         sell_levels=levels,buy_levels=BUYS,fee=fee)
                rows.append({"start":str(s.index[i].date()),"year":int(s.index[i].year),
                             "vs_hold_pct":r["vs_hold_pct"],"cash_usd":r["cash_usd"],
                             "btc_equivalent":r["btc_equivalent"]})
            vals=[x["vs_hold_pct"] for x in rows]
            holdout=[x["vs_hold_pct"] for x in rows if x["year"]>=2022]
            calibration=[x["vs_hold_pct"] for x in rows if x["year"]<=2021]
            results[f"{name}_fee_{fee}"]={"sell_levels":levels,"fee":fee,
                "cohorts":len(rows),"wins":sum(v>0 for v in vals),
                "median_pct":round(float(np.median(vals)),3),
                "worst_pct":round(float(min(vals)),3),
                "calibration_median_pct":round(float(np.median(calibration)),3),
                "holdout_median_pct":round(float(np.median(holdout)),3),
                "holdout_wins":sum(v>0 for v in holdout),"holdout_count":len(holdout),
                "rows":rows}
    out={"results":results,"limitations":"Research diagnostic, not out-of-sample validation: thresholds conceived with knowledge of 2022–2026; all cohorts end Oct 2026 and overlap. Fee-only sensitivity, no independent slippage."}
    p=Path("research_outputs/200wma_lower_tier_fee_sensitivity.json")
    p.parent.mkdir(parents=True,exist_ok=True)
    p.write_text(json.dumps(out,indent=2,default=lambda x:x.item() if hasattr(x,"item") else str(x)))
    print(json.dumps({k:{x:v for x,v in z.items() if x!="rows"} for k,z in results.items()},indent=2))
if __name__=="__main__":main()
