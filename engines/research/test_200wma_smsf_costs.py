"""ETF-like trading costs & SMSF tax sensitivity, paired cash-first DCA.

USD and AUD share historical completed-week USD price/200WMA signals.
ETF market prices are approximated by reference Bitcoin price with
hypothetical annual management fee drag; they are not real ETF quotes.
Tax is estimated from FIFO disposals but netted only at horizon, so
annual liability funding and return drag are NOT captured.
"""
import argparse,json
from pathlib import Path
import numpy as np
import pandas as pd
from engines.research.btc_200wma_history import load_completed_200wma_price_history
from engines.research.test_200wma_12week_execution import staged
from engines.research.test_200wma_cash_deployment import run as pure_dca
from engines.research.smsf_cgt_ledger import FifoCgtLedger,AnnualSmsfTaxPayment

SCENARIOS={
 "control_0broker_0mer":(0.,0.),
 "low_10broker_025mer":(10.,0.0025),
 "mid_20broker_045mer":(20.,0.0045),
 "high_35broker_075mer":(35.,0.0075)
}

def history(currency):
 usd,ma=load_completed_200wma_price_history()
 if currency=="USD":return usd,usd,ma
 raw=pd.read_csv("research_outputs/causal_btc_aud_weekly.csv")
 raw["date"]=pd.to_datetime(raw["date"],utc=True)
 aud=pd.Series(pd.to_numeric(raw["btc_price_aud"],errors="coerce").to_numpy(),
      index=raw["date"]).sort_index().dropna()
 if aud.index.has_duplicates:raise ValueError("Duplicate AUD weekly periods")
 f=pd.concat({"usd":usd,"aud":aud,"ma":ma},axis=1,join="inner").dropna()
 if len(f)<400 or not (f["aud"]/f["usd"]).between(0.7,3).all():
  raise ValueError("Insufficient or invalid matched AUD/USD series")
 return f["aud"],f["usd"],f["ma"]

def summary(rows,key):
 a=np.array([float(row[key]) for row in rows])
 return {"starts":len(rows),"wins":int((a>0).sum()),
         "median_pct":round(float(np.median(a)),3),
         "worst_pct":round(float(np.min(a)),3),
         "p10_pct":round(float(np.percentile(a,10)),3)}

def main():
 ap=argparse.ArgumentParser()
 ap.add_argument("--currency",choices=("USD","AUD"),default="USD")
 args=ap.parse_args()
 prices,signal,ma=history(args.currency)
 starts=[i for i in range(len(prices)-1) if
   pd.Timestamp("2018-01-01",tz="UTC")<=prices.index[i]<=pd.Timestamp("2024-12-31",tz="UTC")][::4]
 all_results={}
 for horizon in (104,208):
  eligible=[i for i in starts if i+horizon<len(prices)]
  configs={}
  for name,(broker,mer) in SCENARIOS.items():
   rows=[]
   for i in eligible:
    # Identical management-fee drag applies to trading and DCA baseline.
    nav=prices*np.power(1-mer,np.arange(len(prices))/52)
    ledger=FifoCgtLedger()
    kwargs=dict(shape="bell",buy_weeks=12,sell_weeks=16,
        block_overlap=True,slippage=0.005,fee=0.001,
        initial_btc_fraction=0.2,funding_weeks=12,funding_weighted=True,
        end_index=i+horizon,signal_price=signal,
        brokerage_fixed=broker)
    strategy=staged(nav,ma,i,trade_callback=ledger,**kwargs)
    baseline=pure_dca(nav,ma,i,i+horizon,12,True,
                      signal_price=signal,brokerage_fixed=broker)
    liability=ledger.tax_summary()
    tax_paid_ledger=FifoCgtLedger()
    annual_settlement=AnnualSmsfTaxPayment(tax_paid_ledger,broker,FEE,SLIPPAGE)
    annual_strategy=staged(nav,ma,i,trade_callback=tax_paid_ledger,
        weekly_hook=annual_settlement,**kwargs)
    annual_liability=tax_paid_ledger.tax_summary()
    if abs(annual_liability["net_units"]-annual_strategy["btc_held"])>1e-5:
     raise AssertionError("Yearly CGT-settled units differ from holdings")
    annual_net=annual_strategy["value_usd"]-annual_liability["tax_outstanding"]
    if abs(liability["net_units"]-strategy["btc_held"])>1e-5:
     raise AssertionError("FIFO units differ from simulated holdings")
    if strategy["cash_usd"]<0:raise AssertionError("Negative cash")
    tax=liability["estimated_total_tax"]
    rows.append({"start":str(prices.index[i].date()),
        "gross_pct":round(100*(strategy["value_usd"]/baseline["value_usd"]-1),4),
        "after_accumulation_tax_pct":round(100*((strategy["value_usd"]-tax)/baseline["value_usd"]-1),4),
        "after_yearly_tax_payment_pct":round(100*(annual_net/baseline["value_usd"]-1),4),
        "annual_tax_paid":annual_liability["tax_cash_paid"],
        "annual_unpaid_tax":annual_liability["tax_outstanding"],
        "tax_funding_sales":annual_settlement.financing_sales,
        "annual_net_value":round(annual_net,2),
        "remaining_cash":strategy["cash_usd"],
        "tax_liability":tax,"sell_fills":liability["sell_fills"],
        "fund_value_before_tax":strategy["value_usd"],
        "net_value_less_liability":round(strategy["value_usd"]-tax,2),
        "fy_details":liability["by_year"]})
   configs[name]={"brokerage_per_fill":broker,"annual_fee":mer,
      "pension_exempt_0pct_tax":summary(rows,"gross_pct"),
      "accumulation_15pct_tax_estimate":summary(rows,"after_accumulation_tax_pct"),
      "accumulation_with_yearly_tax_settlement":summary(rows,"after_yearly_tax_payment_pct"),
      "cohorts_requiring_tax_financing_sales":sum(r["tax_funding_sales"]>0 for r in rows),
      "median_forced_tax_sales":float(np.median([r["tax_funding_sales"] for r in rows])),
      "median_total_tax_liability":round(float(np.median([r["tax_liability"] for r in rows])),2),
      "median_sell_fills":float(np.median([r["sell_fills"] for r in rows])),
      "rows":rows}
  all_results[str(horizon)+"week"]=configs
 out={"currency":args.currency,"fee":0.001,"slippage":0.005,
  "initial_btc_fraction":0.2,"initial_funding_weeks":12,
  "sell_weeks":16,"buy_weeks":12,
  "baseline":"Matching 20% BTC/80% cash initial portfolio and 12-week risk-weighted DCA, then no sales",
  "scenarios":all_results,
  "limitations":"Hypothetical ETF management-fee NAV drag and per-fill brokerage; no actual ETF share price or tracking premium. FIFO gain matching and CGT loss carryforward by July-June year; losses applied to short gains before discounted gains. Complying SMSF 15% accumulation and fully tax-exempt qualifying retirement assets only. Two accumulation variants are shown: terminal tax-liability deduction and conservative early yearly settlements at first July weekly close, with forced ETF disposals if cash is short. ATO actual payment dates differ; neither reflects all possible CGT parcel identification, earnings and actuarial effects. No ETF distributions, administrative SMSF fees, pension payments, unrealised liquidation CGT or in-sample overfitting adjustment. Cohorts overlap, this is NOT independent validation."}
 p=Path(f"research_outputs/200wma_smsf_cost_stress_{args.currency.lower()}.json")
 p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(out,indent=2))
 print(json.dumps({"currency":args.currency,"result":{
  h:{k:{x:v for x,v in config.items() if x!="rows"}
   for k,config in tests.items()} for h,tests in all_results.items()}},indent=2))
if __name__=="__main__":main()
