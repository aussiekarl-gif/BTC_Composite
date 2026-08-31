#!/usr/bin/env python3
"""
BTC Composite DCA Simulator (Risk Band % of Capital)
====================================================
- Total Capital: your full pool (e.g., 10,000 AUD).
- Risk bands defined as percentages of Total Capital.
- Per period, you invest band% of Total Capital when composite falls in that band.
- Normalize button to auto-scale all bands to sum to 100%.
- Default start date: 01/01/2020 (can go back to 2009).
- Frequency: Daily, Weekly, Monthly.
- TWO FUNDAMENTAL MODELS:
  1) SMA Ratio (200-day) - original, lags in bear markets.
  2) Power Law Trend - non-lagging, aligns with absolute price bottoms.
- AUD/USD conversion, error handling, full timeline even after cash exhaustion.
- Dates in dd/mm/yyyy format.
- Buy/Sell labels on chart with toggle (using add_shape to avoid Plotly bug).
- Reset button only resets risk curve parameters (not band percentages).
- Customizable chart colors and line styles.
- Comprehensive explanation section at bottom.
"""

import datetime
import math
from datetime import timedelta, timezone

import pandas as pd
import plotly.graph_objects as go
import requests
import streamlit as st

# ================================================================
# Constants
# ================================================================
GENESIS_DATE = datetime.datetime(2009, 1, 3, tzinfo=timezone.utc)

DEFAULT_BAND_PCTS = [50.0, 25.0, 13.0, 7.0, 5.0, 0.0, 0.0, 0.0, 0.0, 0.0]
DEFAULT_FUND_CHEAP = 1.0
DEFAULT_FUND_EXPENSIVE = 1.5
DEFAULT_PL_CHEAP = -0.4
DEFAULT_PL_EXPENSIVE = 0.4
DEFAULT_BIAS = 1.0

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
        st.error(f"Failed to fetch BTC price data: {e}")
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
        st.warning(f"Could not fetch AUD/USD rates: {e}. Using 1:1 as fallback.")
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

    if params["risk_model"] == "Power Law Trend":
        def calc_fundamental_pl(date, price):
            days = (date - GENESIS_DATE).days
            if days <= 0:
                return 0.5
            fair_value_log = 5.84 * math.log10(days) - 17.01
            log_price = math.log10(price)
            residual = log_price - fair_value_log
            score = (params["pl_expensive"] - residual) / (params["pl_expensive"] - params["pl_cheap"])
            return max(0.0, min(1.0, score))

        data["f_score"] = data.apply(
            lambda row: calc_fundamental_pl(row.name, row["price"]),
            axis=1,
        )
        data["sma_200"] = 0.0

    else:
        sma_series = df_full["price"].rolling(window=200).mean()
        data["sma_200"] = sma_series.reindex(data.index)
        if data["sma_200"].isna().any():
            data["sma_200"] = data["sma_200"].fillna(df_full["price"].expanding().mean().reindex(data.index))

        def calc_fundamental_sma(price, sma):
            if sma <= 0:
                return 0.5
            ratio = price / sma
            if ratio <= params["fund_cheap"]:
                return 1.0
            if ratio >= params["fund_expensive"]:
                return 0.0
            return (params["fund_expensive"] - ratio) / (params["fund_expensive"] - params["fund_cheap"])

        data["f_score"] = data.apply(
            lambda row: calc_fundamental_sma(row["price"], row["sma_200"]),
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
            "sma_200": row.get("sma_200", 0.0),
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
# Reset functions
# ================================================================
def reset_risk_curve_params():
    """Reset ONLY the risk curve parameters (not the band percentages)."""
    st.session_state.fund_cheap = DEFAULT_FUND_CHEAP
    st.session_state.fund_expensive = DEFAULT_FUND_EXPENSIVE
    st.session_state.pl_cheap = DEFAULT_PL_CHEAP
    st.session_state.pl_expensive = DEFAULT_PL_EXPENSIVE
    st.session_state.composite_bias = DEFAULT_BIAS


def reset_band_pcts():
    """Reset the band percentage sliders back to the curated default set."""
    st.session_state.band_pcts = DEFAULT_BAND_PCTS.copy()


# ================================================================
# Streamlit UI
# ================================================================
st.set_page_config(page_title="BTC DCA Simulator (Risk Bands %)", layout="wide")

if "band_pcts" not in st.session_state:
    st.session_state.band_pcts = DEFAULT_BAND_PCTS.copy()
if "fund_cheap" not in st.session_state:
    st.session_state.fund_cheap = DEFAULT_FUND_CHEAP
if "fund_expensive" not in st.session_state:
    st.session_state.fund_expensive = DEFAULT_FUND_EXPENSIVE
if "pl_cheap" not in st.session_state:
    st.session_state.pl_cheap = DEFAULT_PL_CHEAP
if "pl_expensive" not in st.session_state:
    st.session_state.pl_expensive = DEFAULT_PL_EXPENSIVE
if "composite_bias" not in st.session_state:
    st.session_state.composite_bias = DEFAULT_BIAS
if "show_buy_sell_labels" not in st.session_state:
    st.session_state.show_buy_sell_labels = True

if "portfolio_color" not in st.session_state:
    st.session_state.portfolio_color = "#3498DB"
if "portfolio_style" not in st.session_state:
    st.session_state.portfolio_style = "solid"
if "btc_price_color" not in st.session_state:
    st.session_state.btc_price_color = "#F1C40F"
if "btc_price_style" not in st.session_state:
    st.session_state.btc_price_style = "dash"
if "invested_color" not in st.session_state:
    st.session_state.invested_color = "#2ECC71"
if "invested_style" not in st.session_state:
    st.session_state.invested_style = "dash"
if "composite_color" not in st.session_state:
    st.session_state.composite_color = "#E74C3C"
if "composite_style" not in st.session_state:
    st.session_state.composite_style = "dot"

st.title("Bitcoin DCA Simulator (Risk Band % of Capital)")
st.markdown(
    """
    Define **percentages of your total capital** to invest per period for each risk band (0.0-1.0). 
    Use the **Reset** button to restore the curated default allocation.
    """
)

with st.sidebar:
    st.header("Total Capital")
    total_capital_aud = st.number_input(
        "Total Capital (AUD)",
        min_value=1000,
        max_value=100_000_000,
        value=10000,
        step=1000,
        help="Your full pool of capital to deploy (in AUD).",
    )

    st.divider()
    st.header("Frequency")
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
    st.header("Fundamental Model")
    risk_model = st.radio(
        "Risk Model",
        ["SMA Ratio (200-day)", "Power Law Trend"],
        index=1,
        help="SMA lags; Power Law aligns with absolute price bottoms.",
    )

    st.subheader("Risk Curve Parameters")
    
    if risk_model == "SMA Ratio (200-day)":
        fund_cheap = st.slider(
            "Cheap Threshold (SMA multiple)",
            0.7, 1.3, st.session_state.fund_cheap, 0.01,
            help="Price/SMA <= this -> Fundamental Score = 1.0 (max cheap).",
            key="fund_cheap_slider",
        )
        st.session_state.fund_cheap = fund_cheap
        
        fund_expensive = st.slider(
            "Expensive Threshold (SMA multiple)",
            1.2, 2.5, st.session_state.fund_expensive, 0.01,
            help="Price/SMA >= this -> Fundamental Score = 0.0 (max expensive).",
            key="fund_expensive_slider",
        )
        st.session_state.fund_expensive = fund_expensive
        
        if fund_cheap >= fund_expensive:
            st.warning(f"Cheap ({fund_cheap:.2f}) must be < Expensive ({fund_expensive:.2f}). Auto-adjusting.")
            fund_expensive = fund_cheap + 0.05
            st.session_state.fund_expensive = fund_expensive
        
        pl_cheap, pl_expensive = 0.0, 0.0
    else:
        st.caption("Residual = log10(price) - log10(power law fair value)")
        pl_cheap = st.slider(
            "Power Law Cheap Residual",
            -0.8, 0.0, st.session_state.pl_cheap, 0.01,
            help="Residual <= this -> Fundamental Score = 1.0 (max cheap).",
            key="pl_cheap_slider",
        )
        st.session_state.pl_cheap = pl_cheap
        
        pl_expensive = st.slider(
            "Power Law Expensive Residual",
            0.0, 0.8, st.session_state.pl_expensive, 0.01,
            help="Residual >= this -> Fundamental Score = 0.0 (max expensive).",
            key="pl_expensive_slider",
        )
        st.session_state.pl_expensive = pl_expensive
        
        if pl_cheap >= pl_expensive:
            st.warning(f"Cheap residual ({pl_cheap:.2f}) must be < Expensive ({pl_expensive:.2f}). Auto-adjusting.")
            pl_expensive = pl_cheap + 0.05
            st.session_state.pl_expensive = pl_expensive
        
        fund_cheap, fund_expensive = 0.0, 0.0

    composite_bias = st.slider(
        "Composite Bias (Aggressiveness)",
        0.5, 1.5, st.session_state.composite_bias, 0.05,
        help="Scale the final composite up (bullish) or down (bearish).",
        key="bias_slider",
    )
    st.session_state.composite_bias = composite_bias

    if st.button("Reset Risk Curve Parameters to Defaults", use_container_width=True):
        reset_risk_curve_params()
        st.rerun()

    st.divider()
    st.subheader("Risk Band Investment Map (% of Total Capital)")
    st.caption("Set the percentage of your total capital to invest per period for each composite score range.")

    band_labels = [
        "0.0-0.1", "0.1-0.2", "0.2-0.3", "0.3-0.4", "0.4-0.5",
        "0.5-0.6", "0.6-0.7", "0.7-0.8", "0.8-0.9", "0.9-1.0",
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

    if st.button("Reset Bands to Default", use_container_width=True):
        reset_band_pcts()
        st.rerun()

    current_sum = sum(st.session_state.band_pcts)
    if abs(current_sum - 100) < 0.01:
        st.success(f"Total = {current_sum:.1f}%")
    else:
        st.warning(f"Total = {current_sum:.1f}% (click Reset to restore the default allocation)")

    st.caption("Current Allocation by Risk Band")
    allocation_df = pd.DataFrame({
        "Band": band_labels,
        "Allocation %": st.session_state.band_pcts,
    })
    st.bar_chart(allocation_df.set_index("Band"))

    st.divider()
    st.subheader("Date Range")
    genesis = datetime.date(2009, 1, 3)
    today = datetime.datetime.now(timezone.utc).date()

    default_start = datetime.date(2020, 1, 1)

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

    st.divider()
    st.subheader("Chart Customization")
    st.caption("Customize colors and line styles for each trace.")

    st.session_state.portfolio_color = st.color_picker("Portfolio Color", st.session_state.portfolio_color, key="portfolio_color_picker")
    st.session_state.portfolio_style = st.selectbox("Portfolio Style", ["solid", "dash", "dot", "dashdot"], index=0, key="portfolio_style_sel")

    st.session_state.btc_price_color = st.color_picker("BTC Price Color", st.session_state.btc_price_color, key="btc_price_color_picker")
    st.session_state.btc_price_style = st.selectbox("BTC Price Style", ["solid", "dash", "dot", "dashdot"], index=1, key="btc_price_style_sel")

    st.session_state.invested_color = st.color_picker("Total Invested Color", st.session_state.invested_color, key="invested_color_picker")
    st.session_state.invested_style = st.selectbox("Total Invested Style", ["solid", "dash", "dot", "dashdot"], index=1, key="invested_style_sel")

    st.session_state.composite_color = st.color_picker("Composite Color", st.session_state.composite_color, key="composite_color_picker")
    st.session_state.composite_style = st.selectbox("Composite Style", ["solid", "dash", "dot", "dashdot"], index=2, key="composite_style_sel")

    st.divider()
    st.subheader("Chart Labels")
    st.session_state.show_buy_sell_labels = st.checkbox("Show Buy/Sell Labels", value=st.session_state.show_buy_sell_labels, key="show_labels_checkbox")

    st.caption("Data: blockchain.com. Future dates = flat projection (no price change).")

if end_date <= start_date:
    st.error("End Date must be after Start Date. Please adjust.")
    st.stop()

start_dt = datetime.datetime.combine(start_date, datetime.datetime.min.time(), tzinfo=timezone.utc)
end_dt = datetime.datetime.combine(end_date, datetime.datetime.max.time(), tzinfo=timezone.utc)
df_full = fetch_btc_history(start_dt, end_dt)
if df_full.empty:
    st.error("No data found. Try a wider range.")
    st.stop()

risk_bands = []
for i in range(10):
    low = round(i * 0.1, 1)
    high = round((i + 1) * 0.1, 1)
    if i == 9:
        high = 1.0
    pct = st.session_state.band_pcts[i]
    risk_bands.append((low, high, pct))

params = {
    "risk_model": risk_model,
    "frequency": frequency,
    "day_of_week": selected_day,
    "fund_cheap": fund_cheap,
    "fund_expensive": fund_expensive,
    "pl_cheap": pl_cheap,
    "pl_expensive": pl_expensive,
    "composite_bias": composite_bias,
    "total_capital_aud": total_capital_aud,
    "risk_bands": risk_bands,
    "start_date": start_dt,
    "end_date": end_dt,
}

trade_df, summary = simulate_dca(df_full, params)
if trade_df.empty:
    st.warning("No trades executed. Adjust frequency or date range.")
    st.stop()

fx_series = fetch_aud_usd_rates(start_dt, end_dt)
equal_summary, lump_summary = compare_strategies(
    df_full[(df_full.index >= start_dt) & (df_full.index <= end_dt)],
    frequency, selected_day, summary["total_invested_aud"], fx_series
)

st.subheader("Your Risk-Band DCA Performance")
col1, col2, col3, col4, col5 = st.columns(5)
col1.metric("Periods", f"{summary['periods']}")
col2.metric("Invested (AUD)", f"${summary['total_invested_aud']:,.0f} AUD")
col3.metric("BTC Accumulated", f"{summary['btc_held']:.6f} BTC")
col4.metric("Avg Price", f"${summary['avg_price_usd']:,.2f} USD/BTC")
col5.metric("Portfolio Value", f"${summary['portfolio_value_aud']:,.0f} AUD",
            delta=f"{summary['return_pct']:+.2f}%")

st.subheader("Strategy Comparison (Same Total Invested)")

if equal_summary and lump_summary and summary["total_invested_aud"] > 0:
    comp1, comp2, comp3 = st.columns(3)
    with comp1:
        st.metric("Risk-Band (Yours)", f"${summary['portfolio_value_aud']:,.0f} AUD", f"{summary['return_pct']:+.2f}%")
    with comp2:
        st.metric("Equal DCA", f"${equal_summary['portfolio_usd']:,.0f} USD", f"{equal_summary['return']:+.2f}%")
    with comp3:
        st.metric("Lump Sum", f"${lump_summary['portfolio_usd']:,.0f} USD", f"{lump_summary['return']:+.2f}%")
else:
    st.info("Not enough invested capital ($0) to compare strategies. Try adjusting your risk bands so the model invests during the selected period.")

st.subheader("Portfolio Value, Price & Composite Over Time")
st.caption("Drag the chart left/right to scroll, or use the slider below. Scroll to zoom.")

fig = go.Figure()

dates = trade_df["date"]
prices = trade_df["price"]
portfolio_usd = trade_df["btc_held"] * trade_df["price"]
total_invested_usd = trade_df["usd_buy"].cumsum()
composite = trade_df["composite"]

fig.add_trace(go.Scatter(
    x=dates, y=portfolio_usd,
    mode="lines",
    name="Portfolio (USD)",
    line=dict(
        color=st.session_state.portfolio_color,
        width=3,
        dash=st.session_state.portfolio_style
    )
))

fig.add_trace(go.Scatter(
    x=dates, y=prices,
    mode="lines",
    name="BTC Price (USD)",
    line=dict(
        color=st.session_state.btc_price_color,
        width=2,
        dash=st.session_state.btc_price_style
    ),
    yaxis="y2"
))

fig.add_trace(go.Scatter(
    x=dates, y=total_invested_usd,
    mode="lines",
    name="Total Invested (USD)",
    line=dict(
        color=st.session_state.invested_color,
        width=2,
        dash=st.session_state.invested_style
    )
))

fig.add_trace(go.Scatter(
    x=dates, y=composite,
    mode="lines",
    name="Composite Score (0-1)",
    line=dict(
        color=st.session_state.composite_color,
        width=2,
        dash=st.session_state.composite_style
    ),
    yaxis="y3"
))

if st.session_state.show_buy_sell_labels:
    min_price = prices.min()
    max_price = prices.max()
    price_range = max_price - min_price
    if price_range == 0:
        buy_level = min_price
        sell_level = max_price
    else:
        buy_level = min_price + (price_range * 0.05)
        sell_level = max_price - (price_range * 0.05)

    fig.add_shape(
        type="line",
        xref="paper",
        yref="y2",
        x0=0,
        y0=buy_level,
        x1=1,
        y1=buy_level,
        line=dict(color="#00FF00", width=2, dash="solid"),
        opacity=0.5,
    )
    fig.add_annotation(
        xref="paper",
        yref="y2",
        x=1,
        y=buy_level,
        text="BUY ZONE",
        showarrow=False,
        font=dict(color="#00FF00", size=14),
        xanchor="right",
        yanchor="bottom",
    )

    fig.add_shape(
        type="line",
        xref="paper",
        yref="y2",
        x0=0,
        y0=sell_level,
        x1=1,
        y1=sell_level,
        line=dict(color="#FF4444", width=2, dash="solid"),
        opacity=0.5,
    )
    fig.add_annotation(
        xref="paper",
        yref="y2",
        x=1,
        y=sell_level,
        text="SELL ZONE",
        showarrow=False,
        font=dict(color="#FF4444", size=14),
        xanchor="right",
        yanchor="top",
    )

fig.update_layout(
    dragmode="pan",
    xaxis=dict(
        title="Date",
        gridcolor="rgba(128,128,128,0.2)",
        rangeslider=dict(visible=True, thickness=0.05),
        type="date",
        tickformat="%d/%m/%Y",
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

st.subheader("Detailed Trade History")
display_df = trade_df.copy()
display_df["date"] = display_df["date"].dt.strftime("%d/%m/%Y")
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

st.divider()
st.header("How the Risk Model Works")

with st.expander("What is the Composite Score?", expanded=False):
    st.markdown("""
    The **Composite Score** is a number between **0 and 1** that tells you how "cheap" or "expensive" Bitcoin is at any given time:
    
    - **1.0** = Maximum cheap (ideal time to buy aggressively)
    - **0.5** = Neutral (average valuation)
    - **0.0** = Maximum expensive (avoid buying)
    
    It is calculated by taking a **Fundamental Score** (based on price relative to a long-term trend) and multiplying it by a **Composite Bias** (your personal aggressiveness setting).
    """)

with st.expander("How do the Risk Bands work?", expanded=False):
    st.markdown("""
    The **Risk Bands** are your **investment rules**. For each band (0.0-0.1, 0.1-0.2, ... 0.9-1.0), you set:
    
    - **What % of your total capital** to invest in each period when the Composite Score falls into that band.
    
    **Example:**
    - Composite Score = 0.8 -> falls into band 0.8-0.9 -> you invest 10% of your capital that period.
    - Composite Score = 0.2 -> falls into band 0.2-0.3 -> you invest 30% of your capital.
    
    This lets you **customize your risk profile** - invest heavily when the market is cheap, and sit out when it's expensive.
    """)

with st.expander("SMA vs Power Law - Which model should I use?", expanded=False):
    st.markdown("""
    **SMA Ratio (200-day)**
    - Compares price to the 200-day moving average.
    - Simple and well-known, but **lags** in bear markets.
    - The SMA drops during a bear market, so the `Price/SMA` ratio bottoms *before* the price does.
    - Result: you buy too early, and at the true bottom the model looks only neutral.
    
    **Power Law Trend**
    - Compares price to a long-term logarithmic growth curve (5.84 * log10(days_since_genesis) - 17.01).
    - The trend line **continues to rise** even during bear markets.
    - The residual (`price - trend`) is at its absolute minimum **exactly when the price is at its lowest**.
    
    This is a contested, unproven framework among analysts, not an established fact - different published
    sources fit meaningfully different constants for this same model. Treat it as one lens, not a guarantee.
    """)

with st.expander("How to read the chart", expanded=False):
    st.markdown("""
    The chart shows four key elements over time:
    
    1. **Portfolio Value (Blue)** - The current USD value of your accumulated BTC holdings.
    2. **BTC Price (Yellow)** - The actual Bitcoin price in USD.
    3. **Total Invested (Green)** - The cumulative amount you've invested (in USD).
    4. **Composite Score (Red)** - The risk signal (0-1). When it's near 1.0, you're buying heavily.
    
    **Buy/Sell Labels:** these mark a point 5% above the lowest price and 5% below the highest price
    *shown in your selected date range* - they are a visual reference for where the range's extremes sit,
    not a model-driven trading signal. They will move if you change the date range.
    
    Toggle these labels on/off in the sidebar.
    """)

with st.expander("How to customize this tool", expanded=False):
    st.markdown("""
    1. **Adjust Risk Bands** - Change the % allocated to each composite score range.
    2. **Reset Bands to Default** - Restore the curated default allocation (50/25/13/7/5/0/0/0/0/0).
    3. **Reset Risk Curve Parameters** - Restore only the cheap/expensive thresholds and bias to defaults.
    4. **Chart Colors** - Pick any color and line style for each trace.
    5. **Date Range** - Backtest from 2009 to the present, or project into the future.
    6. **Frequency** - Choose Daily, Weekly, or Monthly DCA.
    """)

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
    "Disclaimer: Past performance is not indicative of future results. "
    "The Power Law model is a contested, unproven framework, not a scientific consensus. "
    "Future dates are flat projections (no price movement). "
    "AUD/USD exchange rates are fetched from the Frankfurter API."
)
