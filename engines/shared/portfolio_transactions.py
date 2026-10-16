"""Executed buy/sell ledger for the ONE existing persistent My Portfolio.

Legacy `rows` are original BUY entries. New `sales` is append-only SELL
records. Both remain in the same Google Sheets portfolio_state JSON.
No fabricated trade history, prices, BTC ETF backing, or tax calculation.

Holdings are exact based on RECORDED unit quantities, not independently
verified broker custody. FIFO purchase allocations supply an *estimate*
of remaining economic BTC ETF exposure, not beneficial BTC title.
"""
from __future__ import annotations

import copy
import datetime as dt
import math
import uuid

ASSETS=("ASX:IBIT","Direct BTC")
SALES_KEY="sales"


def numeric(value, *, label="value", allow_zero=False):
    try:
        val=float(value)
    except (ValueError,TypeError):
        raise ValueError(f"{label}: valid number required")
    if not math.isfinite(val) or val<0 or (not allow_zero and val<=0):
        raise ValueError(f"{label}: positive finite number required")
    return val


def parse_date(value):
    if isinstance(value,dt.datetime):
        return value.date()
    if isinstance(value,dt.date):
        return value
    for fmt in ("%d/%m/%y","%d/%m/%Y","%Y-%m-%d"):
        try:return dt.datetime.strptime(str(value).strip(),fmt).date()
        except (ValueError,TypeError):pass
    raise ValueError("Trade date must be DD/MM/YY, DD/MM/YYYY or YYYY-MM-DD")


def _position_quantity(asset,raw):
    qty=numeric(raw,label="Quantity",allow_zero=False)
    if asset=="ASX:IBIT" and abs(qty-round(qty))>1e-9:
        raise ValueError("ASX:IBIT order must use whole ETF units")
    if asset=="Direct BTC" and round(qty,8)!=round(qty,10):
        raise ValueError("Direct BTC quantity supports up to 8 decimals")
    return float(round(qty) if asset=="ASX:IBIT" else round(qty,8))


def _read_ledger(saved):
    if not isinstance(saved,dict):
        raise ValueError("Saved portfolio must be a dictionary")
    buys=saved.get("rows",[])
    sells=saved.get(SALES_KEY,[])
    if not isinstance(buys,list) or not isinstance(sells,list):
        raise ValueError("Portfolio purchases and sales must be lists")
    return buys,sells


def portfolio_positions(saved):
    """Return net holdings/cash; fail CLOSED if sale ledger inconsistent.

    Legacy buys with unavailable BTC AUD price still count as exact ETF
    units, but corresponding BTC-EQUIVALENT exposure is unknown rather
    than invented. Errors in the unit ledger block new sales.
    """
    buys,sells=_read_ledger(saved)
    capital=numeric(saved.get("starting_capital_aud",500000.),
                    label="Starting AUD capital",allow_zero=True)
    inventory={asset:[] for asset in ASSETS}
    events=[]
    fees=buy_cost=sell_proceeds=0.
    for ix,r in enumerate(buys):
        if not isinstance(r,dict):
            raise ValueError(f"Invalid purchase row {ix+1}")
        asset=str(r.get("Asset","")).strip()
        if asset not in ASSETS:raise ValueError(f"Unknown asset in purchase {ix+1}")
        day=parse_date(r.get("Date"))
        units=_position_quantity(asset,r.get("Units / BTC Received"))
        aud=numeric(r.get("AUD Spent"),label="Purchase AUD consideration")
        fee=numeric(r.get("Brokerage / Fee AUD",0),label="Buy fee",allow_zero=True)
        btc_aud=float(r.get("BTC AUD Price") or 0)
        if not math.isfinite(btc_aud) or btc_aud<0:
            raise ValueError("Invalid historical BTC/AUD cost reference")
        exposure=(aud/btc_aud if asset=="ASX:IBIT" and btc_aud>0
                  else units if asset=="Direct BTC" else None)
        events.append((day,0,ix,asset,units,exposure))
        fees+=fee
        buy_cost+=aud
    for ix,r in enumerate(sells):
        if not isinstance(r,dict):
            raise ValueError(f"Invalid sell row {ix+1}")
        asset=str(r.get("Asset","")).strip()
        if asset not in ASSETS:raise ValueError(f"Unknown asset in sale {ix+1}")
        day=parse_date(r.get("Date"))
        units=_position_quantity(asset,r.get("Units Sold"))
        proceeds=numeric(r.get("AUD Proceeds"),label="Sale proceeds")
        fee=numeric(r.get("Brokerage / Fee AUD",0),label="Sell fee",allow_zero=True)
        if proceeds<=fee:
            raise ValueError(f"Sale {ix+1} proceeds must exceed brokerage")
        events.append((day,1,ix,asset,units,None))
        fees+=fee
        sell_proceeds+=proceeds
    # All recorded BUYs on same date precede SALEs, order stable by
    # purchase/sell list index. Reject transactions sold before owned.
    for day,side,ix,asset,units,btc_eq in sorted(events):
        if side==0:
            inventory[asset].append([units,btc_eq/units if btc_eq is not None else None])
        else:
            remaining=units
            for lot in inventory[asset]:
                consume=min(lot[0],remaining)
                lot[0]-=consume
                remaining-=consume
                if remaining<=1e-8:break
            if remaining>1e-8:
                raise ValueError(
                    f"Sale {ix+1} exceeds {asset} bought units available by {day.isoformat()}"
                )
    holdings={}
    exposure=0.
    incomplete=0
    for asset,lots in inventory.items():
        units=sum(max(0.,qty) for qty,ratio in lots)
        units=(float(round(units)) if asset=="ASX:IBIT" else round(units,8))
        holdings[asset]=units
        for qty,ratio in lots:
            if qty>1e-9:
                if ratio is None:incomplete+=1
                else:exposure+=qty*ratio
    cash=capital-buy_cost-fees+sell_proceeds
    if cash<-0.01:
        raise ValueError(
            "Recorded purchases, sales and fees exceed original capital plus realised proceeds"
        )
    return {
        "valid":True,
        "starting_capital_aud":capital,
        "ibit_units":holdings["ASX:IBIT"],
        "direct_btc":holdings["Direct BTC"],
        "btc_equivalent_estimate":(round(exposure,8) if incomplete==0 else None),
        "missing_exposure_lots":incomplete,
        "cash_remaining_aud":round(max(0.,cash),2),
        "spent_aud":round(buy_cost,2),
        "sell_proceeds_aud":round(sell_proceeds,2),
        "fees_aud":round(fees,2),
        "number_buys":len(buys),
        "number_sells":len(sells),
        "has_sales":bool(sells),
        "units_source":"Recorded executed purchases less executed sales; reconcile with broker",
    }


def append_executed_trade(saved,*,side,asset,trade_date,quantity,
                          trade_price_aud,fee_aud=3.,btc_aud_price=None,
                          note=""):
    """Append executed trade with full ledger validation; no storage I/O.

    Price is *actual executed ETF price / unit* or AUD/BTC for Direct BTC,
    not merely the delayed automated market quote.
    """
    if side not in ("BUY","SELL"):
        raise ValueError("Select BUY or SELL")
    if asset not in ASSETS:
        raise ValueError("Choose ASX:IBIT or Direct BTC")
    day=parse_date(trade_date)
    if day>dt.datetime.now(dt.timezone.utc).date():
        raise ValueError("Cannot record future executed trades")
    qty=_position_quantity(asset,quantity)
    price=numeric(trade_price_aud,label="Executed AUD price per unit")
    fee=numeric(fee_aud,label="Brokerage / Fee AUD",allow_zero=True)
    consideration=round(qty*price,2)
    if consideration<=fee:
        raise ValueError("Trade consideration must exceed fees")
    if asset=="ASX:IBIT" and side=="BUY":
        btc_price=numeric(btc_aud_price,label="BTC AUD price at executed purchase")
    else:
        btc_price=0.
    if not isinstance(saved,dict):
        raise ValueError("Load existing saved portfolio before adding a trade")
    if not isinstance(saved.get("rows"),list):
        raise ValueError("Original purchase ledger is missing")
    portfolio=copy.deepcopy(saved)
    portfolio.setdefault(SALES_KEY,[])
    if not isinstance(portfolio[SALES_KEY],list):
        raise ValueError("Sales ledger corrupted")
    # Fail before addition if the original saved ledger is inconsistent
    positions=portfolio_positions(portfolio)
    if side=="BUY" and consideration+fee>positions["cash_remaining_aud"]+.005:
        raise ValueError("BUY exceeds recorded remaining AUD cash")
    if side=="SELL" and qty>positions["ibit_units" if asset=="ASX:IBIT" else "direct_btc"]+1e-8:
        raise ValueError("SELL exceeds net recorded holdings")
    trade_id=uuid.uuid4().hex
    if side=="BUY":
        portfolio["rows"].append({
            "Date":day.strftime("%d/%m/%y"),"Asset":asset,
            "AUD Spent":consideration,"Brokerage / Fee AUD":fee,
            "Units / BTC Received":qty,"BTC AUD Price":btc_price,
            "Transaction ID":trade_id,
            "Notes":str(note).strip()[:300],
        })
    else:
        portfolio[SALES_KEY].append({
            "Date":day.strftime("%d/%m/%y"),"Asset":asset,
            "Units Sold":qty,"AUD Proceeds":consideration,
            "Brokerage / Fee AUD":fee,"Transaction ID":trade_id,
            "Notes":str(note).strip()[:300],
        })
    after=portfolio_positions(portfolio)
    portfolio["capital_remaining_aud"]=after["cash_remaining_aud"]
    return portfolio,after


def append_with_stale_guard(original,fresh,**kwargs):
    """Never overwrite transactions recorded by another Streamlit session."""
    original_buys,original_sells=_read_ledger(original)
    current_buys,current_sells=_read_ledger(fresh)
    if original_buys!=current_buys or original_sells!=current_sells:
        raise ValueError("Portfolio changed since page load; refresh before adding transaction")
    if (original.get("starting_capital_aud",500000.)
            !=fresh.get("starting_capital_aud",500000.)):
        raise ValueError("Portfolio capital changed since page load; refresh")
    return append_executed_trade(fresh,**kwargs)


def merge_legacy_purchase_editor(original,fresh,*,edited_buys,starting_capital_aud):
    """Persist previous Portfolio editor changes WITHOUT deleting new sales.

    This deliberately rejects conflicting stale purchases and sale edits.
    The older editor may modify historical purchases, but NEVER silently
    overwrites `sales`. A dedicated Cycle Trading editor controls sales.
    """
    prior_buys,prior_sells=_read_ledger(original)
    current_buys,current_sells=_read_ledger(fresh)
    if prior_buys!=current_buys or prior_sells!=current_sells:
        raise ValueError("Portfolio changed elsewhere; refresh before saving legacy purchase edits")
    if not isinstance(edited_buys,list):
        raise ValueError("Edited purchases must be a list")
    result=copy.deepcopy(fresh)
    result["rows"]=copy.deepcopy(edited_buys)
    result["starting_capital_aud"]=numeric(
        starting_capital_aud,label="Starting capital",allow_zero=True)
    status=portfolio_positions(result)
    result["capital_remaining_aud"]=status["cash_remaining_aud"]
    return result
