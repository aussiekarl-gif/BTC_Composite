"""Predeclared adaptive BTC 200WMA exits and momentum reentry challengers.

All AUD outcomes compare the SAME A$500k cash-first starting position and
complete ETF liquidation costs, including FIFO SMSF accumulation CGT in
BOTH the trading and independent DCA-only benchmark at the SAME end date.

This is exploratory, in-sample. No candidate is eligible for automatic
promotion into frozen paper v1 or Production V5.8.2.
"""
import json
from pathlib import Path
import numpy as np
import pandas as pd
from engines.research.test_200wma_smsf_costs import history
from engines.research.test_200wma_fair_liquidation import (
    fair_benchmark,fair_trading,summarize,CAP,ANNUAL_MER
)

VARIANTS={
    "existing_12buy_16sell":{},
    "weakness_sell_8week_5pct":{"sell_guard_lookback":8},
    "reentry_8week_breakout":{"trend_reentry_lookback":8},
    "weakness_plus_reentry":{
        "sell_guard_lookback":8,"trend_reentry_lookback":8},
    "exposure40_plus_reentry":{
        "max_cash_weight_after_sell":.40,"trend_reentry_lookback":8},
    "existing_26week_idle":{"cash_recycle_idle_weeks":26}
}

def as_summary(rows):
    return {
        "fully_liquidated":summarize(rows,"fully_liquidated_advantage_pct"),
        "median_sell_fills":float(np.median([r["sell_fills"] for r in rows])),
        "median_reentry_fills":float(np.median([r["reentry_fills"] for r in rows])),
        "median_cash_at_exit_aud":round(float(np.median([r["free_cash_aud"] for r in rows])),2),
        "by_year":{str(year):summarize(
            [r for r in rows if r["year"]==year],
            "fully_liquidated_advantage_pct")
            for year in sorted({r["year"] for r in rows})}
    }

def main():
    px,signal,ma=history("AUD")
    prices=px*np.power(1-ANNUAL_MER,np.arange(len(px),dtype=float)/52)
    starts=[i for i in range(len(px)-1) if
        pd.Timestamp("2018-01-01",tz="UTC")<=prices.index[i]<=pd.Timestamp("2024-12-31",tz="UTC")][::4]
    results={}
    for horizon in (104,156,208):
        eligible=[i for i in starts if i+horizon<len(prices)]
        records={name:[] for name in VARIANTS}
        for i in eligible:
            end=i+horizon
            base_state,base_liq=fair_benchmark(prices,signal,ma,i,end)
            base=base_liq["net_fully_liquidated_aud"]
            if base<=0:raise AssertionError("DCA comparator liquidated wealth invalid")
            for name,settings in VARIANTS.items():
                trial,liq,_=fair_trading(prices,signal,ma,i,end,**settings)
                records[name].append({
                    "start":str(prices.index[i].date()),
                    "end":str(prices.index[end].date()),
                    "year":int(prices.index[i].year),
                    "fully_liquidated_advantage_pct":round(100*(liq["net_fully_liquidated_aud"]/base-1),4),
                    "trading_liquidated_aud":liq["net_fully_liquidated_aud"],
                    "dca_liquidated_aud":base,
                    "free_cash_aud":trial["cash_usd"],
                    "sell_fills":trial["sell_fills"],
                    "reentry_fills":trial["reentry_fills"],
                    "exit_cgt_aud":liq["tax_remaining_at_exit_aud"],
                })
        # Every candidate must compare against precisely the same independent
        # baseline; no case-specific calendar/data/FX horizon choices.
        keys=list(records)
        for k in range(len(eligible)):
            values={records[name][k]["dca_liquidated_aud"] for name in keys}
            if len(values)!=1:raise AssertionError("DCA baseline varies by strategy")
        results[f"{horizon}week"]={
            name:{"stats":as_summary(rows),"rows":rows}
            for name,rows in records.items()}
    doc={
        "scope":"AUD exploratory fixed-horizon adaptive tier challengers, 2018-2024 overlapping starts",
        "capital_aud":CAP,
        "assumptions":"Synthetic BTC/AUD ETF price with 0.45% annual MER, A$20 brokerage, 0.1% dealing fee and 0.5% slippage on every fill including final exit. Both model and DCA final holdings sold at same price/date and taxed using FIFO 15% illustrative SMSF accumulation CGT. Trading pays historic realised tax each July. Existing strategy otherwise unaltered.",
        "strategy_variants":{
            "existing_12buy_16sell":"Original 10/10 200WMA tier crossing and 12-week buy / 16-week sell schedules, overlap blocked.",
            "weakness_sell_8week_5pct":"Sell-tier crossing schedules execute only on completed weeks when BTC is >=5% below prior eight-week rolling high; pending sells may expire.",
            "reentry_8week_breakout":"Existing sells, buy 25% of free cash after prior completed weekly BTC close breaks preceding 8-week highs and is >3% above four weeks ago, if cash >40% of marked holdings and a tier sell happened; 12-week cooldown.",
            "weakness_plus_reentry":"Both 5% post-peak sell gate and 8-week breakout cash reentry.",
            "exposure40_plus_reentry":"Sell cash cap of 40% total mark-to-market plus 8-week breakout cash reentry.",
            "existing_26week_idle":"Unaltered research exploratory 26-week idle cash recycle rule."
        },
        "critical_limits":"Variants proposed after inspecting 2019/2023 and prior historical returns. Overlapping starts are not independent and do not constitute out-of-sample evidence. BTC signal week j and prices through j inform fills at next weekly execution i. Ignore capital-gains holding parcel selection outside FIFO, ETF tax attribution/dividends, pension exemptions, varying brokerage/spread, borrowing and retirement withdrawals. Frozen v1 paper test not changed.",
        "results":results
    }
    p=Path("research_outputs/200wma_adaptive_challengers_fair_exit_aud.json")
    p.parent.mkdir(parents=True,exist_ok=True)
    p.write_text(json.dumps(doc,indent=2))
    short={h:{n:{"full":v["stats"]["fully_liquidated"],
                     "median_sells":v["stats"]["median_sell_fills"],
                     "median_reentries":v["stats"]["median_reentry_fills"],
                     "median_cash":v["stats"]["median_cash_at_exit_aud"],
                     "weak_years":{y:{"median":v["stats"]["by_year"][y]["median_pct"],
                             "wins":v["stats"]["by_year"][y]["wins"]}
                        for y in ("2019","2021","2023") if y in v["stats"]["by_year"]}}
                  for n,v in results[h].items()}
          for h in results}
    print(json.dumps(short,indent=2))
if __name__=="__main__":main()
