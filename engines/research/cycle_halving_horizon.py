"""Long-range BTC halving calendar and price-chart annotations (research only)."""
from __future__ import annotations

import datetime as dt
import pandas as pd


HISTORICAL_HALVINGS = (
    ("2012-11-28", "2012", "confirmed"),
    ("2016-07-09", "2016", "confirmed"),
    ("2020-05-11", "2020", "confirmed"),
    ("2024-04-20", "2024", "confirmed"),
)
BLOCKS_PER_HALVING = 210_000
EXPECTED_BLOCK_MINUTES = 10
FINAL_HALVING_YEAR = 2040


def build_halving_schedule(next_estimated_date: str, *, final_year: int = FINAL_HALVING_YEAR):
    """Return confirmed historical events and clearly labelled future estimates.

    Future dates are seeded by the current block-height estimate, then projected
    at 210,000 blocks and 10 minutes per block. They are not calendar promises.
    """
    try:
        first = dt.date.fromisoformat(str(next_estimated_date))
    except (TypeError, ValueError) as exc:
        raise ValueError("A valid next-halving estimate date is required") from exc
    if final_year < first.year or final_year > 2100:
        raise ValueError("Invalid final halving year")

    rows = [
        {"year": label, "date": date, "status": status,
         "before_500d": (dt.date.fromisoformat(date) - dt.timedelta(days=500)).isoformat(),
         "after_500d": (dt.date.fromisoformat(date) + dt.timedelta(days=500)).isoformat()}
        for date, label, status in HISTORICAL_HALVINGS
    ]
    step = dt.timedelta(minutes=BLOCKS_PER_HALVING * EXPECTED_BLOCK_MINUTES)
    current = dt.datetime.combine(first, dt.time.min, tzinfo=dt.timezone.utc)
    while current.year <= final_year:
        date = current.date()
        rows.append({
            "year": str(date.year), "date": date.isoformat(), "status": "estimated",
            "before_500d": (date - dt.timedelta(days=500)).isoformat(),
            "after_500d": (date + dt.timedelta(days=500)).isoformat(),
        })
        current += step
    return rows


def build_halving_horizon_chart(history: pd.Series, schedule):
    """Full available daily BTC history plus 500-day windows through final event."""
    import plotly.graph_objects as go

    if not isinstance(history, pd.Series) or history.empty:
        raise ValueError("Historical BTC price series is empty")
    prices = pd.to_numeric(history, errors="coerce").dropna().sort_index()
    if prices.empty or (prices <= 0).any():
        raise ValueError("BTC history must contain positive prices")

    figure = go.Figure()
    figure.add_trace(go.Scatter(
        x=prices.index, y=prices.values, mode="lines",
        name="BTC/USD daily close", line=dict(width=1.4),
        hovertemplate="%{x|%d %b %Y}<br>BTC: US$%{y:,.0f}<extra></extra>",
    ))
    for item in schedule:
        event = dt.date.fromisoformat(item["date"])
        before = dt.date.fromisoformat(item["before_500d"])
        after = dt.date.fromisoformat(item["after_500d"])
        estimated = item["status"] != "confirmed"
        colour = "rgba(245, 158, 11, 0.10)" if estimated else "rgba(20, 184, 166, 0.09)"
        figure.add_vrect(
            x0=before, x1=event, fillcolor=colour, opacity=1,
            line_width=0, layer="below",
        )
        figure.add_vrect(
            x0=event, x1=after, fillcolor=colour, opacity=1,
            line_width=0, layer="below",
        )
        figure.add_vline(
            x=event, line_width=1.5,
            line_dash="dash" if estimated else "solid",
            line_color="#f59e0b" if estimated else "#14b8a6",
        )
        figure.add_annotation(
            x=event, y=1, yref="paper", yanchor="top",
            text=f"{item['year']} {'EST.' if estimated else 'HALVING'}",
            showarrow=False, textangle=-90,
            xshift=7, yshift=-8, font=dict(size=10),
        )

    last_event = max(dt.date.fromisoformat(x["date"]) for x in schedule)
    end = last_event + dt.timedelta(days=500)
    figure.update_layout(
        title="Bitcoin halving cycles · confirmed history and estimates through 2040",
        height=560, margin=dict(l=12, r=20, t=55, b=35),
        hovermode="x unified",
        xaxis=dict(
            title="UTC calendar date",
            range=[prices.index.min(), end],
            rangeslider=dict(visible=True),
        ),
        yaxis=dict(title="BTC/USD (log scale)", type="log"),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, x=0),
    )
    return figure
