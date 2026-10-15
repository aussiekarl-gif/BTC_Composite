from engines.research.btc_200wma_history import load_completed_200wma_price_history
"""Research: integrated 20% BTC/80% cash deployment plus 200WMA trades.

Compare the same initial cash-heavy entry against a pure DCA benchmark.
The trading engine starts 20% in BTC, systematically deploys the other 80%,
and makes separate tier sells/rebuys from the resulting portfolio.
"""
import json
from pathlib import Path
import numpy as np
import pandas as pd
from engines.research.test_200wma_12week_execution import staged
from engines.research.test_200wma_cash_deployment import run as pure_dca

def summarize(rows):
 a=np.array([r["vs_pure_dca_pct"] for r in rows])
 b=np.array([r["vs_immediate_pct"] for r in rows])
 return {"cohorts":len(rows),"wins_vs_pure_dca":int(sum(a>0)),
 "median_vs_pure_dca_pct":round(float(np.median(a)),3),"worst_vs_pure_dca_pct":round(float(min(a)),3),
 "median_vs_immediate_pct":round(float(np.median(b)),3),
 "median_remaining_cash_usd":round(float(np.median([r["cash_usd"] for r in rows])),2),
 "median_transaction_fills":round(float(np.median([r["transactions"] for r in rows])),1)}

def main():
 s,ma=load_completed_200wma_price_history()
 starts=[i for i in range(201,len(s)-1) if pd.Timestamp("2018-01-01",tz="UTC")<=s.index[i]<=pd.Timestamp("2024-12-31",tz="UTC")][::4]
 # Ledger consistency: with all tier trades disabled, the staged engine must
 # exactly reconcile against an independent pure-DCA implementation.
 for i in starts[::13]:
  for horizon in (104,208):
   if i+horizon>=len(s):continue
   for weeks in (12,26):
    for weighted in (False,True):
     no_trades=staged(s,ma,i,shape="bell",buy_weeks=12,sell_weeks=16,
        buy_levels=[],sell_levels=[],block_overlap=True,slippage=0.005,
        fee=0.001,end_index=i+horizon,initial_btc_fraction=0.2,
        funding_weeks=weeks,funding_weighted=weighted)
     pure=pure_dca(s,ma,i,i+horizon,weeks,weighted)
     if no_trades["transactions"]!=0 or abs(no_trades["value_usd"]-pure["value_usd"])>0.05:
      raise AssertionError("Integrated cash deployment does not reconcile to pure DCA")
 output={}
 for horizon in (104,208):
  valid=[i for i in starts if i+horizon<len(s)]
  tests={}
  for funding_weeks in (12,26):
   for weighted in (False,True):
    rows=[]
    for i in valid:
     end=i+horizon
     funded=staged(s,ma,i,shape="bell",reverse_cancel=False,
          buy_weeks=12,sell_weeks=16,block_overlap=True,slippage=0.005,
          fee=0.001,end_index=end,initial_btc_fraction=0.2,
          funding_weeks=funding_weeks,funding_weighted=weighted)
     pure=pure_dca(s,ma,i,end,funding_weeks,weighted)
     rows.append({"start":str(s.index[i].date()),"year":int(s.index[i].year),
                  "vs_pure_dca_pct":round(100*(funded["value_usd"]/pure["value_usd"]-1),3),
                  "vs_immediate_pct":funded["vs_hold_pct"],
                  "cash_usd":funded["cash_usd"],"btc_equivalent":funded["btc_equivalent"],
                  "transactions":funded["transactions"],"pending_jobs":funded["pending_jobs"]})
    name=f"{funding_weeks}week_{'risk' if weighted else 'equal'}_entry_plus_12buy_16sell"
    tests[name]={"aggregate":summarize(rows),
       "by_year":{str(y):summarize([r for r in rows if r["year"]==y]) for y in sorted(set(r["year"] for r in rows))},
       "rows":rows}
  output[f"{horizon}week_horizon"]={"tests":tests}
 p=Path("research_outputs/200wma_integrated_cash_and_trading.json");p.parent.mkdir(parents=True,exist_ok=True)
 p.write_text(json.dumps({"initial_btc_fraction":0.2,"fee":0.001,"slippage":0.005,
      "results":output,"limitations":"Research only. 92 historically chosen correlated starts; 2/4-year fixed horizon cohorts overlap, no AUD/FX or SMSF taxes, threshold parameters seen in sample, no independent OOS."},indent=2))
 print(json.dumps({h:{n:r["aggregate"] for n,r in e["tests"].items()} for h,e in output.items()},indent=2))
if __name__=="__main__":main()
