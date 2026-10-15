from engines.research.btc_200wma_history import load_completed_200wma_price_history
"""Research-only exact 10x10 200WMA deviation crossing backtest.

No lookahead: weekly close signal, next weekly close fill. Repeated crossings
re-arm after opposite-side crossings. No production or portfolio writes.
"""
import json
from pathlib import Path
import numpy as np
import pandas as pd

CAP=500000.0
FEE=0.001
BUYS=[25,20,15,10,5,0,-5,-10,-20,-30]
SELLS=[100,120,140,160,180,200,220,240,260,280]

def simulate(price, ma, start, end=None, buy_levels=BUYS, sell_levels=SELLS):
    end=len(price)-1 if end is None else end
    btc=CAP*(1-FEE)/float(price.iloc[start+1])
    initial_btc=btc
    cash=0.0
    previous=None
    armed_sell=[True]*len(sell_levels)
    armed_buy=[True]*len(buy_levels)
    trades=[]
    for i in range(start+2,end+1):
        j=i-1
        if not np.isfinite(ma.iloc[j]) or ma.iloc[j]<=0:
            continue
        ratio=float(price.iloc[j]/ma.iloc[j]-1)*100
        execution=float(price.iloc[i])
        if previous is not None:
            # Re-arm only after the ratio returns to the other side.
            for k,t in enumerate(sell_levels):
                if ratio<t:
                    armed_sell[k]=True
            for k,t in enumerate(buy_levels):
                if ratio>t:
                    armed_buy[k]=True
            # Fixed fraction of INITIAL BTC, never more than actual holdings.
            for k,t in enumerate(sell_levels):
                if armed_sell[k] and previous<t<=ratio:
                    quantity=min(btc,initial_btc/len(sell_levels))
                    if quantity>1e-10:
                        btc-=quantity
                        cash+=quantity*execution*(1-FEE)
                        trades.append({"date":str(price.index[i].date()),"side":"SELL","tier":k+1,"deviation_pct":round(ratio,2),"btc":round(quantity,8)})
                    armed_sell[k]=False
            # Use a fraction of available cash at each crossing; no leverage.
            for k,t in enumerate(buy_levels):
                if armed_buy[k] and previous>t>=ratio and cash>1e-8:
                    spend=cash/len(buy_levels)
                    btc+=spend*(1-FEE)/execution
                    cash-=spend
                    trades.append({"date":str(price.index[i].date()),"side":"BUY","tier":k+1,"deviation_pct":round(ratio,2),"btc":round(spend*(1-FEE)/execution,8)})
                    armed_buy[k]=False
        previous=ratio
    terminal=float(price.iloc[end])
    value=cash+btc*terminal
    hold_btc=CAP*(1-FEE)/float(price.iloc[start+1])
    return {"value_usd":round(value,2),"hold_usd":round(hold_btc*terminal,2),
            "vs_hold_pct":round(100*(value/(hold_btc*terminal)-1),3),
            "btc_held":round(btc,8),"btc_equivalent":round(value/terminal,8),
            "cash_usd":round(cash,2),"trades":trades}

def main():
    s,ma=load_completed_200wma_price_history()
    eligible=[i for i in range(201,len(s)-1) if pd.Timestamp("2018-01-01",tz="UTC")<=s.index[i]<=pd.Timestamp("2024-12-31",tz="UTC")]
    rows=[]
    for start in eligible[::4]:
        r=simulate(s,ma,start)
        rows.append({"start":str(s.index[start].date()),"year":int(s.index[start].year),
                     **{k:v for k,v in r.items() if k!="trades"},
                     "sells":sum(t["side"]=="SELL" for t in r["trades"]),
                     "buys":sum(t["side"]=="BUY" for t in r["trades"])})
    by_year={}
    for y in sorted(set(r["year"] for r in rows)):
        vals=[r["vs_hold_pct"] for r in rows if r["year"]==y]
        by_year[str(y)]={"starts":len(vals),"wins":sum(v>0 for v in vals),
                         "median_pct":round(float(np.median(vals)),2),
                         "worst_pct":round(min(vals),2)}
    case_starts={}
    for year in (2018,2020,2021,2022,2023,2024):
        matches=[i for i in eligible if s.index[i].year==year]
        if matches:
            i=matches[0]
            case_starts[str(year)]=simulate(s,ma,i)
    out={"name":"exact-10-buy-10-sell-deviation-crossing-rearm","currency":"USD",
         "fee":FEE,"buy_deviation_pct":BUYS,"sell_deviation_pct":SELLS,
         "starts":len(rows),"wins":sum(r["vs_hold_pct"]>0 for r in rows),
         "median_pct":round(float(np.median([r["vs_hold_pct"] for r in rows])),2),
         "by_year":by_year,"rows":rows,"case_trades":case_starts,
         "limitations":"Overlapping starts, in-sample, fixed terminal date, no slippage or taxes; no live execution. Fixed initial-BTC sell sizing, current-cash/10 buy sizing; these are provisional execution rules."}
    p=Path("research_outputs/200wma_exact_10x10.json")
    p.parent.mkdir(parents=True,exist_ok=True)
    p.write_text(json.dumps(out,indent=2))
    print(json.dumps({k:v for k,v in out.items() if k not in ("rows","case_trades")},indent=2))
if __name__=="__main__":main()
