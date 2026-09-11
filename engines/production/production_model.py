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
import json

import numpy as np
from datetime import timedelta, timezone

import pandas as pd
import plotly.graph_objects as go
import requests
import streamlit as st

try:
    from streamlit_local_storage import LocalStorage
    LOCAL_STORAGE_AVAILABLE = True
except Exception:
    LocalStorage = None
    LOCAL_STORAGE_AVAILABLE = False


# ================================================================
# Constants
# ================================================================

GENESIS_DATE = dt.datetime(2009, 1, 3, tzinfo=timezone.utc)

DEFAULT_PL_CHEAP = -0.10
DEFAULT_PL_EXPENSIVE = 0.20

DEFAULT_FUND_CHEAP = 1.00
DEFAULT_FUND_EXPENSIVE = 1.50

DEFAULT_MIN_CASH_RESERVE_PCT = 0.00
DEFAULT_MAX_SELL_PCT_PERIOD = 0.25  # Avoid dumping >25% of BTC in one period
DEFAULT_FEE_PCT = 0.00

REQUEST_HEADERS = {"User-Agent": "BTC-DCA-Simulator/3.4"}

BGEOMETRICS_BASE = "https://bitcoin-data.com/v1"
DEFAULT_VALUATION_STRENGTH = 0.75
DEFAULT_MIN_VALUATION_MULT = 0.50
DEFAULT_MAX_VALUATION_MULT = 2.50
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


DEFAULT_INTELLIGENT_DCA_BUDGET_AUD = 500000.0

SMART_DCA_LOW_RISK_WEIGHT = 2.75
SMART_DCA_HIGH_RISK_WEIGHT = 0.05

SMART_DCA_POINTS = [
    (0.00, 2.7500),
    (0.10, 2.3125),
    (0.20, 1.8750),
    (0.30, 1.5250),
    (0.40, 1.21875),
    (0.50, 1.0000),
    (0.60, 0.6305555555),
    (0.70, 0.3666666666),
    (0.80, 0.2083333334),
    (0.90, 0.0711111111),
    (1.00, 0.0500),
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
    """Cycle-relative estimate for a materially lower future Risk Score.

    Uses only the current cycle plus the previous two cycles and only information
    observable as of the supplied series endpoint. To avoid pseudo-replication,
    each BTC cycle contributes at most ONE representative analogue: the prior
    observation closest to today's risk and cycle age whose full outcome horizon
    is already known.
    """
    frame, current_cycle, current_week = _cycle_context(risk_series)
    horizon = int(max(1, min(float(horizon_weeks), 156.0)))
    empty = {
        "samples": 0, "tolerance": np.nan, "chance_any_lower": np.nan,
        "chance_materially_lower": np.nan, "chance_le_005": np.nan,
        "chance_le_002": np.nan, "chance_le_001": np.nan,
        "median_future_min": np.nan, "material_threshold": np.nan,
        "evidence_label": "LOW", "phase_window_weeks": np.nan,
        "cycles_used": 0, "cycle_successes": 0, "cycle_details": [],
    }
    if frame.empty or not np.isfinite(current_risk):
        return empty

    material_threshold = max(
        0.0,
        min(float(current_risk) - 0.01, float(current_risk) * 0.75)
    )
    asof = frame.index.max()

    representatives = []
    chosen_tol = np.nan
    chosen_phase = np.nan

    # Widen only as needed. Within each cycle, choose the closest analogue.
    for phase_window in (26, 39, 52, 78):
        for tol in (0.015, 0.025, 0.04, 0.06, 0.10):
            reps = []
            for offset, cycle_weight in CYCLE_WEIGHTS.items():
                cid = current_cycle - offset
                if cid < 0:
                    continue

                candidates = frame[
                    (frame["cycle_id"] == cid)
                    & ((frame["risk"] - float(current_risk)).abs() <= tol)
                    & ((frame["cycle_week"] - current_week).abs() <= phase_window)
                ].copy()

                if candidates.empty:
                    continue

                # Outcome window must be completely in the known past.
                candidates = candidates[
                    (candidates.index < asof)
                    & ((candidates.index + pd.to_timedelta(horizon, unit="W")) <= asof)
                ].copy()
                if candidates.empty:
                    continue

                # Rank by closeness in risk first, then cycle phase.
                candidates["_risk_gap"] = (candidates["risk"] - float(current_risk)).abs()
                candidates["_phase_gap"] = (candidates["cycle_week"] - current_week).abs()
                candidates["_score"] = (
                    candidates["_risk_gap"] / max(tol, 1e-9)
                    + candidates["_phase_gap"] / max(float(phase_window), 1.0)
                )
                ts = candidates["_score"].idxmin()
                row = candidates.loc[ts]

                outcome_end = ts + pd.Timedelta(weeks=horizon)
                future = frame[
                    (frame["cycle_id"] == cid)
                    & (frame.index > ts)
                    & (frame.index <= outcome_end)
                ]["risk"]
                if future.empty:
                    continue

                reps.append({
                    "cycle_id": int(cid),
                    "offset": int(offset),
                    "weight": float(cycle_weight),
                    "analogue_date": ts,
                    "analogue_risk": float(row["risk"]),
                    "analogue_cycle_week": int(row["cycle_week"]),
                    "future_min": float(future.min()),
                })

            # We can never have more than 3 independent cycle observations.
            if len(reps) >= 2:
                representatives = reps
                chosen_tol, chosen_phase = tol, phase_window
                break
            if len(reps) > len(representatives):
                representatives = reps
                chosen_tol, chosen_phase = tol, phase_window
        if len(representatives) >= 2:
            break

    if not representatives:
        empty["material_threshold"] = material_threshold
        return empty

    weights = np.array([x["weight"] for x in representatives], dtype=float)
    weights = weights / weights.sum()
    mins = np.array([x["future_min"] for x in representatives], dtype=float)

    def wp(condition):
        return float(weights[np.asarray(condition, dtype=bool)].sum())

    cycles_used = len(representatives)
    cycle_successes = int((mins <= material_threshold).sum())
    evidence = "MODERATE" if cycles_used == 3 else "LOW"

    details = []
    for rep, norm_weight in zip(representatives, weights):
        details.append({
            **rep,
            "normalized_weight": float(norm_weight),
            "materially_lower": bool(rep["future_min"] <= material_threshold),
        })

    return {
        "samples": cycles_used,  # retained for compatibility; now means independent cycles
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
        "cycles_used": cycles_used,
        "cycle_successes": cycle_successes,
        "cycle_details": details,
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

    # Normalize all caller date/datetime inputs to UTC-aware timestamps.
    # This prevents comparisons between a UTC DatetimeIndex and Python date objects.
    start_ts = pd.Timestamp(start_date)
    end_ts = pd.Timestamp(end_date)
    if start_ts.tzinfo is None:
        start_ts = start_ts.tz_localize("UTC")
    else:
        start_ts = start_ts.tz_convert("UTC")
    if end_ts.tzinfo is None:
        # For a plain date, include the whole day.
        end_ts = end_ts.tz_localize("UTC") + pd.Timedelta(days=1) - pd.Timedelta(microseconds=1)
    else:
        end_ts = end_ts.tz_convert("UTC")

    fetch_start = start_ts - timedelta(days=buffer_days)

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
        (df.index <= end_ts)
    ].copy()

    return df


@st.cache_data(ttl=60)
def fetch_live_btc_aud():
    """Fetch a fresh BTC/AUD spot price for the DCA Today display only."""
    url = "https://api.coingecko.com/api/v3/simple/price"
    params = {"ids": "bitcoin", "vs_currencies": "aud"}
    try:
        resp = requests.get(url, params=params, headers=REQUEST_HEADERS, timeout=15)
        resp.raise_for_status()
        payload = resp.json()
        value = float(payload.get("bitcoin", {}).get("aud", np.nan))
        return value if np.isfinite(value) and value > 0 else np.nan
    except Exception:
        return np.nan


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







# ================================================================







def simulate_dca_backtest(
    df_full, params, base_dca_aud, dca_frequency, strategy_mode, risk_curve=None
):
    """Historical accumulation-only backtest for active Plain and Smart DCA modes."""
    if risk_curve is None:
        risk_curve = DEFAULT_ALWAYS_DCA_POINTS
    if strategy_mode not in {"Plain DCA", "Risk-Scaled DCA"}:
        raise ValueError(f"Unsupported active DCA strategy: {strategy_mode}")
    if df_full.empty:
        return pd.DataFrame(), {}
    df = df_full[(df_full.index >= params["start_date"]) & (df_full.index <= params["end_date"])].copy()
    if df.empty:
        return pd.DataFrame(), {}
    df = add_risk_indicators(df, params["risk_model"], params)
    execution = select_execution_dates(df, dca_frequency, params["day_of_week"])
    if execution.empty:
        return pd.DataFrame(), {}
    btc = cumulative_invested = cumulative_fees = 0.0
    rows = []
    for timestamp, row in execution.iterrows():
        price_usd = float(row["price"]); usd_per_aud = float(row["usd_per_aud"])
        if price_usd <= 0 or usd_per_aud <= 0:
            continue
        price_aud = price_usd / usd_per_aud
        risk = float(row["risk_score"]) if pd.notna(row["risk_score"]) else np.nan
        if strategy_mode == "Plain DCA":
            multiplier, contribution, signal = 1.0, float(base_dca_aud), "FIXED DCA"
        else:
            multiplier = float(interpolate(risk_curve, risk)) if np.isfinite(risk) else 1.0
            contribution = float(base_dca_aud) * multiplier
            signal = "SCALED DCA"
        fee = contribution * float(params.get("fee_pct", 0.0))
        net_contribution = max(0.0, contribution - fee)
        btc_bought = net_contribution / price_aud if price_aud > 0 else 0.0
        btc += btc_bought; cumulative_invested += contribution; cumulative_fees += fee
        btc_value = btc * price_aud; pnl = btc_value - cumulative_invested
        roi_pct = (btc_value / cumulative_invested - 1.0) * 100.0 if cumulative_invested > 0 else 0.0
        avg_cost_aud = cumulative_invested / btc if btc > 0 else 0.0
        rows.append({
            "date": timestamp, "price_usd": price_usd, "btc_price_aud": price_aud,
            "risk_score": risk, "strategy_mode": strategy_mode, "dca_multiplier": multiplier,
            "base_dca_aud": float(base_dca_aud), "dca_frequency": dca_frequency,
            "actual_buy_aud": contribution, "btc_bought": btc_bought, "btc_held": btc,
            "cumulative_invested_aud": cumulative_invested, "cumulative_fees_aud": cumulative_fees,
            "btc_value_aud": btc_value, "pnl_aud": pnl, "roi_pct": roi_pct,
            "avg_cost_aud": avg_cost_aud, "signal": signal,
        })
    result = pd.DataFrame(rows)
    if result.empty:
        return result, {}
    final = result.iloc[-1]
    summary = {
        "strategy_mode": strategy_mode, "base_dca_aud": float(base_dca_aud), "frequency": dca_frequency,
        "total_invested_aud": float(final["cumulative_invested_aud"]), "btc_held": float(final["btc_held"]),
        "btc_value_aud": float(final["btc_value_aud"]), "pnl_aud": float(final["pnl_aud"]),
        "roi_pct": float(final["roi_pct"]), "avg_cost_aud": float(final["avg_cost_aud"]),
        "fees_aud": float(final["cumulative_fees_aud"]), "execution_count": int(len(result)),
        "buy_count": int((result["actual_buy_aud"] > 0).sum()),
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





# ================================================================
# Walk-forward Optimisation (V3.6)
# ================================================================





