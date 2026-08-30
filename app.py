#!/usr/bin/env python3
"""
BTC Composite DCA Simulator (Streamlit Dashboard)
==================================================
Interactive backtest & forward-simulation of your Dynamic Composite DCA model.
Uses Price vs 200-day SMA as a proxy for the fundamental composite.
Supports FUTURE DATES (extends the last known price flat).
"""

import datetime
from datetime import timedelta, timezone

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import requests
import streamlit as st

# ================================================================
# Configuration (Matches your config.json)
# ================================================================
SPREAD_WEEKS = 12
NEUTRAL_SLICE_AT_50K = 0.04375  # 4.375%


# ================================================================
# Data Fetcher (cached, with future date projection)
# ================================================================
@st.cache_data(ttl=3600)
def fetch_btc_history(start_date, end_date):
    """Fetch daily BTC prices. If end_date is in the future, extends with flat price."""
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

    # Filter to requested range
    if start_date:
        df = df[df.index >= start_date]

    # --- Future projection logic ---
    if end_date and end_date > df.index[-1]:
        # Extend with flat price (last known price) for future dates
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
# Core Strategy Logic
# ================================================================
def simulate_dca(df, total_capital_aud, target_weeks, spread_weeks, price_max, price_min):
    """
    Simulates the Composite DCA strategy on weekly data.
    Returns a DataFrame with every weekly trade and a portfolio summary.
    """
    # 1. Filter to Mondays (or the closest available day of each week)
    weekly = df.resample("W-MON").first().dropna().copy()
    if weekly.empty:
        return pd.DataFrame(), {}

    # 2. Calculate 200-day SMA (rolling, using original daily data)
    sma_series = df["price"].rolling(window=200).mean()
    weekly["sma_200"] = sma_series.reindex(weekly.index).ffill()

    # 3. Fundamental proxy: Price vs 200-day SMA
    # Map: price/SMA = 1.0 -> score=1.0 (cheap), price/SMA = 1.5 -> score=0.0 (expensive)
    weekly["f_score"] = weekly.apply(
        lambda row: max(0.0, min(1.0, (1.5 - (row["price"] / row["sma_200"])) / 0.5))
        if row["sma_200"] > 0 else 0.5,
        axis=1,
    )

    # 4. Price Penalty Factor (USER FIX: clear labels)
    def calc_price_penalty(price):
        if price <= price_max:   # Below floor -> Full buying power
            return 1.0
        if price >= price_min:   # Above ceiling -> No buying
            return 0.0
        # Linear interpolation between floor and ceiling
        return (price_min - price) / (price_min - price_max)

    weekly["price_factor"] = weekly["price"].apply(calc_price_penalty)

    # 5. Final Composite = Fundamental * Price Penalty
    weekly["composite"] = weekly["f_score"] * weekly["price_factor"]

    # 6. Weekly Slice %
    weekly["slice_pct"] = (weekly["composite"] * 100) / spread_weeks
    weekly["slice_pct"] = weekly["slice_pct"].clip(lower=0)

    # 7. AUD Baseline
    baseline_weekly_aud = total_capital_aud / (target_weeks * NEUTRAL_SLICE_AT_50K)

    # 8. Simulate buying weekly
    cash = total_capital_aud
    btc_held = 0.0
    total_invested = 0.0
    trades = []

    for idx, row in weekly.iterrows():
        aud_buy = baseline_weekly_aud * (row["slice_pct"] / 100)
        aud_buy = min(aud_buy, cash)
        aud_buy = max(aud_buy, 0.0)

        if aud_buy > 1.0 and row["price"] > 0:
            btc_bought = aud_buy / row["price"]
            btc_held += btc_bought
            total_invested += aud_buy
            cash -= aud_buy
        else:
            btc_bought = 0.0

        trades.append(
            {
                "date": idx,
                "price": row["price"],
                "sma_200": row["sma_200"],
                "f_score": row["f_score"],
                "price_factor": row["price_factor"],
                "composite": row["composite"],
                "slice_pct": row["slice_pct"],
                "aud_buy": aud_buy,
                "btc_bought": btc_bought,
                "btc_held": btc_held,
                "cash_remaining": cash,
                "total_invested": total_invested,
            }
        )

    trade_df = pd.DataFrame(trades)

    # Portfolio valuation
    current_price = weekly["price"].iloc[-1] if not weekly.empty else 0
    current_portfolio_value = btc_held * current_price
    total_return_pct = (
        ((current_portfolio_value / total_invested) - 1) * 100 if total_invested > 0 else 0
    )
    avg_price = total_invested / btc_held if btc_held > 0 else 0
    latest_composite = weekly["composite"].iloc[-1] if not weekly.empty else 0
    latest_factor = weekly["price_factor"].iloc[-1] if not weekly.empty else 0

    summary = {
        "total_capital": total_capital_aud,
        "total_invested": total_invested,
        "cash_remaining": cash,
        "btc_held": btc_held,
        "avg_price": avg_price,
        "current_price": current_price,
        "portfolio_value": current_portfolio_value,
        "total_return_pct": total_return_pct,
        "baseline_weekly_aud": baseline_weekly_aud,
        "weeks_simulated": len(trade_df),
        "latest_composite": latest_composite,
        "latest_factor": latest_factor,
    }

    return trade_df, summary


# ================================================================
# Streamlit UI
# ================================================================
st.set_page_config(page_title="BTC DCA Simulator", layout="wide")

st.title("₿ Bitcoin DCA Simulator (Composite Model)")
st.markdown(
    """
    This simulator runs your **Dynamic Composite DCA** model on historical & projected BTC data.
    It combines a fundamental proxy (Price vs 200-day SMA) with a strict **price penalty**
    to determine your weekly AUD buys.
    """
)

# --- Sidebar: User Inputs ---
with st.sidebar:
    st.header("⚙️ Parameters")
    total_capital = st.number_input(
        "Total Capital (AUD)",
        min_value=1000,
        max_value=10_000_000,
        value=500000,
        step=10000,
        help="Your total cash pool to deploy.",
    )

    target_weeks = st.slider(
        "Target Deployment (Weeks)",
        min_value=4,
        max_value=52,
        value=16,
        step=1,
        help="Aim to deploy all capital within this many weeks under neutral conditions.",
    )

    st.divider()
    st.subheader("📅 Date Range")
    today = datetime.datetime.now(timezone.utc)
    default_start = today - timedelta(days=365 * 2)
    
    # Allow future end dates!
    start_date = st.date_input(
        "Start Date",
        value=default_start,
        max_value=today,  # Start must be <= today
    )
    end_date = st.date_input(
        "End Date",
        value=today + timedelta(days=90),  # Default: 3 months into future
        min_value=today,  # End can be in the future
    )

    st.divider()
    st.subheader("📐 Strategy Anchors")
    # FIXED: Clearer labels to avoid min/max confusion
    price_max = st.number_input(
        "🔽 Aggressive Floor (Max DCA)", 
        value=45000, 
        step=1000, 
        help="Below this price, penalty = 1.0 (max buying power)."
    )
    price_min = st.number_input(
        "🔼 Conservative Ceiling (Zero DCA)", 
        value=65000, 
        step=1000, 
        help="Above this price, penalty = 0.0 (no buying)."
    )
    spread_weeks = st.number_input(
        "Spread Weeks", value=12, step=1, help="Spread the full 100% allocation over this many weeks."
    )

    st.divider()
    st.caption("🔬 Data sourced from blockchain.com (free, keyless).")
    st.caption("📈 Future dates use the last known price (flat projection).")
    st.caption("Fundamental proxy: Price vs 200-day SMA.")

# --- Fetch Data ---
with st.spinner("Fetching historical BTC prices..."):
    start_dt = datetime.datetime.combine(start_date, datetime.datetime.min.time(), tzinfo=timezone.utc)
    end_dt = datetime.datetime.combine(end_date, datetime.datetime.max.time(), tzinfo=timezone.utc)
    df = fetch_btc_history(start_dt, end_dt)

if df.empty:
    st.error("No data found for the selected date range. Please try a wider range.")
    st.stop()

# --- Run Simulation ---
trade_df, summary = simulate_dca(
    df,
    total_capital,
    target_weeks,
    spread_weeks,
    price_max,
    price_min,
)

if trade_df.empty:
    st.warning("No trades were executed in this period. Try adjusting the date range or price anchors.")
    st.stop()

# ================================================================
# METRICS CARDS (UPDATED with Composite & Factor)
# ================================================================
col1, col2, col3, col4, col5 = st.columns(5)

with col1:
    st.metric(
        "💰 Total Invested",
        f"${summary['total_invested']:,.0f} AUD",
        help="Total capital deployed so far.",
    )

with col2:
    st.metric(
        "₿ BTC Accumulated",
        f"{summary['btc_held']:.4f} BTC",
        help="Total Bitcoin accumulated.",
    )

with col3:
    st.metric(
        "💹 Avg Buy Price",
        f"${summary['avg_price']:,.2f} USD",
        help="Average purchase price.",
    )

with col4:
    current_price = summary['current_price']
    port_value = summary['portfolio_value']
    invested = summary['total_invested']
    return_pct = ((port_value / invested) - 1) * 100 if invested > 0 else 0
    st.metric(
        "📈 Portfolio Value",
        f"${port_value:,.0f} USD",
        delta=f"{return_pct:+.2f}%",
        help="Current value of your holdings.",
    )

with col5:
    # NEW: Composite & Factor combined metric
    comp = summary['latest_composite']
    factor = summary['latest_factor']
    st.metric(
        "🧠 Current Composite",
        f"{comp:.3f}",
        delta=f"Factor {factor:.2f}",
        help="Composite = Fundamental (0-1) × Price Penalty. 1 = Max Cheap, 0 = Max Expensive.",
    )

# ================================================================
# CHART: Portfolio, Price, AND Composite
# ================================================================
st.subheader("📊 Portfolio Value Over Time (with Risk Signals)")

fig = go.Figure()

# Trace 1: Portfolio Value
fig.add_trace(
    go.Scatter(
        x=trade_df["date"],
        y=trade_df["btc_held"] * trade_df["price"],
        mode="lines",
        name="Portfolio Value (USD)",
        line=dict(color="#F7931A", width=3),
    )
)

# Trace 2: BTC Price (Secondary Axis)
fig.add_trace(
    go.Scatter(
        x=trade_df["date"],
        y=trade_df["price"],
        mode="lines",
        name="BTC Price (USD)",
        line=dict(color="#2E86C1", width=2, dash="dot"),
        yaxis="y2",
    )
)

# Trace 3: Total Invested (Baseline)
fig.add_trace(
    go.Scatter(
        x=trade_df["date"],
        y=trade_df["total_invested"],
        mode="lines",
        name="Total Invested (USD)",
        line=dict(color="#28B463", width=2, dash="dash"),
    )
)

# Trace 4: Composite Score (NEW - Right Axis)
fig.add_trace(
    go.Scatter(
        x=trade_df["date"],
        y=trade_df["composite"],
        mode="lines",
        name="Composite Score (0-1)",
        line=dict(color="#9B59B6", width=2, dash="dot"),
        yaxis="y3",
    )
)

# Layout with THREE axes
fig.update_layout(
    xaxis=dict(title="Date", gridcolor="rgba(128,128,128,0.2)"),
    yaxis=dict(title="Portfolio / Invested ($)", tickprefix="$", gridcolor="rgba(128,128,128,0.2)"),
    yaxis2=dict(
        title="BTC Price ($)",
        tickprefix="$",
        overlaying="y",
        side="right",
        gridcolor="rgba(128,128,128,0)",
    ),
    yaxis3=dict(
        title="Composite Score",
        overlaying="y",
        side="right",
        position=0.85,  # Slightly offset from price axis
        range=[0, 1.1],
        gridcolor="rgba(128,128,128,0)",
    ),
    legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
    hovermode="x unified",
    template="plotly_dark",
    height=500,
)

st.plotly_chart(fig, use_container_width=True)

# ================================================================
# TRADE HISTORY TABLE
# ================================================================
st.subheader("📋 Simulated Trade History")

display_df = trade_df.copy()
display_df["date"] = display_df["date"].dt.strftime("%Y-%m-%d")
display_df["price"] = display_df["price"].map("${:,.0f}".format)
display_df["f_score"] = display_df["f_score"].map("{:.3f}".format)
display_df["price_factor"] = display_df["price_factor"].map("{:.3f}".format)
display_df["composite"] = display_df["composite"].map("{:.3f}".format)
display_df["slice_pct"] = display_df["slice_pct"].map("{:.2f}%".format)
display_df["aud_buy"] = display_df["aud_buy"].map("${:,.2f}".format)
display_df["btc_bought"] = display_df["btc_bought"].map("{:.6f}".format)
display_df["btc_held"] = display_df["btc_held"].map("{:.6f}".format)
display_df["cash_remaining"] = display_df["cash_remaining"].map("${:,.0f}".format)

columns_to_show = [
    "date",
    "price",
    "f_score",
    "price_factor",
    "composite",
    "slice_pct",
    "aud_buy",
    "btc_bought",
    "btc_held",
    "cash_remaining",
]
display_df = display_df[columns_to_show]
display_df.columns = [
    "Date",
    "BTC Price",
    "Fund. Score",
    "Penalty Factor",
    "Composite",
    "Slice %",
    "AUD Buy",
    "BTC Bought",
    "BTC Held",
    "Cash Left",
]

st.dataframe(display_df, use_container_width=True, height=400)

# ================================================================
# FOOTER & SUMMARY
# ================================================================
st.divider()
col_a, col_b = st.columns(2)
with col_a:
    st.metric(
        "📆 Target Deployment Period",
        f"{target_weeks} weeks ({target_weeks//4} months)",
        help="If BTC stays at $50k and composite is 0.70, you'll finish on time.",
    )
with col_b:
    st.metric(
        "🧮 Baseline Weekly DCA",
        f"${summary['baseline_weekly_aud']:,.0f} AUD",
        help="The 100% baseline amount. Your actual buys are a percentage of this.",
    )

st.caption(
    f"""
    **Simulation Summary**  
    • Total Capital: ${summary['total_capital']:,.0f} AUD  
    • Weeks Simulated: {summary['weeks_simulated']}  
    • Average Buy Price: ${summary['avg_price']:,.2f} USD  
    • Current BTC Price: ${summary['current_price']:,.2f} USD  
    • Cash Remaining: ${summary['cash_remaining']:,.0f} AUD  
    • Final Composite: {summary['latest_composite']:.3f}  
    """
)
st.caption(
    "⚠️ **Disclaimer:** Past performance is not indicative of future results. "
    "Future dates are projected using flat last-known price (no price movement). "
    "This simulation uses Price vs 200-day SMA as a proxy for the full 5-indicator composite. "
    "Real results using MVRV, Puell, AHR999, Power-law, and Realised Price may vary."
)
