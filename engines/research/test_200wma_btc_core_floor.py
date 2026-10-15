from engines.research.btc_200wma_history import load_completed_200wma_price_history
"""Research-only BTC core retention test for cash-first 200WMA trading.

Evaluate exact same initial 20% BTC/80% cash portfolio, 12-week risk-weighted
funding and 12-week buy/16-week sell bell curve across fixed 2/3/4-year horizons.
The protected BTC core is an absolute BTC quantity fixed at entry, not a
percentage of current value; performance is compared to a pure-DCA benchmark.
"""
import json
from pathlib import Path
import numpy as np
import pandas as pd

from engines.research.test_200wma_12week_execution import staged
from engines.research.test_200wma_cash_deployment import run as pure_dca

CAP=500000.0
FEE=0.001
SLIPPAGE=0.005

def report(rows):
    v=np.array([r["vs_dca_pct"] for r in rows],dtype=float)
    return {
        "starts":len(rows),
        "wins":int((v>0).sum()),
        "median_pct":round(float(np.median(v)),3),
        "mean_pct":round(float(np.mean(v)),3),
        "worst_pct":round(float(np.min(v)),3),
        "p10_pct":round(float(np.percentile(v,10)),3),
        "p25_pct":round(float(np.percentile(v,25)),3),
        "best_pct":round(float(np.max(v)),3),
        "median_btc_held":round(float(np.median([r["btc_held"] for r in rows])),6),
        "median_btc_equivalent":round(float(np.median([r["btc_equivalent"] for r in rows])),6),
        "median_cash_usd":round(float(np.median([r["cash_usd"] for r in rows])),2),
        "median_transactions":round(float(np.median([r["transactions"] for r in rows])),1),
        "worst_start":min(rows,key=lambda r:r["vs_dca_pct"])["start"],
    }

def main():
    s,ma=load_completed_200wma_price_history()
    starts=[i for i in range(201,len(s)-1)
        if pd.Timestamp("2018-01-01",tz="UTC")<=s.index[i]<=pd.Timestamp("2024-12-31",tz="UTC")][::4]
    out={}
    for horizon in (104,156,208):
        valid=[i for i in starts if i+horizon<len(s)]
        bench={i:pure_dca(s,ma,i,i+horizon,12,True)["value_usd"] for i in valid}
        tests={}
        for floor in (0.,0.25,0.50,0.75):
            rows=[]
            for i in valid:
                r=staged(s,ma,i,shape="bell",reverse_cancel=False,buy_weeks=12,
                     sell_weeks=16,block_overlap=True,slippage=SLIPPAGE,fee=FEE,
                     end_index=i+horizon,initial_btc_fraction=0.2,
                     funding_weeks=12,funding_weighted=True,
                     btc_core_fraction=floor)
                rows.append({
                    "start":str(s.index[i].date()),
                    "start_year":int(s.index[i].year),
                    "vs_dca_pct":round(100*(r["value_usd"]/bench[i]-1),4),
                    "btc_held":r["btc_held"],
                    "btc_equivalent":r["btc_equivalent"],
                    "cash_usd":r["cash_usd"],
                    "transactions":r["transactions"],
                    "pending_jobs":r["pending_jobs"]
                })
            tests[str(floor)]={
                "aggregate":report(rows),
                "by_start_year":{str(y):report([r for r in rows if r["start_year"]==y])
                    for y in sorted(set(r["start_year"] for r in rows))},
                "rows":rows,
            }
        out[f"{horizon}_week"]={"tests":tests}
    result={
        "description":"Fixed absolute-BTC core retained during staged sell/rebuy after cash-first funding",
        "initial_btc_fraction":0.2,
        "risk_weighted_funding_weeks":12,
        "buy_schedule_weeks":12,
        "sell_schedule_weeks":16,
        "fee":FEE,"slippage":SLIPPAGE,
        "core_definition":"Floor fraction * hypothetical BTC obtained from investing entire initial USD budget at initial purchase price (after fee). Trading cannot sell these BTC units.",
        "comparison":"Identical 20% BTC/80% cash entry with 12-week risk-weighted DCA, no sells",
        "limitations":"Overlapping starts; holding periods fixed by available data; historic thresholds selected using this data; USD only, no SMSF taxes, FX, spread variability or actual liquidity.",
        "results":out
    }
    p=Path("research_outputs/200wma_btc_core_floor.json")
    p.parent.mkdir(parents=True,exist_ok=True)
    p.write_text(json.dumps(result,indent=2))
    print(json.dumps({h:{floor:v["aggregate"] for floor,v in z["tests"].items()} for h,z in out.items()},indent=2))
if __name__=="__main__":main()
