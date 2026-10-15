"""Research-only USD indicator / AUD execution paired-cohort BTC comparison.

Completed USD weekly 200WMA deviation signals, executed using separately
sourced weekly BTC/AUD prices from the causal research data pipeline.
The same calendar starts/ends are used for USD and AUD to isolate FX impact.
Both comparisons begin with 20% BTC + 80% cash, with no tax assumptions.
"""
import json
from pathlib import Path
import numpy as np
import pandas as pd

from engines.research.test_200wma_12week_execution import staged
from engines.research.test_200wma_cash_deployment import run as pure_dca

def summary(rows,key):
 a=np.array([float(r[key]) for r in rows])
 return {"n":len(rows),"wins":int(sum(a>0)),
   "median_pct":round(float(np.median(a)),3),
   "worst_pct":round(float(np.min(a)),3),
   "p10_pct":round(float(np.percentile(a,10)),3)}
def main():
 provider_csv="data/price_200_week_moving_average_200wma__2026-10-07T21-20-24.csv"
 aud_csv="research_outputs/causal_btc_aud_weekly.csv"
 raw=pd.read_csv(provider_csv)
 raw["date"]=pd.to_datetime(raw["timestamp"],unit="ms",utc=True)
 original=pd.Series(pd.to_numeric(raw["Price"],errors="coerce").to_numpy(),
      index=raw["date"]).sort_index().dropna()
 usd=original.resample("W-MON").last().dropna()
 # Discard any last partial W-MON week, whose label lies in the future
 # relative to the latest real daily source observation.
 last_completed=original.index.max().normalize()
 usd=usd.loc[usd.index<=last_completed]
 usd_ma=usd.shift(1).rolling(200,min_periods=200).mean()
 aud_source=pd.read_csv(aud_csv)
 aud_source["date"]=pd.to_datetime(aud_source["date"],utc=True)
 aud=pd.Series(pd.to_numeric(aud_source["btc_price_aud"],errors="coerce").to_numpy(),
      index=aud_source["date"]).sort_index().dropna()
 if aud.index.has_duplicates or usd.index.has_duplicates:
  raise ValueError("Duplicate weekly source dates")
 frame=pd.concat({"usd":usd,"aud":aud,"usd_200wma":usd_ma},axis=1,join="inner").dropna()
 frame=frame.loc[frame.index <= last_completed]
 if frame.empty or not frame.index.is_monotonic_increasing:
  raise ValueError("Incomplete paired USD/AUD weekly data")
 if not (frame["usd"]>0).all() or not (frame["aud"]>0).all():
  raise ValueError("Invalid price history")
 fx_proxy=frame["aud"]/frame["usd"]
 if not (fx_proxy.between(0.7,3.0)).all():
  raise ValueError("USD/AUD FX-proxy outlier; check data providers")
 # Ensure 200WMA has been warmed with actual source history prior to each start.
 starts=[i for i in range(len(frame)-1) if frame.index[i]>=pd.Timestamp("2018-01-01",tz="UTC")
    and frame.index[i]<=pd.Timestamp("2024-12-31",tz="UTC")
    and np.isfinite(frame["usd_200wma"].iloc[i])][::4]
 if len(starts)<50:
  raise ValueError(f"Insufficient matched USD/AUD cohorts: {len(starts)}")
 s_usd=frame["usd"]
 s_aud=frame["aud"]
 ma=frame["usd_200wma"]
 results={}
 for horizon in (104,156,208):
  valid=[i for i in starts if i+horizon<len(frame)]
  configs={}
  for floor in (0.,0.25,0.5):
   rows=[]
   for i in valid:
    end=i+horizon
    p_usd=pure_dca(s_usd,ma,i,end,12,True,signal_price=s_usd)
    p_aud=pure_dca(s_aud,ma,i,end,12,True,signal_price=s_usd)
    kw={"shape":"bell","buy_weeks":12,"sell_weeks":16,
       "block_overlap":True,"slippage":0.005,"fee":0.001,
       "initial_btc_fraction":0.2,"funding_weeks":12,
       "funding_weighted":True,"btc_core_fraction":floor,
       "end_index":end}
    r_usd=staged(s_usd,ma,i,**kw)
    r_aud=staged(s_aud,ma,i,signal_price=s_usd,**kw)
    usd_adv=100*(r_usd["value_usd"]/p_usd["value_usd"]-1)
    aud_adv=100*(r_aud["value_usd"]/p_aud["value_usd"]-1)
    rows.append({"start":str(frame.index[i].date()),"end":str(frame.index[end].date()),
       "year":int(frame.index[i].year),"usd_adv_pct":round(usd_adv,4),
       "aud_adv_pct":round(aud_adv,4),"fx_effect_pp":round(aud_adv-usd_adv,4),
       "final_aud":r_aud["value_usd"],"final_btc":r_aud["btc_held"],
       "final_cash_aud":r_aud["cash_usd"]})
   configs[str(floor)]={"usd":summary(rows,"usd_adv_pct"),
      "aud":summary(rows,"aud_adv_pct"),"fx_effect_pp":summary(rows,"fx_effect_pp"),
      "by_year":{str(y):{"usd":summary([x for x in rows if x["year"]==y],"usd_adv_pct"),
         "aud":summary([x for x in rows if x["year"]==y],"aud_adv_pct")}
         for y in sorted(set(x["year"] for x in rows))},
      "rows":rows}
  results[f"{horizon}_week"]=configs
 out={"data_sources":{"usd":"BlockHorizon price export as archived in repository",
      "aud":"Blockchain.com BTC/USD times historical USD/AUD Frankfurter FX, from causal BTC/AUD research output"},
    "matching_weeks":len(frame),"first_week":str(frame.index[0].date()),
    "last_completed_week":str(frame.index[-1].date()),
    "source_last_observation":str(last_completed.date()),
    "fee":0.001,"slippage":0.005,
    "fx_proxy_min":round(float(fx_proxy.min()),5),
    "fx_proxy_median":round(float(fx_proxy.median()),5),
    "fx_proxy_max":round(float(fx_proxy.max()),5),
    "results":results,
    "limitations":"Different BTC/USD providers underlie the signal series and AUD price conversion. USD/AUD FX is historical daily reference data, not broker executable quotes or spread. All starts overlap; no tax; in-sample tier decisions."}
 p=Path("research_outputs/200wma_aud_currency_impact.json")
 p.parent.mkdir(parents=True,exist_ok=True)
 p.write_text(json.dumps(out,indent=2))
 print(json.dumps({"matched_weeks":len(frame),"last_completed_week":out["last_completed_week"],
   "fx_proxy_median":out["fx_proxy_median"],
   "results":{h:{floor:{"usd":v["usd"],"aud":v["aud"],"fx_effect_pp":v["fx_effect_pp"]}
     for floor,v in z.items()} for h,z in results.items()}},indent=2))
if __name__=="__main__":main()
