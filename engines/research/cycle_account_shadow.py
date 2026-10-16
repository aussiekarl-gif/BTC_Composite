"""Read-only historical-policy proposal against a REAL recorded transaction ledger.

This is the bridge from the ORIGINAL BTC denominator used in legacy
research to an actual account, WITHOUT changing the public Streamlit
BUY/HOLD/SELL model or submitting broker orders.

Only proposes on a real eligible cycle review DATE and when the account
owned the asset BEFORE day500. Uses earlier executed SELLs to avoid
double-selling original holdings, and checks current net inventory.
Does not apply 2025 day500 selling to BTC/IBIT first bought in 2026.
"""
from __future__ import annotations

import math
import pandas as pd

from engines.shared.portfolio_transactions import (
    portfolio_positions,parse_date,
)
from engines.research.cycle_position_anchor import original_cycle_inventory
from engines.research.shared_cycle_policy import (
    staged_exit_decision,exit_review_days,START_DAY,REVIEW_DAY,
)


def _dated_portfolio(snapshot,cutoff,*,exclusive=False):
    """Point-in-time buy/sell slice of a saved ledger."""
    if not isinstance(snapshot,dict):
        raise ValueError("Saved portfolio data unavailable")
    copied={k:v for k,v in snapshot.items() if k not in ("rows","sales")}
    for key in ("rows","sales"):
        copied[key]=[]
        for record in snapshot.get(key,[]):
            recorded=parse_date(record["Date"])
            if recorded<cutoff if exclusive else recorded<=cutoff:
                copied[key].append(record)
    return copied


def shadow_original_btc_exit(price,halving,saved,*,asof,asset="ASX:IBIT",
                             policy="maturity_90pct_holdback20pct"):
    """Current proposal as ORIGINAL-BTC fraction, not percentage of cash.

    A candidate is RESEARCH CONTEXT only even when quantities known.
    Input data/portfolio reconciliation and broker confirmation still
    needed before any manual ETF/BTC order.
    """
    if asset not in ("ASX:IBIT","Direct BTC"):
        raise ValueError("Supported assets are ASX:IBIT and Direct BTC")
    date=pd.Timestamp(asof)
    if date.tzinfo is None:date=date.tz_localize("UTC")
    else:date=date.tz_convert("UTC")
    date=date.normalize()
    h=pd.Timestamp(halving)
    if h.tzinfo is None:h=h.tz_localize("UTC")
    else:h=h.tz_convert("UTC")
    h=h.normalize()
    day=(date-h).days
    base={
        "research_only":True,
        "place_order":False,
        "asset":asset,"policy":policy,
        "asof_date":str(date.date()),"halving_day":day,
        "action":"HOLD","quantity":0.,"original_position":0.,
        "fraction_original":0.,"pct_original":0.,
        "requires_broker_confirmation":True,
        "requires_smsf_cgt_review":True,
    }
    if day<START_DAY:
        base["reason"]="Day500 original-position anchor is not yet due."
        return base
    if day>REVIEW_DAY:
        base["reason"]="Historical day500–730 sell review window expired; no backdating."
        return base
    if day not in exit_review_days():
        base["reason"]="Not a scheduled original-BTC exit review date."
        return base
    if date not in price.index:
        base["reason"]="Completed BTC reference close unavailable for review date."
        return base
    # A scheduled review is a single research tranche, not an invitation
    # to repeat it after the user has already logged an executed same-day SELL.
    if isinstance(saved,dict) and any(
        record.get("Asset")==asset
        and parse_date(record.get("Date"))==date.date()
        for record in saved.get("sales",[])
    ):
        base["reason"]="A SELL is already recorded on this cycle review date."
        return base

    historical=_dated_portfolio(saved,date.date(),exclusive=True)
    try:
        info=original_cycle_inventory(historical,h,asof=date)
    except (ValueError,TypeError,KeyError) as exc:
        base["reason"]=f"Recorded original portfolio cannot be reconciled: {exc}"
        return base
    original=float(info["original_holdings"][asset])
    base["original_position"]=original
    if original<=1e-8:
        base["reason"]=(
            "No recorded original holdings before day500. "
            "Later BTC/IBIT buys cannot receive retroactive sell signals."
        )
        return base
    sold=float(info["sold_from_original"][asset])
    base["original_sold_before"]=sold
    base["original_left_before"]=max(0.,original-sold)
    if original-sold<=1e-8:
        base["reason"]="Original day500 inventory already distributed."
        return base
    # Use exactly same full historical exit policy, not the simplified
    # percentage-of-REMAINING-live-holdings allocation table.
    try:
        step=staged_exit_decision(
            price,h,day=day,sold_original_fraction=sold/original,
            policy=policy)
    except (TypeError,ValueError,KeyError) as exc:
        base["reason"]=f"Historical policy price observations invalid: {exc}"
        return base
    target=original*step["fraction_original"]
    latest=portfolio_positions(historical)
    available=float(latest["ibit_units" if asset=="ASX:IBIT" else "direct_btc"])
    raw=min(target,max(0.,original-sold),available)
    if asset=="ASX:IBIT":
        qty=float(math.floor(raw+1e-10))
    else:
        qty=float(math.floor(raw*1e8+1e-7)/1e8)
    base.update({
        "fraction_original":step["fraction_original"],
        "pct_original":round(100*step["fraction_original"],3),
        "regime":step["regime"],
        "quantity":qty,
        "available_recorded_units":available,
        "remaining_after_proposal":max(0.,original-sold-qty),
        "pre560_sold_cap_original_pct":step["pre560_sold_cap_original_pct"],
        "holdback_can_sell_after_day560":step["holdback_can_sell_after_day560"],
    })
    base["action"]="SELL REVIEW" if qty>0 else "HOLD"
    base["reason"]=(
        f"Review day {day}: research fraction {100*step['fraction_original']:.2f}% "
        "of recorded original BTC/ETF holdings; reconcile broker, taxes "
        "and exact original parcel before taking any action."
        if qty>0 else
        "Policy yields no executable whole-unit sale on this review date."
    )
    return base
