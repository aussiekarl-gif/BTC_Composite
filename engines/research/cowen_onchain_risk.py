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
    higher_is_riskier: bool,
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
    if any(not np.isfinite(float(v)) or float(v) <= 0 for v in supplied.values()):
        raise ValueError("all seven active metric weights must be finite and positive")
    scores = component_scores.reindex(columns=ACTIVE_METRICS).apply(
        pd.to_numeric, errors="coerce"
    )
    complete = scores.notna().all(axis=1)
    total = float(sum(supplied.values()))
    result = scores.mul(pd.Series(supplied, dtype=float), axis=1).div(total)
    return result.where(complete)


def calculate_terminal_price(inputs: pd.DataFrame) -> pd.DataFrame:
    """Calculate Cowen's raw Terminal Price from complete daily CDD, price and supply.

    Cowen's public 2026 explanation defines Value Days Destroyed as
    CDD * BTC price, Transferred Price as cumulative VDD / (market age * supply),
    and Terminal Price as 21 * Transferred Price.

    The first row is treated as market-age day 1 (the first price observation).
    Inputs must be complete and contiguous: a missing CDD day cannot be treated
    as zero because that would permanently understate cumulative VDD.
    This returns raw price levels and price/terminal ratio, not a 0-1 risk score.
    """
    required = ("cdd_btc_days", "price_usd", "supply_btc")
    if not isinstance(inputs, pd.DataFrame):
        raise TypeError("inputs must be a pandas DataFrame")
    if not set(required).issubset(inputs.columns):
        raise ValueError(f"inputs must contain {required}")
    frame = inputs.loc[:, required].apply(pd.to_numeric, errors="coerce").copy()
    if not frame.index.is_monotonic_increasing or frame.index.has_duplicates:
        raise ValueError("inputs index must be sorted and unique")
    if not isinstance(frame.index, pd.DatetimeIndex):
        raise TypeError("inputs index must be a DatetimeIndex")
    if frame.index.tz is None or str(frame.index.tz) != "UTC":
        raise ValueError("inputs dates must be timezone-aware UTC")
    if frame.index.hasnans:
        raise ValueError("inputs index cannot contain NaT")
    if len(frame) < 1:
        raise ValueError("inputs must contain at least one daily observation")
    if frame.isna().any().any():
        raise ValueError("CDD, price and supply must be complete; no gap filling is allowed")
    if (frame["cdd_btc_days"] < 0).any():
        raise ValueError("CDD cannot be negative")
    if (frame[["price_usd", "supply_btc"]] <= 0).any().any():
        raise ValueError("price and supply must be positive")
    if len(frame) > 1:
        gaps = frame.index.to_series().diff().dropna()
        if not gaps.eq(pd.Timedelta(days=1)).all():
            raise ValueError("inputs must have one observation per consecutive UTC day")

    out = frame.copy()
    out["value_days_destroyed_usd"] = out["cdd_btc_days"] * out["price_usd"]
    out["cumulative_value_days_destroyed_usd"] = out["value_days_destroyed_usd"].cumsum()
    out["market_age_days"] = np.arange(1, len(out) + 1, dtype=int)
    out["transferred_price_usd"] = (
        out["cumulative_value_days_destroyed_usd"]
        / (out["market_age_days"] * out["supply_btc"])
    )
    out["terminal_price_usd"] = 21.0 * out["transferred_price_usd"]
    out["price_to_terminal_price"] = out["price_usd"] / out["terminal_price_usd"]
    return out


def _read_daily_chart_export(path, metric_column):
    """Read a BlockHorizon-style millisecond-UTC daily export without filling gaps."""
    frame = pd.read_csv(path)
    required = {"timestamp", metric_column}
    if not required.issubset(frame.columns):
        raise ValueError(f"{path}: missing required columns {sorted(required - set(frame.columns))}")
    # Convert the timestamp/value arrays positionally. Keeping the conversion
    # outside Series index alignment avoids accidental label alignment when a
    # CSV parser or pandas version supplies a non-RangeIndex.
    timestamps = pd.to_numeric(frame["timestamp"], errors="coerce").to_numpy(dtype=float)
    values = pd.to_numeric(frame[metric_column], errors="coerce").to_numpy(dtype=float)
    valid = np.isfinite(timestamps)
    dates = pd.to_datetime(
        timestamps[valid].astype("int64"),
        unit="ms", utc=True, errors="coerce",
    ).normalize()
    valid_dates = ~pd.isna(dates)
    result = pd.Series(
        values[valid][valid_dates],
        index=pd.DatetimeIndex(dates[valid_dates]),
        name=metric_column,
        dtype=float,
    ).sort_index()
    if result.index.has_duplicates:
        duplicate_dates = result.index[result.index.duplicated()].unique()
        examples = ", ".join(str(x.date()) for x in duplicate_dates[:5])
        raise ValueError(f"{path}: duplicate UTC dates ({examples})")
    return result


def build_existing_raw_candidates(data_dir):
    """Load only the existing local exports that can support first-pass components.

    Returned values are raw metric candidates, not Cowen risk scores. MVRV is
    explicitly a PlanB-realized-price proxy; MVRV Z is the saved provider export.
    Missing observations remain NaN. No composite or trading output is produced.
    """
    from pathlib import Path

    root = Path(data_dir)
    revenue = _read_daily_chart_export(
        root / "miner_revenue_total_daily__2026-10-07T21-26-46.csv",
        "Miner Revenue: Total (Daily)",
    )
    realized = pd.read_csv(root / "planb_realized_prices_2026-10-07T21-19-48.csv")
    required = {"timestamp", "Price", "Realized Price"}
    if not required.issubset(realized.columns):
        raise ValueError("PlanB realized-price export has unexpected columns")
    dates = pd.to_datetime(
        pd.to_numeric(realized["timestamp"], errors="coerce"),
        unit="ms", utc=True, errors="coerce"
    ).dt.normalize()
    price = pd.to_numeric(realized["Price"], errors="coerce")
    realized_price = pd.to_numeric(realized["Realized Price"], errors="coerce")
    planb = pd.DataFrame(
        {"price_usd": price.to_numpy(dtype=float),
         "realized_price_usd": realized_price.to_numpy(dtype=float)},
        index=dates,
    ).loc[lambda x: x.index.notna()].sort_index()
    if planb.index.has_duplicates:
        raise ValueError("PlanB realized-price export has duplicate UTC dates")
    if (planb[["price_usd", "realized_price_usd"]] <= 0).any().any():
        raise ValueError("PlanB price fields must be positive")

    # Standard Puell candidate: daily miner revenue divided by its trailing
    # 365-observation simple moving average. Includes the current completed day;
    # this is a candidate definition, not proof of exact Cowen source parity.
    puell = revenue / revenue.rolling(365, min_periods=365).mean()
    puell.name = "puell_multiple_candidate"

    mvrv_proxy = planb["price_usd"] / planb["realized_price_usd"]
    mvrv_proxy.name = "mvrv_planb_realized_price_proxy"

    z_path = root / "mvrv_z_score_2026-10-06T21-46-14.csv"
    mvrv_z = _read_daily_chart_export(z_path, "MVRV Z-Score")
    mvrv_z.name = "mvrv_z_score_provider_export"

    result = pd.concat(
        [puell, mvrv_proxy, mvrv_z], axis=1, join="outer"
    ).sort_index()
    result.index.name = "date_utc"
    return result
