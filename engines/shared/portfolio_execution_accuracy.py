"""Read-only, currency-safe 2026 BTC portfolio entry accuracy.

The Portfolio screen stores ASX:IBIT as an estimated BTC-equivalent
economic exposure (not actual custody of BTC). Direct BTC records use
their actual entered quantity. This module never writes user data.

BTC/AUD reference: AUD cash paid including fees / BTC exposure.
BTC/USD reference: sum(AUD cash paid * USD-per-AUD FX at each trade date)
/ BTC exposure. Crucially: never compare AUD acquisition cost against
USD cycle low, nor use today's FX for historical trades.

Reference lows are manual, provisional and evaluated *with hindsight*;
they are NOT decision rules or independently verified cycle bottoms.
"""
from __future__ import annotations

import math

import numpy as np
import pandas as pd

START_2026 = pd.Timestamp("2026-01-01")
DEFAULT_REFERENCE_USD = 58_000.0


def _positive_finite(value):
    try:
        v = float(value)
    except (ValueError, TypeError):
        return None
    return v if math.isfinite(v) and v > 0 else None


def _nonnegative_finite(value):
    try:
        v = float(value)
    except (ValueError, TypeError):
        return None
    return v if math.isfinite(v) and v >= 0 else None


def _day(value):
    if value is None or pd.isna(value):
        return None
    if isinstance(value, str):
        value = value.strip()
        for fmt in ("%d/%m/%y", "%d/%m/%Y", "%Y-%m-%d"):
            try:
                d = pd.to_datetime(value, format=fmt, errors="raise")
                return d.tz_localize(None).normalize()
            except (TypeError, ValueError):
                continue
        return None
    try:
        d = pd.Timestamp(value)
        if pd.isna(d):
            return None
        if d.tz is not None:
            d = d.tz_convert("UTC").tz_localize(None)
        return d.normalize()
    except (ValueError, TypeError):
        return None


def _normalise_fx(usd_per_aud):
    if usd_per_aud is None:
        return pd.Series(dtype=float)
    fx = pd.Series(usd_per_aud, dtype="object").copy()
    fx.index = pd.to_datetime(fx.index, utc=True, errors="coerce")
    fx = fx[fx.index.notna()]
    fx.index = fx.index.tz_convert(None).normalize()
    fx = pd.to_numeric(fx, errors="coerce")
    fx = fx[np.isfinite(fx) & fx.gt(0)]
    return fx.sort_index().loc[lambda s: ~s.index.duplicated(keep="last")]


def fx_rate_asof(usd_per_aud, trade_date, *, max_lag_days=7):
    """Use *only* business-day rates published ON/BEFORE trade date."""
    rates = _normalise_fx(usd_per_aud)
    stamp = _day(trade_date)
    if stamp is None or rates.empty:
        return None
    eligible = rates.loc[rates.index <= stamp]
    if eligible.empty:
        return None
    ts = eligible.index[-1]
    if (stamp-ts).days > max_lag_days:
        return None
    return float(eligible.iloc[-1])


def calculate_portfolio_entry_error(
    rows,
    *,
    reference_price,
    reference_currency="USD",
    usd_per_aud=None,
    start_date=START_2026,
):
    """Calculate fee-inclusive weighted average acquisition price for 2026.

    Accepts the existing Streamlit *calculated* rows (BTC Equivalent populated),
    not the raw user ledger. Any dated positive-cash purchase missing BTC
    exposure or valid FX causes a clearly unavailable metric, rather than
    silently favouring only correctly priced transactions.
    """
    if reference_currency not in {"USD", "AUD"}:
        raise ValueError("Reference currency must be USD or AUD")
    ref=_positive_finite(reference_price)
    if ref is None:
        raise ValueError("Reference bottom price must be strictly positive")
    if not isinstance(rows, pd.DataFrame):
        raise TypeError("Portfolio rows must be a DataFrame")
    required={"Date", "AUD Spent", "Brokerage / Fee AUD", "BTC Equivalent"}
    if not required.issubset(rows.columns):
        raise ValueError("Missing required calculated portfolio columns")

    start=_day(start_date)
    if start is None:
        raise ValueError("Invalid start date")

    total_aud=0.0
    total_usd=0.0
    btc=0.0
    purchased_rows=0
    skipped_earlier=0
    issues=[]
    rates=_normalise_fx(usd_per_aud)
    for n, (_,row) in enumerate(rows.iterrows(),start=1):
        spent=_nonnegative_finite(row["AUD Spent"])
        fee=_nonnegative_finite(row["Brokerage / Fee AUD"])
        quantity=_positive_finite(row["BTC Equivalent"])
        trade_date=_day(row.get("_purchase_date",row["Date"]))
        if spent is None or fee is None:
            issues.append(f"Row {n}: invalid AUD amount or brokerage.")
            continue
        if spent==0 and (quantity is None or quantity==0):
            continue
        # Do not count old synthetic-history purchases in real 2026 portfolio.
        if trade_date is None:
            issues.append(f"Row {n}: missing or invalid purchase date.")
            continue
        if trade_date < start:
            skipped_earlier+=1
            continue
        if spent <= 0 or quantity is None:
            issues.append(f"Row {n}: missing AUD consideration or BTC-equivalent quantity.")
            continue
        cash=spent+fee
        total_aud+=cash
        btc+=quantity
        purchased_rows+=1
        if reference_currency=="USD":
            fx=fx_rate_asof(rates,trade_date)
            if fx is None:
                issues.append(f"Row {n}: USD/AUD FX unavailable on or before {trade_date.date()}.")
            else:
                total_usd+=cash*fx

    # No misleading partial result if some purchase costs or FX were missing.
    average_aud=total_aud/btc if btc>0 and not issues else None
    average_reference=(
        (total_usd/btc if reference_currency=="USD" else average_aud)
        if btc>0 and not issues else None
    )
    error_pct=(100*(average_reference/ref-1)
               if average_reference is not None else None)
    return {
        "since":str(start.date()),
        "reference_currency":reference_currency,
        "reference_bottom":ref,
        "purchase_rows":purchased_rows,
        "excluded_pre2026_rows":skipped_earlier,
        "btc_equivalent":btc,
        "aud_paid_including_fees":total_aud,
        "weighted_average_aud":average_aud,
        "weighted_average_in_reference_currency":average_reference,
        "error_pct":error_pct,
        "within_25pct": (abs(error_pct)<=25 if error_pct is not None else None),
        "issues":issues,
        "provisional_reference":True,
        "measure":"BTC-equivalent weighted acquisition-price error; buys only.",
    }
