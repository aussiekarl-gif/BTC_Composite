"""Matched-entry, cash-funded 200WMA BUY research (not SELL/rebuy).

Freeze the exact new forward-policy mechanics from #125 against:
  - current simplified DAILY 2.5% of REMAINING CASH below prior 200WMA,
  - equal-budget fixed weekly 52-week DCA, price-independent,
  - immediate lump sum on the first possible day.

All accounts begin in AUD CASH on the same user-like historical start
date; NO fictitious purchases at a prior halving and NO backdated SELLs.
Historic 2017/2021 full observation windows and 2025/26 right-censored.
Uses strictly previous-day BTC/USD for allocation decisions, prior dated
USD/AUD spot FX, AUD3 per fill and hypothetical FIFO SMSF liquidation tax.
Closes are optimistic proxies for executable BTC/IBIT prices. Tests must
show that changing future prices cannot change earlier executed trades.
"""
from __future__ import annotations

import argparse
import json
import math
from pathlib import Path

import numpy as np
import pandas as pd

from engines.research.day500_aftertax_reinvestment import (
    PRIMARY,SCORE_DAYS,fetch_fx_for_cycle,fx_before,
)
from engines.research.shared_cycle_policy import recovery_buy_budget_fraction
from engines.research.smsf_self_financing_replay import AuditSmsfAccount
from engines.research.top_signal_horse_race import read_exported_history

POLICIES=(
    "forward_original_budget_weekly",
    "current_2p5_remaining_cash_daily",
    "fixed_52_week_equal_cash",
    "immediate_lump_sum",
)
START_DAYS=(650,750,850,900)
BUDGET_AUD=400_000.
FEE_AUD=3.
MIN_ORDER_AUD=100.
FIXED_DCA_WEEKS=52


def _utc(value):
    x=pd.Timestamp(value)
    return x.tz_localize("UTC") if x.tzinfo is None else x.tz_convert("UTC")


def _historical_wma(price,day):
    """Strictly lagged index-exact weekly close lookup without per-day joins."""
    if day not in price.index:
        raise ValueError("Review day missing from dated BTC history")
    pos=price.index.get_loc(day)
    offsets=pos-1-7*np.arange(200)
    if offsets.min()<0:
        raise ValueError("Insufficient prior 200-week BTC history")
    observed=price.index.take(offsets)
    expected=pd.DatetimeIndex([
        day-pd.Timedelta(days=1+7*i) for i in range(200)])
    if not observed.equals(expected):
        raise ValueError("200 exact prior weekly closes unavailable")
    values=price.to_numpy(dtype=float)
    previous=float(values[pos-1])
    mean=float(values[offsets].mean())
    if (not math.isfinite(previous) or not math.isfinite(mean)
            or previous<=0 or mean<=0):
        raise ValueError("Invalid prior BTC close or WMA")
    return previous,mean


def matched_fresh_cash_replay(price,fx,*,start,terminal,policy,
                              budget_aud=BUDGET_AUD,fee_aud=FEE_AUD,
                              min_order_aud=MIN_ORDER_AUD):
    """A purely chronological cash-only BUY replay from a fixed start.

    A single fresh-cash subaccount has no prior BTC and therefore does
    not run a halving-day500 SELL strategy. Cash cannot be recycled from
    nonexistent historical profits. All portfolios spend at T close
    only after T-1 observations; no sale decisions are simulated.
    """
    if policy not in POLICIES:raise ValueError("Unknown fresh cash BUY policy")
    start=_utc(start).normalize()
    end=_utc(terminal).normalize()
    if not (isinstance(price,pd.Series)
            and isinstance(price.index,pd.DatetimeIndex)
            and price.index.tz is not None
            and price.index.is_unique and price.index.is_monotonic_increasing):
        raise ValueError("Ordered unique timezone-aware BTC history required")
    if start>=end or start not in price.index or end not in price.index:
        raise ValueError("Start and terminal must be observed and ordered")
    warmup=start-pd.Timedelta(days=1394)
    required=pd.date_range(warmup,end,freq="D",tz="UTC")
    if not required.isin(price.index).all():
        raise ValueError("Missing continuous BTC history for causal 200WMA and fills")
    if (not math.isfinite(float(budget_aud)) or float(budget_aud)<=100
            or not math.isfinite(float(fee_aud)) or float(fee_aud)<0
            or not math.isfinite(float(min_order_aud)) or float(min_order_aud)<=fee_aud):
        raise ValueError("Invalid initial cash or brokerage bounds")
    acct=AuditSmsfAccount(float(budget_aud),fee=float(fee_aud),tax=True)
    initial=acct.cash
    active=None
    executed=[]
    eligible_days=0
    bought_usd=0.
    for day in pd.date_range(start+pd.Timedelta(days=1),end,freq="D",tz="UTC"):
        prev,ma=_historical_wma(price,day)
        eligible=prev<ma
        if eligible:eligible_days+=1
        if active is None and policy=="forward_original_budget_weekly" and eligible:
            active=day
        gross=0.
        pct_original=None
        if policy=="forward_original_budget_weekly":
            if active is not None and (day-active).days%7==0:
                frac=recovery_buy_budget_fraction(
                    price.loc[:day],day,style="adaptive_recovery")[
                        "fraction_of_initial_buyback_cash"]
                pct_original=frac*100
                gross=min(acct.cash,initial*frac)
        elif policy=="current_2p5_remaining_cash_daily":
            if eligible:
                gross=acct.cash*.025
        elif policy=="fixed_52_week_equal_cash":
            # The weekly schedule starts the first day AFTER the start date.
            # If terminal is earlier than 52 weeks, remaining cash stays cash.
            weeks=(day-(start+pd.Timedelta(days=1))).days//7
            if (day-start).days<=7*(FIXED_DCA_WEEKS-1)+1 and (day-start).days%7==1:
                gross=min(acct.cash,initial/FIXED_DCA_WEEKS)
        else:
            if day==start+pd.Timedelta(days=1):
                gross=acct.cash
        if gross>min_order_aud and gross>fee_aud*2:
            spot_usd=float(price.loc[day])
            aud_rate=fx_before(fx,day)
            spot_aud=spot_usd*aud_rate
            if acct.buy(day,spot_aud,min(1.,gross/acct.cash)):
                order=acct.orders[-1]
                bought_usd+=float(order["gross_aud"])/aud_rate
                executed.append({
                    "date":str(day.date()),
                    "gross_aud":round(float(order["gross_aud"]),2),
                    "btc":round(float(order["btc"]),10),
                    "spot_usd":spot_usd,
                    "aud_per_usd":aud_rate,
                    "pct_original_budget":(round(pct_original,2)
                                           if pct_original is not None else None),
                })
        acct.mark(float(price.loc[day])*fx_before(fx,day))
    end_usd=float(price.loc[end])
    end_aud=end_usd*fx_before(fx,end)
    lowest=float(price.loc[start+pd.Timedelta(days=1):end].min())
    qty=sum(x["btc"] for x in executed)
    # Use exact acct orders for weighted average; displayed fills can be
    # rounded without shifting the official reference VWAP.
    ordered_qty=sum(float(o["btc"]) for o in acct.orders if o["side"]=="BUY")
    avg_usd=(bought_usd/ordered_qty if ordered_qty>0 else None)
    spent=sum(x["gross_aud"] for x in executed)
    equity=acct.cash+acct.btc*end_aud
    return {
        "policy":policy,
        "start_date":str(start.date()),"terminal_date":str(end.date()),
        "initial_cash_aud":float(initial),"no_legacy_sell_or_historical_btc":True,
        "first_valid_200wma_activation_date":str(active.date()) if active is not None else None,
        "eligible_below_200wma_daily_closes":eligible_days,
        "fill_count":len(executed),
        "btc_purchased_and_held":round(acct.btc,8),
        "cash_left_aud":round(acct.cash,2),
        "cash_spent_ex_fees_aud":round(spent,2),
        "cash_left_pct":round(100*acct.cash/initial,2),
        "marked_terminal_aud":round(equity,2),
        "after_hypothetical_liquidation_cgt_aud":round(
            acct.liquidation_value(end,end_aud),2),
        "terminal_btc_equivalent_including_cash":round(
            acct.btc+acct.cash/end_aud,8),
        "average_buy_usd_vwap":round(avg_usd,2) if avg_usd is not None else None,
        "average_buy_error_above_observed_future_low_pct":(
            round(100*(avg_usd/lowest-1),2) if avg_usd is not None else None),
        "observed_post_start_low_usd":round(lowest,2),
        "terminal_btc_usd":round(end_usd,2),
        "estimated_selling_cgt_if_liquidated_aud":round(
            max(0.,equity-acct.liquidation_value(end,end_aud)),2),
        "fee_total_aud":round(acct.total_fees,2),
        "execution_day_close_proxy_only":True,
        "orders":executed,
    }


def evaluate_fresh_cash_matched_starts(
        history,*,fx_fetcher=fetch_fx_for_cycle,
        start_days=START_DAYS,cycles=("2017","2021","2025"),
        budget_aud=BUDGET_AUD):
    source=history["price_usd"].dropna().sort_index()
    cutoff=pd.Timestamp("2026-10-05",tz="UTC")
    price=source.loc[:cutoff]
    scenarios=[]
    for label in cycles:
        if label not in PRIMARY:raise ValueError("Unknown inspected cycle")
        h=pd.Timestamp(PRIMARY[label]["halving"],tz="UTC")
        end=min(h+pd.Timedelta(days=SCORE_DAYS),price.index[-1])
        if end not in price.index:raise ValueError("No dated cohort terminal")
        fx=fx_fetcher(h,end)
        for day in start_days:
            start=h+pd.Timedelta(days=int(day))
            if start>=end:continue
            variants={
                name:matched_fresh_cash_replay(
                    price,fx,start=start,terminal=end,policy=name,
                    budget_aud=budget_aud)
                for name in POLICIES
            }
            reference=variants["immediate_lump_sum"][
                "after_hypothetical_liquidation_cgt_aud"]
            if reference<=0:raise ArithmeticError("Invalid benchmark")
            comparisons={}
            for key,obj in variants.items():
                val=obj["after_hypothetical_liquidation_cgt_aud"]
                comparisons[key]={
                    **{field:obj[field] for field in (
                        "fill_count","first_valid_200wma_activation_date",
                        "eligible_below_200wma_daily_closes",
                        "btc_purchased_and_held","cash_left_aud",
                        "cash_left_pct","marked_terminal_aud",
                        "after_hypothetical_liquidation_cgt_aud",
                        "average_buy_usd_vwap",
                        "average_buy_error_above_observed_future_low_pct",
                        "terminal_btc_equivalent_including_cash",
                        "fee_total_aud")},
                    "aftertax_aud_vs_immediate_lump_pct":round(
                        100*(val/reference-1),2),
                }
            forward=comparisons["forward_original_budget_weekly"]
            live=comparisons["current_2p5_remaining_cash_daily"]
            result={
                "cycle":label,"start_day_from_halving":int(day),
                "start_date":str(start.date()),"terminal":str(end.date()),
                "complete_score_window":bool(end==h+pd.Timedelta(days=SCORE_DAYS)),
                "remaining_days_from_start":(end-start).days,
                "aftertax_forward_vs_current_live_buy_pct":round(
                    100*(forward["after_hypothetical_liquidation_cgt_aud"]/
                         live["after_hypothetical_liquidation_cgt_aud"]-1),2),
                "cash_undereployment_cost_vs_lump_aud":{
                    k:round(reference-v["after_hypothetical_liquidation_cgt_aud"],2)
                    for k,v in comparisons.items() if k!="immediate_lump_sum"
                },
                "variants":comparisons,
                "trade_audit":{key:obj["orders"] for key,obj in variants.items()},
            }
            scenarios.append(result)
    if not scenarios:
        raise ValueError("No fully observed matched research starts")
    return {
        "study":"2026-style matched fresh AUD cash 200WMA DCA, no prior BTC or invented SELL",
        "initial_cash_aud":float(budget_aud),
        "start_days_relative_to_confirmed_halving":list(start_days),
        "actual_observed_archive_end":str(price.index[-1].date()),
        "cohorts":scenarios,
        "assumptions":[
            "Identical date and available AUD cash among four arms; no past BTC holdings or imaginary day500 SELL proceeds.",
            "Original adaptive recovery weekly fraction of FIXED starting cash only AFTER newly observed prior-close-below-200WMA activation.",
            "Existing simplified live BUY rule tested daily: 2.5% of REMAINING cash each day prior close is below previous 200WMA; no follow-on recovery purchases when market rebounds.",
            "Equal weekly DCA tests 52 weekly tranches; lump sums spend all money at the next observed close. No 2025 backdated trades.",
            "All arms use next-day daily close proxy BTC/USD and prior dated USD/AUD, A$3/fill, simplified FIFO SMSF CGT on hypothetical terminal liquidation.",
            "No actual IBIT ETF market hours, whole-share rounding, fees, bid/ask slippage, real tax returns, cash yield or reinvested sale tax.",
            "2017 and 2021 windows are already inspected and in-sample; 2025/26 is right-censored at Oct 5 2026.",
            "Scenarios and model thresholds were shaped by historical Bitcoin discussion; this is NOT out-of-sample evidence.",
            "Cash not invested can outperform Bitcoin when BTC falls. Cash underdeployment cost is relative to lump sum and can be negative.",
            "Only BUY accumulation is compared; sell/rebuy cycles require separate position-aware forward testing and must not inherit historical sell-timing gains.",
            "Production V5.8.2, Research V5.9, live Streamlit/ntfy percentages, Google Sheets and actual user's trades unchanged.",
        ],
    }


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--output",type=Path)
    a=parser.parse_args()
    result=evaluate_fresh_cash_matched_starts(read_exported_history())
    for row in result["cohorts"]:
        print(json.dumps({
            "cycle":row["cycle"],"start_day":row["start_day_from_halving"],
            "start_date":row["start_date"],"terminal":row["terminal"],
            "complete":row["complete_score_window"],
            "forward_vs_current_pct":row["aftertax_forward_vs_current_live_buy_pct"],
            "models":{
                key:{k:v[k] for k in (
                    "fill_count","cash_left_pct",
                    "after_hypothetical_liquidation_cgt_aud",
                    "average_buy_error_above_observed_future_low_pct")}
                for key,v in row["variants"].items()
            }
        },sort_keys=True))
    if a.output:
        a.output.parent.mkdir(parents=True,exist_ok=True)
        a.output.write_text(json.dumps(result,indent=2))
        print("Full dated cash-only trade audits written:",a.output)


if __name__=="__main__":
    main()
