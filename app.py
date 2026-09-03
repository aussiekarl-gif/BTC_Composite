#!/usr/bin/env python3
"""
BTC Dynamic DCA & Tactical Rebalancing Simulator V5.0 FULL
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

DEFAULT_ALWAYS_DCA_POINTS = [
    (0.00, 3.00),
    (0.10, 2.50),
    (0.20, 2.00),
    (0.30, 1.50),
    (0.40, 1.20),
    (0.50, 1.00),
    (0.60, 0.80),
    (0.70, 0.60),
    (0.80, 0.40),
    (0.90, 0.25),
    (1.00, 0.10),
]

OPPORTUNITY_MULTIPLIER_POINTS = [
    (0.0, 0.25),
    (20.0, 0.40),
    (35.0, 0.65),
    (50.0, 1.00),
    (65.0, 1.40),
    (75.0, 1.80),
    (85.0, 2.30),
    (95.0, 2.80),
    (100.0, 3.00),
]

DEFAULT_OPPORTUNITY_HORIZON_DAYS = 365
DEFAULT_OPPORTUNITY_NEIGHBORS = 40
DEFAULT_OPPORTUNITY_MIN_HISTORY = 120
DEFAULT_OPPORTUNITY_LEARNED_WEIGHT = 0.70
DEFAULT_OPPORTUNITY_VALUATION_WEIGHT = 0.30
DEFAULT_INTELLIGENT_DCA_BUDGET_AUD = 500000.0

SMART_DCA_POINTS = [
    (0.00, 5.00),
    (0.10, 4.00),
    (0.20, 3.00),
    (0.30, 2.20),
    (0.40, 1.50),
    (0.50, 1.00),
    (0.60, 0.65),
    (0.70, 0.40),
    (0.80, 0.25),
    (0.90, 0.12),
    (1.00, 0.10),
]

def build_smart_dca_curve(low_risk_weight=5.0, high_risk_weight=0.10):
    """Build a simple convex Smart DCA curve from two user-facing endpoints.

    Risk 0.50 is anchored at 1.00x. The intermediate shape is fixed so the
    user only controls how aggressive low-risk buying is and how small
    high-risk buying becomes.
    """
    low = max(1.0, float(low_risk_weight))
    high = min(1.0, max(0.01, float(high_risk_weight)))

    # Shape fractions chosen to reproduce the V5.1 default conviction curve.
    low_shape = {0.00: 1.00, 0.10: 0.75, 0.20: 0.50, 0.30: 0.30, 0.40: 0.125, 0.50: 0.00}
    high_shape = {0.50: 1.00, 0.60: 0.6111111111, 0.70: 0.3333333333,
                  0.80: 0.1666666667, 0.90: 0.0222222222, 1.00: 0.00}

    points = []
    for risk in (0.00, 0.10, 0.20, 0.30, 0.40, 0.50):
        weight = 1.0 + (low - 1.0) * low_shape[risk]
        points.append((risk, weight))
    for risk in (0.60, 0.70, 0.80, 0.90, 1.00):
        weight = high + (1.0 - high) * high_shape[risk]
        points.append((risk, weight))
    return points

DCA_CURVE_PRESETS = {
    "Conservative": [
        (0.00, 2.00),
        (0.10, 1.80),
        (0.20, 1.60),
        (0.30, 1.40),
        (0.40, 1.20),
        (0.50, 1.00),
        (0.60, 0.85),
        (0.70, 0.70),
        (0.80, 0.55),
        (0.90, 0.40),
        (1.00, 0.25),
    ],
    "Current": DEFAULT_ALWAYS_DCA_POINTS,
    "Aggressive": [
        (0.00, 4.00),
        (0.10, 3.25),
        (0.20, 2.50),
        (0.30, 1.90),
        (0.40, 1.45),
        (0.50, 1.00),
        (0.60, 0.70),
        (0.70, 0.45),
        (0.80, 0.25),
        (0.90, 0.12),
        (1.00, 0.05),
    ],
}
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



BTC_HALVING_DATES = [
    pd.Timestamp("2016-07-09"),
    pd.Timestamp("2020-05-11"),
    pd.Timestamp("2024-04-20"),
]
CYCLE_WEIGHTS = {0: 0.50, 1: 0.30, 2: 0.20}


def _cycle_relative_risk_frame(risk_series):
    """Return weekly risk observations tagged by BTC halving cycle and cycle week."""
    s = pd.to_numeric(pd.Series(risk_series), errors="coerce").dropna()
    s = s[(s >= 0.0) & (s <= 1.0)]
    if not isinstance(s.index, pd.DatetimeIndex):
        return pd.DataFrame(columns=["risk", "cycle_id", "cycle_week"])

    idx = pd.to_datetime(s.index)
    if idx.tz is not None:
        idx = idx.tz_localize(None)

    rows = []
    for ts, risk in zip(idx, s.values):
        eligible = [d for d in BTC_HALVING_DATES if d <= ts]
        if not eligible:
            continue
        halving = max(eligible)
        cycle_id = BTC_HALVING_DATES.index(halving)
        rows.append({
            "date": ts,
            "risk": float(risk),
            "cycle_id": int(cycle_id),
            "cycle_week": max(0, int((ts - halving).days // 7)),
        })
    if not rows:
        return pd.DataFrame(columns=["risk", "cycle_id", "cycle_week"])
    return pd.DataFrame(rows).set_index("date").sort_index()


def _cycle_context(risk_series):
    """Current cycle plus previous two cycles, using only observations supplied to the function."""
    frame = _cycle_relative_risk_frame(risk_series)
    if frame.empty:
        return frame, None, None

    current_cycle = int(frame["cycle_id"].iloc[-1])
    current_week = int(frame["cycle_week"].iloc[-1])
    allowed = [c for c in (current_cycle, current_cycle - 1, current_cycle - 2) if c >= 0]
    return frame[frame["cycle_id"].isin(allowed)].copy(), current_cycle, current_week


def opportunity_rarity_from_history(risk_series, current_risk):
    """Cycle-relative rarity based only on BTC Risk Score.

    Primary evidence is the current halving cycle. Previous two cycles are included
    at comparable cycle ages and weighted 50% / 30% / 20%. No price-level signal is
    added here; cycle information only contextualises the existing risk score.
    """
    frame, current_cycle, current_week = _cycle_context(risk_series)
    if frame.empty or not np.isfinite(current_risk):
        return {
            "percentile": np.nan, "cheap_frequency": np.nan,
            "rarity_label": "INSUFFICIENT HISTORY", "rarity_multiplier": 1.0,
            "expected_comparable_weeks_4y": np.nan, "samples": 0,
            "evidence_label": "LOW", "cycle_breakdown": {},
        }

    # Compare similar cycle phase: +/- 26 weeks, widening only if evidence is sparse.
    selected = pd.DataFrame()
    phase_window = 26
    for phase_window in (26, 39, 52, 78):
        selected = frame[(frame["cycle_week"] - current_week).abs() <= phase_window].copy()
        if len(selected) >= 20:
            break

    cycle_stats = {}
    weighted_num = weighted_den = 0.0
    total_samples = 0
    for offset, weight in CYCLE_WEIGHTS.items():
        cid = current_cycle - offset
        part = selected[selected["cycle_id"] == cid]
        if part.empty:
            continue
        freq = float((part["risk"] <= float(current_risk)).mean())
        cycle_stats[f"cycle_{offset}"] = {"frequency": freq, "samples": int(len(part))}
        weighted_num += weight * freq
        weighted_den += weight
        total_samples += len(part)

    if weighted_den <= 0 or total_samples < 8:
        cheap_frequency = float((frame["risk"] <= float(current_risk)).mean()) if len(frame) else np.nan
        evidence = "LOW"
    else:
        cheap_frequency = weighted_num / weighted_den
        evidence = "HIGH" if total_samples >= 40 else ("MODERATE" if total_samples >= 20 else "LOW")

    percentile = cheap_frequency * 100.0 if np.isfinite(cheap_frequency) else np.nan

    if not np.isfinite(cheap_frequency):
        label, mult = "INSUFFICIENT HISTORY", 1.0
    elif cheap_frequency <= 0.05:
        label, mult = "EXTREME", 1.35
    elif cheap_frequency <= 0.10:
        label, mult = "VERY HIGH", 1.25
    elif cheap_frequency <= 0.20:
        label, mult = "HIGH", 1.15
    elif cheap_frequency <= 0.35:
        label, mult = "ABOVE AVERAGE", 1.07
    elif cheap_frequency <= 0.60:
        label, mult = "NORMAL", 1.00
    else:
        label, mult = "COMMON", 0.95

    return {
        "percentile": percentile,
        "cheap_frequency": cheap_frequency,
        "rarity_label": label,
        "rarity_multiplier": mult,
        "expected_comparable_weeks_4y": cheap_frequency * 208.0 if np.isfinite(cheap_frequency) else np.nan,
        "samples": int(total_samples),
        "evidence_label": evidence,
        "phase_window_weeks": int(phase_window),
        "cycle_breakdown": cycle_stats,
    }


def lower_risk_opportunity_stats(risk_series, current_risk, horizon_weeks):
    """Cycle-relative analogue estimate for a lower future Risk Score.

    Uses only the risk history supplied as-of the decision date. Analogues come from
    the current cycle and previous two cycles, at similar cycle age and similar risk.
    Earlier analogue outcomes must already be observable by the as-of date, preventing
    look-ahead leakage in walk-forward use.
    """
    frame, current_cycle, current_week = _cycle_context(risk_series)
    horizon = int(max(1, min(float(horizon_weeks), 156.0)))
    empty = {
        "samples": 0, "tolerance": np.nan, "chance_any_lower": np.nan,
        "chance_materially_lower": np.nan, "chance_le_005": np.nan,
        "chance_le_002": np.nan, "chance_le_001": np.nan,
        "median_future_min": np.nan, "material_threshold": np.nan,
        "evidence_label": "LOW", "phase_window_weeks": np.nan,
    }
    if frame.empty or not np.isfinite(current_risk):
        return empty

    material_threshold = max(0.0, min(float(current_risk) - 0.01, float(current_risk) * 0.75))
    asof = frame.index.max()
    analogues = []

    chosen_tol = np.nan
    chosen_phase = np.nan
    for phase_window in (26, 39, 52, 78):
        for tol in (0.015, 0.025, 0.04, 0.06, 0.10):
            candidates = frame[
                ((frame["risk"] - float(current_risk)).abs() <= tol)
                & ((frame["cycle_week"] - current_week).abs() <= phase_window)
            ]
            tmp = []
            for ts, row in candidates.iterrows():
                # Exclude today's observation and require the full outcome window to be known.
                if ts >= asof:
                    continue
                outcome_end = ts + pd.Timedelta(weeks=horizon)
                if outcome_end > asof:
                    continue
                same_cycle = frame[
                    (frame["cycle_id"] == row["cycle_id"])
                    & (frame.index > ts)
                    & (frame.index <= outcome_end)
                ]["risk"]
                if same_cycle.empty:
                    continue
                future_min = float(same_cycle.min())
                offset = current_cycle - int(row["cycle_id"])
                weight = CYCLE_WEIGHTS.get(offset, 0.0)
                if weight <= 0:
                    continue
                tmp.append((future_min, weight))
            if len(tmp) >= 8:
                analogues = tmp
                chosen_tol, chosen_phase = tol, phase_window
                break
            if len(tmp) > len(analogues):
                analogues = tmp
                chosen_tol, chosen_phase = tol, phase_window
        if len(analogues) >= 8:
            break

    if not analogues:
        empty["material_threshold"] = material_threshold
        return empty

    mins = np.array([x[0] for x in analogues], dtype=float)
    weights = np.array([x[1] for x in analogues], dtype=float)
    weights = weights / weights.sum()

    def wp(condition):
        return float(weights[np.asarray(condition, dtype=bool)].sum())

    samples = len(mins)
    evidence = "HIGH" if samples >= 30 else ("MODERATE" if samples >= 12 else "LOW")
    return {
        "samples": samples,
        "tolerance": float(chosen_tol),
        "chance_any_lower": wp(mins < float(current_risk)),
        "chance_materially_lower": wp(mins <= material_threshold),
        "chance_le_005": wp(mins <= 0.05),
        "chance_le_002": wp(mins <= 0.02),
        "chance_le_001": wp(mins <= 0.01),
        "median_future_min": float(np.median(mins)),
        "material_threshold": material_threshold,
        "evidence_label": evidence,
        "phase_window_weeks": int(chosen_phase),
    }


def risk_occurrence_table(risk_series):
    """Return simple weekly risk buckets for the DCA Today visibility chart."""
    s = pd.to_numeric(pd.Series(risk_series), errors="coerce").dropna()
    bins = [
        (0.00, 0.01, "0.00–0.01"),
        (0.01, 0.02, "0.01–0.02"),
        (0.02, 0.05, "0.02–0.05"),
        (0.05, 0.10, "0.05–0.10"),
        (0.10, 0.20, "0.10–0.20"),
        (0.20, 0.40, "0.20–0.40"),
        (0.40, 0.60, "0.40–0.60"),
        (0.60, 0.80, "0.60–0.80"),
        (0.80, 1.000001, "0.80–1.00"),
    ]
    rows = []
    total = max(len(s), 1)
    for lo, hi, label in bins:
        count = int(((s >= lo) & (s < hi)).sum())
        rows.append({"Risk range": label, "Weeks": count, "Percent": 100.0 * count / total})
    return pd.DataFrame(rows)

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

def _weighted_percentile_rank(values, target):
    values = pd.to_numeric(pd.Series(values), errors="coerce").dropna()
    if values.empty or not np.isfinite(target):
        return np.nan
    return float((values <= target).mean())


def build_opportunity_scores(
    indicator_df,
    execution_index,
    horizon_days=DEFAULT_OPPORTUNITY_HORIZON_DAYS,
    neighbors=DEFAULT_OPPORTUNITY_NEIGHBORS,
    min_history=DEFAULT_OPPORTUNITY_MIN_HISTORY,
    learned_weight=DEFAULT_OPPORTUNITY_LEARNED_WEIGHT,
    valuation_weight=DEFAULT_OPPORTUNITY_VALUATION_WEIGHT,
):
    """
    Walk-forward historical analogue engine.

    For every execution date, it only trains on observations whose full
    forward-return outcome would already have been known on that date.
    No future observations are used to score a historical decision.

    The engine compares today's state with past states using:
      - calibrated risk
      - raw valuation risk
      - 365d drawdown
      - RSI
      - Mayer multiple
      - Power Law residual
      - 365d price position
      - Optimized Trend state/strength

    It then measures how the most similar historical states performed over
    the selected forward horizon.

    This is intentionally transparent statistical learning, not a claim that
    future BTC returns can be known.
    """
    if indicator_df.empty:
        return pd.DataFrame()

    x = indicator_df.copy().sort_index()

    horizon_days = max(30, int(horizon_days))
    neighbors = max(5, int(neighbors))
    min_history = max(30, int(min_history))

    # Forward return label. Daily BTC data makes calendar-day shift a close
    # approximation; the label is available to the learner only after the
    # horizon has fully elapsed.
    x["opportunity_future_return"] = (
        x["price"].shift(-horizon_days) / x["price"] - 1.0
    )

    feature_cols = [
        "risk_score",
        "raw_risk_score",
        "drawdown_365",
        "rsi_14",
        "mayer",
        "power_law_residual",
        "price_position_365",
        "optimized_trend_state",
        "optimized_trend_strength",
    ]

    # Feature transforms keep scales sensible and reduce domination by one
    # variable before robust standardisation.
    features = pd.DataFrame(index=x.index)
    features["risk_score"] = pd.to_numeric(x["risk_score"], errors="coerce")
    features["raw_risk_score"] = pd.to_numeric(x["raw_risk_score"], errors="coerce")
    features["drawdown_365"] = pd.to_numeric(x["drawdown_365"], errors="coerce")
    features["rsi_14"] = pd.to_numeric(x["rsi_14"], errors="coerce") / 100.0
    features["mayer"] = np.log(
        pd.to_numeric(x["mayer"], errors="coerce").clip(lower=0.05)
    )
    features["power_law_residual"] = pd.to_numeric(
        x["power_law_residual"], errors="coerce"
    )
    features["price_position_365"] = pd.to_numeric(
        x["price_position_365"], errors="coerce"
    )
    features["optimized_trend_state"] = pd.to_numeric(
        x["optimized_trend_state"], errors="coerce"
    )
    features["optimized_trend_strength"] = pd.to_numeric(
        x["optimized_trend_strength"], errors="coerce"
    ).clip(-2, 2) / 2.0

    future_return = pd.to_numeric(
        x["opportunity_future_return"], errors="coerce"
    )

    output = []

    for ts in pd.DatetimeIndex(execution_index):
        if ts not in x.index:
            continue

        current = features.loc[ts]
        risk = float(x.at[ts, "risk_score"]) if pd.notna(x.at[ts, "risk_score"]) else np.nan

        # A historical sample can only be used if its forward horizon had
        # completed by the current decision date.
        cutoff = ts - pd.Timedelta(days=horizon_days)
        eligible_mask = (
            (features.index <= cutoff)
            & future_return.notna()
        )

        hist_features = features.loc[eligible_mask].copy()
        hist_returns = future_return.loc[eligible_mask].copy()

        # Require enough common features for robust analogue matching.
        valid_current = current.notna()
        common_cols = [
            c for c in feature_cols
            if c in hist_features.columns and valid_current.get(c, False)
        ]

        if len(common_cols) < 5:
            learned_score = np.nan
            expected_return = np.nan
            positive_rate = np.nan
            sample_count = 0
            avg_distance = np.nan
        else:
            hist = hist_features[common_cols]
            complete = hist.notna().sum(axis=1) >= max(4, int(len(common_cols) * 0.70))
            hist = hist.loc[complete]
            rets = hist_returns.loc[hist.index]

            if len(hist) < min_history:
                learned_score = np.nan
                expected_return = np.nan
                positive_rate = np.nan
                sample_count = int(len(hist))
                avg_distance = np.nan
            else:
                # Fill historical gaps using historical medians only.
                med = hist.median()
                hist_filled = hist.fillna(med)
                current_filled = current[common_cols].fillna(med)

                # Robust scale using only information available at the time.
                scale = (hist_filled.quantile(0.75) - hist_filled.quantile(0.25))
                fallback_scale = hist_filled.std(ddof=0)
                scale = scale.where(scale.abs() > 1e-9, fallback_scale)
                scale = scale.replace(0, 1.0).fillna(1.0)

                z_hist = (hist_filled - med) / scale
                z_current = (current_filled - med) / scale

                distances = np.sqrt(
                    ((z_hist - z_current) ** 2).mean(axis=1)
                )

                k = min(neighbors, len(distances))
                nearest_idx = distances.nsmallest(k).index
                nearest_dist = distances.loc[nearest_idx]
                nearest_ret = rets.loc[nearest_idx]

                weights = 1.0 / (nearest_dist + 0.15)
                weight_sum = float(weights.sum())

                if weight_sum <= 0:
                    expected_return = float(nearest_ret.mean())
                    positive_rate = float((nearest_ret > 0).mean())
                else:
                    expected_return = float(
                        np.average(nearest_ret.values, weights=weights.values)
                    )
                    positive_rate = float(
                        np.average(
                            (nearest_ret.values > 0).astype(float),
                            weights=weights.values,
                        )
                    )

                return_percentile = _weighted_percentile_rank(
                    rets,
                    expected_return,
                )

                learned_score = 100.0 * (
                    0.55 * return_percentile
                    + 0.45 * positive_rate
                )
                sample_count = int(len(nearest_ret))
                avg_distance = float(nearest_dist.mean())

        valuation_score = (
            (1.0 - risk) * 100.0
            if np.isfinite(risk)
            else 50.0
        )

        if np.isfinite(learned_score):
            total_w = max(float(learned_weight) + float(valuation_weight), 1e-9)
            opportunity_score = (
                float(learned_weight) * learned_score
                + float(valuation_weight) * valuation_score
            ) / total_w
            confidence = min(
                100.0,
                35.0
                + 65.0 * min(1.0, sample_count / max(neighbors, 1))
                * (1.0 / (1.0 + max(avg_distance, 0.0))),
            )
        else:
            # During early history there may not yet be enough completed
            # forward-return examples. Fall back to valuation rather than
            # inventing a learned signal.
            opportunity_score = valuation_score
            confidence = 25.0

        opportunity_score = float(np.clip(opportunity_score, 0.0, 100.0))
        multiplier = float(
            interpolate(OPPORTUNITY_MULTIPLIER_POINTS, opportunity_score)
        )

        if opportunity_score >= 85:
            quality = "EXCEPTIONAL"
        elif opportunity_score >= 75:
            quality = "STRONG"
        elif opportunity_score >= 60:
            quality = "GOOD"
        elif opportunity_score >= 45:
            quality = "NORMAL"
        elif opportunity_score >= 30:
            quality = "WEAK"
        else:
            quality = "POOR"

        output.append(
            {
                "date": ts,
                "opportunity_score": opportunity_score,
                "opportunity_quality": quality,
                "opportunity_multiplier": multiplier,
                "opportunity_expected_return": expected_return,
                "opportunity_positive_rate": positive_rate,
                "opportunity_neighbors": sample_count,
                "opportunity_confidence": confidence,
                "opportunity_learned_score": learned_score,
                "opportunity_valuation_score": valuation_score,
            }
        )

    if not output:
        return pd.DataFrame()

    return pd.DataFrame(output).set_index("date").sort_index()


def simulate_dca_backtest(
    df_full,
    params,
    base_dca_aud,
    dca_frequency,
    strategy_mode,
    risk_curve=None,
    opportunity_horizon_days=DEFAULT_OPPORTUNITY_HORIZON_DAYS,
    opportunity_neighbors=DEFAULT_OPPORTUNITY_NEIGHBORS,
    opportunity_min_history=DEFAULT_OPPORTUNITY_MIN_HISTORY,
):
    """
    Historical accumulation-only DCA backtest with no capital ceiling.

    strategy_mode:
      - "Plain DCA": exact base amount every execution.
      - "Risk-Scaled DCA": always buys, amount varies with calibrated risk.
      - "Risk-Gated DCA": buys only inside BUY zone; otherwise $0.
      - "Opportunity-Scaled DCA": always buys; sizing is learned from
        walk-forward historical analogue outcomes plus valuation risk.
    """
    if risk_curve is None:
        risk_curve = DEFAULT_ALWAYS_DCA_POINTS

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

    opportunity_df = pd.DataFrame()
    if strategy_mode == "Opportunity-Scaled DCA":
        opportunity_df = build_opportunity_scores(
            df,
            execution.index,
            horizon_days=opportunity_horizon_days,
            neighbors=opportunity_neighbors,
            min_history=opportunity_min_history,
        )

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

        opportunity_score = np.nan
        opportunity_quality = ""
        opportunity_expected_return = np.nan
        opportunity_positive_rate = np.nan
        opportunity_confidence = np.nan

        if strategy_mode == "Plain DCA":
            multiplier = 1.0
            contribution = float(base_dca_aud)
            signal = "FIXED DCA"

        elif strategy_mode == "Risk-Scaled DCA":
            multiplier = (
                float(interpolate(risk_curve, risk))
                if np.isfinite(risk)
                else 1.0
            )
            contribution = float(base_dca_aud) * multiplier
            signal = "SCALED DCA"

        elif strategy_mode == "Opportunity-Scaled DCA":
            if timestamp in opportunity_df.index:
                opp_row = opportunity_df.loc[timestamp]
                opportunity_score = float(opp_row["opportunity_score"])
                opportunity_quality = str(opp_row["opportunity_quality"])
                opportunity_expected_return = opp_row["opportunity_expected_return"]
                opportunity_positive_rate = opp_row["opportunity_positive_rate"]
                opportunity_confidence = float(opp_row["opportunity_confidence"])
                multiplier = float(opp_row["opportunity_multiplier"])
            else:
                opportunity_score = (
                    (1.0 - risk) * 100.0 if np.isfinite(risk) else 50.0
                )
                opportunity_quality = "NORMAL"
                opportunity_expected_return = np.nan
                opportunity_positive_rate = np.nan
                opportunity_confidence = 25.0
                multiplier = float(
                    interpolate(OPPORTUNITY_MULTIPLIER_POINTS, opportunity_score)
                )

            contribution = float(base_dca_aud) * multiplier
            signal = f"OPPORTUNITY {opportunity_quality}"

        else:  # Risk-Gated DCA
            multiplier = (
                float(interpolate(DEFAULT_BUY_POINTS, risk))
                if np.isfinite(risk)
                else 0.0
            )
            contribution = (
                float(base_dca_aud) * multiplier
                if np.isfinite(risk)
                and risk <= float(params["buy_threshold"])
                else 0.0
            )
            signal = "BUY" if contribution > 0 else "HOLD"

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
                "strategy_mode": strategy_mode,
                "opportunity_score": opportunity_score,
                "opportunity_quality": opportunity_quality,
                "opportunity_expected_return": opportunity_expected_return,
                "opportunity_positive_rate": opportunity_positive_rate,
                "opportunity_confidence": opportunity_confidence,
                "dca_multiplier": multiplier,
                "base_dca_aud": float(base_dca_aud),
                "dca_frequency": dca_frequency,
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
        "strategy_mode": strategy_mode,
        "base_dca_aud": float(base_dca_aud),
        "frequency": dca_frequency,
        "total_invested_aud": float(final["cumulative_invested_aud"]),
        "btc_held": float(final["btc_held"]),
        "btc_value_aud": float(final["btc_value_aud"]),
        "pnl_aud": float(final["pnl_aud"]),
        "roi_pct": float(final["roi_pct"]),
        "avg_cost_aud": float(final["avg_cost_aud"]),
        "fees_aud": float(final["cumulative_fees_aud"]),
        "execution_count": int(len(result)),
        "buy_count": int((result["actual_buy_aud"] > 0).sum()),
        "final_opportunity_score": (
            float(result["opportunity_score"].dropna().iloc[-1])
            if "opportunity_score" in result
            and not result["opportunity_score"].dropna().empty
            else np.nan
        ),
        "final_opportunity_quality": (
            str(result.loc[result["opportunity_score"].notna(), "opportunity_quality"].iloc[-1])
            if "opportunity_score" in result
            and result["opportunity_score"].notna().any()
            else ""
        ),
    }

    return result, summary


def apply_equal_capital_allocator(
    result_df,
    total_budget_aud=DEFAULT_INTELLIGENT_DCA_BUDGET_AUD,
    fee_pct=0.0,
):
    """
    Allocate a hard fixed lifetime budget across the already-selected historical
    execution dates using the strategy's relative DCA weights.

    Unlike post-hoc comparison normalization, this produces an explicit
    contribution schedule whose total contributions equal the chosen budget.
    The timing weights are preserved, but the strategy cannot invest more than
    the fixed budget.

    This is a historical research allocator, not a future-price forecast.
    """
    if result_df.empty or total_budget_aud <= 0:
        return pd.DataFrame(), {}

    out = result_df.copy().reset_index(drop=True)

    weights = pd.to_numeric(
        out["actual_buy_aud"], errors="coerce"
    ).fillna(0.0).clip(lower=0.0)

    total_weight = float(weights.sum())
    if total_weight <= 0:
        return pd.DataFrame(), {}

    contributions = weights / total_weight * float(total_budget_aud)

    # Force exact budget equality despite floating-point accumulation.
    if len(contributions) > 0:
        contributions.iloc[-1] += float(total_budget_aud) - float(contributions.sum())

    btc = 0.0
    cumulative = 0.0
    fees = 0.0
    replay_rows = []

    for i, row in out.iterrows():
        contribution = float(contributions.iloc[i])
        fee = contribution * float(fee_pct)
        net = max(0.0, contribution - fee)
        price_aud = float(row["btc_price_aud"])
        btc_bought = net / price_aud if price_aud > 0 else 0.0

        btc += btc_bought
        cumulative += contribution
        fees += fee
        btc_value = btc * price_aud

        replay = row.to_dict()
        replay.update(
            {
                "actual_buy_aud": contribution,
                "btc_bought": btc_bought,
                "btc_held": btc,
                "cumulative_invested_aud": cumulative,
                "cumulative_fees_aud": fees,
                "btc_value_aud": btc_value,
                "pnl_aud": btc_value - cumulative,
                "roi_pct": (
                    (btc_value / cumulative - 1.0) * 100.0
                    if cumulative > 0 else 0.0
                ),
                "avg_cost_aud": cumulative / btc if btc > 0 else 0.0,
            }
        )
        replay_rows.append(replay)

    replay_df = pd.DataFrame(replay_rows)
    final = replay_df.iloc[-1]

    summary = {
        "budget_aud": float(total_budget_aud),
        "total_invested_aud": float(final["cumulative_invested_aud"]),
        "btc_held": float(final["btc_held"]),
        "btc_value_aud": float(final["btc_value_aud"]),
        "avg_cost_aud": float(final["avg_cost_aud"]),
        "roi_pct": float(final["roi_pct"]),
        "fees_aud": float(final["cumulative_fees_aud"]),
    }
    return replay_df, summary


def normalize_dca_to_target_capital(
    result_df,
    target_total_aud,
    fee_pct=0.0,
):
    """
    Replay a DCA result using exactly target_total_aud in total contributions.

    The original strategy's per-period contribution weights are preserved,
    but every contribution is scaled by one constant factor. This gives a
    like-for-like capital comparison against Plain DCA.
    """
    if result_df.empty or target_total_aud <= 0:
        return pd.DataFrame(), {}

    original_total = float(
        result_df["actual_buy_aud"].sum()
    )
    if original_total <= 0:
        return pd.DataFrame(), {}

    scale = float(target_total_aud) / original_total

    btc = 0.0
    cumulative_invested = 0.0
    rows = []

    for _, row in result_df.iterrows():
        contribution = float(row["actual_buy_aud"]) * scale
        fee = contribution * float(fee_pct)
        net = max(0.0, contribution - fee)
        price_aud = float(row["btc_price_aud"])

        btc_bought = (
            net / price_aud
            if price_aud > 0
            else 0.0
        )

        btc += btc_bought
        cumulative_invested += contribution
        btc_value = btc * price_aud

        rows.append(
            {
                "date": row["date"],
                "price_usd": row["price_usd"],
                "btc_price_aud": price_aud,
                "risk_score": row["risk_score"],
                "actual_buy_aud": contribution,
                "btc_bought": btc_bought,
                "btc_held": btc,
                "cumulative_invested_aud": cumulative_invested,
                "btc_value_aud": btc_value,
                "avg_cost_aud": (
                    cumulative_invested / btc
                    if btc > 0 else 0.0
                ),
            }
        )

    out = pd.DataFrame(rows)
    if out.empty:
        return out, {}

    final = out.iloc[-1]
    roi_pct = (
        (float(final["btc_value_aud"]) / target_total_aud - 1.0) * 100.0
        if target_total_aud > 0
        else np.nan
    )

    summary = {
        "target_total_aud": target_total_aud,
        "scale_factor": scale,
        "btc_held": float(final["btc_held"]),
        "btc_value_aud": float(final["btc_value_aud"]),
        "avg_cost_aud": float(final["avg_cost_aud"]),
        "roi_pct": roi_pct,
    }
    return out, summary


def optimise_dca_curve_walk_forward(
    df_full,
    params,
    base_dca_aud,
    dca_frequency,
):
    """
    Simple 70/30 walk-forward choice among named curves.

    Training objective:
      maximize normalized BTC accumulated using the same total capital
      as Plain DCA on the training period.

    Validation:
      report the selected curve on the untouched final 30%.
    """
    start = params["start_date"]
    end = params["end_date"]
    if end <= start:
        return {}, pd.DataFrame()

    split = start + (end - start) * 0.70

    train_params = dict(params)
    train_params["end_date"] = split

    valid_params = dict(params)
    valid_params["start_date"] = split
    valid_params["end_date"] = end

    rows = []

    # Plain DCA capital target on training set.
    plain_train, plain_train_sm = simulate_dca_backtest(
        df_full,
        train_params,
        base_dca_aud,
        dca_frequency,
        "Plain DCA",
    )
    if not plain_train_sm:
        return {}, pd.DataFrame()

    train_target = plain_train_sm["total_invested_aud"]

    for name, curve in DCA_CURVE_PRESETS.items():
        scaled_train, _ = simulate_dca_backtest(
            df_full,
            train_params,
            base_dca_aud,
            dca_frequency,
            "Risk-Scaled DCA",
            risk_curve=curve,
        )
        _, norm_train = normalize_dca_to_target_capital(
            scaled_train,
            train_target,
            fee_pct=train_params.get("fee_pct", 0.0),
        )

        if not norm_train:
            continue

        rows.append(
            {
                "Curve": name,
                "Train BTC": norm_train["btc_held"],
                "Train ROI %": norm_train["roi_pct"],
            }
        )

    train_table = pd.DataFrame(rows)
    if train_table.empty:
        return {}, train_table

    best_name = str(
        train_table.sort_values(
            "Train BTC",
            ascending=False,
        ).iloc[0]["Curve"]
    )
    best_curve = DCA_CURVE_PRESETS[best_name]

    # Validation comparison against Plain DCA.
    plain_valid, plain_valid_sm = simulate_dca_backtest(
        df_full,
        valid_params,
        base_dca_aud,
        dca_frequency,
        "Plain DCA",
    )
    scaled_valid, _ = simulate_dca_backtest(
        df_full,
        valid_params,
        base_dca_aud,
        dca_frequency,
        "Risk-Scaled DCA",
        risk_curve=best_curve,
    )

    validation = {}
    if plain_valid_sm:
        valid_target = plain_valid_sm["total_invested_aud"]
        _, norm_valid = normalize_dca_to_target_capital(
            scaled_valid,
            valid_target,
            fee_pct=valid_params.get("fee_pct", 0.0),
        )
        if norm_valid:
            validation = {
                "selected_curve": best_name,
                "plain_btc": plain_valid_sm["btc_held"],
                "scaled_btc": norm_valid["btc_held"],
                "btc_advantage_pct": (
                    norm_valid["btc_held"] / plain_valid_sm["btc_held"] - 1.0
                ) * 100.0 if plain_valid_sm["btc_held"] > 0 else np.nan,
                "plain_roi_pct": plain_valid_sm["roi_pct"],
                "scaled_roi_pct": norm_valid["roi_pct"],
            }

    return validation, train_table


def validate_smart_dca_recent_period(
    df_full,
    params,
    dca_frequency,
    total_budget_aud,
    recent_fraction=0.30,
    risk_curve=None,
):
    """
    Compare the same fixed Smart DCA curve with Plain DCA on the most recent
    portion of the selected history. No curve fitting or optimizer is used.
    """
    start = params["start_date"]
    end = params["end_date"]
    if end <= start:
        return {}

    split = start + (end - start) * (1.0 - float(recent_fraction))
    recent_params = dict(params)
    recent_params["start_date"] = split
    recent_params["end_date"] = end
    recent_budget = float(total_budget_aud) * float(recent_fraction)

    plain_raw, _ = simulate_dca_backtest(
        df_full, recent_params, DEFAULT_FIXED_DCA_AUD, dca_frequency, "Plain DCA"
    )
    smart_raw, _ = simulate_dca_backtest(
        df_full, recent_params, DEFAULT_FIXED_DCA_AUD, dca_frequency,
        "Risk-Scaled DCA", risk_curve=(risk_curve or SMART_DCA_POINTS)
    )

    _, plain_sm = apply_equal_capital_allocator(
        plain_raw, total_budget_aud=recent_budget,
        fee_pct=recent_params.get("fee_pct", 0.0)
    )
    _, smart_sm = apply_equal_capital_allocator(
        smart_raw, total_budget_aud=recent_budget,
        fee_pct=recent_params.get("fee_pct", 0.0)
    )

    if not plain_sm or not smart_sm:
        return {}

    advantage = (
        (smart_sm["btc_held"] / plain_sm["btc_held"] - 1.0) * 100.0
        if plain_sm["btc_held"] > 0 else np.nan
    )
    return {
        "split_date": split,
        "plain_btc": plain_sm["btc_held"],
        "smart_btc": smart_sm["btc_held"],
        "btc_advantage_pct": advantage,
        "budget_aud": recent_budget,
    }


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
    page_title="BTC Dynamic DCA V5.7.1 FULL",
    layout="wide",
)

st.title("Bitcoin Dynamic DCA V5.7.1 FULL — Smart DCA")
st.caption("Version 5.7.1 FULL • Backtest + DCA Today • Opportunity Probability")
st.caption("Simple three-mode app • Backtest • DCA Today • My Portfolio")

# ------------------------------------------------
# Sidebar
# ------------------------------------------------

with st.sidebar:
    st.header("Mode")

    mode = st.radio(
        "Analysis Mode",
        [
            "DCA Backtest",
            "DCA Today",
            "My Portfolio",
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
        dca_base_amount_aud = DEFAULT_FIXED_DCA_AUD

        intelligent_dca_budget_aud = st.number_input(
            "Total Budget (AUD)",
            min_value=10_000.0,
            max_value=10_000_000.0,
            value=DEFAULT_INTELLIGENT_DCA_BUDGET_AUD,
            step=10_000.0,
            format="%.0f",
            help="Plain DCA and Smart DCA both receive exactly this total budget.",
        )

        st.subheader("Smart DCA Conviction")
        low_risk_weight = st.slider(
            "Low-risk buy weight (risk 0.00)",
            min_value=2.0, max_value=10.0, value=5.0, step=0.25,
            help="How strongly Smart DCA favors the cheapest valuation periods.",
            key="backtest_low_risk_weight",
        )
        high_risk_weight = st.slider(
            "High-risk buy weight (risk 1.00)",
            min_value=0.01, max_value=0.50, value=0.10, step=0.01,
            help="Very small values preserve most capital during expensive valuation periods.",
            key="backtest_high_risk_weight",
        )
        smart_dca_curve = build_smart_dca_curve(low_risk_weight, high_risk_weight)
        conviction_ratio = low_risk_weight / high_risk_weight
        st.caption(
            f"Current low/high allocation ratio: {conviction_ratio:.0f}:1. "
            "Risk 0.50 remains anchored at 1.00x."
        )

        dca_backtest_start_date = st.date_input(
            "Start Date", value=dt.date(2015, 1, 1),
            min_value=dt.date(2012, 1, 1), max_value=dt.date.today(),
            format="DD/MM/YYYY", key="sidebar_dca_backtest_start_date",
        )
        dca_backtest_end_date = st.date_input(
            "End Date", value=dt.date.today(),
            min_value=dt.date(2012, 1, 1), max_value=dt.date.today(),
            format="DD/MM/YYYY", key="sidebar_dca_backtest_end_date",
        )
        if dca_backtest_start_date >= dca_backtest_end_date:
            st.error("Backtest Start Date must be before Backtest End Date.")

        selected_day_name = st.selectbox(
            "Weekly Execution Day", list(day_map.keys()), index=0,
            disabled=(dca_frequency != "Weekly"), key="dca_backtest_weekday",
        )
        selected_day = day_map[selected_day_name]
        total_capital_aud = 0.0
        frequency = dca_frequency

        st.caption(
            "Same budget and dates. Plain DCA invests evenly; Smart DCA tilts capital toward lower-risk periods."
        )

    elif mode == "DCA Today":
        st.header("DCA Today")

        starting_capital_aud = st.number_input(
            "Starting Capital (AUD)",
            min_value=1_000.0, max_value=100_000_000.0,
            value=500_000.0, step=10_000.0, format="%.0f",
            key="today_starting_capital",
        )
        remaining_capital_aud = st.number_input(
            "Capital Remaining (AUD)",
            min_value=0.0, max_value=float(starting_capital_aud),
            value=min(
                float(starting_capital_aud),
                float(st.session_state.get("portfolio_capital_remaining", starting_capital_aud))
            ),
            step=5_000.0, format="%.0f",
            key="today_remaining_capital",
        )
        target_deployment_date = st.date_input(
            "Target Deployment Date",
            value=dt.date.today() + dt.timedelta(days=365 * 3),
            min_value=dt.date.today() + dt.timedelta(days=7),
            format="DD/MM/YYYY",
            key="today_target_date",
        )

        st.subheader("Smart DCA Conviction")
        low_risk_weight = st.slider(
            "Low-risk buy weight (risk 0.00)",
            min_value=2.0, max_value=10.0, value=5.0, step=0.25,
            key="today_low_risk_weight",
        )
        high_risk_weight = st.slider(
            "High-risk buy weight (risk 1.00)",
            min_value=0.01, max_value=0.50, value=0.10, step=0.01,
            key="today_high_risk_weight",
        )
        smart_dca_curve = build_smart_dca_curve(low_risk_weight, high_risk_weight)
        st.caption(
            f"Current low/high allocation ratio: {low_risk_weight / high_risk_weight:.0f}:1. "
            "Risk 0.50 remains 1.00x."
        )

        # Compatibility values for the shared risk engine.
        total_capital_aud = float(starting_capital_aud)
        frequency = "Weekly"
        selected_day = dt.date.today().weekday()

    else:  # My Portfolio
        st.header("My Portfolio")
        # Compatibility values for the shared engine; portfolio mode does not run market calculations.
        starting_capital_aud = float(st.session_state.get("portfolio_starting_capital", 500000.0))
        remaining_capital_aud = float(st.session_state.get("portfolio_capital_remaining", starting_capital_aud))
        total_capital_aud = starting_capital_aud
        frequency = "Weekly"
        selected_day = dt.date.today().weekday()
        low_risk_weight = 5.0
        high_risk_weight = 0.10
        smart_dca_curve = build_smart_dca_curve(low_risk_weight, high_risk_weight)

    st.divider()

    # ------------------------------------------------------------
    # SIMPLE CONTROLS
    # ------------------------------------------------------------

    strategy_controls_container = st.expander(
        "Advanced engine settings (optional)", expanded=False
    )
    with strategy_controls_container:
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

if mode == "DCA Backtest":
    start_date = dca_backtest_start_date
    end_date = dca_backtest_end_date
else:
    end_date = today
    start_date = today - dt.timedelta(days=365 * 11)


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

if mode == "_Legacy Historical Backtest":

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
        dca_backtest_start_date, dt.time.min, tzinfo=timezone.utc
    )
    params["end_date"] = dt.datetime.combine(
        dca_backtest_end_date, dt.time.max, tzinfo=timezone.utc
    )
    params["day_of_week"] = selected_day

    with st.spinner("Loading historical BTC and AUD/USD data..."):
        df_full = fetch_btc_history(params["start_date"], params["end_date"])
        fx_series = fetch_aud_usd_rates(params["start_date"], params["end_date"])
        bg_token = get_bgeometrics_token()
        bg_data = fetch_bgeometrics_bundle(
            params["start_date"] - timedelta(days=300),
            params["end_date"],
            bg_token,
        )

    if df_full.empty:
        st.error("No BTC price data was returned.")
        st.stop()

    df_full = align_fx_to_dates(df_full, fx_series)
    df_full = merge_bgeometrics(df_full, bg_data)

    with st.spinner("Running equal-capital Plain DCA vs Smart DCA..."):
        plain_raw, _ = simulate_dca_backtest(
            df_full, params, DEFAULT_FIXED_DCA_AUD, dca_frequency, "Plain DCA"
        )
        smart_raw, _ = simulate_dca_backtest(
            df_full, params, DEFAULT_FIXED_DCA_AUD, dca_frequency,
            "Risk-Scaled DCA", risk_curve=smart_dca_curve
        )

        capital_target = float(intelligent_dca_budget_aud)
        plain_df, plain_sm = apply_equal_capital_allocator(
            plain_raw, total_budget_aud=capital_target,
            fee_pct=params.get("fee_pct", 0.0)
        )
        smart_df, smart_sm = apply_equal_capital_allocator(
            smart_raw, total_budget_aud=capital_target,
            fee_pct=params.get("fee_pct", 0.0)
        )
        recent_check = validate_smart_dca_recent_period(
            df_full, params, dca_frequency, capital_target, recent_fraction=0.30,
            risk_curve=smart_dca_curve
        )

    if not plain_sm or not smart_sm:
        st.error("Not enough historical data for this DCA Backtest.")
        st.stop()

    btc_adv = (
        (smart_sm["btc_held"] / plain_sm["btc_held"] - 1.0) * 100.0
        if plain_sm["btc_held"] > 0 else np.nan
    )
    cost_adv = (
        (1.0 - smart_sm["avg_cost_aud"] / plain_sm["avg_cost_aud"]) * 100.0
        if plain_sm["avg_cost_aud"] > 0 else np.nan
    )
    value_adv = (
        (smart_sm["btc_value_aud"] / plain_sm["btc_value_aud"] - 1.0) * 100.0
        if plain_sm["btc_value_aud"] > 0 else np.nan
    )

    st.header("Simple DCA Backtest")
    st.caption(
        f"Same A${capital_target:,.0f} budget • {dca_frequency} • "
        f"{dca_backtest_start_date.strftime('%d/%m/%Y')} to "
        f"{dca_backtest_end_date.strftime('%d/%m/%Y')}"
    )

    p1, p2 = st.columns(2)
    with p1:
        st.subheader("Plain DCA")
        st.metric("BTC Accumulated", f"{plain_sm['btc_held']:.6f}")
        st.metric("Average Cost", f"A${plain_sm['avg_cost_aud']:,.0f}")
        st.metric("Ending Value", f"A${plain_sm['btc_value_aud']:,.0f}")
        st.metric("ROI", f"{plain_sm['roi_pct']:+.2f}%")

    with p2:
        st.subheader("Smart DCA")
        st.metric(
            "BTC Accumulated", f"{smart_sm['btc_held']:.6f}",
            delta=f"{btc_adv:+.2f}% vs Plain"
        )
        st.metric(
            "Average Cost", f"A${smart_sm['avg_cost_aud']:,.0f}",
            delta=f"{cost_adv:+.2f}% advantage"
        )
        st.metric(
            "Ending Value", f"A${smart_sm['btc_value_aud']:,.0f}",
            delta=f"{value_adv:+.2f}% vs Plain"
        )
        st.metric("ROI", f"{smart_sm['roi_pct']:+.2f}%")

    st.subheader("Verdict")
    if btc_adv > 0:
        st.success(
            f"Smart DCA accumulated {btc_adv:+.2f}% more BTC than Plain DCA "
            f"for the same A${capital_target:,.0f}."
        )
    else:
        st.warning(
            f"Smart DCA accumulated {abs(btc_adv):.2f}% less BTC than Plain DCA. "
            "For this period, Plain DCA was the better strategy."
        )

    if recent_check:
        st.subheader("Recent 30% Validation")
        r1, r2, r3 = st.columns(3)
        r1.metric("Validation Budget", f"A${recent_check['budget_aud']:,.0f}")
        r2.metric("Plain DCA BTC", f"{recent_check['plain_btc']:.6f}")
        r3.metric(
            "Smart DCA BTC", f"{recent_check['smart_btc']:.6f}",
            delta=f"{recent_check['btc_advantage_pct']:+.2f}% vs Plain"
        )
        if recent_check["btc_advantage_pct"] > 0:
            st.success("Smart DCA also beat Plain DCA in the most recent 30% of the test period.")
        else:
            st.info("Smart DCA did not beat Plain DCA in the most recent 30% of the test period.")

    with st.expander("How Smart DCA works", expanded=False):
        st.write(
            "Smart DCA always buys, but conviction is intentionally asymmetric. "
            "Low-risk periods can receive many times more capital than high-risk periods. "
            "You control only the two endpoints; risk 0.50 stays anchored at 1.00x. "
            "The total budget is still normalized to exactly the same amount as Plain DCA."
        )
        curve_df = pd.DataFrame(smart_dca_curve, columns=["Risk", "Relative Weight"])
        curve_df["Relative Weight"] = curve_df["Relative Weight"].map(lambda x: f"{x:.2f}x")
        st.dataframe(curve_df, width="stretch", hide_index=True)

    with st.expander("Detailed activity", expanded=False):
        detail_cols = [
            "date", "price_usd", "risk_score", "actual_buy_aud",
            "btc_bought", "btc_held", "cumulative_invested_aud", "avg_cost_aud"
        ]
        smart_detail = smart_df[[c for c in detail_cols if c in smart_df.columns]].copy()
        st.dataframe(smart_detail.tail(250), width="stretch", hide_index=True)

    plain_csv = plain_df.to_csv(index=False).encode("utf-8")
    smart_csv = smart_df.to_csv(index=False).encode("utf-8")
    d1, d2 = st.columns(2)
    d1.download_button(
        "Download Plain DCA CSV", plain_csv,
        file_name="btc_v5_1_plain_dca.csv", mime="text/csv"
    )
    d2.download_button(
        "Download Smart DCA CSV", smart_csv,
        file_name="btc_v5_1_smart_dca.csv", mime="text/csv"
    )


# ================================================================

# ================================================================
# DCA Today
# ================================================================

elif mode == "DCA Today":
    now_utc = dt.datetime.now(timezone.utc)
    lookback_start = now_utc - timedelta(days=365 * 4)

    with st.spinner("Calculating today's BTC valuation risk..."):
        df_today = fetch_btc_history(lookback_start, now_utc)
        fx_today = fetch_aud_usd_rates(lookback_start, now_utc)
        bg_token = get_bgeometrics_token()
        bg_today = fetch_bgeometrics_bundle(
            lookback_start - timedelta(days=300), now_utc, bg_token
        )

    if df_today.empty:
        st.error("No BTC price data was returned.")
        st.stop()

    df_today = align_fx_to_dates(df_today, fx_today)
    df_today = merge_bgeometrics(df_today, bg_today)
    risk_today_df = add_risk_indicators(df_today, risk_model, params)

    valid_today = risk_today_df.dropna(subset=["risk_score", "price"])
    if valid_today.empty:
        st.error("Today's risk score could not be calculated from the available data.")
        st.stop()

    latest = valid_today.iloc[-1]
    current_risk = float(latest["risk_score"])
    current_price_usd = float(latest["price"])
    usd_per_aud = float(latest["usd_per_aud"]) if pd.notna(latest.get("usd_per_aud", np.nan)) else np.nan
    current_price_aud = current_price_usd / usd_per_aud if np.isfinite(usd_per_aud) and usd_per_aud > 0 else np.nan

    risk_weight = float(interpolate(smart_dca_curve, current_risk))

    # Opportunity rarity: use weekly historical risk observations available up
    # to today. This estimates how often BTC has been at least as cheap as now.
    if isinstance(valid_today.index, pd.DatetimeIndex):
        rarity_source = valid_today["risk_score"].resample("W-MON").last().dropna()
    elif "date" in valid_today.columns:
        rarity_source = valid_today.set_index("date")["risk_score"].resample("W-MON").last().dropna()
    else:
        # Safe fallback: use observations in their existing chronological order.
        rarity_source = valid_today["risk_score"].dropna()
    rarity = opportunity_rarity_from_history(rarity_source, current_risk)
    rarity_multiplier = float(rarity["rarity_multiplier"])
    effective_weight = risk_weight * rarity_multiplier

    days_remaining = max((target_deployment_date - dt.date.today()).days, 7)
    weeks_remaining = max(days_remaining / 7.0, 1.0)

    opportunity = lower_risk_opportunity_stats(
        rarity_source, current_risk, min(weeks_remaining, 156.0)
    )

    normal_weekly_allowance = float(remaining_capital_aud) / weeks_remaining
    recommended_buy = min(
        float(remaining_capital_aud),
        max(0.0, normal_weekly_allowance * effective_weight),
    )

    # Extreme-opportunity gate. Full deployment is only allowed when valuation
    # is exceptionally low AND historical analogues do not show a strong chance
    # of a materially lower entry within the remaining horizon. Sparse evidence
    # never forces an all-in recommendation.
    extreme_all_in_eligible = False
    if (
        current_risk <= 0.01
        and opportunity["samples"] >= 8
        and np.isfinite(opportunity["chance_materially_lower"])
        and opportunity["chance_materially_lower"] <= 0.15
    ):
        extreme_all_in_eligible = True
        recommended_buy = float(remaining_capital_aud)

    risk_label = (
        "VERY LOW" if current_risk <= 0.20 else
        "LOW" if current_risk <= 0.40 else
        "NEUTRAL" if current_risk <= 0.60 else
        "HIGH" if current_risk <= 0.80 else
        "VERY HIGH"
    )
    deployed = max(float(starting_capital_aud) - float(remaining_capital_aud), 0.0)
    remaining_after = max(float(remaining_capital_aud) - recommended_buy, 0.0)

    st.header("DCA Today")
    st.caption(
        "Uses the same V5.1 calibrated risk model and the same Smart DCA conviction curve as the backtest. "
        "The recommendation uses only data available now."
    )

    a, b, c, d = st.columns(4)
    a.metric("BTC Risk", f"{current_risk:.3f}", risk_label)
    b.metric("BTC Price", "n/a" if not np.isfinite(current_price_aud) else f"A${current_price_aud:,.0f}")
    c.metric("Opportunity Rarity", rarity["rarity_label"])
    if np.isfinite(opportunity["chance_materially_lower"]):
        d.metric(
            "Chance of Better Entry",
            f"{100.0 * opportunity['chance_materially_lower']:.0f}%",
            help="Historical analogue estimate of reaching a materially lower risk before the selected horizon.",
        )
    else:
        d.metric("Chance of Better Entry", "n/a")

    st.subheader("SMART DCA TODAY")
    st.metric("Recommended Buy", f"A${recommended_buy:,.0f}")

    x1, x2, x3 = st.columns(3)
    x1.metric("Normal Weekly Allowance", f"A${normal_weekly_allowance:,.0f}")
    x2.metric("Capital Remaining After Buy", f"A${remaining_after:,.0f}")
    x3.metric("Already Deployed", f"A${deployed:,.0f}")


    if extreme_all_in_eligible:
        st.success(
            "EXTREME OPPORTUNITY: the model's full-deployment gate is open. "
            "This is a model output, not a guarantee that BTC cannot fall further."
        )
    elif current_risk <= 0.02:
        st.warning(
            "EXTREME LOW RISK, but full deployment is not triggered because the historical "
            "evidence is either sparse or still shows a meaningful chance of an even lower-risk entry."
        )

    st.subheader("How Often This Risk Occurs — Cycle Context")
    occurrence = risk_occurrence_table(rarity_source)
    fig_occurrence = go.Figure()
    fig_occurrence.add_bar(
        x=occurrence["Risk range"],
        y=occurrence["Percent"],
        customdata=occurrence[["Weeks"]],
        hovertemplate="Risk %{x}<br>%{y:.1f}% of weeks<br>%{customdata[0]} weeks<extra></extra>",
    )
    fig_occurrence.update_layout(
        xaxis_title="BTC Risk Range",
        yaxis_title="Historical Weekly Frequency (%)",
        margin=dict(l=20, r=20, t=20, b=20),
        height=380,
    )
    st.plotly_chart(fig_occurrence, width="stretch")
    st.caption(
        f"Current risk {current_risk:.3f}. The chart uses weekly risk observations available "
        "to DCA Today and shows how uncommon each valuation zone has been."
    )

    with st.expander("Chance of a lower-risk entry — current + previous 2 cycles", expanded=False):
        if opportunity["samples"] >= 1:
            st.write(
                f"Historical analogue sample: {opportunity['samples']} prior weekly starting points "
                f"within about ±{opportunity['tolerance']:.3f} risk, looking ahead up to "
                f"{min(weeks_remaining, 156.0):.0f} weeks."
            )
            if np.isfinite(opportunity["chance_any_lower"]):
                st.write(f"Any lower risk: **{100.0 * opportunity['chance_any_lower']:.0f}%**")
            if np.isfinite(opportunity["chance_materially_lower"]):
                st.write(
                    f"Materially lower risk (≤ {opportunity['material_threshold']:.3f}): "
                    f"**{100.0 * opportunity['chance_materially_lower']:.0f}%**"
                )
            st.write(
                "Historical chance of reaching risk ≤0.05 / ≤0.02 / ≤0.01: "
                f"**{100.0 * opportunity['chance_le_005']:.0f}% / "
                f"{100.0 * opportunity['chance_le_002']:.0f}% / "
                f"{100.0 * opportunity['chance_le_001']:.0f}%**"
            )
            st.caption(
                "These are overlapping historical analogues, so treat them as decision-support "
                "estimates rather than independent statistical probabilities."
            )
        else:
            st.write("Not enough comparable historical observations for a useful estimate.")

    if current_risk <= 0.40:
        st.success(
            f"BTC valuation is {risk_label.lower()} and opportunity rarity is {rarity['rarity_label'].lower()}. "
            f"The base Smart weight is {risk_weight:.2f}× and the rarity-adjusted weight is {effective_weight:.2f}×."
        )
    elif current_risk >= 0.60:
        st.info(
            f"BTC valuation is {risk_label.lower()} and opportunity rarity is {rarity['rarity_label'].lower()}. "
            f"The model is preserving capital with an effective weight of {effective_weight:.2f}×."
        )
    else:
        st.info(
            f"BTC valuation is neutral and opportunity rarity is {rarity['rarity_label'].lower()}. "
            f"The effective allocation weight is {effective_weight:.2f}×."
        )

    with st.expander("How this amount is calculated", expanded=False):
        st.write(
            "Normal weekly allowance = capital remaining ÷ weeks remaining. "
            "The existing Smart DCA risk weight is then gently adjusted for how uncommon "
            "the current risk level has been historically, and capped at remaining capital."
        )
        st.write(
            f"A${remaining_capital_aud:,.0f} ÷ {weeks_remaining:.1f} weeks "
            f"× {risk_weight:.2f} base weight × {rarity_multiplier:.2f} rarity "
            f"= A${recommended_buy:,.0f}"
        )
        if np.isfinite(rarity["percentile"]):
            st.write(
                f"Historically, only about {rarity['percentile']:.1f}% of weekly observations "
                f"were at least as cheap as today's risk level. At that historical frequency, "
                f"a four-year cycle would contain roughly {rarity['expected_comparable_weeks_4y']:.0f} "
                "comparable-or-cheaper weekly observations."
            )
        st.caption(
            "This is a live capital-allocation rule, not a future-price forecast. "
            "It does not know future risk scores and does not retrospectively normalize future purchases. "
            "The experimental full-deployment gate can only open below risk 0.01 when enough historical "
            "analogues exist and the estimated chance of a materially better entry is low."
        )

# ================================================================
# My Portfolio
# ================================================================

elif mode == "My Portfolio":
    st.header("My Portfolio")
    st.caption(
        "Track direct BTC and the Australian iShares Bitcoin ETF (ASX: IBIT). "
        "IBIT entries are reported as BTC-equivalent exposure — ETF units are not direct ownership of bitcoin."
    )

    st.info(
        "Australian IBIT only: iShares Bitcoin ETF, ASX ticker IBIT, Australian domicile, "
        "ISIN AU0000424780. Default brokerage per ETF buy is A$3."
    )
    st.caption(
        "Portfolio entries typed into Streamlit are not permanently stored by Streamlit Cloud. "
        "Download the Portfolio CSV after changes so future app updates/restarts can restore them."
    )

    portfolio_cols = [
        "Date",
        "Asset",
        "AUD Spent",
        "Brokerage / Fee AUD",
        "Units / BTC Received",
        "BTC AUD Price",
    ]
    portfolio_df = pd.DataFrame(columns=portfolio_cols)

    uploaded_portfolio = st.file_uploader(
        "Load portfolio CSV (optional)", type=["csv"], key="portfolio_csv_upload"
    )
    if uploaded_portfolio is not None:
        try:
            portfolio_df = pd.read_csv(uploaded_portfolio)
            for col in portfolio_cols:
                if col not in portfolio_df.columns:
                    if col == "Asset":
                        portfolio_df[col] = "ASX:IBIT"
                    elif col == "Date":
                        portfolio_df[col] = ""
                    else:
                        portfolio_df[col] = 0.0
            portfolio_df = portfolio_df[portfolio_cols]
        except Exception as exc:
            st.error(f"Could not read portfolio CSV: {exc}")
            portfolio_df = pd.DataFrame(columns=portfolio_cols)

    starting_portfolio_capital = st.number_input(
        "Starting Deployment Capital (AUD)",
        min_value=0.0,
        value=float(st.session_state.get("portfolio_starting_capital", 500000.0)),
        step=10000.0,
        format="%.2f",
        key="portfolio_starting_capital_input",
    )

    st.subheader("Purchases")
    st.caption(
        "For ASX:IBIT enter the purchase date as DD/MM/YY, units bought and total AUD trade value. "
        "Brokerage defaults to A$3. The app automatically looks up BTC/AUD for the purchase date "
        "and calculates BTC-equivalent exposure. For Direct BTC, enter the actual BTC received."
    )

    # Restore the currently known ASX:IBIT purchase history when no CSV is loaded.
    # These are the five entries visible in the user's portfolio screenshot.
    if portfolio_df.empty:
        portfolio_df = pd.DataFrame([
            {
                "Date": "19/06/26",
                "Asset": "ASX:IBIT",
                "AUD Spent": 1700.0,
                "Brokerage / Fee AUD": 3.0,
                "Units / BTC Received": 100.0,
                "BTC AUD Price": 0.0,
            },
            {
                "Date": "26/08/26",
                "Asset": "ASX:IBIT",
                "AUD Spent": 2092.0,
                "Brokerage / Fee AUD": 3.0,
                "Units / BTC Received": 100.0,
                "BTC AUD Price": 0.0,
            },
            {
                "Date": "31/08/26",
                "Asset": "ASX:IBIT",
                "AUD Spent": 2061.0,
                "Brokerage / Fee AUD": 3.0,
                "Units / BTC Received": 100.0,
                "BTC AUD Price": 0.0,
            },
            {
                "Date": "01/09/26",
                "Asset": "ASX:IBIT",
                "AUD Spent": 2087.0,
                "Brokerage / Fee AUD": 3.0,
                "Units / BTC Received": 100.0,
                "BTC AUD Price": 0.0,
            },
            {
                "Date": "02/09/26",
                "Asset": "ASX:IBIT",
                "AUD Spent": 2050.0,
                "Brokerage / Fee AUD": 3.0,
                "Units / BTC Received": 100.0,
                "BTC AUD Price": 0.0,
            },
        ])

    edited_portfolio = st.data_editor(
        portfolio_df,
        num_rows="dynamic",
        width="stretch",
        hide_index=True,
        column_config={
            "Date": st.column_config.TextColumn(
                "Date (DD/MM/YY)",
                help="Australian date format, e.g. 02/09/26",
            ),
            "Asset": st.column_config.SelectboxColumn(
                "Asset",
                options=["ASX:IBIT", "Direct BTC"],
                required=True,
            ),
            "AUD Spent": st.column_config.NumberColumn(
                "AUD Spent", min_value=0.0, format="A$%.2f"
            ),
            "Brokerage / Fee AUD": st.column_config.NumberColumn(
                "Brokerage / Fee AUD", min_value=0.0, default=3.0, format="A$%.2f"
            ),
            "Units / BTC Received": st.column_config.NumberColumn(
                "Units / BTC Received", min_value=0.0, format="%.8f"
            ),
            "BTC AUD Price": st.column_config.NumberColumn(
                "BTC AUD Price (auto)", min_value=0.0, format="A$%.2f", disabled=True
            ),
        },
        key="portfolio_editor",
    )

    clean = edited_portfolio.copy()
    for col in ["AUD Spent", "Brokerage / Fee AUD", "Units / BTC Received", "BTC AUD Price"]:
        clean[col] = pd.to_numeric(clean[col], errors="coerce").fillna(0.0)

    # Australian date format: DD/MM/YY. Also accept ISO dates from older V5.6 CSVs.
    def _parse_portfolio_date(value):
        if pd.isna(value):
            return pd.NaT
        s = str(value).strip()
        for fmt in ("%d/%m/%y", "%d/%m/%Y", "%Y-%m-%d"):
            try:
                return pd.Timestamp(dt.datetime.strptime(s, fmt).date())
            except Exception:
                pass
        return pd.to_datetime(s, dayfirst=True, errors="coerce")

    clean["_purchase_date"] = clean["Date"].apply(_parse_portfolio_date)

    # Automatically populate BTC/AUD for ASX:IBIT rows from the same BTC + FX data
    # used elsewhere in the app. This avoids manual BTC price entry.
    ibit_dates = clean.loc[
        clean["Asset"].eq("ASX:IBIT") & clean["_purchase_date"].notna(),
        "_purchase_date"
    ]
    if not ibit_dates.empty:
        lookup_start = ibit_dates.min().date() - dt.timedelta(days=7)
        lookup_end = max(ibit_dates.max().date(), dt.date.today())
        try:
            btc_lookup = fetch_btc_history(lookup_start, lookup_end)
            fx_lookup = fetch_aud_usd_rates(lookup_start, lookup_end)
            if btc_lookup is not None and not btc_lookup.empty and fx_lookup:
                lookup = btc_lookup[["price"]].copy()
                lookup["lookup_date"] = pd.to_datetime(lookup.index, utc=True).date
                fx_series = pd.Series(fx_lookup, dtype=float)
                fx_series.index = pd.to_datetime(fx_series.index).date
                lookup["usd_per_aud"] = lookup["lookup_date"].map(fx_series)
                lookup["usd_per_aud"] = lookup["usd_per_aud"].ffill().bfill()
                lookup["btc_aud_auto"] = lookup["price"] / lookup["usd_per_aud"]
                daily_btc_aud = (
                    lookup.dropna(subset=["btc_aud_auto"])
                    .groupby("lookup_date")["btc_aud_auto"]
                    .last()
                )
                for row_idx in clean.index[clean["Asset"].eq("ASX:IBIT")]:
                    pd_date = clean.at[row_idx, "_purchase_date"]
                    if pd.isna(pd_date):
                        continue
                    d = pd_date.date()
                    if d in daily_btc_aud.index:
                        clean.at[row_idx, "BTC AUD Price"] = float(daily_btc_aud.loc[d])
                    else:
                        prior = daily_btc_aud[daily_btc_aud.index <= d]
                        if not prior.empty:
                            clean.at[row_idx, "BTC AUD Price"] = float(prior.iloc[-1])
        except Exception as exc:
            st.warning(f"Could not automatically load BTC/AUD for one or more purchases: {exc}")

    # Calculate BTC-equivalent exposure per transaction.
    #
    # ASX:IBIT:
    #   trade value excluding brokerage / BTC-AUD price on transaction date
    # This is the economic BTC-equivalent represented by the AUD value committed to the ETF.
    # It is deliberately labelled equivalent exposure, not direct BTC ownership.
    #
    # Direct BTC:
    #   uses the actual BTC received entered by the user.
    clean["BTC Equivalent"] = 0.0
    ibit_mask = clean["Asset"].eq("ASX:IBIT")
    direct_mask = clean["Asset"].eq("Direct BTC")

    # Treat "AUD Spent" as the ETF trade consideration excluding brokerage.
    valid_ibit = ibit_mask & (clean["BTC AUD Price"] > 0)
    clean.loc[valid_ibit, "BTC Equivalent"] = (
        clean.loc[valid_ibit, "AUD Spent"] / clean.loc[valid_ibit, "BTC AUD Price"]
    )
    clean.loc[direct_mask, "BTC Equivalent"] = clean.loc[direct_mask, "Units / BTC Received"]

    # Useful audit fields for ETF buys.
    clean["ETF Unit Price AUD"] = np.nan
    valid_units = ibit_mask & (clean["Units / BTC Received"] > 0)
    clean.loc[valid_units, "ETF Unit Price AUD"] = (
        clean.loc[valid_units, "AUD Spent"] / clean.loc[valid_units, "Units / BTC Received"]
    )
    clean["BTC Eq / ETF Unit"] = np.nan
    valid_eq_unit = valid_units & (clean["BTC AUD Price"] > 0)
    clean.loc[valid_eq_unit, "BTC Eq / ETF Unit"] = (
        clean.loc[valid_eq_unit, "ETF Unit Price AUD"] /
        clean.loc[valid_eq_unit, "BTC AUD Price"]
    )

    total_trade_value = float(clean["AUD Spent"].sum())
    total_fees = float(clean["Brokerage / Fee AUD"].sum())
    total_cash_out = total_trade_value + total_fees
    total_btc_equivalent = float(clean["BTC Equivalent"].sum())
    direct_btc = float(clean.loc[direct_mask, "BTC Equivalent"].sum())
    ibit_btc_equivalent = float(clean.loc[ibit_mask, "BTC Equivalent"].sum())
    ibit_units = float(clean.loc[ibit_mask, "Units / BTC Received"].sum())
    capital_remaining = max(0.0, float(starting_portfolio_capital) - total_cash_out)
    avg_cost = total_cash_out / total_btc_equivalent if total_btc_equivalent > 0 else np.nan

    st.session_state["portfolio_starting_capital"] = float(starting_portfolio_capital)
    st.session_state["portfolio_capital_remaining"] = float(capital_remaining)

    p1, p2, p3, p4 = st.columns(4)
    p1.metric("Total BTC Exposure", f"{total_btc_equivalent:.8f} BTC-eq")
    p2.metric("ASX:IBIT Units", f"{ibit_units:,.4f}")
    p3.metric("Capital Remaining", f"A${capital_remaining:,.0f}")
    p4.metric(
        "Average Cost",
        "n/a" if not np.isfinite(avg_cost) else f"A${avg_cost:,.0f}/BTC-eq"
    )

    q1, q2, q3, q4 = st.columns(4)
    q1.metric("IBIT BTC-equivalent", f"{ibit_btc_equivalent:.8f}")
    q2.metric("Direct BTC", f"{direct_btc:.8f}")
    q3.metric("Trade Value", f"A${total_trade_value:,.0f}")
    q4.metric("Brokerage / Fees", f"A${total_fees:,.2f}")

    st.subheader("Calculated Transactions")
    clean["Date"] = clean["_purchase_date"].apply(
        lambda x: x.strftime("%d/%m/%y") if pd.notna(x) else ""
    )
    display_cols = [
        "Date", "Asset", "AUD Spent", "Brokerage / Fee AUD",
        "Units / BTC Received", "ETF Unit Price AUD", "BTC AUD Price",
        "BTC Eq / ETF Unit", "BTC Equivalent"
    ]
    st.dataframe(clean[display_cols], width="stretch", hide_index=True)

    st.caption(
        "For ASX:IBIT, the app calculates the ETF unit price from AUD spent ÷ units, automatically "
        "looks up BTC/AUD for the purchase date, then estimates BTC-equivalent exposure as AUD trade "
        "value ÷ BTC/AUD. This is an economic exposure estimate, not the exact bitcoin legally held "
        "for each ETF unit."
    )

    export_clean = clean.drop(columns=["_purchase_date"], errors="ignore")
    st.download_button(
        "Download Portfolio CSV",
        data=export_clean.to_csv(index=False).encode("utf-8"),
        file_name="btc_portfolio_asx_ibit.csv",
        mime="text/csv",
        key="portfolio_download",
    )

    st.subheader("Decision History")
    st.caption("Optional audit trail: what the model showed versus what you actually bought.")

    decision_cols = [
        "Date", "BTC Price AUD", "Risk", "Better Entry Chance %",
        "Model Recommendation AUD", "Actual Purchase AUD", "Asset"
    ]
    decision_df = pd.DataFrame(columns=decision_cols)

    decision_upload = st.file_uploader(
        "Load decision-history CSV (optional)", type=["csv"], key="decision_csv_upload"
    )
    if decision_upload is not None:
        try:
            decision_df = pd.read_csv(decision_upload)
            for col in decision_cols:
                if col not in decision_df.columns:
                    decision_df[col] = ""
            decision_df = decision_df[decision_cols]
        except Exception as exc:
            st.error(f"Could not read decision-history CSV: {exc}")
            decision_df = pd.DataFrame(columns=decision_cols)

    edited_decisions = st.data_editor(
        decision_df, num_rows="dynamic", width="stretch", hide_index=True,
        key="decision_history_editor"
    )
    st.download_button(
        "Download Decision History CSV",
        data=edited_decisions.to_csv(index=False).encode("utf-8"),
        file_name="btc_dca_decision_history.csv",
        mime="text/csv",
        key="decision_download",
    )

    st.info(
        "After updating purchases, download the portfolio CSV. Upload it next time to restore "
        "your purchases. DCA Today will use the remaining-capital value during the same session."
    )

