#!/usr/bin/env python3
"""
BTC Dynamic DCA & Tactical Rebalancing Simulator V3.2.1 FULL
====================================================

Designed for:
- Derived from the original full Streamlit simulator, preserving its workflow and extending it.
- Historical backtesting
- Risk-weighted DCA
- Time-based deployment
- Deployment-pressure / catch-up mechanism
- Smooth risk multipliers
- Portfolio-target rebalancing / profit taking
- Proper BTC cost-basis tracking
- AUD portfolio accounting
- Forward deployment planning (without pretending future prices are known)

Install:
    pip install streamlit pandas requests plotly

Run:
    streamlit run btc_dynamic_dca_v2.py

Important:
- Historical mode uses only data available on each historical date.
- Forward Plan mode does NOT invent future BTC prices or future risk scores.
  It shows a deployment schedule using the current manually supplied risk score.
- This is a research/backtesting tool, not financial advice.
"""

import datetime as dt
import math
import os

import numpy as np
from datetime import timedelta, timezone

import pandas as pd
import plotly.graph_objects as go
import requests
import streamlit as st


# ================================================================
# Constants
# ================================================================

GENESIS_DATE = dt.datetime(2009, 1, 3, tzinfo=timezone.utc)

DEFAULT_PL_CHEAP = -0.10
DEFAULT_PL_EXPENSIVE = 0.20

DEFAULT_FUND_CHEAP = 1.00
DEFAULT_FUND_EXPENSIVE = 1.50

# Smooth risk -> DCA multiplier curve.
# Lower risk score = cheaper BTC = larger DCA.
DEFAULT_RISK_POINTS = [
    (0.00, 3.00),
    (0.10, 2.60),
    (0.20, 2.10),
    (0.30, 1.60),
    (0.40, 1.25),
    (0.50, 1.00),
    (0.60, 0.75),
    (0.70, 0.50),
    (0.80, 0.25),
    (0.90, 0.10),
    (1.00, 0.00),
]

# Risk -> desired BTC portfolio weight for profit taking/rebalancing.
DEFAULT_TARGET_BTC_POINTS = [
    (0.00, 1.00),
    (0.10, 0.95),
    (0.20, 0.90),
    (0.30, 0.85),
    (0.40, 0.80),
    (0.50, 0.70),
    (0.60, 0.55),
    (0.70, 0.40),
    (0.80, 0.25),
    (0.90, 0.10),
    (1.00, 0.05),
]

DEFAULT_MAX_PERIOD_PCT = 0.20       # Never invest >20% of initial capital in one period
DEFAULT_MIN_CASH_RESERVE_PCT = 0.00
DEFAULT_PRESSURE_STRENGTH = 0.75
DEFAULT_MAX_RISK_MULTIPLIER = 3.00
DEFAULT_MAX_SELL_PCT_PERIOD = 0.25  # Avoid dumping >25% of BTC in one period
DEFAULT_SELL_THRESHOLD = 0.03       # Rebalance only if target weight differs by 3%+
DEFAULT_FEE_PCT = 0.00

REQUEST_HEADERS = {"User-Agent": "BTC-DCA-Simulator/3.2"}

BGEOMETRICS_BASE = "https://bitcoin-data.com/v1"
DEFAULT_COMPOSITE_WEIGHTS = {
    "mvrv": 0.30,
    "power_law": 0.25,
    "mayer": 0.20,
    "fear_greed": 0.15,
    "rsi": 0.10,
}
DEFAULT_REGIME_OVERLAY = 0.25
DEFAULT_VALUATION_STRENGTH = 0.75
DEFAULT_MIN_VALUATION_MULT = 0.50
DEFAULT_MAX_VALUATION_MULT = 2.50
DEFAULT_PRESSURE_CAP = 2.50
DEFAULT_MIN_DAYS_BETWEEN_SALES = 21


# ================================================================
# Utility Functions
# ================================================================

def clamp(value, low, high):
    return max(low, min(high, value))


def interpolate(points, x):
    """Piecewise-linear interpolation."""
    points = sorted(points)

    if x <= points[0][0]:
        return points[0][1]
    if x >= points[-1][0]:
        return points[-1][1]

    for (x1, y1), (x2, y2) in zip(points[:-1], points[1:]):
        if x1 <= x <= x2:
            if x2 == x1:
                return y1
            fraction = (x - x1) / (x2 - x1)
            return y1 + fraction * (y2 - y1)

    return points[-1][1]


def annualized_return(start_value, end_value, years):
    if start_value <= 0 or end_value <= 0 or years <= 0:
        return 0.0
    return (end_value / start_value) ** (1.0 / years) - 1.0


def max_drawdown(values):
    series = pd.Series(values, dtype=float)
    if series.empty:
        return 0.0
    running_max = series.cummax()
    drawdown = series / running_max - 1.0
    return float(drawdown.min())


def format_pct(x):
    return f"{x:+.2f}%"


# ================================================================
# Data Fetchers
# ================================================================

@st.cache_data(ttl=3600)
def fetch_btc_history(start_date, end_date):
    """
    Fetch BTC/USD history from Blockchain.com.

    Extra history before start_date is fetched so the 200-day SMA has
    sufficient lookback data.
    """
    buffer_days = 300
    fetch_start = start_date - timedelta(days=buffer_days)

    url = "https://api.blockchain.info/charts/market-price"
    params = {
        "timespan": "all",
        "format": "json",
        "sampled": "false",
    }

    try:
        resp = requests.get(
            url,
            params=params,
            headers=REQUEST_HEADERS,
            timeout=30,
        )
        resp.raise_for_status()
        payload = resp.json()
    except Exception as exc:
        st.error(f"Failed to fetch BTC price data: {exc}")
        return pd.DataFrame()

    values = payload.get("values", [])
    prices = []

    for point in values:
        try:
            timestamp = float(point["x"])
            price = float(point["y"])
            if price > 0:
                timestamp_dt = dt.datetime.fromtimestamp(
                    timestamp, tz=timezone.utc
                )
                prices.append(
                    {"date": timestamp_dt, "price": price}
                )
        except (KeyError, TypeError, ValueError):
            continue

    if not prices:
        return pd.DataFrame()

    df = pd.DataFrame(prices)
    df["date"] = pd.to_datetime(df["date"], utc=True)
    df = df.set_index("date").sort_index()
    df = df[~df.index.duplicated(keep="last")]

    # Use requested range plus the lookback needed for indicators.
    df = df[
        (df.index >= fetch_start) &
        (df.index <= end_date)
    ].copy()

    return df


@st.cache_data(ttl=86400)
def fetch_aud_usd_rates(start_date, end_date):
    """
    Returns USD per AUD.

    Frankfurter publishes business-day FX rates, so the series is later
    forward-filled onto BTC dates.
    """
    if end_date < start_date:
        return None

    url = (
        f"https://api.frankfurter.app/"
        f"{start_date.strftime('%Y-%m-%d')}.."
        f"{end_date.strftime('%Y-%m-%d')}"
        f"?from=USD&to=AUD"
    )

    try:
        resp = requests.get(
            url,
            headers=REQUEST_HEADERS,
            timeout=30,
        )
        resp.raise_for_status()
        payload = resp.json()

        rates = payload.get("rates", {})
        if not rates:
            return None

        # API returns AUD per USD. Convert to USD per AUD.
        usd_per_aud = {
            date_string: 1.0 / float(values["AUD"])
            for date_string, values in rates.items()
            if values.get("AUD", 0) > 0
        }

        if not usd_per_aud:
            return None

        series = pd.Series(usd_per_aud, dtype=float)
        series.index = pd.to_datetime(series.index, utc=True)
        series = series.sort_index()
        return series

    except Exception as exc:
        st.warning(
            f"Could not fetch AUD/USD rates: {exc}. "
            f"Using 0.70 USD/AUD as fallback."
        )
        return None


def get_bgeometrics_token():
    """Read the token from Streamlit Secrets first, then environment."""
    try:
        token = st.secrets.get("BGEOMETRICS_TOKEN", "")
        if token:
            return str(token).strip()
    except Exception:
        pass
    return os.getenv("BGEOMETRICS_TOKEN", "").strip()


def _pick_api_column(frame, aliases):
    if frame is None or frame.empty:
        return None
    lower = {str(c).lower(): c for c in frame.columns}
    for alias in aliases:
        if alias.lower() in lower:
            return lower[alias.lower()]
    for alias in aliases:
        for col in frame.columns:
            if alias.lower() in str(col).lower():
                return col
    return None


@st.cache_data(ttl=3600, show_spinner=False)
def fetch_bgeometrics_endpoint(endpoint, start_date, end_date, token=""):
    params = {
        "startday": start_date.strftime("%Y-%m-%d"),
        "endday": end_date.strftime("%Y-%m-%d"),
    }
    headers = dict(REQUEST_HEADERS)
    headers["Accept"] = "application/json"
    if token:
        headers["Authorization"] = f"Bearer {token}"

    resp = requests.get(
        f"{BGEOMETRICS_BASE}/{endpoint}",
        params=params,
        headers=headers,
        timeout=30,
    )
    resp.raise_for_status()
    payload = resp.json()

    if isinstance(payload, dict):
        for key in ("data", "results", "items", "values"):
            if isinstance(payload.get(key), list):
                payload = payload[key]
                break
    if isinstance(payload, dict):
        payload = [payload]

    rows = []
    for item in payload if isinstance(payload, list) else []:
        if not isinstance(item, dict):
            continue
        d = (
            item.get("d") or item.get("date") or item.get("day")
            or item.get("theDate")
        )
        if d is None:
            continue
        row = dict(item)
        row["date"] = pd.to_datetime(d, utc=True)
        rows.append(row)

    if not rows:
        return pd.DataFrame()
    return (
        pd.DataFrame(rows)
        .set_index("date")
        .sort_index()
        .loc[lambda x: ~x.index.duplicated(keep="last")]
    )


@st.cache_data(ttl=3600, show_spinner=False)
def fetch_bgeometrics_bundle(start_date, end_date, token=""):
    """Fetch the V3.2 external risk inputs; failures remain visible as missing data."""
    result = pd.DataFrame()
    endpoints = {
        "bg_btc_price": ("btc-price", ["price", "btcPrice", "btc_price", "value", "close"]),
        "mvrv_z": ("mvrv-zscore", ["mvrvZScore", "mvrv_zscore", "zscore", "mvrvZ"]),
        "fear_greed": ("fear-greed", ["fearGreed", "fearAndGreed", "fear_greed", "value", "score"]),
    }
    for dest, (endpoint, aliases) in endpoints.items():
        try:
            frame = fetch_bgeometrics_endpoint(endpoint, start_date, end_date, token)
            col = _pick_api_column(frame, aliases)
            if col is not None:
                series = pd.to_numeric(frame[col], errors="coerce").rename(dest)
                result = result.join(series, how="outer") if not result.empty else series.to_frame()
        except Exception:
            pass

    # Subscriber endpoint. Absence never breaks the transparent local composite.
    try:
        frame = fetch_bgeometrics_endpoint("regime-score", start_date, end_date, token)
        mapping = {
            "regime_score": ["regimeScore"],
            "regime_delta_30d": ["regimeDelta30d"],
            "regime_active_weight": ["activeWeight"],
            "regime": ["regime"],
        }
        for dest, aliases in mapping.items():
            col = _pick_api_column(frame, aliases)
            if col is None:
                continue
            series = frame[col].rename(dest)
            if dest != "regime":
                series = pd.to_numeric(series, errors="coerce")
            result = result.join(series, how="outer") if not result.empty else series.to_frame()
    except Exception:
        pass

    return result.sort_index() if not result.empty else pd.DataFrame()


def merge_bgeometrics(data, external):
    result = data.copy()
    for col in ["mvrv_z", "fear_greed", "regime_score", "regime_delta_30d", "regime_active_weight", "regime"]:
        if col not in result.columns:
            result[col] = np.nan if col != "regime" else ""
    if external is None or external.empty:
        return result
    union = result.index.union(external.index).sort_values()
    ext = external.reindex(union).ffill().reindex(result.index)
    for col in ext.columns:
        result[col] = ext[col]
    return result


def align_fx_to_dates(data, fx_series, fallback=0.70):
    """Align business-day FX rates to BTC dates."""
    result = data.copy()

    if fx_series is None or fx_series.empty:
        result["usd_per_aud"] = fallback
        return result

    combined_index = result.index.union(fx_series.index).sort_values()
    fx = fx_series.reindex(combined_index).ffill()
    fx = fx.reindex(result.index).ffill().bfill().fillna(fallback)

    result["usd_per_aud"] = fx
    return result


# ================================================================
# Risk Engines
# ================================================================

def power_law_score(date, price, cheap=-0.10, expensive=0.20):
    """
    Power-law residual score.

    residual = log10(actual price) - log10(power-law fair value)

    cheap and expensive are residual thresholds:
      cheap      -> score 0
      expensive  -> score 1
    """
    if price <= 0:
        return 0.5, price

    days = (date - GENESIS_DATE).days
    if days <= 0:
        return 0.5, price

    fair_value_log = 5.84 * math.log10(days) - 17.01
    fair_value = 10 ** fair_value_log

    residual = math.log10(price) - fair_value_log

    denominator = expensive - cheap
    if denominator <= 0:
        return 0.5, fair_value

    score = (residual - cheap) / denominator
    score = clamp(score, 0.0, 1.0)

    return score, fair_value


def sma_score(price, sma, cheap=1.0, expensive=1.5):
    """Score based on BTC / 200-day SMA."""
    if price <= 0 or sma <= 0:
        return 0.5, sma

    ratio = price / sma

    denominator = expensive - cheap
    if denominator <= 0:
        return 0.5, sma

    score = (ratio - cheap) / denominator
    score = clamp(score, 0.0, 1.0)

    return score, sma


def add_risk_indicators(data, risk_model, params):
    """Calculate legacy or V3.2 composite risk without future-data leakage."""
    result = data.copy()
    result["sma_200"] = result["price"].rolling(window=200, min_periods=100).mean()
    result["mayer"] = result["price"] / result["sma_200"]

    delta = result["price"].diff()
    gain = delta.clip(lower=0).ewm(alpha=1/14, adjust=False, min_periods=14).mean()
    loss = (-delta.clip(upper=0)).ewm(alpha=1/14, adjust=False, min_periods=14).mean()
    rs = gain / loss.replace(0, np.nan)
    result["rsi_14"] = 100 - 100 / (1 + rs)

    pl_scores, fair_values, pl_residuals = [], [], []
    for timestamp, row in result.iterrows():
        score, fair_value = power_law_score(
            timestamp, float(row["price"]), params["pl_cheap"], params["pl_expensive"]
        )
        pl_scores.append(score)
        fair_values.append(fair_value)
        if fair_value > 0 and row["price"] > 0:
            pl_residuals.append(math.log10(float(row["price"]) / fair_value))
        else:
            pl_residuals.append(np.nan)
    result["power_law_score"] = pl_scores
    result["fair_value"] = fair_values
    result["power_law_residual"] = pl_residuals
    result["price_to_fair"] = result["price"] / result["fair_value"].replace(0, np.nan)

    result["mayer_score"] = ((result["mayer"] - 0.70) / 1.00).clip(0, 1)
    result["rsi_score"] = ((result["rsi_14"] - 25.0) / 50.0).clip(0, 1)
    result["mvrv_score"] = ((pd.to_numeric(result.get("mvrv_z"), errors="coerce") + 0.5) / 6.5).clip(0, 1)
    result["fear_greed_score"] = (pd.to_numeric(result.get("fear_greed"), errors="coerce") / 100.0).clip(0, 1)

    if risk_model == "Power Law Trend":
        result["risk_score"] = result["power_law_score"]
    elif risk_model == "SMA Ratio (200-day)":
        result["risk_score"] = ((result["mayer"] - params["fund_cheap"]) / (params["fund_expensive"] - params["fund_cheap"])).clip(0,1)
    else:
        component_map = {
            "mvrv": "mvrv_score",
            "power_law": "power_law_score",
            "mayer": "mayer_score",
            "fear_greed": "fear_greed_score",
            "rsi": "rsi_score",
        }
        numerator = pd.Series(0.0, index=result.index)
        denominator = pd.Series(0.0, index=result.index)
        for key, col in component_map.items():
            weight = float(params["composite_weights"].get(key, 0.0))
            values = pd.to_numeric(result[col], errors="coerce")
            numerator += values.fillna(0.0) * weight
            denominator += values.notna().astype(float) * weight
        result["core_risk_score"] = (numerator / denominator.replace(0, np.nan)).clip(0,1)

        regime = (pd.to_numeric(result.get("regime_score"), errors="coerce") / 100.0).clip(0,1)
        active = pd.to_numeric(result.get("regime_active_weight"), errors="coerce")
        active = active.where(active <= 1.0, active / 100.0).clip(0,1).fillna(1.0)
        overlay = float(params.get("regime_overlay", 0.0)) * active
        result["risk_score"] = (
            (1.0 - overlay) * result["core_risk_score"] + overlay * regime
        ).where(regime.notna(), result["core_risk_score"]).clip(0,1)

    result["risk_score"] = result["risk_score"].fillna(0.5).clip(0,1)
    result["dca_multiplier"] = result["risk_score"].apply(lambda x: interpolate(DEFAULT_RISK_POINTS, x))
    result["target_btc_weight"] = result["risk_score"].apply(lambda x: interpolate(DEFAULT_TARGET_BTC_POINTS, x))
    result["valuation_multiplier"] = (
        (result["fair_value"] / result["price"].replace(0, np.nan))
        .pow(float(params.get("valuation_strength", DEFAULT_VALUATION_STRENGTH)))
        .clip(float(params.get("min_valuation_mult", DEFAULT_MIN_VALUATION_MULT)),
              float(params.get("max_valuation_mult", DEFAULT_MAX_VALUATION_MULT)))
        .fillna(1.0)
    )
    return result


# ================================================================
# Execution Schedule
# ================================================================

def select_execution_dates(df, frequency, day_of_week):
    """Select actual available market data dates."""
    if df.empty:
        return df.copy()

    if frequency == "Daily":
        return df.copy()

    if frequency == "Weekly":
        weekly = df[df.index.dayofweek == day_of_week].copy()

        # If a selected weekday is unavailable, use the first available
        # date in each calendar week.
        if weekly.empty:
            temp = df.copy()
            temp["week"] = temp.index.to_period("W-SUN")
            weekly = (
                temp.groupby("week", group_keys=False)
                .head(1)
                .drop(columns=["week"])
            )

        return weekly

    # Monthly: first available market observation in each month.
    temp = df.copy()
    temp["month"] = temp.index.to_period("M")
    monthly = (
        temp.groupby("month", group_keys=False)
        .head(1)
        .drop(columns=["month"])
    )
    return monthly


# ================================================================
# Portfolio Engine
# ================================================================

def simulate_dynamic_dca(df_full, params):
    """
    Core historical backtest.

    The strategy has three interacting components:

    1. Time target:
       How much capital would normally have been deployed by now?

    2. Risk multiplier:
       Cheap BTC gets a larger DCA allocation.

    3. Deployment pressure:
       If the strategy is behind its time target, purchases increase.
       If it is ahead, purchases decrease.

    Profit-taking is portfolio-target based rather than "sell X% of all BTC"
    because that makes the sell logic respond to the actual BTC/cash mix.
    """
    if df_full.empty:
        return pd.DataFrame(), {}

    start = params["start_date"]
    end = params["end_date"]

    df = df_full[
        (df_full.index >= start) &
        (df_full.index <= end)
    ].copy()

    if df.empty:
        return pd.DataFrame(), {}

    df = add_risk_indicators(
        df,
        params["risk_model"],
        params,
    )

    execution = select_execution_dates(
        df,
        params["frequency"],
        params["day_of_week"],
    )

    if execution.empty:
        return pd.DataFrame(), {}

    total_capital = float(params["total_capital_aud"])
    cash = total_capital
    btc = 0.0

    # Weighted-average BTC acquisition cost in AUD/BTC.
    btc_cost_basis_aud = 0.0

    cumulative_invested = 0.0
    cumulative_sold_proceeds = 0.0
    cumulative_realized_profit = 0.0
    cumulative_fees = 0.0
    last_sale_date = None

    trades = []

    n_periods = len(execution)

    for period_number, (timestamp, row) in enumerate(
        execution.iterrows(), start=1
    ):
        price_usd = float(row["price"])
        usd_per_aud = float(row["usd_per_aud"])

        if price_usd <= 0 or usd_per_aud <= 0:
            continue

        btc_price_aud = price_usd / usd_per_aud

        risk = float(row["risk_score"])
        risk_multiplier = float(row["dca_multiplier"])
        target_btc_weight = min(float(row["target_btc_weight"]), float(params.get("max_btc_weight", 1.0)))
        valuation_multiplier = float(row.get("valuation_multiplier", 1.0))

        # ------------------------------------------------------------
        # Time target
        # ------------------------------------------------------------
        time_progress = period_number / n_periods
        target_cumulative_invested = total_capital * time_progress

        deployment_gap = (
            target_cumulative_invested - cumulative_invested
        )

        # Convert the gap into a normalized pressure value.
        # Positive = behind schedule.
        gap_pct = deployment_gap / total_capital

        pressure = 1.0 + (
            clamp(
                gap_pct,
                -0.50,
                1.00,
            ) * params["pressure_strength"]
        )

        pressure = clamp(pressure, 0.50, float(params.get("pressure_cap", DEFAULT_PRESSURE_CAP)))

        # ------------------------------------------------------------
        # Dynamic DCA purchase
        # ------------------------------------------------------------
        remaining_periods = max(1, n_periods - period_number + 1)
        base_period_amount = cash / remaining_periods

        desired_buy = (
            base_period_amount
            * risk_multiplier
            * valuation_multiplier
            * pressure
        )

        # Never exceed configured percentage of original capital in one
        # period.
        max_period_buy = (
            total_capital * params["max_period_pct"]
        )

        desired_buy = min(
            desired_buy,
            max_period_buy,
        )

        # Maintain minimum cash reserve.
        minimum_cash = (
            total_capital * params["min_cash_reserve_pct"]
        )

        available_for_buy = max(
            0.0,
            cash - minimum_cash,
        )

        desired_buy = min(
            desired_buy,
            available_for_buy,
        )

        # ------------------------------------------------------------
        # Portfolio-target rebalancing / profit taking
        # ------------------------------------------------------------
        portfolio_before = (
            cash + btc * btc_price_aud
        )

        current_btc_value = btc * btc_price_aud

        current_btc_weight = (
            current_btc_value / portfolio_before
            if portfolio_before > 0
            else 0.0
        )

        # Do not let a large multiplier blindly push BTC above the risk-derived target.
        target_btc_value_before = portfolio_before * target_btc_weight
        allocation_room = max(0.0, target_btc_value_before - current_btc_value)
        overshoot_allowance = total_capital * 0.005
        desired_buy = min(desired_buy, allocation_room + overshoot_allowance)

        target_difference = (
            current_btc_weight - target_btc_weight
        )

        desired_sell = 0.0

        # Only sell if BTC allocation is materially above target.
        sale_gap_ok = (
            last_sale_date is None
            or (timestamp - last_sale_date).days >= int(params.get("min_days_between_sales", 0))
        )
        if (
            btc > 0
            and target_difference >= params["sell_threshold"]
            and sale_gap_ok
        ):
            target_btc_value = (
                portfolio_before * target_btc_weight
            )

            excess_btc_value = max(
                0.0,
                current_btc_value - target_btc_value,
            )

            desired_sell = (
                excess_btc_value
                / btc_price_aud
            )

            max_btc_sell = btc * params["max_sell_pct_period"]

            desired_sell = min(
                desired_sell,
                max_btc_sell,
            )

        # ------------------------------------------------------------
        # Execute SELL first when over target.
        # ------------------------------------------------------------
        sell_proceeds = 0.0
        sell_fee = 0.0
        realized_profit = 0.0

        if desired_sell > 0:
            sell_value_gross = desired_sell * btc_price_aud
            sell_fee = sell_value_gross * params["fee_pct"]
            sell_proceeds = sell_value_gross - sell_fee

            # Weighted average cost basis of BTC sold.
            avg_cost_per_btc = (
                btc_cost_basis_aud / btc
                if btc > 0
                else 0.0
            )

            sold_cost_basis = desired_sell * avg_cost_per_btc
            realized_profit = (
                sell_proceeds - sold_cost_basis
            )

            btc -= desired_sell
            btc_cost_basis_aud -= sold_cost_basis
            btc_cost_basis_aud = max(0.0, btc_cost_basis_aud)

            cash += sell_proceeds

            cumulative_sold_proceeds += sell_proceeds
            cumulative_realized_profit += realized_profit
            cumulative_fees += sell_fee
            last_sale_date = timestamp

        # ------------------------------------------------------------
        # Execute BUY.
        # ------------------------------------------------------------
        buy_amount = desired_buy
        buy_fee = buy_amount * params["fee_pct"]
        total_cash_used = buy_amount

        # If fee is charged in AUD, reduce actual BTC purchase amount.
        net_buy_amount = max(
            0.0,
            buy_amount - buy_fee,
        )

        btc_bought = (
            net_buy_amount / btc_price_aud
            if btc_price_aud > 0
            else 0.0
        )

        if btc_bought > 0:
            btc += btc_bought
            btc_cost_basis_aud += net_buy_amount
            cash -= total_cash_used
            cash = max(0.0, cash)

            cumulative_invested += net_buy_amount
            cumulative_fees += buy_fee

        # ------------------------------------------------------------
        # Portfolio after transactions.
        # ------------------------------------------------------------
        btc_value_aud = btc * btc_price_aud
        total_wealth_aud = cash + btc_value_aud

        actual_btc_weight = (
            btc_value_aud / total_wealth_aud
            if total_wealth_aud > 0
            else 0.0
        )

        avg_cost = (
            btc_cost_basis_aud / btc
            if btc > 0
            else 0.0
        )

        unrealized_profit = (
            btc_value_aud - btc_cost_basis_aud
        )

        trades.append(
            {
                "date": timestamp,
                "price_usd": price_usd,
                "btc_price_aud": btc_price_aud,
                "fair_value_usd": float(row["fair_value"]),
                "risk_score": risk,
                "dca_multiplier": risk_multiplier,
                "valuation_multiplier": valuation_multiplier,
                "target_btc_weight": target_btc_weight,
                "mvrv_score": float(row.get("mvrv_score", np.nan)),
                "power_law_score": float(row.get("power_law_score", np.nan)),
                "mayer_score": float(row.get("mayer_score", np.nan)),
                "fear_greed_score": float(row.get("fear_greed_score", np.nan)),
                "rsi_score": float(row.get("rsi_score", np.nan)),
                "regime_score": float(row.get("regime_score", np.nan)) if pd.notna(row.get("regime_score", np.nan)) else np.nan,
                "actual_btc_weight": actual_btc_weight,
                "time_progress": time_progress,
                "target_cumulative_invested": target_cumulative_invested,
                "cumulative_invested": cumulative_invested,
                "deployment_gap": (
                    target_cumulative_invested
                    - cumulative_invested
                ),
                "pressure": pressure,
                "buy_aud": buy_amount if btc_bought > 0 else 0.0,
                "btc_bought": btc_bought,
                "sell_btc": desired_sell,
                "sell_proceeds_aud": sell_proceeds,
                "realized_profit_aud": realized_profit,
                "fees_aud": buy_fee + sell_fee,
                "btc_held": btc,
                "btc_cost_basis_aud": btc_cost_basis_aud,
                "btc_avg_cost_aud": avg_cost,
                "cash_aud": cash,
                "btc_value_aud": btc_value_aud,
                "total_wealth_aud": total_wealth_aud,
                "unrealized_profit_aud": unrealized_profit,
                "trade": (
                    "BUY+SELL"
                    if btc_bought > 0 and desired_sell > 0
                    else "BUY"
                    if btc_bought > 0
                    else "SELL"
                    if desired_sell > 0
                    else "HOLD"
                ),
            }
        )

    result = pd.DataFrame(trades)

    if result.empty:
        return result, {}

    final = result.iloc[-1]

    first_date = result["date"].iloc[0]
    last_date = result["date"].iloc[-1]

    years = max(
        (last_date - first_date).days / 365.25,
        1 / 365.25,
    )

    starting_capital = total_capital
    ending_wealth = float(final["total_wealth_aud"])

    cagr = annualized_return(
        starting_capital,
        ending_wealth,
        years,
    )

    period_returns = result["total_wealth_aud"].pct_change().dropna()
    periods_per_year = {"Daily": 365.0, "Weekly": 52.0, "Monthly": 12.0}.get(params["frequency"], 52.0)
    sharpe = np.nan
    sortino = np.nan
    if len(period_returns) > 1 and period_returns.std() > 0:
        sharpe = float(period_returns.mean() / period_returns.std() * np.sqrt(periods_per_year))
    downside = period_returns[period_returns < 0]
    if len(downside) > 1 and downside.std() > 0:
        sortino = float(period_returns.mean() / downside.std() * np.sqrt(periods_per_year))

    summary = {
        "starting_capital_aud": starting_capital,
        "ending_wealth_aud": ending_wealth,
        "cash_aud": float(final["cash_aud"]),
        "btc_held": float(final["btc_held"]),
        "btc_value_aud": float(final["btc_value_aud"]),
        "cumulative_invested_aud": float(final["cumulative_invested"]),
        "realized_profit_aud": float(
            result["realized_profit_aud"].sum()
        ),
        "unrealized_profit_aud": float(
            final["unrealized_profit_aud"]
        ),
        "fees_aud": float(result["fees_aud"].sum()),
        "return_pct": (
            ending_wealth / starting_capital - 1.0
        ) * 100.0,
        "cagr_pct": cagr * 100.0,
        "max_drawdown_pct": max_drawdown(
            result["total_wealth_aud"]
        ) * 100.0,
        "periods": len(result),
        "final_risk": float(final["risk_score"]),
        "final_btc_weight": float(final["actual_btc_weight"]),
        "final_target_weight": float(final["target_btc_weight"]),
        "final_avg_cost_aud": float(final["btc_avg_cost_aud"]),
        "sharpe": sharpe,
        "sortino": sortino,
    }

    return result, summary


# ================================================================
# Benchmark Strategies
# ================================================================

def simulate_equal_dca(data, total_capital):
    """Equal DCA using the same execution dates as the dynamic strategy."""
    if data.empty or total_capital <= 0:
        return {}, pd.DataFrame()

    periods = len(data)
    amount_per_period = total_capital / periods

    cash = total_capital
    btc = 0.0
    rows = []

    for timestamp, row in data.iterrows():
        price_aud = float(row["price"]) / float(row["usd_per_aud"])

        if price_aud <= 0:
            continue

        buy = min(amount_per_period, cash)
        btc += buy / price_aud
        cash -= buy

        wealth = cash + btc * price_aud

        rows.append(
            {
                "date": timestamp,
                "btc": btc,
                "cash": cash,
                "wealth": wealth,
            }
        )

    if not rows:
        return {}, pd.DataFrame()

    result = pd.DataFrame(rows)
    final = result.iloc[-1]

    summary = {
        "btc": float(final["btc"]),
        "cash": float(final["cash"]),
        "wealth": float(final["wealth"]),
        "return_pct": (
            final["wealth"] / total_capital - 1
        ) * 100,
        "max_drawdown_pct": max_drawdown(
            result["wealth"]
        ) * 100,
    }

    return summary, result


def simulate_lump_sum(data, total_capital):
    """Invest all capital on the first execution date."""
    if data.empty or total_capital <= 0:
        return {}, pd.DataFrame()

    first = data.iloc[0]
    price_aud_first = float(first["price"]) / float(first["usd_per_aud"])

    if price_aud_first <= 0:
        return {}, pd.DataFrame()

    btc = total_capital / price_aud_first
    rows = []

    for timestamp, row in data.iterrows():
        price_aud = float(row["price"]) / float(row["usd_per_aud"])
        wealth = btc * price_aud

        rows.append(
            {
                "date": timestamp,
                "btc": btc,
                "wealth": wealth,
            }
        )

    result = pd.DataFrame(rows)
    final = result.iloc[-1]

    summary = {
        "btc": btc,
        "wealth": float(final["wealth"]),
        "return_pct": (
            final["wealth"] / total_capital - 1
        ) * 100,
        "max_drawdown_pct": max_drawdown(
            result["wealth"]
        ) * 100,
    }

    return summary, result


# ================================================================
# Forward Deployment Planner
# ================================================================

def build_forward_plan(
    capital,
    start_date,
    end_date,
    frequency,
    risk_score,
    btc_price_usd,
    usd_per_aud,
):
    """
    Creates a forward deployment schedule.

    Future BTC price and risk are deliberately NOT forecast.
    The current supplied risk score is used to calculate the planned
    DCA intensity for the schedule.

    This is a planning tool, not a price prediction.
    """
    if end_date <= start_date:
        return pd.DataFrame()

    dates = pd.date_range(
        start=start_date,
        end=end_date,
        freq="D",
        tz="UTC",
    )

    if frequency == "Weekly":
        dates = dates[dates.dayofweek == 0]

    elif frequency == "Monthly":
        # First day of each month.
        dates = dates[dates.day == 1]

    if len(dates) == 0:
        dates = pd.DatetimeIndex(
            [pd.Timestamp(start_date, tz="UTC")]
        )

    n = len(dates)

    risk_multiplier = interpolate(
        DEFAULT_RISK_POINTS,
        clamp(risk_score, 0, 1),
    )

    base = capital / n

    # Keep the forward schedule conservative and visible.
    max_period = capital * DEFAULT_MAX_PERIOD_PCT

    rows = []
    cumulative = 0.0

    for i, date in enumerate(dates, start=1):
        time_progress = i / n
        target_cumulative = capital * time_progress
        gap = target_cumulative - cumulative

        pressure = 1.0 + (
            clamp(gap / capital, -0.50, 1.00)
            * DEFAULT_PRESSURE_STRENGTH
        )
        pressure = clamp(pressure, 0.50, float(params.get("pressure_cap", DEFAULT_PRESSURE_CAP)))

        planned = min(
            base * risk_multiplier * pressure,
            max_period,
            max(0.0, capital - cumulative),
        )

        cumulative += planned

        rows.append(
            {
                "date": date,
                "risk_score": risk_score,
                "risk_multiplier": risk_multiplier,
                "time_progress_pct": time_progress * 100,
                "target_cumulative_aud": target_cumulative,
                "planned_buy_aud": planned,
                "cumulative_planned_aud": cumulative,
                "capital_remaining_aud": capital - cumulative,
                "btc_price_usd_reference": btc_price_usd,
                "usd_per_aud_reference": usd_per_aud,
                "btc_estimate_at_reference_price": (
                    planned * usd_per_aud / btc_price_usd
                    if btc_price_usd > 0
                    else 0.0
                ),
            }
        )

    return pd.DataFrame(rows)


# ================================================================
# Walk-forward Optimisation (V3.2)
# ================================================================

def normalized_percentile_score(frame):
    """Heuristic multi-objective score using comparable 0..1 percentile ranks."""
    if frame.empty:
        return frame
    out = frame.copy()
    out["return_rank"] = out["return_pct"].rank(pct=True)
    out["drawdown_rank"] = (-out["max_drawdown_pct"].abs()).rank(pct=True)
    out["risk_adjusted_rank"] = out["sortino"].fillna(out["sharpe"]).fillna(-999).rank(pct=True)
    out["btc_rank"] = out["btc_held"].rank(pct=True)
    out["score"] = 0.40*out["return_rank"] + 0.25*out["drawdown_rank"] + 0.20*out["risk_adjusted_rank"] + 0.15*out["btc_rank"]
    return out


def walk_forward_optimise(df_full, base_params):
    """70/30 train/validation search. Risk weights stay fixed to limit overfitting."""
    if df_full.empty:
        return pd.DataFrame(), pd.DataFrame()
    start=base_params["start_date"]; end=base_params["end_date"]
    span=end-start
    split=start + span*0.70
    candidates=[]
    for max_buy in (0.05,0.08,0.12):
        for pressure in (0.50,0.75,1.00):
            for val_strength in (0.50,0.75,1.00):
                p=dict(base_params)
                p.update({"max_period_pct":max_buy,"pressure_strength":pressure,"valuation_strength":val_strength,"end_date":split})
                trades, sm=simulate_dynamic_dca(df_full,p)
                if not sm: continue
                candidates.append({"max_buy_pct":max_buy,"pressure_strength":pressure,"valuation_strength":val_strength,
                    "return_pct":sm["return_pct"],"max_drawdown_pct":sm["max_drawdown_pct"],"sharpe":sm.get("sharpe",np.nan),"sortino":sm.get("sortino",np.nan),"btc_held":sm["btc_held"]})
    train=normalized_percentile_score(pd.DataFrame(candidates)).sort_values("score",ascending=False)
    if train.empty: return train,pd.DataFrame()
    validations=[]
    for _,row in train.head(min(5,len(train))).iterrows():
        p=dict(base_params)
        p.update({"max_period_pct":float(row.max_buy_pct),"pressure_strength":float(row.pressure_strength),"valuation_strength":float(row.valuation_strength),"start_date":split,"end_date":end})
        trades, sm=simulate_dynamic_dca(df_full,p)
        if not sm: continue
        validations.append({"max_buy_pct":row.max_buy_pct,"pressure_strength":row.pressure_strength,"valuation_strength":row.valuation_strength,
            "return_pct":sm["return_pct"],"max_drawdown_pct":sm["max_drawdown_pct"],"sharpe":sm.get("sharpe",np.nan),"sortino":sm.get("sortino",np.nan),"btc_held":sm["btc_held"]})
    validation=normalized_percentile_score(pd.DataFrame(validations)).sort_values("score",ascending=False)
    return train,validation


# ================================================================
# Streamlit UI
# ================================================================

st.set_page_config(
    page_title="BTC Dynamic DCA & Tactical Rebalancer V3.2.1 FULL",
    layout="wide",
)

st.title("Bitcoin Dynamic DCA & Tactical Rebalancer V3.2.1 FULL")
st.caption(
    "Composite on-chain/technical risk + valuation + time deployment + deployment pressure + "
    "portfolio-target rebalancing"
)

# ------------------------------------------------
# Sidebar
# ------------------------------------------------

with st.sidebar:
    st.header("Mode")

    mode = st.radio(
        "Analysis Mode",
        [
            "Historical Backtest",
            "Forward Deployment Plan",
        ],
    )

    st.divider()

    st.header("Capital")

    total_capital_aud = st.number_input(
        "Starting Capital (AUD)",
        min_value=1000.0,
        max_value=100_000_000.0,
        value=500_000.0,
        step=10_000.0,
    )

    frequency = st.selectbox(
        "Execution Frequency",
        ["Weekly", "Daily", "Monthly"],
        index=0,
    )

    day_map = {
        "Monday": 0,
        "Tuesday": 1,
        "Wednesday": 2,
        "Thursday": 3,
        "Friday": 4,
        "Saturday": 5,
        "Sunday": 6,
    }

    selected_day_name = st.selectbox(
        "Weekly Execution Day",
        list(day_map.keys()),
        index=0,
        disabled=(frequency != "Weekly"),
    )

    selected_day = day_map[selected_day_name]

    st.divider()

    st.header("Risk Model")

    risk_model = st.radio(
        "Risk Metric",
        [
            "Composite V3.2",
            "Power Law Trend",
            "SMA Ratio (200-day)",
        ],
        index=0,
    )

    st.caption(
        "Risk score: 0 = very cheap / high allocation, "
        "1 = very expensive / low allocation."
    )

    st.subheader("V3.2 Composite Weights")
    weight_mvrv = st.slider("MVRV Z-Score Weight", 0.0, 1.0, 0.30, 0.05)
    weight_power_law = st.slider("Power Law Weight", 0.0, 1.0, 0.25, 0.05)
    weight_mayer = st.slider("Mayer Multiple Weight", 0.0, 1.0, 0.20, 0.05)
    weight_fear_greed = st.slider("Fear & Greed Weight", 0.0, 1.0, 0.15, 0.05)
    weight_rsi = st.slider("RSI Weight", 0.0, 1.0, 0.10, 0.05)
    regime_overlay = st.slider("BGeometrics Regime Overlay", 0.0, 0.50, DEFAULT_REGIME_OVERLAY, 0.05)

    st.divider()

    st.header("Dynamic DCA Controls")

    pressure_strength = st.slider(
        "Deployment Pressure Strength",
        min_value=0.0,
        max_value=1.5,
        value=DEFAULT_PRESSURE_STRENGTH,
        step=0.05,
        help=(
            "Controls how strongly the strategy catches up when it is "
            "behind its time-based deployment target."
        ),
    )

    max_period_pct = st.slider(
        "Maximum Buy Per Period (% of starting capital)",
        min_value=1.0,
        max_value=50.0,
        value=DEFAULT_MAX_PERIOD_PCT * 100,
        step=1.0,
    ) / 100.0

    valuation_strength = st.slider(
        "Valuation Multiplier Strength", 0.25, 1.50, DEFAULT_VALUATION_STRENGTH, 0.05,
        help="Scales buys using Power Law fair value / current price."
    )
    min_valuation_mult = st.slider("Minimum Valuation Multiplier", 0.25, 1.00, DEFAULT_MIN_VALUATION_MULT, 0.05)
    max_valuation_mult = st.slider("Maximum Valuation Multiplier", 1.00, 4.00, DEFAULT_MAX_VALUATION_MULT, 0.10)
    pressure_cap = st.slider("Maximum Deployment Pressure", 1.0, 4.0, DEFAULT_PRESSURE_CAP, 0.1)

    min_cash_reserve_pct = st.slider(
        "Minimum Cash Reserve (%)",
        min_value=0.0,
        max_value=50.0,
        value=DEFAULT_MIN_CASH_RESERVE_PCT * 100,
        step=1.0,
    ) / 100.0

    st.divider()

    st.header("Rebalancing / Profit Taking")

    sell_threshold = st.slider(
        "Rebalance Threshold",
        min_value=0.0,
        max_value=0.20,
        value=DEFAULT_SELL_THRESHOLD,
        step=0.01,
        help=(
            "The strategy only sells when actual BTC portfolio weight "
            "is this much above its risk-derived target."
        ),
    )

    max_sell_pct_period = st.slider(
        "Maximum BTC Sold Per Period (%)",
        min_value=1.0,
        max_value=100.0,
        value=DEFAULT_MAX_SELL_PCT_PERIOD * 100,
        step=1.0,
    ) / 100.0

    max_btc_weight = st.slider("Maximum BTC Portfolio Weight", 0.25, 1.00, 1.00, 0.05)
    min_days_between_sales = st.number_input("Minimum Days Between Sales", min_value=0, max_value=365, value=DEFAULT_MIN_DAYS_BETWEEN_SALES, step=1)

    fee_pct = st.number_input(
        "Trading Fee (%)",
        min_value=0.0,
        max_value=5.0,
        value=DEFAULT_FEE_PCT * 100,
        step=0.01,
    ) / 100.0


# ================================================================
# Dates / Parameters
# ================================================================

today = dt.datetime.now(timezone.utc).date()
genesis = dt.date(2009, 1, 3)

if mode == "Historical Backtest":
    start_date = st.sidebar.date_input(
        "Backtest Start Date",
        value=dt.date(2020, 1, 1),
        min_value=genesis,
        max_value=today,
        format="DD/MM/YYYY",
    )

    end_date = st.sidebar.date_input(
        "Backtest End Date",
        value=today,
        min_value=start_date,
        max_value=today,
        format="DD/MM/YYYY",
    )

else:
    start_date = st.sidebar.date_input(
        "Deployment Start Date",
        value=today,
        min_value=today,
        format="DD/MM/YYYY",
    )

    end_date = st.sidebar.date_input(
        "Deployment End Date",
        value=today + timedelta(days=90),
        min_value=start_date + timedelta(days=1),
        format="DD/MM/YYYY",
    )

    st.sidebar.divider()
    st.sidebar.header("Live Market Inputs")

    # Automatically derive today's reference inputs. BGeometrics is preferred
    # for BTC price and external risk series; Blockchain.com / Frankfurter are
    # fallbacks so Forward Plan does not require routine manual data entry.
    snapshot_end = dt.datetime.combine(today, dt.time.max, tzinfo=timezone.utc)
    snapshot_start = snapshot_end - timedelta(days=450)
    bg_token = get_bgeometrics_token()

    with st.spinner("Loading current BTC market inputs..."):
        snapshot_prices = fetch_btc_history(snapshot_start, snapshot_end)
        snapshot_bg = fetch_bgeometrics_bundle(
            snapshot_start - timedelta(days=30), snapshot_end, bg_token
        )
        snapshot_fx = fetch_aud_usd_rates(
            (today - timedelta(days=14)), today
        )

    auto_btc_price = np.nan
    if snapshot_bg is not None and not snapshot_bg.empty and "bg_btc_price" in snapshot_bg.columns:
        live_price_series = pd.to_numeric(snapshot_bg["bg_btc_price"], errors="coerce").dropna()
        if not live_price_series.empty:
            auto_btc_price = float(live_price_series.iloc[-1])
    if (not np.isfinite(auto_btc_price) or auto_btc_price <= 0) and not snapshot_prices.empty:
        auto_btc_price = float(snapshot_prices["price"].dropna().iloc[-1])
    if not np.isfinite(auto_btc_price) or auto_btc_price <= 0:
        auto_btc_price = 100_000.0

    auto_usd_per_aud = 0.65
    if snapshot_fx is not None and not snapshot_fx.empty:
        fx_valid = pd.to_numeric(snapshot_fx, errors="coerce").dropna()
        if not fx_valid.empty:
            auto_usd_per_aud = float(fx_valid.iloc[-1])

    auto_risk_score = 0.50
    snapshot_signal_date = None
    if not snapshot_prices.empty:
        snapshot_market = align_fx_to_dates(snapshot_prices, snapshot_fx, fallback=auto_usd_per_aud)
        snapshot_market = merge_bgeometrics(snapshot_market, snapshot_bg)
        snapshot_params = {
            "pl_cheap": DEFAULT_PL_CHEAP,
            "pl_expensive": DEFAULT_PL_EXPENSIVE,
            "fund_cheap": DEFAULT_FUND_CHEAP,
            "fund_expensive": DEFAULT_FUND_EXPENSIVE,
            "composite_weights": {
                "mvrv": weight_mvrv,
                "power_law": weight_power_law,
                "mayer": weight_mayer,
                "fear_greed": weight_fear_greed,
                "rsi": weight_rsi,
            },
            "regime_overlay": regime_overlay,
            "valuation_strength": valuation_strength,
            "min_valuation_mult": min_valuation_mult,
            "max_valuation_mult": max_valuation_mult,
        }
        snapshot_market = add_risk_indicators(snapshot_market, risk_model, snapshot_params)
        valid_risk = pd.to_numeric(snapshot_market["risk_score"], errors="coerce").dropna()
        if not valid_risk.empty:
            auto_risk_score = float(valid_risk.iloc[-1])
            snapshot_signal_date = valid_risk.index[-1]

    st.sidebar.caption(
        f"Auto BTC: ${auto_btc_price:,.0f} USD • "
        f"Auto risk: {auto_risk_score:.3f} • "
        f"USD/AUD: {auto_usd_per_aud:.4f}"
    )

    override_risk = st.sidebar.checkbox("Override calculated risk score", value=False)
    if override_risk:
        forward_risk_score = st.sidebar.slider(
            "Scenario Risk Score",
            min_value=0.0,
            max_value=1.0,
            value=float(round(auto_risk_score, 2)),
            step=0.01,
        )
    else:
        forward_risk_score = auto_risk_score

    override_price = st.sidebar.checkbox("Override current BTC price", value=False)
    if override_price:
        forward_btc_price_usd = st.sidebar.number_input(
            "Scenario BTC Price (USD)",
            min_value=1.0,
            value=float(round(auto_btc_price, 2)),
            step=1_000.0,
        )
    else:
        forward_btc_price_usd = auto_btc_price

    override_fx = st.sidebar.checkbox("Override AUD/USD rate", value=False)
    if override_fx:
        forward_usd_per_aud = st.sidebar.number_input(
            "Scenario USD per AUD",
            min_value=0.10,
            max_value=2.00,
            value=float(round(auto_usd_per_aud, 4)),
            step=0.01,
        )
    else:
        forward_usd_per_aud = auto_usd_per_aud


if end_date <= start_date:
    st.error("End date must be after start date.")
    st.stop()


params = {
    "risk_model": risk_model,
    "frequency": frequency,
    "day_of_week": selected_day,
    "fund_cheap": DEFAULT_FUND_CHEAP,
    "fund_expensive": DEFAULT_FUND_EXPENSIVE,
    "pl_cheap": DEFAULT_PL_CHEAP,
    "pl_expensive": DEFAULT_PL_EXPENSIVE,
    "total_capital_aud": total_capital_aud,
    "pressure_strength": pressure_strength,
    "max_period_pct": max_period_pct,
    "min_cash_reserve_pct": min_cash_reserve_pct,
    "sell_threshold": sell_threshold,
    "max_sell_pct_period": max_sell_pct_period,
    "fee_pct": fee_pct,
    "composite_weights": {
        "mvrv": weight_mvrv,
        "power_law": weight_power_law,
        "mayer": weight_mayer,
        "fear_greed": weight_fear_greed,
        "rsi": weight_rsi,
    },
    "regime_overlay": regime_overlay,
    "valuation_strength": valuation_strength,
    "min_valuation_mult": min_valuation_mult,
    "max_valuation_mult": max_valuation_mult,
    "pressure_cap": pressure_cap,
    "max_btc_weight": max_btc_weight,
    "min_days_between_sales": min_days_between_sales,
    "start_date": dt.datetime.combine(
        start_date,
        dt.time.min,
        tzinfo=timezone.utc,
    ),
    "end_date": dt.datetime.combine(
        end_date,
        dt.time.max,
        tzinfo=timezone.utc,
    ),
}


# ================================================================
# Historical Backtest
# ================================================================

if mode == "Historical Backtest":

    with st.spinner("Loading BTC and AUD/USD history..."):
        df_full = fetch_btc_history(
            params["start_date"],
            params["end_date"],
        )

        fx_series = fetch_aud_usd_rates(
            params["start_date"],
            params["end_date"],
        )

        bg_token = get_bgeometrics_token()
        bg_data = fetch_bgeometrics_bundle(
            params["start_date"] - timedelta(days=300),
            params["end_date"],
            bg_token,
        )

    if df_full.empty:
        st.error("No BTC price data was returned.")
        st.stop()

    df_full = align_fx_to_dates(
        df_full,
        fx_series,
    )
    df_full = merge_bgeometrics(df_full, bg_data)

    # Run strategy.
    trade_df, summary = simulate_dynamic_dca(
        df_full,
        params,
    )

    if trade_df.empty:
        st.error(
            "The simulation produced no observations. "
            "Try a wider date range."
        )
        st.stop()

    # Benchmarks use same execution dates.
    benchmark_data = df_full[
        (df_full.index >= params["start_date"]) &
        (df_full.index <= params["end_date"])
    ].copy()

    benchmark_data = select_execution_dates(
        benchmark_data,
        frequency,
        selected_day,
    )

    equal_summary, equal_df = simulate_equal_dca(
        benchmark_data,
        total_capital_aud,
    )

    lump_summary, lump_df = simulate_lump_sum(
        benchmark_data,
        total_capital_aud,
    )

    # ------------------------------------------------------------
    # Metrics
    # ------------------------------------------------------------

    st.subheader("Dynamic Strategy")

    signal_cols = st.columns(4)
    signal_cols[0].metric("Current Composite Risk", f"{summary['final_risk']:.3f}")
    signal_cols[1].metric("Target BTC Weight", f"{summary['final_target_weight']:.1%}")
    signal_cols[2].metric("Sharpe", "n/a" if pd.isna(summary.get('sharpe')) else f"{summary['sharpe']:.2f}")
    signal_cols[3].metric("Sortino", "n/a" if pd.isna(summary.get('sortino')) else f"{summary['sortino']:.2f}")

    c1, c2, c3, c4, c5, c6 = st.columns(6)

    c1.metric(
        "Ending Wealth",
        f"${summary['ending_wealth_aud']:,.0f}",
        format_pct(summary["return_pct"]),
    )

    c2.metric(
        "BTC Held",
        f"{summary['btc_held']:.6f}",
    )

    c3.metric(
        "Cash",
        f"${summary['cash_aud']:,.0f}",
    )

    c4.metric(
        "Invested",
        f"${summary['cumulative_invested_aud']:,.0f}",
    )

    c5.metric(
        "Max Drawdown",
        f"{summary['max_drawdown_pct']:.2f}%",
    )

    c6.metric(
        "CAGR",
        f"{summary['cagr_pct']:.2f}%",
    )

    # ------------------------------------------------------------
    # Benchmark table
    # ------------------------------------------------------------

    st.subheader("Strategy Comparison")

    comparison = pd.DataFrame(
        [
            {
                "Strategy": "Dynamic Risk DCA",
                "Ending Wealth (AUD)": summary["ending_wealth_aud"],
                "Return": summary["return_pct"],
                "Max Drawdown": summary["max_drawdown_pct"],
                "BTC": summary["btc_held"],
            },
            {
                "Strategy": "Equal DCA",
                "Ending Wealth (AUD)": equal_summary.get(
                    "wealth", 0
                ),
                "Return": equal_summary.get(
                    "return_pct", 0
                ),
                "Max Drawdown": equal_summary.get(
                    "max_drawdown_pct", 0
                ),
                "BTC": equal_summary.get(
                    "btc", 0
                ),
            },
            {
                "Strategy": "Lump Sum",
                "Ending Wealth (AUD)": lump_summary.get(
                    "wealth", 0
                ),
                "Return": lump_summary.get(
                    "return_pct", 0
                ),
                "Max Drawdown": lump_summary.get(
                    "max_drawdown_pct", 0
                ),
                "BTC": lump_summary.get(
                    "btc", 0
                ),
            },
        ]
    )

    display_comparison = comparison.copy()
    display_comparison["Ending Wealth (AUD)"] = (
        display_comparison["Ending Wealth (AUD)"]
        .map(lambda x: f"${x:,.0f}")
    )
    display_comparison["Return"] = (
        display_comparison["Return"]
        .map(lambda x: f"{x:+.2f}%")
    )
    display_comparison["Max Drawdown"] = (
        display_comparison["Max Drawdown"]
        .map(lambda x: f"{x:.2f}%")
    )
    display_comparison["BTC"] = (
        display_comparison["BTC"]
        .map(lambda x: f"{x:.6f}")
    )

    st.dataframe(
        display_comparison,
        use_container_width=True,
        hide_index=True,
    )

    # ------------------------------------------------------------
    # Risk chart
    # ------------------------------------------------------------

    st.subheader("Risk Score, BTC Price & Fair Value")

    fig_risk = go.Figure()

    fig_risk.add_trace(
        go.Scatter(
            x=trade_df["date"],
            y=trade_df["risk_score"],
            name="Risk Score",
            line=dict(width=2),
        )
    )

    fig_risk.add_trace(
        go.Scatter(
            x=trade_df["date"],
            y=trade_df["dca_multiplier"],
            name="DCA Multiplier",
            yaxis="y2",
            line=dict(width=2, dash="dash"),
        )
    )

    fig_risk.update_layout(
        height=500,
        template="plotly_dark",
        xaxis=dict(
            title="Date",
            rangeslider=dict(visible=True),
        ),
        yaxis=dict(
            title="Risk Score",
            range=[0, 1],
        ),
        yaxis2=dict(
            title="DCA Multiplier",
            overlaying="y",
            side="right",
        ),
    )

    st.plotly_chart(
        fig_risk,
        use_container_width=True,
    )

    # ------------------------------------------------------------
    # Portfolio chart
    # ------------------------------------------------------------

    st.subheader("Portfolio Wealth & BTC Allocation")

    fig_portfolio = go.Figure()

    fig_portfolio.add_trace(
        go.Scatter(
            x=trade_df["date"],
            y=trade_df["total_wealth_aud"],
            name="Total Wealth (AUD)",
            line=dict(width=3),
        )
    )

    fig_portfolio.add_trace(
        go.Scatter(
            x=trade_df["date"],
            y=trade_df["cash_aud"],
            name="Cash (AUD)",
            line=dict(width=2, dash="dash"),
        )
    )

    fig_portfolio.add_trace(
        go.Scatter(
            x=trade_df["date"],
            y=trade_df["btc_value_aud"],
            name="BTC Value (AUD)",
            line=dict(width=2),
        )
    )

    fig_portfolio.update_layout(
        height=500,
        template="plotly_dark",
        xaxis=dict(
            title="Date",
            rangeslider=dict(visible=True),
        ),
        yaxis=dict(
            title="AUD",
            tickprefix="$",
        ),
    )

    st.plotly_chart(
        fig_portfolio,
        use_container_width=True,
    )

    # ------------------------------------------------------------
    # BTC price and trade markers
    # ------------------------------------------------------------

    st.subheader("BTC Price & Trade Execution")

    fig_trades = go.Figure()

    fig_trades.add_trace(
        go.Scatter(
            x=trade_df["date"],
            y=trade_df["price_usd"],
            name="BTC Price (USD)",
            line=dict(width=2),
        )
    )

    buys = trade_df[trade_df["buy_aud"] > 0]
    sells = trade_df[trade_df["sell_btc"] > 0]

    if not buys.empty:
        fig_trades.add_trace(
            go.Scatter(
                x=buys["date"],
                y=buys["price_usd"],
                mode="markers",
                name="BUY",
                marker=dict(
                    size=8,
                    symbol="triangle-up",
                ),
            )
        )

    if not sells.empty:
        fig_trades.add_trace(
            go.Scatter(
                x=sells["date"],
                y=sells["price_usd"],
                mode="markers",
                name="SELL / REBALANCE",
                marker=dict(
                    size=8,
                    symbol="triangle-down",
                ),
            )
        )

    fig_trades.update_layout(
        height=550,
        template="plotly_dark",
        xaxis=dict(
            title="Date",
            rangeslider=dict(visible=True),
        ),
        yaxis=dict(
            title="BTC Price (USD)",
            tickprefix="$",
        ),
    )

    st.plotly_chart(
        fig_trades,
        use_container_width=True,
    )

    # ------------------------------------------------------------
    # Deployment pressure chart
    # ------------------------------------------------------------

    st.subheader("Deployment Pressure")

    fig_pressure = go.Figure()

    fig_pressure.add_trace(
        go.Scatter(
            x=trade_df["date"],
            y=trade_df["target_cumulative_invested"],
            name="Time Target",
            line=dict(width=2, dash="dash"),
        )
    )

    fig_pressure.add_trace(
        go.Scatter(
            x=trade_df["date"],
            y=trade_df["cumulative_invested"],
            name="Actual Invested",
            line=dict(width=3),
        )
    )

    fig_pressure.update_layout(
        height=450,
        template="plotly_dark",
        xaxis=dict(
            title="Date",
            rangeslider=dict(visible=True),
        ),
        yaxis=dict(
            title="AUD",
            tickprefix="$",
        ),
    )

    st.plotly_chart(
        fig_pressure,
        use_container_width=True,
    )

    # ------------------------------------------------------------
    # Detailed activity
    # ------------------------------------------------------------

    st.subheader("Detailed Activity History")

    display_df = trade_df[
        [
            "date",
            "trade",
            "price_usd",
            "risk_score",
            "dca_multiplier",
            "valuation_multiplier",
            "target_btc_weight",
            "actual_btc_weight",
            "pressure",
            "buy_aud",
            "btc_bought",
            "sell_btc",
            "sell_proceeds_aud",
            "realized_profit_aud",
            "btc_held",
            "cash_aud",
            "total_wealth_aud",
        ]
    ].copy()

    display_df["date"] = display_df["date"].dt.strftime(
        "%d/%m/%Y"
    )

    display_df["price_usd"] = display_df[
        "price_usd"
    ].map(lambda x: f"${x:,.0f}")

    display_df["risk_score"] = display_df[
        "risk_score"
    ].map(lambda x: f"{x:.3f}")

    display_df["dca_multiplier"] = display_df[
        "dca_multiplier"
    ].map(lambda x: f"{x:.2f}x")

    display_df["valuation_multiplier"] = display_df["valuation_multiplier"].map(lambda x: f"{x:.2f}x")

    display_df["target_btc_weight"] = display_df[
        "target_btc_weight"
    ].map(lambda x: f"{x:.1%}")

    display_df["actual_btc_weight"] = display_df[
        "actual_btc_weight"
    ].map(lambda x: f"{x:.1%}")

    display_df["pressure"] = display_df[
        "pressure"
    ].map(lambda x: f"{x:.2f}x")

    for col in [
        "buy_aud",
        "sell_proceeds_aud",
        "realized_profit_aud",
        "cash_aud",
        "total_wealth_aud",
    ]:
        display_df[col] = display_df[col].map(
            lambda x: f"${x:,.0f}"
        )

    for col in [
        "btc_bought",
        "sell_btc",
        "btc_held",
    ]:
        display_df[col] = display_df[col].map(
            lambda x: f"{x:.6f}"
        )

    display_df.columns = [
        "Date",
        "Action",
        "BTC USD",
        "Risk",
        "DCA Mult.",
        "Valuation Mult.",
        "Target BTC %",
        "Actual BTC %",
        "Pressure",
        "Buy AUD",
        "BTC Bought",
        "BTC Sold",
        "Sale Proceeds",
        "Realized Profit",
        "BTC Balance",
        "Cash",
        "Total Wealth",
    ]

    st.dataframe(
        display_df,
        use_container_width=True,
        height=500,
        hide_index=True,
    )

    # ------------------------------------------------------------
    # CSV download
    # ------------------------------------------------------------

    st.download_button(
        "Download Full Backtest CSV",
        data=trade_df.to_csv(index=False).encode("utf-8"),
        file_name="btc_dynamic_dca_v3_2_full_backtest.csv",
        mime="text/csv",
    )

    st.subheader("Data Quality")
    quality_rows=[]
    for col,label in [("price","BTC price"),("usd_per_aud","AUD/USD"),("mvrv_z","MVRV Z-Score"),("fear_greed","Fear & Greed"),("regime_score","Regime Score")]:
        coverage = float(df_full[col].notna().mean()*100) if col in df_full.columns else 0.0
        quality_rows.append({"Series":label,"Coverage %":coverage})
    st.dataframe(pd.DataFrame(quality_rows),hide_index=True,use_container_width=True)
    st.caption(f"BGeometrics token: {'loaded' if get_bgeometrics_token() else 'not loaded'} • No future BTC prices are fabricated in historical mode.")

    with st.expander("Walk-forward Optimisation (advanced)"):
        st.write("Searches a deliberately small parameter grid on the first 70% of the period and validates the best candidates on the untouched final 30%.")
        if st.button("Run Walk-forward Optimiser", type="secondary"):
            with st.spinner("Running train/validation parameter search..."):
                train_opt, validation_opt = walk_forward_optimise(df_full, params)
            st.markdown("**Training leaders**")
            st.dataframe(train_opt.head(10),hide_index=True,use_container_width=True)
            st.markdown("**Out-of-sample validation**")
            st.dataframe(validation_opt,hide_index=True,use_container_width=True)


# ================================================================
# Forward Plan
# ================================================================

else:

    risk_multiplier = interpolate(
        DEFAULT_RISK_POINTS,
        forward_risk_score,
    )

    st.subheader("Forward Deployment Plan")

    c1, c2, c3, c4 = st.columns(4)

    c1.metric(
        "Capital",
        f"${total_capital_aud:,.0f} AUD",
    )

    c2.metric(
        "Current Risk Score",
        f"{forward_risk_score:.2f}",
    )

    c3.metric(
        "DCA Multiplier",
        f"{risk_multiplier:.2f}x",
    )

    c4.metric(
        "Reference BTC Price",
        f"${forward_btc_price_usd:,.0f}",
    )

    plan = build_forward_plan(
        total_capital_aud,
        start_date,
        end_date,
        frequency,
        forward_risk_score,
        forward_btc_price_usd,
        forward_usd_per_aud,
    )

    if plan.empty:
        st.warning("No deployment dates were generated.")
        st.stop()

    final_planned = float(
        plan["cumulative_planned_aud"].iloc[-1]
    )

    remaining = float(
        plan["capital_remaining_aud"].iloc[-1]
    )

    p1, p2, p3 = st.columns(3)

    p1.metric(
        "Planned Deployment",
        f"${final_planned:,.0f}",
    )

    p2.metric(
        "Capital Remaining",
        f"${remaining:,.0f}",
    )

    p3.metric(
        "Number of Purchases",
        f"{len(plan)}",
    )

    st.info(
        "Forward planning warning: future BTC prices and future risk "
        "scores are unknown. This schedule uses automatically loaded current "
        "market inputs (or your optional scenario overrides) as reference "
        "assumptions. It does not predict future prices."
    )

    # ------------------------------------------------------------
    # Plan chart
    # ------------------------------------------------------------

    fig_plan = go.Figure()

    fig_plan.add_trace(
        go.Scatter(
            x=plan["date"],
            y=plan["target_cumulative_aud"],
            name="Time Target",
            line=dict(width=2, dash="dash"),
        )
    )

    fig_plan.add_trace(
        go.Scatter(
            x=plan["date"],
            y=plan["cumulative_planned_aud"],
            name="Planned Deployment",
            line=dict(width=3),
        )
    )

    fig_plan.update_layout(
        height=450,
        template="plotly_dark",
        xaxis=dict(title="Date"),
        yaxis=dict(
            title="AUD",
            tickprefix="$",
        ),
    )

    st.plotly_chart(
        fig_plan,
        use_container_width=True,
    )

    # ------------------------------------------------------------
    # Plan table
    # ------------------------------------------------------------

    display_plan = plan.copy()

    display_plan["date"] = display_plan["date"].dt.strftime(
        "%d/%m/%Y"
    )

    display_plan["risk_score"] = display_plan[
        "risk_score"
    ].map(lambda x: f"{x:.2f}")

    display_plan["risk_multiplier"] = display_plan[
        "risk_multiplier"
    ].map(lambda x: f"{x:.2f}x")

    display_plan["time_progress_pct"] = display_plan[
        "time_progress_pct"
    ].map(lambda x: f"{x:.1f}%")

    for col in [
        "target_cumulative_aud",
        "planned_buy_aud",
        "cumulative_planned_aud",
        "capital_remaining_aud",
    ]:
        display_plan[col] = display_plan[col].map(
            lambda x: f"${x:,.0f}"
        )

    display_plan = display_plan[
        [
            "date",
            "risk_score",
            "risk_multiplier",
            "time_progress_pct",
            "target_cumulative_aud",
            "planned_buy_aud",
            "cumulative_planned_aud",
            "capital_remaining_aud",
        ]
    ]

    display_plan.columns = [
        "Date",
        "Risk",
        "DCA Mult.",
        "Time Progress",
        "Time Target",
        "Planned Buy",
        "Cumulative Planned",
        "Capital Remaining",
    ]

    st.dataframe(
        display_plan,
        use_container_width=True,
        height=500,
        hide_index=True,
    )

    st.download_button(
        "Download Forward Plan CSV",
        data=plan.to_csv(index=False).encode("utf-8"),
        file_name="btc_forward_deployment_plan.csv",
        mime="text/csv",
    )


# ================================================================
# Methodology Notes
# ================================================================

with st.expander("How the new Dynamic DCA engine works"):
    st.markdown(
        """
### 1. Time-based deployment

The model calculates how much of the starting capital would normally
have been deployed by each point in the selected period.

### 2. Risk-weighted DCA

The risk score is converted into a smooth multiplier:

- Low risk / cheap BTC -> larger purchase
- Neutral risk -> approximately normal DCA
- High risk / expensive BTC -> smaller purchase
- Extreme risk -> potentially zero new purchases

### 3. Deployment pressure

The model compares:

**Target cumulative investment**

against

**Actual cumulative investment**

If the strategy is behind schedule, the next purchase is increased.

This prevents the model from simply sitting on cash indefinitely after
a long expensive period.

### 4. Maximum purchase size

A hard per-period maximum prevents one unusually cheap reading from
consuming the entire portfolio.

### 5. Portfolio-target profit taking

Instead of automatically selling a fixed percentage of all BTC, the
model calculates a risk-derived target BTC portfolio weight.

Example:

If the model says the target BTC allocation is 40%, but BTC has risen
until it represents 60% of the portfolio, the strategy sells enough BTC
to move toward the 40% target.

### 6. Cost basis

The model tracks the weighted-average AUD acquisition cost of BTC.
Realized profit is therefore:

**Sale proceeds - cost basis of BTC sold - fees**

rather than incorrectly treating all sale proceeds as profit.

### 7. Forward mode

Forward mode deliberately does not fill future dates with today's BTC
price and pretend that those are future observations. Future prices and
future risk scores are unknown, so the forward planner clearly labels
today's market values as assumptions.
"""
    )
