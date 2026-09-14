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
    ("Hash Ribbon Ratio (30D/60D)", "derived__hash_ribbon_ratio_30d_60d"),
    ("Difficulty Ribbon Compression (context)", "derived__difficulty_ribbon_compression"),
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

CONTEXT_ONLY_LABELS = {"Difficulty Ribbon Compression (context)"}

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

    # Optional provisional research fallbacks. They remain in explicitly
    # digitized columns and never overwrite authoritative provider observations.
    digitized_artifacts = (
        ("digitized/nupl_lookintobitcoin_chart_read.csv", "digitized__lookintobitcoin_nupl"),
        ("provider/nvt_blockchain_daily.csv", "source__blockchain_nvt"),
        ("provider/nvts_blockchain_observations.csv", "source__blockchain_nvts"),
        ("provider/difficulty_blockchain_sampled.csv", "source__blockchain_difficulty"),
        ("provider/mvrv_blockchain_daily.csv", "source__blockchain_mvrv"),
    )
    for digitized_path, chart_col in digitized_artifacts:
        try:
            digitized_meta = requests.get(
                f"https://api.github.com/repos/{repo}/contents/{digitized_path}",
                headers=headers,
                params={"ref": branch},
                timeout=30,
            )
            digitized_meta.raise_for_status()
            digitized_obj = digitized_meta.json()
            digitized_raw = base64.b64decode(digitized_obj["content"].encode())
            digitized = pd.read_csv(io.BytesIO(digitized_raw))
            digitized["date"] = pd.to_datetime(digitized["date"], utc=True, errors="coerce")
            digitized = digitized.dropna(subset=["date"]).set_index("date").sort_index()
            if chart_col in digitized.columns:
                chart_values = pd.to_numeric(digitized[chart_col], errors="coerce")
                df[chart_col] = chart_values.reindex(df.index)
        except Exception:
            # The main audit master must remain usable if an optional research
            # artifact is missing or temporarily unavailable.
            pass
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
        direct = (
            pd.to_numeric(master[col], errors="coerce")
            if col in master.columns
            else pd.Series(np.nan, index=master.index, dtype=float)
        )
        # Align every source independently before combining. This ensures a
        # chart value dated exactly on Monday cannot outrank a newer-quality
        # provider observation from the preceding few days.
        series = _asof_to_mondays(direct, monday_idx)
        output_label = label

        if col == "MVRV" and "source__blockchain_mvrv" in master.columns:
            provider = pd.to_numeric(master["source__blockchain_mvrv"], errors="coerce")
            series = series.combine_first(_asof_to_mondays(provider, monday_idx))

        if col == "derived__difficulty_ribbon_compression" and "source__blockchain_difficulty" in master.columns:
            blockchain_difficulty = pd.to_numeric(
                master["source__blockchain_difficulty"], errors="coerce"
            ).replace(0.0, np.nan)
            daily_difficulty_index = pd.date_range(
                master.index.min().normalize(),
                master.index.max().normalize(),
                freq="D",
            )
            daily_difficulty = blockchain_difficulty.reindex(
                daily_difficulty_index
            ).ffill()
            ribbon_windows = (9, 14, 25, 40, 60, 90, 128, 200)
            difficulty_ribbon = pd.concat(
                [
                    daily_difficulty.rolling(window, min_periods=window).mean()
                    for window in ribbon_windows
                ],
                axis=1,
            )
            derived_difficulty_compression = (
                difficulty_ribbon.std(axis=1, ddof=0)
                / difficulty_ribbon.mean(axis=1).replace(0.0, np.nan)
            ).replace([np.inf, -np.inf], np.nan)
            series = series.combine_first(
                _asof_to_mondays(derived_difficulty_compression, monday_idx)
            )

        if col == "derived__hash_ribbon_ratio_30d_60d" and "cm__HashRate" in master.columns:
            cm_hash_rate = pd.to_numeric(master["cm__HashRate"], errors="coerce")
            daily_hash_index = pd.date_range(
                master.index.min().normalize(),
                master.index.max().normalize(),
                freq="D",
            )
            daily_hash_rate = cm_hash_rate.reindex(daily_hash_index)
            hash_ma_30d = daily_hash_rate.rolling(30, min_periods=30).mean()
            hash_ma_60d = daily_hash_rate.rolling(60, min_periods=60).mean()
            derived_hash_ribbon = (
                hash_ma_30d / hash_ma_60d.replace(0.0, np.nan)
            ).replace([np.inf, -np.inf], np.nan)
            aligned_hash_ribbon = _asof_to_mondays(
                derived_hash_ribbon, monday_idx
            )
            series = series.combine_first(aligned_hash_ribbon)

        if (
            col == "derived__hash_ribbon_ratio_30d_60d"
            and "source__blockchain_hash_rate_th_s" in master.columns
        ):
            # Blockchain.com's all-history series is sampled roughly every four
            # days. Time-window rolling means use only genuine observations;
            # no daily values are interpolated or invented.
            blockchain_hash = pd.to_numeric(
                master["source__blockchain_hash_rate_th_s"], errors="coerce"
            ).replace(0.0, np.nan).dropna().sort_index()
            blockchain_hash_30d = blockchain_hash.rolling(
                "30D", min_periods=6
            ).mean()
            blockchain_hash_60d = blockchain_hash.rolling(
                "60D", min_periods=12
            ).mean()
            blockchain_hash_ribbon = (
                blockchain_hash_30d
                / blockchain_hash_60d.replace(0.0, np.nan)
            ).replace([np.inf, -np.inf], np.nan)
            series = series.combine_first(
                _asof_to_mondays(blockchain_hash_ribbon, monday_idx)
            )

        if col == "ThermoCap Multiple":
            thermocap_inputs = (
                "cm__PriceUSD",
                "cm__FeeTotNtv",
                "cm__IssTotNtv",
                "cm__CapMrktCurUSD",
            )
            if all(input_col in master.columns for input_col in thermocap_inputs):
                cm_price = pd.to_numeric(master["cm__PriceUSD"], errors="coerce")
                cm_fees = pd.to_numeric(master["cm__FeeTotNtv"], errors="coerce")
                cm_issuance = pd.to_numeric(master["cm__IssTotNtv"], errors="coerce")
                cm_market_cap = pd.to_numeric(master["cm__CapMrktCurUSD"], errors="coerce")
                valid_revenue = (
                    cm_price.notna()
                    & cm_fees.notna()
                    & cm_issuance.notna()
                    & (cm_price > 0)
                )
                daily_miner_revenue_usd = (
                    (cm_issuance + cm_fees) * cm_price
                ).where(valid_revenue)
                cumulative_miner_revenue_usd = (
                    daily_miner_revenue_usd.fillna(0.0).cumsum()
                )
                derived_thermocap = (
                    cm_market_cap / cumulative_miner_revenue_usd.replace(0.0, np.nan)
                ).replace([np.inf, -np.inf], np.nan)
                aligned_thermocap = _asof_to_mondays(
                    derived_thermocap, monday_idx
                )
                derived_used = bool((series.isna() & aligned_thermocap.notna()).any())
                series = series.combine_first(aligned_thermocap)
                if derived_used:
                    output_label = "ThermoCap Multiple (daily derived)"

        if col == "NVT Signal" and "source__blockchain_nvts" in master.columns:
            provider_nvts = pd.to_numeric(
                master["source__blockchain_nvts"], errors="coerce"
            )
            series = series.combine_first(
                _asof_to_mondays(provider_nvts, monday_idx)
            )

        if col == "NVT" and "source__blockchain_nvt" in master.columns:
            provider_nvt = pd.to_numeric(
                master["source__blockchain_nvt"], errors="coerce"
            )
            series = series.combine_first(
                _asof_to_mondays(provider_nvt, monday_idx)
            )

        if col == "NUPL" and "source__blockchain_mvrv" in master.columns:
            provider_mvrv = pd.to_numeric(
                master["source__blockchain_mvrv"], errors="coerce"
            )
            provider_nupl = (1.0 - (1.0 / provider_mvrv)).replace(
                [np.inf, -np.inf], np.nan
            ) * 100.0
            series = series.combine_first(
                _asof_to_mondays(provider_nupl, monday_idx)
            )

        fallback_specs = {
            "NUPL": (
                pd.to_numeric(master["digitized__lookintobitcoin_nupl"], errors="coerce")
                if "digitized__lookintobitcoin_nupl" in master.columns else None,
                "NUPL (chart-read approx.)",
            ),
        }
        if col == "MVRV" and "digitized__lookintobitcoin_nupl" in master.columns:
            chart_nupl = pd.to_numeric(
                master["digitized__lookintobitcoin_nupl"], errors="coerce"
            ) / 100.0
            chart_mvrv = (1.0 / (1.0 - chart_nupl)).replace(
                [np.inf, -np.inf], np.nan
            )
            fallback_specs["MVRV"] = (
                chart_mvrv,
                "MVRV (includes chart-read approx.)",
            )

        if col in fallback_specs:
            fallback, fallback_label = fallback_specs[col]
            if fallback is not None:
                aligned_fallback = _asof_to_mondays(fallback, monday_idx)
                fallback_used = bool((series.isna() & aligned_fallback.notna()).any())
                series = series.combine_first(aligned_fallback)
                if fallback_used:
                    output_label = fallback_label

        if series.notna().sum() < 52:
            continue
        values[output_label] = series
        pct = _expanding_percentile(series, min_periods=52)
        states[output_label] = pct.map(_percentile_to_state)
        available.append(output_label)

    if states.empty:
        raise RuntimeError("Not enough indicator history is available yet to build the timeline.")

    consensus_inputs = states.drop(
        columns=list(CONTEXT_ONLY_LABELS), errors="ignore"
    )
    states["Bottom Consensus"] = consensus_inputs.mean(axis=1, skipna=True).round()
    counts = consensus_inputs.notna().sum(axis=1)
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
provisional_labels = [
    label for label in (
        "NUPL (chart-read approx.)",
    )
    if label in indicator_rows
]
if provisional_labels:
    st.warning(
        f"{', '.join(provisional_labels)} currently use approximate weekly series digitized from charts. "
        "They are research-only and will be superseded automatically where direct provider data becomes available."
    )
if not indicator_rows:
    st.warning("No indicators are available in the selected range.")
    st.stop()

coverage_rows = []
for coverage_label in indicator_rows:
    coverage_values = pd.to_numeric(
        values[coverage_label], errors="coerce"
    ).dropna()
    coverage_states = pd.to_numeric(
        states[coverage_label], errors="coerce"
    ).dropna()
    coverage_rows.append({
        "Indicator": coverage_label,
        "First value": (
            coverage_values.index.min().date().isoformat()
            if not coverage_values.empty else ""
        ),
        "First classified state": (
            coverage_states.index.min().date().isoformat()
            if not coverage_states.empty else ""
        ),
        "Last value": (
            coverage_values.index.max().date().isoformat()
            if not coverage_values.empty else ""
        ),
        "Weekly values": int(len(coverage_values)),
        "Missing-history reason": (
            "52-observation causal warm-up after first value"
            if not coverage_values.empty and not coverage_states.empty
            and coverage_states.index.min() > coverage_values.index.min()
            else ""
        ),
    })
coverage_report = pd.DataFrame(coverage_rows)
with st.expander("DATA COVERAGE AND REMAINING GAPS", expanded=False):
    st.caption(
        "Black periods before First value are unavailable source history. "
        "Periods between First value and First classified state are the required "
        "52-observation causal warm-up, not missing data."
    )
    st.dataframe(coverage_report, use_container_width=True, hide_index=True)
    st.download_button(
        "DOWNLOAD TIMELINE COVERAGE REPORT (.CSV)",
        coverage_report.to_csv(index=False).encode("utf-8"),
        "btc_bottom_timeline_coverage_report.csv",
        "text/csv",
        key="download_timeline_coverage_report",
    )

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
consensus_row = row.drop(labels=list(CONTEXT_ONLY_LABELS), errors="ignore")
counts = _state_counts(consensus_row)
consensus_state = show_states.loc[selected, "Bottom Consensus"]
consensus_name = "Unavailable" if pd.isna(consensus_state) else STATE_NAMES[int(round(float(consensus_state)))]

m1, m2, m3, m4, m5 = st.columns(5)
m1.metric("Deep Value", counts["Deep Value"])
m2.metric("Value", counts["Value"])
m3.metric("Neutral", counts["Neutral"])
m4.metric("Elevated", counts["Elevated"])
m5.metric("Extreme", counts["Extreme"])
st.info(f"Bottom Consensus: **{consensus_name}** — based on {int(consensus_row.notna().sum())} voting indicators for {pd.Timestamp(selected).strftime('%d %b %Y')}. Context-only rows are excluded.")

price_sources = [
    col for col in ("price_usd", "cm__PriceUSD", "src__blockchain_btc_usd")
    if col in master.columns
]
if price_sources:
    # Preserve the preferred audited price where it exists, but fill its early
    # null history from the independent Coin Metrics/blockchain sources.
    combined_price = pd.to_numeric(master[price_sources[0]], errors="coerce")
    for source_col in price_sources[1:]:
        combined_price = combined_price.combine_first(
            pd.to_numeric(master[source_col], errors="coerce")
        )
    price = _asof_to_mondays(combined_price, states.index)
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

combined_export_parts = []
for export_label in indicator_rows:
    if export_label not in show_values.columns:
        continue
    export_value = pd.to_numeric(show_values[export_label], errors="coerce")
    export_state = pd.to_numeric(show_states[export_label], errors="coerce")
    export_frame = pd.DataFrame({
        "date": export_value.index,
        "indicator": export_label,
        "value": export_value.to_numpy(),
        "state_code": export_state.to_numpy(),
        "state": export_state.map(
            lambda value: "" if pd.isna(value)
            else STATE_NAMES[int(round(float(value)))]
        ).to_numpy(),
    })
    # Keep genuine missing weeks visible in the export rather than filling them.
    combined_export_parts.append(export_frame)

if combined_export_parts:
    combined_indicator_export = pd.concat(
        combined_export_parts, ignore_index=True
    ).sort_values(["date", "indicator"])
    st.download_button(
        "DOWNLOAD ALL TIMELINE INDICATORS (.CSV)",
        combined_indicator_export.to_csv(index=False).encode("utf-8"),
        "btc_bottom_timeline_all_indicators.csv",
        "text/csv",
        key="download_all_timeline_indicators",
        help="Long-format export of every displayed weekly indicator value and state. Genuine gaps remain blank.",
    )

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
        indicator_export = pd.DataFrame({
            "date": raw.index,
            "indicator": label,
            "value": raw.to_numpy(),
            "state_code": pd.to_numeric(
                state_series, errors="coerce"
            ).to_numpy(),
            "state": pd.to_numeric(state_series, errors="coerce").map(
                lambda value: "" if pd.isna(value)
                else STATE_NAMES[int(round(float(value)))]
            ).to_numpy(),
        })
        safe_label = "".join(
            char.lower() if char.isalnum() else "_" for char in label
        ).strip("_")
        st.download_button(
            f"DOWNLOAD {label} (.CSV)",
            indicator_export.to_csv(index=False).encode("utf-8"),
            f"btc_bottom_timeline_{safe_label}.csv",
            "text/csv",
            key=f"download_indicator_{chart_index}_{safe_label}",
            help="The exact Monday-aligned values and states displayed in this chart. Genuine gaps remain blank.",
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
