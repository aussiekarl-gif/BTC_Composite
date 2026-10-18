"""Research-only BTC independent-evidence gate. No IO, trades or portfolio writes.

A research watch is not authority to place a trade. Do not count shared
Production/Research/Cycle model inputs as independent evidence.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Literal, Sequence

Direction = Literal["BUY", "SELL", "HOLD"]
Family = Literal["cycle", "valuation", "onchain", "spot_flow", "derivatives"]
FAMILIES = frozenset(("cycle", "valuation", "onchain", "spot_flow", "derivatives"))
INDEPENDENT_FLOW = frozenset(("onchain", "spot_flow", "derivatives"))
MAX_AGE = timedelta(hours=36)


@dataclass(frozen=True)
class Evidence:
    family: Family
    direction: Direction
    observed_at: datetime
    captured_at: datetime
    source: str
    rationale: str
    usable: bool = True


@dataclass(frozen=True)
class ResearchWatch:
    status: str
    candidate_direction: str
    supporting_families: tuple[str, ...]
    opposing_families: tuple[str, ...]
    missing_families: tuple[str, ...]
    rejected: tuple[str, ...]
    explanation: str
    paper_only: bool = True
    executable: bool = False
    executable_order_aud: float = 0.0


def _utc_aware(value: datetime) -> bool:
    return (isinstance(value, datetime) and value.tzinfo is not None
            and value.utcoffset() is not None)


def evaluate_evidence(
    observations: Sequence[Evidence], *, as_of_utc: datetime,
    max_age: timedelta = MAX_AGE,
) -> ResearchWatch:
    """Require fresh, non-contradictory hypotheses from distinct data families.

    Opposing BUY/SELL is a veto. Two correlated cycle+valuation hypotheses
    never suffice. No broker linkage, sizing, messaging or side effects.
    """
    if not _utc_aware(as_of_utc):
        raise ValueError("as_of_utc must be timezone-aware")
    if not isinstance(max_age, timedelta) or max_age <= timedelta(0):
        raise ValueError("max_age must be positive")
    now = as_of_utc.astimezone(timezone.utc)
    by_family: dict[str, Evidence] = {}
    duplicate_families: set[str] = set()
    rejected: list[str] = []
    for item in observations:
        if not isinstance(item, Evidence):
            rejected.append("untyped evidence")
            continue
        if item.family not in FAMILIES:
            rejected.append("unknown evidence family")
            continue
        if item.family in by_family:
            duplicate_families.add(item.family)
        else:
            by_family[item.family] = item

    for family in sorted(duplicate_families):
        del by_family[family]
        rejected.append(f"{family}: duplicate family submissions")

    valid: dict[str, Evidence] = {}
    for family, item in sorted(by_family.items()):
        if item.direction not in ("BUY", "SELL", "HOLD"):
            rejected.append(f"{family}: invalid vote")
        elif not (_utc_aware(item.observed_at)
                  and _utc_aware(item.captured_at)):
            rejected.append(f"{family}: undated/unzoned evidence")
        elif not item.source.strip() or not item.rationale.strip() or not item.usable:
            rejected.append(f"{family}: source unverified/unusable")
        else:
            observed = item.observed_at.astimezone(timezone.utc)
            captured = item.captured_at.astimezone(timezone.utc)
            if observed > captured or captured > now:
                rejected.append(f"{family}: future or backdated capture")
            elif now - observed > max_age or now - captured > max_age:
                rejected.append(f"{family}: stale")
            else:
                valid[family] = item

    missing = tuple(sorted(FAMILIES - valid.keys()))
    buys = tuple(sorted(f for f, v in valid.items() if v.direction == "BUY"))
    sells = tuple(sorted(f for f, v in valid.items() if v.direction == "SELL"))
    if buys and sells:
        return ResearchWatch("CONFLICT", "NONE", (), tuple(sorted(buys+sells)),
                             missing, tuple(rejected),
                             "Opposing current evidence; no candidate action.")
    direction, support = (("BUY", buys) if buys else (("SELL", sells) if sells
                          else ("NONE", ())))
    if len(support) >= 2 and INDEPENDENT_FLOW.intersection(support):
        return ResearchWatch("RESEARCH_WATCH", direction, support, (), missing,
                             tuple(rejected),
                             "Unvalidated paper-only hypothesis; prospective testing required.")
    return ResearchWatch("INSUFFICIENT_EVIDENCE", "NONE", support, (), missing,
                         tuple(rejected),
                         "No independent agreement. Missing/stale data cannot vote.")
