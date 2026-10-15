"""Explain failed BTC 200WMA cycle cohorts without tuning trading parameters.

Uses completed USD signals, BTC/AUD reference execution, conservative
hypothetical ETF MER, per-fill brokerage/slippage and accumulation CGT.
Compares identical cash-funded pure DCA against tier trading and 26-week
idle-cash recycling across previously troublesome 2019 and 2023 starts,
with 2021 controls. Historical, in-sample attribution only.
"""
import json
from pathlib import Path
import numpy as np
import pandas as pd

from engines.research.test_200wma_smsf_costs import history
from engines.research.test_200wma_12week_execution import staged
from engines.research.smsf_cgt_ledger import FifoCgtLedger,AnnualSmsfTaxPayment

FEE=.001
SLIPPAGE=.005
BROKER=20.
MER=.0045
HORIZON=104

def simulate(s,signal,ma,start,end,mode):
    ledger=FifoCgtLedger()
    settle=AnnualSmsfTaxPayment(ledger,BROKER,FEE,SLIPPAGE)
    fills=[]
    snapshots=[]
    def trade(event):
        ledger(event)
        fills.append({"side":event["side"],"kind":event["kind"],
            "units":float(event["units"]),"cash":float(event["cash"]),
            "date":str(pd.Timestamp(event["date"]).date())})
    def weekly(i,date,px,cash,btc):
        cash,btc=settle(i,date,px,cash,btc)
        total=cash+btc*px
        snapshots.append({"date":str(pd.Timestamp(date).date()),
            "cash_share":cash/total if total>0 else 0.,
            "gross_value":total,"cash":cash,"etf_units":btc})
        return cash,btc
    params=dict(shape="bell",buy_weeks=12,sell_weeks=16,
        block_overlap=True,reverse_cancel=False,
        initial_btc_fraction=.2,funding_weeks=12,
        funding_weighted=True,signal_price=signal,
        fee=FEE,slippage=SLIPPAGE,brokerage_fixed=BROKER,
        trade_callback=trade,weekly_hook=weekly,end_index=end)
    if mode=="dca":
        params.update(buy_levels=[],sell_levels=[],cash_recycle_idle_weeks=0)
    elif mode=="tier":
        params.update(cash_recycle_idle_weeks=0)
    elif mode=="recycle26":
        params.update(cash_recycle_idle_weeks=26,
                      cash_recycle_fraction=.25,cash_recycle_min_share=.5)
    else:raise ValueError("Unknown scenario")
    r=staged(s,ma,start,**params)
    tax=ledger.tax_summary()
    if abs(tax["net_units"]-r["btc_held"])>1e-5:
        raise AssertionError("Tax ledger units disagree with portfolio")
    after=snapshots[12:] # Remove initial cash-funding schedule
    values=np.array([x["gross_value"] for x in snapshots],dtype=float)
    dd=100*(values/np.maximum.accumulate(values)-1)
    return {"net_aud":round(r["value_usd"]-tax["tax_outstanding"],2),
        "gross_aud":r["value_usd"],
        "cash_at_end":r["cash_usd"],
        "tax_paid":tax["tax_cash_paid"],
        "max_gross_drawdown_pct":round(float(np.min(dd)),3),
        "mean_cash_weight_post_funding_pct":round(100*float(np.mean([x["cash_share"] for x in after])),3),
        "weeks_above_50pct_cash":sum(x["cash_share"]>.5 for x in after),
        "weeks_observed_after_funding":len(after),
        "tier_sell_fills":sum(e["side"]=="SELL" and e["kind"]=="TIER" for e in fills),
        "tier_buy_fills":sum(e["side"]=="BUY" and e["kind"]=="TIER" for e in fills),
        "recycle_fills":sum(e["kind"]=="RECYCLE" for e in fills),
        "total_tier_sell_proceeds_aud":round(sum(e["cash"] for e in fills if e["side"]=="SELL" and e["kind"]=="TIER"),2),
        "total_tier_rebuys_aud":round(sum(e["cash"] for e in fills if e["side"]=="BUY" and e["kind"]=="TIER"),2),
        "last_four_weeks_cash_pct":[round(100*x["cash_share"],2) for x in snapshots[-4:]]}

def aggregate(rows):
    def median(field):return round(float(np.median([r[field] for r in rows])),3)
    return {"starts":len(rows),"wins_vs_dca":sum(r["vs_dca_pct"]>0 for r in rows),
            "median_vs_dca_pct":median("vs_dca_pct"),
            "worst_vs_dca_pct":round(min(r["vs_dca_pct"] for r in rows),3),
            "median_post_funding_cash_weight_pct":median("mean_cash_weight_post_funding_pct"),
            "median_weeks_above_half_cash":median("weeks_above_50pct_cash"),
            "median_cash_at_end_aud":median("cash_at_end"),
            "median_tier_sell_fills":median("tier_sell_fills"),
            "median_tier_buy_fills":median("tier_buy_fills"),
            "median_recycle_fills":median("recycle_fills")}

def main():
    prices,signals,ma=history("AUD")
    nav=prices*np.power(1-MER,np.arange(len(prices),dtype=float)/52)
    starts=[i for i in range(len(nav)-HORIZON) if
        pd.Timestamp("2018-01-01",tz="UTC")<=nav.index[i]<=pd.Timestamp("2024-12-31",tz="UTC")][::4]
    report={}
    for year in (2019,2021,2023):
        eligible=[i for i in starts if nav.index[i].year==year]
        groups={k:[] for k in ("tier","recycle26")}
        for i in eligible:
            end=i+HORIZON
            base=simulate(nav,signals,ma,i,end,"dca")
            for strategy in groups:
                metrics=simulate(nav,signals,ma,i,end,strategy)
                metrics.update({
                    "start":str(nav.index[i].date()),
                    "end":str(nav.index[end].date()),
                    "dca_net_aud":base["net_aud"],
                    "vs_dca_pct":round(100*(metrics["net_aud"]/base["net_aud"]-1),4)})
                groups[strategy].append(metrics)
        report[str(year)]={strategy:{"aggregate":aggregate(rows),
            "worst_start":min(rows,key=lambda r:r["vs_dca_pct"]),
            "rows":rows} for strategy,rows in groups.items()}
    out={"description":"In-sample cash-drag attribution for weak 2019/2023 2-year rolling entry cohorts compared with 2021",
      "assumptions":"Synthetic AUD ETF proxy, A$20 fill brokerage, 0.1% fee, 0.5% slippage, 0.45% annual expense drag, 20/80 initial capital with 12-week funding, simplified FIFO annual SMSF accumulation tax",
      "data_caution":"2019 and 2023 are already known weak years, so these are forensic diagnostics, NOT evidence of out-of-sample improvement. Weekly start cohorts overlap.",
      "results":report}
    target=Path("research_outputs/200wma_failure_attribution_aud.json")
    target.parent.mkdir(parents=True,exist_ok=True)
    target.write_text(json.dumps(out,indent=2))
    print(json.dumps({year:{name:obj["aggregate"] for name,obj in strategies.items()}
       for year,strategies in report.items()},indent=2))

if __name__=="__main__":main()
