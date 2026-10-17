"""Research-only reconciliation of the ORIGINAL BTC/IBIT cycle-sale cash budget.

The user's Google Sheets executed-trade ledger has no authoritative SMSF
tax provision or explicit buyback-funding tag. Never treat gross current cash
as verified original after-tax sale proceeds. This module traces ORIGINAL
pre-day500 FIFO lots, identifies only their sales in days500..730, estimates
tax conservatively (no losses offset), and treats ALL subsequent purchases
as consuming this budget to avoid double-allocation.

Only an explicit, user-confirmed UNPAID tax provision and ledger check can
produce a read-only AUD research preview. No orders, no ntfy changes,
no historical buys/sells fabricated or retroactively attributed to 2026 lots.
"""
from __future__ import annotations

import copy
import datetime as dt
import hashlib
import json
import math

import pandas as pd

from engines.shared.portfolio_transactions import (
    ASSETS,parse_date,portfolio_positions,
)
from engines.research.shared_cycle_policy import (
    START_DAY,REVIEW_DAY,recovery_buy_budget_fraction,
)
from engines.research.day500_aftertax_reinvestment import (
    DELAY_DAYS_AFTER_LAST_SELL,causal_buyback_dates,
)

EPS=1e-8


def _num(value,label,*,zero=False):
    try:
        v=float(value)
    except (TypeError,ValueError):
        raise ValueError(f"{label} must be a finite AUD amount")
    if not math.isfinite(v) or v<0 or (not zero and v<=0):
        raise ValueError(f"{label} must be a valid positive amount")
    return v


def _as_day(value):
    t=pd.Timestamp(value)
    t=t.tz_localize("UTC") if t.tzinfo is None else t.tz_convert("UTC")
    return t.normalize()


def original_sale_cash_reconciliation(saved,halving,*,asof):
    """FIFO only, original pre-day500 lots; non-original sales are excluded.

    Reserve estimate = 10% of positive long-term net gains plus 15% of
    positive short-term net gains. Deliberately NO benefit from capital
    losses; not an SMSF tax return, independent cost-base audit or tax advice.
    As-of snapshot intentionally excludes transactions after the last
    completed BTC observation, even if the live ledger already has them.
    """
    portfolio_positions(saved)  # Validate the complete source ledger first.
    h=_as_day(halving)
    today=_as_day(asof)
    if today<h:
        raise ValueError("As-of date predates the confirmed halving")
    day500=(h+pd.Timedelta(days=START_DAY)).date()
    day730=(h+pd.Timedelta(days=REVIEW_DAY)).date()
    cutoff=today.date()
    snapshot={k:copy.deepcopy(v) for k,v in saved.items()
              if k not in ("rows","sales")}
    buys=copy.deepcopy(saved.get("rows",[]))
    sells=copy.deepcopy(saved.get("sales",[]))
    snapshot["rows"]=[v for v in buys if parse_date(v.get("Date"))<=cutoff]
    snapshot["sales"]=[v for v in sells if parse_date(v.get("Date"))<=cutoff]
    current=portfolio_positions(snapshot)
    signature=hashlib.sha256(json.dumps(
        {"capital":snapshot.get("starting_capital_aud",500000.),
         "buys":snapshot["rows"],"sales":snapshot["sales"]},
        sort_keys=True,default=str).encode("utf-8")).hexdigest()[:16]
    events=[]
    for i,row in enumerate(snapshot["rows"]):
        if row["Asset"] not in ASSETS:raise ValueError("Unknown BUY asset")
        q=_num(row.get("Units / BTC Received"),"BUY quantity")
        if row["Asset"]=="ASX:IBIT" and abs(q-round(q))>EPS:
            raise ValueError("Fractional ASX:IBIT BUY")
        fee=_num(row.get("Brokerage / Fee AUD",0),"BUY fee",zero=True)
        cost=_num(row.get("AUD Spent"),"BUY consideration")+fee
        events.append((parse_date(row["Date"]),0,i,row["Asset"],q,cost,fee))
    for i,row in enumerate(snapshot["sales"]):
        if row["Asset"] not in ASSETS:raise ValueError("Unknown SELL asset")
        q=_num(row.get("Units Sold"),"SELL quantity")
        if row["Asset"]=="ASX:IBIT" and abs(q-round(q))>EPS:
            raise ValueError("Fractional ASX:IBIT SELL")
        fee=_num(row.get("Brokerage / Fee AUD",0),"SELL fee",zero=True)
        gross=_num(row.get("AUD Proceeds"),"SELL proceeds")
        if gross<=fee:raise ValueError("Proceeds must exceed fee")
        events.append((parse_date(row["Date"]),1,i,row["Asset"],q,gross,fee))
    events.sort()
    lots={asset:[] for asset in ASSETS}
    original_units={asset:0. for asset in ASSETS}
    originals_sold={asset:0. for asset in ASSETS}
    sale_proceeds=0.
    tax_estimate=0.
    allocated_fees=0.
    qualifying_sale_count=0
    for date,side,i,asset,quantity,amount,fee in events:
        if side==0:
            lots[asset].append({
                "date":date,"qty":quantity,"cost":amount,
                "original":date<day500,
            })
            continue
        left=quantity
        original_allocated=0.
        for lot in lots[asset]:
            if left<=EPS:break
            have=lot["qty"]
            if have<=EPS:continue
            taken=min(left,have)
            share=taken/quantity
            cb=lot["cost"]*taken/have
            net=(amount-fee)*share
            if lot["original"] and day500<=date<=day730:
                sale_proceeds+=net
                allocated_fees+=fee*share
                original_allocated+=taken
                gain=net-cb
                long_held=pd.Timestamp(date)>pd.Timestamp(lot["date"])+pd.DateOffset(years=1)
                tax_estimate+=max(0.,gain)*(.10 if long_held else .15)
            lot["qty"]-=taken
            lot["cost"]-=cb
            left-=taken
        if left>EPS:raise ValueError("SELL exceeds dated FIFO inventory")
        if original_allocated>EPS:
            originals_sold[asset]+=original_allocated
            qualifying_sale_count+=1
    for asset in ASSETS:
        original_units[asset]=sum(max(0.,x["qty"]) for x in lots[asset]
                                  if x["original"])+originals_sold[asset]
    gate_start=(h+pd.Timedelta(days=REVIEW_DAY+DELAY_DAYS_AFTER_LAST_SELL)).date()
    # Conservatively debit ALL buys on/after the first possible gated
    # buyback date. The ledger does not identify provenance of each spend.
    subsequent_spending=sum(
        _num(row["AUD Spent"],"Recorded BUY consideration")+
        _num(row.get("Brokerage / Fee AUD",0),"BUY fee",zero=True)
        for row in snapshot["rows"]
        if parse_date(row["Date"])>=gate_start
    )
    return {
        "research_only":True,"place_order":False,
        "ledger_fingerprint":signature,"asof_date":str(cutoff),
        "day500":str(day500),"last_sell_review":str(day730),
        "earliest_buyback_monitor":str(gate_start),
        "original_holdings_at_day500":original_units,
        "original_units_sold_in_review":originals_sold,
        "qualifying_sale_count":qualifying_sale_count,
        "original_net_sale_proceeds_before_cgt_aud":round(sale_proceeds,2),
        "illustrative_unpaid_smsf_cgt_reserve_aud":round(tax_estimate,2),
        "illustrative_aftertax_sale_cash_aud":round(
            max(0.,sale_proceeds-tax_estimate),2),
        "all_later_buys_including_fees_aud":round(subsequent_spending,2),
        "recorded_cash_before_tax_reserve_aud":current["cash_remaining_aud"],
        "unrecorded_future_transactions_ignored":len(buys)!=len(snapshot["rows"]) or len(sells)!=len(snapshot["sales"]),
        "tax_reserve_verified":False,
        "ledger_buyback_tagging_verified":False,
        "explanation":(
            "Tax is a conservative estimated escrow on positive FIFO gains "
            "at illustrative accumulation-phase rates; your verified annual "
            "SMSF liability, offsets, phase and broker balances may differ. "
            "All purchases after review closure count against the budget, "
            "including purchases that could be unrelated."
        ),
    }


def original_buyback_preview(saved,price,halving,*,asof,
                             verified_unpaid_tax_reserve_aud=None,
                             confirmation=False):
    """No actionable recommendation; opt-in historic tranche preview only.

    The dollar preview is non-None only with explicit confirmation of the
    unpaid tax provision against this exact dated portfolio snapshot.
    Today's actual fill, broker positions and account tax phase remain
    user-dependent. Never issue executable order quantities.
    """
    summary=original_sale_cash_reconciliation(saved,halving,asof=asof)
    response={**summary,
        "buyback_phase_observed":False,
        "buyback_trigger_date":None,
        "last_weekly_research_review_date":None,
        "last_review_buy_pct_of_original_budget":None,
        "reconciled_original_aftertax_budget_aud":None,
        "reconciled_unused_buyback_budget_aud":None,
        "read_only_historical_review_aud":None,
        "already_recorded_buy_on_review_day":False,
        "broker_order_allowed":False,
    }
    amount=summary["original_net_sale_proceeds_before_cgt_aud"]
    if amount<=EPS:return response
    h=_as_day(halving); day=_as_day(asof)
    start=h+pd.Timedelta(days=REVIEW_DAY+DELAY_DAYS_AFTER_LAST_SELL)
    if day<start:return response
    if not isinstance(price,pd.Series) or day not in price.index:
        raise ValueError("Completed, dated BTC close unavailable")
    trigger,_=causal_buyback_dates(
        price.loc[:day],start=start,gate=.40,terminal=day,
        weekly_limit=1,entry_mode="below_200wma")
    if trigger is None:return response
    latest=trigger+pd.Timedelta(days=7*((day-trigger).days//7))
    signal=recovery_buy_budget_fraction(price.loc[:latest],latest,
                                        style="adaptive_recovery")
    response.update(
        buyback_phase_observed=True,
        buyback_trigger_date=str(trigger.date()),
        last_weekly_research_review_date=str(latest.date()),
        last_review_buy_pct_of_original_budget=signal["pct_of_initial_buyback_cash"],
    )
    if not confirmation:return response
    if verified_unpaid_tax_reserve_aud is None:
        raise ValueError("Verified unpaid tax reserve is required")
    tax=_num(verified_unpaid_tax_reserve_aud,"Unpaid SMSF tax provision",zero=True)
    if tax>amount+EPS:
        raise ValueError("Tax provision exceeds original gross net sale proceeds")
    net=amount-tax
    spent=summary["all_later_buys_including_fees_aud"]
    remaining=max(0.,net-spent)
    available=max(0.,summary["recorded_cash_before_tax_reserve_aud"]-tax)
    already=any(
        parse_date(v.get("Date"))==latest.date()
        for v in saved.get("rows",[])
        if parse_date(v.get("Date"))<=day.date())
    example=0. if already else min(net*signal["fraction_of_initial_buyback_cash"],
                                     remaining,available)
    response.update(
        tax_reserve_verified=True,
        confirmed_unpaid_cgt_provision_aud=round(tax,2),
        reconciled_original_aftertax_budget_aud=round(net,2),
        reconciled_unused_buyback_budget_aud=round(remaining,2),
        cash_net_unpaid_tax_escrow_aud=round(available,2),
        already_recorded_buy_on_review_day=already,
        read_only_historical_review_aud=round(example,2),
    )
    return response
