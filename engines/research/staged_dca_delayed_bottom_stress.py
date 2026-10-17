"""Research-only downside scenarios for the staged BTC SELL -> REBUY policy.

Synthetic counterfactuals splice a predeclared BTC bear-market shock AFTER an
actual historical day 780 or 900. Observations before the shock remain EXACT.
Every strategy observes ONLY completed prior-day prices, as implemented in
staged_tax_aware_roundtrip. An artificial future low is NEVER a trade input.

Every comparison is internally matched: same historical AUD500k initial
BTC, same dated USD/AUD exchange rates, staged historical SELL policy,
brokerage, simplified FIFO SMSF tax, date window, and price shock.

Synthetic price paths are NOT actual BTC forecasts, probability estimates or
untouched out-of-sample history. They test failure risk and cash exhaustion.
"""
from __future__ import annotations

import argparse
import json
import math
from pathlib import Path

import numpy as np
import pandas as pd

from engines.research.day500_aftertax_reinvestment import (
    SCORE_DAYS,PRIMARY,fetch_fx_for_cycle,
)
from engines.research.staged_tax_aware_roundtrip import (
    replay_roundtrip,BUYERS,SELLERS,BUY_START_DAY,
)
from engines.research.top_signal_horse_race import read_exported_history

# Freeze scenario design before reporting data-derived results.
SHOCK_START_DAYS=(780,900)
TROUGH_DAY=1060
SHOCK_LOSS_FRACTIONS=(.50,.70)
TERMINAL_FRACTIONS_OF_PRE_SHOCK_PRICE=(.55,1.05)
COMPLETED_CYCLES=("2017","2021")
INITIAL_CAPITAL_AUD=500_000.0


def delayed_bottom_path(prices, halving, *, shock_start_day,
                        loss_fraction, terminal_price_fraction,
                        trough_day=TROUGH_DAY, terminal_day=SCORE_DAYS):
    """Retain everything through shock start; geometric fall, then recovery.

    Parameters are fixed scenario definitions, not calibrated to any future
    observed bottom. Synthetic closes use smooth positive geometric changes
    to eliminate discontinuous one-day zero-price paths.
    """
    if not isinstance(prices,pd.Series) or not isinstance(prices.index,pd.DatetimeIndex):
        raise ValueError("Need BTC/USD daily series")
    if prices.index.tz is None or prices.index.has_duplicates or not prices.index.is_monotonic_increasing:
        raise ValueError("Need ordered unique UTC prices")
    if not (BUY_START_DAY<shock_start_day<trough_day<terminal_day):
        raise ValueError("Shock dates must follow BUY start and precede terminal")
    if not 0<loss_fraction<1 or not 0<terminal_price_fraction<=2:
        raise ValueError("Invalid shock depth or terminal recovery fraction")
    h=pd.Timestamp(halving)
    h=h.tz_localize("UTC") if h.tzinfo is None else h.tz_convert("UTC")
    shock_date=h+pd.Timedelta(days=shock_start_day)
    low_date=h+pd.Timedelta(days=trough_day)
    final_date=h+pd.Timedelta(days=terminal_day)
    required=pd.date_range(shock_date,final_date,freq="D",tz="UTC")
    if not required.isin(prices.index).all():
        raise ValueError("Missing required historical observations for shock")
    old=prices.loc[:final_date].copy()
    pivot=float(old.loc[shock_date])
    if not math.isfinite(pivot) or pivot<=0:
        raise ValueError("Bad historical shock anchor")
    low=pivot*(1-loss_fraction)
    target=pivot*terminal_price_fraction

    # Dates 0..shock_date match the historical original exactly.
    decline=pd.date_range(shock_date+pd.Timedelta(days=1),low_date,freq="D",tz="UTC")
    for t in decline:
        span=(t-shock_date).days/(low_date-shock_date).days
        old.loc[t]=pivot*math.exp(math.log(low/pivot)*span)
    recovery=pd.date_range(low_date+pd.Timedelta(days=1),final_date,freq="D",tz="UTC")
    for t in recovery:
        span=(t-low_date).days/(final_date-low_date).days
        old.loc[t]=low*math.exp(math.log(target/low)*span)
    if not (old.loc[:shock_date]==prices.loc[:shock_date]).all():
        raise AssertionError("Scenario changed historical past")
    if (not np.isfinite(old.to_numpy(float)).all()
            or not old.gt(0).all()):
        raise ArithmeticError("Invalid stressed prices")
    return old


def _execution_metrics(rec,*,shock_date,low_date):
    sold_net=float(rec["net_sell_cash_after_tax_aud"])
    buys=rec["buybacks"]
    spent_pre_shock=sum(float(x["gross_aud"]) for x in buys
                        if pd.Timestamp(x["date"],tz="UTC")<=shock_date)
    spent_pre_low=sum(float(x["gross_aud"]) for x in buys
                      if pd.Timestamp(x["date"],tz="UTC")<low_date)
    return {
        "original_sale_proceeds_aud":rec["net_sell_cash_after_tax_aud"],
        "total_reinvested_pct":rec["net_sale_proceeds_reinvested_pct"],
        "spent_before_shock_pct_of_net_sales":round(100*spent_pre_shock/sold_net,2)
            if sold_net>0 else None,
        "spent_before_forced_low_pct_of_net_sales":round(100*spent_pre_low/sold_net,2)
            if sold_net>0 else None,
        "btc_actually_held":rec["btc_remaining"],
        "terminal_btc_equiv_including_cash":rec["terminal_btc_equiv_including_cash"],
        "cash_remaining_aud":rec["cash_remaining_aud"],
        "buy_vwap_error_pct":rec["buy_error_above_observed_bottom_pct"],
        "buy_fills":rec["buy_fills"],
        "terminal_after_liquidation_aud":rec["account_after_hypothetical_liquidation_cgt_aud"],
        "aftertax_vs_hold_pct":rec["liquidated_aud_vs_hold_pct"],
        "account_max_drawdown_pct":rec["account_max_marked_drawdown_pct"],
        "trade_ledger":rec["orders"],
    }


def evaluate_stress(prices, *, fx_fetcher=fetch_fx_for_cycle,
                    cycles=COMPLETED_CYCLES, sellers=SELLERS,
                    starts=SHOCK_START_DAYS,
                    losses=SHOCK_LOSS_FRACTIONS,
                    recoveries=TERMINAL_FRACTIONS_OF_PRE_SHOCK_PRICE):
    """Same shock and sell orders in both BUY accounts; compare actual AUD.

    All historical FX observations are held at their actual dated values,
    making the *BTC* price trajectory the only counterfactual input.
    """
    scenarios=[]
    for label in cycles:
        if label not in PRIMARY or label=="2025":
            raise ValueError("Only historically completed cycles permitted")
        h=pd.Timestamp(PRIMARY[label]["halving"],tz="UTC")
        end=h+pd.Timedelta(days=SCORE_DAYS)
        if end not in prices.index:
            raise ValueError("A completed cycle is required")
        fx=fx_fetcher(h,end)
        for start_day in starts:
            for loss in losses:
                for recovery in recoveries:
                    stress=delayed_bottom_path(
                        prices,h,shock_start_day=start_day,
                        loss_fraction=loss,terminal_price_fraction=recovery)
                    shock_date=h+pd.Timedelta(days=start_day)
                    low_date=h+pd.Timedelta(days=TROUGH_DAY)
                    # The forced low may not equal the lowest *full* entry
                    # window price. Report this independently; never force
                    # a non-observed hindsight scoring trough.
                    observed_low=stress.loc[
                        h+pd.Timedelta(days=BUY_START_DAY):end].idxmin()
                    path_id=(f"{label}-shock{start_day}-loss{int(loss*100)}"
                             f"-terminal{int(recovery*100)}")
                    for seller in sellers:
                        accounts={}
                        for buyer in BUYERS:
                            rec=replay_roundtrip(
                                stress,fx,h,end,seller=seller,buyer=buyer)
                            accounts[buyer]=rec
                        default=accounts[BUYERS[0]]
                        challenger=accounts[BUYERS[1]]
                        # HOLD/SELL must be consistent across buyers.
                        if (default["sales"]!=challenger["sales"] or
                                default["original_btc"]!=challenger["original_btc"]):
                            raise AssertionError("Not comparing identical SELL legs")
                        d=default["account_after_hypothetical_liquidation_cgt_aud"]
                        c=challenger["account_after_hypothetical_liquidation_cgt_aud"]
                        if d<=0 or c<=0:
                            raise ArithmeticError("Non-positive after-tax values")
                        delta=100*(c/d-1)
                        scenarios.append({
                            "scenario":path_id,"cycle":label,
                            "seller":seller,
                            "shock_start_day":int(start_day),
                            "trough_day":TROUGH_DAY,
                            "loss_from_shock_price_pct":round(loss*100,2),
                            "terminal_fraction_of_shock_price_pct":round(recovery*100,2),
                            "shock_start_usd":round(float(stress.loc[shock_date]),2),
                            "forced_trough_usd":round(float(stress.loc[low_date]),2),
                            "terminal_usd":round(float(stress.loc[end]),2),
                            "forced_trough_is_observed_window_low":bool(observed_low==low_date),
                            "realized_low_date_in_buy_window":str(observed_low.date()),
                            "staged_aftertax_advantage_over_existing_pct":round(delta,2),
                            "staged_worse_than_existing":bool(delta<0),
                            "existing":_execution_metrics(default,shock_date=shock_date,low_date=low_date),
                            "staged":_execution_metrics(challenger,shock_date=shock_date,low_date=low_date),
                        })
    aggregates={}
    for label in cycles:
        for seller in sellers:
            subset=[s for s in scenarios if s["cycle"]==label and s["seller"]==seller]
            if not subset:continue
            worst=min(subset,key=lambda x:x["staged_aftertax_advantage_over_existing_pct"])
            best=max(subset,key=lambda x:x["staged_aftertax_advantage_over_existing_pct"])
            aggregates[label+" | "+seller]={
                "scenario_count":len(subset),
                "staged_worse_than_existing_count":sum(x["staged_worse_than_existing"] for x in subset),
                "worst_staged_vs_existing_pct":worst["staged_aftertax_advantage_over_existing_pct"],
                "worst_scenario":worst["scenario"],
                "best_staged_vs_existing_pct":best["staged_aftertax_advantage_over_existing_pct"],
                "best_scenario":best["scenario"],
                "max_staged_pre_trough_spent_pct_net_sale_proceeds":max(
                    x["staged"]["spent_before_forced_low_pct_of_net_sales"] for x in subset),
                "min_staged_aftertax_vs_hold_pct":min(
                    x["staged"]["aftertax_vs_hold_pct"] for x in subset),
                "max_staged_buy_vwap_error_pct":max(
                    x["staged"]["buy_vwap_error_pct"] for x in subset
                    if x["staged"]["buy_vwap_error_pct"] is not None),
                "max_existing_buy_vwap_error_pct":max(
                    x["existing"]["buy_vwap_error_pct"] for x in subset
                    if x["existing"]["buy_vwap_error_pct"] is not None) if any(
                        x["existing"]["buy_vwap_error_pct"] is not None for x in subset) else None,
                "all_scenarios_forced_trough_is_low":all(
                    x["forced_trough_is_observed_window_low"] for x in subset),
            }
    return {
        "study":"Research only: predeclared delayed BTC bear-bottom counterfactuals",
        "historical_cycles":list(cycles),
        "synthetic_not_historical":True,
        "late_low_day":TROUGH_DAY,
        "aftertax_stress_summary":aggregates,
        "scenario_results":scenarios,
        "caveats":[
            "Counterfactual BTC closes after each shock date are intentionally fabricated, not observed outcomes or forecasts.",
            "Original pre-shock prices and same-date historical AUD FX are retained; real AUD FX might react to an actual BTC market shock.",
            "Same staged historical SELL schedule and hypothetical starting A$500k BTC at the historical halving.",
            "Staged BUY remains Research only; no changes to Streamlit, Production, Research V5.9, ntfy or real holdings.",
            "Post-tax amounts use simplified FIFO 10/15% immediate SMSF CGT, not actual annual SMSF/pension/ETF taxation.",
            "Daily-close execution and static AUD 3 transaction fees are optimistic; real slippage/tracking/ETF spreads differ.",
            "Start, low depth and recovery selected as stress cases, not assigned probabilities; frequency of success/failure is NOT win rate.",
            "Past-timing policies were historically inspected; these experiments are robustness diagnostics, not prospective validation.",
        ],
    }


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--output",type=Path)
    args=parser.parse_args()
    source=read_exported_history()["price_usd"].dropna().sort_index()
    result=evaluate_stress(source)
    for key,values in result["aftertax_stress_summary"].items():
        print(json.dumps({"key":key,**values},sort_keys=True))
    if args.output:
        args.output.parent.mkdir(parents=True,exist_ok=True)
        args.output.write_text(json.dumps(result,indent=2))
        print("Full stress scenarios and trade ledgers saved:",args.output)


if __name__=="__main__":
    main()
