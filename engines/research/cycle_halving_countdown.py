"""Approximate Bitcoin halving countdown for the Streamlit Research header.

Uses public chain tip height and the protocol's 210,000-block subsidy epoch.
Ten minutes per block is a projection, never a scheduled calendar date.
No broker, portfolio, order or notification access.
"""
from __future__ import annotations

import datetime as dt
import math
import requests

BLOCKS_PER_HALVING = 210_000
FIRST_CURRENT_ERA_HEIGHT = 840_000
EXPECTED_BLOCK_MINUTES = 10
TIP_SOURCES = (
    ("mempool.space", "https://mempool.space/api/blocks/tip/height"),
    ("Blockchain.com", "https://blockchain.info/q/getblockcount"),
)


def _utc_now(now):
    value = now if now is not None else dt.datetime.now(dt.timezone.utc)
    if value.tzinfo is None:
        raise ValueError("Current timestamp must be timezone-aware")
    return value.astimezone(dt.timezone.utc)


def estimate_halving_from_height(height, *, now=None):
    """Project the next halving using a chain height and 10 min/block.

    Rounds up the approximate days; real date changes with actual hashrate.
    """
    now = _utc_now(now)
    if isinstance(height, bool) or not isinstance(height, int):
        raise ValueError("Bitcoin block height must be an integer")
    if height < FIRST_CURRENT_ERA_HEIGHT or height > 50_000_000:
        raise ValueError("Implausible BTC block height")
    target = ((height // BLOCKS_PER_HALVING) + 1) * BLOCKS_PER_HALVING
    remaining = target - height
    projected = now + dt.timedelta(minutes=EXPECTED_BLOCK_MINUTES * remaining)
    return {
        "days_remaining": math.ceil(remaining * EXPECTED_BLOCK_MINUTES / 1_440),
        "blocks_remaining": remaining,
        "current_height": height,
        "next_halving_height": target,
        "estimated_date_utc": projected.date().isoformat(),
        "height_verified": True,
        "estimate_basis": "210,000-block halving; 10 minutes per block",
    }


def _calendar_fallback(now):
    """Explicitly labelled low-confidence fallback when BOTH sources fail."""
    date = dt.datetime(2028, 4, 20, tzinfo=dt.timezone.utc)
    while date <= now:
        date = date.replace(year=date.year + 4)
    return {
        "days_remaining": math.ceil((date - now).total_seconds() / 86_400),
        "blocks_remaining": None,
        "current_height": None,
        "next_halving_height": None,
        "estimated_date_utc": date.date().isoformat(),
        "height_verified": False,
        "estimate_basis": "4-year calendar approximation (block height unavailable)",
        "source": "Calendar estimate, not a live blockchain reading",
    }


def fetch_halving_countdown(*, now=None, timeout=8):
    """Fetch recent block height, fail to a labelled calendar approximation."""
    now = _utc_now(now)
    for name, url in TIP_SOURCES:
        try:
            response = requests.get(url, timeout=timeout,
                                    headers={"User-Agent": "BTC-DCA-research/1.0"})
            response.raise_for_status()
            raw = response.text.strip()
            if not raw.isdecimal():
                continue
            result = estimate_halving_from_height(int(raw), now=now)
            result["source"] = name
            return result
        except (requests.RequestException, ValueError, OverflowError):
            continue
    return _calendar_fallback(now)
