"""Research-only sensitivity to execution cost for BTC 200WMA challengers.

No threshold fitting. Prices, calendar and DCA reference are identical for
all scenarios; independently revalue identical FIFO CGT liquidation on exit.
All returns are relative to same-cost DCA; no live broker orders.
"""
import json
from pathlib import Path
import numpy as np
import pandas as pd

from engines.research.test_200wma_smsf_costs import history
from engines.research.test_200wma_fair_liquidation import (
    fair_benchmark,fair_trading,CAP,ANNUAL_MER,summarize
)

SCENARIOS={
    "original_tier":{},
    "weakness_sell_8week_5pct":{"sell_guard_lookback":8},
    "reentry_8week_breakout":{"trend_reentry_lookback":8},
    "idle_recycle_26weeks":{"cash_recycle_idle_weeks":26},
}
SLIPPAGE=(.005,.01,.02)

def score(rows):
    z=summarize(rows,"advantage_pct")
    z["median_completed_sell_fills"]=float(np.median([r["sell_fills"] for r in rows]))
    z["median_free_cash_aud"]=round(float(np.median([r["free_cash_aud"] for r in rows])),2)
    z["by_year"]={str(year):summarize(
       [r for r in rows if r["year"]==year],"advantage_pct")
       for year in sorted({r["year"] for r in rows})}
    return z

def run():
    aud,signal,ma=history("AUD")
    prices=aud*np.power(1-ANNUAL_MER,np.arange(len(aud),dtype=float)/52)
    # Nonoverlapping vs previous 4-week experiment? No: 8-week intervals
    # still overlap substantially. These starts are correlated.
    candidate_starts=[i for i in range(len(prices)-1) if
       pd.Timestamp("2018-01-01",tz="UTC")<=prices.index[i]<=pd.Timestamp("2024-12-31",tz="UTC")][::8]
    output={}
    for horizon in (104,208):
        starts=[i for i in candidate_starts if i+horizon<len(prices)]
        horizon_results={}
        for slippage in SLIPPAGE:
            reference={}
            for i in starts:
                _,dca_liq=fair_benchmark(prices,signal,ma,i,i+horizon,slippage=slippage)
                reference[i]=dca_liq["net_fully_liquidated_aud"]
                if reference[i]<=0:raise AssertionError("DCA wealth nonpositive")
            scenarios={}
            for name,params in SCENARIOS.items():
                rows=[]
                for i in starts:
                    mark,liq,_=fair_trading(prices,signal,ma,i,i+horizon,
                         slippage=slippage,**params)
                    rows.append({"start":str(prices.index[i].date()),
                        "year":int(prices.index[i].year),
                        "end":str(prices.index[i+horizon].date()),
                        "advantage_pct":round(100*(liq["net_fully_liquidated_aud"]/reference[i]-1),4),
                        "trading_final_aud":liq["net_fully_liquidated_aud"],
                        "dca_final_aud":reference[i],
                        "sell_fills":mark["sell_fills"],
                        "free_cash_aud":mark["cash_usd"]})
                scenarios[name]={"summary":score(rows),"rows":rows}
            horizon_results[f"slippage_{slippage:.4f}"]=scenarios
        # Pair across friction scenarios: identical starts/end dates, same annual CGT method.
        for name in SCENARIOS:
            sets=[horizon_results[f"slippage_{s:.4f}"][name]["rows"] for s in SLIPPAGE]
            first=[r["start"] for r in sets[0]]
            if any([r["start"] for r in t]!=first for t in sets[1:]):
                raise AssertionError("Different dates used for execution-cost comparisons")
        output[f"{horizon}week"]=horizon_results
    dest=Path("research_outputs/200wma_execution_cost_stress_fair_exit_aud.json")
    dest.parent.mkdir(parents=True,exist_ok=True)
    dest.write_text(json.dumps({
        "description":"Causal Research-only USD 200WMA 2/4 year AUD SMSF fully-liquidated execution cost stress",
        "assumptions":"A$500k 20% initial BTC, same 12-week cash-funding schedule and matched BTC/AUD weekly prices; A$20 brokerage, 0.1% fee plus tested slippage on EACH purchase, interim sale/rebuy, and terminal liquidation in both models. 0.45% annual synthetic ETF expense drag; FIFO 15% illustrative accumulation SMSF annual settlement for tier model, final CGT for both. Slippage applied symmetrically to all transactions.",
        "limitations":"Every 8 weeks 2018-2024; cohorts still overlap and are in-sample. Slippage does not capture order-book impact, NAV timing, capital gains tax complexity, or fund distributions; no portfolio live orders.",
        "results":output
    },indent=2))
    print(json.dumps({h:{slip:{name:{k:v for k,v in z["summary"].items() if k!="by_year"}|
          {"weak_years":{y:{"median_pct":v["median_pct"],"wins":v["wins"]}
             for y,v in z["summary"]["by_year"].items() if y in ("2019","2021","2023")}}
          for name,z in scen.items()} for slip,scen in stress.items()} for h,stress in output.items()},indent=2))
if __name__=="__main__":run()
