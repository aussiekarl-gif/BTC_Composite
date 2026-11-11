"""Read-only visibility helpers for V5.9 risk context and candidate allocations.

These helpers do not replace the frozen R2/Three-Pillar execution sizing.
A candidate preview is never a validated order recommendation.
"""
from __future__ import annotations

import math

from engines.research.v59_dynamic_risk_policy import risk_buy_multiplier


def highlighted_histogram_bucket(value) -> int:
    """Index in research_model.risk_occurrence_table's 13 mutually exclusive bins.

    Do not use a simple count of edges: the histogram begins with separate
    invalid, exact-zero, and (0, .01) bins. That omission previously shifted
    the orange highlight two columns left.
    """
    try:
        x = float(value)
    except (ValueError, TypeError):
        return -1
    if math.isnan(x):
        return -1
    if x < 0:
        return 0
    if x == 0:
        return 1
    if x < 0.01:
        return 2
    for idx, ceiling in enumerate((0.02, 0.05, 0.10, 0.20, 0.40, 0.60, 0.80, 1.00), start=3):
        if x < ceiling:
            return idx
    if x == 1:
        return 11
    return 12


def aggressive_candidate_preview(
    *,
    sizing_risk: float,
    base_weekly_aud: float,
    deployable_aud: float,
    starting_capital_aud: float,
    risk_observation_age_days: int,
    weekly_cap_fraction: float = 0.05,
) -> dict:
    """Preview the separate research risk-band hypothesis without changing live buys.

    A dated closed observation is necessary but not sufficient evidence of
    contemporaneous provider provenance, point-in-time signals, or IBIT fills.
    Age >3 days fails closed and suppresses the illustrative AUD amount.
    """
    mult = risk_buy_multiplier(float(sizing_risk))
    for name, value in (
        ("base_weekly_aud", base_weekly_aud),
        ("deployable_aud", deployable_aud),
        ("starting_capital_aud", starting_capital_aud),
    ):
        if not math.isfinite(float(value)) or float(value) < 0:
            raise ValueError(f"Invalid {name}")
    if not math.isfinite(weekly_cap_fraction) or not 0 < weekly_cap_fraction <= 1:
        raise ValueError("Invalid weekly_cap_fraction")
    if not isinstance(risk_observation_age_days, int):
        raise ValueError("risk_observation_age_days must be an integer")

    recent = 0 <= risk_observation_age_days <= 3
    buy = min(
        float(deployable_aud),
        max(0.0, float(base_weekly_aud) * mult),
        float(starting_capital_aud) * weekly_cap_fraction,
    ) if recent else None
    return {
        "candidate_multiplier": mult,
        "candidate_buy_aud": buy,
        "risk_observation_recent": recent,
        "research_only": True,
        "not_approved_for_live_trading": True,
        "status": "RECENT_SNAPSHOT_NOT_PROVIDER_ATTESTED" if recent else "BLOCKED_STALE_OR_FUTURE_RISK",
    }
