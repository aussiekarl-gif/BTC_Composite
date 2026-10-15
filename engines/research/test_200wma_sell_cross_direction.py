from engines.research.btc_200wma_history import load_completed_200wma_price_history
"""Research-only: compare 200WMA sell activation on upward vs downward crossings.

Same 20% initial BTC, 80% cash, 12-week completed-signal weighted DCA,
12-week bell buys and 16-week bell sells. No forward-looking top detection.
Down-crossing means prev deviation > tier and prior completed week's deviation
<= tier, with next weekly-close execution.
"""
import json
from pathlib import Path
import numpy as np
import pandas as pd
from engines.research.test_200wma_12week_execution import staged
from engines.research.test_200wma_cash_deployment import run as pure_dca

def summary(rows):
 a=np.array([r["vs_dca_pct"] for r in rows])
 return {"starts":len(rows),"wins":int(sum(a>0)),
   "median_pct":round(float(np.median(a)),3),
   "worst_pct":round(float(min(a)),3),
   "p10_pct":round(float(np.percentile(a,10)),3),
   "p25_pct":round(float(np.percentile(a,25)),3),
   "median_trades":float(np.median([r["transactions"] for r in rows])),
   "worst_start":min(rows,key=lambda r:r["vs_dca_pct"])["start"]}
def main():
 s,ma=load_completed_200wma_price_history()
 starts=[i for i in range(201,len(s)-1) if pd.Timestamp("2018-01-01",tz="UTC")<=s.index[i]<=pd.Timestamp("2024-12-31",tz="UTC")][::4]
 result={}
 for horizon in (104,156,208):
  valid=[i for i in starts if i+horizon<len(s)]
  baseline={i:pure_dca(s,ma,i,i+horizon,12,True)["value_usd"] for i in valid}
  tests={}
  for direction in ("up","down"):
   for floor in (0.,0.25,0.5):
    rows=[]
    for i in valid:
     r=staged(s,ma,i,shape="bell",reverse_cancel=False,buy_weeks=12,sell_weeks=16,
         block_overlap=True,slippage=0.005,fee=0.001,end_index=i+horizon,
         initial_btc_fraction=0.2,funding_weeks=12,funding_weighted=True,
         btc_core_fraction=floor,sell_cross_direction=direction)
     rows.append({"start":str(s.index[i].date()),"year":int(s.index[i].year),
                  "vs_dca_pct":round(100*(r["value_usd"]/baseline[i]-1),4),
                  "transactions":r["transactions"],"btc_held":r["btc_held"],
                  "cash_usd":r["cash_usd"]})
    tests[f"{direction}_cross_floor_{floor}"]={"aggregate":summary(rows),
           "by_start_year":{str(y):summary([r for r in rows if r["year"]==y])
             for y in sorted(set(r["year"] for r in rows))},"rows":rows}
  result[f"{horizon}_week"]=tests
 p=Path("research_outputs/200wma_sell_cross_direction.json")
 p.parent.mkdir(parents=True,exist_ok=True)
 p.write_text(json.dumps({"description":"Upward vs downward causal 200WMA deviation threshold sell triggers",
    "note":"Parameters developed using studied sample; diagnostic not forward validation. Upward crossing is prior strategy.",
    "fee":0.001,"slippage":0.005,"results":result},indent=2))
 print(json.dumps({h:{key:v["aggregate"] for key,v in tests.items()} for h,tests in result.items()},indent=2))
if __name__=="__main__":main()
