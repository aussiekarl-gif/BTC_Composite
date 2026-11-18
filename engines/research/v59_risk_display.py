"""Display-only Research risk scale helpers.

The active R2 sizing score remains on its original 0..1 scale. These helpers
map it monotonically to 0..0.40 for dashboard presentation only.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

DISPLAY_RISK_MAX = 0.40


def display_research_risk(value: float) -> float:
    """Map raw R2 risk [0, 1] to a stretched low-end display scale [0, 0.40]."""
    try:
        score = float(value)
    except (TypeError, ValueError):
        return float("nan")
    if not np.isfinite(score):
        return float("nan")
    return DISPLAY_RISK_MAX * float(np.sqrt(np.clip(score, 0.0, 1.0)))


def display_research_risk_series(values: pd.Series) -> pd.Series:
    """Vectorised display mapping; preserves index and missing observations."""
    numeric = pd.to_numeric(pd.Series(values), errors="coerce")
    return numeric.clip(lower=0.0, upper=1.0).pow(0.5) * DISPLAY_RISK_MAX


def display_band_multiplier_range(
    display_lower: float,
    display_upper: float,
    points,
    multiplier_fn,
) -> tuple[float, float]:
    """Return the full multiplier range represented by one display band.

    The display transform is nonlinear, so equal-width display bins can cross
    several raw-risk ladder thresholds. Evaluate both raw endpoints (upper is
    exclusive) rather than assigning the entire bar the multiplier at its
    lower edge. The active ladder is validated as non-increasing by its caller.
    """
    lower = float(display_lower)
    upper = float(display_upper)
    if not (np.isfinite(lower) and np.isfinite(upper)
            and 0.0 <= lower < upper <= DISPLAY_RISK_MAX):
        raise ValueError("Display band must be an increasing interval within 0..0.40")
    raw_lower = (lower / DISPLAY_RISK_MAX) ** 2
    raw_upper = (upper / DISPLAY_RISK_MAX) ** 2
    raw_upper_probe = float(np.nextafter(raw_upper, raw_lower))
    values = (
        float(multiplier_fn(points, raw_lower)),
        float(multiplier_fn(points, raw_upper_probe)),
    )
    if not all(np.isfinite(value) and value >= 0.0 for value in values):
        raise ValueError("Multiplier function returned an invalid value")
    return min(values), max(values)
