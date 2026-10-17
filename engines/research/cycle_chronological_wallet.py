"""Chronological research-only wallet replay of ORIGINAL 200WMA/day500 rules.

Crucial historical-timing audit: existing simulate_roundtrip() precomputes
ALL future SELL review dates to identify its *last* successful sale, then
allows a buyback 14 days after that date. At a live date before day730 the
account cannot know whether another optional tail SELL will trigger later.

This independent wallet therefore ends ALL potential SELL reviews at
halving+730, waits 14 days, then activates first prior-close<200WMA BUY.
The strict pause deliberately trades away some opportunity to avoid
hindsight's knowledge of a future last sale. Neither model is a broker
order, a forecast or a tested 2026 personal portfolio allocation.
"""
from __future__ import annotations

import argparse
import json
import math
from pathlib import Path

import pandas as pd

from engines.research.day500_aftertax_reinvestment import (
    INITIAL_AUD,PRIMARY,SCORE_DAYS,fx_before,fetch_fx_for_cycle,
    simulate_roundtrip,DELAY_DAYS_AFTER_LAST_SELL,
)
from engines.research.shared_cycle_policy import (
    START_DAY,REVIEW_DAY,exit_review_days,staged_exit_decision,
    recovery_buy_budget_fraction,
)
from engines.research.smsf_self_financing_replay import AuditSmsfAccount
from engines.research.top_signal_horse_race import read_exported_history

POLICY="maturity_90pct_holdback20pct"
HISTORICAL_SELLER="dynamic_90pct_holdback20pct"
BUY_STYLES=("adaptive_recovery","adaptive_value")
MIN_AUD_ORDER=100.
FEE_AUD=3.


def previously_completed_200wma_breach(price,date):
    """Only exactly 200 weekly closes T-1, T-8, ..., T-1394."""
    date=pd.Timestamp(date)
    if date.tzinfo is None:date=date.tz_localize("UTC")
    else:date=date.tz_convert("UTC")
    samples=pd.DatetimeIndex(
        [date-pd.Timedelta(days=1+7*i) for i in range(200)])
    if not samples.isin(price.index).all():
        raise ValueError("Cannot establish 200WMA from 200 prior weekly prices")
    seen=price.loc[samples].astype(float)
    prev=float(price.loc[date-pd.Timedelta(days=1)])
    threshold=float(seen.mean())
    if not (math.isfinite(prev) and math.isfinite(threshold)
            and prev>0 and threshold>0):
        raise ValueError("Invalid prior BTC/WMA values")
    return prev<threshold


def replay_chronological_wallet(price,fx,halving,terminal, *,
                                buy_style="adaptive_recovery",
                                initial_aud=INITIAL_AUD):
    """A dated, stateful BUY/SELL/tax account without future sale peeking.

    The explicit REVIEW_DAY+14 barrier is an ultra-conservative,
    predeclared alternative—not a proven optimal trading switch.
    """
    if buy_style not in BUY_STYLES:
        raise ValueError("Unknown original 200WMA recovery style")
    h=pd.Timestamp(halving)
    t=pd.Timestamp(terminal)
    h=h.tz_localize("UTC") if h.tzinfo is None else h.tz_convert("UTC")
    t=t.tz_localize("UTC") if t.tzinfo is None else t.tz_convert("UTC")
    if t<=h or t not in price.index or h not in price.index:
        raise ValueError("Missing initial or terminal observed BTC close")
    if not (price.index.is_monotonic_increasing and price.index.is_unique
            and price.index.tz is not None):
        raise ValueError("UTC ordered unique BTC daily series required")
    if t>h+pd.Timedelta(days=SCORE_DAYS):
        raise ValueError("Historical score horizon exceeded")
    if not math.isfinite(float(initial_aud)) or initial_aud<=FEE_AUD:
        raise ValueError("Invalid AUD starting cash")
    all_dates=pd.date_range(h,t,freq="D",tz="UTC")
    if not all_dates.isin(price.index).all():
        raise ValueError("Missing a daily BTC price")
    acc=AuditSmsfAccount(float(initial_aud),fee=FEE_AUD,tax=True)
    initial_px=float(price.loc[h])*fx_before(fx,h)
    if not acc.buy(h,initial_px,1.):
        raise AssertionError("Unable to purchase initial dated BTC")
    initial_btc=acc.btc
    sale_dates=set(exit_review_days())
    buy_phase_start=h+pd.Timedelta(days=REVIEW_DAY+DELAY_DAYS_AFTER_LAST_SELL)
    activation=None
    initial_rebuy_cash=None
    fills=[]
    for date in all_dates[1:]:
        elapsed=(date-h).days
        usd=float(price.loc[date])
        if not math.isfinite(usd) or usd<=0:
            raise ValueError("Invalid dated USD close")
        if START_DAY<=elapsed<=REVIEW_DAY and elapsed in sale_dates:
            total_sold=sum(float(x["btc"]) for x in acc.orders
                           if x["side"]=="SELL")
            if total_sold>initial_btc+1e-8:
                raise ArithmeticError("Original BTC inventory already exceeded")
            step=staged_exit_decision(
                price.loc[:date],h,day=elapsed,
                sold_original_fraction=min(1.,total_sold/initial_btc),
                policy=POLICY,
            )
            qty=min(acc.btc,initial_btc*step["fraction_original"])
            if qty>1e-12:
                px=usd*fx_before(fx,date)
                if acc.sell(date,px,min(1.,qty/acc.btc)):
                    fills.append({"date":str(date.date()),
                                  "side":"SELL","btc":float(acc.orders[-1]["btc"]),
                                  "fraction_of_original":step["fraction_original"],
                                  "tax_aud":float(acc.orders[-1]["tax_aud"]),
                                  "gross_aud":float(acc.orders[-1]["gross_aud"])})
        if date>=buy_phase_start:
            if activation is None:
                if previously_completed_200wma_breach(price,date):
                    activation=date
                    initial_rebuy_cash=float(acc.cash)
            if activation is not None and (date-activation).days%7==0:
                if initial_rebuy_cash is None:
                    raise AssertionError("No fixed initial buyback budget")
                step=recovery_buy_budget_fraction(
                    price.loc[:date],date,style=buy_style)
                gross=min(acc.cash,initial_rebuy_cash*
                          step["fraction_of_initial_buyback_cash"])
                if gross>MIN_AUD_ORDER:
                    px=usd*fx_before(fx,date)
                    if acc.buy(date,px,min(1.,gross/acc.cash)):
                        fills.append({"date":str(date.date()),"side":"BUY",
                                      "btc":float(acc.orders[-1]["btc"]),
                                      "pct_original_aftertax_buyback_cash":
                                      step["pct_of_initial_buyback_cash"],
                                      "gross_aud":float(acc.orders[-1]["gross_aud"])})
        acc.mark(usd*fx_before(fx,date))

    final_aud=float(price.loc[t])*fx_before(fx,t)
    return {
        "policy":POLICY,
        "buy_style":buy_style,
        "research_only":True,
        "live_execution_parity_verified":False,
        "hypothetical_start_date":str(h.date()),
        "terminal_date":str(t.date()),
        "complete_day1150_window":t==h+pd.Timedelta(days=SCORE_DAYS),
        "initial_aud":float(initial_aud),
        "original_btc":round(initial_btc,8),
        "sell_review_end_day":REVIEW_DAY,
        "causal_buyback_review_start":str(buy_phase_start.date()),
        "buyback_activation_date":str(activation.date()) if activation is not None else None,
        "fixed_original_aftertax_buyback_cash_aud":(
            round(initial_rebuy_cash,2) if initial_rebuy_cash is not None else None),
        "btc_held":round(acc.btc,8),
        "cash_remaining_aud":round(acc.cash,2),
        "btc_equivalent_including_cash":round(acc.btc+acc.cash/final_aud,8),
        "after_hypothetical_liquidation_cgt_aud":round(
            acc.liquidation_value(t,final_aud),2),
        "estimated_realised_cgt_escrow_aud":round(acc.total_tax,2),
        "brokerage_aud":round(acc.total_fees,2),
        "sell_count":sum(x["side"]=="SELL" for x in acc.orders),
        "buyback_count":sum(x["side"]=="BUY" for x in acc.orders)-1,
        "account_min_drawdown_pct":round(100*acc.drawdown,2),
        "executions":fills,
    }


def audit_existing_history(history,*,fx_fetcher=fetch_fx_for_cycle):
    price=history["price_usd"].dropna().sort_index().loc[:"2026-10-05"]
    data=[]
    for label,item in PRIMARY.items():
        h=pd.Timestamp(item["halving"],tz="UTC")
        terminal=min(h+pd.Timedelta(days=SCORE_DAYS),price.index[-1])
        fx=fx_fetcher(h,terminal)
        variants=[]
        for style in BUY_STYLES:
            existing=simulate_roundtrip(
                price,fx,h,terminal,
                seller=HISTORICAL_SELLER,gate=.40,
                buyback_weeks=52,entry_mode="below_200wma",
                buyback_style=style)
            causal=replay_chronological_wallet(
                price,fx,h,terminal,buy_style=style)
            # Historical SELL is the SAME original-BTC strategy:
            if causal["sell_count"]!=existing["sell_count"] or not math.isclose(
                sum(row["btc"] for row in causal["executions"]
                    if row["side"]=="SELL")/causal["original_btc"],
                existing["entry_sold_fraction"],rel_tol=0,abs_tol=2e-5
            ):
                raise AssertionError("Original-BTC exit parity failed")
            held=float(existing["hold_hypothetical_liquidated_after_cgt_aud"])
            variants.append({
                "buy_style":style,
                "legacy_last_sale_informed_activation":existing["buyback_trigger_date"],
                "causal_review_closed_activation":causal["buyback_activation_date"],
                "legacy_aftertax_aud":existing["hypothetical_liquidated_after_cgt_aud"],
                "chronological_aftertax_aud":causal["after_hypothetical_liquidation_cgt_aud"],
                "matched_holding_aftertax_aud":held,
                "legacy_aftertax_advantage_vs_hold_pct":round(
                    100*(existing["hypothetical_liquidated_after_cgt_aud"]/held-1),2),
                "chronological_aftertax_advantage_vs_hold_pct":round(
                    100*(causal["after_hypothetical_liquidation_cgt_aud"]/held-1),2),
                "chronological_vs_legacy_aftertax_pct":round(
                    100*(causal["after_hypothetical_liquidation_cgt_aud"]/
                         existing["hypothetical_liquidated_after_cgt_aud"]-1),2),
                "legacy_btc_units":existing["btc_held_after_buyback"],
                "chronological_btc_units":causal["btc_held"],
                "legacy_cash_aud":existing["cash_remaining_aud"],
                "chronological_cash_aud":causal["cash_remaining_aud"],
                "chronological_rebuy_fills":causal["buyback_count"],
                "chronological_wallet":causal,
            })
        data.append({
            "cycle":label,
            "asof":str(terminal.date()),
            "complete":terminal==h+pd.Timedelta(days=SCORE_DAYS),
            "variants":variants})
    return {
        "study":"Chronological original-BTC exit and prior 200WMA recovery buyback safety audit",
        "status":"Research only, historical-to-Streamlit order parity NOT certified",
        "cycles":data,
        "caveats":[
            "Existing legacy replay determines the last SELL from completed history before opening BUY; may provide knowledge of later optional SELL reviews.",
            "New chronology waits to halving day744 (day730 final SELL review +14) before first below-200WMA BUY eligibility; this is safer, NOT previously optimised.",
            "Historical cycles 2017/2021 were inspected. 2025/26 is right-censored; no prospective proof or real 2026 historical sales.",
            "Both shadow portfolios hypothetically acquire A$500k BTC at historical halving, use date-prior FX and simplified FIFO SMSF 10/15% CGT.",
            "Account balances and CGT remain illustrative and are NOT the actual user's ASX:IBIT broker tax lots or actual fund tax phase.",
            "Nothing changes today's Streamlit BUY/HOLD/SELL or one daily ntfy schedule; no broker orders.",
        ],
    }


def main():
    p=argparse.ArgumentParser()
    p.add_argument("--output",type=Path)
    a=p.parse_args()
    result=audit_existing_history(read_exported_history())
    for cycle in result["cycles"]:
        for v in cycle["variants"]:
            print(json.dumps({
                "cycle":cycle["cycle"],"complete":cycle["complete"],
                "style":v["buy_style"],
                "legacy_trigger":v["legacy_last_sale_informed_activation"],
                "causal_trigger":v["causal_review_closed_activation"],
                "legacy_aftertax_vs_hold_pct":v["legacy_aftertax_advantage_vs_hold_pct"],
                "causal_aftertax_vs_hold_pct":v["chronological_aftertax_advantage_vs_hold_pct"],
                "causal_vs_legacy_pct":v["chronological_vs_legacy_aftertax_pct"],
                "legacy_btc":v["legacy_btc_units"],
                "causal_btc":v["chronological_btc_units"],
                "causal_rebuy_fills":v["chronological_rebuy_fills"]
            },sort_keys=True))
    if a.output:
        a.output.parent.mkdir(parents=True,exist_ok=True)
        a.output.write_text(json.dumps(result,indent=2))
        print("Full annotated wallet audit:",a.output)


if __name__=="__main__":
    main()
