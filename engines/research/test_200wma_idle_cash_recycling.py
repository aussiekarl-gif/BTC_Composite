"""Research: can stale-cash recycling reduce BTC 200WMA sell-too-early losses?

Only structural candidate variants are allowed: no recycling, buy 25% of
free cash after 26 idle weeks, or after 52 idle weeks. Trigger requires
>50% of marked portfolio in unreserved cash and no live buy-tier job;
decided on prior completed weekly close and filled at next weekly close.
No future price information, but parameters are proposed using already
inspected history and NOT independently validated.
"""
import json
from pathlib import Path
import numpy as np
import pandas as pd
from engines.research.test_200wma_smsf_costs import history
from engines.research.test_200wma_12week_execution import staged
from engines.research.test_200wma_cash_deployment import run as pure_dca
from engines.research.smsf_cgt_ledger import FifoCgtLedger,AnnualSmsfTaxPayment

def stats(rows,k):
 arr=np.array([x[k] for x in rows])
 return {"n":len(rows),"wins":int(sum(arr>0)),"median":round(float(np.median(arr)),3),
         "p10":round(float(np.percentile(arr,10)),3),
         "worst":round(float(min(arr)),3)}

def main():
 price,signal,ma=history("AUD")
 nav=price*np.power(1-.0045,np.arange(len(price))/52)
 starts=[i for i in range(len(price)-1)
    if pd.Timestamp("2018-01-01",tz="UTC")<=price.index[i]<=pd.Timestamp("2024-12-31",tz="UTC")][::4]
 out={}
 for horizon in (104,208):
  valid=[i for i in starts if i+horizon<len(price)]
  benchmark={i:pure_dca(nav,ma,i,i+horizon,12,True,
                signal_price=signal,brokerage_fixed=20.)["value_usd"] for i in valid}
  modes={}
  for idle in (0,26,52):
   rows=[]
   for i in valid:
    ledger=FifoCgtLedger()
    taxhook=AnnualSmsfTaxPayment(ledger,brokerage=20.,fee=.001,slippage=.005)
    r=staged(nav,ma,i,shape="bell",buy_weeks=12,sell_weeks=16,
      block_overlap=True,slippage=.005,fee=.001,end_index=i+horizon,
      initial_btc_fraction=.2,funding_weeks=12,funding_weighted=True,
      btc_core_fraction=0.,signal_price=signal,brokerage_fixed=20.,
      cash_recycle_idle_weeks=idle,cash_recycle_fraction=.25,
      cash_recycle_min_share=.5,trade_callback=ledger,weekly_hook=taxhook)
    tx=ledger.tax_summary()
    if abs(tx["net_units"]-r["btc_held"])>1e-5:
     raise AssertionError("Tax lot inventory != portfolio ETF units")
    val=r["value_usd"]-tx["tax_outstanding"]
    rows.append({"start":str(price.index[i].date()),"year":int(price.index[i].year),
      "net_advantage_pct":round(100*(val/benchmark[i]-1),4),
      "net_final_value":round(val,2),
      "gross_advantage_pct":round(100*(r["value_usd"]/benchmark[i]-1),4),
      "remaining_cash":r["cash_usd"],
      "sell_fills":tx["sell_fills"],
      "all_transactions":r["transactions"],
      "tax_paid":tx["tax_cash_paid"]})
   modes[f"recycle_idle_{idle}weeks"]={
     "net_aud":stats(rows,"net_advantage_pct"),
     "gross":stats(rows,"gross_advantage_pct"),
     "median_cash":round(float(np.median([r["remaining_cash"] for r in rows])),2),
     "median_fills":float(np.median([r["all_transactions"] for r in rows])),
     "by_year":{str(y):stats([r for r in rows if r["year"]==y],"net_advantage_pct")
       for y in sorted(set(r["year"] for r in rows))},
     "rows":rows}
  out[f"{horizon}week"]=modes
 p=Path("research_outputs/200wma_idle_cash_recycling_aud.json")
 p.parent.mkdir(parents=True,exist_ok=True)
 p.write_text(json.dumps({"assumptions":"AUD reference ETF proxy, A$20 per fill, 0.45% ETF annual fee, 0.1% dealing and 0.5% slippage, compliant SMSF 15% accumulation CGT charged July, 20/80 initial cash-entry with 12-week funding. Proposed idleness trigger uses completed prior close. Cohorts overlap and parameters were devised after seeing historical data.","results":out},indent=2))
 print(json.dumps({h:{mode:{k:v for k,v in r.items() if k!="rows" and k!="by_year"}|{"by_year":r["by_year"]} for mode,r in tests.items()} for h,tests in out.items()},indent=2))

if __name__=="__main__":main()
