"""Research-only: causal 200-week MA entry, no sells, vs buy-and-hold.

Weekly signal uses ONLY prior 200 observed weekly closes, executes next week.
Same starting cash and 0.1% buy fee. Never optimize thresholds on the test set.
"""
import json
from pathlib import Path
import pandas as pd
import numpy as np

def simulate(prices, threshold=1.0, deadline_weeks=None, initial=500000., fee=.001):
    cash=initial; btc=0.; buys=0; first_buy=None
    ma=prices.shift(1).rolling(200,min_periods=200).mean()
    for i in range(1,len(prices)):
        if i<201: continue
        # Signal from preceding week; fill at this week's close.
        ratio=float(prices.iloc[i-1]/ma.iloc[i-1])
        if not np.isfinite(ratio): continue
        due=deadline_weeks is not None and i>=201+deadline_weeks
        if cash>0 and (ratio<=threshold or due):
            btc+=cash*(1-fee)/float(prices.iloc[i])
            cash=0.;buys+=1;first_buy=str(prices.index[i].date())
    return {"ending_equity":round(cash+btc*float(prices.iloc[-1]),2),
            "btc":round(btc,6),"cash":round(cash,2),"first_buy":first_buy,"buys":buys}

def main():
    data=pd.read_csv("data/price_200_week_moving_average_200wma__2026-10-07T21-20-24.csv")
    data["date"]=pd.to_datetime(data["timestamp"],unit="ms",utc=True)
    price=pd.to_numeric(data["Price"],errors="coerce")
    s=pd.Series(price.to_numpy(),index=data["date"]).sort_index().resample("W-MON").last().dropna()
    s=s.loc["2013-01-01":"2026-10-05"]
    # Fair benchmark starts when the 200-week lookback becomes available.
    start=201
    if len(s)<start+100:raise ValueError("Too few weeks")
    hold_btc=500000*(1-.001)/float(s.iloc[start])
    baseline={"ending_equity":round(hold_btc*float(s.iloc[-1]),2),"btc":round(hold_btc,6)}
    results={"currency":"USD","source":"BlockHorizon historical BTC/USD price CSV",
             "warning":"Not AUD. 200WMA signals lagged; start after 200 weeks; no CGT/slippage beyond fee.",
             "start":str(s.index[start].date()),"end":str(s.index[-1].date()),"observations":len(s),
             "buy_hold":baseline,"strategies":{}}
    for threshold in [.85,1.0,1.10,1.25,1.50]:
        for deadline in [None,26,52,104]:
            key=f"{threshold:.2f}x_200wma_deadline_{deadline if deadline is not None else 'none'}"
            results["strategies"][key]=simulate(s,threshold,deadline)
    path=Path("research_outputs/200wma_entry_usd.json")
    path.parent.mkdir(exist_ok=True,parents=True)
    path.write_text(json.dumps(results,indent=2))
    print(json.dumps(results,indent=2))

if __name__=="__main__":main()
