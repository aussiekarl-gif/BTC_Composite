"""Indicative ASX:IBIT unit sizing beside BTC DCA recommendations.

Presentation only: never modifies model DCA decisions or submits orders.
"""
from __future__ import annotations

import math

from engines.research.ibit_quote import fetch_ibit_quote


def estimate_ibit_units(amount_aud, quote_aud, *, brokerage_aud=0.0):
    """Whole ASX:IBIT units affordable after an optional brokerage allowance."""
    try:
        amount, price, fee = map(float, (amount_aud, quote_aud, brokerage_aud))
    except (TypeError, ValueError, OverflowError):
        return None
    if not all(map(math.isfinite, (amount, price, fee))) or amount < 0 or price <= 0 or fee < 0:
        return None
    return max(0, math.floor(max(0.0, amount - fee) / price))


def show_ibit_dca_equivalent(amount_aud, *, label="Recommended DCA"):
    """Render price + estimated units; fail visibly closed on missing quote."""
    import streamlit as st

    @st.cache_data(ttl=900, show_spinner=False)
    def cached_quote():
        return fetch_ibit_quote()

    try:
        quote = cached_quote()
    except (ValueError, OSError) as exc:
        st.warning(f"ASX:IBIT quote unavailable — cannot calculate ETF units ({exc}).")
        st.caption("Check ASX:IBIT in your broker; no US-listed IBIT quote is substituted.")
        return
    price = quote["price_aud"]
    units = estimate_ibit_units(amount_aud, price)
    left, right = st.columns(2)
    left.metric("ASX:IBIT indicative price (AUD/unit)", f"A${price:,.2f}")
    right.metric(f"{label} — whole IBIT units", f"{units:,}" if units is not None else "Unavailable")
    st.caption(
        f"ASX:IBIT delayed indicative quote • {quote['timestamp_utc']} UTC • "
        f"{quote['provider']}. Units = floor(AUD DCA ÷ indicative price), "
        "excluding brokerage, spread and slippage. Confirm executable ASX price "
        "and fees with your broker before ordering."
    )
