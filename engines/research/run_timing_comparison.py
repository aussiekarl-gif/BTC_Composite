#!/usr/bin/env python3
"""Research-only, same-window BTC entry-timing comparison.

Compares fixed DCA, buy-and-hold, and risk-triggered accumulation without selling.
All strategies use the same valid observations and AUD budget. This is a diagnostic,
not a promise of future returns; risk scores must be point-in-time.
"""
from __future__ import annotations
import json, sys
from pathlib import Path
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
from engines.shared.central_data import load_master

CAPITAL = 500_000.0
FEE = 0.001

def summary(name, data, allocations, cash):
    prices = data["btc_price_aud"].to_numpy(float)
    spent = float(np.sum(allocations))
    fees = spent * FEE
    btc = float(np.sum(np.divide(allocations * (1-FEE), prices, out=np.zeros_like(prices), where=prices>0)))
    final_price = float(prices[-1])
    return {"strategy":name, "starting_capital_aud":CAPITAL, "cash_remaining_aud":float(cash),
            "gross_spent_aud":spent, "fees_aud":fees, "btc_held":btc,
            "ending_equity_aud":float(cash + btc*final_price),
            "return_pct":float((cash+btc*final_price)/CAPITAL*100-100),
            "btc_equivalent_if_all_in_at_start":float(CAPITAL*(1-FEE)/prices[0]),
            "btc_accumulation_vs_fixed_dca_pct":None}

def main():
    raw = load_master(columns=["btc_price_aud", "risk_score"])
    raw["btc_price_aud"] = pd.to_numeric(raw["btc_price_aud"], errors="coerce")
    raw["risk_score"] = pd.to_numeric(raw["risk_score"], errors="coerce")
    data = raw[np.isfinite(raw["btc_price_aud"]) & (raw["btc_price_aud"]>0) &
               np.isfinite(raw["risk_score"]) & raw["risk_score"].between(0,1)].sort_index()
    if len(data)<20: raise RuntimeError(f"Only {len(data)} valid price/risk rows")
    p = data["btc_price_aud"].to_numpy(float)
    risk = data["risk_score"].to_numpy(float)
    n = len(data)
    rows=[]
    # Same dates and final mark for all strategies.
    alloc=np.full(n, CAPITAL/n)
    rows.append(summary("fixed_DCA_equal_installment_each_valid_observation",data,alloc,CAPITAL-float(alloc.sum())))
    rows.append(summary("buy_and_hold_at_first_valid_observation",data,np.r_[CAPITAL,np.zeros(n-1)],0.0))
    for threshold in (0.15,0.25,0.35,0.45,0.55):
        eligible = risk < threshold
        # Allocate equal portions of the budget over qualifying observations; this
        # deliberately removes cash-budget exhaustion as a confounder.
        a=np.zeros(n)
        if eligible.any(): a[eligible]=CAPITAL/int(eligible.sum())
        rows.append(summary(f"risk_DCA_threshold_{threshold:.2f}",data,a,CAPITAL-float(a.sum())))
    # Capped, opportunistic accumulation with unspent cash retained.
    for threshold in (0.15,0.25,0.35,0.45):
        a=np.zeros(n); cash=CAPITAL
        for i,r in enumerate(risk):
            if r < threshold and cash>0:
                strength=(threshold-r)/threshold
                spend=min(cash,CAPITAL*0.02*strength)
                if spend>=100: a[i]=spend; cash-=spend
        rows.append(summary(f"capped_risk_accumulation_{threshold:.2f}",data,a,cash))
    out=pd.DataFrame(rows)
    fixed=float(out.loc[out.strategy=="fixed_DCA_equal_installment_each_valid_observation","btc_held"].iloc[0])
    out["btc_accumulation_vs_fixed_dca_pct"]=(out["btc_held"]/fixed-1)*100
    result={"dataset":{"rows":int(n),"start":str(data.index.min()),"end":str(data.index.max()),
                       "price_start_aud":float(p[0]),"price_end_aud":float(p[-1]),
                       "risk_score_min":float(risk.min()),"risk_score_max":float(risk.max()),
                       "capital_aud":CAPITAL,"fee_per_side_pct":FEE*100},
            "results":out.replace({np.nan:None}).to_dict(orient="records"),
            "caveats":["Risk-score publication timestamps and upstream lookahead have not yet been independently audited.",
                       "Equal-installment DCA is over valid risk-score observations, not necessarily every calendar week.",
                       "Fees included; spread, slippage, tax and terminal liquidation costs excluded.",
                       "Threshold strategies are descriptive comparisons, not selected or validated trading rules."]}
    print("BTC TIMING COMPARISON")
    print(json.dumps(result,indent=2,allow_nan=False,default=str))
if __name__=="__main__": main()
