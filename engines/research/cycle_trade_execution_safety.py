"""Conservative, read-only helpers for Cycle Trading automation.

Signals are daily observations but DCA tranches are NOT daily mandates.
The current research allocation is one tranche per seven calendar days,
across recorded BUY and SELL executions. Execution still manual.

Historical BTC/AUD purchase reference is a market observation only, not
a historical ASX:IBIT fill price or official ETF NAV.
"""
from __future__ import annotations

from datetime import date, datetime
import math
import pandas as pd

from engines.shared.portfolio_transactions import parse_date

TRANCHE_COOLDOWN_DAYS=7
MAX_BTC_REFERENCE_LAG_DAYS=2
MAX_FX_REFERENCE_LAG_DAYS=5


def last_executed_transaction(saved):
    """Read both legacy buys and saved sales; no ledger modification."""
    if not isinstance(saved,dict):
        return None
    observations=[]
    for side,key in (("BUY","rows"),("SELL","sales")):
        records=saved.get(key,[])
        if not isinstance(records,list):
            raise ValueError("Invalid persisted transaction records")
        for index,item in enumerate(records):
            if not isinstance(item,dict):
                raise ValueError("Invalid persisted transaction row")
            date_value=parse_date(item.get("Date"))
            observations.append((date_value,side,index))
    if not observations:
        return None
    day,side,index=max(observations)
    return {"date":day,"side":side,"row_index":index}


def cooldown_check(saved,*,today,days=TRANCHE_COOLDOWN_DAYS):
    """Fail safe on user-recorded trades from the past 7 days.

    A market WATCH remains visible, while suggested executed action
    becomes HOLD; users cannot accidentally DCA multiple times per week.
    """
    d=pd.Timestamp(today).date()
    if not isinstance(days,int) or days<1:
        raise ValueError("Cooldown must be a positive number of days")
    recent=last_executed_transaction(saved)
    if not recent:
        return {"allowed":True,"last_trade_date":None,
                "next_eligible_date":None,"reason":None}
    age=(d-recent["date"]).days
    if age<0:
        raise ValueError("Portfolio has transaction dated after evaluation date")
    next_date=recent["date"]+pd.Timedelta(days=days)
    return {
        "allowed":age>=days,
        "last_trade_date":str(recent["date"]),
        "next_eligible_date":str(next_date),
        "reason":(
            f"Last recorded {recent['side']} was {recent['date']}; "
            f"next weekly DCA tranche is eligible on {next_date} "
            "if the market condition still holds."
            if age<days else None
        ),
    }


def historical_btc_aud_reference(price_usd, fx_aud_per_usd, *,
                                 trade_date,max_price_lag_days=MAX_BTC_REFERENCE_LAG_DAYS,
                                 max_fx_lag_days=MAX_FX_REFERENCE_LAG_DAYS):
    """Date-appropriate reference with no future provider data.

    For trades backfilled into the history, NEVER re-use today's USD/AUD.
    Returns None on incomplete/stale input; edit form then requires
    manual entry of historical BTC/AUD reference.
    """
    if not isinstance(price_usd,pd.Series) or not isinstance(price_usd.index,pd.DatetimeIndex):
        return None
    if not isinstance(fx_aud_per_usd,pd.DataFrame) or "aud_per_usd" not in fx_aud_per_usd:
        return None
    try:
        target=pd.Timestamp(trade_date)
        target=target.tz_localize("UTC") if target.tzinfo is None else target.tz_convert("UTC")
        target=target.normalize()
        price=price_usd.sort_index()
        fx=fx_aud_per_usd["aud_per_usd"].sort_index()
        p=price.loc[price.index<=target]
        x=fx.loc[fx.index<=target]
        if p.empty or x.empty:
            return None
        price_date=p.index[-1]
        fx_date=x.index[-1]
        if target-price_date>pd.Timedelta(days=max_price_lag_days):
            return None
        if target-fx_date>pd.Timedelta(days=max_fx_lag_days):
            return None
        px=float(p.iloc[-1])
        rate=float(x.iloc[-1])
        if not all(math.isfinite(v) and v>0 for v in (px,rate)):
            return None
        return {
            "btc_aud_reference":round(px*rate,2),
            "btc_usd_close":round(px,2),
            "fx_aud_per_usd":round(rate,6),
            "price_date":str(price_date.date()),
            "fx_date":str(fx_date.date()),
            "trade_date":str(target.date()),
            "type":"Estimated historical BTC/AUD reference, not ETF fill",
        }
    except (TypeError,ValueError,KeyError):
        return None
