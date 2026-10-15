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

def staged(s,ma,start,shape="equal",reverse_cancel=False,weeks=12,buy_weeks=None,sell_weeks=None):
    btc=CAP*(1-FEE)/float(s.iloc[start+1])
    initial_btc=btc
    cash=0.
    prev=None
    sell_armed=[True]*10
    buy_armed=[True]*10
    jobs=[]
    transactions=[]
    buy_weeks=buy_weeks or weeks
    sell_weeks=sell_weeks or weeks
    for i in range(start+2,len(s)):
        j=i-1
        if not np.isfinite(ma.iloc[j]) or ma.iloc[j]<=0:continue
        ratio=100*(float(s.iloc[j])/float(ma.iloc[j])-1)
        for k,t in enumerate(SELLS):
            if ratio<t:sell_armed[k]=True
            if prev is not None and sell_armed[k] and prev<t<=ratio:
                jobs.append({"side":"SELL","tier":k,"threshold":t,"start":i,
                             "remaining":initial_btc/10,"weeks":sell_weeks,"weights":weights(shape,sell_weeks).tolist()})
                sell_armed[k]=False
        for k,t in enumerate(BUYS):
            if ratio>t:buy_armed[k]=True
            if prev is not None and buy_armed[k] and prev>t>=ratio and cash>0:
                # Reserve cash at trigger so overlapping buy jobs cannot double spend.
                allocation=cash/10
                cash-=allocation
                jobs.append({"side":"BUY","tier":k,"threshold":t,"start":i,
                             "remaining":allocation,"weeks":buy_weeks,"weights":weights(shape,buy_weeks).tolist()})
                buy_armed[k]=False
        px=float(s.iloc[i])
        remaining_jobs=[]
        for job in jobs:
            age=i-job["start"]
            duration=job["weeks"]
            w=job["weights"]
            if age>=duration:
                if job["side"]=="BUY":cash+=job["remaining"]
                continue
            if reverse_cancel and ((job["side"]=="SELL" and ratio<job["threshold"]) or
                                   (job["side"]=="BUY" and ratio>job["threshold"])):
                if job["side"]=="BUY":cash+=job["remaining"]
                continue
            # Normalize the remaining schedule to prevent stranded quantities.
            remaining_weight=sum(w[age:])
            requested=job["remaining"]*w[age]/remaining_weight
            if job["side"]=="SELL":
                q=min(btc,requested)
                if q>1e-10:
                    btc-=q;cash+=q*px*(1-FEE)
                    transactions.append({"week":str(s.index[i].date()),"side":"SELL","tier":job["tier"]+1,"btc":round(q,8)})
                job["remaining"]-=q
            else:
                spend=min(job["remaining"],requested)
                if spend>1e-8:
                    btc+=spend*(1-FEE)/px
                    transactions.append({"week":str(s.index[i].date()),"side":"BUY","tier":job["tier"]+1,"usd":round(spend,2)})
                job["remaining"]-=spend
            if age<duration-1 and job["remaining"]>1e-8:remaining_jobs.append(job)
            elif job["side"]=="BUY":cash+=job["remaining"]
        jobs=remaining_jobs
        prev=ratio
        if cash < -1e-6 or btc < -1e-9:raise AssertionError("Negative holdings")
    # Unspent committed buy cash is still an asset.
    cash+=sum(j["remaining"] for j in jobs if j["side"]=="BUY")
    final=float(s.iloc[-1])
    hold=CAP*(1-FEE)/float(s.iloc[start+1])*final
    value=cash+btc*final
    return {"value_usd":round(value,2),"vs_hold_pct":round(100*(value/hold-1),3),
            "btc_equivalent":round(value/final,8),"cash_usd":round(cash,2),
            "transactions":len(transactions),"pending_jobs":len(jobs)}

def main():
    d=pd.read_csv("data/price_200_week_moving_average_200wma__2026-10-07T21-20-24.csv")
    d["date"]=pd.to_datetime(d["timestamp"],unit="ms",utc=True)
    s=pd.Series(pd.to_numeric(d["Price"],errors="coerce").to_numpy(),index=d["date"]).sort_index().resample("W-MON").last().dropna()
    ma=s.shift(1).rolling(200,min_periods=200).mean()
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
