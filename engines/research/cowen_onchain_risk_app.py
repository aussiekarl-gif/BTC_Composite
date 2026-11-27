"""Cowen-style On-Chain Metrics Historical Risk research dashboard.

This is a visual research replica, not Cowen's proprietary indicator. It shows
only data that exists locally, labels proxy series, and never emits a trade signal.
"""
from pathlib import Path
import json
from datetime import datetime, timezone
import sys

import numpy as np
import pandas as pd
import streamlit as st

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from engines.research import cowen_onchain_risk as cowen_risk

ACTIVE_METRICS = cowen_risk.ACTIVE_METRICS
ZERO_WEIGHT_DIAGNOSTICS = cowen_risk.ZERO_WEIGHT_DIAGNOSTICS
build_existing_raw_candidates = cowen_risk.build_existing_raw_candidates
prior_only_percentile_risk = cowen_risk.prior_only_percentile_risk

# Compatibility guard for a Streamlit instance that may briefly serve an older
# cached module while the repository deployment is updating. The fallback is
# deliberately identical in its strict six-of-six requirement and remains
# research-only; it never fills missing values or emits a trade signal.
if hasattr(cowen_risk, "build_six_metric_research_composite"):
    build_six_metric_research_composite = cowen_risk.build_six_metric_research_composite
else:
    def build_six_metric_research_composite(component_scores, *, weights=None):
        required = (
            "puell_multiple", "mvrv", "mvrv_z_score",
            "transaction_fees", "terminal_price", "mctc",
        )
        supplied = dict({name: 1.0 for name in required} if weights is None else weights)
        if set(supplied) != set(required):
            raise ValueError("weights must specify exactly the six research metrics")
        if any(not np.isfinite(float(value)) or float(value) <= 0 for value in supplied.values()):
            raise ValueError("all six research metric weights must be finite and positive")
        scores = component_scores.reindex(columns=required).apply(pd.to_numeric, errors="coerce")
        invalid = scores.notna() & ((scores < 0.0) | (scores > 1.0))
        if invalid.any().any():
            raise ValueError("component risk scores must be within [0, 1]")
        complete = scores.notna().all(axis=1)
        weight_series = pd.Series(supplied, dtype=float)
        weighted = scores.mul(weight_series, axis=1).sum(axis=1, min_count=len(required))
        result = pd.DataFrame(index=scores.index)
        result["available_component_count"] = scores.notna().sum(axis=1).astype(int)
        result["component_coverage_pct"] = 100.0 * result["available_component_count"] / len(required)
        result["partial_mean_diagnostic_only"] = scores.mean(axis=1, skipna=True)
        result["composite_risk"] = (weighted / float(weight_series.sum())).where(complete)
        result["status"] = np.where(
            complete, "COMPLETE — SIX-METRIC RESEARCH ONLY", "INCOMPLETE — NOT INVESTABLE"
        )
        result["missing_components"] = [
            ", ".join(name for name in required if pd.isna(row[name]))
            for _, row in scores.iterrows()
        ]
        return result

st.markdown("""
<style>
.cowen-wrap {background:#050505;border:0;border-radius:0;padding:10px 8px 14px 8px;margin:0 0 10px 0}
.cowen-kicker {color:#8e9aa5;font-size:11px;letter-spacing:1.4px;text-transform:uppercase;font-weight:700;text-align:center}
.cowen-heading {color:#f4f6f8;font-size:29px;font-weight:800;margin:3px 0;text-align:center}
.cowen-sub {color:#aab2bb;font-size:12px;text-align:center}
.metric-card {background:#080b10;border:1px solid #252a31;border-radius:7px;padding:11px 13px;
 min-height:118px;margin-bottom:9px}
.metric-name {font-size:13px;color:#a9c2d1;font-weight:700;min-height:34px}
.metric-value {font-size:25px;color:#f4f8fb;font-weight:800;margin:5px 0}
.metric-foot {font-size:11px;color:#8caaba}
.metric-score {font-size:12px;color:#d5e5ee}
.pending {color:#e4b76a}
</style>
""", unsafe_allow_html=True)

st.markdown("""
<div class="cowen-wrap">
 <div class="cowen-kicker">RESEARCH 10.0 • INTO THE CRYPTOVERSE RECONSTRUCTION</div>
 <div class="cowen-heading">On-Chain Metrics Historical Risk</div>
 <div class="cowen-sub">Standalone on-chain risk research page • six-metric experiment • mCTC tracked separately</div>
</div>
""", unsafe_allow_html=True)

st.markdown(
    "**RESEARCH DISPLAY ONLY** — this is not Benjamin Cowen's live indicator and does not "
    "reproduce its proprietary transformations. No DCA, buy or sell signal is generated. "
    "Missing components are left missing; the experimental six-metric score requires all six inputs."
)

DATA_DIR = ROOT / "data"


def onchain_source_health():
    """Read retrieval sidecars and report source freshness without altering metrics."""
    base = DATA_DIR / "research" / "cowen_onchain"
    metadata_files = [
        ("Explore21 Puell", base / "explore21" / "bitcoin-puell-multiple.metadata.json"),
        ("Explore21 MVRV", base / "explore21" / "bitcoin-mvrv-ratio.metadata.json"),
        ("Explore21 MVRV Z", base / "explore21" / "bitcoin-mvrv-z-score.metadata.json"),
        ("Coin Metrics", base / "coinmetrics_btc_daily_community.metadata.json"),
        ("Aethereal fees", base / "bitcoin_network_daily_aethereal.metadata.json"),
        ("Open Bitcoin Metrics CDD", base / "obm_cdd_btcxdays_daily.metadata.json"),
    ]
    now = datetime.now(timezone.utc)
    rows = []
    for source, path in metadata_files:
        if not path.exists():
            rows.append({"Source": source, "Latest observation": "—",
                        "Retrieved (UTC)": "—", "Age": "—", "Health": "NO METADATA"})
            continue
        try:
            metadata = json.loads(path.read_text(encoding="utf-8"))
            last_date = metadata.get("last_date_utc")
            retrieved = metadata.get("retrieved_at_utc")
            retrieval_dt = datetime.fromisoformat(retrieved.replace("Z", "+00:00")) if retrieved else None
            obs_dt = datetime.fromisoformat(last_date).replace(tzinfo=timezone.utc) if last_date else None
            retrieval_age = (now - retrieval_dt).total_seconds() / 86400 if retrieval_dt else None
            observation_age = (now.date() - obs_dt.date()).days if obs_dt else None
            age_text = (
                f"{retrieval_age:.1f}d retrieved / {observation_age}d data"
                if retrieval_age is not None and observation_age is not None else "unknown"
            )
            health = "FRESH" if retrieval_age is not None and observation_age is not None and retrieval_age <= 3 and observation_age <= 2 else "STALE"
            rows.append({
                "Source": source,
                "Latest observation": last_date or "—",
                "Retrieved (UTC)": retrieval_dt.strftime("%Y-%m-%d %H:%M") if retrieval_dt else "—",
                "Age": age_text,
                "Health": health,
            })
        except (OSError, ValueError, TypeError, json.JSONDecodeError):
            rows.append({"Source": source, "Latest observation": "—",
                        "Retrieved (UTC)": "—", "Age": "—", "Health": "METADATA ERROR"})
    return rows


@st.cache_data(ttl=900, show_spinner=False)
def cached_raw_candidates(data_dir):
    """Cache local source-file parsing for interactive research reruns."""
    return build_existing_raw_candidates(Path(data_dir))


@st.cache_data(ttl=900, show_spinner=False)
def cached_prior_risk_frame(series_map):
    """Cache the rolling prior-only percentile calculations for 15 minutes."""
    result = pd.DataFrame()
    for metric, values in series_map.items():
        result[metric] = prior_only_percentile_risk(
            values, window_observations=1825, min_prior_observations=365,
            higher_is_riskier=True,
        )
    return result



def historical_risk_hover_data(risk_series, price_series):
    """Build aligned custom hover data: BTC price USD and risk score.

    Uses exact date alignment only; missing prices remain n/a rather than
    silently forward-filling or introducing look-ahead.
    """
    risk_values = pd.to_numeric(risk_series, errors="coerce")
    prices = pd.to_numeric(price_series, errors="coerce") if price_series is not None else pd.Series(dtype=float)
    aligned_prices = prices.reindex(risk_values.index)
    return [
        [f"${price:,.2f}" if pd.notna(price) else "n/a", f"{risk:.3f}" if pd.notna(risk) else "n/a"]
        for price, risk in zip(aligned_prices.to_numpy(), risk_values.to_numpy())
    ]

try:
    raw = cached_raw_candidates(str(DATA_DIR))
    load_error = None
except Exception as exc:
    raw = pd.DataFrame()
    load_error = str(exc)

# Prefer the public Explore21 source snapshots when present. The older local exports
# remain a clearly labelled fallback for offline use and historical regression tests.
series_map = {}
source_map = {}
if not raw.empty:
    source_candidates = (
        ("puell_multiple_explore21", "puell_multiple", "Explore21 Puell Multiple, method v1 • CC BY 4.0"),
        ("mvrv_explore21", "mvrv", "Explore21 MVRV ratio, method v2 • CC BY 4.0"),
        ("mvrv_z_score_explore21", "mvrv_z_score", "Explore21 MVRV Z-Score, method v1 • CC BY 4.0"),
        ("transaction_fees_btc_candidate", "transaction_fees", "Aethereal preferred; Coin Metrics native BTC fees fallback • mixed-source research candidate"),
        ("price_to_terminal_price_candidate", "terminal_price", "Price / Terminal Price ratio from OBM CDD + Coin Metrics price/supply; partial-history candidate"),
        ("mctc_ratio_candidate", "mctc", "Market Cap / cumulative miner revenue (ThermoCap) • Coin Metrics issuance + preferred Aethereal / fallback Coin Metrics fees; candidate"),
        ("puell_multiple_candidate", "puell_multiple", "Legacy miner-revenue-derived candidate; not preferred"),
        ("mvrv_planb_realized_price_proxy", "mvrv", "PlanB price / realised-price proxy; not exact market-cap MVRV"),
        ("mvrv_z_score_provider_export", "mvrv_z_score", "Saved provider export; methodology not reconciled"),
    )
    for column, metric, source in source_candidates:
        if column in raw and metric not in series_map:
            series_map[metric] = pd.to_numeric(raw[column], errors="coerce")
            source_map[metric] = source

# The 9-slider composition and weights are fixed from the user's Cowen dashboard reference.
COMPONENTS = [
    ("Puell Multiple", "puell_multiple", 1, "Miner issuance/revenue valuation"),
    ("MVRV", "mvrv", 1, "Market value relative to realised value"),
    ("MVRV Z-Score", "mvrv_z_score", 1, "Market-cap deviation from realised value"),
    ("Transaction Fees", "transaction_fees", 1, "On-chain transaction fee activity"),
    ("Terminal Price", "terminal_price", 1, "CDD-derived terminal valuation"),
    ("MCTC", "mctc", 1, "Market Cap / ThermoCap"),
    ("mCTC", "mctc_miner", 1, "Miner Cap / ThermoCap"),
    ("RHODL Ratio", "rhodl_ratio", 0, "Zero-weight diagnostic"),
    ("Supply in Profit / Loss", "supply_pnl", 0, "Zero-weight diagnostic"),
]

# Five-year rolling reference, strictly prior observations only. Cache the
# derived frame too: the rolling rank is the expensive part on slider/rerun events.
risk_frame = (
    cached_prior_risk_frame(series_map)
    if series_map
    else pd.DataFrame(index=raw.index)
)

latest_date = raw.index.max() if not raw.empty else None
# Completeness is measured on one common as-of date. Each card separately displays
# its own latest valid observation so a lagging provider does not hide its last value.
available_now = {
    metric: metric in risk_frame.columns and latest_date in risk_frame.index
    and pd.notna(risk_frame.loc[latest_date, metric])
    for _, metric, weight, _ in COMPONENTS if weight == 1
}
active_available = sum(available_now.values())
latest_raw = raw.loc[latest_date] if latest_date is not None else pd.Series(dtype=float)
metric_latest_dates = {
    metric: values.dropna().index.max()
    for metric, values in series_map.items() if values.notna().any()
}

c1, c2, c3, c4 = st.columns(4)
c1.metric("Active components available", f"{active_available} / 7")
c2.metric("Dashboard completeness", f"{active_available / 7:.0%}")
c3.metric("Latest source date", latest_date.strftime("%d %b %Y") if latest_date is not None else "Unavailable")
c4.metric("Composite score", "NOT CALCULATED")
st.caption("Completeness is assessed on the common latest source date. Cards show each metric's own latest valid date. No missing values are carried forward.")
with st.expander("Source freshness and acquisition health", expanded=True):
    st.caption("Freshness is based on retrieval timestamp (≤3 days) and latest observation date (≤2 days). This reports local snapshot metadata, not a live provider probe.")
    st.dataframe(onchain_source_health(), hide_index=True, use_container_width=True)


if load_error:
    st.error(f"Local source files could not be loaded: {load_error}")

st.subheader("Historical risk components")
st.caption("The layout follows Cowen's component-slider concept. Scores below are transparent five-year prior-only percentiles, not Cowen's proprietary slider transformations.")
for row_start in range(0, len(COMPONENTS), 3):
    cols = st.columns(3)
    for col, (label, metric, weight, description) in zip(cols, COMPONENTS[row_start:row_start + 3]):
        with col:
            if metric in series_map and metric in metric_latest_dates:
                metric_date = metric_latest_dates[metric]
                value = series_map[metric].loc[metric_date]
                score = risk_frame.loc[metric_date, metric] if metric in risk_frame else np.nan
                value_text = f"{value:,.3f}" if pd.notna(value) else "—"
                score_text = f"Historical risk percentile: {score:.0%}" if pd.notna(score) else "Risk percentile: building history"
                provenance = source_map.get(metric, "")
                if metric == "mvrv" and "mvrv_coinmetrics_crosscheck" in raw.columns:
                    cm_value = raw["mvrv_coinmetrics_crosscheck"].get(metric_date, np.nan)
                    if pd.notna(cm_value) and value != 0:
                        delta_pct = 100.0 * (cm_value / value - 1.0)
                        provenance += (
                            f" • Coin Metrics cross-check {cm_value:.3f} "
                            f"({delta_pct:+.2f}% vs Explore21)"
                        )
                if metric == "terminal_price" and "terminal_price_usd_candidate" in raw.columns:
                    terminal_usd = raw["terminal_price_usd_candidate"].get(metric_date, np.nan)
                    if pd.notna(terminal_usd):
                        provenance += f" • implied terminal price USD {terminal_usd:,.0f}"
                if metric == "mctc" and "thermocap_usd_candidate" in raw.columns:
                    thermocap_usd = raw["thermocap_usd_candidate"].get(metric_date, np.nan)
                    if pd.notna(thermocap_usd):
                        provenance += f" • reconstructed ThermoCap USD {thermocap_usd / 1e9:,.2f}B"
                    if "coinmetrics_thermocap_crosscheck" in raw.columns:
                        direct_thermocap = raw["coinmetrics_thermocap_crosscheck"].get(metric_date, np.nan)
                        diff = raw.get("thermocap_reconstruction_diff_pct", pd.Series(dtype=float)).get(metric_date, np.nan)
                        if pd.notna(direct_thermocap):
                            provenance += f" • Coin Metrics RevAllTimeUSD {direct_thermocap / 1e9:,.2f}B"
                        if pd.notna(diff):
                            provenance += f" • reconstruction difference {diff:+.2f}%"
                    fallback_count = raw.get(
                        "thermocap_fee_fallback_count", pd.Series(dtype=float)
                    ).get(metric_date, np.nan)
                    if pd.notna(fallback_count) and fallback_count > 0:
                        provenance += f" • source-backed fallback days {int(fallback_count)}"
                st.markdown(
                    f'<div class="metric-card"><div class="metric-name">{label} '
                    f'<span style="color:#7fa4b9">· weight {weight}</span></div>'
                    f'<div class="metric-value">{value_text}</div>'
                    f'<div class="metric-score">{score_text}</div>'
                    f'<div class="metric-foot">{provenance} • data through {metric_date:%d %b %Y}</div></div>',
                    unsafe_allow_html=True,
                )
            else:
                status = "ZERO-WEIGHT DIAGNOSTIC" if weight == 0 else "AWAITING VERIFIED DATA"
                st.markdown(
                    f'<div class="metric-card"><div class="metric-name">{label} '
                    f'<span style="color:#7fa4b9">· weight {weight}</span></div>'
                    f'<div class="metric-value pending">—</div>'
                    f'<div class="metric-score">{status}</div>'
                    f'<div class="metric-foot">{description}</div></div>',
                    unsafe_allow_html=True,
                )

# Cowen-style historical chart: nine component controls, dual-axis price/risk view.
# The seven active components are fixed at weight 1 by default; RHODL and Supply P/L
# remain visible as zero-weight diagnostics. Missing data never becomes a zero score.
st.subheader("On-Chain Metrics Historical Risk")

short_names = {
    "puell_multiple": "Puell",
    "mvrv": "MVRV",
    "mvrv_z_score": "MVRV Z",
    "transaction_fees": "Fees",
    "terminal_price": "Terminal",
    "mctc": "MCTC",
    "mctc_miner": "mCTC",
    "rhodl_ratio": "RHODL",
    "supply_pnl": "Supply P/L",
}
weight_values = {}
slider_cols = st.columns(9, gap="small")
for col, (label, metric, default_weight, _) in zip(slider_cols, COMPONENTS):
    with col:
        metric_available = metric in risk_frame.columns and risk_frame[metric].notna().any()
        # The experimental six-metric builder requires strictly positive
        # weights. Keep its six controls above zero; zero-weight diagnostics
        # retain the original 0–1 range.
        minimum_weight = 0.05 if metric in (
            "puell_multiple", "mvrv", "mvrv_z_score",
            "transaction_fees", "terminal_price", "mctc",
        ) else 0.0
        weight_values[metric] = st.slider(
            short_names.get(metric, label),
            min_value=minimum_weight,
            max_value=1.0,
            value=float(default_weight),
            step=0.05,
            key=f"cowen_weight_{metric}",
            disabled=(not metric_available and default_weight > 0),
            help=("Verified historical candidate series available." if metric_available
                  else "No eligible historical series yet; this component cannot contribute."),
        )

# Experimental six-metric composite; mCTC remains a separate missing seventh component.
SIX_METRICS = ("puell_multiple", "mvrv", "mvrv_z_score", "transaction_fees", "terminal_price", "mctc")
six_weights = {name: float(weight_values.get(name, 1.0)) for name in SIX_METRICS}
six_composite_history = build_six_metric_research_composite(risk_frame, weights=six_weights)
six_valid_history = six_composite_history["composite_risk"].dropna() if not six_composite_history.empty else pd.Series(dtype=float)
six_latest_date = six_valid_history.index.max() if not six_valid_history.empty else None
six_complete_now = six_latest_date is not None
if six_complete_now:
    latest_total = float(six_valid_history.loc[six_latest_date])
    st.metric("Experimental Six-Metric Risk", f"{latest_total:.3f}", help=f"Latest complete six-input date: {six_latest_date:%d %b %Y}")
else:
    st.metric("Experimental Six-Metric Risk", "INCOMPLETE")
    st.caption("All six component histories must overlap. No partial score is substituted.")
st.caption("Experimental equal-weight six-of-six score; excludes mCTC and is not Cowen's proprietary indicator. Research only; backtesting and forward validation required.")
control1, control2, control3 = st.columns([1, 1, 1.6])
with control1:
    renormalize_average = st.toggle(
        "Re-normalize Average", value=False, key="cowen_renormalize_average",
        help="When enabled, moving-average risk overlays are rescaled to the 0–1 risk axis.",
    )
with control2:
    moving_average = st.selectbox(
        "Moving Average", ["None", "7D", "30D", "90D", "365D"],
        index=0, key="cowen_moving_average",
    )
with control3:
    chart_type = st.radio(
        "Chart Type", ["Raw Values", "Colour-Coded"],
        horizontal=True, key="cowen_chart_type",
    )

import plotly.graph_objects as go
from plotly.subplots import make_subplots

fig = make_subplots(specs=[[{"secondary_y": True}]])
price_series = None
for price_col in ("coinmetrics_price_usd", "btc_price_usd", "price_usd"):
    if price_col in raw.columns and pd.to_numeric(raw[price_col], errors="coerce").notna().any():
        price_series = pd.to_numeric(raw[price_col], errors="coerce").dropna()
        break

metric_labels = {
    "puell_multiple": "Puell Multiple Risk",
    "mvrv": "MVRV Risk",
    "mvrv_z_score": "MVRV Z-Score Risk",
    "transaction_fees": "Transaction Fees Risk",
    "terminal_price": "Terminal Price Risk",
    "mctc": "MCTC Risk",
    "mctc_miner": "mCTC Risk",
    "rhodl_ratio": "RHODL Ratio Risk",
    "supply_pnl": "Supply P/L Risk",
}

available_chart_metrics = [
    metric for metric in metric_labels
    if metric in risk_frame.columns and risk_frame[metric].notna().any()
]
chart_view = st.selectbox(
    "Historical chart view",
    ["BTC price + six-metric risk", "BTC price + selected component", "Risk components (small multiples)"],
    index=0,
    key="cowen_chart_view",
    help="The default shows one risk series at a time to avoid overlapping noisy lines.",
)
selected_metric = st.selectbox(
    "Component to display",
    available_chart_metrics,
    format_func=lambda value: metric_labels[value].replace(" Risk", ""),
    key="cowen_selected_component",
    disabled=(not available_chart_metrics or chart_view != "BTC price + selected component"),
)



hover_risk_line = None
if price_series is not None:
    if chart_view == "BTC price + six-metric risk" and six_complete_now:
        hover_risk_line = six_composite_history["composite_risk"].dropna()
    elif chart_view == "BTC price + selected component" and selected_metric:
        hover_risk_line = risk_frame[selected_metric].dropna()
    price_custom = (
        [
            [f"${price:,.2f}", f"{risk:.3f}" if pd.notna(risk) else "n/a"]
            for price, risk in zip(
                price_series.to_numpy(),
                hover_risk_line.reindex(price_series.index).to_numpy(),
            )
        ]
        if hover_risk_line is not None else None
    )
    fig.add_trace(
        go.Scatter(
            x=price_series.index, y=price_series.values, name="BTC Price",
            mode="lines", line=dict(width=2.2, color="#168bd2"),
            customdata=price_custom,
            hovertemplate=(
                "%{x|%d %b %Y}<br>BTC Price: %{customdata[0]}<br>"
                "BTC Risk: %{customdata[1]}<extra></extra>"
            ) if price_custom is not None else
            "%{x|%d %b %Y}<br>BTC Price: $%{y:,.2f}<extra></extra>",
        ),
        secondary_y=False,
    )

if chart_view == "BTC price + six-metric risk" and six_complete_now:
    six_line = six_composite_history["composite_risk"].dropna()
    six_custom = historical_risk_hover_data(six_line, price_series) if price_series is not None else [["n/a", f"{value:.3f}"] for value in six_line.values]
    fig.add_trace(go.Scatter(x=six_line.index, y=six_line.values, name="Experimental Six-Metric Risk (6/6)", mode="lines", line=dict(width=2.4, color="#e56b72"), customdata=six_custom, hovertemplate="%{x|%d %b %Y}<br>BTC Price: %{customdata[0]}<br>BTC Risk: %{customdata[1]}<extra></extra>"), secondary_y=True)
elif chart_view == "BTC price + selected component" and selected_metric:
    values = risk_frame[selected_metric].dropna()
    component_custom = historical_risk_hover_data(values, price_series) if price_series is not None else [["n/a", f"{value:.3f}"] for value in values.values]
    fig.add_trace(
        go.Scatter(
            x=values.index, y=values.values,
            name=metric_labels[selected_metric],
            mode="lines",
            line=dict(width=2.0),
            customdata=component_custom,
            hovertemplate="%{x|%d %b %Y}<br>BTC Price: %{customdata[0]}<br>" + metric_labels[selected_metric] + ": %{customdata[1]}<extra></extra>",
        ),
        secondary_y=True,
    )
elif chart_view == "Risk components (small multiples)":
    st.caption("Each component has its own panel, with a shared date axis and 0–100% risk scale.")
    panel_cols = st.columns(2)
    for idx, metric in enumerate(available_chart_metrics):
        values = risk_frame[metric].dropna()
        with panel_cols[idx % 2]:
            mini = go.Figure(go.Scatter(
                x=values.index, y=values.values, mode="lines",
                name=metric_labels[metric], line=dict(width=1.6),
                hovertemplate="%{x|%d %b %Y}<br>%{y:.1%}<extra></extra>",
            ))
            mini.update_layout(
                template="plotly_dark", height=230,
                margin=dict(l=12, r=12, t=30, b=12),
                paper_bgcolor="#050505", plot_bgcolor="#050505",
                title=metric_labels[metric], showlegend=False,
            )
            mini.update_yaxes(range=[0, 1], tickformat=".0%")
            st.plotly_chart(mini, use_container_width=True, config={"displaylogo": False})

ma_days = {"7D": 7, "30D": 30, "90D": 90, "365D": 365}.get(moving_average)
if ma_days and price_series is not None:
    price_ma = price_series.rolling(ma_days, min_periods=ma_days).mean().dropna()
    fig.add_trace(
        go.Scatter(
            x=price_ma.index, y=price_ma.values,
            name=f"BTC Price {moving_average} MA",
            mode="lines", line=dict(width=1.5, dash="dot", color="#83bde2"),
        ),
        secondary_y=False,
    )
if ma_days and not six_composite_history.empty:
    # Use the same complete six-of-six score as the main chart; never average
    # a changing subset of components for the moving-average overlay.
    risk_ma = (
        six_composite_history["composite_risk"]
        .rolling(ma_days, min_periods=ma_days)
        .mean()
        .dropna()
    )
    if renormalize_average and not risk_ma.empty:
        lo, hi = float(risk_ma.min()), float(risk_ma.max())
        if hi > lo:
            risk_ma = (risk_ma - lo) / (hi - lo)
    if not risk_ma.empty:
        fig.add_trace(
            go.Scatter(
                x=risk_ma.index, y=risk_ma.values,
                name=f"Active risk {moving_average} MA",
                mode="lines", line=dict(width=1.8, dash="dash", color="#f2b35e"),
            ),
            secondary_y=True,
        )

if chart_type == "Colour-Coded":
    # Risk-zone bands echo Cowen's 0–1 gauge without implying proprietary colours.
    for y0, y1, fill in (
        (0.0, 0.1, "rgba(35,150,100,0.10)"),
        (0.1, 0.3, "rgba(70,140,190,0.08)"),
        (0.3, 0.5, "rgba(220,170,70,0.08)"),
        (0.5, 1.0, "rgba(210,75,85,0.08)"),
    ):
        fig.add_hrect(y0=y0, y1=y1, fillcolor=fill, line_width=0, secondary_y=True)

fig.update_layout(
    template="plotly_dark",
    height=460,
    margin=dict(l=42, r=42, t=28, b=48),
    paper_bgcolor="#050505",
    plot_bgcolor="#050505",
    font=dict(color="#d7dce2", size=11),
    legend=dict(orientation="h", yanchor="top", y=-0.16, x=0.0),
    hovermode="x unified",
    title=None,
)
fig.update_xaxes(
    title_text="Year", showgrid=True, gridcolor="rgba(150,150,150,0.15)",
    rangeslider_visible=False,
)
fig.update_yaxes(
    title_text="BTC Price (USD)", type="log", secondary_y=False,
    showgrid=True, gridcolor="rgba(150,150,150,0.15)",
)
fig.update_yaxes(
    title_text="Risk (0 = floor, 1 = top)", range=[0, 1],
    showgrid=False, secondary_y=True,
)
if chart_type == "Colour-Coded":
    fig.update_traces(selector=dict(name="BTC Price"), line=dict(color="#168bd2", width=2.5))
st.plotly_chart(fig, use_container_width=True, config={"displaylogo": False})

if price_series is None:
    st.info("BTC price history is not present in the currently loaded source snapshot.")
if not six_complete_now:
    st.warning(
        "The six-metric experimental score is not plotted because one or more inputs "
        "are not available for every date. Individual available risk histories "
        "remain visible; no partial composite is substituted. mCTC remains unavailable."
    )

st.subheader("Component readings and source provenance")
cards_cols = st.columns(3)
for idx, (label, metric, default_weight, description) in enumerate(COMPONENTS):
    col = cards_cols[idx % 3]
    with col:
        if metric in series_map and metric in metric_latest_dates:
            metric_date = metric_latest_dates[metric]
            value = series_map[metric].loc[metric_date]
            score = risk_frame.loc[metric_date, metric] if metric in risk_frame else np.nan
            value_text = f"{value:,.4f}" if pd.notna(value) else "—"
            score_text = f"Prior-only risk: {score:.1%}" if pd.notna(score) else "Risk history building"
            st.markdown(f"**{label}** · weight {weight_values.get(metric, default_weight):.2f}")
            st.metric("Latest raw value", value_text, help=source_map.get(metric, ""))
            st.caption(f"{score_text} · data through {metric_date:%d %b %Y}")
            st.caption(source_map.get(metric, description))
        else:
            st.markdown(f"**{label}** · weight {weight_values.get(metric, default_weight):.2f}")
            st.caption("Awaiting verified source data" if default_weight else "Zero-weight diagnostic; no source series")

with st.expander("Methodology, weights and data limitations", expanded=False):
    st.markdown("""
    **Active Cowen components (weight 1 each):** Puell Multiple, MVRV, MVRV Z-Score,
    Transaction Fees, Terminal Price, MCTC and mCTC.

    **Zero-weight diagnostics:** RHODL Ratio and Supply in Profit/Loss. They are shown
    for visual completeness but do not contribute to the active composite.

    **What is currently populated:** Explore21 provides daily Puell Multiple (method v1),
    MVRV ratio (method v2) and MVRV Z-Score (method v1), all CC BY 4.0 with source
    attribution in the snapshot metadata. Aethereal provides a separate daily total-fees
    series in BTC/day, free for research and education; it is a candidate, not a verified
    Cowen source. Coin Metrics Community provides an independent market-cap MVRV
    cross-check and BTC issuance, price and supply. Coin Metrics Community is CC BY-NC 4.0
    and is not suitable for commercial redistribution. Explore21's pre-18 Nov 2026
    historical rows are not verified point-in-time vintages.

    **Percentile method:** each observation is ranked against up to the preceding
    1,825 daily observations; at least 365 prior observations are required. Today's
    observation is excluded from its own reference distribution. Missing values are
    not filled. Direction is provisionally higher = higher risk for these three
    candidates and remains subject to source/formula review.

    **Not yet displayed as scores:** Transaction Fees, Terminal Price, MCTC and mCTC
    Transaction Fees is displayed as an Aethereal BTC/day candidate, but its exact
    Cowen transformation and direction still need validation. Terminal Price is shown
    as a partial-history price/terminal-price ratio candidate using Open Bitcoin Metrics
    CDD and Coin Metrics price/supply. Its cumulative history begins on the first common
    valid Coin Metrics date (2010-07-18), not genesis. MCTC is now a transparent
    reconstruction from cumulative daily issuance USD plus fees BTC valued at the
    Coin Metrics daily close, divided into market cap; its ThermoCap variant still needs
    parity checking against the uploaded provider history. mCTC remains unavailable
    pending a defensible miner-entity series.
    """)

st.caption("Research 10.0 • Cowen On-Chain Risk • isolated from Production and V5.9 • no trade execution")
