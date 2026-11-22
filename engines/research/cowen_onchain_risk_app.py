"""Cowen-style On-Chain Metrics Historical Risk research dashboard.

This is a visual research replica, not Cowen's proprietary indicator. It shows
only data that exists locally, labels proxy series, and never emits a trade signal.
"""
from pathlib import Path
import sys

import numpy as np
import pandas as pd
import streamlit as st

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from engines.research.cowen_onchain_risk import (
    ACTIVE_METRICS,
    ZERO_WEIGHT_DIAGNOSTICS,
    build_existing_raw_candidates,
    prior_only_percentile_risk,
)

st.markdown("""
<style>
.cowen-wrap {background:linear-gradient(135deg,#101d2b,#152b3d);border:1px solid #294b62;
 border-radius:14px;padding:18px 22px;margin:4px 0 18px 0}
.cowen-kicker {color:#91b8cc;font-size:12px;letter-spacing:1.8px;text-transform:uppercase;font-weight:700}
.cowen-heading {color:#f4f8fb;font-size:30px;font-weight:800;margin:3px 0}
.cowen-sub {color:#b8cbd8;font-size:13px}
.metric-card {background:#0b2030;border:1px solid #24465d;border-radius:12px;padding:13px 15px;
 min-height:132px;margin-bottom:10px}
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
 <div class="cowen-sub">Standalone on-chain risk research page • seven active metrics • two zero-weight diagnostics</div>
</div>
""", unsafe_allow_html=True)

st.warning(
    "RESEARCH DISPLAY ONLY — this is not Benjamin Cowen's live indicator and does not "
    "reproduce its proprietary transformations. No DCA, buy or sell signal is generated. "
    "Missing components are left missing; no partial composite is presented as a risk score."
)

DATA_DIR = ROOT / "data"
try:
    raw = build_existing_raw_candidates(DATA_DIR)
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

risk_frame = pd.DataFrame(index=raw.index) if not raw.empty else pd.DataFrame()
for metric, values in series_map.items():
    # Five-year rolling reference, strictly prior observations only.
    risk_frame[metric] = prior_only_percentile_risk(
        values, window_observations=1825, min_prior_observations=365,
        higher_is_riskier=True,
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

st.subheader("Historical component history")
if not risk_frame.empty:
    choices = [m for m in risk_frame.columns if risk_frame[m].notna().any()]
    labels = {
        "puell_multiple": "Puell Multiple",
        "mvrv": "MVRV (PlanB realised-price proxy)",
        "mvrv_z_score": "MVRV Z-Score (saved provider export)",
    }
    selected = st.multiselect(
        "Display components", choices, default=choices,
        format_func=lambda x: labels.get(x, x),
    )
    if selected:
        chart = (risk_frame[selected] * 100).rename(columns=labels)
        st.line_chart(chart, y_label="Prior-only historical risk percentile (0–100)")
    else:
        st.info("Select at least one component to display its history.")
else:
    st.info("No eligible historical component series are currently available.")

with st.expander("Methodology, weights and data limitations", expanded=False):
    st.markdown("""
    **Active Cowen components (weight 1 each):** Puell Multiple, MVRV, MVRV Z-Score,
    Transaction Fees, Terminal Price, MCTC and mCTC.

    **Zero-weight diagnostics:** RHODL Ratio and Supply in Profit/Loss. They are shown
    for visual completeness but do not contribute to the active composite.

    **What is currently populated:** Explore21 provides daily Puell Multiple (method v1),
    MVRV ratio (method v2) and MVRV Z-Score (method v1), all CC BY 4.0 with source
    attribution in the snapshot metadata. Coin Metrics Community provides an independent
    market-cap MVRV cross-check and BTC issuance, price and supply. Coin Metrics Community
    is CC BY-NC 4.0 and is not suitable for commercial redistribution. Explore21's
    pre-18 Nov 2026 historical rows are not verified point-in-time vintages.

    **Percentile method:** each observation is ranked against up to the preceding
    1,825 daily observations; at least 365 prior observations are required. Today's
    observation is excluded from its own reference distribution. Missing values are
    not filled. Direction is provisionally higher = higher risk for these three
    candidates and remains subject to source/formula review.

    **Not yet displayed as scores:** Transaction Fees, Terminal Price, MCTC and mCTC
    remain unavailable in this dashboard until source series and formulas are validated.
    The MCTC/ThermoCap snapshot and CDD inputs are separate outstanding data tasks; mCTC
    remains unresolved.
    """)

st.caption("Research 10.0 • Cowen On-Chain Risk • isolated from Production and V5.9 • no trade execution")
