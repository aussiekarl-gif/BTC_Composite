"""Read-only hybrid 2026 BTC DCA: evergreen base plus causal deep-drawdown reserve.

Fixed, predeclared research candidates:
  * Core: either 25% or 50% of the SAME initial AUD 500k, bought as 12
    equal AUD orders from the initial observed January weekly price.
  * Reserve: the remaining 75% or 50% stays cash until a prior-week
    close is >=40% below the trailing 52-week AUD price high; *then*
    it follows existing flexible risk-scaled dynamic DCA opportunities.
  * Cash/BTC never borrow between sleeves, so the model is self-financing.
    Per-sleeve FIFO taxable lots and AUD 3/order fees are counted.
    Keeping sleeves separate is a conservative simplification because
    cross-sleeve SMSF losses/discounts would in reality share one fund.
  * The 12 weeks constrain only a modest CORE fallback. There is **no
    fixed duration** on reserve buying or exit decisions.

All live decisions use prior-week price/risk. Hindsight low enters only
post-execution scoring. Historical score vintage still unverified.
This model is NOT the user's actual 2026 My Portfolio transactions.
"""
from __future__ import annotations

import argparse
import json
import math

import numpy as np
import pandas as pd

from engines.research.adaptive_dca_execution import simulate_adaptive
from engines.research.full_cycle_reinvestment import CAPITAL, validate_history
from engines.research.real_2026_deployment_audit import (
    _start_index, benchmark_account,
)
from engines.research.smsf_self_financing_replay import AuditSmsfAccount, sizing
from engines.research.verified_recent_price_bridge import (
    append_verified_prices, asof_on_mondays, expanding_aud_powerlaw_risk,
    fetch_public_series, first_causal_gate_week,
    weighted_entry_from_synthetic_orders,
)

BASE_CORE_FRACTIONS = (0.25, 0.50)
FIXED_GATE_DRAWDOWN = 0.40
BASELINE_CORE_WEEKS = 12
TRANSFER_YEARS = (2019, 2020, 2021, 2022, 2023, 2024, 2025)


def hybrid_account(history, start_date, *, core_fraction=.25,
                   gate_drawdown=FIXED_GATE_DRAWDOWN, base_weeks=BASELINE_CORE_WEEKS,
                   starting_cash=CAPITAL, historical_fx=None):
    """Simulate two segregated sleeves without borrowing or any future-look trades."""
    h = validate_history(history)
    if not 0 < core_fraction < 1:
        raise ValueError("core_fraction must lie strictly between 0 and 1")
    if not 0 < gate_drawdown < 1:
        raise ValueError("Invalid drawdown activation threshold")
    if not isinstance(base_weeks, int) or base_weeks <= 0:
        raise ValueError("Invalid fixed baseline schedule")
    if not math.isfinite(starting_cash) or starting_cash <= 0:
        raise ValueError("Invalid initial AUD capital")
    first=_start_index(h,start_date)
    gate,prior_drop=first_causal_gate_week(
        h,drawdown=gate_drawdown,start_date=start_date)
    core_budget=float(starting_cash)*core_fraction
    reserve_budget=float(starting_cash)-core_budget
    core=AuditSmsfAccount(core_budget,tax=True)
    reserve=AuditSmsfAccount(reserve_budget,tax=True)
    prices=h["btc_price_aud"].to_numpy(dtype=float)
    risk=h["risk_score"].to_numpy(dtype=float)
    # Read ahead to discover dates only in the *research simulator*;
    # simulate_adaptive is already prefix-invariant and uses previous
    # completed week's signal to place its own trade at the next close.
    opportunities={}
    if gate is not None:
        proposed=simulate_adaptive(
            h,confirm_drawdown=.10,initial_cash=reserve_budget,
            deployment_start=gate,fee_aud=3.0)
        opportunities={event["date"]:event for event in proposed["trades"]}
        if any(pd.Timestamp(k)<gate for k in opportunities):
            raise AssertionError("Reserve traded before observed causal gate")
    highest=float(starting_cash)
    worst_dd=0.
    core_tranche=core_budget/base_weeks
    combined_curve=[]
    for j in range(first,len(h)):
        now=h.index[j]
        price=float(prices[j])
        if j-first<base_weeks and core.cash>0:
            gross=core.cash if j-first==base_weeks-1 else min(core.cash,core_tranche)
            core.buy(now,price,gross/core.cash)
        event=opportunities.get(str(now))
        if event is not None:
            frac=sizing("adaptive",event,prices,risk,j)
            if event["side"]=="BUY":
                reserve.buy(now,price,frac)
            elif event["side"]=="SELL":
                reserve.sell(now,price,frac)
            else:
                raise ValueError("Unsupported reserved allocation direction")
        # Each ledger independently remains self-financing, and total
        # account drawdown is measured from the COMBINED weekly equity.
        a=core.mark(price)
        b=reserve.mark(price)
        equity=a+b
        highest=max(highest,equity)
        worst_dd=min(worst_dd,equity/highest-1)
        combined_curve.append(equity)
        if core.cash<-1e-7 or reserve.cash<-1e-7 or core.btc<-1e-9 or reserve.btc<-1e-9:
            raise ArithmeticError("Negative holdings in self-financing hybrid")

    orders=sorted([dict(o) for o in core.orders+reserve.orders],
                  key=lambda x:x["date"])
    terminal_price=float(prices[-1])
    combined_cash=core.cash+reserve.cash
    combined_btc=core.btc+reserve.btc
    marked=combined_cash+combined_btc*terminal_price
    after_liquidation=(
        core.liquidation_value(h.index[-1],terminal_price)
        +reserve.liquidation_value(h.index[-1],terminal_price))
    result={
        "model":f"core_{int(core_fraction*100)}pct_reserve_{int((1-core_fraction)*100)}pct",
        "requested_deployment_date":str(pd.Timestamp(start_date).date()),
        "initial_AUD_cash":float(starting_cash),
        "baseline_core_pct":round(100*core_fraction,2),
        "core_aud_at_start":round(core_budget,2),
        "reserve_aud_at_start":round(reserve_budget,2),
        "baseline_core_weeks":base_weeks,
        "deep_drawdown_gate_pct":round(100*gate_drawdown,2),
        "gate_triggered":gate is not None,
        "gate_date":str(gate) if gate is not None else None,
        "gate_observed_prior_week_drawdown_pct":(
            round(100*prior_drop,3) if prior_drop is not None else None),
        "last_observed_date":str(h.index[-1]),
        "orders":len(orders),
        "core_buy_orders":sum(x["side"]=="BUY" for x in core.orders),
        "reserve_buy_orders":sum(x["side"]=="BUY" for x in reserve.orders),
        "reserve_sell_orders":sum(x["side"]=="SELL" for x in reserve.orders),
        "BTC_held":round(combined_btc,8),
        "AUD_cash_left":round(combined_cash,2),
        "marked_value_aud":round(marked,2),
        "hypothetical_after_liquidation_cgt_aud":round(after_liquidation,2),
        "cgt_realised_withheld_est_aud":round(core.total_tax+reserve.total_tax,2),
        "brokerage_aud":round(core.total_fees+reserve.total_fees,2),
        "max_combined_drawdown_pct":round(100*worst_dd,2),
        "first_order_date":orders[0]["date"] if orders else None,
        "last_order_date":orders[-1]["date"] if orders else None,
        "cash_deployed_to_buy_orders_pct":round(
            100*sum(o["gross_aud"] for o in orders if o["side"]=="BUY")/starting_cash,3),
    }
    if historical_fx is not None:
        result["buying_error_vs_user_reported_low"] = (
            weighted_entry_from_synthetic_orders(orders,historical_fx,
                                                  starting_capital=starting_cash))
    return result


def historical_transfer(history, *, start_years=TRANSFER_YEARS,
                        starting_cash=CAPITAL):
    """Same Jan-start date and ~52-week horizon for every tested era."""
    h=validate_history(history)
    rows=[]
    for year in start_years:
        start=f"{year}-01-01"
        end=pd.Timestamp(start,tz="UTC")+pd.Timedelta(weeks=52)
        truncated=h.loc[h.index<end]
        if len(truncated)<104 or truncated.index[-1]<end-pd.Timedelta(weeks=2):
            continue
        matched=benchmark_account(truncated,start,"immediate_buy",
                                  initial_cash=starting_cash)
        equal=benchmark_account(truncated,start,"equal_12week_buy",
                                initial_cash=starting_cash)
        candidates=[
            hybrid_account(truncated,start,core_fraction=f,
                           starting_cash=starting_cash)
            for f in BASE_CORE_FRACTIONS
        ]
        for p in candidates:
            p["relative_to_immediate_hold_pct"]=round(
                100*(p["marked_value_aud"]/matched["account_marked_value_aud"]-1),3)
            p["relative_to_equal_12week_pct"]=round(
                100*(p["marked_value_aud"]/equal["account_marked_value_aud"]-1),3)
        rows.append({
            "cohort_start":start,
            "end":str(truncated.index[-1]),
            "immediate_hold_aud":matched["account_marked_value_aud"],
            "equal_12week_aud":equal["account_marked_value_aud"],
            "hybrid_candidates":candidates,
        })
    summary=[]
    for fraction in BASE_CORE_FRACTIONS:
        sample=[next(p for p in r["hybrid_candidates"]
                     if p["baseline_core_pct"]==fraction*100)
                for r in rows]
        summary.append({
            "core_pct":100*fraction,
            "reserve_pct":100*(1-fraction),
            "cohorts":len(sample),
            "gate_triggered":sum(x["gate_triggered"] for x in sample),
            "beat_hold":sum(x["relative_to_immediate_hold_pct"]>0 for x in sample),
            "beat_equal_dca":sum(x["relative_to_equal_12week_pct"]>0 for x in sample),
            "median_vs_hold_pct":round(float(np.median(
                [x["relative_to_immediate_hold_pct"] for x in sample])),3)
                if sample else None,
            "median_vs_equal_dca_pct":round(float(np.median(
                [x["relative_to_equal_12week_pct"] for x in sample])),3)
                if sample else None,
        })
    return {"by_year":rows,"summary":summary,
            "in_sample_historical_transfer_only":True}


def evaluate_from_verified_providers(master, *, asof="2026-10-16"):
    raw=validate_history(master)
    btc_usd, aud_fx=fetch_public_series(asof=asof)
    public=asof_on_mondays(
        btc_usd,aud_fx,start=raw.index[-1]-pd.Timedelta(weeks=10),end=asof)
    combined,price_check=append_verified_prices(raw,public,asof=asof)
    causal_price_only=expanding_aud_powerlaw_risk(combined).dropna(subset=["risk_score"])
    start="2026-01-01"
    cohorts=[
        hybrid_account(causal_price_only,start,core_fraction=f,
                       historical_fx=aud_fx)
        for f in BASE_CORE_FRACTIONS
    ]
    hold=benchmark_account(causal_price_only,start,"immediate_buy")
    equal=benchmark_account(causal_price_only,start,"equal_12week_buy")
    for c in cohorts:
        c["relative_to_immediate_hold_pct"]=round(
            100*(c["marked_value_aud"]/hold["account_marked_value_aud"]-1),3)
        c["relative_to_equal_12week_pct"]=round(
            100*(c["marked_value_aud"]/equal["account_marked_value_aud"]-1),3)
    transfer=historical_transfer(causal_price_only)
    return {
        "research_only":True,
        "asof":asof,
        "last_observed_week":str(causal_price_only.index[-1]),
        "actual_user_portfolio_read":False,
        "real_user_cash_deployment_start_year":2026,
        "starting_aud_capital":CAPITAL,
        "reference_low_usd":57717.,
        "price_bridge_quality":price_check,
        "in_sample_2026_hybrids":cohorts,
        "same_start_2026_controls":{
            "immediate_buy_hold_aud":hold["account_marked_value_aud"],
            "equal_12week_dca_aud":equal["account_marked_value_aud"]},
        "fixed_one_year_historical_robustness":transfer,
        "warnings":[
            "Core 12-week schedule is fixed; reserve's adaptive execution window is not fixed.",
            "Previous-week gate is causal, but parameters and periods were proposed after historical inspection; NOT untouched out-of-sample.",
            "Two independent sleeves are self-financing but CGT losses are NOT offset across their tax ledgers; combined SMSF annual liability may differ.",
            "Same-week baseline and reserve buy orders incur two AUD 3 fees, a conservative separate-order assumption.",
            "Risk scores are independently constructed strict-prior AUD Power Law, NOT the archival validated composite and NOT Production.",
            "Reported USD 57,717 June 30 low is USER PROVIDED; not certified by daily price API as an intraday low.",
            "Buying error excludes undeployed cash; deployment rate and BTC held are disclosed.",
            "Weekly closes assumed executable; no ETF tracking spread/management fee, pension tax exemption, or cash yield.",
            "No real My Portfolio positions or user Google Sheets data imported, modified or used.",
            "Do not promote either allocation to Production based on selected retrospective history.",
        ],
    }


def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--asof",default="2026-10-16")
    ap.add_argument("--output",default="")
    args=ap.parse_args()
    from engines.shared.central_data import load_master
    raw=load_master(columns=["btc_price_aud","risk_score"])
    numeric=raw[["btc_price_aud","risk_score"]].apply(
        pd.to_numeric,errors="coerce")
    valid=(numeric["btc_price_aud"].gt(0)
           &numeric["risk_score"].between(0,1))
    result=evaluate_from_verified_providers(numeric.loc[valid],asof=args.asof)
    result["master_valid_weekly_pairs"]=int(valid.sum())
    output=json.dumps(result,indent=2,allow_nan=False,
                      default=lambda x:x.item() if isinstance(x,np.generic) else str(x))
    if args.output:
        from pathlib import Path
        Path(args.output).write_text(output+"\n",encoding="utf-8")
    print(output)


if __name__=="__main__":
    main()
