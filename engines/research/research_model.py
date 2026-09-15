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

# V5.9 three-pillar research overlay. Deliberately broad causal timing zone,
# based only on elapsed days since the previous known halving (no future-date look-ahead).
HALVING_ACCUMULATION_START_DAY = 800
HALVING_ACCUMULATION_END_DAY = 1000
# Retained for compatibility with older exports. The halving zone is now
# context-only and applies no sizing floor.
HALVING_ACCUMULATION_FLOOR_MULT = 1.00


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


def _days_since_previous_halving(index):
    """Causal cycle clock: elapsed days since the latest halving already observed."""
    idx = pd.to_datetime(index)
    naive = idx.tz_localize(None) if getattr(idx, "tz", None) is not None else idx
    halvings = [pd.Timestamp("2012-11-28"), pd.Timestamp("2016-07-09"),
                pd.Timestamp("2020-05-11"), pd.Timestamp("2024-04-20")]
    vals = []
    for ts in naive:
        prior = [h for h in halvings if h <= ts]
        vals.append(float((ts - max(prior)).days) if prior else np.nan)
    return pd.Series(vals, index=index, dtype=float)


def apply_three_pillar_allocator(result_df, total_budget_aud=DEFAULT_INTELLIGENT_DCA_BUDGET_AUD, fee_pct=0.0):
    """Runway-guarded R2 + context-only halving zone + staged bottom events."""
    if result_df.empty:
        return pd.DataFrame(), {}
    x = result_df.copy()
    base = pd.to_numeric(x["dca_multiplier"], errors="coerce").fillna(1.0)
    event = pd.to_numeric(x.get("bottom_challenger_event_multiplier"), errors="coerce")
    days = _days_since_previous_halving(x.index)
    in_zone = days.between(HALVING_ACCUMULATION_START_DAY, HALVING_ACCUMULATION_END_DAY, inclusive="both")
    # Ordinary weeks cannot exceed 1.00x, so the remaining budget retains a
    # full paced runway to the final execution. Only a newly staged exceptional
    # bottom event is allowed to front-load at its explicit 3x/4x/3x weight.
    timed = np.minimum(base, 1.0)
    combined = np.where(event.notna(), np.maximum(timed, event), timed)
    x["r2_dca_multiplier"] = base
    x["days_since_previous_halving"] = days.values
    x["halving_accumulation_zone"] = in_zone.values
    x["halving_timing_multiplier"] = timed
    x["dca_multiplier"] = combined
    x["challenger_multiplier_applied"] = combined
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





