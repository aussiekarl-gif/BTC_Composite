"""Read-only, account-aware applicability of original backtested Cycle rules.

Does NOT create a personal after-tax buyback budget from estimated cash or
fake historical positions. The original Research SELL schedule applies only
to units held before confirmed halving day500, and the historical BUY program
requires a validated post-sale net cash budget. Those conditions are
different from today's simplified percent-of-remaining Streamlit/ntfy.
"""
from __future__ import annotations

import pandas as pd

from engines.research.cycle_position_anchor import original_cycle_inventory
from engines.research.cycle_account_shadow import shadow_original_btc_exit
from engines.research.shared_cycle_policy import (
    START_DAY,REVIEW_DAY,exit_review_days,recovery_buy_budget_fraction,
)
from engines.research.day500_aftertax_reinvestment import (
    causal_buyback_dates,DELAY_DAYS_AFTER_LAST_SELL,
)
from engines.shared.portfolio_transactions import portfolio_positions


def historical_cycle_wallet_status(price, halving, saved, *, asof):
    """Account-state eligibility checks; never returns an executable BUY order."""
    if not isinstance(saved,dict):
        raise ValueError("A saved executed-trade portfolio is required")
    holdings=portfolio_positions(saved)  # no fabricated inventory, validate FIFO
    date=pd.Timestamp(asof)
    epoch=pd.Timestamp(halving)
    date=date.tz_localize("UTC") if date.tzinfo is None else date.tz_convert("UTC")
    epoch=epoch.tz_localize("UTC") if epoch.tzinfo is None else epoch.tz_convert("UTC")
    date=date.normalize()
    epoch=epoch.normalize()
    day=(date-epoch).days
    if day<0 or date not in price.index:
        raise ValueError("Observed as-of BTC close and verified halving required")
    result={
        "research_only":True,
        "place_order":False,
        "parity_to_current_ntfy_verified":False,
        "halving_day":day,
        "recorded_ibit_units":holdings["ibit_units"],
        "recorded_direct_btc":holdings["direct_btc"],
        "recorded_cash_aud_before_cgt":holdings["cash_remaining_aud"],
        "original_ibit_units":None,"original_direct_btc":None,
        "sale_review_ibit_units":0.,"sale_review_direct_btc":0.,
        "original_aftertax_buyback_budget_aud":None,
        "buyback_pct_original_budget":None,
        "buyback_trigger_date":None,
        "action":"HOLD","phase":"BEFORE_DAY500",
        "reason":"Not yet in the original-position day500 review period.",
    }
    if day<START_DAY:return result
    original=original_cycle_inventory(saved,epoch,asof=date)
    result["original_ibit_units"]=float(original["original_holdings"]["ASX:IBIT"])
    result["original_direct_btc"]=float(original["original_holdings"]["Direct BTC"])
    if not original["eligible"]:
        result.update(phase="NO_ORIGINAL_POSITION",
                      reason=(
                          "No BTC/IBIT units recorded as held BEFORE this halving's "
                          "day500 review. 2026 purchases cannot be backdated to a "
                          "September 2025 historical SELL. Original buyback cash "
                          "from those historical sales is unavailable."
                      ))
        return result
    if day<=REVIEW_DAY:
        result["phase"]="ORIGINAL_EXIT_REVIEWS"
        result["reason"]="Original BTC/IBIT SELL review (research only). No broker order."
        if day in exit_review_days():
            for asset,field in (
                ("ASX:IBIT","sale_review_ibit_units"),
                ("Direct BTC","sale_review_direct_btc")):
                preview=shadow_original_btc_exit(
                    price.loc[:date],epoch,saved,asof=date,asset=asset)
                result[field]=preview["quantity"]
            if result["sale_review_ibit_units"] or result["sale_review_direct_btc"]:
                result["action"]="SELL REVIEW — VERIFY"
                result["reason"]=(
                    "Historical ORIGINAL-position tranche. Quantities are "
                    "read-only, need broker confirmation and an SMSF tax review."
                )
        return result

    # A real account needs to have completed sale recording/CGT reconciliation.
    # We can reconstruct a public historical 200WMA gate, NOT original sale
    # cash after actual tax or a valid personal order quantity.
    gate_start=epoch+pd.Timedelta(
        days=REVIEW_DAY+DELAY_DAYS_AFTER_LAST_SELL)
    result["phase"]="AFTER_EXIT_REVIEWS"
    result["reason"]=(
        "Historical original-BTC exit reviews have ended. Any BUY budget "
        "requires reconciled actual sale proceeds, FIFO tax lots and verified "
        "SMSF phase; no personal BUY amount can be calculated."
    )
    if date<gate_start:return result
    trigger,_=causal_buyback_dates(
        price.loc[:date],start=gate_start,gate=.40,terminal=date,
        weekly_limit=1,entry_mode="below_200wma")
    if trigger is None:return result
    result["buyback_trigger_date"]=str(trigger.date())
    # Show the last weekly historical research step for context, not as
    # an automatically executable today BUY.
    elapsed=(date-trigger).days
    review=trigger+pd.Timedelta(days=7*(elapsed//7))
    frac=recovery_buy_budget_fraction(
        price.loc[:review],review,style="adaptive_recovery")
    result["buyback_pct_original_budget"]=frac["pct_of_initial_buyback_cash"]
    result["phase"]="HISTORICAL_BUYBACK_ACTIVE_NO_VERIFIED_BUDGET"
    result["reason"]=(
        "Original historical 200WMA-triggered buyback phase is observable, "
        "but its ORIGINAL net after-tax sale cash is not established by this "
        "portfolio ledger. No BUY amount or broker order is authorised."
    )
    return result
