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
