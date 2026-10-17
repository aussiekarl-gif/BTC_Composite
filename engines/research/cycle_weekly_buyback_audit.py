"""Research-only dated weekly audit of ORIGINAL below-200WMA recovery BUYs.

This does not place trades, produce an ntfy signal, or treat unreviewed BUYs
as proven cycle reinvestments. Every weekly percentage is computed strictly
from prices BEFORE that review, using shared_cycle_policy. Dates and fill
amounts come exclusively from executed ledger rows.

Executed purchases in a given weekly window are either:
  - user-labelled original cycle sale proceeds for THIS specific halving,
  - unreviewed/other-cycle; spending conserved but NOT counted as proof,
  - independent cash, explicitly excluded from cycle-funded spending.

The original sell-cash budget exists only if original eligible SELLs exist.
Any dollar plan requires explicit tax and broker confirmation in the *existing*
original_buyback_preview; this module never authorizes a new order.
"""
from __future__ import annotations

import math

import pandas as pd

from engines.shared.portfolio_transactions import parse_date,portfolio_positions
from engines.research.day500_aftertax_reinvestment import (
    DELAY_DAYS_AFTER_LAST_SELL,causal_buyback_dates,
)
from engines.research.shared_cycle_policy import (
    REVIEW_DAY,recovery_buy_budget_fraction,
)
from engines.research.cycle_real_sale_budget import (
    original_sale_cash_reconciliation,
)

MAX_REVIEWS=520


def weekly_original_buyback_ledger(price,halving,saved,*,asof):
    """Build causal schedule and match recorded fills without inventing trades.

    This is intentionally a study of *recorded* trades and weekly research
    targets, not a live portfolio order, after-tax balance or broker order.
    """
    portfolio_positions(saved)  # Original rows must be valid
    state=original_sale_cash_reconciliation(saved,halving,asof=asof)
    t=pd.Timestamp(asof)
    t=t.tz_localize("UTC") if t.tzinfo is None else t.tz_convert("UTC")
    t=t.normalize()
    h=pd.Timestamp(halving)
    h=h.tz_localize("UTC") if h.tzinfo is None else h.tz_convert("UTC")
    h=h.normalize()
    start=h+pd.Timedelta(days=REVIEW_DAY+DELAY_DAYS_AFTER_LAST_SELL)
    empty={
        "research_only":True,
        "live_trade_parity_verified":False,
        "broker_order_allowed":False,
        "funds_unverified":True,
        "asof_date":str(t.date()),
        "historical_exit_proceeds_aud":state["original_net_sale_proceeds_before_cgt_aud"],
        "historical_research_activation_date":None,
        "current_review_date":None,
        "days_since_current_review":None,
        "next_review_date":None,
        "review_history":[],
        "review_count":0,
        "recorded_cycle_tagged_spent_aud":0.,
        "recorded_unreviewed_spent_aud":0.,
        "recorded_independent_spent_aud":0.,
        "recorded_prior_to_trigger_spent_aud":0.,
        "recorded_total_debited_spent_aud":state["all_later_buys_including_fees_aud"],
        "original_sale_cash_budget_is_zero":state["original_net_sale_proceeds_before_cgt_aud"]<=0.,
    }
    if t<start or empty["original_sale_cash_budget_is_zero"]:
        return empty
    if not isinstance(price,pd.Series) or not isinstance(price.index,pd.DatetimeIndex):
        raise ValueError("Valid dated BTC series needed for 200WMA historical review")
    if price.index.tz is None or not price.index.is_monotonic_increasing or price.index.has_duplicates:
        raise ValueError("BTC close index must be ordered, unique, timezone-aware")
    if t not in price.index or start not in price.index:
        raise ValueError("Missing required BTC daily close in original weekly review")
    trigger,_=causal_buyback_dates(
        price.loc[:t],start=start,gate=.40,terminal=t,
        weekly_limit=1,entry_mode="below_200wma")
    if trigger is None:return empty
    count=(t-trigger).days//7+1
    if count>MAX_REVIEWS:
        raise ValueError("Too many observed weekly reviews; needs manual study")
    dates=[trigger+pd.Timedelta(days=7*i) for i in range(count)]
    if not pd.DatetimeIndex(dates).isin(price.index).all():
        raise ValueError("Missing observed weekly BTC close; fail closed")
    rows=[]
    for i,day in enumerate(dates):
        frac=recovery_buy_budget_fraction(
            price.loc[:day],day,style="adaptive_recovery")
        rows.append({
            "week":i+1,
            "review_date":str(day.date()),
            "pct_original_aftertax_buyback_budget":frac["pct_of_initial_buyback_cash"],
            "market_recovery_confirmed":frac["recovery_confirmation"],
            "recorded_this_cycle_aud":0.,
            "recorded_unreviewed_or_other_cycle_aud":0.,
            "recorded_independent_aud":0.,
            "recorded_buy_count":0,
            "recorded_cycle_funding_provenance":"No cycle-funded fill recorded",
            "last_completed_review_not_current_order":True,
        })
    # Map every executed BUY after day744 and through observed as-of to
    # the calendar week whose review is the most recent prior one.
    # Buys before trigger are NOT assigned to some future review.
    spent_before_trigger=0.
    for v in saved.get("rows",[]):
        date=parse_date(v.get("Date"))
        if date<start.date() or date>t.date():
            continue
        cost=float(v.get("AUD Spent"))+float(v.get("Brokerage / Fee AUD",0))
        if not math.isfinite(cost) or cost<=0:
            raise ValueError("Invalid executed purchase consideration")
        source=v.get("Funding Source","Unreviewed")
        if source in (None,""):
            source="Unreviewed"
        if date<trigger.date():
            if source!="Independent cash":spent_before_trigger+=cost
            continue
        idx=(date-trigger.date()).days//7
        if idx<0 or idx>=len(rows):
            raise AssertionError("Unexpected out-of-range dated executed purchase")
        row=rows[idx]
        row["recorded_buy_count"]+=1
        if source=="Independent cash":
            row["recorded_independent_aud"]+=cost
        elif source=="Original cycle sale proceeds":
            label=v.get("Funding Cycle Halving")
            if not label:raise ValueError("Unverified missing original funding cycle tag")
            stamped=pd.Timestamp(label)
            stamped=stamped.tz_localize("UTC") if stamped.tzinfo is None else stamped.tz_convert("UTC")
            if stamped.normalize()==h:
                row["recorded_this_cycle_aud"]+=cost
            else:
                # Unmatched cycle label does NOT create cash for current cycle.
                row["recorded_unreviewed_or_other_cycle_aud"]+=cost
        elif source=="Unreviewed":
            row["recorded_unreviewed_or_other_cycle_aud"]+=cost
        else:
            raise ValueError("Unknown funding provenance")
    for row in rows:
        row["recorded_cycle_funding_provenance"]=(
            "User-labelled this cycle (not broker verified)"
            if row["recorded_this_cycle_aud"]>0 else
            "Only unreviewed/other-cycle buys; cannot certify weekly fill"
            if row["recorded_unreviewed_or_other_cycle_aud"]>0 else
            "Independent-cash purchases only" if row["recorded_independent_aud"]>0
            else "No cycle-funded fill recorded")
        for key in ("recorded_this_cycle_aud",
                    "recorded_unreviewed_or_other_cycle_aud",
                    "recorded_independent_aud"):
            row[key]=round(row[key],2)
    results={**empty,
        "historical_research_activation_date":str(trigger.date()),
        "current_review_date":str(dates[-1].date()),
        "days_since_current_review":(t-dates[-1]).days,
        "next_review_date":str((dates[-1]+pd.Timedelta(days=7)).date()),
        "review_history":rows,
        "review_count":len(rows),
        "recorded_cycle_tagged_spent_aud":round(sum(
            x["recorded_this_cycle_aud"] for x in rows),2),
        "recorded_unreviewed_spent_aud":round(sum(
            x["recorded_unreviewed_or_other_cycle_aud"] for x in rows),2),
        "recorded_independent_spent_aud":round(sum(
            x["recorded_independent_aud"] for x in rows),2),
        "recorded_prior_to_trigger_spent_aud":round(spent_before_trigger,2),
    }
    assigned=results["recorded_cycle_tagged_spent_aud"]+results[
        "recorded_unreviewed_spent_aud"]+results["recorded_prior_to_trigger_spent_aud"]
    if abs(assigned-state["all_later_buys_including_fees_aud"])>.025:
        raise AssertionError(
            "Weekly audit does not reconcile with conservative total cash spending"
        )
    return results
