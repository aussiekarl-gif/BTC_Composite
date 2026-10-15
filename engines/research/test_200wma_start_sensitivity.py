"""Four-week rolling entry dates, exact same-end buy-hold, original 200WMA tiers.

Research only. This tests entry-date sensitivity, NOT independent cycles.
The trade rules are imported unchanged from the prior tier-ladder study.
"""
import json
from pathlib import Path
import numpy as np
import pandas as pd
from engines.research.test_200wma_tier_ladders import simulate, LADDERS, CAP, FEE

def main():
    d=pd.read_csv("data/price_200_week_moving_average_200wma__2026-10-07T21-20-24.csv")
    d["date"]=pd.to_datetime(d["timestamp"],unit="ms",utc=True)
    s=pd.Series(pd.to_numeric(d["Price"],errors="coerce").to_numpy(),index=d["date"]).sort_index().resample("W-MON").last().dropna()
    ma=s.shift(1).rolling(200,min_periods=200).mean()
    eligible=[i for i in range(201,len(s)-1) if s.index[i]>=pd.Timestamp("2010-01-01",tz="UTC") and s.index[i]<=pd.Timestamp("2024-12-31",tz="UTC")]
    starts=eligible[::4]
    rows=[]
    for start in starts:
        hold_btc=CAP*(1-FEE)/float(s.iloc[start+1])
        hold_usd=hold_btc*float(s.iloc[-1])
        strategy=simulate(s,ma,start,LADDERS["original"],0.)
        strategy_btc_equiv=strategy["ending_usd"]/float(s.iloc[-1])
        rows.append({"start":str(s.index[start].date()),"year":int(s.index[start].year),
                     "hold_usd":round(hold_usd,2),"hold_btc":round(hold_btc,8),
                     "strategy_usd":strategy["ending_usd"],
                     "strategy_btc_equiv":round(strategy_btc_equiv,8),
                     "strategy_btc_held":strategy["btc"],
                     "strategy_cash_usd":strategy["cash_usd"],
                     "relative_pct":round(100*(strategy["ending_usd"]/hold_usd-1),3),
                     "sells":strategy["sell_trades"],"buys":strategy["buy_trades"]})
    by_year={}
    for year in sorted(set(r["year"] for r in rows)):
        values=[r["relative_pct"] for r in rows if r["year"]==year]
        by_year[str(year)]={"starts":len(values),"wins":sum(v>0 for v in values),
                            "median_pct":round(float(np.median(values)),2),
                            "worst_pct":round(min(values),2),
                            "best_pct":round(max(values),2)}
    output={"method":"Four-week rolling starts; identical last-week mark-to-market; original 9 sell tiers / 5 buy tiers",
            "currency":"USD","initial_usd":CAP,"fee":FEE,"start_count":len(rows),
            "wins":sum(r["relative_pct"]>0 for r in rows),
            "median_pct":round(float(np.median([r["relative_pct"] for r in rows])),2),
            "worst_pct":min(r["relative_pct"] for r in rows),
            "best_pct":max(r["relative_pct"] for r in rows),
            "by_start_year":by_year,"rows":rows,
            "limitations":"Overlapping entry cohorts, all share 2026 exit. Original model is not exact proposed 10x10. Historical thresholds not out-of-sample."}
    p=Path("research_outputs/200wma_start_sensitivity.json")
    p.parent.mkdir(parents=True,exist_ok=True)
    p.write_text(json.dumps(output,indent=2))
    print(json.dumps({k:v for k,v in output.items() if k!="rows"},indent=2))
if __name__=="__main__":main()
