"""Research-only common exit: value trading and DCA after identical liquidation.

A valid comparison must apply identical ETF dealing costs and 15% complying
SMSF accumulation-phase capital-gains assumptions to ALL unsold parcels in
BOTH models. Prior realised CGT cash payments have already reduced portfolio
cash and are not charged twice.

This ledger is an illustrative FIFO stress test, not Australian tax advice:
it excludes ETF attribution/distributions, SMSF ECPI, super contributions,
members' other income and actually scheduled ATO payment due dates.
"""
from copy import deepcopy
import math
import pandas as pd

def terminal_liquidation(ledger,cash,units,day,price,
                         brokerage=20.0,fee=0.001,slippage=0.005,
                         fully_tax_exempt=False):
    """Dispose of an entire ETF position at the common dated price.

    The supplied ledger is never mutated. Returns realisable AUD proceeds
    net of final CGT and prior cash tax settlements, with sale fee included.
    """
    date=pd.Timestamp(day)
    # The acquisition ledger normally uses UTC dates; normalize exit dates
    # so the >=12-month holding-period test never compares naive with aware.
    date=date.tz_localize("UTC") if date.tzinfo is None else date.tz_convert("UTC")
    cash=float(cash)
    units=float(units)
    price=float(price)
    if cash<-0.01 or units<-1e-7:
        raise ValueError("Cash or inventory cannot be negative at liquidation")
    if not math.isfinite(price) or price<=0 or not 0<=fee<1 or not 0<=slippage<1:
        raise ValueError("Invalid quoted ETF price or dealing friction")
    if brokerage<0 or not math.isfinite(brokerage):
        raise ValueError("Invalid fixed brokerage")
    record=deepcopy(ledger)
    if abs(record.bought_units-record.sold_units-units)>1e-5:
        raise AssertionError("Portfolio and FIFO acquisition inventory disagree")
    market_value=cash+units*price
    realised=0.0
    if units>1e-9:
        realised=units*price*(1-fee)*(1-slippage)-brokerage
        if realised<=0:raise ValueError("Liquidation proceeds cannot cover fees")
        record({"side":"SELL","kind":"TERMINAL_LIQUIDATION",
                "date":date,"units":units,"cash":realised,
                "price":price,"brokerage":brokerage})
    detail=record.tax_summary()
    if abs(detail["net_units"])>1e-5:
        raise AssertionError("Some ETF inventory remains unsold")
    # For wholly exempt pension-only testing use a separate ledger without
    # prior taxable distributions/sales; previously paid tax cannot be undone.
    if fully_tax_exempt:
        if ledger.paid_total>0:
            raise ValueError("Cannot label a previously taxed ledger fully exempt")
        due=0.0
    else:
        due=float(detail["tax_outstanding"])
    net=cash+realised-due
    return {
        "before_liquidation_mark_aud":round(market_value,2),
        "net_sale_proceeds_aud":round(realised,2),
        "sale_dealing_cost_aud":round(units*price-realised,2),
        "tax_already_paid_aud":round(float(ledger.paid_total),2),
        "tax_remaining_at_exit_aud":round(due,2),
        "total_estimated_cgt_aud":round(float(detail["estimated_total_tax"]),2),
        "net_fully_liquidated_aud":round(net,2),
        "previous_sell_fills":int(sum(x["sells"] for x in ledger.years.values())),
    }
