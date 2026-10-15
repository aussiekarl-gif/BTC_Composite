"""Test total cash-exposure ceilings as an alternative to BTC tier sell paralysis.

Research-only post-hoc sensitivity: 25%, 40%, 60% max total cash weight
(including reserved/funding cash) after any tier sell, versus no cash ceiling.
AUD synthetic ETF proxy, annual SMSF CGT, same cash-funded DCA comparison,
fixed 104/208 week horizons. All overlapping in-sample cohorts.
"""
import json
from pathlib import Path
import numpy as np
import pandas as pd

from engines.research.test_200wma_smsf_costs import history
from engines.research.test_200wma_12week_execution import staged
from engines.research.test_200wma_cash_deployment import run as pure_dca
from engines.research.smsf_cgt_ledger import FifoCgtLedger,AnnualSmsfTaxPayment

FEE=.001
SLIPPAGE=.005
BROKER=20.
MER=.0045

def summarize(rows):
    v=np.asarray([r["vs_dca_pct"] for r in rows],dtype=float)
    return {"starts":len(rows),"wins":int((v>0).sum()),
        "median_pct":round(float(np.median(v)),3),
        "worst_pct":round(float(v.min()),3),
        "p10_pct":round(float(np.percentile(v,10)),3),
        "median_cash_aud":round(float(np.median([r["free_cash"] for r in rows])),2),
        "median_sell_fills":float(np.median([r["sell_fills"] for r in rows]))}

def run():
    px,signal,ma=history("AUD")
    nav=px*np.power(1-MER,np.arange(len(px),dtype=float)/52)
    starts=[i for i in range(len(px)-1)
      if pd.Timestamp("2018-01-01",tz="UTC")<=px.index[i]<=pd.Timestamp("2024-12-31",tz="UTC")][::4]
    results={}
    for horizon in (104,208):
        valid=[i for i in starts if i+horizon<len(px)]
        baseline={i:pure_dca(nav,ma,i,i+horizon,12,True,
            signal_price=signal,brokerage_fixed=BROKER)["value_usd"] for i in valid}
        tests={}
        for ceiling in (None,.25,.40,.60):
            rows=[]
            for i in valid:
                ledger=FifoCgtLedger()
                hook=AnnualSmsfTaxPayment(ledger,BROKER,FEE,SLIPPAGE)
                trial=staged(nav,ma,i,shape="bell",reverse_cancel=False,
                    buy_weeks=12,sell_weeks=16,block_overlap=True,
                    fee=FEE,slippage=SLIPPAGE,brokerage_fixed=BROKER,
                    end_index=i+horizon,initial_btc_fraction=.2,
                    funding_weeks=12,funding_weighted=True,signal_price=signal,
                    max_cash_weight_after_sell=ceiling,
                    trade_callback=ledger,weekly_hook=hook)
                tax=ledger.tax_summary()
                if abs(tax["net_units"]-trial["btc_held"])>1e-5:
                    raise AssertionError("Invalid tax lot balance")
                value=trial["value_usd"]-tax["tax_outstanding"]
                rows.append({"start":str(px.index[i].date()),
                    "year":int(px.index[i].year),
                    "vs_dca_pct":round(100*(value/baseline[i]-1),4),
                    "net_value":round(value,2),
                    "free_cash":trial["cash_usd"],
                    "sell_fills":tax["sell_fills"],
                    "cash_weight_at_exit":round(100*trial["cash_usd"]/trial["value_usd"],3)})
            label="uncapped" if ceiling is None else f"max_cash_{int(100*ceiling)}pct"
            tests[label]={"aggregate":summarize(rows),
                 "by_year":{str(y):summarize([r for r in rows if r["year"]==y])
                            for y in sorted(set(r["year"] for r in rows))},
                 "rows":rows}
        results[f"{horizon}week"]={"tests":tests}
    # Regression guard: capped experiment must not alter no-cap baseline.
    n=results["104week"]["tests"]["uncapped"]["aggregate"]["median_pct"]
    if abs(n-2.402)>.02:raise AssertionError(f"Unexpected original AUD CGT median {n}")
    n4=results["208week"]["tests"]["uncapped"]["aggregate"]["median_pct"]
    if abs(n4-33.099)>.02:raise AssertionError(f"Unexpected original four-year AUD median {n4}")
    p=Path("research_outputs/200wma_cash_exposure_ceiling_aud.json")
    p.parent.mkdir(parents=True,exist_ok=True)
    p.write_text(json.dumps({"assumptions":"Synthetic BTC/AUD ETF prices, 20% initial BTC 80% cash, 12-week weighted funding, 12-week tier buys, 16-week tier sells, broker A$20, 0.1% fee, 0.5% slippage, hypothetical 0.45% management drag; simplified annual 15% SMSF accumulation CGT. Post-hoc ceiling selected with knowledge of 2019 and 2023. No Production writes.",
        "interpretation":"Sell fill quantity capped from causal current ETF marked holdings to keep funding cash + reserved buy cash + free cash below specified % of total marked portfolio. Trading disabled only at cap; no forced extra buying.",
        "results":results},indent=2))
    print(json.dumps({h:{case:r["aggregate"]|
          {"by_year":{y:{k:v for k,v in d.items() if k in ("median_pct","wins","median_cash_aud")}
                      for y,d in r["by_year"].items() if y in ("2019","2021","2023")}}
          for case,r in hdata["tests"].items()} for h,hdata in results.items()},indent=2))

if __name__=="__main__":run()
