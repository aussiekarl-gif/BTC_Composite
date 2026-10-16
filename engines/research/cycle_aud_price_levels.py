"""Read-only observed AUD Bitcoin cycle high/low and interval percentage.

Uses historical DAILY BTC/USD CLOSES multiplied by AUD per USD from
Frankfurter on/before the SAME historical date. Never converts a 2025
top using today's exchange rate. Non-forward-looking description
only: maxima/minima are identified in hindsight as of the most recent
completed BTC close, not actionable trade signals.

Current cycle starts at the supplied verified halving date (2024 default for historical tests).
'Current cycle bottom' = lowest observed BTC/AUD daily close AFTER
the highest observed BTC/AUD daily close in that cycle, not necessarily
the absolute low since the halving or user-reported intraday USD low.
"""
from __future__ import annotations

import math

import pandas as pd

from engines.research.cycle_trading_dashboard_model import (
    LAST_CONFIRMED_HALVING, _coerce_daily_prices,
)

MAX_FX_LAG_DAYS=5


def observed_aud_cycle_levels(btc_price_usd, dated_fx, *,
                              start=LAST_CONFIRMED_HALVING,
                              asof=None, max_fx_lag_days=MAX_FX_LAG_DAYS):
    """Return nonforecast cycle peak, postpeak trough and price-range position.

    FX is always the latest ON/BEFORE the BTC close date; never a
    future fx rate or a single modern FX rate for every historic day.
    Missing/stale historical FX fails closed (no misleading AUD top).
    """
    usd=_coerce_daily_prices(btc_price_usd)
    start=pd.Timestamp(start)
    if start.tzinfo is None:start=start.tz_localize("UTC")
    else:start=start.tz_convert("UTC")
    start=start.normalize()
    if asof is not None:
        end=pd.Timestamp(asof)
        if end.tzinfo is None:end=end.tz_localize("UTC")
        else:end=end.tz_convert("UTC")
        usd=usd.loc[:end.normalize()]
    usd=usd.loc[start:]
    if len(usd)<2:
        raise ValueError("Insufficient observed cycle price history")
    if not isinstance(dated_fx,pd.DataFrame) or "aud_per_usd" not in dated_fx:
        raise ValueError("Historical dated AUD/USD exchange rates unavailable")
    fx=dated_fx["aud_per_usd"].copy()
    if not isinstance(fx.index,pd.DatetimeIndex) or fx.empty:
        raise ValueError("Historical FX dates missing")
    fx.index=pd.to_datetime(fx.index,utc=True).normalize()
    if fx.index.has_duplicates:raise ValueError("Duplicate historical FX dates")
    fx=pd.to_numeric(fx,errors="coerce").sort_index().dropna()
    if fx.empty or not (fx>0).all() or not all(math.isfinite(z) for z in fx):
        raise ValueError("Invalid historical AUD/USD rates")
    # Calendar-date alignment and source-date vintage for weekends.
    aligned=fx.reindex(usd.index,method="ffill")
    source_dates=pd.Series(fx.index,index=fx.index).reindex(
        usd.index,method="ffill")
    if aligned.isna().any() or source_dates.isna().any():
        raise ValueError("Missing historical AUD/USD before cycle BTC price")
    lag=(usd.index.to_series(index=usd.index)-source_dates).dt.days
    if lag.gt(max_fx_lag_days).any() or lag.lt(0).any():
        raise ValueError("Stale or future AUD/USD rates in cycle observations")
    aud=usd.mul(aligned)
    if aud.isna().any() or not (aud>0).all():
        raise ValueError("Invalid calculated historical BTC/AUD closes")

    top_date=aud.idxmax()
    top=float(aud.loc[top_date])
    post_peak=aud.loc[top_date:]
    if len(post_peak)<2:
        raise ValueError("No recorded period after observed top yet")
    bottom_date=post_peak.idxmin()
    bottom=float(post_peak.loc[bottom_date])
    if bottom>=top:
        raise ValueError("No lower cycle trough after observed top yet")
    last_date=aud.index[-1]
    current=float(aud.iloc[-1])
    pct_from_top=(current/top-1)*100
    pct_from_bottom=(current/bottom-1)*100
    position=(current-bottom)/(top-bottom)*100
    return {
        "scope":f"Since {start.date()} halving; lowest observed daily close AFTER the peak",
        "source":"Daily BTC/USD closes × same-date-or-prior Frankfurter USD→AUD rate",
        "start_date":str(start.date()),
        "asof_date":str(last_date.date()),
        "cycle_top_date":str(top_date.date()),
        "cycle_top_aud":round(top,2),
        "cycle_bottom_date":str(bottom_date.date()),
        "cycle_bottom_aud":round(bottom,2),
        "last_price_aud":round(current,2),
        "pct_change_from_top":round(pct_from_top,2),
        "pct_change_from_bottom":round(pct_from_bottom,2),
        "position_between_low_high_pct":round(position,2),
        "observation_only":True,
        "forecast":False,
        "fx_max_lag_days_observed":int(lag.max()),
        "record_count":len(aud),
        "comparison_note":(
            "Daily closing prices in AUD, not intraday lows/highs. "
            "An observed current-cycle bottom is provisional and may fall lower."
        ),
    }
