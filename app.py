#!/usr/bin/env python3
"""
BTC Composite DCA & Rebalancing Simulator (Corrected Risk Bands & Profit Taking)
=================================================================================
- Risk Score: 0.0 = Absolute Bottom (Cheap), 1.0 = Absolute Top (Expensive).
- Bands 0.0-0.4: Positive percentages (+) to BUY Bitcoin.
- Bands 0.6-1.0: Negative percentages (-) to SELL / Take Profit into cash.
- Dynamic price-deviation multiplier scales purchase size during deep discounts.
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

DEFAULT_PL_CHEAP = -0.10
DEFAULT_PL_EXPENSIVE = 0.20
DEFAULT_FUND_CHEAP = 1.0
DEFAULT_FUND_EXPENSIVE = 1.5
DEFAULT_BIAS = 1.0

# Default band percentages across 10 deciles (0.0 to 1.0)
DEFAULT_BAND_PCTS = [50.0, 25.0, 10.0, 5.0, 0.0, 0.0, -10.0, -20.0, -35.0, -50.0]

# ================================================================
# Data Fetcher
# ================================================================
@st.cache_data(ttl=3600)
def fetch_btc_history(start_date, end_date):
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


@st.cache_data(ttl=86400)
def fetch_aud_usd_rates(start_date, end_date):
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
                return 0.5, 1.0
            fair_value_log = 5.84 * math.log10(days) - 17.01
            fair_value = 10 ** fair_value_log
            log_price = math.log10(price)
            residual = log_price - fair_value_log
            
            score = (residual - params["pl_cheap"]) / (params["pl_expensive"] - params["pl_cheap"])
            return max(0.0, min(1.0, score)), fair_value

        results = data.apply(lambda row: calc_fundamental_pl(row.name, row["price"]), axis=1)
        data["f_score"] = [r[0] for r in results]
        data["fair_value"] = [r[1] for r in results]
        data["sma_200"] = 0.0
    else:
        sma_series = df_full["price"].rolling(window=200).mean()
        data["sma_200"] = sma_series.reindex(data.index)
        if data["sma_200"].isna().any():
            data["sma_200"] = data["sma_200"].fillna(df_full["price"].expanding().mean().reindex(data.index))

        def calc_fundamental_sma(price, sma):
            if sma <= 0:
                return 0.5, sma
            ratio = price / sma
            score = (ratio - params["fund_cheap"]) / (params["fund_expensive"] - params["fund_cheap"])
            return max(0.0, min(1.0, score)), sma

        results = data.apply(lambda row: calc_fundamental_sma(row["price"], row["sma_200"]), axis=1)
        data["f_score"] = [r[0] for r in results]
        data["fair_value"] = [r[1] for r in results]

    data["composite"] = data["f_score"] * params["composite_bias"]
    data["composite"] = data["composite"].clip(0.0, 1.0)

    fx_series = fetch_aud_usd_rates(params["start_date"], params["end_date"])
    if fx_series is not None:
        data["usd_per_aud"] = fx_series.reindex(data.index).ffill().fillna(0.7)
    else:
        data["usd_per_aud"] = 1.0

    def get_band_action(comp):
        for min_r, max_r, pct in params["risk_bands"]:
            if min_r <= comp <= max_r:
                return pct
        return 0.0

    data["band_action"] = data["composite"].apply(get_band_action)

    cash_remaining_aud = params["total_capital_aud"]
    btc_held = 0.0
    total_realized_profit_aud = 0.0
    trades = []

    for idx, row in data.iterrows():
        action_val = row["band_action"]
        aud_flow = 0.0
        usd_flow = 0.0
        btc_change = 0.0
        trade_type = "HOLD"

        current_price_usd = row["price"]
        fair_value = row["fair_value"]
        usd_per_aud = row["usd_per_aud"]

        price_ratio = fair_value / current_price_usd if current_price_usd > 0 else 1.0
        price_multiplier = max(0.5, price_ratio)

        if action_val > 0:
            base_aud_buy = (action_val / 100.0) * params["total_capital_aud"]
            aud_buy = base_aud_buy * price_multiplier
            aud_buy = min(aud_buy, cash_remaining_aud)

            if aud_buy > 0.01 and current_price_usd > 0:
                usd_buy = aud_buy * usd_per_aud
                btc_bought = usd_buy / current_price_usd
                btc_held += btc_bought
                cash_remaining_aud -= aud_buy
                aud_flow = aud_buy
                usd_flow = usd_buy
                btc_change = btc_bought
                trade_type = "BUY"
        elif action_val < 0:
            sell_pct = abs(action_val) / 100.0
            btc_to_sell = btc_held * sell_pct
            if btc_to_sell > 0.00000001 and current_price_usd > 0:
                usd_sale = btc_to_sell * current_price_usd
                aud_sale = usd_sale / usd_per_aud if usd_per_aud > 0 else usd_sale
                btc_held -= btc_to_sell
                cash_remaining_aud += aud_sale
                total_realized_profit_aud += aud_sale
                aud_flow = aud_sale
                usd_flow = usd_sale
                btc_change = -btc_to_sell
                trade_type = "SELL"

        trades.append({
            "date": idx,
            "price": current_price_usd,
            "fair_value": fair_value,
            "sma_200": row.get("sma_200", 0.0),
            "f_score": row["f_score"],
            "composite": row["composite"],
            "band_action": action_val,
            "trade_type": trade_type,
            "aud_flow": aud_flow,
            "usd_flow": usd_flow,
            "btc_change": btc_change,
            "btc_held": btc_held,
            "cash_remaining_aud": cash_remaining_aud,
        })

    trade_df = pd.DataFrame(trades)
    if trade_df.empty:
        return trade_df, {}

    current_price = data["price"].iloc[-1] if not data.empty else 0
    portfolio_value_usd = btc_held * current_price
    last_usd_per_aud = data["usd_per_aud"].iloc[-1] if not data.empty else 1.0
    portfolio_value_aud = portfolio_value_usd / last_usd_per_aud
    total_net_wealth_aud = portfolio_value_aud + cash_remaining_aud

    summary = {
        "total_capital_aud": params["total_capital_aud"],
        "cash_remaining_aud": cash_remaining_aud,
        "btc_held": btc_held,
        "current_price_usd": current_price,
        "portfolio_value_usd": portfolio_value_usd,
        "portfolio_value_aud": portfolio_value_aud,
        "total_net_wealth_aud": total_net_wealth_aud,
        "net_return_pct": ((total_net_wealth_aud / params["total_capital_aud"]) - 1) * 100,
        "periods": len(trade_df),
        "final_composite": data["composite"].iloc[-1] if not data.empty else 0,
    }
    return trade_df, summary


# ================================================================
# Comparison Strategies & UI Layout
# ================================================================
def compare_strategies(df, frequency, day_of_week, total_capital_aud, fx_series):
    data = df.copy()
    if frequency == "Weekly":
        data = data[data.index.dayofweek == day_of_week]
    elif frequency == "Monthly":
        data = data[data.index.day == 1]

    if data.empty or total_capital_aud == 0:
        return {}, {}

    periods = len(data)
    if periods == 0:
        return {}, {}

    equal_per_period_aud = total_capital_aud / periods

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
    total_invested_usd = total_capital_aud * first_usd_per_aud
    btc_lump = total_invested_usd / first_price if first_price > 0 else 0
    port_lump_usd = btc_lump * current_price
    return_lump = ((port_lump_usd / total_invested_usd) - 1) * 100 if total_invested_usd > 0 else 0

    return {"btc": btc_equal, "portfolio_usd": port_equal_usd, "return": return_equal}, \
           {"btc": btc_lump, "portfolio_usd": port_lump_usd, "return": return_lump}


def reset_band_pcts():
    st.session_state.band_pcts = DEFAULT_BAND_PCTS.copy()


st.set_page_config(page_title="BTC Dynamic DCA & Rebalancing Simulator", layout="wide")

if "band_pcts" not in st.session_state:
    st.session_state.band_pcts = DEFAULT_BAND_PCTS.copy()
if "show_buy_sell_labels" not in st.session_state:
    st.session_state.show_buy_sell_labels = True

st.title("Bitcoin Dynamic DCA & Profit-Taking Rebalancer")

with st.sidebar:
    st.header("Capital Setup")
    total_capital_aud = st.number_input("Total Starting Capital (AUD)", min_value=1000, max_value=100_000_000, value=10000, step=1000)

    st.divider()
    frequency = st.selectbox("Execution Frequency", ["Daily", "Weekly", "Monthly"], index=1)
    day_map = {"Monday": 0, "Tuesday": 1, "Wednesday": 2, "Thursday": 3, "Friday": 4, "Saturday": 5, "Sunday": 6}
    day_of_week = st.selectbox("Day of Week", list(day_map.keys()), index=0, disabled=(frequency != "Weekly"))
    selected_day = day_map[day_of_week] if frequency == "Weekly" else 0

    risk_model = st.radio("Risk Metric", ["SMA Ratio (200-day)", "Power Law Trend"], index=1)

    st.divider()
    st.subheader("Risk Band Allocations")
    band_labels = [
        "0.0-0.1 (Cheapest / Bottom)", "0.1-0.2", "0.2-0.3", "0.3-0.4", "0.4-0.5 (Neutral)",
        "0.5-0.6 (Neutral)", "0.6-0.7", "0.7-0.8", "0.8-0.9", "0.9-1.0 (Peak / Expensive)"
    ]

    col1, col2 = st.columns(2)
    for i in range(10):
        with col1 if i % 2 == 0 else col2:
            st.session_state.band_pcts[i] = st.slider(
                band_labels[i], min_value=-50.0, max_value=100.0,
                value=float(st.session_state.band_pcts[i]), step=1.0, key=f"slider_{i}"
            )

    if st.button("Reset Bands to Default", use_container_width=True):
        reset_band_pcts()
        st.rerun()

    st.divider()
    genesis = datetime.date(2009, 1, 3)
    today = datetime.datetime.now(timezone.utc).date()
    start_date = st.date_input("Start Date", value=datetime.date(2020, 1, 1), min_value=genesis, max_value=today, format="DD/MM/YYYY")
    end_date = st.date_input("End Date", value=today + timedelta(days=90), min_value=start_date, format="DD/MM/YYYY")

if end_date <= start_date:
    st.error("End Date must follow Start Date.")
    st.stop()

start_dt = datetime.datetime.combine(start_date, datetime.datetime.min.time(), tzinfo=timezone.utc)
end_dt = datetime.datetime.combine(end_date, datetime.datetime.max.time(), tzinfo=timezone.utc)
df_full = fetch_btc_history(start_dt, end_dt)

if df_full.empty:
    st.error("No historical data available for selected parameters.")
    st.stop()

risk_bands = []
for i in range(10):
    low = round(i * 0.1, 1)
    high = round((i + 1) * 0.1, 1)
    if i == 9:
        high = 1.0
    risk_bands.append((low, high, st.session_state.band_pcts[i]))

params = {
    "risk_model": risk_model, "frequency": frequency, "day_of_week": selected_day,
    "fund_cheap": DEFAULT_FUND_CHEAP, "fund_expensive": DEFAULT_FUND_EXPENSIVE,
    "pl_cheap": DEFAULT_PL_CHEAP, "pl_expensive": DEFAULT_PL_EXPENSIVE,
    "composite_bias": DEFAULT_BIAS, "total_capital_aud": total_capital_aud,
    "risk_bands": risk_bands, "start_date": start_dt, "end_date": end_dt,
}

trade_df, summary = simulate_dca(df_full, params)
fx_series = fetch_aud_usd_rates(start_dt, end_dt)
equal_summary, lump_summary = compare_strategies(
    df_full[(df_full.index >= start_dt) & (df_full.index <= end_dt)],
    frequency, selected_day, total_capital_aud, fx_series
)

st.subheader("Dynamic Rebalancing Performance")
m1, m2, m3, m4, m5 = st.columns(5)
m1.metric("Periods Run", f"{summary['periods']}")
m2.metric("Ending Cash (AUD)", f"${summary['cash_remaining_aud']:,.0f} AUD")
m3.metric("BTC Held", f"{summary['btc_held']:.6f} BTC")
m4.metric("Current Portfolio Value", f"${summary['portfolio_value_aud']:,.0f} AUD")
m5.metric("Total Net Wealth", f"${summary['total_net_wealth_aud']:,.0f} AUD", delta=f"{summary['net_return_pct']:+.2f}%")

st.subheader("Strategy Benchmark Comparison")
if equal_summary and lump_summary:
    c1, c2, c3 = st.columns(3)
    c1.metric("Dynamic Rebalancer", f"${summary['total_net_wealth_aud']:,.0f} AUD", f"{summary['net_return_pct']:+.2f}%")
    c2.metric("Standard Equal DCA", f"${equal_summary['portfolio_usd']:,.0f} USD", f"{equal_summary['return']:+.2f}%")
    c3.metric("Lump Sum", f"${lump_summary['portfolio_usd']:,.0f} USD", f"{lump_summary['return']:+.2f}%")

st.subheader("Portfolio Wealth, Price & Trade Markers")
fig = go.Figure()
fig.add_trace(go.Scatter(x=trade_df["date"], y=trade_df["btc_held"] * trade_df["price"], name="BTC Holdings Value (USD)", line=dict(color="#3498DB", width=2)))
fig.add_trace(go.Scatter(x=trade_df["date"], y=trade_df["cash_remaining_aud"], name="Cash Reserve (AUD)", line=dict(color="#2ECC71", width=2, dash="dash")))
fig.add_trace(go.Scatter(x=trade_df["date"], y=trade_df["price"], name="BTC Price (USD)", line=dict(color="#F1C40F", width=1), yaxis="y2"))

buys = trade_df[trade_df["trade_type"] == "BUY"]
sells = trade_df[trade_df["trade_type"] == "SELL"]
fig.add_trace(go.Scatter(x=buys["date"], y=buys["price"], mode="markers", name="Execution: BUY", marker=dict(color="#00FF00", size=8, symbol="triangle-up"), yaxis="y2"))
fig.add_trace(go.Scatter(x=sells["date"], y=sells["price"], mode="markers", name="Execution: SELL (Take Profit)", marker=dict(color="#FF4444", size=8, symbol="triangle-down"), yaxis="y2"))

fig.update_layout(
    dragmode="pan",
    xaxis=dict(title="Date", rangeslider=dict(visible=True)),
    yaxis=dict(title="Value ($)", tickprefix="$"),
    yaxis2=dict(title="BTC Price ($)", tickprefix="$", overlaying="y", side="right"),
    legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
    template="plotly_dark",
    height=550,
)
st.plotly_chart(fig, use_container_width=True)
