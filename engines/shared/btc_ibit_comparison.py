"""Read-only ASX:IBIT versus BTC/AUD indexed historical comparison.

Separate Yahoo daily close series; not synchronized intraday or execution prices.
"""
from __future__ import annotations

import datetime as dt
import math

import pandas as pd
import requests

ENDPOINTS = ("https://query1.finance.yahoo.com/v8/finance/chart/",
             "https://query2.finance.yahoo.com/v8/finance/chart/")


def parse_daily_closes(payload, expected_symbol, expected_currency):
    item = payload["chart"]["result"][0]
    meta = item["meta"]
    if meta.get("symbol", "").upper() != expected_symbol or meta.get("currency", "").upper() != expected_currency:
        raise ValueError("Unexpected symbol/currency in comparison price series")
    stamps = item.get("timestamp") or []
    closes = item["indicators"]["quote"][0]["close"]
    rows = {}
    for timestamp, value in zip(stamps, closes):
        try:
            price = float(value)
            date = dt.datetime.fromtimestamp(int(timestamp), dt.timezone.utc).date()
        except (TypeError, ValueError, OverflowError, OSError):
            continue
        if math.isfinite(price) and price > 0:
            rows[date] = price
    if not rows:
        raise ValueError("No valid dated closes")
    return pd.Series(rows, dtype="float64").sort_index()


def fetch_daily_series(symbol, currency, *, timeout=12):
    errors = []
    for endpoint in ENDPOINTS:
        try:
            response = requests.get(
                endpoint + symbol,
                params={"interval": "1d", "range": "1mo"},
                headers={"User-Agent": "Mozilla/5.0 (BTC AUD IBIT research comparison)"},
                timeout=timeout,
            )
            response.raise_for_status()
            return parse_daily_closes(response.json(), symbol, currency)
        except (requests.RequestException, ValueError, TypeError, KeyError, IndexError) as exc:
            errors.append(type(exc).__name__)
    raise ValueError(f"{symbol} comparison feed unavailable: {', '.join(errors)}")


def build_indexed_comparison(btc_aud, ibit_aud, *, sessions=10):
    """Join on common dated sessions; index each series to 100 on first common date."""
    joined = pd.concat(
        [btc_aud.rename("BTC/AUD"), ibit_aud.rename("ASX:IBIT")], axis=1,
        join="inner",
    ).dropna().tail(sessions)
    if len(joined) < 2 or (joined.iloc[0] <= 0).any():
        raise ValueError("Not enough overlapping valid daily observations")
    indexed = joined.div(joined.iloc[0]).mul(100.0)
    return joined, indexed


def show_btc_ibit_comparison(*, expanded=False):
    import streamlit as st

    with st.expander("📈 BTC/AUD vs ASX:IBIT — last 10 trading sessions", expanded=expanded):
        st.caption("Both lines indexed to 100 on the first common date. This compares percentage movement, not unit prices.")
        @st.cache_data(ttl=1800, show_spinner=False)
        def load():
            return (fetch_daily_series("BTC-AUD", "AUD"),
                    fetch_daily_series("IBIT.AX", "AUD"))
        try:
            btc, ibit = load()
            actual, indexed = build_indexed_comparison(btc, ibit)
        except (ValueError, KeyError, TypeError, IndexError, requests.RequestException) as exc:
            st.warning(f"Comparison chart unavailable: {exc}. No historical values are invented.")
            return
        st.line_chart(indexed, x_label="Date (UTC calendar date)", y_label="Indexed close (first = 100)")
        last = actual.iloc[-1]
        first = actual.iloc[0]
        a, b = st.columns(2)
        a.metric("BTC/AUD latest dated close", f"A${last['BTC/AUD']:,.0f}",
                 delta=f"{(last['BTC/AUD']/first['BTC/AUD']-1)*100:+.1f}% over period")
        b.metric("ASX:IBIT latest dated close", f"A${last['ASX:IBIT']:,.2f}",
                 delta=f"{(last['ASX:IBIT']/first['ASX:IBIT']-1)*100:+.1f}% over period")
        st.caption(
            f"Last shared UTC calendar date: {actual.index[-1]} • "
            "Yahoo Finance daily closes, delayed and indicative. BTC trades 24/7; "
            "ASX:IBIT trades only during ASX sessions. The two closes are NOT simultaneous; "
            "daily deviations do not by themselves establish tracking error. "
            "Not a live execution quote or trading signal."
        )
