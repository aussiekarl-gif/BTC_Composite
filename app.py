#!/usr/bin/env python3
"""
BTC Composite DCA Simulator (Fully Flexible)
=============================================
Adjust risk thresholds, bias, and compare vs Equal DCA & Lump Sum.
Supports historical data + future projection (flat price).
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
# Core Simulation (with full parameter control)
# ================================================================
def simulate_dca(df, params):
    """
    params: dict with keys:
        total_capital, target_weeks, spread_weeks,
        price_max, price_min,
        fund_cheap, fund_expensive, composite_bias
    """
    weekly = df.resample("W-MON").first().dropna().copy()
    if weekly.empty:
        return pd.DataFrame(), {}

    # SMA
    sma_series = df["price"].rolling(window=200).mean()
    weekly["sma_200"] = sma_series.reindex(weekly.index).ffill()

    # --- 1. Fundamental Score (user-adjustable curve) ---
    def calc_fundamental(price, sma):
        if sma <= 0:
            return 0.5
        ratio = price / sma
        if ratio <= params["fund_cheap"]:
            return 1.0
        if ratio >= params["fund_expensive"]:
            return 0.0
        # Linear interpolation between cheap and expensive
        return (params["fund_expensive"] - ratio) / (params["fund_expensive"] - params["fund_cheap"])

    weekly["f_score"] = weekly.apply(
        lambda row: calc_fundamental(row["price"], row["sma_200"]),
        axis=1,
    )

    # --- 2. Price Penalty (user-adjusted floor/ceiling) ---
    def calc_price_penalty(price):
        if price <= params["price_max"]:
            return 1.0
        if price >= params["price_min"]:
            return 0.0
        return (params["price_min"] - price) / (params["price_min"] - params["price_max"])

    weekly["price_factor"] = weekly["price"].apply(calc_price_penalty)

    # --- 3. Final Composite (Fundamental * Penalty * Bias) ---
    weekly["composite"] = weekly["f_score"] * weekly["price_factor"] * params["composite_bias"]
    weekly["composite"] = weekly["composite"].clip(0.0, 1.0)

    # --- 4. Slice & Baseline ---
    weekly["slice_pct"] = (weekly["composite"] * 100) / params["spread_weeks"]
    weekly["slice_pct"] = weekly["slice_pct"].clip(lower=0)

    baseline_weekly = params["total_capital"] / (params["target_weeks"] * 0.04375)

    # --- 5. Run simulation ---
    cash = params["total_capital"]
    btc_held = 0.0
    total_invested = 0.0
    trades = []

    for idx, row in weekly.iterrows():
        aud_buy = baseline_weekly * (row["slice_pct"] / 100)
        aud_buy = min(aud_buy, cash)
        aud_buy = max(aud_buy, 0.0)

        if aud_buy > 1.0 and row["price"] > 0:
            btc_bought = aud_buy / row["price"]
            btc_held += btc_bought
            total_invested += aud_buy
            cash -= aud_buy
        else:
            btc_bought = 0.0

        trades.append({
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
        })

    trade_df = pd.DataFrame(trades)
    current_price = weekly["price"].iloc[-1] if not weekly.empty else 0
    portfolio_value = btc_held * current_price
    avg_price = total_invested / btc_held if btc_held > 0 else 0

    summary = {
        "total_capital": params["total_capital"],
        "total_invested": total_invested,
        "cash_remaining": cash,
        "btc_held": btc_held,
        "avg_price": avg_price,
        "current_price": current_price,
        "portfolio_value": portfolio_value,
        "return_pct": ((portfolio_value / total_invested) - 1) * 100 if total_invested > 0 else 0,
        "baseline_weekly": baseline_weekly,
        "weeks": len(trade_df),
        "final_composite": weekly["composite"].iloc[-1] if not weekly.empty else 0,
    }
    return trade_df, summary


# ================================================================
# Comparison Strategies (Equal DCA & Lump Sum)
# ================================================================
def compare_strategies(df, total_capital, target_weeks, current_price):
    """Calculate Equal DCA and Lump Sum results for the same period."""
    weekly = df.resample("W-MON").first().dropna().copy()
    if weekly.empty:
        return {}, {}

    n_weeks = min(len(weekly), target_weeks)
    equal_per_week = total_capital / n_weeks if n_weeks > 0 else 0

    # Equal DCA
    btc_equal = 0.0
    invested_equal = 0.0
    for i in range(n_weeks):
        price = weekly["price"].iloc[i]
        btc_equal += equal_per_week / price
        invested_equal += equal_per_week

    port_equal = btc_equal * current_price
    return_equal = ((port_equal / invested_equal) - 1) * 100 if invested_equal > 0 else 0

    # Lump Sum (all-in on first day)
    first_price = weekly["price"].iloc[0]
    btc_lump = total_capital / first_price
    port_lump = btc_lump * current_price
    return_lump = ((port_lump / total_capital) - 1) * 100 if total_capital > 0 else 0

    equal_summary = {
        "btc": btc_equal,
        "invested": invested_equal,
        "portfolio": port_equal,
        "return": return_equal,
    }
    lump_summary = {
        "btc": btc_lump,
        "invested": total_capital,
        "portfolio": port_lump,
        "return": return_lump,
    }
    return equal_summary, lump_summary


# ================================================================
# Streamlit UI
# ================================================================
st.set_page_config(page_title="BTC DCA Simulator", layout="wide")
st.title("₿ Bitcoin DCA Simulator (Flexible Composite)")
st.markdown("Adjust the **risk curve, bias, and speed** – compare your Dynamic DCA against Equal DCA and Lump Sum.")

# --- SIDEBAR: Full Controls ---
with st.sidebar:
    st.header("💰 Capital & Speed")
    total_capital = st.number_input("Total Capital (AUD)", 1000, 10_000_000, 500000, 10000)
    target_weeks = st.slider("Target Deployment (Weeks)", 4, 52, 16, 1)

    st.divider()
    st.header("📐 Price Penalty (USD)")
    price_max = st.number_input("🔽 Aggressive Floor (Max DCA)", 20000, 100000, 45000, 1000,
                                help="Below this, penalty = 1.0 (full buying power).")
    price_min = st.number_input("🔼 Conservative Ceiling (Zero DCA)", 30000, 150000, 65000, 1000,
                                help="Above this, penalty = 0.0 (no buying).")
    spread_weeks = st.number_input("Spread Weeks", 4, 26, 12, 1,
                                   help="Spread 100% allocation over this many weeks.")

    st.divider()
    st.header("🧠 Fundamental Risk Curve (SMA Proxy)")
    st.caption("Price / 200-day SMA ratio mapping to Fundamental Score (0–1).")
    fund_cheap = st.slider("Cheap Threshold (SMA multiple)", 0.7, 1.3, 1.0, 0.01,
                           help="Below this ratio, Fundamental Score = 1.0 (max cheap).")
    fund_expensive = st.slider("Expensive Threshold (SMA multiple)", 1.2, 2.5, 1.5, 0.01,
                               help="Above this ratio, Fundamental Score = 0.0 (max expensive).")

    st.divider()
    st.header("⚖️ Composite Bias")
    composite_bias = st.slider("Bias Multiplier", 0.5, 1.5, 1.0, 0.05,
                               help="Scale the final composite up (aggressive) or down (conservative).")

    st.divider()
    st.subheader("📅 Date Range")
    today = datetime.datetime.now(timezone.utc)
    start_date = st.date_input("Start Date", value=today - timedelta(days=365*2), max_value=today)
    end_date = st.date_input("End Date", value=today + timedelta(days=90), min_value=today)

    st.caption("🔬 Data: blockchain.com (free). Future dates = flat projection.")

# --- Load Data ---
start_dt = datetime.datetime.combine(start_date, datetime.datetime.min.time(), tzinfo=timezone.utc)
end_dt = datetime.datetime.combine(end_date, datetime.datetime.max.time(), tzinfo=timezone.utc)
df = fetch_btc_history(start_dt, end_dt)
if df.empty:
    st.error("No data found. Try a wider range.")
    st.stop()

# --- Build Params ---
params = {
    "total_capital": total_capital,
    "target_weeks": target_weeks,
    "spread_weeks": spread_weeks,
    "price_max": price_max,
    "price_min": price_min,
    "fund_cheap": fund_cheap,
    "fund_expensive": fund_expensive,
    "composite_bias": composite_bias,
}

# --- Run Simulations ---
trade_df, summary = simulate_dca(df, params)
if trade_df.empty:
    st.warning("No trades. Adjust parameters.")
    st.stop()

equal_summary, lump_summary = compare_strategies(
    df, total_capital, target_weeks, summary["current_price"]
)

# ================================================================
# METRICS CARDS: Dynamic DCA
# ================================================================
st.subheader("📊 Your Dynamic DCA Performance")
col1, col2, col3, col4, col5 = st.columns(5)
col1.metric("💰 Invested", f"${summary['total_invested']:,.0f} AUD")
col2.metric("₿ BTC Accumulated", f"{summary['btc_held']:.4f} BTC")
col3.metric("💹 Avg Price", f"${summary['avg_price']:,.2f} USD")
col4.metric("📈 Portfolio Value", f"${summary['portfolio_value']:,.0f} USD",
            delta=f"{summary['return_pct']:+.2f}%")
col5.metric("🧠 Final Composite", f"{summary['final_composite']:.3f}")

# ================================================================
# COMPARISON CARDS (Profit vs Other Strategies)
# ================================================================
st.subheader("⚔️ Strategy Comparison (Profit / Return)")
comp_col1, comp_col2, comp_col3 = st.columns(3)

with comp_col1:
    st.metric(
        "🚀 Dynamic DCA (Yours)",
        f"${summary['portfolio_value']:,.0f} USD",
        delta=f"{summary['return_pct']:+.2f}%",
        help="Your composite model's result.",
    )
with comp_col2:
    st.metric(
        "📅 Equal DCA (Fixed $/week)",
        f"${equal_summary['portfolio']:,.0f} USD",
        delta=f"{equal_summary['return']:+.2f}%",
        help="Same total capital, spread evenly over the period.",
    )
with comp_col3:
    st.metric(
        "💥 Lump Sum (All-in Day 1)",
        f"${lump_summary['portfolio']:,.0f} USD",
        delta=f"{lump_summary['return']:+.2f}%",
        help="Invest everything on the first day of the backtest.",
    )

# ================================================================
# CHART: Portfolio + Composite + Price
# ================================================================
st.subheader("📈 Portfolio Value Over Time (with Risk Signals)")
fig = go.Figure()

# Portfolio Value
fig.add_trace(go.Scatter(
    x=trade_df["date"], y=trade_df["btc_held"] * trade_df["price"],
    mode="lines", name="Portfolio Value (USD)", line=dict(color="#F7931A", width=3)
))
# BTC Price
fig.add_trace(go.Scatter(
    x=trade_df["date"], y=trade_df["price"],
    mode="lines", name="BTC Price (USD)", line=dict(color="#2E86C1", width=2, dash="dot"),
    yaxis="y2"
))
# Total Invested
fig.add_trace(go.Scatter(
    x=trade_df["date"], y=trade_df["total_invested"],
    mode="lines", name="Total Invested (USD)", line=dict(color="#28B463", width=2, dash="dash")
))
# Composite Score
fig.add_trace(go.Scatter(
    x=trade_df["date"], y=trade_df["composite"],
    mode="lines", name="Composite Score (0-1)", line=dict(color="#9B59B6", width=2, dash="dot"),
    yaxis="y3"
))

fig.update_layout(
    xaxis=dict(title="Date", gridcolor="rgba(128,128,128,0.2)"),
    yaxis=dict(title="Portfolio / Invested ($)", tickprefix="$", gridcolor="rgba(128,128,128,0.2)"),
    yaxis2=dict(title="BTC Price ($)", tickprefix="$", overlaying="y", side="right", gridcolor="rgba(128,128,128,0)"),
    yaxis3=dict(title="Composite Score", overlaying="y", side="right", position=0.85, range=[0, 1.1], gridcolor="rgba(128,128,128,0)"),
    legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
    hovermode="x unified",
    template="plotly_dark",
    height=500,
)
st.plotly_chart(fig, use_container_width=True)

# ================================================================
# TRADE HISTORY (Full Transparency)
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

cols = ["date", "price", "f_score", "price_factor", "composite", "slice_pct", "aud_buy", "btc_bought", "btc_held", "cash_remaining"]
display_df = display_df[cols]
display_df.columns = ["Date", "BTC Price", "Fund. Score", "Penalty", "Composite", "Slice %", "AUD Buy", "BTC Bought", "BTC Held", "Cash Left"]
st.dataframe(display_df, use_container_width=True, height=400)

# ================================================================
# FOOTER
# ================================================================
st.divider()
st.caption(
    f"""
    **Summary:** Total Capital: ${summary['total_capital']:,.0f} AUD | 
    Weeks Simulated: {summary['weeks']} | 
    Avg Buy: ${summary['avg_price']:,.2f} USD | 
    Current Price: ${summary['current_price']:,.2f} USD
    """
)
st.caption(
    "⚠️ **Disclaimer:** Past performance is not indicative of future results. "
    "Future dates use flat last-known price. The fundamental proxy uses Price vs 200-day SMA. "
    "Adjust the sliders to see how different risk tolerances affect your profit."
)
