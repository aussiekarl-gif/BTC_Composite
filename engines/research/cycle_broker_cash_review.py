"""Read-only actual portfolio CASH reconciliation and indicative FIFO SMSF gains.

Research display only. Does NOT assume that gross recorded sale proceeds are
unencumbered AUD available to trade, or that annual SMSF CGT was already paid.
Unpaid tax, pension phase, tax loss balances, trust contributions,
withdrawals, distributions and actual broker balances are unknown.

A verified free-broker-cash amount must ALREADY BE NET OF unpaid tax and
other liabilities; never subtract the illustrative tax provision again.
No trades or notifications are created, and the live signal is untouched.
"""
from __future__ import annotations

import copy
import datetime as dt
import math

import pandas as pd

from engines.shared.portfolio_transactions import (
    ASSETS,parse_date,portfolio_positions,
)

FEE_AUD=3.
MIN_ORDER_AUD=100.
SMALL=1e-8


def _num(value, name, *, allow_zero=False):
    try: value=float(value)
    except (ValueError,TypeError):
        raise ValueError(f"{name} must be a finite AUD amount")
    if not math.isfinite(value) or value<0 or (not allow_zero and value<=0):
        raise ValueError(f"{name} must be positive and finite")
    return value


def _date(value):
    if isinstance(value,pd.Timestamp) and value.tz is not None:
        return value.tz_convert("UTC").date()
    return parse_date(value)


def _fiscal_year(day):
    return f"{day.year if day.month>=7 else day.year-1}/{(day.year+1 if day.month>=7 else day.year)%100:02d}"


def _positive_tax_provision(gain, start, sold):
    # Australian super fund CGT: illustrative accumulation account,
    # gross positive lots only (no verified losses/carryforwards).
    more_than_12m=(pd.Timestamp(sold)>
                   pd.Timestamp(start)+pd.DateOffset(years=1))
    return max(0.,gain)*(.10 if more_than_12m else .15)


def fifo_sales_and_inventory(saved,*,asof):
    """Replay dated FIFO parcels across BOTH assets, no future transactions.

    This is an illustrative purchase-cost FIFO convention, NOT verification
    of tax identification, cost base adjustments or an SMSF tax return.
    """
    portfolio_positions(saved)  # Reject internally invalid entire ledger
    day=_date(asof)
    snapshot={k:copy.deepcopy(v) for k,v in saved.items()
              if k not in ("rows","sales")}
    for name in ("rows","sales"):
        snapshot[name]=[
            copy.deepcopy(x) for x in saved.get(name,[])
            if _date(x.get("Date"))<=day
        ]
    positions=portfolio_positions(snapshot)
    original_count=len(saved.get("rows",[]))+len(saved.get("sales",[]))
    current_count=len(snapshot["rows"])+len(snapshot["sales"])
    events=[]
    for i,row in enumerate(snapshot["rows"]):
        asset=row.get("Asset")
        if asset not in ASSETS:raise ValueError("Unknown purchased asset")
        units=_num(row.get("Units / BTC Received"),"Purchase units")
        basis=_num(row.get("AUD Spent"),"Purchase AUD")+_num(
            row.get("Brokerage / Fee AUD",0),"Buy fee",allow_zero=True)
        events.append((_date(row.get("Date")),0,i,asset,units,basis,0.))
    for i,row in enumerate(snapshot["sales"]):
        asset=row.get("Asset")
        if asset not in ASSETS:raise ValueError("Unknown sold asset")
        units=_num(row.get("Units Sold"),"Sale units")
        fee=_num(row.get("Brokerage / Fee AUD",0),"Sell fee",allow_zero=True)
        proceeds=_num(row.get("AUD Proceeds"),"Sale gross AUD")
        if proceeds<=fee:raise ValueError("Sale gross must exceed brokerage")
        events.append((_date(row.get("Date")),1,i,asset,units,proceeds,fee))
    events.sort()
    lots={asset:[] for asset in ASSETS}
    per_fy={}
    sales=[]
    for day,side,i,asset,units,amount,fee in events:
        if side==0:
            lots[asset].append(dict(date=day,units=units,basis=amount))
            continue
        left=units
        gain=0.
        basis_used=0.
        provision=0.
        positive_parcel_gains=0.
        for lot in lots[asset]:
            if left<=SMALL:break
            if lot["units"]<=SMALL:continue
            take=min(left,lot["units"])
            part_basis=lot["basis"]*take/lot["units"]
            net=(amount-fee)*take/units
            part_gain=net-part_basis
            provision+=_positive_tax_provision(part_gain,lot["date"],day)
            positive_parcel_gains+=max(0.,part_gain)
            gain+=part_gain
            basis_used+=part_basis
            lot["units"]-=take
            lot["basis"]-=part_basis
            left-=take
        if left>SMALL:
            raise ValueError("Cannot identify FIFO basis of all recorded sold units")
        fy=_fiscal_year(day)
        row=per_fy.setdefault(fy,{
            "financial_year":fy,"realized_net_gain_aud":0.,
            "gross_positive_parcel_gains_aud":0.,
            "indicative_max_gains_tax_aud":0.,"sale_count":0})
        row["realized_net_gain_aud"]+=gain
        row["gross_positive_parcel_gains_aud"]+=positive_parcel_gains
        row["indicative_max_gains_tax_aud"]+=provision
        row["sale_count"]+=1
        sales.append(dict(
            date=str(day),asset=asset,
            units=units,net_proceeds_aud=round(amount-fee,2),
            estimated_fifo_cost_base_aud=round(basis_used,2),
            estimated_realised_gain_aud=round(gain,2),
            indicative_positive_only_tax_aud=round(provision,2),
            financial_year=fy))
    by_year=[]
    for fy in sorted(per_fy):
        row=per_fy[fy]
        by_year.append({
            k:round(v,2) if isinstance(v,float) else v
            for k,v in row.items()
        })
    return {
        "research_only":True,
        "realized_sales":sales,
        "by_financial_year":by_year,
        "gross_positive_only_tax_projection_aud":round(sum(
            x["indicative_max_gains_tax_aud"] for x in by_year),2),
        "tax_already_paid_known":False,
        "fund_pension_phase_verified":False,
        "recorded_cash_before_tax_aud":positions["cash_remaining_aud"],
        "recorded_net_ibit_units":positions["ibit_units"],
        "recorded_direct_btc_units":positions["direct_btc"],
        "newer_ledger_trades_excluded":current_count<original_count,
        "inventory":lots,
        "limitations":(
            "FIFO cost basis is estimated from your entered AUD purchase/sale "
            "values. SMSF accumulation-phase indicative positive-gain-only CGT "
            "is NOT your actual unpaid tax: net losses, FY offset rules, "
            "pension phase, settlement and tax payments are not verified."
        ),
    }


def projected_ibit_sell_tax(saved,*,asof,units,price_aud,fee_aud=FEE_AUD):
    """Only estimate a hypothetical new IBIT sale from recorded FIFO lots."""
    unit_count=_num(units,"Proposed ETF units")
    if abs(unit_count-round(unit_count))>SMALL:
        raise ValueError("IBIT transactions require whole ETF units")
    price=_num(price_aud,"Broker ASX:IBIT quote")
    fee=_num(fee_aud,"Broker fee",allow_zero=True)
    state=fifo_sales_and_inventory(saved,asof=asof)
    if unit_count>state["recorded_net_ibit_units"]+SMALL:
        raise ValueError("Proposed ETF sale exceeds recorded holdings")
    gross=unit_count*price
    if gross<=fee:raise ValueError("Gross sale does not cover fee")
    remaining=unit_count
    provision=0.
    gain=0.
    cost_basis=0.
    day=_date(asof)
    for lot in state["inventory"]["ASX:IBIT"]:
        if remaining<=SMALL:break
        take=min(remaining,max(0.,lot["units"]))
        if take<=SMALL:continue
        basis=lot["basis"]*take/lot["units"]
        net=(gross-fee)*take/unit_count
        gain_part=net-basis
        gain+=gain_part
        cost_basis+=basis
        provision+=_positive_tax_provision(gain_part,lot["date"],day)
        remaining-=take
    if remaining>SMALL:
        raise ValueError("Recorded FIFO parcels insufficient for preview")
    return {
        "illustrative_sell_units":int(round(unit_count)),
        "illustrative_sell_gross_aud":round(gross,2),
        "illustrative_net_before_cgt_aud":round(gross-fee,2),
        "illustrative_FIFO_cost_basis_aud":round(cost_basis,2),
        "illustrative_realized_gain_aud":round(gain,2),
        "illustrative_positive_only_cgt_provision_aud":round(provision,2),
        "illustrative_net_after_cgt_provision_aud":round(
            gross-fee-provision,2),
        "research_only":True,
        "tax_paid_or_pension_phase_unverified":True,
    }


def broker_reconciled_trade_preview(saved,decision,*,asof,
                                    confirmed_broker_cash_after_reserves_aud=None,
                                    verified_broker_ibit_price_aud=None,
                                    confirmed=False):
    """Mirror existing live candidate with a smaller VERIFIED cash cap.

    The model action must ALREADY be BUY or SELL. This read-only calculator
    never promotes HOLD into BUY or SELL, avoids stale decisions, and NEVER
    passes its values into the actual decision or the daily notification.
    """
    audit=fifo_sales_and_inventory(saved,asof=asof)
    result={
        "research_only":True,"place_order":False,
        "new_trade_authorized":False,
        "phase":"NOT_VERIFIED",
        "model_action":decision.get("action","HOLD"),
        "gross_unreserved_ledger_cash_aud":audit["recorded_cash_before_tax_aud"],
        "conservative_estimate_of_total_historic_cgt_aud":audit[
            "gross_positive_only_tax_projection_aud"],
        "estimated_tax_is_unpaid_liability":False,
        "confirmed_free_broker_cash_aud":None,
        "max_cash_without_reconciling_other_liabilities_aud":None,
        "reconciled_research_gross_aud":None,
        "reconciled_whole_ibit_units":None,
        "reconciled_research_net_sale_aud_after_illustrative_tax":None,
        "historic_tax":audit,
    }
    if not confirmed:
        result["phase"]="NEEDS_BROKER_CONFIRMATION"
        return result
    action=decision.get("action")
    if action=="HOLD":
        result["phase"]="HOLD_REMAINS_HOLD"
        return result
    if verified_broker_ibit_price_aud is None:
        raise ValueError("A current manually checked ASX:IBIT broker quote is required")
    quote=_num(verified_broker_ibit_price_aud,"Broker ETF price")
    if action not in ("BUY","SELL"):
        raise ValueError("Unexpected model action")
    if action=="BUY":
        if confirmed_broker_cash_after_reserves_aud is None:
            raise ValueError("Broker AUD cash AFTER tax and liabilities is required")
        broker=_num(confirmed_broker_cash_after_reserves_aud,
                    "Broker free cash after reserves",allow_zero=True)
        available=min(audit["recorded_cash_before_tax_aud"],broker)
        pct=_num(decision.get("buy_pct_total_cash"),"Existing model BUY fraction")/100.
        if pct>1:
            raise ValueError("Invalid BUY percentage")
        # The independent reconciliation is a CAP, never permission to
        # increase the original model's candidate after manual cash limits.
        existing_gross=_num(
            decision.get("action_aud"),"Existing model proposed gross AUD",
            allow_zero=True)
        gross=min(available*pct,available,existing_gross)
        units=max(0,math.floor((gross-FEE_AUD)/quote+1e-10))
        result.update(
            confirmed_free_broker_cash_aud=round(broker,2),
            max_cash_without_reconciling_other_liabilities_aud=round(available,2),
            phase=("BROKER_CASH_TOO_SMALL" if gross<MIN_ORDER_AUD+FEE_AUD or units<1
                   else "BUY_RESEARCH_PREVIEW"),
            reconciled_research_gross_aud=round(gross,2) if units>=1 else 0.,
            reconciled_whole_ibit_units=units,
        )
    else:
        units=int(decision.get("suggested_ibit_units",0))
        if units<=0:raise ValueError("SELL decision has no verified whole units")
        projection=projected_ibit_sell_tax(
            saved,asof=asof,units=units,price_aud=quote)
        result.update(
            phase="SELL_RESEARCH_PREVIEW",
            reconciled_whole_ibit_units=units,
            reconciled_research_gross_aud=projection["illustrative_sell_gross_aud"],
            reconciled_research_net_sale_aud_after_illustrative_tax=projection[
                "illustrative_net_after_cgt_provision_aud"],
            projected_sale=projection,
        )
    return result
