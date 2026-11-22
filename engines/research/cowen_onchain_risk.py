"""Research-only Cowen On-Chain Historical Risk reconstruction utilities.

This module deliberately separates metric normalisation from the seven-metric
completeness gate. It does not fetch data, infer missing values, or emit trades.
All component scores use the convention 0 = lower historical risk and 1 = higher.
"""
from __future__ import annotations

from collections.abc import Mapping

import numpy as np
import pandas as pd

ACTIVE_METRICS = (
    "puell_multiple",
    "mvrv",
    "mvrv_z_score",
    "transaction_fees",
    "terminal_price",
    "mctc",
    "mctc_miner",
)
ZERO_WEIGHT_DIAGNOSTICS = ("rhodl_ratio", "supply_pnl")
DEFAULT_WEIGHTS = {name: 1.0 for name in ACTIVE_METRICS}


def prior_only_percentile_risk(
    values: pd.Series,
    *,
    window_observations: int,
    min_prior_observations: int,
    higher_is_riskier: bool = True,
) -> pd.Series:
    """Rank today's value against strictly earlier observations only.

    The rolling window is expressed in observations, not calendar days. Callers
    must choose it to match the source cadence (e.g. daily vs weekly). The current
    observation is ranked against the preceding window; it is never included in
    its own reference distribution. No interpolation or filling is performed.
    """
    if not isinstance(values, pd.Series):
        raise TypeError("values must be a pandas Series")
    if window_observations < 1:
        raise ValueError("window_observations must be positive")
    if min_prior_observations < 2 or min_prior_observations > window_observations:
        raise ValueError("min_prior_observations must be between 2 and window_observations")
    if not values.index.is_monotonic_increasing or values.index.has_duplicates:
        raise ValueError("values index must be sorted and unique")

    raw = pd.to_numeric(values, errors="coerce").astype(float)

    def rank_current_against_prior(window: np.ndarray) -> float:
        current = window[-1]
        prior = window[:-1]
        prior = prior[np.isfinite(prior)]
        if not np.isfinite(current) or len(prior) < min_prior_observations:
            return np.nan
        less = np.count_nonzero(prior < current)
        equal = np.count_nonzero(prior == current)
        return float((less + 0.5 * equal) / len(prior))

    ranked = raw.rolling(
        window=window_observations + 1,
        min_periods=min_prior_observations + 1,
    ).apply(rank_current_against_prior, raw=True)
    if not higher_is_riskier:
        ranked = 1.0 - ranked
    ranked.name = f"{values.name or 'metric'}_risk_percentile"
    return ranked.clip(0.0, 1.0)


def build_seven_metric_composite(
    component_scores: pd.DataFrame,
    *,
    weights: Mapping[str, float] | None = None,
) -> pd.DataFrame:
    """Build a seven-of-seven research composite or explicitly mark it incomplete.

    A partial mean is included only as a diagnostic. It is never returned as the
    composite risk score and cannot be interpreted as an investable signal.
    """
    if not isinstance(component_scores, pd.DataFrame):
        raise TypeError("component_scores must be a pandas DataFrame")
    if not component_scores.index.is_monotonic_increasing or component_scores.index.has_duplicates:
        raise ValueError("component_scores index must be sorted and unique")

    supplied = dict(DEFAULT_WEIGHTS if weights is None else weights)
    if set(supplied) != set(ACTIVE_METRICS):
        raise ValueError("weights must specify exactly the seven active metrics")
    if any(not np.isfinite(float(v)) or float(v) <= 0 for v in supplied.values()):
        raise ValueError("all seven active metric weights must be finite and positive")

    scores = component_scores.reindex(columns=ACTIVE_METRICS).apply(
        pd.to_numeric, errors="coerce"
    )
    invalid = scores.notna() & ((scores < 0.0) | (scores > 1.0))
    if invalid.any().any():
        raise ValueError("component risk scores must be within [0, 1]")

    present = scores.notna()
    count = present.sum(axis=1)
    complete = count.eq(len(ACTIVE_METRICS))
    weight_series = pd.Series(supplied, dtype=float)
    weighted_sum = scores.mul(weight_series, axis=1).sum(axis=1, min_count=len(ACTIVE_METRICS))
    total_weight = float(weight_series.sum())

    out = pd.DataFrame(index=scores.index)
    out["available_component_count"] = count.astype(int)
    out["component_coverage_pct"] = 100.0 * count / len(ACTIVE_METRICS)
    out["partial_mean_diagnostic_only"] = scores.mean(axis=1, skipna=True)
    out["composite_risk"] = (weighted_sum / total_weight).where(complete)
    out["status"] = np.where(
        complete,
        "COMPLETE — RESEARCH ONLY",
        "INCOMPLETE — NOT INVESTABLE",
    )
    out["missing_components"] = [
        ", ".join(name for name in ACTIVE_METRICS if pd.isna(row[name]))
        for _, row in scores.iterrows()
    ]
    return out


def component_contributions(
    component_scores: pd.DataFrame,
    *,
    weights: Mapping[str, float] | None = None,
) -> pd.DataFrame:
    """Return weighted contributions, blank on dates lacking any active metric."""
    supplied = dict(DEFAULT_WEIGHTS if weights is None else weights)
    if set(supplied) != set(ACTIVE_METRICS):
        raise ValueError("weights must specify exactly the seven active metrics")
    scores = component_scores.reindex(columns=ACTIVE_METRICS).apply(
        pd.to_numeric, errors="coerce"
    )
    complete = scores.notna().all(axis=1)
    total = float(sum(supplied.values()))
    result = scores.mul(pd.Series(supplied, dtype=float), axis=1).div(total)
    return result.where(complete)
