#!/usr/bin/env python3
"""
BTC Composite DCA Simulator (Risk Band Mapping)
=================================================
- Choose ANY start and end date (end_date > start_date).
- Define specific investment amounts for 10 risk bands (0.0–1.0).
- Frequency: Daily, Weekly, or Monthly. 
- Backtest from 2009 to the future (flat projection).
- Scrollable chart with TradingView-style slider.
"""

import datetime
from datetime import timedelta, timezone

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import requests
import streamlit as st

# ================================================================
# Data Fetcher (with future projection)
# ================================================================
@st.cache_data(ttl=3600)
def fetch_btc_history(start_date, end_date):
    """Fetch daily BTC prices. Extends with flat price for future dates."""
    url = "https://api.blockchain.info/charts/market-price?timespan=all&format=json&sampled=false"
    resp = requests.get(url, timeout=30)
    resp.raise_for_status()
    data = resp.json()["values"]

    prices = []
    for point in data:
        dt = datetime.datetime.fromtimestamp(point["x"], tz=timezone.utc)
        price = float(point["y"])
        if price > 0:
            prices.append({"date": dt, "price": price})

    df = pd.DataFrame(prices)
    df = df.set_index("date").sort_index()

    if start_date:
        df = df[df.index >= start_date]

    # Future projection (flat price)
    if end_date and end_date > df.index[-1]:
        last_price = df["price"].iloc[-1]
        last_date = df.index[-1]
        current_date = last_date + timedelta(days=1)
        future_dates = []
        while current_date <= end_date:
            future_dates.append(current_date)
            current_date += timedelta(days=1)
        if future_dates:
            future_df = pd.DataFrame(
                {"price": [last_price] * len(future_dates)},
                index=future_dates
            )
            df = pd.concat([df, future_df])

    if end_date:
        df = df[df.index <= end_date]

    return df


# ================================================================
# Core Simulation (with Risk Band Mapping)
# ================================================================
def simulate_dca(df, params):
    """
    params: dict with keys:
        frequency, day_of_week,
        fund_cheap, fund_expensive, composite_bias,
        risk_bands: list of (min_risk, max_risk, amount_aud)
    """
    data = df.copy()
    
    # --- Filter by frequency ---
    if params["frequency"] == "Weekly":
        data = data[data.index.dayofweek == params["day_of_week"]]
    elif params["frequency"] == "Monthly":
        data = data[data.index.day == 1]
    # Daily: all

    if data.empty:
        return pd.DataFrame(), {}

    # --- SMA & Fundamental Score ---
    sma_series = df["price"].rolling(window=200).mean()
    data["sma_200"] = sma_series.reindex(data.index).ffill()

    def calc_fundamental(price, sma):
        if sma <= 0:
            return 0.5
        ratio = price / sma
        if ratio <= params["fund_cheap"]:
            return 1.0
        if ratio >= params["fund_expensive"]:
            return 0.0
        return (params["fund_expensive"] - ratio) / (params["fund_expensive"] - params["fund_cheap"])

    data["f_score"] = data.apply(
        lambda row: calc_fundamental(row["price"], row["sma_200"]),
        axis=1,
    )
    data["composite"] = data["f_score"] * params["composite_bias"]
    data["composite"] = data["composite"].clip(0.0, 1.0)

    # --- Risk Band Mapping: assign AUD amount per period based on composite ---
    def get_band_amount(comp):
        for min_r, max_r, amount in params["risk_bands"]:
            if min_r <= comp <= max_r:
                return amount
        return 0.0

    data["aud_buy"] = data["composite"].apply(get_band_amount)

    # --- Run simulation ---
    btc_held = 0.0
    total_invested = 0.0
    trades = []

    for idx, row in data.iterrows():
        aud_buy = row["aud_buy"]
        if aud_buy > 0.01 and row["price"] > 0:
            btc_bought = aud_buy / row["price"]
            btc_held += btc_bought
            total_invested += aud_buy
        else:
            btc_bought = 0.0

        trades.append({
            "date": idx,
            "price": row["price"],
            "sma_200": row["sma_200"],
            "f_score": row["f_score"],
            "composite": row["composite"],
            "aud_buy": aud_buy,
            "btc_bought": btc_bought,
            "btc_held": btc_held,
            "total_invested": total_invested,
        })

    trade_df = pd.DataFrame(trades)
    if trade_df.empty:
        return trade_df, {}

    current_price = data["price"].iloc[-1]
    portfolio_value = btc_held * current_price
    avg_price = total_invested / btc_held if btc_held > 0 else 0

    summary = {
        "total_invested": total_invested,
        "btc_held": btc_held,
        "avg_price": avg_price,
        "current_price": current_price,
        "portfolio_value": portfolio_value,
        "return_pct": ((portfolio_value / total_invested) - 1) * 100 if total_invested > 0 else 0,
        "periods": len(trade_df),
        "final_composite": data["composite"].iloc[-1] if not data.empty else 0,
    }
    return trade_df, summary


# ================================================================
# Comparison Strategies (Equal DCA & Lump Sum)
# ================================================================
def compare_strategies(df, frequency, day_of_week, total_invested):
    """Equal DCA = exactly the same as our periodic buys, but 100% slice."""
    data = df.copy()
    if frequency == "Weekly":
        data = data[data.index.dayofweek == day_of_week]
    elif frequency == "Monthly":
        data = data[data.index.day == 1]

    if data.empty or total_invested == 0:
        return {}, {}

    periods = len(data)
    if periods == 0:
        return {}, {}

    equal_per_period = total_invested / periods

    # Equal DCA
    btc_equal = 0.0
    for idx, row in data.iterrows():
        if row["price"] > 0:
            btc_equal += equal_per_period / row["price"]
    current_price = data["price"].iloc[-1]
    port_equal = btc_equal * current_price
    return_equal = ((port_equal / total_invested) - 1) * 100 if total_invested > 0 else 0

    # Lump Sum (invest total_invested on first day)
    first_price = data["price"].iloc[0]
    btc_lump = total_invested / first_price if first_price > 0 else 0
    port_lump = btc_lump * current_price
    return_lump = ((port_lump / total_invested) - 1) * 100 if total_invested > 0 else 0

    equal_summary = {"btc": btc_equal, "invested": total_invested, "portfolio": port_equal, "return": return_equal}
    lump_summary = {"btc": btc_lump, "invested": total_invested, "portfolio": port_lump, "return": return_lump}
    return equal_summary, lump_summary


# ================================================================
# Streamlit UI
# ================================================================
st.set_page_config(page_title="BTC DCA Simulator (Risk Bands)", layout="wide")
st.title("₿ Bitcoin DCA Simulator (Risk Band Mapping)")
st.markdown(
    """
    Define **exactly how much** to invest per period for each risk band (0.0–1.0). 
    No formulas, no spread weeks – just your manual risk allocation.
    """
)

# --- SIDEBAR ---
with st.sidebar:
    st.header("📅 Frequency")
    frequency = st.selectbox("Repeat Purchase", ["Daily", "Weekly", "Monthly"], index=1)
    day_map = {"Monday": 0, "Tuesday": 1, "Wednesday": 2, "Thursday": 3, "Friday": 4, "Saturday": 5, "Sunday": 6}
    day_of_week = st.selectbox(
        "Day of Week",
        list(day_map.keys()),
        index=0,
        disabled=(frequency != "Weekly"),
    )
    selected_day = day_map[day_of_week] if frequency == "Weekly" else 0

    st.divider()
    st.header("🧠 Risk Curve Parameters")
    fund_cheap = st.slider(
        "Cheap Threshold (SMA multiple)",
        0.7, 1.3, 1.0, 0.01,
        help="Price/SMA ≤ this → Fundamental Score = 1.0 (max cheap).",
    )
    fund_expensive = st.slider(
        "Expensive Threshold (SMA multiple)",
        1.2, 2.5, 1.5, 0.01,
        help="Price/SMA ≥ this → Fundamental Score = 0.0 (max expensive).",
    )
    composite_bias = st.slider(
        "Composite Bias (Aggressiveness)",
        0.5, 1.5, 1.0, 0.05,
        help="Scale the final composite up (bullish) or down (bearish).",
    )

    st.divider()
    st.subheader("📊 Risk Band Investment Map")
    st.caption("Set the AUD amount to invest per period for each composite score range.")

    # Generate 10 bands: 0.0–0.1, 0.1–0.2, ..., 0.9–1.0
    risk_bands = []
    for i in range(10):
        low = round(i * 0.1, 1)
        high = round((i + 1) * 0.1, 1)
        if i == 9:
            high = 1.0  # Fix floating point
        label = f"{low:.1f}–{high:.1f}"
        # Default: risk 1.0 (expensive) -> $100, risk 0.0 (cheap) -> $1000, scaled linearly.
        default_amt = int(100 + (900 * (1 - (low + high) / 2)))
        amt = st.number_input(
            label,
            min_value=0,
            max_value=1_000_000,
            value=default_amt,
            step=50,
            key=f"band_{i}",
        )
        risk_bands.append((low, high, float(amt)))

    st.divider()
    st.subheader("📅 Date Range")
    genesis = datetime.datetime(2009, 1, 3, tzinfo=timezone.utc)
    today = datetime.datetime.now(timezone.utc)

    # START DATE: completely flexible, can go back to genesis
    start_date = st.date_input(
        "Start Date",
        value=genesis,
        min_value=genesis,
        max_value=today,
        help="Can be any date from 2009-01-03 to today.",
    )

    # END DATE: min_value = start_date (no arbitrary "today" lock!)
    end_date = st.date_input(
        "End Date",
        value=today + timedelta(days=90),
        min_value=start_date,
        help="Can be any date AFTER the start date (past, present, or future).",
    )

    st.caption("🔬 Data: blockchain.com. Future dates = flat projection (no price change).")

# --- Validation: Ensure start < end ---
if end_date <= start_date:
    st.error("❌ End Date must be after Start Date. Please adjust.")
    st.stop()

# --- Load Data ---
start_dt = datetime.datetime.combine(start_date, datetime.datetime.min.time(), tzinfo=timezone.utc)
end_dt = datetime.datetime.combine(end_date, datetime.datetime.max.time(), tzinfo=timezone.utc)
df = fetch_btc_history(start_dt, end_dt)
if df.empty:
    st.error("No data found. Try a wider range.")
    st.stop()

# --- Build Params ---
params = {
    "frequency": frequency,
    "day_of_week": selected_day,
    "fund_cheap": fund_cheap,
    "fund_expensive": fund_expensive,
    "composite_bias": composite_bias,
    "risk_bands": risk_bands,
}

# --- Run Simulations ---
trade_df, summary = simulate_dca(df, params)
if trade_df.empty:
    st.warning("No trades executed. Adjust frequency or date range.")
    st.stop()

# --- Get total invested for comparisons ---
total_invested_comp = summary["total_invested"]
equal_summary, lump_summary = compare_strategies(
    df, frequency, selected_day, total_invested_comp
)

# ================================================================
# METRICS CARDS
# ================================================================
st.subheader("📊 Your Risk-Band DCA Performance")
col1, col2, col3, col4, col5 = st.columns(5)
col1.metric("⏳ Periods", f"{summary['periods']}")
col2.metric("💰 Total Invested", f"${summary['total_invested']:,.0f} AUD")
col3.metric("₿ BTC Accumulated", f"{summary['btc_held']:.6f} BTC")
col4.metric("💹 Avg Price", f"${summary['avg_price']:,.2f} USD")
col5.metric("📈 Portfolio Value", f"${summary['portfolio_value']:,.0f} USD",
            delta=f"{summary['return_pct']:+.2f}%")

# ================================================================
# COMPARISON CARDS
# ================================================================
st.subheader("⚔️ Strategy Comparison (Same Total Invested)")
comp1, comp2, comp3 = st.columns(3)
with comp1:
    st.metric("🚀 Risk-Band (Yours)", f"${summary['portfolio_value']:,.0f} USD", f"{summary['return_pct']:+.2f}%")
with comp2:
    st.metric("📅 Equal DCA (Fixed $)", f"${equal_summary['portfolio']:,.0f} USD", f"{equal_summary['return']:+.2f}%")
with comp3:
    st.metric("💥 Lump Sum (Day 1)", f"${lump_summary['portfolio']:,.0f} USD", f"{lump_summary['return']:+.2f}%")

# ================================================================
# CHART – SCROLLABLE (TradingView-style) + Updated Colors
# ================================================================
st.subheader("📈 Portfolio Value, Price & Composite Over Time")
st.caption("🖱️ Drag the chart left/right to scroll, or use the slider below. Scroll to zoom.")

fig = go.Figure()

# Portfolio Value – BLUE
fig.add_trace(go.Scatter(
    x=trade_df["date"], y=trade_df["btc_held"] * trade_df["price"],
    mode="lines", name="Portfolio (USD)", line=dict(color="#3498DB", width=3)
))

# BTC Price – YELLOW
fig.add_trace(go.Scatter(
    x=trade_df["date"], y=trade_df["price"],
    mode="lines", name="BTC Price (USD)", line=dict(color="#F1C40F", width=2, dash="dot"),
    yaxis="y2"
))

# Total Invested – GREEN
fig.add_trace(go.Scatter(
    x=trade_df["date"], y=trade_df["total_invested"],
    mode="lines", name="Total Invested (USD)", line=dict(color="#2ECC71", width=2, dash="dash")
))

# Composite Score – RED
fig.add_trace(go.Scatter(
    x=trade_df["date"], y=trade_df["composite"],
    mode="lines", name="Composite Score (0-1)", line=dict(color="#E74C3C", width=2, dash="dot"),
    yaxis="y3"
))

# --- UPDATED LAYOUT: Scrollable + Pan ---
fig.update_layout(
    dragmode="pan",  # Click and drag to pan left/right (TradingView style)
    xaxis=dict(
        title="Date",
        gridcolor="rgba(128,128,128,0.2)",
        rangeslider=dict(
            visible=True,
            thickness=0.05,  # Thin slider bar at the bottom
        ),
        type="date"
    ),
    yaxis=dict(
        title="Portfolio / Invested ($)",
        tickprefix="$",
        gridcolor="rgba(128,128,128,0.2)"
    ),
    yaxis2=dict(
        title="BTC Price ($)",
        tickprefix="$",
        overlaying="y",
        side="right",
        gridcolor="rgba(128,128,128,0)"
    ),
    yaxis3=dict(
        title="Composite Score",
        overlaying="y",
        side="right",
        position=0.85,
        range=[0, 1.1],
        gridcolor="rgba(128,128,128,0)"
    ),
    legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
    hovermode="x unified",
    template="plotly_dark",
    height=500,
)
st.plotly_chart(fig, use_container_width=True)

# ================================================================
# TRADE HISTORY
# ================================================================
st.subheader("📋 Detailed Trade History")
display_df = trade_df.copy()
display_df["date"] = display_df["date"].dt.strftime("%Y-%m-%d")
display_df["price"] = display_df["price"].map("${:,.0f}".format)
display_df["f_score"] = display_df["f_score"].map("{:.3f}".format)
display_df["composite"] = display_df["composite"].map("{:.3f}".format)
display_df["aud_buy"] = display_df["aud_buy"].map("${:,.2f}".format)
display_df["btc_bought"] = display_df["btc_bought"].map("{:.8f}".format)
display_df["btc_held"] = display_df["btc_held"].map("{:.8f}".format)

cols = ["date", "price", "f_score", "composite", "aud_buy", "btc_bought", "btc_held"]
display_df = display_df[cols]
display_df.columns = ["Date", "BTC Price", "Fund. Score", "Composite", "AUD Buy", "BTC Bought", "BTC Held"]
st.dataframe(display_df, use_container_width=True, height=400)

# ================================================================
# FOOTER
# ================================================================
st.divider()
st.caption(
    f"""
    **Summary:** Periods: {summary['periods']} | 
    Avg Price: ${summary['avg_price']:,.2f} USD | 
    Current Price: ${summary['current_price']:,.2f} USD | 
    Final Composite: {summary['final_composite']:.3f}
    """
)
st.caption(
    "⚠️ **Disclaimer:** Past performance is not indicative of future results. "
    "The fundamental proxy uses Price vs 200-day SMA. "
    "Future dates are flat projections (no price movement)."
)
