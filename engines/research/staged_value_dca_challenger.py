"""Research-only, predeclared staged DCA-in challenger.

This is NOT the live Cycle Trading/ntfy/portfolio rule. Every candidate signal
uses strictly PRIOR completed BTC daily observations; simulated BTC is bought
on the next observed daily close at the same weekly decision cadence as the
current 2.5%-of-remaining-cash rule.

The 20%/25% VWAP-above-bottom bands are SCORECARD TARGETS, never algorithm
inputs. Actual bottoms are known ONLY when scoring the completed window.
No retroactive buys, holdings imported from SMSF, broker fills or trades.
All capital and costs here are USD-denominated HYPOTHETICAL controls to avoid
fabricating dated AUD FX; this is not a tax-adjusted AUD portfolio backtest.
Do not reuse headline BTC outcomes as proof of live strategy profitability.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import math
from pathlib import Path

import numpy as np
import pandas as pd

from engines.research.cycle_trade_allocation import calculate_allocation_signal
from engines.research.cycle_trading_dashboard_model import build_dashboard_market
from engines.research.top_signal_horse_race import read_exported_history

START_DAY=620
FINAL_DAY=1150
DEPLOYMENT_USD=500_000.0
FEE_USD_PER_FILL=3.0
MIN_TRADE_USD=100.0
MIN_RESERVE_FRACTION=0.02
CYCLE_HALVINGS={
    "2017":pd.Timestamp("2016-07-09",tz="UTC"),
    "2021":pd.Timestamp("2020-05-11",tz="UTC"),
    "2025":pd.Timestamp("2024-04-20",tz="UTC"),
}


def candidate_buy_signal(market):
    """Fixed research tiers; no knowledge of future trough/return.

    A below-200WMA gate has priority. Earlier, small tranches are possible
    only at substantial drawdowns; above-gate recovery requires a 50DMA
    improvement based entirely on dated prices through yesterday.
    """
    p=market["price_history"]
    if not isinstance(p,pd.Series) or len(p)<367:
        raise ValueError("Need 365 fully observed prior closes")
    prior=pd.to_numeric(p.iloc[:-1],errors="coerce")
    if len(prior)<365 or not prior.iloc[-365:].gt(0).all():
        raise ValueError("Invalid 365-day observations")
    prev=float(prior.iloc[-1])
    wma=float(market["prior_200wma_usd"])
    if not math.isfinite(prev) or not math.isfinite(wma) or wma<=0:
        raise ValueError("Invalid BTC price or 200WMA")
    ratio=prev/wma
    high365=float(prior.iloc[-365:].max())
    drawdown=max(0.0,1.0-prev/high365)
    mean50=float(prior.iloc[-50:].mean())
    old_mean50=float(prior.iloc[-64:-14].mean())
    recovering=prev>mean50 and mean50>old_mean50
    pct=0.0
    zone="no qualifying accumulation setup"
    if ratio<=.85:
        pct,zone=20.0,"deep value: <=0.85x prior 200WMA"
    elif ratio<1.0:
        pct,zone=14.0,"value: below prior 200WMA"
    elif ratio<=1.10 and drawdown>=.25 and recovering:
        pct,zone=10.0,"confirmed recovery within 1.10x 200WMA"
    elif ratio<=1.10 and drawdown>=.35:
        pct,zone=5.0,"early severe drawdown within 1.10x 200WMA"
    elif ratio<=1.20 and drawdown>=.25 and recovering:
        pct,zone=8.0,"confirmed recovery within 1.20x 200WMA"
    elif ratio<=1.20 and drawdown>=.35:
        pct,zone=4.0,"early severe drawdown within 1.20x 200WMA"
    elif ratio<=1.30 and drawdown>=.25 and recovering:
        pct,zone=5.0,"confirmed recovery within 1.30x 200WMA"
    elif ratio<=1.30 and drawdown>=.35:
        pct,zone=3.0,"early severe drawdown within 1.30x 200WMA"

    return {
        "buy_pct_cash":pct,
        "signal":"BUY WATCH" if pct>0 else "HOLD",
        "zone":zone,
        "prior_price_over_200wma":round(ratio,4),
        "prior_drawdown_365_pct":round(drawdown*100,2),
        "prior_recovery_confirmed":bool(recovering),
        "research_only":True,
    }


def simulate_cash_cohort(prices, *, halving, policy, start_day=START_DAY,
                         final_day=FINAL_DAY, deployment=DEPLOYMENT_USD,
                         fee=FEE_USD_PER_FILL, asof=None):
    """Fair cash-funded side-by-side: common date, price, capital, fee, cadence.

    Both strategies receive the SAME USD 500k of fresh shadow cash on day620,
    with ZERO prior holdings, and trade once every 7 calendar days at most.
    An observed day's close is an optimistic fill proxy, NOT guaranteed real
    execution. Date-T signal uses prices strictly through T-1.
    """
    if policy not in ("current_2p5pct","staged_value_recovery"):
        raise ValueError("Unknown buy research policy")
    if (not isinstance(prices,pd.Series) or
            not isinstance(prices.index,pd.DatetimeIndex) or
            prices.index.tz is None):
        raise ValueError("Provide sorted UTC daily BTC/USD series")
    if not (prices.index.is_monotonic_increasing and prices.index.is_unique):
        raise ValueError("BTC timestamps must be unique and ascending")
    if not np.isfinite(float(deployment)) or deployment<=0 or fee<0:
        raise ValueError("Bad initial capital or fee")
    halving=pd.Timestamp(halving)
    halving=halving.tz_localize("UTC") if halving.tzinfo is None else halving.tz_convert("UTC")
    entry=halving+pd.Timedelta(days=start_day)
    end=halving+pd.Timedelta(days=final_day)
    if asof is not None:
        limit=pd.Timestamp(asof)
        limit=limit.tz_localize("UTC") if limit.tzinfo is None else limit.tz_convert("UTC")
        end=min(end,limit.normalize())
    end=min(end,prices.index.max())
    if end<entry:
        raise ValueError("Observation ends before entry cohort starts")

    cash=float(deployment)
    btc=0.0
    spent=0.0
    buys=[]
    times=pd.date_range(entry,end,freq="7D",tz="UTC")
    for when in times:
        if when not in prices.index:
            raise ValueError(f"Missing executable BTC daily price: {when}")
        prior=prices.loc[:when]
        # Cross-check same strict historical data as live, rather than
        # approximating 200WMA with a conventional unshifted rolling average.
        market=build_dashboard_market(
            prior,pd.DataFrame(),asof=str(when.date()),
            confirmed_halving_date=str(halving.date())
            if halving>=pd.Timestamp("2024-04-20",tz="UTC") else None)
        market["halving_day"]=int((when-halving).days)
        market["halving_date"]=str(halving.date())
        signal=(calculate_allocation_signal(market)["buy_pct_cash"]
                if policy=="current_2p5pct" else
                candidate_buy_signal(market)["buy_pct_cash"])
        if signal<=0:
            continue
        # Reserve a small amount for fees / contingencies; no forced buy
        # on last day and no retroactive deposits.
        reserve=deployment*MIN_RESERVE_FRACTION
        proposed=cash*(signal/100.0)
        gross=min(proposed,max(0,cash-reserve))
        if gross<max(MIN_TRADE_USD,fee+1):
            continue
        px=float(prices.loc[when])
        if not math.isfinite(px) or px<=0:
            raise ValueError("Invalid execution-day BTC price")
        qty=(gross-fee)/px
        if qty<=0:
            continue
        btc+=qty
        cash-=gross
        spent+=gross
        buys.append({"date":str(when.date()),"btc_price_usd":round(px,2),
                     "buy_pct_remaining_cash":round(signal,2),
                     "gross_usd":round(gross,2),
                     "btc_units":qty})
    window=prices.loc[entry:end]
    if window.empty:
        raise ValueError("No observed entry period")
    trough=float(window.min())
    terminal=float(window.iloc[-1])
    # Cost-weighted execution VWAP uses full-precision cash, not rounded
    # presentation rows, preventing a tiny numerical audit discrepancy.
    vwap=((spent-fee*len(buys))/btc) if btc else None
    btc_equiv=btc+cash/terminal
    bh_price=float(prices.loc[entry])
    buy_hold=(deployment-fee)/bh_price
    completed=bool(end>=halving+pd.Timedelta(days=final_day))
    target25=bool(vwap is not None and vwap<=1.25*trough and spent>=.5*deployment)
    target20=bool(vwap is not None and vwap<=1.20*trough and spent>=.5*deployment)
    return {
        "policy":policy,"window_start":str(entry.date()),
        "window_end":str(end.date()),"complete_window":completed,
        "buy_count":len(buys),
        "cash_deployed_pct":round(100*spent/deployment,2),
        "cash_left_usd":round(cash,2),
        "btc_units":round(btc,8),
        "terminal_btc_equivalent_including_cash":round(btc_equiv,8),
        "buy_hold_btc_units":round(buy_hold,8),
        "terminal_btc_eq_vs_buy_hold_pct":round(100*(btc_equiv/buy_hold-1),2),
        "observed_window_low_usd":round(trough,2),
        "vwap_usd":round(vwap,2) if vwap is not None else None,
        "vwap_error_above_observed_low_pct":round(100*(vwap/trough-1),2) if vwap else None,
        # Only completed windows can earn the historical target verdict.
        # The 2025/26 window is RIGHT-CENSORED: a lower future trough may
        # change both bottom and execution-price error substantially.
        "meets_25pct_target_with_50pct_deployment":target25 if completed else None,
        "meets_20pct_stretch_with_50pct_deployment":target20 if completed else None,
        "provisional_below_25pct_error_with_50pct_deployment":target25 if not completed else None,
        "provisional_below_20pct_error_with_50pct_deployment":target20 if not completed else None,
        "first_buy":buys[0]["date"] if buys else None,
        "last_buy":buys[-1]["date"] if buys else None,
        "trades":buys,
    }


def evaluate_saved_history(prices):
    """Research comparison. Excludes 2013, labels unfinished 2025 as censored."""
    data={}
    for label,halving in CYCLE_HALVINGS.items():
        cohort={}
        for policy in ("current_2p5pct","staged_value_recovery"):
            cohort[policy]=simulate_cash_cohort(
                prices,halving=halving,policy=policy)
        data[label]=cohort
    return {
        "study":"Frozen research staged DCA-in challenger",
        "asof":str(prices.index.max().date()),
        "benchmark":"same fresh USD 500,000 cash at halving+620; buy-and-hold BTC acquired day620",
        "eligible_cycles":data,
        "targets":{"central_vwap_error_pct":25,"stretch_vwap_error_pct":20,
                   "minimum_cash_deployed_pct":50},
        "caveats":[
            "This tests accumulation from fresh USD cash, NOT existing BTC plus sales.",
            "No SMSF CGT, ETF spread/fees/FX, or actual portfolio holdings modeled.",
            "2017 and 2021 are historically inspected; 2025 still right-censored.",
            "Only 2 historical completed modern observations; NOT out-of-sample validation.",
            "End-of-day execution price is an optimistic proxy, not guaranteed a fill.",
            "Buy-and-hold comparator starts at identical cohort date and capital.",
            "Best VWAP without sufficient deployment is explicitly not considered success.",
            "No modified live Streamlit, Production, Research 5.9, ntfy or sheets.",
        ],
    }


def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--output",type=Path)
    args=ap.parse_args()
    raw=read_exported_history()["price_usd"]
    prices=raw.dropna().sort_index()
    result=evaluate_saved_history(prices)
    # Keep stdout concise for GitHub Actions logs; full trade ledger in artifact.
    for label,group in result["eligible_cycles"].items():
        for policy,rec in group.items():
            print(json.dumps({
                "cycle":label,"policy":policy,
                "window":rec["window_start"]+".."+rec["window_end"],
                "complete":rec["complete_window"],
                "fills":rec["buy_count"],"deployed_pct":rec["cash_deployed_pct"],
                "vwap_usd":rec["vwap_usd"],"error_pct":rec["vwap_error_above_observed_low_pct"],
                "btc_units":rec["btc_units"],
                "terminal_btc_equiv":rec["terminal_btc_equivalent_including_cash"],
                "vs_buy_hold_pct":rec["terminal_btc_eq_vs_buy_hold_pct"],
                "meets_25":rec["meets_25pct_target_with_50pct_deployment"],
                "meets_20":rec["meets_20pct_stretch_with_50pct_deployment"],
                "provisional_under_25":rec["provisional_below_25pct_error_with_50pct_deployment"],
            },sort_keys=True))
    if args.output:
        args.output.parent.mkdir(parents=True,exist_ok=True)
        args.output.write_text(json.dumps(result,indent=2,default=str))
        print("Full trades written to:",args.output)


if __name__=="__main__":
    main()
