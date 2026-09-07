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

SMART_DCA_LOW_RISK_WEIGHT = 2.00
SMART_DCA_HIGH_RISK_WEIGHT = 0.80

# V5.9 Research: deliberately moderate, neutral-centred sizing curve.
# Research candidate is intentionally simple: 2.0x at risk 0, 1.0x at 0.5,
# and 0.8x at risk 1.0, with linear interpolation between anchors.
SMART_DCA_POINTS = [
    (0.00, 2.00),
    (0.50, 1.00),
    (1.00, 0.80),
]

RESEARCH_PL_REFIT_DAYS = 91
RESEARCH_PL_MIN_WEEKS = 52
RESEARCH_PL_HISTORY_START = pd.Timestamp("2012-01-01", tz="UTC")

# V5.9 R2 Bottom Zone Challenger — research-only staged deployment overlay.
BOTTOM_CHALLENGER_THRESHOLD = 0.85
BOTTOM_CHALLENGER_PRICE_POSITION_MAX = 0.20
BOTTOM_CHALLENGER_REQUIRED_CONFIRMING_CATEGORIES = 2
BOTTOM_CHALLENGER_STEP_DOWN = 0.15
BOTTOM_CHALLENGER_INITIAL_MULT = 3.00
BOTTOM_CHALLENGER_STEP_MULT = 4.00
BOTTOM_CHALLENGER_RECOVERY_MULT = 3.00
BOTTOM_CHALLENGER_RECENT_WEEKS = 26


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

def walk_forward_power_law(data, cheap=-0.10, expensive=0.20, min_weeks=52, refit_days=91):
    """Causal expanding Power Law fit using only observations strictly before each date.

    The regression is fitted to weekly BTC closes and refreshed slowly (quarterly by
    default). Between refits the last known coefficients are frozen. This avoids using
    today's final Power Law coefficients throughout history.
    """
    prices = pd.to_numeric(data["price"], errors="coerce").astype(float)
    scores = pd.Series(np.nan, index=data.index, dtype=float)
    fair = pd.Series(np.nan, index=data.index, dtype=float)
    residuals = pd.Series(np.nan, index=data.index, dtype=float)
    slopes = pd.Series(np.nan, index=data.index, dtype=float)
    intercepts = pd.Series(np.nan, index=data.index, dtype=float)

    last_fit = None
    slope = intercept = np.nan
    for ts in data.index:
        need_refit = last_fit is None or (ts - last_fit).days >= int(refit_days)
        if need_refit:
            hist = prices.loc[prices.index < ts].dropna()
            if not hist.empty:
                weekly = hist.resample("W-MON").last().dropna()
                days = np.array([(x - GENESIS_DATE).days for x in weekly.index], dtype=float)
                vals = weekly.to_numpy(dtype=float)
                ok = (days > 0) & np.isfinite(vals) & (vals > 0)
                if int(ok.sum()) >= int(min_weeks):
                    x = np.log10(days[ok])
                    y = np.log10(vals[ok])
                    slope, intercept = np.polyfit(x, y, 1)
                    last_fit = ts

        price = float(prices.loc[ts]) if pd.notna(prices.loc[ts]) else np.nan
        days_now = (ts - GENESIS_DATE).days
        if np.isfinite(slope) and np.isfinite(intercept) and np.isfinite(price) and price > 0 and days_now > 0:
            fv_log = float(slope) * math.log10(days_now) + float(intercept)
            fv = 10 ** fv_log
            resid = math.log10(price) - fv_log
            denom = expensive - cheap
            score = clamp((resid - cheap) / denom, 0.0, 1.0) if denom > 0 else 0.5
            scores.loc[ts] = score
            fair.loc[ts] = fv
            residuals.loc[ts] = resid
            slopes.loc[ts] = slope
            intercepts.loc[ts] = intercept

    return scores, fair, residuals, slopes, intercepts



def continuous_pl_display_risk(price, fair_value, cheap=-0.10, expensive=0.20):
    """Continuous valuation-risk display that reserves 0.000 for a zero BTC price.

    This is intentionally separate from the proven R2 sizing score.  It anchors
    fair value at 0.50, the legacy R2 cheap boundary near 0.20, and the legacy
    expensive boundary near 0.80.  For any strictly positive BTC price the
    returned value is strictly above zero; as price grows without bound it
    approaches 1.0 asymptotically.
    """
    try:
        price = float(price)
        fair_value = float(fair_value)
    except Exception:
        return np.nan
    if not np.isfinite(price) or not np.isfinite(fair_value) or fair_value <= 0:
        return np.nan
    if price <= 0:
        return 0.0

    ratio = price / fair_value
    if ratio <= 0:
        return 0.0

    cheap_ratio = 10.0 ** float(cheap)
    expensive_ratio = 10.0 ** float(expensive)

    # Choose exponents so the historical R2 clamp boundaries retain intuitive
    # display anchors: cheap boundary ~= 0.20 and expensive boundary ~= 0.80.
    if 0 < cheap_ratio < 1:
        low_exp = math.log(0.20 / 0.50) / math.log(cheap_ratio)
    else:
        low_exp = 4.0
    if expensive_ratio > 1:
        high_exp = math.log(0.50 / (1.0 - 0.80)) / math.log(expensive_ratio)
    else:
        high_exp = 2.0

    if ratio <= 1.0:
        out = 0.50 * (ratio ** low_exp)
    else:
        out = 1.0 - 0.50 / (ratio ** high_exp)

    # Numerically preserve the semantic rule: positive BTC price != zero risk.
    if out <= 0.0:
        out = float(np.nextafter(0.0, 1.0))
    return float(min(out, float(np.nextafter(1.0, 0.0))))


def format_continuous_risk(value, price=None):
    """Format risk so a positive BTC price never visually rounds to 0.000."""
    if value is None or not np.isfinite(value):
        return "n/a"
    if price is not None and np.isfinite(price) and float(price) > 0 and 0 < float(value) < 0.0005:
        return "<0.001"
    return f"{float(value):.3f}"


def add_cycle_context_research(result, params):
    """Add causal, display-only bottom/trend context to a scored BTC frame.

    Nothing in this function changes ``risk_score`` or the R2 DCA multiplier.
    It creates:
      * continuous_valuation_risk -- zero only when BTC price is zero
      * weekly_bull_confirmed -- 50-week MA reclaim proxy with 3-week confirmation
      * bull_age_weeks / cycle_stage
      * bottom_zone_score -- current bottom-like evidence (0..100)
      * bottom_confidence_score -- recent bottom evidence + trend confirmation (0..100)

    Bottom Confidence is an evidence score, NOT a calibrated probability that the
    exact cycle low is in.  Every input is based only on data available on or
    before each timestamp.
    """
    out = result.copy()
    cheap = float(params.get("pl_cheap", DEFAULT_PL_CHEAP))
    expensive = float(params.get("pl_expensive", DEFAULT_PL_EXPENSIVE))

    # ---------- Continuous valuation risk (display only) ----------
    out["continuous_valuation_risk"] = [
        continuous_pl_display_risk(px, fv, cheap, expensive)
        for px, fv in zip(
            pd.to_numeric(out.get("price"), errors="coerce"),
            pd.to_numeric(out.get("fair_value"), errors="coerce"),
        )
    ]

    # ---------- Weekly trend confirmation / age ----------
    price = pd.to_numeric(out["price"], errors="coerce")
    weekly = price.resample("W-MON").last().dropna()
    w = pd.DataFrame(index=weekly.index)
    w["close"] = weekly
    w["ma50"] = weekly.rolling(50, min_periods=50).mean()
    w["ma200"] = weekly.rolling(200, min_periods=156).mean()
    above50 = (w["close"] > w["ma50"]) & w["ma50"].notna()
    below50 = (w["close"] < w["ma50"]) & w["ma50"].notna()
    w["bull_reclaim_confirm"] = (above50.astype(int).rolling(3, min_periods=3).sum() >= 3)
    w["bear_break_confirm"] = (below50.astype(int).rolling(3, min_periods=3).sum() >= 3)

    state = False
    start = None
    states, ages, flips = [], [], []
    for ts, row in w.iterrows():
        flip = False
        if (not state) and bool(row["bull_reclaim_confirm"]):
            state = True
            start = ts
            flip = True
        elif state and bool(row["bear_break_confirm"]):
            state = False
            start = None
        states.append(bool(state))
        ages.append(int((ts - start).days // 7) if state and start is not None else np.nan)
        flips.append(bool(flip))
    w["weekly_bull_confirmed"] = states
    w["bull_age_weeks"] = ages
    w["bull_confirmation_flip"] = flips

    def stage(age, state):
        if not state or not np.isfinite(age):
            return "BEAR / UNCONFIRMED"
        age = int(age)
        if age <= 26:
            return "EARLY RECOVERY"
        if age <= 78:
            return "EXPANSION"
        if age <= 104:
            return "MATURE BULL"
        return "LATE BULL"
    w["cycle_stage"] = [stage(a, st) for a, st in zip(w["bull_age_weeks"], w["weekly_bull_confirmed"])]

    # ---------- Bottom-zone evidence ----------
    # Each component is deliberately simple and monotonic. Missing components are
    # ignored and the available weights are renormalized. This is research context.
    resid = pd.to_numeric(out.get("power_law_residual"), errors="coerce")
    pl_evidence = ((0.15 - resid) / (0.15 - cheap)).clip(0, 1)

    rolling_high = price.rolling(365, min_periods=180).max()
    drawdown = (1.0 - price / rolling_high.replace(0, np.nan)).clip(0, 1)
    dd_evidence = ((drawdown - 0.20) / (0.50 - 0.20)).clip(0, 1)

    # Align weekly 200W MA to daily rows without looking ahead.
    ma200_daily = w["ma200"].reindex(out.index, method="ffill")
    ratio_200w = price / ma200_daily.replace(0, np.nan)
    ma200_evidence = ((1.60 - ratio_200w) / (1.60 - 1.10)).clip(0, 1)

    mvrv_z = pd.to_numeric(out.get("mvrv_z"), errors="coerce")
    mvrv_evidence = ((2.0 - mvrv_z) / (2.0 - 0.5)).clip(0, 1)

    fear = pd.to_numeric(out.get("fear_greed"), errors="coerce")
    fear_evidence = ((60.0 - fear) / (60.0 - 25.0)).clip(0, 1)

    evidence_parts = {
        "pl": (pl_evidence, 0.30),
        "drawdown": (dd_evidence, 0.25),
        "ma200": (ma200_evidence, 0.20),
        "mvrv": (mvrv_evidence, 0.15),
        "fear": (fear_evidence, 0.10),
    }
    numerator = pd.Series(0.0, index=out.index)
    denominator = pd.Series(0.0, index=out.index)
    available = pd.Series(0, index=out.index, dtype=int)
    for name, (series, weight) in evidence_parts.items():
        valid = series.notna()
        numerator = numerator.add(series.fillna(0.0) * weight, fill_value=0.0)
        denominator = denominator.add(valid.astype(float) * weight, fill_value=0.0)
        available = available.add(valid.astype(int), fill_value=0).astype(int)
        out[f"bottom_component_{name}"] = series

    bottom_zone = (numerator / denominator.replace(0, np.nan)).clip(0, 1)
    out["bottom_zone_score"] = bottom_zone * 100.0
    out["bottom_components_available"] = available

    # Carry forward the strongest bottom-like evidence from the prior ~26 weeks.
    # This allows capitulation evidence near the low to remain relevant when trend
    # confirmation arrives several weeks later, while remaining fully causal.
    recent_zone = out["bottom_zone_score"].rolling(182, min_periods=1).max() / 100.0

    bull_daily = w["weekly_bull_confirmed"].reindex(out.index, method="ffill").fillna(False).astype(bool)
    age_daily = w["bull_age_weeks"].reindex(out.index, method="ffill")
    stage_daily = w["cycle_stage"].reindex(out.index, method="ffill").fillna("BEAR / UNCONFIRMED")
    flip_daily = w["bull_confirmation_flip"].reindex(out.index, method="ffill").fillna(False).astype(bool)
    ma50_daily = w["ma50"].reindex(out.index, method="ffill")

    out["weekly_bull_confirmed"] = bull_daily
    out["bull_age_weeks"] = age_daily
    out["cycle_stage"] = stage_daily
    out["bull_confirmation_flip"] = flip_daily
    out["weekly_ma50"] = ma50_daily
    out["weekly_ma200"] = ma200_daily

    trend_evidence = bull_daily.astype(float)
    out["bottom_confidence_score"] = (100.0 * (0.75 * recent_zone + 0.25 * trend_evidence)).clip(0, 100)

    def conf_label(score, bull):
        if not np.isfinite(score):
            return "n/a"
        if bull and score >= 80:
            return "HIGH — BOTTOM LIKELY IN"
        if score >= 65:
            return "ELEVATED"
        if score >= 45:
            return "DEVELOPING"
        return "LOW"
    out["bottom_confidence_label"] = [
        conf_label(sc, bu) for sc, bu in zip(out["bottom_confidence_score"], bull_daily)
    ]

    return out


def add_bottom_zone_challenger(result):
    """Add a causal staged Exceptional Bottom Zone research overlay.

    Frozen R2 is untouched. Weekly signals require deep Power-Law valuation,
    BTC in the lowest 20% of its trailing 52-week price range, and at least two
    additional strongly-stressed categories. Correlated indicators are grouped.

    Staging: 3x on initial exceptional entry; 4x after each new >=15% lower price
    while confluence remains exceptional; 3x on a later bull-recovery confirmation
    occurring within 26 weeks. There is no fixed reserve and no automatic all-in.
    """
    out = result.copy()
    if out.empty:
        return out

    price = pd.to_numeric(out.get("price"), errors="coerce")
    weekly_price = price.resample("W-MON").last().dropna()
    weekly = pd.DataFrame(index=weekly_price.index)
    weekly["price"] = weekly_price

    def wk(col):
        if col not in out.columns:
            return pd.Series(np.nan, index=weekly.index, dtype=float)
        return pd.to_numeric(out[col], errors="coerce").resample("W-MON").last().reindex(weekly.index)

    pl = wk("bottom_component_pl").clip(0, 1)
    mvrv = wk("bottom_component_mvrv").clip(0, 1)
    drawdown = wk("bottom_component_drawdown").clip(0, 1)
    ma200 = wk("bottom_component_ma200").clip(0, 1)
    fear = wk("bottom_component_fear").clip(0, 1)

    mayer = wk("mayer")
    mayer_evidence = ((1.40 - mayer) / (1.40 - 0.85)).clip(0, 1)
    rsi = wk("rsi_14")
    rsi_evidence = ((45.0 - rsi) / (45.0 - 25.0)).clip(0, 1)

    roll_low = weekly["price"].rolling(52, min_periods=26).min()
    roll_high = weekly["price"].rolling(52, min_periods=26).max()
    price_position = ((weekly["price"] - roll_low) / (roll_high - roll_low).replace(0, np.nan)).clip(0, 1)

    onchain = mvrv
    market_structure = pd.concat([drawdown, ma200, mayer_evidence], axis=1).max(axis=1, skipna=True)
    sentiment = pd.concat([fear, rsi_evidence], axis=1).max(axis=1, skipna=True)

    threshold = float(BOTTOM_CHALLENGER_THRESHOLD)
    category_votes = pd.concat([
        (onchain >= threshold).rename("onchain"),
        (market_structure >= threshold).rename("market_structure"),
        (sentiment >= threshold).rename("sentiment"),
    ], axis=1).fillna(False).sum(axis=1).astype(int)

    exceptional = (
        (pl >= threshold)
        & (price_position <= float(BOTTOM_CHALLENGER_PRICE_POSITION_MAX))
        & (category_votes >= int(BOTTOM_CHALLENGER_REQUIRED_CONFIRMING_CATEGORIES))
    ).fillna(False)

    if "bull_confirmation_flip" in out.columns:
        bull_flip = out["bull_confirmation_flip"].astype(bool).resample("W-MON").max().reindex(weekly.index).fillna(False)
    else:
        bull_flip = pd.Series(False, index=weekly.index)

    events, event_mults, episode_ids, anchors = [], [], [], []
    last_event_price = np.nan
    last_exceptional_ts = None
    episode_id = 0
    recovery_used = False
    prev_exceptional = False

    for ts in weekly.index:
        px = float(weekly.at[ts, "price"]) if pd.notna(weekly.at[ts, "price"]) else np.nan
        is_exceptional = bool(exceptional.loc[ts])
        event = "NONE"
        mult = np.nan

        if last_exceptional_ts is not None and (ts - last_exceptional_ts).days > BOTTOM_CHALLENGER_RECENT_WEEKS * 7:
            last_event_price = np.nan
            last_exceptional_ts = None
            recovery_used = False
            prev_exceptional = False

        if is_exceptional and not prev_exceptional:
            episode_id += 1
            event = "INITIAL EXCEPTIONAL ZONE"
            mult = float(BOTTOM_CHALLENGER_INITIAL_MULT)
            last_event_price = px
            last_exceptional_ts = ts
            recovery_used = False
        elif is_exceptional and np.isfinite(last_event_price) and np.isfinite(px) and px <= last_event_price * (1.0 - BOTTOM_CHALLENGER_STEP_DOWN):
            event = "LOWER CAPITULATION STAGE"
            mult = float(BOTTOM_CHALLENGER_STEP_MULT)
            last_event_price = px
            last_exceptional_ts = ts
        elif bool(bull_flip.loc[ts]) and last_exceptional_ts is not None and not recovery_used:
            if (ts - last_exceptional_ts).days <= BOTTOM_CHALLENGER_RECENT_WEEKS * 7:
                event = "RECOVERY CONFIRMATION"
                mult = float(BOTTOM_CHALLENGER_RECOVERY_MULT)
                recovery_used = True

        events.append(event)
        event_mults.append(mult)
        episode_ids.append(episode_id if last_exceptional_ts is not None else 0)
        anchors.append(last_event_price)
        prev_exceptional = is_exceptional

    weekly["bottom_challenger_pl_evidence"] = pl
    weekly["bottom_challenger_price_position"] = price_position
    weekly["bottom_challenger_onchain"] = onchain
    weekly["bottom_challenger_market_structure"] = market_structure
    weekly["bottom_challenger_sentiment"] = sentiment
    weekly["bottom_challenger_category_votes"] = category_votes
    weekly["bottom_challenger_exceptional_zone"] = exceptional.astype(bool)
    weekly["bottom_challenger_event"] = events
    weekly["bottom_challenger_event_multiplier"] = event_mults
    weekly["bottom_challenger_episode"] = episode_ids
    weekly["bottom_challenger_anchor_price"] = anchors

    state_cols = [
        "bottom_challenger_pl_evidence", "bottom_challenger_price_position",
        "bottom_challenger_onchain", "bottom_challenger_market_structure",
        "bottom_challenger_sentiment", "bottom_challenger_category_votes",
        "bottom_challenger_exceptional_zone", "bottom_challenger_episode",
        "bottom_challenger_anchor_price",
    ]
    for col in state_cols:
        out[col] = weekly[col].reindex(out.index, method="ffill")

    out["bottom_challenger_event"] = "NONE"
    out["bottom_challenger_event_multiplier"] = np.nan
    common = out.index.intersection(weekly.index)
    if len(common):
        out.loc[common, "bottom_challenger_event"] = weekly.loc[common, "bottom_challenger_event"].astype(str)
        out.loc[common, "bottom_challenger_event_multiplier"] = weekly.loc[common, "bottom_challenger_event_multiplier"]

    # Current-week decision fields: a Monday signal remains actionable until the next
    # Monday observation. This allows a user whose weekly DCA day is Tue-Sun to act
    # on the latest completed weekly signal without looking ahead. Daily backtests do
    # not use this field, preventing one weekly event from being applied every day.
    out["bottom_challenger_week_event"] = weekly["bottom_challenger_event"].reindex(out.index, method="ffill").fillna("NONE")
    out["bottom_challenger_week_multiplier"] = weekly["bottom_challenger_event_multiplier"].reindex(out.index, method="ffill")
    return out

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
    if risk_model == "Research WF Power Law":
        pl_score, fair_value, pl_residual, pl_slope, pl_intercept = walk_forward_power_law(
            result,
            params["pl_cheap"],
            params["pl_expensive"],
            min_weeks=params.get("research_pl_min_weeks", RESEARCH_PL_MIN_WEEKS),
            refit_days=params.get("research_pl_refit_days", RESEARCH_PL_REFIT_DAYS),
        )
        result["power_law_score"] = pl_score
        result["fair_value"] = fair_value
        result["power_law_residual"] = pl_residual
        result["power_law_slope"] = pl_slope
        result["power_law_intercept"] = pl_intercept
    else:
        pl_scores, fair_values, pl_residuals = [], [], []
        for timestamp, row in result.iterrows():
            score, fair_value = power_law_score(
                timestamp, float(row["price"]), params["pl_cheap"], params["pl_expensive"]
            )
            pl_scores.append(score); fair_values.append(fair_value)
            pl_residuals.append(math.log10(float(row["price"]) / fair_value) if fair_value > 0 and row["price"] > 0 else np.nan)
        result["power_law_score"] = pd.Series(pl_scores, index=result.index, dtype=float)
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
    if risk_model in {"Power Law Trend", "Research WF Power Law"}:
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

    # V5.9 Research sizing uses the causal Power Law score directly. The legacy
    # percentile/drawdown calibration is retained above for diagnostics only.
    if risk_model == "Research WF Power Law":
        # Preserve the calculated score separately, but use a neutral 0.50 fallback
        # whenever the walk-forward fit is not yet available. Missing data must never
        # be interpreted as maximum cheapness (risk 0.0).
        result["power_law_risk_calculated"] = result["power_law_score"].clip(0, 1)
        result["risk_score_source"] = np.where(
            result["power_law_risk_calculated"].notna(),
            "Walk-forward Power Law",
            "Neutral fallback",
        )
        result["risk_score"] = result["power_law_risk_calculated"].fillna(0.50).clip(0, 1)
        result["raw_risk_score"] = result["risk_score"]
        result["risk_components_available"] = result["power_law_risk_calculated"].notna().astype(int)

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

    # V5.9 R2 Context Research: display-only valuation / bottom / cycle context.
    # This does not alter risk_score or Smart DCA sizing.
    result = add_cycle_context_research(result, params)
    result = add_bottom_zone_challenger(result)

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
    if params["risk_model"] == "Research WF Power Law":
        scored_full = add_risk_indicators(df_full.copy(), params["risk_model"], params)
        df = scored_full[(scored_full.index >= params["start_date"]) & (scored_full.index <= params["end_date"])].copy()
    else:
        df = df_full[(df_full.index >= params["start_date"]) & (df_full.index <= params["end_date"])].copy()
        if not df.empty:
            df = add_risk_indicators(df, params["risk_model"], params)
    if df.empty:
        return pd.DataFrame(), {}
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
            "risk_score": risk,
            "risk_score_source": row.get("risk_score_source", "Calculated"),
            "power_law_risk_calculated": row.get("power_law_risk_calculated", row.get("power_law_score", np.nan)),
            "continuous_valuation_risk": row.get("continuous_valuation_risk", np.nan),
            "bottom_zone_score": row.get("bottom_zone_score", np.nan),
            "bottom_confidence_score": row.get("bottom_confidence_score", np.nan),
            "bottom_confidence_label": row.get("bottom_confidence_label", "n/a"),
            "weekly_bull_confirmed": row.get("weekly_bull_confirmed", False),
            "bull_age_weeks": row.get("bull_age_weeks", np.nan),
            "cycle_stage": row.get("cycle_stage", "n/a"),
            "bottom_challenger_exceptional_zone": row.get("bottom_challenger_exceptional_zone", False),
            "bottom_challenger_category_votes": row.get("bottom_challenger_category_votes", 0),
            "bottom_challenger_price_position": row.get("bottom_challenger_price_position", np.nan),
            "bottom_challenger_event": (
                row.get("bottom_challenger_week_event", "NONE") if dca_frequency == "Weekly"
                else row.get("bottom_challenger_event", "NONE")
            ),
            "bottom_challenger_event_multiplier": (
                row.get("bottom_challenger_week_multiplier", np.nan) if dca_frequency == "Weekly"
                else np.nan
            ),
            "strategy_mode": strategy_mode, "dca_multiplier": multiplier,
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


def apply_causal_budget_allocator(result_df, total_budget_aud=DEFAULT_INTELLIGENT_DCA_BUDGET_AUD, fee_pct=0.0):
    """Sequential fixed-budget allocator matching DCA Today logic.

    At each execution, only the remaining budget, remaining execution count and
    current multiplier are used. The final execution receives any residual so
    Plain and Smart finish with exactly the same total budget.
    """
    if result_df.empty or total_budget_aud <= 0:
        return pd.DataFrame(), {}
    out = result_df.copy().reset_index(drop=True)
    remaining = float(total_budget_aud)
    btc = cumulative = fees = 0.0
    replay_rows = []
    n = len(out)
    for i, row in out.iterrows():
        periods_left = n - i
        mult = float(row.get("dca_multiplier", 1.0)) if pd.notna(row.get("dca_multiplier", 1.0)) else 1.0
        allowance = remaining / max(periods_left, 1)
        contribution = remaining if periods_left == 1 else min(remaining, max(0.0, allowance * mult))
        fee = contribution * float(fee_pct)
        net = max(0.0, contribution - fee)
        price_aud = float(row["btc_price_aud"])
        btc_bought = net / price_aud if price_aud > 0 else 0.0
        btc += btc_bought; cumulative += contribution; fees += fee; remaining -= contribution
        btc_value = btc * price_aud
        replay = row.to_dict()
        replay.update({"actual_buy_aud": contribution, "btc_bought": btc_bought, "btc_held": btc,
                       "cumulative_invested_aud": cumulative, "cumulative_fees_aud": fees,
                       "btc_value_aud": btc_value, "pnl_aud": btc_value-cumulative,
                       "roi_pct": ((btc_value/cumulative-1)*100 if cumulative>0 else 0.0),
                       "avg_cost_aud": (cumulative/btc if btc>0 else 0.0)})
        replay_rows.append(replay)
    replay_df = pd.DataFrame(replay_rows)
    final = replay_df.iloc[-1]
    return replay_df, {"budget_aud": float(total_budget_aud), "total_invested_aud": float(final["cumulative_invested_aud"]),
                       "btc_held": float(final["btc_held"]), "btc_value_aud": float(final["btc_value_aud"]),
                       "avg_cost_aud": float(final["avg_cost_aud"]), "roi_pct": float(final["roi_pct"]),
                       "fees_aud": float(final["cumulative_fees_aud"])}


def apply_bottom_challenger_allocator(result_df, total_budget_aud=DEFAULT_INTELLIGENT_DCA_BUDGET_AUD, fee_pct=0.0):
    """Replay frozen R2 with the staged challenger multiplier only on event weeks."""
    if result_df.empty:
        return pd.DataFrame(), {}
    x = result_df.copy()
    base = pd.to_numeric(x["dca_multiplier"], errors="coerce").fillna(1.0)
    event = pd.to_numeric(x.get("bottom_challenger_event_multiplier"), errors="coerce")
    x["r2_dca_multiplier"] = base
    x["dca_multiplier"] = np.where(event.notna(), np.maximum(base, event), base)
    x["challenger_multiplier_applied"] = x["dca_multiplier"]
    return apply_causal_budget_allocator(x, total_budget_aud=total_budget_aud, fee_pct=fee_pct)


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

    _, plain_sm = apply_causal_budget_allocator(
        plain_raw, total_budget_aud=recent_budget,
        fee_pct=recent_params.get("fee_pct", 0.0)
    )
    _, smart_sm = apply_causal_budget_allocator(
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





# ================================================================
# Streamlit UI
# ================================================================


# Browser-local persistence: survives normal app reruns/redeploys on the same browser/device.
# CSV export remains available as a portable backup.
PERSISTENCE_KEY = "btc_dynamic_dca_v59_research_state"
SHARED_PORTFOLIO_KEY = "btc_dynamic_dca_shared_portfolio_v1"
browser_state = {}
local_storage = None

def _parse_saved_date(value, fallback):
    try:
        parsed = pd.to_datetime(value, errors="coerce")
        if pd.notna(parsed):
            return parsed.date()
    except Exception:
        pass
    return fallback

def _load_browser_state():
    if not LOCAL_STORAGE_AVAILABLE:
        return {}
    try:
        store = LocalStorage()
        raw = store.getItem(PERSISTENCE_KEY)
        if isinstance(raw, str) and raw.strip():
            data = json.loads(raw)
            return data if isinstance(data, dict) else {}
        if isinstance(raw, dict):
            return raw
    except Exception:
        return {}
    return {}

def _save_browser_state(state):
    if not LOCAL_STORAGE_AVAILABLE:
        return
    try:
        store = LocalStorage()
        store.setItem(PERSISTENCE_KEY, json.dumps(state, default=str))
    except Exception:
        pass


def _load_shared_portfolio(fallback_state=None):
    """Load portfolio data shared by V5.8.2 and V5.9 on this browser/device.

    On first use, V5.8.2 is the preferred migration source so an existing production
    portfolio automatically appears in V5.9 even if V5.9 is opened first.
    """
    fallback_state = fallback_state if isinstance(fallback_state, dict) else {}
    fallback = fallback_state.get("portfolio", {}) if isinstance(fallback_state.get("portfolio", {}), dict) else {}
    if not LOCAL_STORAGE_AVAILABLE:
        return fallback.copy()
    try:
        store = LocalStorage()
        raw = store.getItem(SHARED_PORTFOLIO_KEY)
        if isinstance(raw, str) and raw.strip():
            data = json.loads(raw)
            if isinstance(data, dict):
                return data
        elif isinstance(raw, dict):
            return raw

        # One-time migration. Prefer the existing V5.8.2 production portfolio.
        migration_candidates = []
        for legacy_key in ("btc_dynamic_dca_v58_state", "btc_dynamic_dca_v59_research_state"):
            legacy_raw = store.getItem(legacy_key)
            legacy_state = None
            if isinstance(legacy_raw, str) and legacy_raw.strip():
                try:
                    legacy_state = json.loads(legacy_raw)
                except Exception:
                    legacy_state = None
            elif isinstance(legacy_raw, dict):
                legacy_state = legacy_raw
            if isinstance(legacy_state, dict) and isinstance(legacy_state.get("portfolio"), dict):
                migration_candidates.append(legacy_state["portfolio"])
        if fallback:
            migration_candidates.append(fallback)

        for candidate in migration_candidates:
            if candidate:
                store.setItem(SHARED_PORTFOLIO_KEY, json.dumps(candidate, default=str))
                return candidate.copy()
    except Exception:
        pass
    return fallback.copy()


def _save_shared_portfolio(portfolio):
    """Persist only portfolio inputs in a cross-version shared namespace."""
    if not LOCAL_STORAGE_AVAILABLE or not isinstance(portfolio, dict):
        return
    try:
        store = LocalStorage()
        store.setItem(SHARED_PORTFOLIO_KEY, json.dumps(portfolio, default=str))
    except Exception:
        pass

browser_state = _load_browser_state()
shared_portfolio = _load_shared_portfolio(browser_state)

st.title("Bitcoin Dynamic DCA V5.9 R2 — Bottom Zone Challenger")
st.caption("Version 5.9 R2 CHALLENGER • Frozen R2 control • Staged Exceptional Bottom Zone overlay • Persistent portfolio")
st.caption("Simple three-mode app • DCA Today • DCA Backtest • My Portfolio")

# ------------------------------------------------
# Sidebar
# ------------------------------------------------

with st.sidebar:
    st.header("Mode")

    mode = st.radio(
        "Analysis Mode",
        [
            "DCA Today",
            "DCA Backtest",
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

        saved_bt = browser_state.get("backtest", {}) if isinstance(browser_state, dict) else {}
        saved_freq = saved_bt.get("frequency", "Weekly")
        dca_frequency = st.radio(
            "DCA Frequency",
            ["Daily", "Weekly"],
            horizontal=True,
            index=0 if saved_freq == "Daily" else 1,
            key="dca_backtest_frequency",
        )
        dca_base_amount_aud = DEFAULT_FIXED_DCA_AUD

        intelligent_dca_budget_aud = st.number_input(
            "Total Budget (AUD)",
            min_value=10_000.0,
            max_value=10_000_000.0,
            value=float(saved_bt.get("budget_aud", DEFAULT_INTELLIGENT_DCA_BUDGET_AUD)),
            step=10_000.0,
            format="%.0f",
            help="Plain DCA and Smart DCA both receive exactly this total budget.",
        )

        # Fixed, walk-forward-tested Smart DCA curve.
        low_risk_weight = SMART_DCA_LOW_RISK_WEIGHT
        high_risk_weight = SMART_DCA_HIGH_RISK_WEIGHT
        smart_dca_curve = SMART_DCA_POINTS

        dca_backtest_start_date = st.date_input(
            "Start Date", value=_parse_saved_date(saved_bt.get("start_date"), dt.date(2015, 1, 1)),
            min_value=dt.date(2012, 1, 1), max_value=dt.date.today(),
            format="DD/MM/YYYY", key="sidebar_dca_backtest_start_date",
        )
        dca_backtest_end_date = st.date_input(
            "End Date", value=_parse_saved_date(saved_bt.get("end_date"), dt.date.today()),
            min_value=dt.date(2012, 1, 1), max_value=dt.date.today(),
            format="DD/MM/YYYY", key="sidebar_dca_backtest_end_date",
        )
        if dca_backtest_start_date >= dca_backtest_end_date:
            st.error("Backtest Start Date must be before Backtest End Date.")

        saved_weekday = saved_bt.get("weekday", "Monday")
        weekday_names = list(day_map.keys())
        selected_day_name = st.selectbox(
            "Weekly Execution Day",
            weekday_names,
            index=weekday_names.index(saved_weekday) if saved_weekday in weekday_names else 0,
            disabled=(dca_frequency != "Weekly"),
            key="dca_backtest_weekday",
        )
        selected_day = day_map[selected_day_name]
        total_capital_aud = 0.0
        frequency = dca_frequency

        st.caption(
            "Same budget and dates. Both strategies deploy sequentially; Smart DCA uses only information available at each execution."
        )
        browser_state["backtest"] = {
            "frequency": dca_frequency,
            "budget_aud": float(intelligent_dca_budget_aud),
            "start_date": dca_backtest_start_date.isoformat(),
            "end_date": dca_backtest_end_date.isoformat(),
            "weekday": selected_day_name,
        }
        _save_browser_state(browser_state)

    elif mode == "DCA Today":
        st.header("DCA Today")

        saved_today = browser_state.get("today", {}) if isinstance(browser_state, dict) else {}
        saved_portfolio = shared_portfolio if isinstance(shared_portfolio, dict) else {}

        starting_default = float(saved_portfolio.get(
            "starting_capital_aud",
            saved_today.get("starting_capital_aud", 500_000.0)
        ))
        starting_capital_aud = st.number_input(
            "Starting Capital (AUD)",
            min_value=1_000.0, max_value=100_000_000.0,
            value=starting_default, step=10_000.0, format="%.0f",
            key="today_starting_capital",
        )

        portfolio_remaining_saved = saved_portfolio.get("capital_remaining_aud", None)
        remaining_default = saved_today.get("remaining_capital_aud", starting_capital_aud)
        if portfolio_remaining_saved is not None:
            remaining_default = portfolio_remaining_saved

        remaining_capital_aud = st.number_input(
            "Capital Remaining (AUD)",
            min_value=0.0, max_value=float(starting_capital_aud),
            value=min(float(starting_capital_aud), float(remaining_default)),
            step=5_000.0, format="%.0f",
            key="today_remaining_capital",
        )

        default_target = dt.date.today() + dt.timedelta(days=365 * 3)
        saved_target = _parse_saved_date(saved_today.get("target_date"), default_target)
        if saved_target < dt.date.today() + dt.timedelta(days=7):
            saved_target = default_target
        target_deployment_date = st.date_input(
            "Target Deployment Date",
            value=saved_target,
            min_value=dt.date.today() + dt.timedelta(days=7),
            format="DD/MM/YYYY",
            key="today_target_date",
        )

        low_risk_weight = SMART_DCA_LOW_RISK_WEIGHT
        high_risk_weight = SMART_DCA_HIGH_RISK_WEIGHT
        smart_dca_curve = SMART_DCA_POINTS

        st.caption(
            "V5.9 Research sizing: causal walk-forward Power Law risk with a moderate curve — "
            "2.00× at risk 0.00, 1.00× at risk 0.50, and 0.80× at risk 1.00."
        )

        browser_state["today"] = {
            "starting_capital_aud": float(starting_capital_aud),
            "remaining_capital_aud": float(remaining_capital_aud),
            "target_date": target_deployment_date.isoformat(),
        }
        _save_browser_state(browser_state)

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
        low_risk_weight = SMART_DCA_LOW_RISK_WEIGHT
        high_risk_weight = SMART_DCA_HIGH_RISK_WEIGHT
        smart_dca_curve = SMART_DCA_POINTS

    st.divider()
    st.caption(
        "Engine settings are fixed internally for consistency between Backtest and DCA Today."
    )

    # Fixed calibrated engine defaults. These remain in code but are no longer user-facing.
    risk_model = "Research WF Power Law"
    base_dca_pct = 0.01
    max_period_pct = 0.05
    max_sell_pct_period = min(DEFAULT_MAX_SELL_PCT_PERIOD, 0.20)
    buy_threshold = DEFAULT_BUY_THRESHOLD
    sell_risk_threshold = DEFAULT_SELL_RISK_THRESHOLD

    regime_overlay = 0.0

    valuation_strength = DEFAULT_VALUATION_STRENGTH
    min_valuation_mult = DEFAULT_MIN_VALUATION_MULT
    max_valuation_mult = min(DEFAULT_MAX_VALUATION_MULT, 2.0)
    min_cash_reserve_pct = DEFAULT_MIN_CASH_RESERVE_PCT
    min_trade_aud = DEFAULT_MIN_TRADE_AUD
    fee_pct = DEFAULT_FEE_PCT
    min_days_between_sales = DEFAULT_MIN_DAYS_BETWEEN_SALES
    min_risk_components = DEFAULT_MIN_RISK_COMPONENTS
    require_weak_trend_for_sell = False

    trend_er_period = DEFAULT_TREND_ER_PERIOD
    trend_fast = DEFAULT_TREND_FAST
    trend_slow = DEFAULT_TREND_SLOW
    trend_range_period = DEFAULT_TREND_RANGE_PERIOD
    trend_band_mult = DEFAULT_TREND_BAND_MULT
    trend_buy_bull = DEFAULT_TREND_BUY_BULL
    trend_buy_neutral = DEFAULT_TREND_BUY_NEUTRAL
    trend_buy_bear = DEFAULT_TREND_BUY_BEAR
    trend_sell_bull = DEFAULT_TREND_SELL_BULL
    trend_sell_neutral = DEFAULT_TREND_SELL_NEUTRAL
    trend_sell_bear = DEFAULT_TREND_SELL_BEAR


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
    "research_pl_min_weeks": RESEARCH_PL_MIN_WEEKS,
    "research_pl_refit_days": RESEARCH_PL_REFIT_DAYS,
    "total_capital_aud": total_capital_aud,
    "base_dca_pct": base_dca_pct,
    "pressure_strength": 0.0,
    "max_period_pct": max_period_pct,
    "min_cash_reserve_pct": min_cash_reserve_pct,
    "sell_threshold": 0.0,
    "max_sell_pct_period": max_sell_pct_period,
    "fee_pct": fee_pct,
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

# ================================================================
# DCA Backtest
# ================================================================

if mode == "DCA Backtest":

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
        research_fetch_start = min(pd.Timestamp(params["start_date"], tz="UTC") if pd.Timestamp(params["start_date"]).tzinfo is None else pd.Timestamp(params["start_date"]).tz_convert("UTC"), RESEARCH_PL_HISTORY_START)
        df_full = fetch_btc_history(research_fetch_start, params["end_date"])
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

    with st.spinner("Running causal equal-budget Plain DCA vs V5.9 Research Smart DCA..."):
        plain_raw, _ = simulate_dca_backtest(
            df_full, params, DEFAULT_FIXED_DCA_AUD, dca_frequency, "Plain DCA"
        )
        smart_raw, _ = simulate_dca_backtest(
            df_full, params, DEFAULT_FIXED_DCA_AUD, dca_frequency,
            "Risk-Scaled DCA", risk_curve=smart_dca_curve
        )

        capital_target = float(intelligent_dca_budget_aud)
        plain_df, plain_sm = apply_causal_budget_allocator(
            plain_raw, total_budget_aud=capital_target,
            fee_pct=params.get("fee_pct", 0.0)
        )
        smart_df, smart_sm = apply_causal_budget_allocator(
            smart_raw, total_budget_aud=capital_target,
            fee_pct=params.get("fee_pct", 0.0)
        )
        challenger_df, challenger_sm = apply_bottom_challenger_allocator(
            smart_raw, total_budget_aud=capital_target,
            fee_pct=params.get("fee_pct", 0.0)
        )
        recent_check = validate_smart_dca_recent_period(
            df_full, params, dca_frequency, capital_target, recent_fraction=0.30,
            risk_curve=smart_dca_curve
        )

    if not plain_sm or not smart_sm or not challenger_sm:
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
    challenger_vs_r2 = (
        (challenger_sm["btc_held"] / smart_sm["btc_held"] - 1.0) * 100.0
        if smart_sm["btc_held"] > 0 else np.nan
    )
    challenger_vs_plain = (
        (challenger_sm["btc_held"] / plain_sm["btc_held"] - 1.0) * 100.0
        if plain_sm["btc_held"] > 0 else np.nan
    )
    challenger_events = int((challenger_df.get("bottom_challenger_event", pd.Series(dtype=str)) != "NONE").sum())

    st.header("Simple DCA Backtest")
    st.caption(
        f"Same A${capital_target:,.0f} budget • {dca_frequency} • "
        f"{dca_backtest_start_date.strftime('%d/%m/%Y')} to "
        f"{dca_backtest_end_date.strftime('%d/%m/%Y')}"
    )

    p1, p2, p3 = st.columns(3)
    with p1:
        st.subheader("Plain DCA")
        st.metric("BTC Accumulated", f"{plain_sm['btc_held']:.6f}")
        st.metric("Average Cost", f"A${plain_sm['avg_cost_aud']:,.0f}")
        st.metric("Ending Value", f"A${plain_sm['btc_value_aud']:,.0f}")
        st.metric("ROI", f"{plain_sm['roi_pct']:+.2f}%")

    with p2:
        st.subheader("Frozen R2")
        st.metric("BTC Accumulated", f"{smart_sm['btc_held']:.6f}", delta=f"{btc_adv:+.2f}% vs Plain")
        st.metric("Average Cost", f"A${smart_sm['avg_cost_aud']:,.0f}")
        st.metric("Ending Value", f"A${smart_sm['btc_value_aud']:,.0f}")
        st.metric("ROI", f"{smart_sm['roi_pct']:+.2f}%")

    with p3:
        st.subheader("Bottom Challenger")
        st.metric("BTC Accumulated", f"{challenger_sm['btc_held']:.6f}", delta=f"{challenger_vs_r2:+.2f}% vs R2")
        st.metric("Average Cost", f"A${challenger_sm['avg_cost_aud']:,.0f}")
        st.metric("Ending Value", f"A${challenger_sm['btc_value_aud']:,.0f}")
        st.metric("Staged Events", f"{challenger_events}")

    st.subheader("Verdict")
    if challenger_vs_r2 > 0:
        st.success(
            f"Bottom Challenger accumulated {challenger_vs_r2:+.2f}% more BTC than frozen R2 "
            f"and {challenger_vs_plain:+.2f}% versus Plain DCA for the same A${capital_target:,.0f} budget."
        )
    elif challenger_vs_r2 < 0:
        st.warning(
            f"Bottom Challenger accumulated {abs(challenger_vs_r2):.2f}% less BTC than frozen R2 in this period. "
            "R2 remains the control; the challenger is not promoted automatically."
        )
    else:
        st.info("Bottom Challenger and frozen R2 accumulated the same BTC in this period.")
    st.caption(
        "Research-only overlay: 3x initial exceptional entry • 4x each new ≥15% lower capitulation stage "
        "while confluence remains exceptional • 3x recent recovery confirmation • no fixed reserve • no all-in."
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
            "date", "price_usd", "risk_score", "continuous_valuation_risk",
            "bottom_challenger_exceptional_zone", "bottom_challenger_category_votes",
            "bottom_challenger_price_position", "bottom_challenger_event",
            "r2_dca_multiplier", "challenger_multiplier_applied",
            "actual_buy_aud", "btc_bought", "btc_held",
            "cumulative_invested_aud", "avg_cost_aud"
        ]
        challenger_detail = challenger_df[[c for c in detail_cols if c in challenger_df.columns]].copy()
        st.dataframe(challenger_detail.tail(250), width="stretch", hide_index=True)

    plain_csv = plain_df.to_csv(index=False).encode("utf-8")
    smart_csv = smart_df.to_csv(index=False).encode("utf-8")
    challenger_csv = challenger_df.to_csv(index=False).encode("utf-8")
    d1, d2, d3 = st.columns(3)
    d1.download_button(
        "Download Plain DCA CSV", plain_csv,
        file_name="btc_v5_1_plain_dca.csv", mime="text/csv"
    )
    d2.download_button(
        "Download Frozen R2 CSV", smart_csv,
        file_name="btc_v5_9_r2_frozen.csv", mime="text/csv"
    )
    d3.download_button(
        "Download Bottom Challenger CSV", challenger_csv,
        file_name="btc_v5_9_r2_bottom_challenger.csv", mime="text/csv"
    )


# ================================================================

# ================================================================
# DCA Today
# ================================================================

elif mode == "DCA Today":
    now_utc = dt.datetime.now(timezone.utc)
    # V5.9 Research Power Law is expanding from the fixed research-history start.
    # This makes today's fit consistent with historical backtests regardless of the
    # selected DCA start date.
    lookback_start = RESEARCH_PL_HISTORY_START.to_pydatetime()

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
    current_display_risk = float(latest.get("continuous_valuation_risk", np.nan))
    current_bottom_zone = float(latest.get("bottom_zone_score", np.nan))
    current_bottom_confidence = float(latest.get("bottom_confidence_score", np.nan))
    current_bottom_label = str(latest.get("bottom_confidence_label", "n/a"))
    current_bull = bool(latest.get("weekly_bull_confirmed", False))
    current_bull_age = float(latest.get("bull_age_weeks", np.nan))
    current_cycle_stage = str(latest.get("cycle_stage", "BEAR / UNCONFIRMED"))
    current_challenger_zone = bool(latest.get("bottom_challenger_exceptional_zone", False))
    current_challenger_votes = int(latest.get("bottom_challenger_category_votes", 0) or 0)
    current_challenger_price_position = float(latest.get("bottom_challenger_price_position", np.nan))
    current_challenger_event = str(latest.get("bottom_challenger_week_event", latest.get("bottom_challenger_event", "NONE")))
    current_challenger_event_mult = float(latest.get("bottom_challenger_week_multiplier", latest.get("bottom_challenger_event_multiplier", np.nan)))
    current_weekly_ma50 = float(latest.get("weekly_ma50", np.nan))
    current_weekly_ma200 = float(latest.get("weekly_ma200", np.nan))

    # V5.9 R2 visibility layer: preserve the bounded 0..1 sizing score, but also
    # expose the underlying Power Law residual so Risk 0 / Risk 1 do not hide
    # how far valuation sits beyond the clamp boundary. This is DISPLAY ONLY.
    current_pl_residual = float(latest.get("power_law_residual", np.nan))
    current_pl_fair_usd = float(latest.get("fair_value", np.nan))
    current_pl_slope = float(latest.get("power_law_slope", np.nan))
    current_pl_intercept = float(latest.get("power_law_intercept", np.nan))
    pl_cheap_threshold = float(params.get("pl_cheap", DEFAULT_PL_CHEAP))
    pl_expensive_threshold = float(params.get("pl_expensive", DEFAULT_PL_EXPENSIVE))
    pl_span = pl_expensive_threshold - pl_cheap_threshold
    unclipped_pl_position = (
        (current_pl_residual - pl_cheap_threshold) / pl_span
        if np.isfinite(current_pl_residual) and pl_span > 0 else np.nan
    )
    price_vs_pl_fair_pct = (
        (10.0 ** current_pl_residual - 1.0) * 100.0
        if np.isfinite(current_pl_residual) else np.nan
    )
    risk0_boundary_ratio = 10.0 ** pl_cheap_threshold
    risk1_boundary_ratio = 10.0 ** pl_expensive_threshold
    if np.isfinite(current_pl_residual) and current_pl_residual <= pl_cheap_threshold:
        boundary_depth_pct = (1.0 - 10.0 ** (current_pl_residual - pl_cheap_threshold)) * 100.0
        boundary_depth_label = "Below Risk-0 boundary"
        boundary_depth_text = f"{boundary_depth_pct:.1f}% deeper"
    elif np.isfinite(current_pl_residual) and current_pl_residual >= pl_expensive_threshold:
        boundary_depth_pct = (10.0 ** (current_pl_residual - pl_expensive_threshold) - 1.0) * 100.0
        boundary_depth_label = "Above Risk-1 boundary"
        boundary_depth_text = f"{boundary_depth_pct:.1f}% higher"
    elif np.isfinite(current_pl_residual):
        boundary_depth_pct = np.nan
        boundary_depth_label = "Clamp status"
        boundary_depth_text = "Inside 0–1 range"
    else:
        boundary_depth_pct = np.nan
        boundary_depth_label = "Clamp status"
        boundary_depth_text = "n/a"

    current_price_usd = float(latest["price"])
    usd_per_aud = float(latest["usd_per_aud"]) if pd.notna(latest.get("usd_per_aud", np.nan)) else np.nan
    historical_price_aud = current_price_usd / usd_per_aud if np.isfinite(usd_per_aud) and usd_per_aud > 0 else np.nan

    # Display a fresh spot price where available. The risk engine continues to use
    # the historical/closed data above, so a live quote cannot change the risk score.
    live_price_aud = fetch_live_btc_aud()
    current_price_aud = live_price_aud if np.isfinite(live_price_aud) else historical_price_aud
    price_is_live = bool(np.isfinite(live_price_aud))

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
    # V5.9 Research: rarity is decision-support context only. Risk Score alone controls sizing.
    effective_weight = risk_weight

    days_remaining = max((target_deployment_date - dt.date.today()).days, 7)
    weeks_remaining = max(days_remaining / 7.0, 1.0)

    opportunity = lower_risk_opportunity_stats(
        rarity_source, current_risk, min(weeks_remaining, 156.0)
    )

    normal_weekly_allowance = float(remaining_capital_aud) / weeks_remaining
    recommended_buy = min(
        float(remaining_capital_aud),
        max(0.0, normal_weekly_allowance * risk_weight),
    )
    challenger_weight = (
        max(risk_weight, current_challenger_event_mult)
        if np.isfinite(current_challenger_event_mult) else risk_weight
    )
    challenger_recommended_buy = min(
        float(remaining_capital_aud),
        max(0.0, normal_weekly_allowance * challenger_weight),
    )

    # Better-entry probability is informational only in V5.9 Research.
    # It never overrides the Risk Score sizing curve.
    extreme_all_in_eligible = False

    risk_label = (
        "VERY LOW" if current_risk <= 0.20 else
        "LOW" if current_risk <= 0.40 else
        "NEUTRAL" if current_risk <= 0.60 else
        "HIGH" if current_risk <= 0.80 else
        "VERY HIGH"
    )
    deployed = max(float(starting_capital_aud) - float(remaining_capital_aud), 0.0)
    remaining_after = max(float(remaining_capital_aud) - challenger_recommended_buy, 0.0)

    st.header("DCA Today")
    st.caption(
        "Frozen R2 remains the control. The research challenger can temporarily raise the weekly multiplier "
        "only on explicit staged Exceptional Bottom Zone events; no fixed reserve or automatic all-in."
    )

    a, b, c, d = st.columns(4)
    a.metric(
        "BTC Valuation Risk",
        format_continuous_risk(current_display_risk, current_price_usd),
        risk_label,
        help=(
            "Continuous display risk. 0.000 is reserved for a BTC price of zero. "
            f"The frozen R2 sizing score is {current_risk:.3f} and still controls the DCA multiplier."
        ),
    )
    b.metric(
        "BTC Price",
        "n/a" if not np.isfinite(current_price_aud) else f"A${current_price_aud:,.0f}",
        help="Live BTC/AUD spot quote (60-second cache) when available; otherwise latest historical BTC/AUD. Risk uses closed historical data."
    )
    c.metric("Opportunity Rarity", rarity["rarity_label"])
    if opportunity["cycles_used"] >= 1:
        d.metric(
            "Better Entry Evidence",
            f"{opportunity['cycle_successes']} of {opportunity['cycles_used']} cycles",
            help=(
                "Number of comparable BTC cycles that later produced a materially lower Risk Score. "
                "Each of the current + previous two cycles contributes at most one independent analogue. "
                "This is limited historical evidence, not a precise probability."
            ),
        )
    else:
        d.metric("Better Entry Evidence", "n/a")

    st.caption(
        ("BTC price: live BTC/AUD spot quote" if price_is_live else "BTC price: latest historical BTC/AUD fallback")
        + f" • checked {now_utc.strftime('%d/%m/%y %H:%M UTC')}. "
        "The valuation Risk Score remains based on closed historical data."
    )

    st.subheader("Cycle / Bottom Intelligence — Research Context")
    q1, q2, q3, q4 = st.columns(4)
    q1.metric(
        "Exceptional Bottom Zone",
        "ACTIVE" if current_challenger_zone else "INACTIVE",
        current_challenger_event if current_challenger_event != "NONE" else f"{current_challenger_votes}/3 confirming categories",
        help=(
            "Research challenger. Requires deep causal Power-Law valuation, BTC in the lowest 20% of its trailing "
            "52-week range, and at least two additional strongly-stressed categories."
        ),
    )
    q2.metric(
        "Weekly Trend",
        "BULL CONFIRMED" if current_bull else "UNCONFIRMED / BEAR",
        help=(
            "Research proxy for your weekly yellow/bull transition: 3 consecutive weekly closes above "
            "the causal 50-week moving average. A 3-week break below resets the bull state."
        ),
    )
    q3.metric(
        "Bull Age",
        "n/a" if not np.isfinite(current_bull_age) else f"{int(current_bull_age)} weeks",
        help="Weeks since the current weekly bull confirmation. Research context only; no DCA adjustment.",
    )
    q4.metric(
        "Cycle Stage",
        current_cycle_stage,
        help="Display classification from bull age. It is not hard-coded into the R2 sizing curve.",
    )

    ma50_text = "n/a" if not np.isfinite(current_weekly_ma50) else f"US${current_weekly_ma50:,.0f}"
    ma200_text = "n/a" if not np.isfinite(current_weekly_ma200) else f"US${current_weekly_ma200:,.0f}"
    zone_text = "n/a" if not np.isfinite(current_bottom_zone) else f"{current_bottom_zone:.0f}/100"
    st.caption(
        f"Current bottom-zone evidence: {zone_text} • 50-week MA: {ma50_text} • 200-week MA: {ma200_text}. "
        "Exceptional Bottom Zone is a causal research signal, not a guarantee that the exact cycle low is in."
    )

    st.info(
        f"Frozen R2: Risk {current_risk:.3f} → {risk_weight:.2f}×. "
        f"Bottom Challenger today: {challenger_weight:.2f}×"
        + (f" ({current_challenger_event})" if current_challenger_event != "NONE" else " (no staged event today)")
        + ". Production V5.8.2 and the R2 control are unchanged."
    )

    with st.expander("📅 Halving Cycle — 500 / 500 Theory", expanded=False):
        current_halving = pd.Timestamp("2024-04-20")
        current_day = pd.Timestamp(now_utc.date())
        days_from_halving = int((current_day - current_halving).days)
        pre500 = current_halving - pd.Timedelta(days=500)
        post500 = current_halving + pd.Timedelta(days=500)

        if days_from_halving < -500:
            theory_status = "CASH / WAITING — before the historical −500-day accumulation window"
        elif days_from_halving < 0:
            theory_status = "ACCUMULATION WINDOW — within 500 days before the halving"
        elif days_from_halving <= 500:
            theory_status = "HOLD / EXPANSION — between halving day and +500 days"
        else:
            theory_status = "PAST THE HISTORICAL +500-DAY EXIT MARKER"

        h1, h2, h3, h4 = st.columns(4)
        h1.metric("Current Halving", current_halving.strftime("%d %b %Y"))
        h2.metric("Days From Halving", f"{days_from_halving:+,} days")
        h3.metric("−500 Day Marker", pre500.strftime("%d %b %Y"))
        h4.metric("+500 Day Marker", post500.strftime("%d %b %Y"))
        st.markdown(f"**Theory status today:** {theory_status}")

        # Future-cycle planning markers. Bitcoin halvings occur at block-height milestones,
        # not fixed calendar dates, so these dates are intentionally approximate and should
        # be refreshed as the network approaches block 1,050,000.
        next_halving_est = pd.Timestamp("2028-04-12")
        next_pre500 = next_halving_est - pd.Timedelta(days=500)
        next_post500 = next_halving_est + pd.Timedelta(days=500)
        st.markdown("**Next halving cycle — approximate planning dates**")
        n1, n2, n3 = st.columns(3)
        n1.metric("Approx. −500 Accumulation Start", next_pre500.strftime("%d %b %Y"))
        n2.metric("Approx. 2028 Halving", next_halving_est.strftime("%d %b %Y"))
        n3.metric("Approx. +500 Marker", next_post500.strftime("%d %b %Y"))
        st.caption(
            "The next Bitcoin halving is currently estimated for roughly 10–13 April 2028. "
            "The app uses 12 April 2028 as a neutral planning estimate, giving approximate ±500-day markers. "
            "The actual halving date will move with block production speed."
        )

        st.markdown(
            "**Theory:** accumulate from about 500 days before a Bitcoin halving, hold through the halving, "
            "consider the period around 500 days after the halving as a historical take-profit zone, then wait "
            "for the next accumulation window. This panel is research context only and does not change R2 or "
            "trigger an automatic sale."
        )

        # Empirical timing check using only BTC prices available in the app. A broad ±900-day
        # window is used to locate the preceding bear-market low and the following cycle high.
        px_hist = df_today[["price"]].copy()
        px_hist.index = pd.to_datetime(px_hist.index).tz_localize(None) if getattr(pd.to_datetime(px_hist.index), "tz", None) is not None else pd.to_datetime(px_hist.index)
        px_hist["price"] = pd.to_numeric(px_hist["price"], errors="coerce")
        px_hist = px_hist.dropna(subset=["price"])
        cycle_rows = []
        for halving_date in [pd.Timestamp("2016-07-09"), pd.Timestamp("2020-05-11"), pd.Timestamp("2024-04-20")]:
            before = px_hist[(px_hist.index >= halving_date - pd.Timedelta(days=900)) & (px_hist.index <= halving_date)]
            after_end = min(halving_date + pd.Timedelta(days=900), current_day)
            after = px_hist[(px_hist.index >= halving_date) & (px_hist.index <= after_end)]
            if before.empty or after.empty:
                continue
            low_date = before["price"].idxmin()
            high_date = after["price"].idxmax()
            cycle_rows.append({
                "Halving": halving_date.strftime("%d %b %Y"),
                "Theory BUY (−500d)": (halving_date - pd.Timedelta(days=500)).strftime("%d %b %Y"),
                "Theory SELL (+500d)": (halving_date + pd.Timedelta(days=500)).strftime("%d %b %Y"),
                "Actual prior low": low_date.strftime("%d %b %Y"),
                "Low vs halving": f"{int((low_date-halving_date).days):+d} d",
                "Actual post-halving high": high_date.strftime("%d %b %Y"),
                "High vs halving": f"{int((high_date-halving_date).days):+d} d",
                "Status": "cycle-to-date" if halving_date.year == 2024 else "historical",
            })
        if cycle_rows:
            cycle_table = pd.DataFrame(cycle_rows)
            future_row = pd.DataFrame([{
                "Halving": "≈ " + next_halving_est.strftime("%d %b %Y"),
                "Theory BUY (−500d)": "≈ " + next_pre500.strftime("%d %b %Y"),
                "Theory SELL (+500d)": "≈ " + next_post500.strftime("%d %b %Y"),
                "Actual prior low": "future / unknown",
                "Low vs halving": "—",
                "Actual post-halving high": "future / unknown",
                "High vs halving": "—",
                "Status": "future estimate",
            }])
            cycle_table = pd.concat([cycle_table, future_row], ignore_index=True)
            st.dataframe(cycle_table, width="stretch", hide_index=True)
            st.caption(
                "Theory BUY and SELL dates are the simple −500/+500-day rule; they are shown explicitly for each cycle. "
                "The 2024 row is cycle-to-date and can change. The 2028 BUY/Halving/SELL dates are approximate planning dates; "
                "the actual halving occurs at a block-height milestone. "
                "Historical low/high searches use a broad ±900-day window so we can test whether the simple ±500-day "
                "idea roughly aligns with actual macro turning points rather than assuming it does."
            )

        st.warning(
            "Bitcoin has only a small number of independent halving cycles. Spot ETFs, institutional flows, "
            "market maturation and diminishing percentage returns may shift or weaken historical cycle timing. "
            "Do not treat ±500 days as a guaranteed bottom or top."
        )

    st.subheader("Power Law Risk Visibility")
    v1, v2, v3, v4 = st.columns(4)
    v1.metric(
        "R2 Sizing Risk",
        f"{current_risk:.3f}",
        help="Frozen bounded 0–1 R2 score used for DCA sizing. This may clamp at 0 or 1; the continuous valuation risk above does not.",
    )
    v2.metric(
        "Unclipped PL Position",
        "n/a" if not np.isfinite(unclipped_pl_position) else f"{unclipped_pl_position:.3f}",
        help=(
            "Same Power Law position before clamping. 0.000 is the Risk-0 boundary, "
            "1.000 is the Risk-1 boundary; negative values show how far below Risk 0 BTC sits."
        ),
    )
    v3.metric(
        "Price vs PL Fair Value",
        "n/a" if not np.isfinite(price_vs_pl_fair_pct) else f"{price_vs_pl_fair_pct:+.1f}%",
        help="Closed-data BTC price relative to the causal walk-forward Power Law fair value.",
    )
    v4.metric(
        boundary_depth_label,
        boundary_depth_text,
        help="Shows depth beyond a clamp boundary without increasing the DCA multiplier beyond its fixed cap.",
    )

    fair_text = "n/a" if not np.isfinite(current_pl_fair_usd) else f"US${current_pl_fair_usd:,.0f}"
    st.caption(
        f"Walk-forward PL fair value: {fair_text}. Risk 0 begins at about "
        f"{risk0_boundary_ratio * 100:.1f}% of fair value; Risk 1 begins at about "
        f"{risk1_boundary_ratio * 100:.1f}% of fair value. The R2 strategy is unchanged: "
        f"maximum DCA weight remains {interpolate(smart_dca_curve, 0.0):.2f}×."
    )

    if np.isfinite(current_pl_residual):
        view_min = min(-0.50, current_pl_residual - 0.08)
        view_max = max(0.50, current_pl_residual + 0.08)
        pl_fig = go.Figure()
        pl_fig.add_scatter(
            x=[current_pl_residual], y=["Current"], mode="markers+text",
            text=[f"Residual {current_pl_residual:+.3f}"], textposition="top center",
            marker={"size": 14},
            hovertemplate=(
                f"Current residual: {current_pl_residual:+.4f}<br>"
                f"Unclipped position: {unclipped_pl_position:+.3f}<br>"
                f"Price vs fair value: {price_vs_pl_fair_pct:+.1f}%<extra></extra>"
            ),
        )
        pl_fig.add_vline(x=pl_cheap_threshold, line_dash="dash", annotation_text="Risk 0 boundary")
        pl_fig.add_vline(x=0.0, line_dash="dot", annotation_text="PL fair value")
        pl_fig.add_vline(x=pl_expensive_threshold, line_dash="dash", annotation_text="Risk 1 boundary")
        pl_fig.update_layout(
            xaxis_title="Power Law residual (log10 price ÷ fair value)",
            yaxis_title="",
            yaxis={"showticklabels": False},
            xaxis={"range": [view_min, view_max]},
            height=230,
            margin=dict(l=20, r=20, t=45, b=45),
            showlegend=False,
        )
        st.plotly_chart(pl_fig, width="stretch")
        st.caption(
            "This chart is visibility only. A displayed Risk of 0 can represent anything below the left boundary; "
            "the marker and unclipped position show how deep into that zone BTC actually is."
        )

    with st.expander("How the signals work", expanded=False):
        st.markdown(
            "**Risk Score = buy sizing.** The Smart DCA amount is determined by the BTC Risk Score "
            "using the fixed walk-forward-tested curve; the Risk Score itself is not cycle-adjusted.\n\n"
            "**Opportunity Rarity = cycle-based context.** It compares today's Risk Score with comparable "
            "periods in the current BTC halving cycle plus the previous two cycles.\n\n"
            "**Better Entry Evidence = cycle-based context.** It asks whether comparable cycle situations "
            "later produced a materially lower Risk Score.\n\n"
            "**Historical Weekly Risk Distribution = descriptive only.** It shows how often each Risk Score "
            "range occurred historically and is not cycle-adjusted.\n\n"
            "**Continuous Valuation Risk = visibility.** It is a smooth Power-Law-relative display score; "
            "0.000 is reserved for a zero BTC price. It does not replace the frozen R2 sizing score.\n\n"
            "**Exceptional Bottom Zone = challenger trigger.** Deep Power-Law valuation and a low trailing-year price "
            "position are mandatory; at least two independent confirming categories must also be strongly stressed.\n\n"
            "**Staged deployment = 3x / 4x / 3x.** Initial exceptional entry uses 3x, each new ≥15% lower "
            "capitulation stage while confluence remains exceptional uses 4x, and a recent recovery confirmation uses 3x.\n\n"
            "**Bull Age / Cycle Stage = context.** They describe how long the current confirmed weekly bull trend "
            "has been active and do not alter sizing.\n\n"
            "Opportunity Rarity and Better Entry Evidence remain informational only. Bull Age remains context only. "
            "Only an explicit Bottom Challenger staged event can raise the research-challenger purchase above frozen R2."
        )

    with st.expander("Opportunity Rarity Guide", expanded=False):
        rarity_guide = pd.DataFrame([
            ["EXTREME", "≤ 5%", "Exceptionally rare low-risk opportunity"],
            ["VERY HIGH", "> 5–10%", "Very rare opportunity"],
            ["HIGH", "> 10–20%", "Rare / attractive opportunity"],
            ["ABOVE AVERAGE", "> 20–35%", "Better than usual"],
            ["NORMAL", "> 35–60%", "Fairly typical opportunity"],
            ["COMMON", "> 60%", "This risk level or lower occurs frequently"],
        ], columns=["Opportunity Rarity", "Historical frequency", "Interpretation"])
        rarity_guide["Current"] = rarity_guide["Opportunity Rarity"].apply(
            lambda x: "← CURRENT" if x == rarity["rarity_label"] else ""
        )
        st.dataframe(rarity_guide, width="stretch", hide_index=True)
        st.caption(
            "V5.9 R2 uses Opportunity Rarity for context only. It does not increase or reduce the recommended buy."
        )

    st.subheader("DCA TODAY — R2 CONTROL vs BOTTOM CHALLENGER")
    y1, y2 = st.columns(2)
    y1.metric("Frozen R2 Buy", f"A${recommended_buy:,.0f}", help=f"{risk_weight:.2f}× normal weekly allowance")
    y2.metric(
        "Bottom Challenger Buy", f"A${challenger_recommended_buy:,.0f}",
        delta=(f"A${challenger_recommended_buy-recommended_buy:+,.0f} vs R2" if challenger_recommended_buy != recommended_buy else "same as R2"),
        help=f"{challenger_weight:.2f}× normal weekly allowance; staged events only"
    )

    x1, x2, x3 = st.columns(3)
    x1.metric("Normal Weekly Allowance", f"A${normal_weekly_allowance:,.0f}")
    x2.metric("Capital Remaining After Challenger Buy", f"A${remaining_after:,.0f}")
    x3.metric("Already Deployed", f"A${deployed:,.0f}")

    pos_text = "n/a" if not np.isfinite(current_challenger_price_position) else f"{current_challenger_price_position*100:.1f}%"
    st.caption(
        f"Bottom Challenger: {'EXCEPTIONAL ZONE ACTIVE' if current_challenger_zone else 'no exceptional zone'} • "
        f"confirming categories {current_challenger_votes}/3 • trailing-year price position {pos_text}. "
        "No fixed reserve and no automatic all-in."
    )

    st.subheader("Historical Weekly Risk Distribution")
    occurrence = risk_occurrence_table(rarity_source)
    fig_occurrence = go.Figure()
    fig_occurrence.add_bar(
        x=occurrence["Risk range"],
        y=occurrence["Percent"],
        customdata=occurrence[["Weeks"]],
        hovertemplate=(
            "Risk %{x}<br>%{y:.1f}% of weekly observations"
            "<br>%{customdata[0]} weeks"
            "<extra></extra>"
        ),
    )
    fig_occurrence.update_layout(
        xaxis_title="BTC Risk Range",
        yaxis_title="Historical Weekly Frequency (%)",
        margin=dict(l=20, r=20, t=20, b=20),
        height=380,
    )
    st.plotly_chart(fig_occurrence, width="stretch")
    st.caption(
        f"Current risk {current_risk:.3f}. This chart is descriptive: it shows the percentage "
        "of weekly observations that fell inside each Risk Score range. It does NOT assign "
        "Opportunity Rarity to individual buckets. Opportunity Rarity is calculated separately "
        "as how often comparable cycle-phase observations were at or below today's risk "
        f"(currently: {rarity['rarity_label']})."
    )

    with st.expander("Chance of a lower-risk entry — current + previous 2 cycles", expanded=False):
        if opportunity["samples"] >= 1:
            st.write(
                f"Independent cycle analogues: **{opportunity['cycles_used']}** "
                f"(evidence: **{opportunity['evidence_label']}**). "
                f"Each cycle contributes at most one closest match within about "
                f"±{opportunity['tolerance']:.3f} risk and a comparable cycle phase."
            )
            st.write(
                f"Materially-lower outcome occurred in **{opportunity['cycle_successes']} of "
                f"{opportunity['cycles_used']}** comparable cycle analogues."
            )
            if np.isfinite(opportunity["chance_any_lower"]):
                st.write(f"Any lower risk: **{100.0 * opportunity['chance_any_lower']:.0f}%**")
            if np.isfinite(opportunity["chance_materially_lower"]):
                st.write(
                    f"Materially lower risk (≤ {opportunity['material_threshold']:.3f}): "
                    f"**{opportunity['cycle_successes']} of {opportunity['cycles_used']} cycles**"
                )
            st.write(
                "Historical chance of reaching risk ≤0.05 / ≤0.02 / ≤0.01: "
                f"**{100.0 * opportunity['chance_le_005']:.0f}% / "
                f"{100.0 * opportunity['chance_le_002']:.0f}% / "
                f"{100.0 * opportunity['chance_le_001']:.0f}%**"
            )
            st.caption(
                "This uses at most one representative analogue per BTC cycle to avoid counting "
                "overlapping weeks as independent evidence. With only up to three cycles, treat "
                "the percentage as a historical decision-support rate, not a precise probability."
            )
        else:
            st.write("Not enough comparable historical observations for a useful estimate.")

    if current_risk <= 0.40:
        st.success(
            f"BTC valuation is {risk_label.lower()} and opportunity rarity is {rarity['rarity_label'].lower()}. "
            f"The fixed Smart DCA risk weight is {risk_weight:.2f}×. Opportunity Rarity is informational only."
        )
    elif current_risk >= 0.60:
        st.info(
            f"BTC valuation is {risk_label.lower()} and opportunity rarity is {rarity['rarity_label'].lower()}. "
            f"The model is preserving capital with a Risk Score weight of {risk_weight:.2f}×."
        )
    else:
        st.info(
            f"BTC valuation is neutral and opportunity rarity is {rarity['rarity_label'].lower()}. "
            f"The Risk Score allocation weight is {risk_weight:.2f}×."
        )

    with st.expander("How this amount is calculated", expanded=False):
        st.write(
            "Normal weekly allowance = capital remaining ÷ weeks remaining. "
            "That allowance is multiplied only by the fixed Smart DCA weight from today's Risk Score, "
            "then capped at remaining capital."
        )
        st.write(
            f"A${remaining_capital_aud:,.0f} ÷ {weeks_remaining:.1f} weeks "
            f"× {risk_weight:.2f} Risk Score weight "
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
        "Portfolio entries are saved automatically in this browser/device when browser storage is available. "
        "CSV export remains a portable backup for another device or browser."
    )

    portfolio_cols = [
        "Date",
        "Asset",
        "AUD Spent",
        "Brokerage / Fee AUD",
        "Units / BTC Received",
        "BTC AUD Price",
    ]

    saved_portfolio = shared_portfolio if isinstance(shared_portfolio, dict) else {}
    saved_rows = saved_portfolio.get("rows", [])
    portfolio_df = pd.DataFrame(saved_rows) if isinstance(saved_rows, list) and saved_rows else pd.DataFrame(columns=portfolio_cols)
    for col in portfolio_cols:
        if col not in portfolio_df.columns:
            portfolio_df[col] = "" if col in ("Date", "Asset") else 0.0
    portfolio_df = portfolio_df[portfolio_cols]

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
        value=float(saved_portfolio.get(
            "starting_capital_aud",
            st.session_state.get("portfolio_starting_capital", 500000.0)
        )),
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
        },
        column_order=[
            "Date",
            "Asset",
            "AUD Spent",
            "Brokerage / Fee AUD",
            "Units / BTC Received",
        ],
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
            if btc_lookup is not None and not btc_lookup.empty and fx_lookup is not None and not fx_lookup.empty:
                lookup = btc_lookup[["price"]].copy()

                # Normalize both BTC and FX lookup keys to timezone-naive midnight
                # Timestamps. This avoids comparing UTC DatetimeIndex values with
                # plain Python date objects.
                lookup_dates = pd.to_datetime(lookup.index, utc=True).tz_convert(None).normalize()
                lookup["lookup_date"] = lookup_dates

                fx_series = pd.Series(fx_lookup, dtype=float)
                fx_series.index = (
                    pd.to_datetime(fx_series.index, utc=True)
                    .tz_convert(None)
                    .normalize()
                )

                fx_aligned = fx_series.reindex(
                    pd.DatetimeIndex(lookup["lookup_date"]),
                    method="ffill"
                )
                if fx_aligned.isna().any():
                    fx_aligned = fx_aligned.bfill()
                lookup["usd_per_aud"] = fx_aligned.to_numpy()
                lookup["btc_aud_auto"] = lookup["price"] / lookup["usd_per_aud"]

                daily_btc_aud = (
                    lookup.dropna(subset=["btc_aud_auto"])
                    .groupby("lookup_date")["btc_aud_auto"]
                    .last()
                    .sort_index()
                )

                for row_idx in clean.index[clean["Asset"].eq("ASX:IBIT")]:
                    pd_date = clean.at[row_idx, "_purchase_date"]
                    if pd.isna(pd_date):
                        continue

                    d = pd.Timestamp(pd_date).tz_localize(None).normalize()

                    if d in daily_btc_aud.index:
                        clean.at[row_idx, "BTC AUD Price"] = float(daily_btc_aud.loc[d])
                    else:
                        prior = daily_btc_aud.loc[:d]
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

    # Current portfolio valuation. For ASX:IBIT this is a BTC-equivalent estimate
    # based on live BTC/AUD, not the exact traded ASX market price of the ETF.
    portfolio_live_btc_aud = fetch_live_btc_aud()
    if not np.isfinite(portfolio_live_btc_aud) or portfolio_live_btc_aud <= 0:
        try:
            _end = dt.date.today()
            _start = _end - dt.timedelta(days=10)
            _btc_hist = fetch_btc_history(_start, _end)
            _fx_hist = fetch_aud_usd_rates(_start, _end)
            if (
                _btc_hist is not None and not _btc_hist.empty and
                _fx_hist is not None and not _fx_hist.empty
            ):
                _latest_btc_usd = float(_btc_hist["price"].dropna().iloc[-1])
                _fx_series = pd.Series(_fx_hist, dtype=float).dropna()
                _latest_usd_per_aud = float(_fx_series.iloc[-1])
                if _latest_btc_usd > 0 and _latest_usd_per_aud > 0:
                    portfolio_live_btc_aud = _latest_btc_usd / _latest_usd_per_aud
        except Exception:
            portfolio_live_btc_aud = np.nan

    current_investment_value = (
        total_btc_equivalent * portfolio_live_btc_aud
        if total_btc_equivalent > 0 and np.isfinite(portfolio_live_btc_aud) and portfolio_live_btc_aud > 0
        else np.nan
    )
    unrealized_pl = (
        current_investment_value - total_cash_out
        if np.isfinite(current_investment_value) and total_cash_out > 0
        else np.nan
    )
    total_return_pct = (
        (unrealized_pl / total_cash_out) * 100.0
        if np.isfinite(unrealized_pl) and total_cash_out > 0
        else np.nan
    )

    v1, v2, v3 = st.columns(3)
    v1.metric(
        "Current Investment Value",
        "n/a" if not np.isfinite(current_investment_value) else f"A${current_investment_value:,.0f}",
        help="Estimated from total BTC-equivalent exposure × current BTC/AUD. For ASX:IBIT this is an economic BTC-equivalent estimate, not the exact live ASX ETF market value.",
    )
    v2.metric(
        "Unrealised Return",
        "n/a" if not np.isfinite(unrealized_pl) else f"A${unrealized_pl:,.0f}",
    )
    v3.metric(
        "Return",
        "n/a" if not np.isfinite(total_return_pct) else f"{total_return_pct:+.2f}%",
        help="(Current estimated investment value − total cash paid including brokerage/fees) ÷ total cash paid.",
    )
    if np.isfinite(portfolio_live_btc_aud):
        st.caption(
            f"Portfolio valuation uses BTC/AUD ≈ A${portfolio_live_btc_aud:,.0f}. "
            "ASX:IBIT value is estimated from BTC-equivalent exposure, so it can differ from the ETF's exact live ASX market value due to tracking difference, fees and market pricing."
        )

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
    saved_decisions = browser_state.get("decision_rows", []) if isinstance(browser_state, dict) else []
    decision_df = pd.DataFrame(saved_decisions) if isinstance(saved_decisions, list) and saved_decisions else pd.DataFrame(columns=decision_cols)
    for col in decision_cols:
        if col not in decision_df.columns:
            decision_df[col] = ""
    decision_df = decision_df[decision_cols]

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

    # Automatic browser persistence for portfolio + decision history.
    browser_state["portfolio"] = {
        "starting_capital_aud": float(starting_portfolio_capital),
        "capital_remaining_aud": float(capital_remaining),
        "rows": export_clean[portfolio_cols].to_dict(orient="records"),
    }
    _save_shared_portfolio(browser_state["portfolio"])
    shared_portfolio = browser_state["portfolio"].copy()
    browser_state["decision_rows"] = edited_decisions[decision_cols].to_dict(orient="records")
    _save_browser_state(browser_state)

    if LOCAL_STORAGE_AVAILABLE:
        st.success(
            "Saved automatically in this browser. CSV download remains available as a portable backup."
        )
    else:
        st.warning(
            "Browser-local saving is unavailable in this deployment. Use the CSV download as backup."
        )

