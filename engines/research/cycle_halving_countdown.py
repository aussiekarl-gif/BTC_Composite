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
LAST_KNOWN_HALVING_DATE = dt.date(2024, 4, 20)
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
    # 2024 is verified history; later halving timestamps need independent
    # block evidence before they may reset trading cycle-day calculations.
    latest_epoch_height = (height // BLOCKS_PER_HALVING) * BLOCKS_PER_HALVING
    verified_history = latest_epoch_height == FIRST_CURRENT_ERA_HEIGHT
    return {
        "last_halving_height": latest_epoch_height,
        "last_halving_date": LAST_KNOWN_HALVING_DATE.isoformat() if verified_history else None,
        "halving_date_verified": verified_history,
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
        "last_halving_date": LAST_KNOWN_HALVING_DATE.isoformat() if now.date() < dt.date(2028,1,1) else None,
        "halving_date_verified": False,
        "last_halving_height": None,
    }


def fetch_verified_halving_date(height, *, now=None, timeout=8):
    """Confirm future halving event date from one of two public block APIs."""
    now=_utc_now(now)
    if height < FIRST_CURRENT_ERA_HEIGHT + BLOCKS_PER_HALVING or (
            height % BLOCKS_PER_HALVING != 0):
        raise ValueError("Not a future halving boundary")

    def valid_date(timestamp):
        stamp=dt.datetime.fromtimestamp(int(timestamp), dt.timezone.utc)
        if stamp.date()<=LAST_KNOWN_HALVING_DATE or stamp>now:
            raise ValueError("Invalid future halving block timestamp")
        return stamp.date().isoformat()

    try:
        hash_url=f"https://mempool.space/api/block-height/{height}"
        hash_response=requests.get(hash_url,timeout=timeout)
        hash_response.raise_for_status()
        block_hash=hash_response.text.strip().lower()
        if len(block_hash)!=64 or any(ch not in "0123456789abcdef" for ch in block_hash):
            raise ValueError("Invalid halving block hash")
        response=requests.get(f"https://mempool.space/api/block/{block_hash}",
                              timeout=timeout)
        response.raise_for_status()
        payload=response.json()
        if not isinstance(payload,dict) or int(payload.get("height",-1))!=height:
            raise ValueError("Halving block height did not match")
        return valid_date(payload["timestamp"])
    except (requests.RequestException, ValueError, KeyError,
            OverflowError, OSError, TypeError):
        # Distinct public source so a temporary mempool.space outage is not
        # a single point of failure for a new confirmed halving date.
        response=requests.get(
            f"https://blockchain.info/block-height/{height}?format=json",
            timeout=timeout)
        response.raise_for_status()
        blocks=response.json().get("blocks",[])
        if not isinstance(blocks,list):
            raise ValueError("Invalid alternate halving block response")
        for block in blocks:
            if (isinstance(block,dict) and block.get("main_chain") is True
                    and int(block.get("height",-1))==height):
                return valid_date(block["time"])
        raise ValueError("Alternate provider did not confirm canonical block")

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
            if not result["halving_date_verified"]:
                try:
                    confirmed = fetch_verified_halving_date(
                        result["last_halving_height"], now=now, timeout=timeout)
                    result["last_halving_date"] = confirmed
                    result["halving_date_verified"] = True
                except (requests.RequestException, ValueError, TypeError, OverflowError):
                    result["cycle_safety_note"] = (
                        "New halving epoch detected but event date could not be verified. "
                        "No cycle-timed trade recommendations until confirmed."
                    )
            return result
        except (requests.RequestException, ValueError, OverflowError):
            continue
    return _calendar_fallback(now)


def normalise_halving_epoch_metadata(countdown):
    """Backfill historical 2024 epoch metadata missing from cached old quotes.

    Streamlit may hold a successful pre-upgrade countdown dict for an hour.
    Those old results have a verified live block height, but predate the
    last_halving_date/halving_date_verified fields. Never infer a future
    halving date merely from calendar time or an unverified quote.
    """
    if not isinstance(countdown, dict):
        raise ValueError("Invalid halving quote payload")
    result = dict(countdown)
    height = result.get("current_height")
    next_height = result.get("next_halving_height")
    # The actual 2024 event is independently established history.
    # A valid live block tip in the same epoch proves no NEW halving has
    # occurred, even if this quote was cached before the schema upgrade.
    known_2024_epoch = (
        result.get("height_verified") is True
        and isinstance(height, int) and not isinstance(height, bool)
        and FIRST_CURRENT_ERA_HEIGHT <= height < FIRST_CURRENT_ERA_HEIGHT + BLOCKS_PER_HALVING
        and next_height == FIRST_CURRENT_ERA_HEIGHT + BLOCKS_PER_HALVING
    )
    if known_2024_epoch:
        existing = result.get("last_halving_date")
        if existing not in (None, LAST_KNOWN_HALVING_DATE.isoformat()):
            raise ValueError("Conflicting verified halving event date")
        result["last_halving_date"] = LAST_KNOWN_HALVING_DATE.isoformat()
        result["last_halving_height"] = FIRST_CURRENT_ERA_HEIGHT
        result["halving_date_verified"] = True
        return result

    # A future epoch is only valid when the actual epoch-start block date
    # has already been separately verified by the provider fetch path.
    if result.get("halving_date_verified") is True:
        date_raw = result.get("last_halving_date")
        if not isinstance(date_raw, str) or not date_raw:
            result["halving_date_verified"] = False
        elif (not isinstance(height, int) or isinstance(height, bool)
              or not isinstance(next_height, int)
              or next_height != (height // BLOCKS_PER_HALVING + 1) * BLOCKS_PER_HALVING):
            result["halving_date_verified"] = False
        else:
            try:
                confirmed = dt.date.fromisoformat(date_raw)
                if confirmed < LAST_KNOWN_HALVING_DATE:
                    result["halving_date_verified"] = False
            except ValueError:
                result["halving_date_verified"] = False
    else:
        result["halving_date_verified"] = False
    return result


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
