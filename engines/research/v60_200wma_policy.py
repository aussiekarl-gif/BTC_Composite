"""V6.0 clean-slate 200WMA-centred accumulation research policy.

Research-only. This module is intentionally independent of V5.9 and Production.
Signals use a completed Sunday close against the PREVIOUS 200 completed weekly
closes; the signal Sunday is excluded from its own moving average.
All buy sizing is percentage-first. No broker, portfolio store or order access.
"""
from __future__ import annotations

import math
from typing import Mapping

import pandas as pd

MODEL_VERSION = "V6.0"
BASE_BUY_PCT_AVAILABLE_CASH = 2.5
DISCOUNT_THRESHOLDS_PCT = (20.0, 25.0, 30.0)
MAX_WEEKLY_BUY_PCT_ORIGINAL_CAPITAL = 5.0

# Candidate ladders are hypotheses only. The measured ladder is the reference;
# stepped and aggressive alternatives exist only to test sensitivity.
CANDIDATE_LADDERS: Mapping[str, tuple[float, float, float, float]] = {
    "baseline": (2.5, 2.5, 2.5, 2.5),
    "measured": (2.5, 3.5, 5.0, 7.5),
    "stepped": (2.5, 5.0, 7.5, 10.0),
    "aggressive": (2.5, 7.5, 10.0, 15.0),
}


def weekly_prior_200wma_signals(daily_closes: pd.Series) -> pd.DataFrame:
    """Return completed Sunday signals using only the prior 200 weekly closes."""
    if not isinstance(daily_closes, pd.Series) or daily_closes.empty:
        raise ValueError("A non-empty daily BTC/USD close Series is required")
    prices = pd.to_numeric(daily_closes, errors="coerce").dropna().copy()
    prices.index = pd.to_datetime(prices.index, utc=True).floor("D")
    prices = prices.sort_index()
    if prices.index.has_duplicates:
        raise ValueError("Daily BTC close dates must be unique")
    if (prices <= 0).any() or not prices.map(math.isfinite).all():
        raise ValueError("BTC closes must be finite and positive")
    weekly = prices.resample("W-SUN").last().dropna()
    prior_200wma = weekly.rolling(200, min_periods=200).mean().shift(1)
    result = pd.DataFrame({
        "signal_date": weekly.index,
        "btc_usd_sunday_close": weekly.to_numpy(dtype=float),
        "prior_200wma_usd": prior_200wma.to_numpy(dtype=float),
    })
    result["ratio_to_200wma"] = (
        result["btc_usd_sunday_close"] / result["prior_200wma_usd"]
    )
    result["discount_below_200wma_pct"] = (
        (1.0 - result["ratio_to_200wma"]).clip(lower=0.0) * 100.0
    )
    return result


def allocation_for_discount(
    ratio_to_200wma: float,
    *,
    candidate: str = "measured",
) -> float:
    """Return the candidate buy percentage of deployable cash, not dollars."""
    if candidate not in CANDIDATE_LADDERS:
        raise ValueError(f"Unknown V6.0 candidate: {candidate}")
    ratio = float(ratio_to_200wma)
    if not math.isfinite(ratio) or ratio <= 0:
        raise ValueError("A finite positive prior 200WMA ratio is required")
    ladder = CANDIDATE_LADDERS[candidate]
    discount = max(0.0, (1.0 - ratio) * 100.0)
    tier = 0
    for index, threshold in enumerate(DISCOUNT_THRESHOLDS_PCT, start=1):
        if discount + 1e-10 >= threshold:
            tier = index
    return float(ladder[tier])


def calculate_buy_plan(
    *,
    ratio_to_200wma: float,
    available_cash_aud: float,
    original_capital_aud: float,
    initial_cash_aud: float,
    candidate: str = "measured",
    protected_cash_floor_pct_initial_cash: float = 0.0,
) -> dict:
    """Calculate a research buy plan with an optional protected-cash overlay.

    The reserve is a percentage of initial cash. The candidate percentage is
    applied only to deployable cash above that reserve. A weekly hard cap of
    5% of original capital remains a separate guardrail.
    """
    values = (available_cash_aud, original_capital_aud, initial_cash_aud,
              protected_cash_floor_pct_initial_cash)
    if not all(math.isfinite(float(x)) for x in values):
        raise ValueError("Cash, capital and reserve inputs must be finite")
    if available_cash_aud < 0 or original_capital_aud <= 0 or initial_cash_aud < 0:
        raise ValueError("Invalid cash or capital amount")
    if not 0 <= protected_cash_floor_pct_initial_cash < 100:
        raise ValueError("Protected cash floor must be in [0, 100)")
    buy_pct = allocation_for_discount(ratio_to_200wma, candidate=candidate)
    reserve_aud = initial_cash_aud * protected_cash_floor_pct_initial_cash / 100.0
    deployable_cash = max(0.0, available_cash_aud - reserve_aud)
    uncapped_buy_aud = deployable_cash * buy_pct / 100.0
    weekly_cap_aud = original_capital_aud * MAX_WEEKLY_BUY_PCT_ORIGINAL_CAPITAL / 100.0
    buy_aud = min(uncapped_buy_aud, weekly_cap_aud)
    effective_pct_available_cash = (
        100.0 * buy_aud / available_cash_aud if available_cash_aud > 0 else 0.0
    )
    return {
        "model_version": MODEL_VERSION,
        "candidate": candidate,
        "ratio_to_200wma": float(ratio_to_200wma),
        "discount_below_200wma_pct": max(0.0, (1.0-float(ratio_to_200wma))*100.0),
        "buy_pct_deployable_cash": buy_pct,
        "protected_cash_floor_pct_initial_cash": float(protected_cash_floor_pct_initial_cash),
        "protected_cash_floor_aud": reserve_aud,
        "available_cash_aud": float(available_cash_aud),
        "deployable_cash_aud": deployable_cash,
        "weekly_hard_cap_aud": weekly_cap_aud,
        "buy_aud": buy_aud,
        "effective_buy_pct_available_cash": effective_pct_available_cash,
        "research_only": True,
        "trade_executable": False,
    }
