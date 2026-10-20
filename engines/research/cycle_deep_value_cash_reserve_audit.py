"""Research ONLY: conditional reserve floors protecting AUD for deeper BTC discounts.

This is a sensitivity of an EXISTING BUY-side fresh-AUD paper research engine,
NOT a new Streamlit rule, portfolio purchase or broker/ASX quote. Cash may
remain unspent in 2027 without time limits. Only previous completed BTC/USD
daily close / previous exact 200WMA can affect hypothetical BUY size.

All model candidate parameters are frozen here *before this study's audit*,
but 2017/2021 have already been studied repeatedly: NOT unseen holdouts.
"""
from __future__ import annotations

import argparse
import csv
import json
import math
from pathlib import Path

import numpy as np
import pandas as pd

from engines.research.cycle_trade_allocation import calculate_allocation_signal
from engines.research.cycle_conditional_deep_value_buy_audit import (
    utcday, _allocation,
    BASELINE, FROZEN_CANDIDATES, FROZEN_HISTORY_CUTOFF,
    SHOCK_CASES, SHOCK_DROPS, SHOCK_FINAL_LEVELS, SHOCK_TROUGH_DAY,
)
from engines.research.day500_aftertax_reinvestment import (
    PRIMARY, SCORE_DAYS, fx_before, fetch_fx_for_cycle,
)
from engines.research.fresh_cash_200wma_matched_backtest import (
    BUDGET_AUD, FEE_AUD, START_DAYS, MIN_ORDER_AUD, _historical_wma,
)
from engines.research.live_weekly_buy_parity import TRADE_COOLDOWN_DAYS
from engines.research.smsf_self_financing_replay import AuditSmsfAccount
from engines.research.staged_dca_delayed_bottom_stress import delayed_bottom_path
from engines.research.top_signal_horse_race import read_exported_history

# The identical 2.5% Cycle baseline and unconditional prior-tiered study
# anchor the comparison. Floor is ORIGINAL cash, not marked-up portfolio.
# Locked cash is released only when prior BTC/USD closes at progressively
# lower ratios to 200WMA; it is never forced into BTC.
RESERVE_POLICIES={
    "actual_market_2p5_no_reserve": {
        "size":BASELINE,
        "floors":((1.00,0.00),)},
    "tiered_3p5_5p0_no_reserve": {
        "size":"tiered_3p5_at_10pct_and_5p0_at_20pct",
        "floors":((1.00,0.00),)},
    "tiered_hold_25pct_until_20pct_discount": {
        "size":"tiered_3p5_at_10pct_and_5p0_at_20pct",
        "floors":((.70,0.00),(.80,.10),(1.00,.25))},
    "tiered_hold_40pct_25pct_10pct": {
        "size":"tiered_3p5_at_10pct_and_5p0_at_20pct",
        "floors":((.70,0.00),(.80,.10),(.90,.25),(1.00,.40))},
    "tiered_hold_50pct_until_20pct_discount": {
        "size":"tiered_3p5_at_10pct_and_5p0_at_20pct",
        "floors":((.70,0.00),(.80,.25),(1.00,.50))},
}
REFERENCE="actual_market_2p5_no_reserve"
CHECKPOINT_PAPER_ONLY="NO_MANDATORY_BUY_IN_2026_OR_2027"
OUTPUT=Path("artifacts/research_cycle_200wma_cash_reserve")

def requested_fraction_and_reserve(policy:str, prior_close_over_wma:float,
                                  initial_cash:float,*,policy_map=None)->tuple[float,float]:
    """Exactly zero discretionary buying above WMA; no forward prices read."""
    policies=RESERVE_POLICIES if policy_map is None else policy_map
    if policy not in policies:
        raise ValueError("Unknown locked cash reserve candidate")
    if (not math.isfinite(float(prior_close_over_wma))
        or prior_close_over_wma<=0 or prior_close_over_wma>=1):
        raise ValueError("Only for eligible previous-close below-200WMA")
    if not math.isfinite(float(initial_cash)) or initial_cash<=0:
        raise ValueError("Invalid original AUD cash")
    plan=policies[policy]
    pct=_allocation(plan["size"],prior_close_over_wma)
    for threshold,floor in plan["floors"]:
        if prior_close_over_wma<=threshold:
            return pct,float(floor)*initial_cash
    raise AssertionError("Frozen reserve thresholds do not cover eligible BTC value")


def replay_reserves(prices:pd.Series,fx:pd.DataFrame,*,start,terminal,
                    capital_aud=BUDGET_AUD,policies=None,policy_map=None):
    began,end=utcday(start),utcday(terminal)
    if (not isinstance(prices,pd.Series) or not isinstance(prices.index,pd.DatetimeIndex)
        or prices.index.tz is None or not prices.index.is_monotonic_increasing
        or prices.index.has_duplicates or began not in prices.index
        or end not in prices.index or began>=end):
        raise ValueError("UTC observed start/end and unaltered ordered BTC series required")
    expected=pd.date_range(began-pd.Timedelta(days=1394),end,freq="D",tz="UTC")
    if not expected.isin(prices.index).all():
        raise ValueError("Exact pre-trade 200-week warmup history missing")
    values=prices.loc[expected].to_numpy(float)
    if not np.isfinite(values).all() or np.any(values<=0):
        raise ValueError("Nonfinite or missing BTC completed historical close")
    if (not isinstance(fx,pd.DataFrame) or not isinstance(fx.index,pd.DatetimeIndex)
        or fx.index.tz is None):
        raise ValueError("Verified timezone-aware prior AUD FX required")
    available=RESERVE_POLICIES if policy_map is None else policy_map
    if policies is None: policies=tuple(available)
    if (not math.isfinite(float(capital_aud)) or capital_aud<=MIN_ORDER_AUD
        or not policies or len(set(policies))!=len(policies)
        or any(k not in available for k in policies)):
        raise ValueError("Invalid original cash or reserve policies")
    accounts={p:AuditSmsfAccount(float(capital_aud),fee=FEE_AUD,tax=True) for p in policies}
    orders={p:[] for p in policies}
    last={p:None for p in policies}
    exposure={p:0.0 for p in policies}
    last_price=None
    market_watch_days=0
    count=0
    for day in pd.date_range(began+pd.Timedelta(days=1),end,freq="D",tz="UTC"):
        previous,wma=_historical_wma(prices,day)
        cheap=previous<wma
        signal=calculate_allocation_signal({
            "price_history":prices.loc[:day],
            "previous_close_usd":previous,
            "prior_200wma_usd":wma,
            "previous_close_below_200wma":cheap,
            "halving_day":9999,
        },buy_style="adaptive_recovery")
        if (cheap and (signal["signal"]!="BUY WATCH"
                       or signal["buy_pct_cash"]!=2.5)
            or not cheap and signal["signal"]=="BUY WATCH"):
            raise AssertionError("Shared original Cycle market gate changed")
        if cheap:market_watch_days+=1
        current=float(prices.loc[day])*fx_before(fx,day)
        last_price=current
        ratio=previous/wma
        for policy,account in accounts.items():
            due=last[policy] is None or (day-last[policy]).days>=TRADE_COOLDOWN_DAYS
            if cheap and due:
                fraction,protect=requested_fraction_and_reserve(
                    policy,ratio,capital_aud,policy_map=available)
                # Fixed minimum original AUD cash floor. Never borrow or
                # spend protected cash, even at threshold boundaries.
                gross=min(account.cash*fraction,
                          max(0.0,account.cash-protect))
                if gross>MIN_ORDER_AUD and gross>FEE_AUD*2:
                    if account.buy(day,current,gross/account.cash):
                        o=account.orders[-1]
                        if account.cash<protect-1e-6:
                            raise AssertionError("Paper account crossed cash reserve floor")
                        orders[policy].append({
                            "date":str(day.date()),
                            "prior_close_over_previous_200wma":round(ratio,6),
                            "advertised_conditional_pct_remaining_cash":round(100*fraction,4),
                            "actual_spent_pct_remaining_cash":round(100*gross/(account.cash+gross),4),
                            "protected_original_cash_AUD":round(protect,2),
                            "cash_after_AUD":round(account.cash,2),
                            "BTC_units_acquired":round(o["btc"],10),
                            "gross_AUD":round(o["gross_aud"],2),
                            "unchanged_live_market_buy_pct":signal["buy_pct_cash"],
                        })
                        last[policy]=day
            account.mark(current)
            equity=account.cash+account.btc*current
            if not math.isfinite(equity) or equity<=0:
                raise ArithmeticError("Invalid combined marked cash/BTC equity")
            exposure[policy]+=100*(account.btc*current)/equity
        count+=1
    result={}
    for policy,account in accounts.items():
        if any((utcday(a["date"])-utcday(b["date"])).days<TRADE_COOLDOWN_DAYS
               for a,b in zip(orders[policy][1:],orders[policy][:-1])):
            raise AssertionError("Current seven-day cooldown breached")
        result[policy]={
            "initial_cash_AUD":round(float(capital_aud),2),
            "cash_left_AUD":round(account.cash,2),
            "cash_left_pct_original":round(100*account.cash/capital_aud,4),
            "BTC_held":round(account.btc,8),
            "matched_current_market_BUY_WATCH_days":market_watch_days,
            "fills":len(orders[policy]),
            "marked_equity_AUD":round(account.cash+account.btc*last_price,2),
            "after_illustrative_FIFO_SMSF_liquidation_AUD":round(
                account.liquidation_value(end,last_price),2),
            "max_drawdown_pct":round(account.drawdown*100,4),
            "mean_daily_BTC_exposure_pct":round(exposure[policy]/count,4),
            "brokerage_AUD":round(account.total_fees,2),
            "orders":orders[policy],
        }
    return {
        "start":str(began.date()),
        "end":str(end.date()),
        "terminal_cash_sweep_or_forced_date":False,
        "candidate_cash_floors_of_initial_AUD_only":True,
        "last_btc_date_observed":str(end.date()),
        "independent_live_IBIT_execution_proven":False,
        "all_buy_decisions_use_previously_completed_market_data":True,
        "confirmed_user_portfolio_not_loaded":True,
        "accounts":result,
    }


def compare(replay,*,cycle:str,day:int,synthetic:bool=False,
            drop=None,recovery=None,completed:bool=False)->list[dict]:
    control=replay["accounts"][REFERENCE]
    rows=[]
    for policy,r in replay["accounts"].items():
        change=100*(r["after_illustrative_FIFO_SMSF_liquidation_AUD"]/
                    control["after_illustrative_FIFO_SMSF_liquidation_AUD"]-1)
        rows.append({
            "cycle":cycle,"halving_day_entry":int(day),"scenario_synthetic":synthetic,
            "forced_extra_btc_drop":drop,"forced_terminal_vs_before_shock":recovery,
            "is_completed_historical_cycle":completed,"policy":policy,
            "start":replay["start"],"last_observed_date":replay["end"],
            "terminal_AUD_illustrative_after_FIFO_CGT":
                r["after_illustrative_FIFO_SMSF_liquidation_AUD"],
            "vs_unmodified_live_2p5_total_AUD_pct":round(change,4),
            "AUD_cash_left_pct_of_original":r["cash_left_pct_original"],
            "AUD_cash_left":r["cash_left_AUD"],
            "BTC_held":r["BTC_held"],
            "max_drawdown_pct":r["max_drawdown_pct"],
            "mean_daily_BTC_exposure_pct":r["mean_daily_BTC_exposure_pct"],
            "trade_count":r["fills"],"paper_orders":r["orders"],
        })
    return rows


def audit(history,*,fx_fetcher=fetch_fx_for_cycle,policy_map=None):
    available=RESERVE_POLICIES if policy_map is None else policy_map
    px=history["price_usd"].dropna().sort_index().loc[:FROZEN_HISTORY_CUTOFF]
    real=[];stresses=[]
    for label,item in PRIMARY.items():
        halving=utcday(item["halving"])
        terminal=min(halving+pd.Timedelta(days=SCORE_DAYS),px.index[-1])
        fx=fx_fetcher(halving,terminal)
        for offset in START_DAYS:
            start=halving+pd.Timedelta(days=int(offset))
            if start>=terminal:continue
            run=replay_reserves(px,fx,start=start,terminal=terminal,policy_map=available)
            real.extend(compare(run,cycle=label,day=int(offset),
                                completed=terminal==halving+pd.Timedelta(days=SCORE_DAYS)))
        for label_stress,offset,shock_at in SHOCK_CASES:
            if label_stress!=label:continue
            if terminal!=halving+pd.Timedelta(days=SCORE_DAYS):
                raise ValueError("Synthetic stress requires completed historical parent")
            for decline in SHOCK_DROPS:
                for recovery in SHOCK_FINAL_LEVELS:
                    shocked=delayed_bottom_path(
                        px,halving,shock_start_day=shock_at,
                        loss_fraction=decline,terminal_price_fraction=recovery,
                        trough_day=SHOCK_TROUGH_DAY)
                    run=replay_reserves(shocked,fx,start=halving+pd.Timedelta(days=offset),
                                        terminal=terminal,policy_map=available)
                    stresses.extend(compare(
                        run,cycle=label,day=offset,synthetic=True,
                        drop=decline,recovery=recovery,completed=True))
    if not real or not stresses:
        raise AssertionError("Real and adverse cohort tests must be populated")
    return {
        "kind":"RESEARCH_ONLY_200WMA_CASH_RESERVE_FLOORS_DEEPER_BUY_STRESS",
        "user_deployment_deadline":"FLEXIBLE_THROUGH_2027_NO_MANDATORY_BUY",
        "fixed_sizing_and_original_AUD_reserve_policies":available,
        "price_cutoff_UTC":str(FROZEN_HISTORY_CUTOFF.date()),
        "cash_control_original_2p5_market_and_7day_ledger_parity_required":True,
        "different_cohort_dates_in_same_cycle_are_not_independent_cycles":True,
        "historical_cycles_previously_seen_not_unseen_proof":True,
        "fresh_AUD_only_not_actual_user_portfolio":True,
        "illustrative_SMSF_accumulation_tax_not_user_tax":True,
        "ASX_IBIT_not_actually_available_in_2017_or_2021":True,
        "no_verifiable_executable_prices_for_BTC_weekends":True,
        "no_fixed_future_buy_or_automatic_model_promotion":True,
        "no_live_BUY_SELL_Streamlit_ntfy_changes":True,
        "market_outperformance_established":False,
        "historical":real,"synthetic_extended_bear":stresses,
    }


def main(argv=None):
    p=argparse.ArgumentParser(description="Paper-only BTC 200WMA reserves stress test")
    p.add_argument("--out",type=Path,default=OUTPUT)
    args=p.parse_args(argv)
    result=audit(read_exported_history())
    args.out.mkdir(parents=True,exist_ok=True)
    (args.out/"audit.json").write_text(json.dumps(result,indent=2,sort_keys=True)+"\n")
    for name,key in (("historical.csv","historical"),
                     ("synthetic.csv","synthetic_extended_bear")):
        rows=result[key]
        with (args.out/name).open("w",newline="") as f:
            fields=[k for k in rows[0] if k!="paper_orders"]
            w=csv.DictWriter(f,fieldnames=fields)
            w.writeheader()
            for row in rows:w.writerow({k:v for k,v in row.items() if k in fields})
    for group in ("historical","synthetic_extended_bear"):
        for r in result[group]:
            if r["policy"]==REFERENCE:continue
            print(json.dumps({
                "cycle":r["cycle"],"group":group,
                "policy":r["policy"],"start_day":r["halving_day_entry"],
                "terminal_vs_current_2p5_AUD_pct":r["vs_unmodified_live_2p5_total_AUD_pct"],
                "cash_left_pct":r["AUD_cash_left_pct_of_original"],
                "drawdown_pct":r["max_drawdown_pct"],
                "BTC_held":r["BTC_held"],
                "shock_pct":r["forced_extra_btc_drop"],
                "recovery_frac":r["forced_terminal_vs_before_shock"],
                "proven_alpha":False,
            },sort_keys=True))
    print("PAPER RESEARCH ONLY, NO TRADING/PORTFOLIO/MESSAGES")


if __name__=="__main__":
    main()
