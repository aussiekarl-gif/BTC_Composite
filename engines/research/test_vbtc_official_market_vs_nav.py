"""Trade VBTC research models against historical official ASX last traded quotes.

Issuer data covers only ETF inception onward (June 2024); NEVER pretend
the actual Australian ETF existed in the 2018/2019/2022 historical tests.
Signals remain BTC/USD prior-week closes vs USD 200WMA from archived data.
NAV-only fills are a hypothetical frictionless reference, not an executable
quote. No double counting of ETF 0.45% management fees baked into NAV.
"""
import json
from pathlib import Path
import numpy as np
import pandas as pd

from engines.research.vbtc_official_history import download_history
from engines.research.btc_200wma_history import load_completed_200wma_price_history
from engines.research.test_200wma_12week_execution import staged
from engines.research.test_200wma_cash_deployment import run as pure_dca
from engines.research.smsf_cgt_ledger import FifoCgtLedger,AnnualSmsfTaxPayment

def summary(rows):
    v=np.array([r["excess_after_model_tax_pct"] for r in rows])
    return {"starts":len(rows),"wins_vs_dca":int((v>0).sum()),
            "median_excess_pct":round(float(np.median(v)),3),
            "worst_pct":round(float(np.min(v)),3),
            "p10_pct":round(float(np.percentile(v,10)),3),
            "median_final_cash_aud":round(float(np.median([r["cash_aud"] for r in rows])),2)}

def run_model(series,usd,ma,start,end,guard):
    ledger=FifoCgtLedger()
    hook=AnnualSmsfTaxPayment(ledger,brokerage=20.,fee=.001,slippage=.005)
    x=staged(series,ma,start,end_index=end,
        shape="bell",buy_weeks=12,sell_weeks=16,
        block_overlap=True,reverse_cancel=False,
        initial_btc_fraction=.2,funding_weeks=12,
        funding_weighted=True,buy_levels=None,sell_levels=None,
        signal_price=usd,fee=.001,slippage=.005,
        brokerage_fixed=20.,btc_core_fraction=0.,
        cash_recycle_idle_weeks=(26 if guard else 0),
        cash_recycle_fraction=.25,cash_recycle_min_share=.5,
        trade_callback=ledger,weekly_hook=hook)
    tax=ledger.tax_summary()
    if abs(tax["net_units"]-x["btc_held"])>1e-5:
        raise AssertionError("Historical issuer-ETF tax ledger inventory mismatch")
    return {"net_aud":x["value_usd"]-tax["tax_outstanding"],
            "gross_aud":x["value_usd"],
            "cash_aud":x["cash_usd"],
            "etf_units":x["btc_held"],
            "tax_paid":tax["tax_cash_paid"],
            "tax_outstanding":tax["tax_outstanding"]}

def main():
    frame,meta=download_history()
    raw=frame.set_index("date").sort_index()
    weekly=raw[["nav_aud","last_traded_aud","premium_pct_calculated","volume"]].resample("W-MON").last()
    # Do not add a partial future-labelled Monday containing an incomplete week.
    weekly=weekly.loc[weekly.index<=raw.index.max().normalize()]
    usd,ma=load_completed_200wma_price_history()
    paired=pd.concat({"usd":usd,"wma":ma,"nav":weekly["nav_aud"],
       "trade":weekly["last_traded_aud"],
       "premium":weekly["premium_pct_calculated"],
       "volume":weekly["volume"]},axis=1,join="inner").dropna()
    if len(paired)<105:raise ValueError("VBTC live issuer history is insufficient for 2-year tests")
    if (paired[["usd","wma","nav","trade"]]<=0).any().any() or (paired["volume"]<0).any():
        raise ValueError("Bad issuer or USD data")
    starts=list(range(0,len(paired)-1,4))
    results={}
    for horizon in (52,104):
        eligible=[i for i in starts if i+horizon<len(paired)]
        models={}
        for price_kind in ("trade","nav"):
            s=paired[price_kind];signal=paired["usd"];wma=paired["wma"]
            rows=[]
            for i in eligible:
                end=i+horizon
                no_tier=pure_dca(s,wma,i,end,12,True,
                    signal_price=signal,brokerage_fixed=20.)
                ref_value=no_tier["value_usd"]
                for guard in (False,True):
                    state=run_model(s,signal,wma,i,end,guard)
                    rows.append({"start":str(paired.index[i].date()),
                        "end":str(paired.index[end].date()),
                        "guard":guard,
                        "excess_after_model_tax_pct":round(100*(state["net_aud"]/ref_value-1),4),
                        "cash_aud":round(state["cash_aud"],2),
                        "net_aud":round(state["net_aud"],2),
                        "dca_aud":round(ref_value,2)})
            for guard in (False,True):
                subset=[r for r in rows if r["guard"]==guard]
                models[f"{price_kind}_{'recycle26' if guard else 'tiers'}"]={
                    "summary":summary(subset),"rows":subset}
        results[f"{horizon}week"]={"models":models}
    premium=frame["premium_pct_calculated"].to_numpy(float)
    summary_meta={"records":len(frame),
        "issuer_first":meta["first"],"issuer_last":meta["last"],
        "paired_completed_weeks":len(paired),
        "signal_data_last_week":str(paired.index[-1].date()),
        "median_premium_pct":round(float(np.median(premium)),3),
        "p90_premium_pct":round(float(np.percentile(premium,90)),3),
        "max_premium_pct":round(float(premium.max()),3),
        "min_premium_pct":round(float(premium.min()),3),
        "days_premium_over_1pct":int(sum(premium>1)),
        "days_discount_below_minus_1pct":int(sum(premium< -1)),
        "zero_volume_days":int((frame["volume"]==0).sum()),
        "days_premium_over_5pct_with_volume":int(((frame["premium_pct_calculated"]>5)&(frame["volume"]>0)).sum()),
        "days_discount_below_minus_5pct_with_volume":int(((frame["premium_pct_calculated"]< -5)&(frame["volume"]>0)).sum()),
        "top_absolute_premium_examples":[{
            "date":str(row["date"].date()),"premium_pct":round(float(row["premium_pct_calculated"]),3),
            "last_traded_aud":round(float(row["last_traded_aud"]),4),
            "nav_aud":round(float(row["nav_aud"]),4),
            "volume":int(row["volume"])}
            for _,row in frame.iloc[np.argsort(-np.abs(premium))[:8]].iterrows()],
        "issuer_spread_data_available":False}
    p=Path("research_outputs/200wma_vbtc_official_market_vs_nav.json")
    p.parent.mkdir(parents=True,exist_ok=True)
    p.write_text(json.dumps({"issuer":meta,"price_summary":summary_meta,
        "results":results,
        "limitations":"Actual VBTC inception June 2024; only ~2 years of real exchange data, overlapping start cohorts. ASX last-traded prices are observable, not guaranteed executable fills; bid/ask unavailable. Additional hypothetical 0.1% dealing fee, 0.5% slippage and $20 brokerage. No extra management fee (NAV already net). Simplified SMSF early-July 15% accumulation CGT. USD moving-average data provider distinct from VBTC issuer. No 2019 or 2023 real VBTC fund existed to replicate those years."},indent=2))
    print(json.dumps({"issuer":summary_meta,
         "aggregates":{h:{k:v["summary"] for k,v in z["models"].items()} for h,z in results.items()}},indent=2))
if __name__=="__main__":main()
