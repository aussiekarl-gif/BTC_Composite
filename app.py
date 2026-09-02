#!/usr/bin/env python3
"""
BTC Dynamic DCA & Tactical Rebalancing Simulator V3.6.5 FULL
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
DEFAULT_BUY_POINTS = [
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

REQUEST_HEADERS = {"User-Agent": "BTC-DCA-Simulator/3.4"}

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

# V3.6 strict valuation-zone execution defaults.
DEFAULT_BUY_THRESHOLD = 0.25
DEFAULT_SELL_RISK_THRESHOLD = 0.75
DEFAULT_MIN_TRADE_AUD = 100.0
DEFAULT_MIN_RISK_COMPONENTS = 3

DEFAULT_PRICE_POSITION_WINDOW = 365
DEFAULT_RISK_CALIBRATION_MIN_PERIODS = 180
DEFAULT_RISK_CALIBRATION_WINDOW = 1460  # ~4 years
DEFAULT_RISK_CALIBRATION_BLEND = 0.85
DEFAULT_PRICE_POSITION_WEIGHT = 0.20

DEFAULT_ABSOLUTE_RISK_WEIGHT = 0.60
DEFAULT_RELATIVE_RISK_WEIGHT = 0.40
DEFAULT_DRAWDOWN_WINDOW = 365
DEFAULT_FIXED_DCA_AUD = 1000.0
DEFAULT_BUY_POINTS = [
    (0.00, 4.00), (0.10, 3.25), (0.20, 2.50), (0.30, 1.65),
    (0.35, 1.20), (0.40, 0.60), (0.45, 0.00), (1.00, 0.00),
]
DEFAULT_SELL_POINTS = [
    (0.00, 0.00), (0.69, 0.00), (0.70, 0.02), (0.75, 0.04),
    (0.80, 0.07), (0.85, 0.11), (0.90, 0.16), (0.95, 0.22), (1.00, 0.30),
]
DEFAULT_TREND_ER_PERIOD = 20
DEFAULT_TREND_FAST = 2
DEFAULT_TREND_SLOW = 30
DEFAULT_TREND_RANGE_PERIOD = 14
DEFAULT_TREND_BAND_MULT = 2.0
DEFAULT_TREND_BUY_BULL = 1.10
DEFAULT_TREND_BUY_NEUTRAL = 1.00
DEFAULT_TREND_BUY_BEAR = 0.90
DEFAULT_TREND_SELL_BULL = 0.50
DEFAULT_TREND_SELL_NEUTRAL = 1.00
DEFAULT_TREND_SELL_BEAR = 1.25


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


def _adaptive_ma(close, er_period=20, fast=2, slow=30):
    c = pd.to_numeric(close, errors="coerce").astype(float)
    change = c.diff(er_period).abs()
    volatility = c.diff().abs().rolling(er_period, min_periods=er_period).sum()
    er = (change / volatility.replace(0, np.nan)).clip(0, 1).fillna(0)
    fast_sc = 2.0 / (fast + 1.0)
    slow_sc = 2.0 / (slow + 1.0)
    alpha = (er * (fast_sc - slow_sc) + slow_sc) ** 2
    vals = c.to_numpy(); alphas = alpha.to_numpy()
    out = np.full(len(c), np.nan, dtype=float)
    valid = np.where(np.isfinite(vals))[0]
    if len(valid) == 0:
        return pd.Series(out, index=c.index)
    first = int(valid[0]); out[first] = vals[first]
    for i in range(first + 1, len(vals)):
        prev = out[i-1] if np.isfinite(out[i-1]) else vals[i]
        price = vals[i]
        if not np.isfinite(price):
            out[i] = prev; continue
        a = alphas[i] if np.isfinite(alphas[i]) else slow_sc ** 2
        out[i] = prev + a * (price - prev)
    return pd.Series(out, index=c.index)


def add_optimized_trend_replica(data, er_period=20, fast=2, slow=30, range_period=14, band_mult=2.0):
    """Non-proprietary BTC-adaptive trend approximation; not the proprietary InvestAnswers formula."""
    x = data.copy()
    close = pd.to_numeric(x["price"], errors="coerce").astype(float)
    ama = _adaptive_ma(close, er_period, fast, slow)
    rng = close.diff().abs().ewm(span=range_period, adjust=False, min_periods=range_period).mean()
    floor = close * close.pct_change().rolling(30, min_periods=10).std().fillna(0) * 0.35
    ar = pd.concat([rng, floor], axis=1).max(axis=1)
    upper = ama + band_mult * ar; lower = ama - band_mult * ar; slope = ama.diff(5)
    state=[]; current=0
    for i in range(len(x)):
        p,u,l,sl = close.iloc[i],upper.iloc[i],lower.iloc[i],slope.iloc[i]
        if np.isfinite(p) and np.isfinite(u) and np.isfinite(l):
            if p > u and (not np.isfinite(sl) or sl >= 0): current=1
            elif p < l and (not np.isfinite(sl) or sl <= 0): current=-1
        state.append(current)
    denom=(band_mult*ar).replace(0,np.nan)
    x["optimized_trend_ma"]=ama; x["optimized_trend_upper"]=upper; x["optimized_trend_lower"]=lower
    x["optimized_trend_state"]=pd.Series(state,index=x.index,dtype=int)
    x["optimized_trend"]=x["optimized_trend_state"].map({1:"BULLISH / BLUE",0:"NEUTRAL",-1:"BEARISH / ORANGE"})
    x["optimized_trend_strength"]=((close-ama)/denom).clip(-2,2).fillna(0)
    x["optimized_trend_flip"]=x["optimized_trend_state"].diff().fillna(0).astype(int)
    return x


def _piecewise_score(points, value):
    """Interpolate a monotonic 0..1 score from x/y points."""
    if value is None or not np.isfinite(value):
        return np.nan
    return float(interpolate(points, float(value)))


def _expanding_percentile(series, min_periods=180, rolling_window=1460):
    """
    Historical percentile without look-ahead.

    For each date, compare the current raw composite only with values available
    up to and including that date. A rolling cap can be used so very old cycle
    history does not dominate forever.
    """
    values = pd.to_numeric(series, errors="coerce").to_numpy(dtype=float)
    out = np.full(len(values), np.nan, dtype=float)

    for i, x in enumerate(values):
        if not np.isfinite(x):
            continue

        start = max(0, i - int(rolling_window) + 1)
        hist = values[start:i+1]
        hist = hist[np.isfinite(hist)]

        if len(hist) < int(min_periods):
            continue

        # Mid-rank percentile gives stable 0..1 calibration.
        less = np.sum(hist < x)
        equal = np.sum(hist == x)
        out[i] = (less + 0.5 * equal) / len(hist)

    return pd.Series(out, index=series.index)


def add_risk_indicators(data, risk_model, params):
    """
    V3.6 valuation risk engine.

    Design goals:
      * stronger relationship with BTC valuation / price regime
      * use the full 0.00..1.00 trading band
      * no look-ahead in historical calibration
      * keep Regime Score separate from valuation risk
      * preserve raw composite for auditability
    """
    result = data.copy()

    # -------------------------
    # Core market calculations
    # -------------------------
    result["sma_200"] = result["price"].rolling(
        window=200, min_periods=100
    ).mean()
    result["mayer"] = result["price"] / result["sma_200"]

    delta = result["price"].diff()
    gain = delta.clip(lower=0).ewm(
        alpha=1/14, adjust=False, min_periods=14
    ).mean()
    loss = (-delta.clip(upper=0)).ewm(
        alpha=1/14, adjust=False, min_periods=14
    ).mean()
    rs = gain / loss.replace(0, np.nan)
    result["rsi_14"] = 100 - 100 / (1 + rs)

    # -------------------------
    # Power-law valuation
    # -------------------------
    pl_scores, fair_values, pl_residuals = [], [], []
    for timestamp, row in result.iterrows():
        score, fair_value = power_law_score(
            timestamp,
            float(row["price"]),
            params["pl_cheap"],
            params["pl_expensive"],
        )
        pl_scores.append(score)
        fair_values.append(fair_value)

        if fair_value > 0 and row["price"] > 0:
            pl_residuals.append(
                math.log10(float(row["price"]) / fair_value)
            )
        else:
            pl_residuals.append(np.nan)

    result["power_law_score"] = pd.Series(
        pl_scores, index=result.index, dtype=float
    )
    result["fair_value"] = fair_values
    result["power_law_residual"] = pl_residuals
    result["price_to_fair"] = (
        result["price"] / result["fair_value"].replace(0, np.nan)
    )

    # -------------------------
    # Stronger piecewise mappings
    # -------------------------
    # MVRV-Z: nonlinear so elevated readings can actually approach 1.0.
    mvrv_z_points = [
        (-1.0, 0.00),
        (-0.5, 0.05),
        (0.0, 0.12),
        (0.5, 0.22),
        (1.0, 0.34),
        (1.5, 0.50),
        (2.0, 0.66),
        (2.5, 0.78),
        (3.0, 0.87),
        (4.0, 0.95),
        (5.0, 1.00),
    ]

    # Mayer: mature-market valuation bands.
    mayer_points = [
        (0.55, 0.00),
        (0.70, 0.08),
        (0.85, 0.18),
        (1.00, 0.30),
        (1.20, 0.45),
        (1.40, 0.60),
        (1.60, 0.74),
        (1.80, 0.84),
        (2.10, 0.93),
        (2.50, 1.00),
    ]

    rsi_points = [
        (15, 0.00),
        (25, 0.08),
        (35, 0.20),
        (45, 0.36),
        (55, 0.52),
        (65, 0.70),
        (75, 0.86),
        (85, 0.96),
        (95, 1.00),
    ]

    fear_points = [
        (0, 0.00),
        (10, 0.05),
        (20, 0.12),
        (30, 0.22),
        (40, 0.34),
        (50, 0.48),
        (60, 0.62),
        (70, 0.76),
        (80, 0.88),
        (90, 0.96),
        (100, 1.00),
    ]

    result["mvrv_score"] = pd.to_numeric(
        result.get("mvrv_z"), errors="coerce"
    ).apply(lambda x: _piecewise_score(mvrv_z_points, x))

    result["mayer_score"] = pd.to_numeric(
        result["mayer"], errors="coerce"
    ).apply(lambda x: _piecewise_score(mayer_points, x))

    result["rsi_score"] = pd.to_numeric(
        result["rsi_14"], errors="coerce"
    ).apply(lambda x: _piecewise_score(rsi_points, x))

    result["fear_greed_score"] = pd.to_numeric(
        result.get("fear_greed"), errors="coerce"
    ).apply(lambda x: _piecewise_score(fear_points, x))

    # -------------------------
    # 365-day price-position score
    # -------------------------
    pp_window = int(
        params.get(
            "price_position_window",
            DEFAULT_PRICE_POSITION_WINDOW,
        )
    )
    rolling_low = result["price"].rolling(
        pp_window, min_periods=max(90, pp_window // 4)
    ).min()
    rolling_high = result["price"].rolling(
        pp_window, min_periods=max(90, pp_window // 4)
    ).max()

    result["price_position_365"] = (
        (result["price"] - rolling_low)
        / (rolling_high - rolling_low).replace(0, np.nan)
    ).clip(0, 1)

    # Slight convexity so the top quartile matters more.
    result["price_position_score"] = (
        result["price_position_365"].pow(1.25)
    ).clip(0, 1)

    # -------------------------
    # Legacy single-factor modes
    # -------------------------
    if risk_model == "Power Law Trend":
        result["raw_risk_score"] = result["power_law_score"]
        result["risk_components_available"] = 1

    elif risk_model == "SMA Ratio (200-day)":
        result["raw_risk_score"] = result["mayer_score"]
        result["risk_components_available"] = (
            result["mayer"].notna().astype(int)
        )

    else:
        # New recommended weights:
        # 25% power law
        # 25% MVRV-Z
        # 20% 365d price position
        # 15% Mayer
        # 10% Fear & Greed
        #  5% RSI
        weights = {
            "power_law": 0.25,
            "mvrv": 0.25,
            "price_position": 0.20,
            "mayer": 0.15,
            "fear_greed": 0.10,
            "rsi": 0.05,
        }

        component_map = {
            "power_law": "power_law_score",
            "mvrv": "mvrv_score",
            "price_position": "price_position_score",
            "mayer": "mayer_score",
            "fear_greed": "fear_greed_score",
            "rsi": "rsi_score",
        }

        numerator = pd.Series(0.0, index=result.index)
        denominator = pd.Series(0.0, index=result.index)
        available_count = pd.Series(
            0, index=result.index, dtype=int
        )

        for key, col in component_map.items():
            weight = float(weights[key])
            values = pd.to_numeric(
                result[col], errors="coerce"
            )
            available = values.notna()

            numerator += values.fillna(0.0) * weight
            denominator += available.astype(float) * weight
            available_count += available.astype(int)

        result["raw_risk_score"] = (
            numerator / denominator.replace(0, np.nan)
        ).clip(0, 1)
        result["risk_components_available"] = available_count

        min_components = int(
            params.get(
                "min_risk_components",
                DEFAULT_MIN_RISK_COMPONENTS,
            )
        )
        result.loc[
            result["risk_components_available"] < min_components,
            "raw_risk_score",
        ] = np.nan

    # -------------------------
    # Historical calibration
    # -------------------------
    min_periods = int(
        params.get(
            "risk_calibration_min_periods",
            DEFAULT_RISK_CALIBRATION_MIN_PERIODS,
        )
    )
    cal_window = int(
        params.get(
            "risk_calibration_window",
            DEFAULT_RISK_CALIBRATION_WINDOW,
        )
    )
    cal_blend = float(
        params.get(
            "risk_calibration_blend",
            DEFAULT_RISK_CALIBRATION_BLEND,
        )
    )

    result["risk_percentile"] = _expanding_percentile(
        result["raw_risk_score"],
        min_periods=min_periods,
        rolling_window=cal_window,
    )

    # V3.6 hybrid calibration.
    # V3.5 could make risk collapse during a prolonged decline because the
    # percentile kept comparing the market with its own recent highs.
    # V3.6 retains an absolute valuation anchor and uses percentile as a
    # secondary relative-cycle input.

    absolute_weight = float(
        params.get("absolute_risk_weight", DEFAULT_ABSOLUTE_RISK_WEIGHT)
    )
    relative_weight = float(
        params.get("relative_risk_weight", DEFAULT_RELATIVE_RISK_WEIGHT)
    )

    rolling_peak_365 = result["price"].rolling(
        DEFAULT_DRAWDOWN_WINDOW,
        min_periods=90,
    ).max()

    result["drawdown_365"] = (
        result["price"] / rolling_peak_365.replace(0, np.nan) - 1.0
    ).clip(-1.0, 0.0)

    # A drawdown reduces risk gradually, but does not make an expensive market
    # instantly "ultra-cheap".
    result["drawdown_risk_modifier"] = (
        1.0 + 0.60 * result["drawdown_365"]
    ).clip(0.50, 1.00)

    result["absolute_risk_anchor"] = (
        result["raw_risk_score"] * result["drawdown_risk_modifier"]
    ).clip(0, 1)

    relative_risk = result["risk_percentile"].where(
        result["risk_percentile"].notna(),
        result["raw_risk_score"],
    )

    total_weight = max(absolute_weight + relative_weight, 1e-9)

    result["risk_score"] = (
        absolute_weight * result["absolute_risk_anchor"]
        + relative_weight * relative_risk
    ) / total_weight

    # Guardrail against false ultra-low readings:
    # final risk cannot sit more than 0.15 below the raw valuation composite.
    result["risk_floor"] = (
        result["raw_risk_score"] - 0.15
    ).clip(0, 1)

    result["risk_score"] = pd.concat(
        [result["risk_score"], result["risk_floor"]],
        axis=1,
    ).max(axis=1).clip(0, 1)

    # -------------------------
    # Context kept separate
    # -------------------------
    result["regime_context_score"] = (
        pd.to_numeric(
            result.get("regime_score"), errors="coerce"
        )
        / 100.0
    ).clip(0, 1)

    # Trading curves use calibrated risk.
    result["dca_multiplier"] = result["risk_score"].apply(
        lambda x: (
            interpolate(DEFAULT_BUY_POINTS, x)
            if pd.notna(x)
            else 0.0
        )
    )

    result["target_btc_weight"] = result["risk_score"].apply(
        lambda x: (
            interpolate(
                DEFAULT_TARGET_BTC_POINTS, x
            )
            if pd.notna(x)
            else np.nan
        )
    )

    result["valuation_multiplier"] = (
        (
            result["fair_value"]
            / result["price"].replace(0, np.nan)
        )
        .pow(
            float(
                params.get(
                    "valuation_strength",
                    DEFAULT_VALUATION_STRENGTH,
                )
            )
        )
        .clip(
            float(
                params.get(
                    "min_valuation_mult",
                    DEFAULT_MIN_VALUATION_MULT,
                )
            ),
            float(
                params.get(
                    "max_valuation_mult",
                    DEFAULT_MAX_VALUATION_MULT,
                )
            ),
        )
        .fillna(1.0)
    )

    result = add_optimized_trend_replica(
        result,
        er_period=int(
            params.get(
                "trend_er_period",
                DEFAULT_TREND_ER_PERIOD,
            )
        ),
        fast=int(
            params.get(
                "trend_fast",
                DEFAULT_TREND_FAST,
            )
        ),
        slow=int(
            params.get(
                "trend_slow",
                DEFAULT_TREND_SLOW,
            )
        ),
        range_period=int(
            params.get(
                "trend_range_period",
                DEFAULT_TREND_RANGE_PERIOD,
            )
        ),
        band_mult=float(
            params.get(
                "trend_band_mult",
                DEFAULT_TREND_BAND_MULT,
            )
        ),
    )

    result["risk_zone"] = pd.cut(
        result["risk_score"],
        bins=[
            -np.inf, 0.15, 0.30, 0.50, 0.70, 0.85, np.inf
        ],
        labels=[
            "DEEP VALUE",
            "VALUE",
            "LOW / NEUTRAL",
            "ELEVATED",
            "HIGH",
            "EXTREME",
        ],
    ).astype(str)

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

def _trend_factor(state, bull, neutral, bear):
    return float(bull if state > 0 else bear if state < 0 else neutral)


def dca_day_signal(risk, buy_threshold, sell_threshold):
    """
    Current-day DCA signal based on the latest calculated valuation risk.
    This is not a forecast of future risk.
    """
    if risk is None or not np.isfinite(risk):
        return {
            "eligible": False,
            "label": "NO DATA",
            "quality": "Insufficient risk data",
            "multiplier": 0.0,
        }

    risk = float(clamp(risk, 0.0, 1.0))
    mult = float(interpolate(DEFAULT_BUY_POINTS, risk))

    if risk <= buy_threshold:
        if mult >= 2.50:
            quality = "STRONG DCA"
        elif mult >= 1.25:
            quality = "GOOD DCA"
        else:
            quality = "LIGHT DCA"

        return {
            "eligible": True,
            "label": "YES",
            "quality": quality,
            "multiplier": mult,
        }

    if risk >= sell_threshold:
        return {
            "eligible": False,
            "label": "NO",
            "quality": "SELL ZONE",
            "multiplier": 0.0,
        }

    return {
        "eligible": False,
        "label": "NO",
        "quality": "HOLD",
        "multiplier": 0.0,
    }


def simulate_dynamic_dca(df_full, params):
    """V3.6: strict BUY-low / HOLD / SELL-high. No same-period BUY+SELL and no forced catch-up."""
    if df_full.empty: return pd.DataFrame(), {}
    df=df_full[(df_full.index>=params["start_date"]) & (df_full.index<=params["end_date"])].copy()
    if df.empty: return pd.DataFrame(), {}
    df=add_risk_indicators(df,params["risk_model"],params)
    execution=select_execution_dates(df,params["frequency"],params["day_of_week"])
    if execution.empty: return pd.DataFrame(), {}

    capital=float(params["total_capital_aud"]); cash=capital; btc=0.0; basis=0.0
    invested=sold_total=realized_total=fees_total=0.0; last_sale=None; peak=capital; trades=[]
    n=len(execution); base=capital*float(params.get("base_dca_pct",0.01))
    buy_th=float(params.get("buy_threshold",DEFAULT_BUY_THRESHOLD)); sell_th=float(params.get("sell_risk_threshold",DEFAULT_SELL_RISK_THRESHOLD))

    for i,(ts,row) in enumerate(execution.iterrows(),start=1):
        price_usd=float(row["price"]); fx=float(row["usd_per_aud"])
        if price_usd<=0 or fx<=0: continue
        paud=price_usd/fx
        risk=float(row["risk_score"]) if pd.notna(row["risk_score"]) else np.nan
        trend=int(row.get("optimized_trend_state",0)) if pd.notna(row.get("optimized_trend_state",0)) else 0
        if not np.isfinite(risk): zone="HOLD"; reason="Insufficient risk components"
        elif risk<=buy_th: zone="BUY"; reason=f"Risk {risk:.3f} <= BUY threshold {buy_th:.2f}"
        elif risk>=sell_th and params.get("require_weak_trend_for_sell",False) and trend>0: zone="HOLD"; reason="High valuation but trend remains bullish"
        elif risk>=sell_th: zone="SELL"; reason=f"Risk {risk:.3f} >= SELL threshold {sell_th:.2f}"
        else: zone="HOLD"; reason="Risk between BUY and SELL zones"

        buy_mult=interpolate(DEFAULT_BUY_POINTS,risk) if np.isfinite(risk) else 0.0
        sell_frac=interpolate(DEFAULT_SELL_POINTS,risk) if np.isfinite(risk) else 0.0
        val_mult=float(row.get("valuation_multiplier",1.0))
        buy_tf=_trend_factor(trend,params.get("trend_buy_bull",DEFAULT_TREND_BUY_BULL),params.get("trend_buy_neutral",DEFAULT_TREND_BUY_NEUTRAL),params.get("trend_buy_bear",DEFAULT_TREND_BUY_BEAR))
        sell_tf=_trend_factor(trend,params.get("trend_sell_bull",DEFAULT_TREND_SELL_BULL),params.get("trend_sell_neutral",DEFAULT_TREND_SELL_NEUTRAL),params.get("trend_sell_bear",DEFAULT_TREND_SELL_BEAR))
        min_trade=float(params.get("min_trade_aud",DEFAULT_MIN_TRADE_AUD))
        buy=btc_bought=sell_btc=sell_proceeds=rp=buy_fee=sell_fee=0.0; action="HOLD"

        if zone=="BUY":
            reserve=capital*float(params.get("min_cash_reserve_pct",0.0)); available=max(0.0,cash-reserve)
            raw=base*buy_mult*val_mult*buy_tf; cap=capital*float(params.get("max_period_pct",DEFAULT_MAX_PERIOD_PCT))
            buy=min(raw,cap,available)
            if buy>=min_trade:
                buy_fee=buy*float(params.get("fee_pct",0.0)); net=max(0.0,buy-buy_fee); btc_bought=net/paud
                btc+=btc_bought; basis+=net; cash-=buy; invested+=net; fees_total+=buy_fee; action="BUY"
                reason+=f" | {buy_mult:.2f}x risk × {val_mult:.2f}x valuation × {buy_tf:.2f}x trend"
            else: buy=0.0
        elif zone=="SELL" and btc>0:
            allowed=last_sale is None or (ts-last_sale).days>=int(params.get("min_days_between_sales",DEFAULT_MIN_DAYS_BETWEEN_SALES))
            if allowed:
                btc_value=btc*paud; gross=min(btc_value*sell_frac*sell_tf,btc_value*float(params.get("max_sell_pct_period",DEFAULT_MAX_SELL_PCT_PERIOD)),btc_value)
                if gross>=min_trade:
                    sell_btc=gross/paud; sell_fee=gross*float(params.get("fee_pct",0.0)); sell_proceeds=gross-sell_fee
                    basis_sold=basis*(sell_btc/btc) if btc>0 else 0.0; rp=sell_proceeds-basis_sold
                    btc-=sell_btc; basis=max(0.0,basis-basis_sold); cash+=sell_proceeds; sold_total+=sell_proceeds; realized_total+=rp; fees_total+=sell_fee; last_sale=ts; action="SELL"
                    reason+=f" | sell curve {sell_frac:.1%} × trend {sell_tf:.2f}x"

        btc_value=btc*paud; wealth=cash+btc_value; peak=max(peak,wealth); weight=btc_value/wealth if wealth>0 else 0.0; avg=basis/btc if btc>0 else 0.0
        ref_target=interpolate(DEFAULT_TARGET_BTC_POINTS,risk) if np.isfinite(risk) else np.nan
        target_ref=capital*(i/n)
        trades.append({
            "date":ts,"price_usd":price_usd,"btc_price_aud":paud,"fair_value_usd":float(row["fair_value"]),
            "risk_score":risk,"risk_zone":("DEEP VALUE" if np.isfinite(risk) and risk<=.2 else "VALUE" if np.isfinite(risk) and risk<=buy_th else "EXTREME" if np.isfinite(risk) and risk>=.9 else "HIGH" if np.isfinite(risk) and risk>=sell_th else "NEUTRAL"),
            "risk_components":int(row.get("risk_components_available",0)),"dca_multiplier":buy_mult,"sell_fraction":sell_frac,"valuation_multiplier":val_mult,
            "target_btc_weight":ref_target,"actual_btc_weight":weight,"optimized_trend":row.get("optimized_trend","NEUTRAL"),"optimized_trend_state":trend,"trend_strength":float(row.get("optimized_trend_strength",0.0)),
            "decision_zone":zone,"decision_reason":reason,"time_progress":i/n,"target_cumulative_invested":target_ref,"cumulative_invested":invested,"deployment_gap":target_ref-invested,"pressure":1.0,
            "buy_aud":buy if action=="BUY" else 0.0,"btc_bought":btc_bought,"sell_btc":sell_btc,"sell_proceeds_aud":sell_proceeds,"realized_profit_aud":rp,"fees_aud":buy_fee+sell_fee,
            "btc_held":btc,"btc_cost_basis_aud":basis,"btc_avg_cost_aud":avg,"cash_aud":cash,"btc_value_aud":btc_value,"total_wealth_aud":wealth,"unrealized_profit_aud":btc_value-basis,"trade":action
        })
    result=pd.DataFrame(trades)
    if result.empty: return result,{}

    # V3.6 execution invariants.
    if ((result["buy_aud"] > 0) & (result["sell_btc"] > 0)).any():
        raise RuntimeError("V3.6 invariant failed: simultaneous BUY and SELL.")

    if (
        (result["buy_aud"] > 0)
        & (
            result["risk_score"].isna()
            | (result["risk_score"] > buy_th)
        )
    ).any():
        raise RuntimeError("V3.6 invariant failed: BUY outside BUY zone.")

    if (
        (result["sell_btc"] > 0)
        & (
            result["risk_score"].isna()
            | (result["risk_score"] < sell_th)
        )
    ).any():
        raise RuntimeError("V3.6 invariant failed: SELL outside SELL zone.")

    if (result["cash_aud"] < -0.01).any() or (result["btc_held"] < -1e-12).any():
        raise RuntimeError("V3.6 invariant failed: negative cash or BTC.")

    hard_buy_cap = capital * float(params.get("max_period_pct", DEFAULT_MAX_PERIOD_PCT))
    if (result["buy_aud"] > hard_buy_cap + 0.01).any():
        raise RuntimeError("V3.6 invariant failed: BUY above hard cap.")
    final=result.iloc[-1]; years=max((result.date.iloc[-1]-result.date.iloc[0]).days/365.25,1/365.25); endw=float(final.total_wealth_aud)
    rets=result.total_wealth_aud.pct_change().dropna(); ppy={"Daily":365.0,"Weekly":52.0,"Monthly":12.0}.get(params["frequency"],52.0)
    sharpe=float(rets.mean()/rets.std()*np.sqrt(ppy)) if len(rets)>1 and rets.std()>0 else np.nan; down=rets[rets<0]; sortino=float(rets.mean()/down.std()*np.sqrt(ppy)) if len(down)>1 and down.std()>0 else np.nan
    summary={"starting_capital_aud":capital,"ending_wealth_aud":endw,"cash_aud":float(final.cash_aud),"btc_held":float(final.btc_held),"btc_value_aud":float(final.btc_value_aud),"cumulative_invested_aud":float(final.cumulative_invested),"realized_profit_aud":float(result.realized_profit_aud.sum()),"unrealized_profit_aud":float(final.unrealized_profit_aud),"fees_aud":float(result.fees_aud.sum()),"return_pct":(endw/capital-1)*100,"cagr_pct":annualized_return(capital,endw,years)*100,"max_drawdown_pct":max_drawdown(result.total_wealth_aud)*100,"periods":len(result),"final_risk":float(final.risk_score) if pd.notna(final.risk_score) else np.nan,"final_btc_weight":float(final.actual_btc_weight),"final_target_weight":float(final.target_btc_weight) if pd.notna(final.target_btc_weight) else np.nan,"final_avg_cost_aud":float(final.btc_avg_cost_aud),"final_trend":str(final.optimized_trend),"final_decision":str(final.decision_zone),"sharpe":sharpe,"sortino":sortino,"buy_count":int((result.trade=="BUY").sum()),"sell_count":int((result.trade=="SELL").sum())}
    return result,summary


# ================================================================
def simulate_dca_backtest(
    df_full,
    params,
    base_dca_aud,
    dca_frequency,
    use_risk_model=True,
):
    """
    Historical DCA backtest with NO capital ceiling.

    With risk model:
      actual contribution = base DCA * risk multiplier,
      and no contribution outside the BUY zone.

    Without risk model:
      actual contribution = base DCA every execution.

    This mode never sells and never assumes a starting cash balance.
    """
    if df_full.empty:
        return pd.DataFrame(), {}

    df = df_full[
        (df_full.index >= params["start_date"])
        & (df_full.index <= params["end_date"])
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
        dca_frequency,
        params["day_of_week"],
    )

    if execution.empty:
        return pd.DataFrame(), {}

    btc = 0.0
    cumulative_invested = 0.0
    cumulative_fees = 0.0
    rows = []

    for timestamp, row in execution.iterrows():
        price_usd = float(row["price"])
        usd_per_aud = float(row["usd_per_aud"])

        if price_usd <= 0 or usd_per_aud <= 0:
            continue

        price_aud = price_usd / usd_per_aud
        risk = (
            float(row["risk_score"])
            if pd.notna(row["risk_score"])
            else np.nan
        )

        if use_risk_model:
            risk_mult = (
                float(interpolate(DEFAULT_BUY_POINTS, risk))
                if np.isfinite(risk)
                else 0.0
            )
            contribution = (
                float(base_dca_aud) * risk_mult
                if np.isfinite(risk)
                and risk <= float(params["buy_threshold"])
                else 0.0
            )
            signal = "BUY" if contribution > 0 else "HOLD"
        else:
            risk_mult = 1.0
            contribution = float(base_dca_aud)
            signal = "FIXED DCA"

        fee = contribution * float(params.get("fee_pct", 0.0))
        net_contribution = max(0.0, contribution - fee)
        btc_bought = (
            net_contribution / price_aud
            if price_aud > 0
            else 0.0
        )

        btc += btc_bought
        cumulative_invested += contribution
        cumulative_fees += fee

        btc_value = btc * price_aud
        pnl = btc_value - cumulative_invested
        roi_pct = (
            (btc_value / cumulative_invested - 1.0) * 100.0
            if cumulative_invested > 0
            else 0.0
        )
        avg_cost_aud = (
            cumulative_invested / btc
            if btc > 0
            else 0.0
        )

        rows.append(
            {
                "date": timestamp,
                "price_usd": price_usd,
                "btc_price_aud": price_aud,
                "risk_score": risk,
                "risk_multiplier": risk_mult,
                "base_dca_aud": float(base_dca_aud),
                "dca_frequency": dca_frequency,
                "use_risk_model": bool(use_risk_model),
                "actual_buy_aud": contribution,
                "btc_bought": btc_bought,
                "btc_held": btc,
                "cumulative_invested_aud": cumulative_invested,
                "cumulative_fees_aud": cumulative_fees,
                "btc_value_aud": btc_value,
                "pnl_aud": pnl,
                "roi_pct": roi_pct,
                "avg_cost_aud": avg_cost_aud,
                "signal": signal,
            }
        )

    result = pd.DataFrame(rows)

    if result.empty:
        return result, {}

    final = result.iloc[-1]

    summary = {
        "base_dca_aud": float(base_dca_aud),
        "frequency": dca_frequency,
        "use_risk_model": bool(use_risk_model),
        "total_invested_aud": float(final["cumulative_invested_aud"]),
        "btc_held": float(final["btc_held"]),
        "btc_value_aud": float(final["btc_value_aud"]),
        "pnl_aud": float(final["pnl_aud"]),
        "roi_pct": float(final["roi_pct"]),
        "avg_cost_aud": float(final["avg_cost_aud"]),
        "fees_aud": float(final["cumulative_fees_aud"]),
        "execution_count": int(len(result)),
        "buy_count": int((result["actual_buy_aud"] > 0).sum()),
    }

    return result, summary


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
    buy_threshold,
    sell_threshold,
    base_dca_pct,
    max_period_pct,
):
    """Conditional forward planner with no forced deployment."""
    if end_date <= start_date:
        return pd.DataFrame()

    dates = pd.date_range(start=start_date, end=end_date, freq="D", tz="UTC")
    if frequency == "Weekly":
        dates = dates[dates.dayofweek == 0]
    elif frequency == "Monthly":
        dates = dates[dates.day == 1]

    if len(dates) == 0:
        dates = pd.DatetimeIndex([pd.Timestamp(start_date, tz="UTC")])

    base = capital * float(base_dca_pct)
    hard_cap = capital * float(max_period_pct)

    if not np.isfinite(risk_score):
        decision = "HOLD"
        buy_multiplier = 0.0
    elif risk_score <= buy_threshold:
        decision = "BUY"
        buy_multiplier = interpolate(DEFAULT_BUY_POINTS, clamp(risk_score, 0, 1))
    elif risk_score >= sell_threshold:
        decision = "SELL ZONE — NO BUY"
        buy_multiplier = 0.0
    else:
        decision = "HOLD — NO BUY"
        buy_multiplier = 0.0

    current_signal = dca_day_signal(
        risk_score,
        buy_threshold,
        sell_threshold,
    )

    rows = []
    cumulative = 0.0

    for date in dates:
        planned = 0.0
        if decision == "BUY":
            planned = min(
                base * buy_multiplier,
                hard_cap,
                max(0.0, capital - cumulative),
            )

        cumulative += planned

        rows.append(
            {
                "date": date,
                "risk_score": risk_score,
                "decision": decision,
                "dca_today": current_signal["label"],
                "dca_quality": current_signal["quality"],
                "buy_multiplier": buy_multiplier,
                "base_dca_aud": base,
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
# Walk-forward Optimisation (V3.6)
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
    """V3.6 70/30 train/validation search. Valuation weights stay fixed to reduce overfitting."""
    if df_full.empty:
        return pd.DataFrame(), pd.DataFrame()
    start=base_params["start_date"]; end=base_params["end_date"]; split=start+(end-start)*0.70
    candidates=[]
    for max_buy in (0.05,0.08,0.12):
        for buy_th in (0.35,0.40,0.45):
            for sell_th in (0.70,0.75,0.80):
                for val_strength in (0.50,0.75,1.00):
                    if sell_th <= buy_th: continue
                    q=dict(base_params); q.update({"max_period_pct":max_buy,"buy_threshold":buy_th,"sell_risk_threshold":sell_th,"valuation_strength":val_strength,"end_date":split})
                    trades,sm=simulate_dynamic_dca(df_full,q)
                    if not sm: continue
                    candidates.append({"max_buy_pct":max_buy,"buy_threshold":buy_th,"sell_threshold":sell_th,"valuation_strength":val_strength,"return_pct":sm["return_pct"],"max_drawdown_pct":sm["max_drawdown_pct"],"sharpe":sm.get("sharpe",np.nan),"sortino":sm.get("sortino",np.nan),"btc_held":sm["btc_held"],"buys":sm.get("buy_count",0),"sells":sm.get("sell_count",0)})
    train=normalized_percentile_score(pd.DataFrame(candidates)).sort_values("score",ascending=False)
    if train.empty: return train,pd.DataFrame()
    vals=[]
    for _,row in train.head(min(8,len(train))).iterrows():
        q=dict(base_params); q.update({"max_period_pct":float(row.max_buy_pct),"buy_threshold":float(row.buy_threshold),"sell_risk_threshold":float(row.sell_threshold),"valuation_strength":float(row.valuation_strength),"start_date":split,"end_date":end})
        trades,sm=simulate_dynamic_dca(df_full,q)
        if not sm: continue
        vals.append({"max_buy_pct":row.max_buy_pct,"buy_threshold":row.buy_threshold,"sell_threshold":row.sell_threshold,"valuation_strength":row.valuation_strength,"return_pct":sm["return_pct"],"max_drawdown_pct":sm["max_drawdown_pct"],"sharpe":sm.get("sharpe",np.nan),"sortino":sm.get("sortino",np.nan),"btc_held":sm["btc_held"],"buys":sm.get("buy_count",0),"sells":sm.get("sell_count",0)})
    return train, normalized_percentile_score(pd.DataFrame(vals)).sort_values("score",ascending=False)


# ================================================================
# Streamlit UI
# ================================================================

st.set_page_config(
    page_title="BTC Dynamic DCA V3.6.5 FULL",
    layout="wide",
)

st.title("Bitcoin Dynamic DCA V3.6.5 FULL — Buy Low / Sell High")
st.caption("Version 3.6.5 FULL • CALIBRATED 0–1 RISK • STRICT BUY / HOLD / SELL • Optimized Trend Replica")
st.caption("Simplified controls • fixed calibrated composite risk • no forced deployment")

# ------------------------------------------------
# Sidebar
# ------------------------------------------------

with st.sidebar:
    st.header("Mode")

    mode = st.radio(
        "Analysis Mode",
        [
            "Historical Backtest",
            "DCA Backtest",
            "Forward Deployment Plan",
        ],
    )

    st.divider()

    day_map = {
        "Monday": 0,
        "Tuesday": 1,
        "Wednesday": 2,
        "Thursday": 3,
        "Friday": 4,
        "Saturday": 5,
        "Sunday": 6,
    }

    if mode == "DCA Backtest":
        st.header("DCA Backtest")

        dca_frequency = st.radio(
            "DCA Frequency",
            ["Daily", "Weekly"],
            horizontal=True,
            index=1,
            key="dca_backtest_frequency",
        )

        dca_base_amount_aud = st.number_input(
            f"Base {dca_frequency} DCA (AUD)",
            min_value=10.0,
            max_value=100_000.0,
            value=DEFAULT_FIXED_DCA_AUD,
            step=100.0,
            key="dca_backtest_base_amount",
        )

        dca_use_risk_model = st.toggle(
            "Use Risk Model",
            value=True,
            help=(
                "ON: the base DCA is increased/decreased by calibrated risk. "
                "OFF: exactly the base amount is invested every execution."
            ),
        )

        dca_backtest_start_date = st.date_input(
            "Start Date",
            value=dt.date(2015, 1, 1),
            min_value=dt.date(2012, 1, 1),
            max_value=dt.date.today(),
            format="DD/MM/YYYY",
            key="sidebar_dca_backtest_start_date",
        )

        dca_backtest_end_date = st.date_input(
            "End Date",
            value=dt.date.today(),
            min_value=dt.date(2012, 1, 1),
            max_value=dt.date.today(),
            format="DD/MM/YYYY",
            key="sidebar_dca_backtest_end_date",
        )

        if dca_backtest_start_date >= dca_backtest_end_date:
            st.error("Backtest Start Date must be before Backtest End Date.")

        selected_day_name = st.selectbox(
            "Weekly Execution Day",
            list(day_map.keys()),
            index=0,
            disabled=(dca_frequency != "Weekly"),
            key="dca_backtest_weekday",
        )
        selected_day = day_map[selected_day_name]

        # Compatibility values. DCA Backtest does not use a capital ceiling.
        total_capital_aud = 0.0
        frequency = dca_frequency

        st.caption(
            "No capital limit is used in DCA Backtest. "
            "The simulation simply sums each historical contribution."
        )

    else:
        st.header("Capital")

        total_capital_aud = st.number_input(
            "Simulation Capital (AUD)",
            min_value=1000.0,
            max_value=100_000_000.0,
            value=100_000.0,
            step=10_000.0,
        )

        frequency = st.selectbox(
            "Execution Frequency",
            ["Weekly", "Daily", "Monthly"],
            index=0,
        )

        selected_day_name = st.selectbox(
            "Weekly Execution Day",
            list(day_map.keys()),
            index=0,
            disabled=(frequency != "Weekly"),
        )
        selected_day = day_map[selected_day_name]

    st.divider()

    # ------------------------------------------------------------
    # SIMPLE CONTROLS
    # ------------------------------------------------------------

    st.header("Strategy Controls")

    st.caption(
        "The V3.6 calibrated composite risk model is the standard engine. "
        "0.00 = cheapest / lowest risk, 1.00 = most expensive / highest risk."
    )

    # Standard engine. Legacy modes remain available under Advanced Settings.
    risk_model = "Composite V3.6"

    st.subheader("DCA Size")

    base_dca_pct = st.slider(
        "Base DCA per execution (% of starting capital)",
        0.10,
        5.00,
        1.00,
        0.10,
        help=(
            "Starting DCA size before valuation and trend adjustments. "
            "This is not forced deployment."
        ),
    ) / 100.0

    max_period_pct = st.slider(
        "Maximum BUY per execution (%)",
        0.5,
        20.0,
        5.0,
        0.5,
        help="Hard safety cap for any single BUY.",
    ) / 100.0

    max_sell_pct_period = st.slider(
        "Maximum SELL per execution (% of BTC)",
        1.0,
        50.0,
        min(DEFAULT_MAX_SELL_PCT_PERIOD * 100, 20.0),
        1.0,
        help="Hard safety cap for any single SELL.",
    ) / 100.0

    st.divider()

    st.subheader("BUY / HOLD / SELL Risk Bands")

    if "buy_threshold_widget" not in st.session_state:
        st.session_state["buy_threshold_widget"] = DEFAULT_BUY_THRESHOLD
    if "sell_threshold_widget" not in st.session_state:
        st.session_state["sell_threshold_widget"] = DEFAULT_SELL_RISK_THRESHOLD

    preset_cols = st.columns(2)
    if preset_cols[0].button("Balanced  0.25 / 0.75", width="stretch"):
        st.session_state["buy_threshold_widget"] = 0.25
        st.session_state["sell_threshold_widget"] = 0.75
        st.rerun()
    if preset_cols[1].button("Wide  0.20 / 0.80", width="stretch"):
        st.session_state["buy_threshold_widget"] = 0.20
        st.session_state["sell_threshold_widget"] = 0.80
        st.rerun()

    preset_cols2 = st.columns(2)
    if preset_cols2[0].button("Narrow  0.30 / 0.70", width="stretch"):
        st.session_state["buy_threshold_widget"] = 0.30
        st.session_state["sell_threshold_widget"] = 0.70
        st.rerun()
    if preset_cols2[1].button("Aggressive  0.15 / 0.85", width="stretch"):
        st.session_state["buy_threshold_widget"] = 0.15
        st.session_state["sell_threshold_widget"] = 0.85
        st.rerun()

    buy_threshold = st.slider(
        "BUY when risk ≤",
        0.00,
        1.00,
        step=0.01,
        key="buy_threshold_widget",
    )

    sell_risk_threshold = st.slider(
        "SELL when risk ≥",
        0.00,
        1.00,
        step=0.01,
        key="sell_threshold_widget",
    )

    if buy_threshold >= sell_risk_threshold:
        st.error("BUY threshold must be lower than SELL threshold.")

    buy_w = max(0.0, min(100.0, buy_threshold * 100.0))
    hold_w = max(
        0.0,
        min(
            100.0,
            (sell_risk_threshold - buy_threshold) * 100.0,
        ),
    )
    sell_w = max(
        0.0,
        min(100.0, (1.0 - sell_risk_threshold) * 100.0),
    )

    st.markdown(
        f"""
        <div style="display:flex;width:100%;height:30px;border-radius:7px;overflow:hidden;
                    border:1px solid rgba(255,255,255,0.18);font-size:11px;font-weight:700;text-align:center;">
            <div style="width:{buy_w:.2f}%;background:rgba(46,160,67,0.75);display:flex;align-items:center;justify-content:center;">BUY</div>
            <div style="width:{hold_w:.2f}%;background:rgba(31,111,235,0.70);display:flex;align-items:center;justify-content:center;">HOLD</div>
            <div style="width:{sell_w:.2f}%;background:rgba(218,98,0,0.82);display:flex;align-items:center;justify-content:center;">SELL</div>
        </div>
        <div style="display:flex;justify-content:space-between;font-size:11px;opacity:0.75;margin-top:3px;">
            <span>0.00</span><span>{buy_threshold:.2f}</span><span>{sell_risk_threshold:.2f}</span><span>1.00</span>
        </div>
        """,
        unsafe_allow_html=True,
    )

    # ------------------------------------------------------------
    # ADVANCED SETTINGS (collapsed by default)
    # ------------------------------------------------------------

    with st.expander("Advanced Settings", expanded=False):

        st.caption(
            "Most users can leave these at their defaults. "
            "BGeometrics Regime is fetched automatically as context and has no manual slider."
        )

        risk_model = st.selectbox(
            "Risk engine",
            [
                "Composite V3.6",
                "Power Law Trend",
                "SMA Ratio (200-day)",
            ],
            index=0,
            help="Composite V3.6 is recommended.",
        )

        st.markdown("**Composite model weights (fixed)**")
        st.caption(
            "Power Law 25% • MVRV-Z 25% • 365d Price Position 20% • "
            "Mayer 15% • Fear & Greed 10% • RSI 5%"
        )

        # Compatibility variables: the V3.5 engine uses fixed weights internally.
        weight_mvrv = 0.25
        weight_power_law = 0.25
        weight_mayer = 0.15
        weight_fear_greed = 0.10
        weight_rsi = 0.05
        regime_overlay = 0.0

        valuation_strength = st.slider(
            "Valuation multiplier strength",
            0.25,
            1.50,
            DEFAULT_VALUATION_STRENGTH,
            0.05,
        )

        min_valuation_mult = st.slider(
            "Minimum valuation multiplier",
            0.25,
            1.00,
            DEFAULT_MIN_VALUATION_MULT,
            0.05,
        )

        max_valuation_mult = st.slider(
            "Maximum valuation multiplier",
            1.00,
            3.00,
            min(DEFAULT_MAX_VALUATION_MULT, 2.0),
            0.10,
        )

        min_cash_reserve_pct = st.slider(
            "Minimum cash reserve (%)",
            0.0,
            50.0,
            DEFAULT_MIN_CASH_RESERVE_PCT * 100,
            1.0,
        ) / 100.0

        min_trade_aud = st.number_input(
            "Minimum trade (AUD)",
            0.0,
            100000.0,
            DEFAULT_MIN_TRADE_AUD,
            100.0,
        )

        fee_pct = st.number_input(
            "Trading fee (%)",
            min_value=0.0,
            max_value=5.0,
            value=DEFAULT_FEE_PCT * 100,
            step=0.01,
        ) / 100.0

        min_days_between_sales = st.number_input(
            "Minimum days between sales",
            min_value=0,
            max_value=365,
            value=DEFAULT_MIN_DAYS_BETWEEN_SALES,
            step=1,
        )

        min_risk_components = st.slider(
            "Minimum composite inputs",
            1,
            6,
            DEFAULT_MIN_RISK_COMPONENTS,
            1,
        )

        require_weak_trend_for_sell = st.checkbox(
            "Require trend to stop being bullish before SELL",
            value=False,
        )

        st.markdown("**Optimized Trend Replica**")

        trend_er_period = st.slider(
            "Trend efficiency lookback",
            10,
            60,
            DEFAULT_TREND_ER_PERIOD,
            1,
        )
        trend_fast = st.slider(
            "Trend fast response",
            2,
            10,
            DEFAULT_TREND_FAST,
            1,
        )
        trend_slow = st.slider(
            "Trend slow response",
            15,
            80,
            DEFAULT_TREND_SLOW,
            1,
        )
        trend_range_period = st.slider(
            "Trend range lookback",
            7,
            40,
            DEFAULT_TREND_RANGE_PERIOD,
            1,
        )
        trend_band_mult = st.slider(
            "Trend band multiplier",
            0.5,
            4.0,
            DEFAULT_TREND_BAND_MULT,
            0.1,
        )
        trend_buy_bull = st.slider(
            "BUY factor: bullish",
            0.0,
            2.0,
            DEFAULT_TREND_BUY_BULL,
            0.05,
        )
        trend_buy_neutral = st.slider(
            "BUY factor: neutral",
            0.0,
            2.0,
            DEFAULT_TREND_BUY_NEUTRAL,
            0.05,
        )
        trend_buy_bear = st.slider(
            "BUY factor: bearish",
            0.0,
            2.0,
            DEFAULT_TREND_BUY_BEAR,
            0.05,
        )
        trend_sell_bull = st.slider(
            "SELL factor: bullish",
            0.0,
            2.0,
            DEFAULT_TREND_SELL_BULL,
            0.05,
        )
        trend_sell_neutral = st.slider(
            "SELL factor: neutral",
            0.0,
            2.0,
            DEFAULT_TREND_SELL_NEUTRAL,
            0.05,
        )
        trend_sell_bear = st.slider(
            "SELL factor: bearish",
            0.0,
            2.0,
            DEFAULT_TREND_SELL_BEAR,
            0.05,
        )


# ================================================================
# Dates / Parameters
# ================================================================

today = dt.datetime.now(timezone.utc).date()
genesis = dt.date(2009, 1, 3)

if mode == "Historical Backtest":
    start_date = st.sidebar.date_input(
        "Backtest Start Date",
        value=dt.date(2024, 1, 1),
        min_value=genesis,
        max_value=today,
        format="DD/MM/YYYY",
        key="historical_backtest_start_date",
    )

    end_date = st.sidebar.date_input(
        "Backtest End Date",
        value=today,
        min_value=start_date,
        max_value=today,
        format="DD/MM/YYYY",
        key="historical_backtest_end_date",
    )

elif mode == "DCA Backtest":
    # Use only the DCA Backtest dates defined in the left sidebar.
    start_date = dca_backtest_start_date
    end_date = dca_backtest_end_date

else:
    start_date = st.sidebar.date_input(
        "Deployment Start Date",
        value=today,
        min_value=today,
        format="DD/MM/YYYY",
        key="forward_deployment_start_date",
    )

    end_date = st.sidebar.date_input(
        "Deployment End Date",
        value=today + timedelta(days=90),
        min_value=start_date + timedelta(days=1),
        format="DD/MM/YYYY",
        key="forward_deployment_end_date",
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
    "base_dca_pct": base_dca_pct,
    "pressure_strength": 0.0,
    "max_period_pct": max_period_pct,
    "min_cash_reserve_pct": min_cash_reserve_pct,
    "sell_threshold": 0.0,
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
    "pressure_cap": 1.0,
    "max_btc_weight": 1.0,
    "min_days_between_sales": min_days_between_sales,
    "buy_threshold": buy_threshold,
    "sell_risk_threshold": sell_risk_threshold,
    "min_trade_aud": min_trade_aud,
    "min_risk_components": min_risk_components,
    "price_position_window": DEFAULT_PRICE_POSITION_WINDOW,
    "risk_calibration_min_periods": DEFAULT_RISK_CALIBRATION_MIN_PERIODS,
    "risk_calibration_window": DEFAULT_RISK_CALIBRATION_WINDOW,
    "risk_calibration_blend": DEFAULT_RISK_CALIBRATION_BLEND,
    "absolute_risk_weight": DEFAULT_ABSOLUTE_RISK_WEIGHT,
    "relative_risk_weight": DEFAULT_RELATIVE_RISK_WEIGHT,
    "require_weak_trend_for_sell": require_weak_trend_for_sell,
    "trend_er_period": trend_er_period,
    "trend_fast": trend_fast,
    "trend_slow": trend_slow,
    "trend_range_period": trend_range_period,
    "trend_band_mult": trend_band_mult,
    "trend_buy_bull": trend_buy_bull,
    "trend_buy_neutral": trend_buy_neutral,
    "trend_buy_bear": trend_buy_bear,
    "trend_sell_bull": trend_sell_bull,
    "trend_sell_neutral": trend_sell_neutral,
    "trend_sell_bear": trend_sell_bear,
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


# Hard UI guard: strict BUY/HOLD/SELL requires a non-overlapping HOLD zone.
if buy_threshold >= sell_risk_threshold:
    st.error(
        "Invalid risk bands: BUY threshold must be lower than SELL threshold. "
        "Please adjust the sidebar controls."
    )
    st.stop()


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

    signal_cols = st.columns(5)
    signal_cols[0].metric("Current Valuation Risk", "n/a" if pd.isna(summary['final_risk']) else f"{summary['final_risk']:.3f}")
    signal_cols[1].metric("Decision", summary.get("final_decision","HOLD"))
    signal_cols[2].metric("Optimized Trend", summary.get("final_trend","NEUTRAL"))
    signal_cols[3].metric("Sharpe", "n/a" if pd.isna(summary.get('sharpe')) else f"{summary['sharpe']:.2f}")
    signal_cols[4].metric("Sortino", "n/a" if pd.isna(summary.get('sortino')) else f"{summary['sortino']:.2f}")

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

    if "raw_risk_score" in trade_df.columns:
        fig_risk.add_trace(
            go.Scatter(
                x=trade_df["date"],
                y=trade_df["raw_risk_score"],
                name="Raw Composite Risk",
                line=dict(width=1, dash="dot"),
            )
        )

    fig_risk.add_trace(
        go.Scatter(
            x=trade_df["date"],
            y=trade_df["risk_score"],
            name="Calibrated Risk",
            line=dict(width=2),
        )
    )

    fig_risk.add_trace(
        go.Scatter(
            x=trade_df["date"],
            y=trade_df["dca_multiplier"],
            name="BUY Multiplier",
            yaxis="y2",
            line=dict(width=2, dash="dash"),
        )
    )

    fig_risk.add_hline(y=buy_threshold, line_dash="dot", annotation_text="BUY threshold")
    fig_risk.add_hline(y=sell_risk_threshold, line_dash="dot", annotation_text="SELL threshold")

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
            title="BUY Multiplier",
            overlaying="y",
            side="right",
        ),
    )

    st.plotly_chart(
        fig_risk,
        use_container_width=True,
    )

    # ------------------------------------------------------------
    # Optimized Trend Replica
    # ------------------------------------------------------------
    st.subheader("Optimized Trend Replica")
    fig_trend = go.Figure()
    fig_trend.add_trace(go.Scatter(x=trade_df["date"], y=trade_df["price_usd"], name="BTC Price (USD)", line=dict(width=2)))
    bulls=trade_df[trade_df["optimized_trend_state"]>0]; bears=trade_df[trade_df["optimized_trend_state"]<0]
    if not bulls.empty: fig_trend.add_trace(go.Scatter(x=bulls["date"],y=bulls["price_usd"],mode="markers",name="Bullish / Blue",marker=dict(size=5)))
    if not bears.empty: fig_trend.add_trace(go.Scatter(x=bears["date"],y=bears["price_usd"],mode="markers",name="Bearish / Orange",marker=dict(size=5)))
    fig_trend.update_layout(height=500,template="plotly_dark",xaxis=dict(title="Date",rangeslider=dict(visible=True)),yaxis=dict(title="BTC Price (USD)",tickprefix="$"),hovermode="x unified")
    st.plotly_chart(fig_trend,use_container_width=True)

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

    st.subheader("Reference Deployment vs Actual (No Catch-up)")

    fig_pressure = go.Figure()

    fig_pressure.add_trace(
        go.Scatter(
            x=trade_df["date"],
            y=trade_df["target_cumulative_invested"],
            name="Equal-Time Reference",
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
            "decision_zone",
            "optimized_trend",
            "price_usd",
            "risk_score",
            "raw_risk_score",
            "absolute_risk_anchor",
            "risk_floor",
            "dca_multiplier",
            "valuation_multiplier",
            "target_btc_weight",
            "actual_btc_weight",
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
        "Decision Zone",
        "Optimized Trend",
        "BTC USD",
        "Risk",
        "Raw Risk",
        "Absolute Anchor",
        "Risk Floor",
        "DCA Mult.",
        "Valuation Mult.",
        "Reference BTC %",
        "Actual BTC %",
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
        file_name="btc_dynamic_dca_v3_5_2_full_backtest.csv",
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
        st.write("Searches V3.6 BUY threshold, SELL threshold, maximum buy size and valuation strength on the first 70% of the period, then validates leaders on the untouched final 30%.")
        if st.button("Run Walk-forward Optimiser", type="secondary"):
            with st.spinner("Running train/validation parameter search..."):
                train_opt, validation_opt = walk_forward_optimise(df_full, params)
            st.markdown("**Training leaders**")
            st.dataframe(train_opt.head(10),hide_index=True,use_container_width=True)
            st.markdown("**Out-of-sample validation**")
            st.dataframe(validation_opt,hide_index=True,use_container_width=True)


# ================================================================
# DCA Backtest
# ================================================================

elif mode == "DCA Backtest":

    if dca_backtest_start_date >= dca_backtest_end_date:
        st.error("Backtest Start Date must be before Backtest End Date.")
        st.stop()

    params["start_date"] = dt.datetime.combine(
        dca_backtest_start_date,
        dt.time.min,
        tzinfo=timezone.utc,
    )
    params["end_date"] = dt.datetime.combine(
        dca_backtest_end_date,
        dt.time.max,
        tzinfo=timezone.utc,
    )
    params["day_of_week"] = selected_day

    with st.spinner("Loading historical BTC and AUD/USD data..."):
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
    df_full = merge_bgeometrics(
        df_full,
        bg_data,
    )

    st.header("DCA Backtest Results")

    model_text = (
        "Risk-adjusted DCA"
        if dca_use_risk_model
        else "Plain fixed DCA"
    )

    st.caption(
        f"Selected strategy: {model_text} • "
        f"{dca_frequency} base amount ${dca_base_amount_aud:,.0f} AUD • "
        f"{dca_backtest_start_date.strftime('%d/%m/%Y')} to "
        f"{dca_backtest_end_date.strftime('%d/%m/%Y')} • "
        "No starting-capital limit."
    )

    dca_df, dca_summary = simulate_dca_backtest(
        df_full,
        params,
        dca_base_amount_aud,
        dca_frequency,
        dca_use_risk_model,
    )

    # Always run the opposite method for direct comparison.
    comparison_df, comparison_summary = simulate_dca_backtest(
        df_full,
        params,
        dca_base_amount_aud,
        dca_frequency,
        not dca_use_risk_model,
    )

    if not dca_df.empty and dca_summary:
        st.subheader(f"Selected: {model_text}")

        c1, c2, c3, c4, c5 = st.columns(5)

        c1.metric(
            "Total Invested",
            f"${dca_summary['total_invested_aud']:,.0f}",
        )
        c2.metric(
            "BTC Held",
            f"{dca_summary['btc_held']:.6f}",
        )
        c3.metric(
            "BTC Value",
            f"${dca_summary['btc_value_aud']:,.0f}",
        )
        c4.metric(
            "Average Cost",
            f"${dca_summary['avg_cost_aud']:,.0f}",
        )
        c5.metric(
            "ROI",
            f"{dca_summary['roi_pct']:+.2f}%",
        )

        st.subheader("Strategy Comparison")
        st.caption(
            "The main results above always show the option you selected. "
            "The comparison below deliberately runs the alternative method on the same dates "
            "and with the same base DCA amount."
        )

        left, right = st.columns(2)

        if dca_use_risk_model:
            risk_summary = dca_summary
            plain_summary = comparison_summary
        else:
            plain_summary = dca_summary
            risk_summary = comparison_summary

            if (
                abs(dca_summary["total_invested_aud"] - plain_summary["total_invested_aud"]) > 0.01
                or abs(dca_summary["btc_held"] - plain_summary["btc_held"]) > 1e-10
                or abs(dca_summary["roi_pct"] - plain_summary["roi_pct"]) > 1e-9
            ):
                st.error(
                    "Internal consistency check failed: with Risk Model OFF, "
                    "selected DCA results must match Plain Fixed DCA."
                )

        if not dca_use_risk_model:
            st.success(
                "Risk Model is OFF: the selected results above are the Plain Fixed DCA results. "
                "The Risk-Adjusted column below is shown only as a comparison."
            )

        with left:
            st.markdown("**Risk-Adjusted DCA**")
            st.metric(
                "Invested",
                f"${risk_summary['total_invested_aud']:,.0f}",
            )
            st.metric(
                "BTC",
                f"{risk_summary['btc_held']:.6f}",
            )
            st.metric(
                "ROI",
                f"{risk_summary['roi_pct']:+.2f}%",
            )

        with right:
            st.markdown("**Plain Fixed DCA**")
            st.metric(
                "Invested",
                f"${plain_summary['total_invested_aud']:,.0f}",
            )
            st.metric(
                "BTC",
                f"{plain_summary['btc_held']:.6f}",
            )
            st.metric(
                "ROI",
                f"{plain_summary['roi_pct']:+.2f}%",
            )

        fig_dca = go.Figure()

        fig_dca.add_trace(
            go.Bar(
                x=dca_df["date"],
                y=dca_df["actual_buy_aud"],
                name=model_text,
            )
        )

        fig_dca.add_trace(
            go.Scatter(
                x=dca_df["date"],
                y=dca_df["base_dca_aud"],
                name="Base DCA",
                line=dict(dash="dot"),
            )
        )

        fig_dca.update_layout(
            height=420,
            template="plotly_dark",
            xaxis_title="Date",
            yaxis_title="AUD per execution",
            hovermode="x unified",
        )

        st.plotly_chart(
            fig_dca,
            width="stretch",
        )

        dca_display = dca_df[
            [
                "date",
                "dca_frequency",
                "price_usd",
                "risk_score",
                "risk_multiplier",
                "base_dca_aud",
                "actual_buy_aud",
                "cumulative_invested_aud",
                "btc_bought",
                "btc_held",
                "roi_pct",
                "signal",
            ]
        ].copy()

        dca_display["date"] = pd.to_datetime(
            dca_display["date"]
        ).dt.strftime("%d/%m/%Y")

        dca_display["price_usd"] = dca_display[
            "price_usd"
        ].map(lambda x: f"${x:,.0f}")

        dca_display["risk_score"] = dca_display[
            "risk_score"
        ].map(
            lambda x: "n/a"
            if pd.isna(x)
            else f"{x:.3f}"
        )

        dca_display["risk_multiplier"] = dca_display[
            "risk_multiplier"
        ].map(lambda x: f"{x:.2f}x")

        for col in [
            "base_dca_aud",
            "actual_buy_aud",
            "cumulative_invested_aud",
        ]:
            dca_display[col] = dca_display[col].map(
                lambda x: f"${x:,.0f}"
            )

        for col in [
            "btc_bought",
            "btc_held",
        ]:
            dca_display[col] = dca_display[col].map(
                lambda x: f"{x:.6f}"
            )

        dca_display["roi_pct"] = dca_display[
            "roi_pct"
        ].map(lambda x: f"{x:+.2f}%")

        dca_display.columns = [
            "Date",
            "Frequency",
            "BTC USD",
            "Risk",
            "Risk Mult.",
            "Base DCA AUD",
            "Actual Buy AUD",
            "Total Invested",
            "BTC Bought",
            "BTC Held",
            "ROI",
            "Signal",
        ]

        st.dataframe(
            dca_display,
            width="stretch",
            hide_index=True,
        )

    else:
        st.info("No DCA Backtest rows are available for the selected period.")


# ================================================================
# Forward Plan
# ================================================================

else:

    risk_multiplier = interpolate(
        DEFAULT_BUY_POINTS,
        forward_risk_score,
    )

    st.subheader("Forward Deployment Plan")

    today_signal = dca_day_signal(
        forward_risk_score,
        buy_threshold,
        sell_risk_threshold,
    )

    c1, c2, c3, c4 = st.columns(4)

    c1.metric(
        "Current Risk Score",
        f"{forward_risk_score:.2f}",
    )

    c2.metric(
        "DCA Today?",
        today_signal["label"],
        help="Uses the latest calculated risk available when the app is opened or refreshed.",
    )

    c3.metric(
        "DCA Quality",
        today_signal["quality"],
    )

    c4.metric(
        "Reference BTC Price",
        f"${forward_btc_price_usd:,.0f}",
    )

    signal_date_text = (
        snapshot_signal_date.strftime("%d/%m/%Y")
        if snapshot_signal_date is not None
        else "latest available data"
    )

    if today_signal["eligible"]:
        st.success(
            f"DCA signal for {signal_date_text}: {today_signal['quality']} "
            f"(risk {forward_risk_score:.3f}, buy multiplier {today_signal['multiplier']:.2f}x)."
        )
    elif today_signal["quality"] == "SELL ZONE":
        st.warning(
            f"DCA signal for {signal_date_text}: NO — valuation risk is in the SELL zone "
            f"({forward_risk_score:.3f})."
        )
    else:
        st.info(
            f"DCA signal for {signal_date_text}: NO — current valuation risk is in the HOLD zone "
            f"({forward_risk_score:.3f})."
        )

    plan = build_forward_plan(
        total_capital_aud,
        start_date,
        end_date,
        frequency,
        forward_risk_score,
        forward_btc_price_usd,
        forward_usd_per_aud,
        buy_threshold,
        sell_risk_threshold,
        base_dca_pct,
        max_period_pct,
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
            y=plan["cumulative_planned_aud"],
            name="Equal-Time Reference",
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

    display_plan["buy_multiplier"] = display_plan[
        "buy_multiplier"
    ].map(lambda x: f"{x:.2f}x")

    # Text fields: do not attempt numeric percentage formatting.
    display_plan["decision"] = display_plan["decision"].astype(str)
    display_plan["dca_today"] = display_plan["dca_today"].astype(str)
    display_plan["dca_quality"] = display_plan["dca_quality"].astype(str)

    for col in [
        "base_dca_aud",
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
            "dca_today",
            "dca_quality",
            "buy_multiplier",
            "decision",
            "base_dca_aud",
            "planned_buy_aud",
            "cumulative_planned_aud",
            "capital_remaining_aud",
        ]
    ]

    expected_forward_columns = 10
    if display_plan.shape[1] != expected_forward_columns:
        st.error(
            f"Forward table schema mismatch: expected {expected_forward_columns} columns, "
            f"received {display_plan.shape[1]}."
        )
        st.stop()

    display_plan.columns = [
        "Date",
        "Risk",
        "DCA Today?",
        "DCA Quality",
        "BUY Mult.",
        "Decision",
        "Base DCA",
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
### 1. Fixed base DCA

The model calculates how much of the starting capital would normally
have been deployed by each point in the selected period.

### 2. Risk-weighted DCA

The risk score is converted into a smooth multiplier:

- Low risk / cheap BTC -> larger purchase
- Neutral risk -> approximately normal DCA
- High risk / expensive BTC -> smaller purchase
- Extreme risk -> potentially zero new purchases

### 3. No forced deployment

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
