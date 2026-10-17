"""Opt-in executed BUY funding classification for the ONE existing portfolio.

This changes metadata only, never actual executed trade date, quantities,
prices, fees, costs, sale transactions, or tax assessments.

'Independent cash' is a USER-ATTESTED funding designation, not proof of a
bank transfer. 'Original cycle sale proceeds' needs recorded original lots
actually sold in that halving's day500..730 window. Missing/legacy labels
stay unreviewed and MUST be debited conservatively from original buyback cash.
"""
from __future__ import annotations

import copy
import datetime as dt
import pandas as pd

from engines.shared.portfolio_transactions import (
    portfolio_positions,parse_date,
)
from engines.research.shared_cycle_policy import REVIEW_DAY
from engines.research.day500_aftertax_reinvestment import (
    DELAY_DAYS_AFTER_LAST_SELL,
)
from engines.research.cycle_real_sale_budget import original_sale_cash_reconciliation

UNREVIEWED="Unreviewed"
INDEPENDENT="Independent cash"
CYCLE_SALE="Original cycle sale proceeds"
FUNDING_LABELS=(UNREVIEWED,INDEPENDENT,CYCLE_SALE)


def _epoch(value):
    stamp=pd.Timestamp(value)
    if pd.isna(stamp):
        raise ValueError("Cycle halving date is missing")
    stamp=stamp.tz_localize("UTC") if stamp.tzinfo is None else stamp.tz_convert("UTC")
    return stamp.normalize()


def classify_executed_buy(saved,*,row_index,funding_source,halving=None,
                          confirmed=False):
    """Pure authenticated-in-UI metadata update; no storage or brokerage call."""
    if not confirmed:
        raise ValueError("Explicit funding classification confirmation is required")
    if funding_source not in FUNDING_LABELS:
        raise ValueError("Unknown funding source; leave purchase unreviewed")
    portfolio_positions(saved)
    rows=saved.get("rows")
    if isinstance(row_index,bool) or not isinstance(row_index,int) or not isinstance(rows,list) or not 0<=row_index<len(rows):
        raise ValueError("Select a valid existing executed BUY")
    original=rows[row_index]
    if not isinstance(original,dict):
        raise ValueError("Purchase row corrupted")
    date=parse_date(original.get("Date"))
    today=dt.datetime.now(dt.timezone.utc).date()
    if date>today:
        raise ValueError("Future dated BUY cannot be classified")
    result=copy.deepcopy(saved)
    target=result["rows"][row_index]
    if funding_source==CYCLE_SALE:
        if halving is None:
            raise ValueError("The original cycle's confirmed halving date is required")
        epoch=_epoch(halving)
        earliest=(epoch+pd.Timedelta(days=REVIEW_DAY+DELAY_DAYS_AFTER_LAST_SELL)).date()
        if date<earliest:
            raise ValueError("BUY predates this cycle's earliest causal buyback review")
        state=original_sale_cash_reconciliation(saved,epoch,asof=today.isoformat())
        if state["original_net_sale_proceeds_before_cgt_aud"]<=0:
            raise ValueError("No original BTC/IBIT sale proceeds for this halving; cannot label BUY as cycle-funded")
        target["Funding Source"]=CYCLE_SALE
        target["Funding Cycle Halving"]=str(epoch.date())
    elif funding_source==INDEPENDENT:
        target["Funding Source"]=INDEPENDENT
        target.pop("Funding Cycle Halving",None)
    else:
        # Remove the tag entirely for backwards-compatible conservative rules.
        target.pop("Funding Source",None)
        target.pop("Funding Cycle Halving",None)
    # Metadata updates must not adjust financial balances or any sales.
    before=portfolio_positions(saved)
    after=portfolio_positions(result)
    if before!=after or result.get("sales",[])!=saved.get("sales",[]):
        raise AssertionError("Funding metadata must never affect holdings or cash")
    for i,(old,new) in enumerate(zip(rows,result["rows"])):
        stripped={k:v for k,v in new.items()
                  if k not in ("Funding Source","Funding Cycle Halving")}
        stripped_old={k:v for k,v in old.items()
                  if k not in ("Funding Source","Funding Cycle Halving")}
        if stripped!=stripped_old:
            raise AssertionError(f"Executed BUY {i+1} changed while tagging")
    return result


def classify_with_stale_guard(original,fresh,**kwargs):
    """Block edits when another Streamlit session changed the ledger."""
    if not isinstance(original,dict) or not isinstance(fresh,dict):
        raise ValueError("Live saved portfolio is unavailable")
    if (original.get("rows",[])!=fresh.get("rows",[])
            or original.get("sales",[])!=fresh.get("sales",[])
            or original.get("starting_capital_aud",500000.)!=
               fresh.get("starting_capital_aud",500000.)):
        raise ValueError("Portfolio changed since page load; refresh before classifying")
    return classify_executed_buy(fresh,**kwargs)
