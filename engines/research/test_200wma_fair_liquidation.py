"""Common fully-liquidated AUD BTC DCA vs 200WMA trading benchmark.

Both strategies:
- begin with the same hypothetical AUD 500k, 20% BTC / 80% cash;
- deploy the other 80% over 12 completed weeks by the same causal weight;
- pay identical fees and slippage on buys and final liquidation;
- use FIFO Australian SMSF accumulation CGT including all unrealised lots
  disposed of at the same final 2y/4y weekly closing price.

Trading additionally settles realised SMSF CGT at the first July weekly
close as a conservative cashflow stress, whereas buy-only DCA owes no CGT
until exit. These are model estimates, NOT an SMSF return or tax advice.
"""
import json
from pathlib import Path
import numpy as np
import pandas as pd

from engines.research.test_200wma_smsf_costs import history
from engines.research.test_200wma_12week_execution import staged
from engines.research.test_200wma_cash_deployment import run as pure_dca
from engines.research.smsf_cgt_ledger import FifoCgtLedger,AnnualSmsfTaxPayment
from engines.research.terminal_liquidation import terminal_liquidation

FEE=.001
SLIPPAGE=.005
BROKER_AUD=20.
ANNUAL_MER=.0045
CAP=500000.


def summarize(rows,key):
    v=np.array([r[key] for r in rows],dtype=float)
    return {"starts":len(rows),"wins":int((v>0).sum()),
        "median_pct":round(float(np.median(v)),3),
        "worst_pct":round(float(np.min(v)),3),
        "p10_pct":round(float(np.percentile(v,10)),3)}

def fair_benchmark(s,signal,ma,start,end):
    ledger=FifoCgtLedger()
    state=pure_dca(s,ma,start,end,12,True,signal_price=signal,
                   brokerage_fixed=BROKER_AUD,trade_callback=ledger)
    mark=state["value_usd"]
    liquidation=terminal_liquidation(ledger,state["cash_usd"],
        ledger.bought_units-ledger.sold_units,s.index[end],s.iloc[end],
        brokerage=BROKER_AUD,fee=FEE,slippage=SLIPPAGE)
    return state,liquidation

def fair_trading(s,signal,ma,start,end,
                 cash_recycle_idle_weeks=0,
                 max_cash_weight_after_sell=None,
                 sell_guard_lookback=0,
                 trend_reentry_lookback=0):
    ledger=FifoCgtLedger()
    hook=AnnualSmsfTaxPayment(ledger,BROKER_AUD,FEE,SLIPPAGE)
    state=staged(s,ma,start,shape="bell",reverse_cancel=False,
      buy_weeks=12,sell_weeks=16,block_overlap=True,
      fee=FEE,slippage=SLIPPAGE,
      brokerage_fixed=BROKER_AUD,end_index=end,
      initial_btc_fraction=.20,funding_weeks=12,
      funding_weighted=True,signal_price=signal,
      cash_recycle_idle_weeks=cash_recycle_idle_weeks,
      max_cash_weight_after_sell=max_cash_weight_after_sell,
      sell_guard_lookback=sell_guard_lookback,
      trend_reentry_lookback=trend_reentry_lookback,
      trade_callback=ledger,weekly_hook=hook)
    if abs(ledger.bought_units-ledger.sold_units-state["btc_held"])>1e-5:
        raise AssertionError("Strategy holdings and FIFO ledger differ")
    # Take the comparison on exactly the same completed weekly bar.
    liquidation=terminal_liquidation(ledger,state["cash_usd"],
      ledger.bought_units-ledger.sold_units,s.index[end],s.iloc[end],
      brokerage=BROKER_AUD,fee=FEE,slippage=SLIPPAGE)
    # Report the previous method to quantify the unfair tax timing it used.
    estimate=state["value_usd"]-ledger.tax_summary()["tax_outstanding"]
    return state,liquidation,estimate

def main():
    px,signal,ma=history("AUD")
    prices=px*np.power(1-ANNUAL_MER,np.arange(len(px),dtype=float)/52)
    all_starts=[i for i in range(len(prices)-1) if
      pd.Timestamp("2018-01-01",tz="UTC")<=prices.index[i]<=pd.Timestamp("2024-12-31",tz="UTC")][::4]
    results={}
    for horizon in (104,208):
        starts=[i for i in all_starts if i+horizon<len(prices)]
        cases={}
        for label,settings in {
            "original_tier":{},
            "idle_recycle_26weeks":{"cash_recycle_idle_weeks":26},
        }.items():
            rows=[]
            for i in starts:
                end=i+horizon
                b,bl=fair_benchmark(prices,signal,ma,i,end)
                t,tl,estimate=fair_trading(prices,signal,ma,i,end,**settings)
                if tl["net_fully_liquidated_aud"]<=0 or bl["net_fully_liquidated_aud"]<=0:
                    raise ValueError("Negative or zero post-exit wealth")
                rows.append({
                    "start":str(prices.index[i].date()),
                    "end":str(prices.index[end].date()),
                    "start_year":int(prices.index[i].year),
                    "fully_liquidated_advantage_pct":round(100*(tl["net_fully_liquidated_aud"]/bl["net_fully_liquidated_aud"]-1),4),
                    "old_unmatched_tax_advantage_pct":round(100*(estimate/b["value_usd"]-1),4),
                    "gross_mark_advantage_pct":round(100*(t["value_usd"]/b["value_usd"]-1),4),
                    "trading_fully_liquidated_aud":tl["net_fully_liquidated_aud"],
                    "dca_fully_liquidated_aud":bl["net_fully_liquidated_aud"],
                    "trading_final_sale_tax_aud":tl["tax_remaining_at_exit_aud"],
                    "dca_final_sale_tax_aud":bl["tax_remaining_at_exit_aud"],
                    "trading_previously_paid_tax_aud":tl["tax_already_paid_aud"],
                    "trading_cash_at_exit_aud":t["cash_usd"],
                    "dca_cash_at_exit_aud":b["cash_usd"]
                })
            cases[label]={
                "fair":summarize(rows,"fully_liquidated_advantage_pct"),
                "old_unmatched":summarize(rows,"old_unmatched_tax_advantage_pct"),
                "gross":summarize(rows,"gross_mark_advantage_pct"),
                "by_start_year":{str(y):summarize([r for r in rows if r["start_year"]==y],
                    "fully_liquidated_advantage_pct") for y in sorted(set(r["start_year"] for r in rows))},
                "median_exit_tax_dca_aud":round(float(np.median([r["dca_final_sale_tax_aud"] for r in rows])),2),
                "median_exit_tax_trading_aud":round(float(np.median([r["trading_final_sale_tax_aud"] for r in rows])),2),
                "rows":rows
            }
        results[f"{horizon}week"]=cases
    p=Path("research_outputs/200wma_fair_terminal_liquidation_aud.json")
    p.parent.mkdir(parents=True,exist_ok=True)
    p.write_text(json.dumps({
        "currency":"AUD",
        "capital_aud":CAP,
        "fee_each_fill":FEE,"slippage_each_fill":SLIPPAGE,
        "brokerage_aud":BROKER_AUD,"annual_hypothetical_mer":ANNUAL_MER,
        "reference":"Synthetic BTC/AUD ETF price proxy, not actual VBTC history",
        "tax":"Illustrative FIFO 15% SMSF accumulation tax, fully liquidated on identical dated exit, earlier July settlements for trading",
        "limitations":"Overlapping in-sample start windows, optimistic midpoint/close fills, no true ETF spreads/tax distribution, no ECPI/mixed assets, no independent holdout",
        "results":results
    },indent=2))
    print(json.dumps({h:{k:{z:v for z,v in obj.items() if z not in ("rows","by_start_year")}
        |{"by_start_year":{yr:{"median_pct":q["median_pct"],"wins":q["wins"],"starts":q["starts"]} for yr,q in obj["by_start_year"].items() if yr in ("2019","2021","2023")}}
        for k,obj in e.items()} for h,e in results.items()},indent=2))

if __name__=="__main__":main()
