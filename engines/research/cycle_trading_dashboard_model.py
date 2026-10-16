"""Read-only Streamlit adapter for BTC cycle trading Research.

No trading, persistence writes, or Production module imports.
Shows user-owned BTC-equivalent from the authoritative *read* portfolio,
without inventing ETF backing or tax status. Current recommendations
are illustrations only, using lagged price/200WMA and explicit cash.
"""
from __future__ import annotations

import math
import pandas as pd
import numpy as np

from engines.shared.portfolio_transactions import portfolio_positions

from engines.research.day500_aftertax_reinvestment import (
    WMA_DYNAMIC_STYLES, simulate_roundtrip,
)
from engines.research.top_signal_horse_race import HALVINGS


LAST_CONFIRMED_HALVING=pd.Timestamp("2024-04-20",tz="UTC")
USER_REPORTED_2026_LOW_USD=57717.
FEE_AUD=3.


def _cash(x,default=0.):
    try:
        num=float(x)
    except (ValueError,TypeError):
        return default
    return num if math.isfinite(num) and num>=0 else default


def portfolio_snapshot(saved):
    """Net recorded actual holdings, including executed sale ledger.

    Return status rather than fake positions if purchase / sale rows are
    missing or inconsistent. Keep dashboard's stable view fields.
    """
    try:
        balance=portfolio_positions(saved)
    except (ValueError,TypeError,KeyError) as exc:
        return {"valid":False,"reason":str(exc)}
    rows=saved.get("rows",[])
    sold=saved.get("sales",[])
    avg=(balance["spent_aud"]+balance["fees_aud"])/balance["btc_equivalent_estimate"] if (
        balance["btc_equivalent_estimate"] and not sold) else None
    return {
        "valid":True,"rows":len(rows),"sales":len(sold),
        "unpriced_or_unknown_rows":balance["missing_exposure_lots"],
        "capital_aud":balance["starting_capital_aud"],
        "spent_aud":balance["spent_aud"],
        "sell_proceeds_aud":balance["sell_proceeds_aud"],
        "fees_aud":balance["fees_aud"],
        "cash_remaining_aud":balance["cash_remaining_aud"],
        "btc_equivalent":balance["btc_equivalent_estimate"],
        "ibit_units":balance["ibit_units"],
        "direct_btc":balance["direct_btc"],
        "approx_average_cost_aud_per_btc":avg,
        "has_sales":balance["has_sales"],
    }


def portfolio_buy_error_from_reported_low(saved,fx,*,low_usd=USER_REPORTED_2026_LOW_USD):
    """Historical purchase VWAP in USD, user-reported intraday trough.

    Uses actual saved AUD trade values plus recorded fee, estimated
    BTC-equivalent exposure, and FX strictly BEFORE every purchase.
    Never backfills missing BTC price or FX; returns no result on
    incomplete records, never a misleading partial average.
    """
    if not isinstance(saved,dict) or not isinstance(saved.get("rows"),list):
        return {"available":False,"reason":"No saved purchase records"}
    if (not isinstance(fx,pd.DataFrame) or fx.empty
            or "aud_per_usd" not in fx):
        return {"available":False,"reason":"Historical USD/AUD rates unavailable"}
    if not math.isfinite(low_usd) or low_usd<=0:
        raise ValueError("Low-price benchmark must be positive")
    cost_usd=btc_eq=0.
    valid=0
    for item in saved["rows"]:
        if not isinstance(item,dict):
            return {"available":False,"reason":"Invalid saved purchase row"}
        raw_date=str(item.get("Date","")).strip()
        date=None
        for fmt in ("%d/%m/%y","%d/%m/%Y","%Y-%m-%d"):
            try:
                date=pd.Timestamp(pd.to_datetime(raw_date,format=fmt)).tz_localize("UTC")
                break
            except (ValueError,TypeError):
                pass
        if date is None:
            return {"available":False,"reason":"Missing or malformed purchase date"}
        eligible=fx.loc[fx.index<date]
        if eligible.empty or (date-eligible.index[-1]).days>7:
            return {"available":False,"reason":"Purchase date FX not historically available"}
        rate=float(eligible.iloc[-1]["aud_per_usd"])
        if rate<=0 or not math.isfinite(rate):
            return {"available":False,"reason":"Invalid historical FX"}
        asset=str(item.get("Asset","")).strip()
        aud=_cash(item.get("AUD Spent"))
        fee=_cash(item.get("Brokerage / Fee AUD"))
        if asset=="ASX:IBIT":
            historic=_cash(item.get("BTC AUD Price"))
            qty=aud/historic if historic>0 else 0.
        elif asset=="Direct BTC":
            qty=_cash(item.get("Units / BTC Received"))
        else:
            qty=0.
        if aud<=0 or qty<=0:
            return {"available":False,
                    "reason":"At least one purchase lacks a valid BTC-equivalent or AUD cost"}
        cost_usd+=(aud+fee)/rate
        btc_eq+=qty
        valid+=1
    if btc_eq<=0:
        return {"available":False,"reason":"No recorded BTC-equivalent purchases"}
    avg=cost_usd/btc_eq
    return {
        "available":True,
        "purchases_count":valid,
        "btc_equivalent_purchased":round(btc_eq,8),
        "total_usd_cost":round(cost_usd,2),
        "effective_avg_usd_per_btc":round(avg,2),
        "error_above_user_reported_low_pct":round(100*(avg/low_usd-1),2),
        "reference_low_usd":float(low_usd),
        "reference_low_kind":"User-reported intraday 30 Jun 2026 — provisional",
        "limit":"Approximate BTC-equivalent ETF exposure from saved trades, not direct BTC; charges included, ETF tracking and FX spread excluded.",
    }



def _coerce_daily_prices(price):
    if isinstance(price,pd.DataFrame):
        if "price_usd" in price.columns:
            price=price["price_usd"]
        elif "btc_usd" in price.columns:
            price=price["btc_usd"]
        else:
            raise ValueError("Missing BTC/USD column")
    if not isinstance(price,pd.Series) or not isinstance(price.index,pd.DatetimeIndex):
        raise ValueError("Need historical dated BTC/USD prices")
    p=pd.to_numeric(price,errors="coerce").dropna().sort_index()
    if p.index.tz is None:p.index=p.index.tz_localize("UTC")
    else:p.index=p.index.tz_convert("UTC")
    p.index=p.index.normalize()
    if p.index.has_duplicates:
        raise ValueError("Duplicate daily historical prices")
    if not p.gt(0).all():
        raise ValueError("Invalid BTC/USD price")
    return p


def build_dashboard_market(price,fx,*,asof=None,confirmed_halving_date=None):
    """200 prior, 7-days-apart BTC closes; no current close in the SMA.

    Archive and public providers merged ONLY with newer dates after
    verifying overlap in the outer Streamlit loader.
    """
    p=_coerce_daily_prices(price)
    if len(p)<1401:
        raise ValueError("Not enough daily history for strict prior 200WMA")
    if asof is not None:
        when=pd.Timestamp(asof)
        when=when.tz_localize("UTC") if when.tzinfo is None else when.tz_convert("UTC")
        p=p.loc[:when.normalize()]
    if len(p)<1401:
        raise ValueError("No sufficient observations by selected date")
    last=p.index[-1]
    i=len(p)-1
    # Require continuous 200 *calendar* weeks, no silent weekend holes
    dates=[last-pd.Timedelta(days=1+7*j) for j in range(200)]
    missing=[t for t in dates if t not in p.index]
    if missing:
        raise ValueError("Missing dates in 200-week moving average history")
    previous=p.loc[dates]
    ma=float(previous.mean())
    px=float(p.iloc[-1])
    previous_close=float(p.iloc[-2])
    ratio=previous_close/ma
    fx_val=None
    fx_date=None
    if isinstance(fx,pd.DataFrame) and not fx.empty and "aud_per_usd" in fx:
        available=fx.loc[fx.index<last]
        if not available.empty and (last-available.index[-1]).days<=7:
            fx_val=float(available["aud_per_usd"].iloc[-1])
            fx_date=str(available.index[-1].date())
    # Historical research defaults to the known 2024 epoch. Live callers
    # should pass the newly verified epoch-start block date after 2028.
    halving=LAST_CONFIRMED_HALVING
    if confirmed_halving_date is not None:
        candidate=pd.Timestamp(confirmed_halving_date)
        candidate=(candidate.tz_localize("UTC") if candidate.tzinfo is None
                   else candidate.tz_convert("UTC")).normalize()
        if candidate<LAST_CONFIRMED_HALVING or candidate>last:
            raise ValueError("Confirmed halving cannot precede 2024 or postdate the observed BTC close")
        halving=candidate
    age=(last-halving).days
    state=("Accumulation observation only" if age>560
           else "Day-500 staged distribution observation" if age>=500
           else "Before day-500 distribution window")
    return {
        "asof_date":str(last.date()),
        "btc_price_usd":px,
        "previous_close_usd":previous_close,
        "prior_200wma_usd":ma,
        "prior_close_vs_200wma_pct":100*(ratio-1),
        "previous_close_below_200wma":bool(previous_close<ma),
        "usd_aud_prior":fx_val,
        "fx_source_date":fx_date,
        "btc_price_aud_estimate":px*fx_val if fx_val else None,
        "halving_day":age,
        "halving_date":str(halving.date()),
        "day500_date":str((halving+pd.Timedelta(days=500)).date()),
        "day560_date":str((halving+pd.Timedelta(days=560)).date()),
        "phase":state,
        "price_history":p,
    }


def planned_buy_order(market,*,cash_available,style="adaptive_recovery",
                      min_ticket_aud=100.):
    """Prior observations only, 200WMA entry; illustrative not broker order."""
    if style not in WMA_DYNAMIC_STYLES:
        raise ValueError("Unknown dynamic allocation style")
    p=market["price_history"]
    last=p.index[-1]
    i=len(p)-1
    if i<64:raise ValueError("Insufficient price observations")
    ratio=market["previous_close_usd"]/market["prior_200wma_usd"]
    cash=_cash(cash_available)
    if market["usd_aud_prior"] is None:
        return {"action":"DATA UNAVAILABLE","reason":"AUD conversion is not available",
                "amount_aud":0.,"btc_equivalent_estimate":None}
    # A 200WMA buyback assumes prior distribution proceeds; don't
    # automatically treat a 2026 purchaser as a historical 2025 seller.
    if not market["previous_close_below_200wma"]:
        return {"action":"WAIT / REVIEW","reason":"Prior close is not below 200WMA; initial buyback trigger not met. Once triggered, an active DCA phase may continue above 200WMA.",
                "amount_aud":0.,"btc_equivalent_estimate":0.}
    if style=="adaptive_value":
        fraction=(.10 if ratio<=.85 else .035)
    else:
        fraction=.025
    gross=cash*fraction
    if gross<max(min_ticket_aud,FEE_AUD*2):
        return {"action":"NO TRADE","reason":"Illustrative amount is below minimum ticket",
                "amount_aud":0.,"btc_equivalent_estimate":0.}
    btc_aud=market["btc_price_aud_estimate"]
    return {
        "action":"ILLUSTRATIVE BUY",
        "reason":"Unconfirmed live order: WMA gate and prior-day illustrative DCA sizing only",
        "amount_aud":round(gross,2),
        "fee_aud":FEE_AUD,
        "btc_equivalent_estimate":round((gross-FEE_AUD)/btc_aud,8),
        "pct_available_cash":round(100*fraction,2),
        "not_a_live_model_instruction":True,
    }


def historical_one_scenario(history,fx,*,cycle="2021",
                            seller="dynamic_90pct_holdback20pct",
                            style="adaptive_recovery"):
    if cycle not in ("2017","2021","2025"):
        raise ValueError("2013 excluded from primary comparison")
    if seller not in ("fixed_525_to_560","dynamic_90pct",
                      "dynamic_90pct_holdback20pct"):
        raise ValueError("Unknown seller")
    if style not in WMA_DYNAMIC_STYLES:
        raise ValueError("Unknown buyback")
    price=_coerce_daily_prices(history)
    halving=dict(zip(("2013","2017","2021","2025"),HALVINGS))[cycle]
    cutoff=halving+pd.Timedelta(days=1150)
    end=min(cutoff,price.index[-1])
    if end<=halving+pd.Timedelta(days=560):
        raise ValueError("Not enough data to measure completed exit")
    result=simulate_roundtrip(price,fx,halving,end,
                              seller=seller,gate=.40,
                              entry_mode="below_200wma",
                              buyback_style=style)
    return {**result,
            "cycle":cycle,
            "end_date":str(end.date()),
            "complete_cycle":bool(end==cutoff),
            "historical_only":True}
