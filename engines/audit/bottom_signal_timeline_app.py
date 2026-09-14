import os
import io
import base64
from datetime import datetime

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import requests
import streamlit as st


INDICATORS = [
    ("Risk Score (V5.8.2)", "risk_score"),
    ("MVRV Z-Score", "MVRV Z-Score (positive control)"),
    ("Puell Multiple", "Puell Multiple"),
    ("Mayer Multiple (200D)", "Mayer Multiple (200D)"),
    ("2Y MA Multiple", "2Y MA Multiple"),
    ("200W MA Multiple", "200W MA Multiple"),
    ("MVRV", "MVRV"),
    ("NUPL", "NUPL"),
    ("NVT", "NVT"),
    ("NVT Signal", "NVT Signal"),
    ("ThermoCap Multiple", "ThermoCap Multiple"),
    ("VDD Multiple", "VDD Multiple"),
    ("STH MVRV", "STH MVRV"),
    ("LTH MVRV", "LTH MVRV"),
    ("aSOPR", "aSOPR"),
    ("Supply in Profit %", "Supply in Profit %"),
    ("UTXOs in Profit %", "UTXOs in Profit %"),
    ("Percent STH in Profit", "Percent STH in Profit"),
    ("Percent LTH in Profit", "Percent LTH in Profit"),
    ("STH SOPR", "STH SOPR"),
    ("LTH SOPR", "LTH SOPR"),
]

STATE_NAMES = {
    0: "Deep Value",
    1: "Value",
    2: "Neutral",
    3: "Elevated",
    4: "Extreme",
}

COLORSCALE = [
    [0.00, "#1769aa"],
    [0.24, "#1769aa"],
    [0.25, "#8fc1ef"],
    [0.49, "#8fc1ef"],
    [0.50, "#e7edf3"],
    [0.74, "#e7edf3"],
    [0.75, "#f1a3b8"],
    [0.89, "#f1a3b8"],
    [0.90, "#cb153d"],
    [1.00, "#cb153d"],
]


def _secret_or_env(name, default=""):
    try:
        value = st.secrets.get(name, "")
        if value:
            return str(value).strip()
    except Exception:
        pass
    return os.getenv(name, default).strip()


@st.cache_data(ttl=900, show_spinner=False)
def load_audit_master():
    token = _secret_or_env("AUDIT_GITHUB_TOKEN") or _secret_or_env("GITHUB_TOKEN") or _secret_or_env("GH_TOKEN")
    repo = _secret_or_env("AUDIT_GITHUB_REPO")
    branch = _secret_or_env("AUDIT_GITHUB_BRANCH", "main") or "main"
    path = _secret_or_env("AUDIT_GITHUB_PATH", "btc_audit_backup.csv") or "btc_audit_backup.csv"
    if not token or not repo:
        raise RuntimeError("AUDIT_GITHUB_TOKEN / AUDIT_GITHUB_REPO are not configured.")

    url = f"https://api.github.com/repos/{repo}/contents/{path}"
    headers = {
        "Accept": "application/vnd.github+json",
        "Authorization": f"Bearer {token}",
        "X-GitHub-Api-Version": "2022-11-28",
        "User-Agent": "btc-bottom-signal-timeline",
    }
    meta = requests.get(url, headers=headers, params={"ref": branch}, timeout=30)
    meta.raise_for_status()
    obj = meta.json()
    raw = b""
    if obj.get("content"):
        raw = base64.b64decode(obj["content"].encode())
    else:
        raw_headers = dict(headers)
        raw_headers["Accept"] = "application/vnd.github.raw"
        rr = requests.get(url, headers=raw_headers, params={"ref": branch}, timeout=60)
        rr.raise_for_status()
        raw = rr.content
    if not raw:
        raise RuntimeError("Central audit master is empty.")

    df = pd.read_csv(io.BytesIO(raw))
    if "date" not in df.columns:
        raise RuntimeError("Central audit master has no date column.")
    df["date"] = pd.to_datetime(df["date"], utc=True, errors="coerce")
    df = df.dropna(subset=["date"]).set_index("date").sort_index()
    return df


def _asof_to_mondays(series, mondays):
    s = pd.to_numeric(series, errors="coerce").dropna().sort_index()
    if s.empty:
        return pd.Series(np.nan, index=mondays, dtype=float)
    left = pd.DataFrame({"date": pd.DatetimeIndex(mondays)}).sort_values("date")
    right = s.rename("value").reset_index()
    right.columns = ["source_date", "value"]
    right["source_date"] = pd.to_datetime(right["source_date"], utc=True, errors="coerce")
    right = right.dropna(subset=["source_date"]).sort_values("source_date")
    out = pd.merge_asof(left, right, left_on="date", right_on="source_date", direction="backward")
    return pd.Series(pd.to_numeric(out["value"], errors="coerce").to_numpy(), index=mondays)


def _expanding_percentile(series, min_periods=52):
    x = pd.to_numeric(series, errors="coerce")
    vals = x.to_numpy(dtype=float)
    out = np.full(len(vals), np.nan)
    seen = []
    for i, value in enumerate(vals):
        if np.isfinite(value):
            seen.append(value)
        if np.isfinite(value) and len(seen) >= min_periods:
            arr = np.asarray(seen, dtype=float)
            out[i] = (np.sum(arr < value) + 0.5 * np.sum(arr == value)) / len(arr)
    return pd.Series(out, index=series.index)


def _percentile_to_state(percentile):
    if not np.isfinite(percentile):
        return np.nan
    if percentile <= 0.10:
        return 0
    if percentile <= 0.25:
        return 1
    if percentile < 0.75:
        return 2
    if percentile < 0.90:
        return 3
    return 4


def build_timeline(master):
    # Use the central master's full calendar instead of anchoring every series
    # to Risk Score, which only begins in 2016. Each indicator remains blank
    # until its own first genuine observation.
    first_monday = pd.Timestamp(master.index.min()).normalize()
    if first_monday.weekday() != 0:
        first_monday += pd.Timedelta(days=(7 - first_monday.weekday()))
    last_monday = pd.Timestamp(master.index.max()).normalize()
    last_monday -= pd.Timedelta(days=last_monday.weekday())
    monday_idx = pd.date_range(first_monday, last_monday, freq="W-MON")
    if len(monday_idx) == 0:
        raise RuntimeError("No Monday observations found in central audit master.")

    values = pd.DataFrame(index=monday_idx)
    states = pd.DataFrame(index=monday_idx)
    available = []
    for label, col in INDICATORS:
        if col not in master.columns:
            continue
        series = _asof_to_mondays(master[col], monday_idx)
        if series.notna().sum() < 52:
            continue
        values[label] = series
        pct = _expanding_percentile(series, min_periods=52)
        states[label] = pct.map(_percentile_to_state)
        available.append(label)

    if states.empty:
        raise RuntimeError("Not enough indicator history is available yet to build the timeline.")

    states["Bottom Consensus"] = states.mean(axis=1, skipna=True).round()
    counts = states.drop(columns=["Bottom Consensus"]).notna().sum(axis=1)
    consensus = states["Bottom Consensus"]
    consensus[counts < 3] = np.nan
    states["Bottom Consensus"] = consensus
    return values, states


def _state_counts(row):
    row = pd.to_numeric(row, errors="coerce").dropna()
    counts = {name: 0 for name in STATE_NAMES.values()}
    for value in row:
        iv = int(round(float(value)))
        if iv in STATE_NAMES:
            counts[STATE_NAMES[iv]] += 1
    return counts


def _forward_return(price, selected, weeks):
    if selected not in price.index or not np.isfinite(price.loc[selected]):
        return np.nan
    target = selected + pd.Timedelta(weeks=weeks)
    later = price.loc[price.index >= target].dropna()
    if later.empty:
        return np.nan
    return later.iloc[0] / price.loc[selected] - 1.0


st.title("Bitcoin Bottom Signal Timeline")
st.caption("Historical multi-indicator state map. Research/audit only — it does not change Monday DCA sizing or Production.")

try:
    master = load_audit_master()
    values, states = build_timeline(master)
except Exception as exc:
    st.error(f"Timeline could not be built: {exc}")
    st.stop()

available_years = list(range(int(states.index.min().year), int(states.index.max().year) + 1))
left_year, right_year = st.slider(
    "History range",
    min_value=available_years[0],
    max_value=available_years[-1],
    value=(available_years[0], available_years[-1]),
)
mask = (states.index.year >= left_year) & (states.index.year <= right_year)
show_states = states.loc[mask].copy()
show_values = values.reindex(show_states.index)

indicator_rows = [c for c in show_states.columns if c != "Bottom Consensus"]
if not indicator_rows:
    st.warning("No indicators are available in the selected range.")
    st.stop()

z = show_states[indicator_rows + ["Bottom Consensus"]].T.to_numpy(dtype=float)
heat = go.Figure(
    data=go.Heatmap(
        z=z,
        x=show_states.index,
        y=indicator_rows + ["Bottom Consensus"],
        zmin=0,
        zmax=4,
        colorscale=COLORSCALE,
        colorbar=dict(
            title="State",
            tickmode="array",
            tickvals=[0, 1, 2, 3, 4],
            ticktext=[STATE_NAMES[i] for i in range(5)],
        ),
        hovertemplate="%{y}<br>%{x|%d %b %Y}<br>State: %{z}<extra></extra>",
        xgap=0,
        ygap=1,
    )
)
heat.update_layout(
    height=max(470, 30 * (len(indicator_rows) + 2)),
    margin=dict(l=10, r=10, t=15, b=10),
    xaxis=dict(title=None, rangeslider=dict(visible=False)),
    yaxis=dict(autorange="reversed", title=None),
)
st.plotly_chart(heat, use_container_width=True)

st.caption("Blue = historically cheap/value relative to information available at that time. Red = historically elevated/extreme. States use causal expanding percentiles, so future observations are not used to classify past weeks.")

selectable = list(show_states.index)
default_idx = len(selectable) - 1
selected = st.select_slider(
    "Selected week",
    options=selectable,
    value=selectable[default_idx],
    format_func=lambda d: pd.Timestamp(d).strftime("%d %b %Y"),
)

row = show_states.loc[selected, indicator_rows]
counts = _state_counts(row)
consensus_state = show_states.loc[selected, "Bottom Consensus"]
consensus_name = "Unavailable" if pd.isna(consensus_state) else STATE_NAMES[int(round(float(consensus_state)))]

m1, m2, m3, m4, m5 = st.columns(5)
m1.metric("Deep Value", counts["Deep Value"])
m2.metric("Value", counts["Value"])
m3.metric("Neutral", counts["Neutral"])
m4.metric("Elevated", counts["Elevated"])
m5.metric("Extreme", counts["Extreme"])
st.info(f"Bottom Consensus: **{consensus_name}** — based on {int(row.notna().sum())} available indicators for {pd.Timestamp(selected).strftime('%d %b %Y')}.")

price_col = "price_usd" if "price_usd" in master.columns else "src__blockchain_btc_usd" if "src__blockchain_btc_usd" in master.columns else None
if price_col:
    price = _asof_to_mondays(master[price_col], states.index)
    price = pd.to_numeric(price, errors="coerce")
    c1, c2 = st.columns([2, 1])
    with c1:
        pfig = go.Figure()
        pfig.add_trace(go.Scatter(x=price.index, y=price, mode="lines", name="BTC Price (USD)", line=dict(width=1.8)))
        if selected in price.index and np.isfinite(price.loc[selected]):
            pfig.add_vline(x=selected, line_dash="dash", line_width=1.5)
        pfig.update_yaxes(type="log", title="BTC Price (USD, log scale)")
        pfig.update_layout(height=390, margin=dict(l=10, r=10, t=30, b=10), title="BTC price with selected week")
        st.plotly_chart(pfig, use_container_width=True)
    with c2:
        st.subheader("Forward returns")
        for weeks in (4, 13, 26, 52):
            ret = _forward_return(price, selected, weeks)
            st.metric(f"{weeks} weeks", "—" if not np.isfinite(ret) else f"{ret:+.1%}")

st.subheader("Individual indicator histories")
st.caption("Each chart uses the same Monday-aligned source values and selected week as the heatmap. Missing source periods remain blank.")

chart_columns = st.columns(2)
for chart_index, label in enumerate(indicator_rows):
    raw = pd.to_numeric(show_values[label], errors="coerce") if label in show_values.columns else pd.Series(np.nan, index=show_values.index)
    state_series = show_states[label] if label in show_states.columns else pd.Series(np.nan, index=show_states.index)
    available_raw = raw.dropna()
    with chart_columns[chart_index % 2]:
        if available_raw.empty:
            st.info(f"{label}: no values are available in the selected history range.")
            continue

        # Give every chart its own honest time range. Plotly otherwise includes
        # leading/trailing dates even when all corresponding values are null.
        first_actual = available_raw.index[0]
        last_actual = available_raw.index[-1]
        raw = raw.loc[first_actual:last_actual]
        state_series = state_series.reindex(raw.index)

        indicator_fig = go.Figure()
        indicator_fig.add_trace(
            go.Scatter(
                x=raw.index,
                y=raw,
                mode="lines",
                name=label,
                line=dict(color="#60b8f4", width=1.7),
                connectgaps=False,
                hovertemplate="%{x|%d %b %Y}<br>Value: %{y:.4g}<extra></extra>",
            )
        )
        selected_in_range = first_actual <= selected <= last_actual
        selected_value = raw.get(selected, np.nan) if selected_in_range else np.nan
        selected_state = state_series.get(selected, np.nan) if selected_in_range else np.nan
        if np.isfinite(selected_value):
            selected_name = "Unavailable" if pd.isna(selected_state) else STATE_NAMES[int(round(float(selected_state)))]
            indicator_fig.add_trace(
                go.Scatter(
                    x=[selected],
                    y=[selected_value],
                    mode="markers",
                    name=f"Selected week: {selected_name}",
                    marker=dict(color="#ff4b55", size=9, line=dict(color="#ffffff", width=1)),
                    hovertemplate=(
                        f"{pd.Timestamp(selected).strftime('%d %b %Y')}<br>"
                        f"Value: {selected_value:.4g}<br>State: {selected_name}<extra></extra>"
                    ),
                )
            )
        if selected_in_range:
            indicator_fig.add_vline(x=selected, line_dash="dash", line_width=1.2, line_color="#ff4b55")
        indicator_fig.update_layout(
            height=300,
            margin=dict(l=8, r=8, t=42, b=8),
            title=label,
            showlegend=False,
            xaxis=dict(title=None, rangeslider=dict(visible=False)),
            yaxis=dict(title="Value", fixedrange=False),
            hovermode="x unified",
        )
        st.plotly_chart(
            indicator_fig,
            use_container_width=True,
            key=f"indicator_history_{chart_index}_{label}",
        )

st.subheader("Indicator values — selected week")
detail_rows = []
for label in indicator_rows:
    raw_value = show_values.at[selected, label] if label in show_values.columns else np.nan
    state_value = show_states.at[selected, label]
    detail_rows.append({
        "Indicator": label,
        "Value": raw_value,
        "State": "—" if pd.isna(state_value) else STATE_NAMES[int(round(float(state_value)))],
    })
detail = pd.DataFrame(detail_rows)
st.dataframe(detail, use_container_width=True, hide_index=True)

st.caption("Method: each indicator is aligned to Monday using the latest available observation, then classified by its expanding historical percentile. This is a visualization layer only; no Production or Research sizing logic is changed.")
