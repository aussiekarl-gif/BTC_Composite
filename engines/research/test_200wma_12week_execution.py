from engines.research.btc_200wma_history import load_completed_200wma_price_history
"""Compare 12- and 16-week time-distributed 200WMA crossing trades with immediate execution.
Research-only, no production writes. Completed weekly signal, next-week fill.
"""
import json
from pathlib import Path
import numpy as np
import pandas as pd
from engines.research.test_200wma_exact_10x10 import CAP,FEE,BUYS,SELLS,simulate

def weights(shape,weeks):
    if shape=="equal":v=np.ones(weeks)
    elif shape=="front":v=np.arange(weeks,0,-1,dtype=float)
    elif shape=="back":v=np.arange(1,weeks+1,dtype=float)
    else:
        x=np.linspace(-1,1,weeks)
        v=np.maximum(0.05,1-np.abs(x))
    return v/v.sum()

def staged(s,ma,start,shape="equal",reverse_cancel=False,weeks=12,buy_weeks=None,sell_weeks=None,buy_levels=None,sell_levels=None,fee=FEE,block_overlap=False,slippage=0.0,end_index=None,initial_btc_fraction=1.0,funding_weeks=0,funding_weighted=False,btc_core_fraction=0.0,sell_cross_direction="up",signal_price=None,brokerage_fixed=0.0,trade_callback=None,weekly_hook=None,cash_recycle_idle_weeks=0,cash_recycle_fraction=0.25,cash_recycle_min_share=0.50):
    if signal_price is None:signal_price=s
    if not s.index.equals(signal_price.index):raise ValueError("Signal-price and execution-price dates differ")
    buy_levels=BUYS if buy_levels is None else buy_levels
    sell_levels=SELLS if sell_levels is None else sell_levels
    if not 0 <= initial_btc_fraction <= 1:raise ValueError("Invalid BTC fraction")
    if funding_weeks < 0:raise ValueError("Invalid funding weeks")
    if not 0 <= btc_core_fraction <= 1:raise ValueError("Invalid BTC core fraction")
    if not 0 <= brokerage_fixed < CAP:raise ValueError("Invalid fixed brokerage")
    if cash_recycle_idle_weeks < 0 or not 0 < cash_recycle_fraction <= 1 or not 0 < cash_recycle_min_share < 1:
        raise ValueError("Invalid cash recycling parameters")
    if sell_cross_direction not in ("up","down"):raise ValueError("Invalid sell crossing direction")
    first_cash=CAP*initial_btc_fraction
    first_units=max(0.0,first_cash-brokerage_fixed)*(1-fee)*(1-slippage if funding_weeks else 1)/float(s.iloc[start+1]) if first_cash>brokerage_fixed else 0.0
    if first_cash and first_cash<=brokerage_fixed:raise ValueError("Initial seed order below fixed brokerage")
    # Initial sell-tier size remains based on the hypothetical fully-invested starting BTC holding.
    initial_btc=max(0.0,CAP-brokerage_fixed)*(1-fee)/float(s.iloc[start+1])
    btc=first_units
    funding_cash=CAP*(1-initial_btc_fraction) if funding_weeks else 0.0
    cash=0.0 if funding_weeks else CAP*(1-initial_btc_fraction)
    if trade_callback is not None and first_cash>0:
        trade_callback({"side":"BUY","kind":"INITIAL","date":s.index[start+1],
                        "units":first_units,"cash":first_cash,"price":float(s.iloc[start+1]),"brokerage":brokerage_fixed})
    prev=None
    sell_armed=[True]*len(sell_levels)
    buy_armed=[True]*len(buy_levels)
    jobs=[]
    transactions=[]
    last_buy_fill_index=start+1
    buy_weeks=buy_weeks or weeks
    sell_weeks=sell_weeks or weeks
    ending=(len(s)-1) if end_index is None else int(end_index)
    if ending >= len(s) or ending < start+1:raise ValueError("Invalid end_index")
    for i in range(start+2,ending+1):
        j=i-1
        if not np.isfinite(ma.iloc[j]) or ma.iloc[j]<=0:continue
        ratio=100*(float(signal_price.iloc[j])/float(ma.iloc[j])-1)
        for k,t in enumerate(sell_levels):
            if (ratio<t if sell_cross_direction=="up" else ratio>t):sell_armed[k]=True
            crossed=(prev<t<=ratio if sell_cross_direction=="up" else prev>t>=ratio) if prev is not None else False
            if sell_armed[k] and crossed and not (block_overlap and any(z["side"]=="SELL" and z["tier"]==k for z in jobs)):
                jobs.append({"side":"SELL","tier":k,"threshold":t,"start":i,
                             "remaining":initial_btc/len(sell_levels),"weeks":sell_weeks,"weights":weights(shape,sell_weeks).tolist()})
                sell_armed[k]=False
        for k,t in enumerate(buy_levels):
            if ratio>t:buy_armed[k]=True
            if prev is not None and buy_armed[k] and prev>t>=ratio and cash>0 and not (block_overlap and any(z["side"]=="BUY" and z["tier"]==k for z in jobs)):
                # Reserve cash at trigger so overlapping buy jobs cannot double spend.
                allocation=cash/len(buy_levels)
                cash-=allocation
                jobs.append({"side":"BUY","tier":k,"threshold":t,"start":i,
                             "remaining":allocation,"weeks":buy_weeks,"weights":weights(shape,buy_weeks).tolist()})
                buy_armed[k]=False
        # The recycling decision is formed from the previous *completed*
        # weekly holdings and market close, with a next-close execution.
        previous_px=float(s.iloc[j])
        recycle_due=(cash_recycle_idle_weeks>0 and i>start+1+funding_weeks
            and i-last_buy_fill_index>=cash_recycle_idle_weeks
            and cash>brokerage_fixed+1e-8
            and cash/(cash+btc*previous_px)>cash_recycle_min_share
            and not any(z["side"]=="BUY" for z in jobs))
        px=float(s.iloc[i])
        if funding_weeks and i <= start+1+funding_weeks:
            funding_step=i-(start+2)
            remaining_funding_steps=funding_weeks-funding_step
            if funding_weighted:
                multiplier=(4.0 if ratio<=0 else 2.0 if ratio<=25 else 1.0 if ratio<=100 else 0.5 if ratio<=200 else 0.25)
            else:multiplier=1.0
            amount=funding_cash if remaining_funding_steps==1 else min(funding_cash,funding_cash/remaining_funding_steps*multiplier)
            if amount>brokerage_fixed+1e-8:
                acquired=(amount-brokerage_fixed)*(1-fee)*(1-slippage)/px
                btc+=acquired
                funding_cash-=amount
                last_buy_fill_index=i
                if trade_callback is not None:
                    trade_callback({"side":"BUY","kind":"FUNDING","date":s.index[i],
                                    "units":acquired,"cash":amount,"price":px,"brokerage":brokerage_fixed})
        remaining_jobs=[]
        for job in jobs:
            age=i-job["start"]
            duration=job["weeks"]
            w=job["weights"]
            if age>=duration:
                if job["side"]=="BUY":cash+=job["remaining"]
                continue
            if reverse_cancel and ((job["side"]=="SELL" and ((ratio<job["threshold"]) if sell_cross_direction=="up" else (ratio>job["threshold"]))) or
                                   (job["side"]=="BUY" and ratio>job["threshold"])):
                if job["side"]=="BUY":cash+=job["remaining"]
                continue
            # Normalize the remaining schedule to prevent stranded quantities.
            remaining_weight=sum(w[age:])
            requested=job["remaining"]*w[age]/remaining_weight
            if job["side"]=="SELL":
                # Protect an irrevocable core of the original fully-funded BTC-equivalent.
                # BTC gained through market rises does not automatically raise the core.
                available_to_sell=max(0.0,btc-initial_btc*btc_core_fraction)
                q=min(available_to_sell,requested)
                received=q*px*(1-fee)*(1-slippage)-brokerage_fixed
                if q>1e-10 and received>1e-8:
                    btc-=q;cash+=received
                    transactions.append({"week":str(s.index[i].date()),"side":"SELL","tier":job["tier"]+1,"btc":round(q,8)})
                    if trade_callback is not None:
                        trade_callback({"side":"SELL","kind":"TIER","date":s.index[i],
                                        "units":q,"cash":received,"price":px,"brokerage":brokerage_fixed})
                else:q=0.0
                job["remaining"]-=q
            else:
                spend=min(job["remaining"],requested)
                if spend>brokerage_fixed+1e-8:
                    acquired=(spend-brokerage_fixed)*(1-fee)*(1-slippage)/px
                    btc+=acquired
                    last_buy_fill_index=i
                    transactions.append({"week":str(s.index[i].date()),"side":"BUY","tier":job["tier"]+1,"usd":round(spend,2)})
                    if trade_callback is not None:
                        trade_callback({"side":"BUY","kind":"TIER","date":s.index[i],
                                        "units":acquired,"cash":spend,"price":px,"brokerage":brokerage_fixed})
                else:spend=0.0
                job["remaining"]-=spend
            if age<duration-1 and job["remaining"]>1e-8:remaining_jobs.append(job)
            elif job["side"]=="BUY":cash+=job["remaining"]
        jobs=remaining_jobs
        if recycle_due and not any(z["side"]=="BUY" for z in jobs):
            spend=cash*cash_recycle_fraction
            if spend>brokerage_fixed+1e-8:
                acquired=(spend-brokerage_fixed)*(1-fee)*(1-slippage)/px
                cash-=spend
                btc+=acquired
                last_buy_fill_index=i
                transactions.append({"week":str(s.index[i].date()),"side":"BUY","tier":0,"usd":round(spend,2)})
                if trade_callback is not None:
                    trade_callback({"side":"BUY","kind":"RECYCLE","date":s.index[i],
                                    "units":acquired,"cash":spend,"price":px,"brokerage":brokerage_fixed})
        prev=ratio
        if weekly_hook is not None:
            cash,btc=weekly_hook(i,s.index[i],px,cash,btc)
        if cash < -1e-6 or btc < -1e-9:raise AssertionError("Negative holdings")
    # Unspent committed buy cash is still an asset.
    cash+=sum(j["remaining"] for j in jobs if j["side"]=="BUY")
    final=float(s.iloc[ending])
    hold=CAP*(1-fee)*(1-slippage if funding_weeks else 1)/float(s.iloc[start+1])*final
    cash+=funding_cash
    value=cash+btc*final
    return {"value_usd":round(value,2),"vs_hold_pct":round(100*(value/hold-1),3),
            "btc_equivalent":round(value/final,8),"cash_usd":round(cash,2),"btc_held":round(btc,8),
            "transactions":len(transactions),"pending_jobs":len(jobs)}

def main():
    s,ma=load_completed_200wma_price_history()
    starts=[i for i in range(201,len(s)-1) if pd.Timestamp("2018-01-01",tz="UTC")<=s.index[i]<=pd.Timestamp("2024-12-31",tz="UTC")][::4]
    variants=[("immediate",None,None,None,None,None)]+[(f"{weeks}w_{shape}_cancel_{cancel}",shape,cancel,weeks,None,None) for weeks in (12,16) for shape in ("equal","front","back","bell") for cancel in (False,True)]+[(f"buy_{bw}w_sell_{sw}w_{shape}_cancel_{cancel}",shape,cancel,12,bw,sw) for bw,sw in ((12,16),(16,12)) for shape in ("equal","front","back","bell") for cancel in (False,True)]
    results={}
    for label,shape,cancel,weeks,buy_weeks,sell_weeks in variants:
        rows=[]
        for i in starts:
            r=simulate(s,ma,i) if shape is None else staged(s,ma,i,shape,cancel,weeks,buy_weeks,sell_weeks)
            rows.append({"start":str(s.index[i].date()),"vs_hold_pct":r["vs_hold_pct"]})
        vals=[x["vs_hold_pct"] for x in rows]
        results[label]={
            "starts":len(rows),"wins":sum(v>0 for v in vals),
            "median_pct":round(float(np.median(vals)),3),"worst_pct":round(min(vals),3),
            "rows":rows}
    out={"test":"12- and 16-week execution scheduling after 200WMA percentage-tier crossings",
         "start_policy":"2018+ only","fee":FEE,"results":results,
         "limitations":"All starts overlap and end at same date. No slippage, tax, AUD conversion or out-of-sample test. Staged sell jobs can overlap and are capped by actual BTC. Cancel uses last known signal."}
    p=Path("research_outputs/200wma_12week_execution.json")
    p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(out,indent=2,default=lambda x: x.item() if hasattr(x,"item") else str(x)))
    print(json.dumps({k:{x:v for x,v in z.items() if x!="rows"} for k,z in results.items()},indent=2,default=lambda x: x.item() if hasattr(x,"item") else str(x)))
if __name__=="__main__":main()
