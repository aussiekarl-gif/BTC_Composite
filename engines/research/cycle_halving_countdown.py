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


# Research-only time markers; not assertions about BTC price tops.
CYCLE_REVIEW_MARKERS = (
    (500, "D500", "First distribution review"),
    (560, "D560", "Staged distribution checkpoint"),
    (730, "D730", "Extended exit review"),
)


def build_halving_timeline(*, last_halving_date, today, countdown):
    """One consistent date/counter source for both header metrics and chart."""
    if isinstance(last_halving_date, str):
        last_halving_date = dt.date.fromisoformat(last_halving_date)
    if isinstance(today, dt.datetime):
        today = today.date()
    if not isinstance(last_halving_date, dt.date) or not isinstance(today, dt.date):
        raise ValueError("Expected actual calendar dates")
    elapsed = (today - last_halving_date).days
    remaining = countdown.get("days_remaining")
    if (elapsed < 0 or isinstance(remaining, bool)
            or not isinstance(remaining, int) or remaining < 0):
        raise ValueError("Halving timeline dates or projected days are invalid")
    total = elapsed + remaining
    if total <= 0:
        raise ValueError("Projected cycle length must be positive")
    milestones = [
        {"day": day, "short": short, "description": description}
        for day, short, description in CYCLE_REVIEW_MARKERS
        if day < total
    ]
    return {
        "last_halving_date": last_halving_date.isoformat(),
        "elapsed_days": elapsed,
        "remaining_days": remaining,
        "estimated_next_halving_date": countdown["estimated_date_utc"],
        "total_projected_days": total,
        "progress_pct": 100 * elapsed / total,
        "milestones": milestones,
    }


def build_halving_progress_bar(timeline):
    """Compact horizontal stacked bar, with milestone lines and TODAY pointer."""
    import plotly.graph_objects as go

    elapsed = timeline["elapsed_days"]
    remaining = timeline["remaining_days"]
    total = timeline["total_projected_days"]
    figure = go.Figure()
    figure.add_trace(go.Bar(
        x=[elapsed], y=[0], orientation="h", width=0.31,
        name="Elapsed", marker_color="#14b8a6",
        hovertemplate=f"{elapsed:,} days from last halving<extra></extra>",
    ))
    figure.add_trace(go.Bar(
        x=[remaining], y=[0], orientation="h", width=0.31,
        name="Projected remaining", marker_color="#334155",
        hovertemplate=f"~{remaining:,} days projected remaining<extra></extra>",
    ))
    for marker in timeline["milestones"]:
        day = marker["day"]
        figure.add_shape(
            type="line", x0=day, x1=day, y0=-0.23, y1=0.23,
            line=dict(color="#fbbf24", width=2),
        )
        # Stagger the D500/D560 labels so close review days stay legible.
        ypos = -0.57 if day == 560 else 0.55
        figure.add_annotation(
            x=day, y=ypos, text=marker["short"],
            showarrow=False, font=dict(size=11, color="#fbbf24"),
        )
    figure.add_shape(
        type="line", x0=elapsed, x1=elapsed, y0=-0.34, y1=0.34,
        line=dict(color="#fb923c", width=3),
    )
    figure.add_annotation(
        x=elapsed, y=-0.75, text="TODAY",
        showarrow=False, font=dict(size=11, color="#fb923c"),
    )
    figure.add_annotation(
        x=0, y=-1.03, text="Last halving",
        showarrow=False, xanchor="left",
        font=dict(size=10, color="#94a3b8"),
    )
    figure.add_annotation(
        x=total, y=-1.03, text="Next (est.)",
        showarrow=False, xanchor="right",
        font=dict(size=10, color="#94a3b8"),
    )
    figure.update_layout(
        barmode="stack", showlegend=False,
        height=170,
        margin=dict(l=0, r=0, t=8, b=8),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        xaxis=dict(range=[-total * .015, total * 1.015],
                   visible=False, fixedrange=True),
        yaxis=dict(range=[-1.23, 1.02], visible=False, fixedrange=True),
        hovermode="closest",
        dragmode=False,
    )
    return figure
