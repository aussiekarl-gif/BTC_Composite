#!/usr/bin/env python3
"""
BTC Composite DCA Simulator (Risk Band % of Capital)
====================================================
- Total Capital: your full pool (e.g., 10,000 AUD).
- Risk bands defined as percentages of Total Capital.
- Per period, you invest band% of Total Capital when composite falls in that band.
- Normalize button to auto-scale all bands to sum to 100% (optional).
- Default start date: 01/01/2020 (can go back to 2009).
- Frequency: Daily, Weekly, Monthly.
- Backtest from 2009 to future (flat projection).
- All bugs fixed: SMA buffer, slider overlap, AUD/USD conversion, error handling, cash exhaustion, NaN warnings.
- Dates displayed in dd/mm/yyyy format.
- No 500k reference anywhere.
"""

import datetime
from datetime import timedelta, timezone

import pandas as pd
import plotly.graph_objects as go
import requests
import streamlit as st

# ================================================================
# Data Fetcher (with future projection and SMA buffer)
# ================================================================
@st.cache_data(ttl=3600)
def fetch_btc_history(start_date, end_date):
    """Fetch daily BTC prices with a 300-day buffer before start_date for SMA."""
    buffer_days = 300
    fetch_start = start_date - timedelta(days=buffer_days)
    
    url = "https://api.blockchain.info/charts/market-price?timespan=all&format=json&sampled=false"
    try:
        resp = requests.get(url, timeout=30)
        resp.raise_for_status()
    except Exception as e:
        st.error(f"❌ Failed to fetch BTC price data: {e}")
        return pd.DataFrame()

    data = resp.json()["values"]

    prices = []
    for point in data:
        dt = datetime.datetime.fromtimestamp(point["x"], tz=timezone.utc)
        price = float(point["y"])
        if price > 0:
            prices.append({"date": dt, "price": price})

    df = pd.DataFrame(prices)
    df = df.set_index("date").sort_index()

    df = df[(df.index >= fetch_start) & (df.index <= end_date)]

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

    return df


# ================================================================
# Historical AUD/USD Exchange Rate (daily)
# ================================================================
@st.cache_data(ttl=86400)
def fetch_aud_usd_rates(start_date, end_date):
    """Fetch daily AUD/USD rates from Frankfurter API."""
    url = f"https://api.frankfurter.app/{start_date.strftime('%Y-%m-%d')}..{end_date.strftime('%Y-%m-%d')}?from=USD&to=AUD"
    try:
        resp = requests.get(url, timeout=30)
        resp.raise_for_status()
        data = resp.json()
        rates = data["rates"]
        aud_per_usd = {k: v["AUD"] for k, v in rates.items()}
        usd_per_aud = {k: 1.0 / v for k, v in aud_per_usd.items()}
        fx_series = pd.Series(usd_per_aud)
        fx_series.index = pd.to_datetime(fx_series.index)
        return fx_series
    except Exception as e:
        st.warning(f"⚠️ Could not fetch AUD/USD rates: {e}. Using 1:1 as fallback.")
        return None


# ================================================================
# Core Simulation
# ================================================================
def simulate_dca(df_full, params):
    df = df_full[(df_full.index >= params["start_date"]) & (df_full.index <= params["end_date"])].copy()
    if df.empty:
        return pd.DataFrame(), {}

    if params["frequency"] == "Weekly":
        data = df[df.index.dayofweek == params["day_of_week"]]
    elif params["frequency"] == "Monthly":
        data = df[df.index.day == 1]
    else:
        data = df

    if data.empty:
        return pd.DataFrame(), {}

    sma_series = df_full["price"].rolling(window=200).mean()
    data["sma_200"] = sma_series.reindex(data.index)
    if data["sma_200"].isna().any():
        data["sma_200"] = data["sma_200"].fillna(df_full["price"].expanding().mean().reindex(data.index))

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

    fx_series = fetch_aud_usd_rates(params["start_date"], params["end_date"])
    if fx_series is not None:
        data["usd_per_aud"] = fx_series.reindex(data.index).ffill().fillna(0.7)
    else:
        data["usd_per_aud"] = 1.0

    def get_band_pct(comp):
        for min_r, max_r, pct in params["risk_bands"]:
            if min_r <= comp <= max_r:
                return pct
        return 0.0

    data["band_pct"] = data["composite"].apply(get_band_pct)

    total_capital_aud = params["total_capital_aud"]
    cash_remaining_aud = total_capital_aud
    btc_held = 0.0
    total_invested_aud = 0.0
    trades = []

    for idx, row in data.iterrows():
        aud_buy = (row["band_pct"] / 100.0) * total_capital_aud
        aud_buy = min(aud_buy, cash_remaining_aud)
        aud_buy = max(aud_buy, 0.0)

        usd_buy = aud_buy * row["usd_per_aud"]

        if usd_buy > 0.01 and row["price"] > 0:
            btc_bought = usd_buy / row["price"]
            btc_held += btc_bought
            total_invested_aud += aud_buy
            cash_remaining_aud -= aud_buy
        else:
            btc_bought = 0.0

        trades.append({
            "date": idx,
            "price": row["price"],
            "sma_200": row["sma_200"],
            "f_score": row["f_score"],
            "composite": row["composite"],
            "band_pct": row["band_pct"],
            "aud_buy": aud_buy,
            "usd_buy": usd_buy,
            "btc_bought": btc_bought,
            "btc_held": btc_held,
            "total_invested_aud": total_invested_aud,
            "cash_remaining_aud": cash_remaining_aud,
        })

    trade_df = pd.DataFrame(trades)
    if trade_df.empty:
        return trade_df, {}

    current_price = data["price"].iloc[-1] if not data.empty else 0
    portfolio_value_usd = btc_held * current_price
    last_usd_per_aud = data["usd_per_aud"].iloc[-1] if not data.empty else 1.0
    portfolio_value_aud = portfolio_value_usd / last_usd_per_aud

    total_invested_usd = trade_df["usd_buy"].sum() if not trade_df.empty else 0
    avg_price_usd = total_invested_usd / btc_held if btc_held > 0 else 0

    summary = {
        "total_capital_aud": total_capital_aud,
        "total_invested_aud": total_invested_aud,
        "cash_remaining_aud": cash_remaining_aud,
        "btc_held": btc_held,
        "avg_price_usd": avg_price_usd,
        "current_price_usd": current_price,
        "portfolio_value_usd": portfolio_value_usd,
        "portfolio_value_aud": portfolio_value_aud,
        "return_pct": ((portfolio_value_usd / total_invested_usd) - 1) * 100 if total_invested_usd > 0 else 0,
        "periods": len(trade_df),
        "final_composite": data["composite"].iloc[-1] if not data.empty else 0,
    }
    return trade_df, summary


# ================================================================
# Comparison Strategies
# ================================================================
def compare_strategies(df, frequency, day_of_week, total_invested_aud, fx_series):
    data = df.copy()
    if frequency == "Weekly":
        data = data[data.index.dayofweek == day_of_week]
    elif frequency == "Monthly":
        data = data[data.index.day == 1]

    if data.empty or total_invested_aud == 0:
        return {}, {}

    periods = len(data)
    if periods == 0:
        return {}, {}

    equal_per_period_aud = total_invested_aud / periods

    if fx_series is not None:
        data["usd_per_aud"] = fx_series.reindex(data.index).ffill().fillna(0.7)
    else:
        data["usd_per_aud"] = 1.0

    btc_equal = 0.0
    for idx, row in data.iterrows():
        usd_per_period = equal_per_period_aud * row["usd_per_aud"]
        if row["price"] > 0:
            btc_equal += usd_per_period / row["price"]
    current_price = data["price"].iloc[-1]
    port_equal_usd = btc_equal * current_price
    return_equal = ((port_equal_usd / (equal_per_period_aud * periods)) - 1) * 100 if equal_per_period_aud > 0 else 0

    first_price = data["price"].iloc[0]
    first_usd_per_aud = data["usd_per_aud"].iloc[0]
    total_invested_usd = total_invested_aud * first_usd_per_aud
    btc_lump = total_invested_usd / first_price if first_price > 0 else 0
    port_lump_usd = btc_lump * current_price
    return_lump = ((port_lump_usd / total_invested_usd) - 1) * 100 if total_invested_usd > 0 else 0

    equal_summary = {"btc": btc_equal, "invested_aud": total_invested_aud, "portfolio_usd": port_equal_usd, "return": return_equal}
    lump_summary = {"btc": btc_lump, "invested_aud": total_invested_aud, "portfolio_usd": port_lump_usd, "return": return_lump}
    return equal_summary, lump_summary


# ================================================================
# Streamlit UI
# ================================================================
st.set_page_config(page_title="BTC DCA Simulator (Risk Bands %)", layout="wide")

if "band_pcts" not in st.session_state:
    st.session_state.band_pcts = [15.0, 12.0, 10.0, 8.0, 6.0, 4.0, 3.0, 2.0, 1.0, 1.0]

st.title("₿ Bitcoin DCA Simulator (Risk Band % of Capital)")
st.markdown(
    """
    Define **percentages of your total capital** to invest per period for each risk band (0.0–1.0). 
    Use the **Normalize** button to automatically scale all bands to sum to 100% (optional).
    """
)

with st.sidebar:
    st.header("💰 Total Capital")
    total_capital_aud = st.number_input(
        "Total Capital (AUD)",
        min_value=1000,
        max_value=100_000_000,
        value=10000,        # 👈 changed from 500000
        step=1000,
        help="Your full pool of capital to deploy (in AUD).",
    )

    st.divider()
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
    if fund_cheap >= fund_expensive:
        st.warning(f"⚠️ Cheap threshold ({fund_cheap:.2f}) must be less than expensive ({fund_expensive:.2f}). Auto-adjusting.")
        fund_expensive = fund_cheap + 0.05

    composite_bias = st.slider(
        "Composite Bias (Aggressiveness)",
        0.5, 1.5, 1.0, 0.05,
        help="Scale the final composite up (bullish) or down (bearish).",
    )

    st.divider()
    st.subheader("📊 Risk Band Investment Map (% of Total Capital)")
    st.caption("Set the percentage of your total capital to invest per period for each composite score range.")

    band_labels = [
        "0.0–0.1", "0.1–0.2", "0.2–0.3", "0.3–0.4", "0.4–0.5",
        "0.5–0.6", "0.6–0.7", "0.7–0.8", "0.8–0.9", "0.9–1.0",
    ]

    col1, col2 = st.columns(2)

    for i in range(10):
        with col1 if i % 2 == 0 else col2:
            st.session_state.band_pcts[i] = st.slider(
                band_labels[i],
                min_value=0.0,
                max_value=100.0,
                value=st.session_state.band_pcts[i],
                step=0.5,
                key=f"slider_{i}",
            )

    # Custom CSS for button
    st.markdown(
        """
        <style>
        div.stButton > button:has(.normalize-text) {
            background-color: #F7931A !important;
            color: white !important;
            font-weight: bold !important;
            border-radius: 8px !important;
            border: none !important;
            padding: 0.6rem 1rem !important;
            width: 100% !important;
            font-size: 1.05rem !important;
            box-shadow: 0 2px 8px rgba(247, 147, 26, 0.4) !important;
            transition: all 0.25s ease !important;
            white-space: nowrap !important;
            letter-spacing: 0.5px !important;
        }
        div.stButton > button:has(.normalize-text):hover {
            background-color: #d9821a !important;
            transform: translateY(-2px) !important;
            box-shadow: 0 6px 16px rgba(247, 147, 26, 0.6) !important;
        }
        div.stButton > button:has(.normalize-text):active {
            transform: translateY(0px) !important;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )

    if st.button("⚖️ Normalize to 100%", key="normalize_btn", use_container_width=True):
        total = sum(st.session_state.band_pcts)
        if total > 0:
            scaled = [v / total * 100 for v in st.session_state.band_pcts]
            st.session_state.band_pcts = [round(v, 2) for v in scaled]
            st.rerun()

    current_sum = sum(st.session_state.band_pcts)
    if abs(current_sum - 100) < 0.01:
        st.success(f"✅ Total = {current_sum:.1f}%")
    else:
        st.warning(f"⚠️ Total = {current_sum:.1f}% (click Normalize to scale to 100%)")

    st.caption("Current Allocation by Risk Band")
    allocation_df = pd.DataFrame({
        "Band": band_labels,
        "Allocation %": st.session_state.band_pcts,
    })
    st.bar_chart(allocation_df.set_index("Band"))

    st.divider()
    st.subheader("📅 Date Range")
    genesis = datetime.date(2009, 1, 3)
    today = datetime.datetime.now(timezone.utc).date()

    default_start = datetime.date(2020, 1, 1)

    # Use format="DD/MM/YYYY" for dd/mm/yyyy display
    start_date = st.date_input(
        "Start Date",
        value=default_start,
        min_value=genesis,
        max_value=today,
        format="DD/MM/YYYY",
        help="Default: 01/01/2020. You can still go back to 2009.",
    )
    end_date = st.date_input(
        "End Date",
        value=today + timedelta(days=90),
        min_value=start_date,
        format="DD/MM/YYYY",
    )

    st.caption("🔬 Data: blockchain.com. Future dates = flat projection (no price change).")

# --- Validation ---
if end_date <= start_date:
    st.error("❌ End Date must be after Start Date. Please adjust.")
    st.stop()

# --- Load Data ---
start_dt = datetime.datetime.combine(start_date, datetime.datetime.min.time(), tzinfo=timezone.utc)
end_dt = datetime.datetime.combine(end_date, datetime.datetime.max.time(), tzinfo=timezone.utc)
df_full = fetch_btc_history(start_dt, end_dt)
if df_full.empty:
    st.error("No data found. Try a wider range.")
    st.stop()

# --- Build Params ---
risk_bands = []
for i in range(10):
    low = round(i * 0.1, 1)
    high = round((i + 1) * 0.1, 1)
    if i == 9:
        high = 1.0
    pct = st.session_state.band_pcts[i]
    risk_bands.append((low, high, pct))

params = {
    "frequency": frequency,
    "day_of_week": selected_day,
    "fund_cheap": fund_cheap,
    "fund_expensive": fund_expensive,
    "composite_bias": composite_bias,
    "total_capital_aud": total_capital_aud,
    "risk_bands": risk_bands,
    "start_date": start_dt,
    "end_date": end_dt,
}

# --- Run Simulation ---
trade_df, summary = simulate_dca(df_full, params)
if trade_df.empty:
    st.warning("No trades executed. Adjust frequency or date range.")
    st.stop()

# --- Comparisons ---
fx_series = fetch_aud_usd_rates(start_dt, end_dt)
equal_summary, lump_summary = compare_strategies(
    df_full[(df_full.index >= start_dt) & (df_full.index <= end_dt)],
    frequency, selected_day, summary["total_invested_aud"], fx_series
)

# ================================================================
# METRICS CARDS
# ================================================================
st.subheader("📊 Your Risk-Band DCA Performance")
col1, col2, col3, col4, col5 = st.columns(5)
col1.metric("⏳ Periods", f"{summary['periods']}")
col2.metric("💰 Invested (AUD)", f"${summary['total_invested_aud']:,.0f} AUD")
col3.metric("₿ BTC Accumulated", f"{summary['btc_held']:.6f} BTC")
col4.metric("💹 Avg Price", f"${summary['avg_price_usd']:,.2f} USD/BTC")
col5.metric("📈 Portfolio Value", f"${summary['portfolio_value_aud']:,.0f} AUD",
            delta=f"{summary['return_pct']:+.2f}%")

# ================================================================
# COMPARISON CARDS
# ================================================================
st.subheader("⚔️ Strategy Comparison (Same Total Invested)")

if equal_summary and lump_summary and summary["total_invested_aud"] > 0:
    comp1, comp2, comp3 = st.columns(3)
    with comp1:
        st.metric("🚀 Risk-Band (Yours)", f"${summary['portfolio_value_aud']:,.0f} AUD", f"{summary['return_pct']:+.2f}%")
    with comp2:
        st.metric("📅 Equal DCA", f"${equal_summary['portfolio_usd']:,.0f} USD", f"{equal_summary['return']:+.2f}%")
    with comp3:
        st.metric("💥 Lump Sum", f"${lump_summary['portfolio_usd']:,.0f} USD", f"{lump_summary['return']:+.2f}%")
else:
    st.info("ℹ️ Not enough invested capital ($0) to compare strategies. Try adjusting your risk bands so the model invests during the selected period.")

# ================================================================
# CHART (dates formatted in tooltip)
# ================================================================
st.subheader("📈 Portfolio Value, Price & Composite Over Time")
st.caption("🖱️ Drag the chart left/right to scroll, or use the slider below. Scroll to zoom.")

fig = go.Figure()

portfolio_usd = trade_df["btc_held"] * trade_df["price"]
fig.add_trace(go.Scatter(
    x=trade_df["date"], y=portfolio_usd,
    mode="lines", name="Portfolio (USD)", line=dict(color="#3498DB", width=3)
))
fig.add_trace(go.Scatter(
    x=trade_df["date"], y=trade_df["price"],
    mode="lines", name="BTC Price (USD)", line=dict(color="#F1C40F", width=2, dash="dot"),
    yaxis="y2"
))
total_invested_usd = trade_df["usd_buy"].cumsum()
fig.add_trace(go.Scatter(
    x=trade_df["date"], y=total_invested_usd,
    mode="lines", name="Total Invested (USD)", line=dict(color="#2ECC71", width=2, dash="dash")
))
fig.add_trace(go.Scatter(
    x=trade_df["date"], y=trade_df["composite"],
    mode="lines", name="Composite Score (0-1)", line=dict(color="#E74C3C", width=2, dash="dot"),
    yaxis="y3"
))

fig.update_layout(
    dragmode="pan",
    xaxis=dict(
        title="Date",
        gridcolor="rgba(128,128,128,0.2)",
        rangeslider=dict(visible=True, thickness=0.05),
        type="date",
        tickformat="%d/%m/%Y",   # dd/mm/yyyy on axis
    ),
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
# TRADE HISTORY (dates formatted)
# ================================================================
st.subheader("📋 Detailed Trade History")
display_df = trade_df.copy()
display_df["date"] = display_df["date"].dt.strftime("%d/%m/%Y")  # dd/mm/yyyy
display_df["price"] = display_df["price"].map("${:,.0f}".format)
display_df["f_score"] = display_df["f_score"].map("{:.3f}".format)
display_df["composite"] = display_df["composite"].map("{:.3f}".format)
display_df["band_pct"] = display_df["band_pct"].map("{:.1f}%".format)
display_df["aud_buy"] = display_df["aud_buy"].map("${:,.2f}".format)
display_df["usd_buy"] = display_df["usd_buy"].map("${:,.2f}".format)
display_df["btc_bought"] = display_df["btc_bought"].map("{:.8f}".format)
display_df["btc_held"] = display_df["btc_held"].map("{:.8f}".format)
display_df["cash_remaining_aud"] = display_df["cash_remaining_aud"].map("${:,.0f}".format)

cols = ["date", "price", "f_score", "composite", "band_pct", "aud_buy", "usd_buy", "btc_bought", "btc_held", "cash_remaining_aud"]
display_df = display_df[cols]
display_df.columns = ["Date", "BTC Price", "Fund. Score", "Composite", "Band %", "AUD Buy", "USD Buy", "BTC Bought", "BTC Held", "Cash Left (AUD)"]
st.dataframe(display_df, use_container_width=True, height=400)

# ================================================================
# FOOTER
# ================================================================
st.divider()
st.caption(
    f"""
    **Summary:** Total Capital: ${summary['total_capital_aud']:,.0f} AUD | 
    Invested: ${summary['total_invested_aud']:,.0f} AUD | 
    Cash Remaining: ${summary['cash_remaining_aud']:,.0f} AUD | 
    Avg Price: ${summary['avg_price_usd']:,.2f} USD | 
    Current Price: ${summary['current_price_usd']:,.2f} USD | 
    Final Composite: {summary['final_composite']:.3f}
    """
)
st.caption(
    "⚠️ **Disclaimer:** Past performance is not indicative of future results. "
    "The fundamental proxy uses Price vs 200-day SMA. "
    "Future dates are flat projections (no price movement). "
    "AUD/USD exchange rates are fetched from Frankfurter API."
)
