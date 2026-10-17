"""Research-only prospective 200WMA DCA funded by real *available* AUD cash.

The original historical strategy reinvested ACTUAL net after-tax day500 sale
proceeds. A user who only bought in 2026 has no such 2025 sale proceeds.
This experiment reuses the pre-existing 200WMA gate and weekly adaptive
recovery fractions, but anchors an explicitly confirmed NEW cash budget
as of a real enrolment date. It is a DIFFERENT funding scenario from the
historical backtest, not a claim of identical after-tax live returns.

No broker orders, no ntfy signals, no real holdings edits, no automatic
rebalancing, and no historical backdating. Portfolio metadata changes only
when the user explicitly confirms and saves an enrolment.
"""
from __future__ import annotations

import copy
import datetime as dt
import hashlib
import json
import math
from zoneinfo import ZoneInfo

import pandas as pd

from engines.shared.portfolio_transactions import (
    parse_date,portfolio_positions,
)
from engines.research.day500_aftertax_reinvestment import causal_buyback_dates
from engines.research.shared_cycle_policy import recovery_buy_budget_fraction

CONFIG_KEY="cycle_forward_cash_dca_research"
MIN_BUDGET_AUD=100.
DEFAULT_STYLE="adaptive_recovery"


def _day(x):
    t=pd.Timestamp(x)
    if pd.isna(t):
        raise ValueError("Missing date")
    return (t.tz_localize("UTC") if t.tzinfo is None
            else t.tz_convert("UTC")).normalize()


def _finite_positive(x,label,*,zero=False):
    try: v=float(x)
    except (TypeError,ValueError): raise ValueError(f"{label} must be a valid amount")
    if not math.isfinite(v) or v<0 or (v==0 and not zero):
        raise ValueError(f"{label} must be finite and nonnegative")
    return v


def _dated_snapshot(saved,asof):
    limit=_day(asof).date()
    snapshot={k:copy.deepcopy(v) for k,v in saved.items()
              if k not in ("rows","sales")}
    for field in ("rows","sales"):
        rows=saved.get(field,[])
        if not isinstance(rows,list):
            raise ValueError("Executed transaction history must be lists")
        snapshot[field]=[
            copy.deepcopy(row) for row in rows
            if parse_date(row.get("Date"))<=limit
        ]
    positions=portfolio_positions(snapshot)
    return snapshot,positions


def _fingerprint(snapshot):
    payload={k:snapshot.get(k) for k in (
        "starting_capital_aud","rows","sales"
    )}
    return hashlib.sha256(json.dumps(
        payload,sort_keys=True,default=str).encode()).hexdigest()[:16]


def make_forward_cash_enrolment(saved, *, start_date, budget_aud,
                                broker_available_after_reserves_aud,
                                confirmed=False, today=None):
    """Generate metadata only; the Streamlit save action is separately opt-in.

    Restrict first enrolment to TODAY (Brisbane), never a historically
    hindsight-optimised start date. Budget is confirmed <= BOTH recorded
    unspent cash and broker-verified cash AFTER outside liabilities.
    Purchases already recorded on the enrolment day are included in
    starting cash, not debited twice without transaction timestamps.
    """
    if not confirmed:
        raise ValueError("Confirm available broker cash and forward programme")
    now=_day(today if today is not None else
             dt.datetime.now(ZoneInfo("Australia/Brisbane")).date())
    start=_day(start_date)
    if start!=now:
        raise ValueError("Forward DCA starts today only; no retrospective enrolment")
    if not isinstance(saved,dict):
        raise ValueError("Saved portfolio is unavailable")
    if saved.get(CONFIG_KEY):
        raise ValueError("Forward programme already configured; do not silently reset budget")
    snapshot,positions=_dated_snapshot(saved,now)
    if len(snapshot["rows"])!=len(saved.get("rows",[])) or len(snapshot["sales"])!=len(saved.get("sales",[])):
        raise ValueError("Future-dated recorded trades must be reconciled first")
    budget=_finite_positive(budget_aud,"Original forward cash budget")
    verified=_finite_positive(
        broker_available_after_reserves_aud,
        "Broker available cash after unpaid tax and other reserves",
        zero=True,
    )
    if budget<MIN_BUDGET_AUD:
        raise ValueError("Initial forward budget is below minimum research amount")
    if budget>min(verified,positions["cash_remaining_aud"])+.005:
        raise ValueError("Budget exceeds verified broker or recorded available cash")
    result=copy.deepcopy(saved)
    result[CONFIG_KEY]={
        "start_date":str(start.date()),
        "initial_budget_aud":round(budget,2),
        "recorded_initial_cash_aud":positions["cash_remaining_aud"],
        "broker_available_after_reserves_at_start_aud":round(verified,2),
        "original_ledger_fingerprint":_fingerprint(snapshot),
        "style":DEFAULT_STYLE,
        "research_only":True,
        "basis":"User-confirmed free AUD cash, NOT historical day500 sale proceeds",
    }
    if portfolio_positions(result)!=portfolio_positions(saved):
        raise AssertionError("Enrollment cannot change holdings/cash/sales")
    return result


def enrol_with_stale_guard(page_snapshot,latest,**kwargs):
    """Prevent an enrolment from overwriting changes in another session."""
    if not isinstance(page_snapshot,dict) or not isinstance(latest,dict):
        raise ValueError("Saved portfolio unavailable")
    if any(page_snapshot.get(k)!=latest.get(k)
           for k in ("rows","sales","starting_capital_aud",CONFIG_KEY)):
        raise ValueError("Portfolio changed since page load; refresh before enrolment")
    return make_forward_cash_enrolment(latest,**kwargs)


def forward_cash_dca_status(price,saved,*,asof,
                            broker_cash_after_reserves_aud=None,
                            feed_verified=True):
    """Deterministic 200WMA-triggered weekly state without future prices.

    An AUD preview is returned ONLY on the EXACT current weekly review
    date, with an independently confirmed broker cash-after-liabilities
    input. A purchase already recorded in that seven-day interval blocks
    proposing a second tranche. All unknown funding purchases are debited
    conservatively. The resulting value is a research illustration only.
    """
    base={
        "phase":"NOT_ENROLLED",
        "research_only":True,"broker_order_allowed":False,
        "historical_live_parity_verified":False,
        "price_data_verified":bool(feed_verified),
        "original_fresh_cash_budget_aud":None,
        "remaining_unspent_budget_aud":None,
        "recorded_account_cash_aud":None,
        "trigger_date":None,"last_completed_review_date":None,
        "next_review_date":None,"last_review_pct_original_budget":None,
        "current_review_pct_original_budget":None,
        "review_due_today":False,
        "research_review_aud":None,
        "spent_since_enrolment_aud":None,
        "unreviewed_spending_aud":None,
        "independently_funded_spending_aud":None,
        "message":"No user-confirmed prospective fixed-cash budget yet.",
    }
    if not isinstance(saved,dict):
        base["phase"]="LEDGER_UNAVAILABLE"
        return base
    snapshot,positions=_dated_snapshot(saved,asof)
    base["recorded_account_cash_aud"]=positions["cash_remaining_aud"]
    config=saved.get(CONFIG_KEY)
    if not config:
        return base
    if config.get("research_only") is not True or config.get("style")!=DEFAULT_STYLE:
        raise ValueError("Unrecognised forward cash research configuration")
    start=_day(config["start_date"])
    # The initial unspent-cash budget cannot be trusted if historical
    # transactions/balances from the enrolment day were subsequently edited.
    initial_snapshot,_=_dated_snapshot(saved,start)
    if _fingerprint(initial_snapshot)!=config.get("original_ledger_fingerprint"):
        raise ValueError(
            "Pre-enrolment portfolio trade history changed; reconcile before using forward budget"
        )
    date=_day(asof)
    budget=_finite_positive(config["initial_budget_aud"],"Initial budget")
    if budget<MIN_BUDGET_AUD or budget>float(config.get("recorded_initial_cash_aud",0))+.005:
        raise ValueError("Forward budget is inconsistent with initial recorded cash")
    base["original_fresh_cash_budget_aud"]=round(budget,2)
    spent=0.
    independent=0.
    unknown=0.
    buy_dates=[]
    for row in snapshot["rows"]:
        d=_day(parse_date(row["Date"]))
        if d<=start:continue
        cost=_finite_positive(row["AUD Spent"],"BUY consideration")+_finite_positive(
            row.get("Brokerage / Fee AUD",0),"BUY fee",zero=True)
        source=row.get("Funding Source","Unreviewed")
        if source=="Independent cash":
            independent+=cost
        elif source in (None,"","Unreviewed","Original cycle sale proceeds"):
            spent+=cost
            if source in (None,"","Unreviewed"):
                unknown+=cost
        else:
            raise ValueError("Invalid BUY funding-source metadata")
        buy_dates.append(d)
    remaining=max(0.,budget-spent)
    base.update(
        spent_since_enrolment_aud=round(spent,2),
        unreviewed_spending_aud=round(unknown,2),
        independently_funded_spending_aud=round(independent,2),
        remaining_unspent_budget_aud=round(remaining,2),
    )
    if date<=start:
        base.update(
            phase="WAITING_FOR_START",
            message="Enrolment takes effect with the first FULLY observed future daily BTC close.",
        )
        return base
    if not feed_verified:
        base.update(phase="UNVERIFIED_PRICE_FEED",
                    message="Market prices are stale/unverified; no dated research BUY.")
        return base
    if (not isinstance(price,pd.Series)
            or not isinstance(price.index,pd.DatetimeIndex)
            or price.index.tz is None or not price.index.is_monotonic_increasing
            or price.index.has_duplicates or date not in price.index):
        raise ValueError("Dated, complete, UTC BTC price series required")
    # Activation can occur only strictly AFTER real budget enrolment, never
    # on the date of the enrolment or by retrospectively selecting a bottom.
    start_gate=start+pd.Timedelta(days=1)
    trigger,_=causal_buyback_dates(
        price.loc[:date],start=start_gate,gate=.40,
        terminal=date,weekly_limit=1,entry_mode="below_200wma")
    if trigger is None:
        base.update(
            phase="WAITING_BELOW_200WMA",
            message="No fully observed previous-close below-200WMA entry AFTER enrolment.",
        )
        return base
    gap=(date-trigger).days
    index=gap//7
    review=trigger+pd.Timedelta(days=7*index)
    pct=recovery_buy_budget_fraction(
        price.loc[:review],review,style=DEFAULT_STYLE)["pct_of_initial_buyback_cash"]
    next_review=review+pd.Timedelta(days=7)
    due=date==review
    base.update(
        trigger_date=str(trigger.date()),
        last_completed_review_date=str(review.date()),
        next_review_date=str(next_review.date()),
        last_review_pct_original_budget=pct,
        current_review_pct_original_budget=pct if due else None,
        review_due_today=due,
    )
    if not due:
        base.update(
            phase="BETWEEN_WEEKLY_REVIEWS",
            message="Last weekly percentage is HISTORY, not a new order today.",
        )
        return base
    if any(review-pd.Timedelta(days=6)<=d<=review for d in buy_dates):
        base.update(
            phase="ALREADY_RECORDED_BUY_THIS_WEEK",
            message="A BUY was already recorded in the previous seven days; no duplicate review.",
        )
        return base
    if remaining<MIN_BUDGET_AUD:
        base.update(
            phase="BUDGET_EXHAUSTED",
            message="No sufficient original free-cash budget remains.",
        )
        return base
    if broker_cash_after_reserves_aud is None:
        base.update(
            phase="BROKER_CASH_REQUIRED",
            message="Confirm available broker AUD cash after outstanding tax and reserves for a research AUD preview.",
        )
        return base
    broker_cash=_finite_positive(
        broker_cash_after_reserves_aud,
        "Broker available cash after reserves",zero=True)
    proposed=min(
        budget*(pct/100.),
        remaining,
        max(0.,positions["cash_remaining_aud"]),
        broker_cash,
    )
    base.update(
        phase="REVIEW_RESEARCH_ONLY",
        research_review_aud=round(proposed,2) if proposed>=MIN_BUDGET_AUD else 0.,
        message="Observed weekly research BUY amount only; never an executable broker order.",
    )
    return base
