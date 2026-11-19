"""Streamlit dashboard for the isolated V6.0 200WMA research programme.

No portfolio, broker, order, notification or Production integration.
"""
import json
from pathlib import Path

import pandas as pd
import streamlit as st

from engines.research.v60_200wma_policy import (
    CANDIDATE_LADDERS,
)

st.title("Bitcoin Dynamic DCA V6.0 — 200WMA Research")
st.caption("Independent Research • 200-week valuation • Percentage-based accumulation")

st.warning(
    "Research only — V6.0 is not approved for live investing. "
    "This screen does not issue a buy/sell recommendation, read your portfolio, "
    "or connect to a broker."
)

st.subheader("Research design")
st.write(
    "The 200-week moving average is the primary valuation reference. "
    "A normal 2.5% base DCA remains active above and around the average; "
    "the model does not wait for BTC to fall below the 200WMA before buying. "
    "Deeper discounts increase the percentage of deployable cash used."
)

rows = []
for name, ladder in CANDIDATE_LADDERS.items():
    rows.append({
        "Candidate": name.replace("_", " ").title(),
        "Normal": f"{ladder[0]:.1f}%",
        "20% below": f"{ladder[1]:.1f}%",
        "25% below": f"{ladder[2]:.1f}%",
        "30% below": f"{ladder[3]:.1f}%",
    })
st.subheader("Candidate allocation ladders")
st.dataframe(pd.DataFrame(rows), hide_index=True, width="stretch")
st.caption(
    "Percentages apply to deployable cash, not fixed AUD amounts. "
    "These are research hypotheses, not selected settings."
)

st.subheader("Cash protection")
st.write(
    "Protected-cash floors of 0%, 10%, 20% and 30% of initial cash are "
    "tested separately from the allocation ladder. A separate weekly hard "
    "cap of 5% of original capital remains in the replay."
)

SNAPSHOT_PATH = (
    Path(__file__).resolve().parents[2]
    / "data" / "research_forward_validation"
    / "v60_dashboard_snapshot_2026-11-19.json"
)
snapshot = json.loads(SNAPSHOT_PATH.read_text(encoding="utf-8"))
historical = snapshot["historical_replay"]
stress = snapshot["synthetic_stress"]

st.subheader("Historical holdout snapshot")
st.caption(
    f"BTC data cutoff {historical['btc_last_observation_date']} • "
    f"{historical['holdout_cohort_count']} overlapping 104-week holdout windows • "
    "5% gross cash-yield scenario • no protected-cash floor"
)
comparison_rows = []
for label, key in (
    ("Reference 20/25/30", "measured_ladder_holdout"),
    ("Sensitivity 10/15/20", "measured_ladder_10_15_20_holdout"),
):
    item = historical[key]
    comparison_rows.append({
        "Policy": label,
        "Median final AUD uplift vs fixed DCA": f"{item['median_final_equity_uplift_vs_fixed_pct']:+.2f}%",
        "Median BTC-unit uplift vs fixed DCA": f"{item['median_btc_units_uplift_vs_fixed_pct']:+.2f}%",
        "Cohort wins": f"{item['cohort_win_rate_final_equity_pct']:.1f}%",
    })
st.dataframe(pd.DataFrame(comparison_rows), hide_index=True, width="stretch")
st.warning(
    "The discount tiers did not activate at all during 2017–2021. "
    "In the 2022-onward holdout they activated only 24 / 16 / 9 weeks at "
    "10% / 15% / 20% discounts. The 20% and 25% thresholds were reached "
    "on the same nine weeks; all observed tier activations were in 2022–2023. "
    "The rolling cohorts overlap and are not independent tests."
)

st.subheader("Severe-bear stress warning")
st.write(
    "In a synthetic 104-week 70% decline, the measured 20/25/30 policy "
    f"returned {stress['measured_20_25_30']['no_reserve_return_pct']:.1f}% "
    "with no reserve, versus "
    f"{stress['fixed_weekly']['no_reserve_return_pct']:.1f}% for fixed weekly DCA. "
    "With a 30% protected-cash floor, the outcomes were "
    f"{stress['measured_20_25_30']['reserve_30_pct_return_pct']:.1f}% and "
    f"{stress['fixed_weekly']['reserve_30_pct_return_pct']:.1f}% respectively."
)
st.caption(
    "A 40% cumulative-spend cap nearly matched fixed DCA in the synthetic bear "
    "but reduced the measured policy's rapid-V recovery result. No reserve or "
    "cumulative cap has been selected."
)

st.subheader("Validation status")
st.info(
    "Historical replay and synthetic stress testing are complete. "
    "Cumulative deployment pacing remains under research, and prospective "
    "V6.0 paper validation has not yet started. No candidate is approved "
    "for live investing."
)
st.caption(
    "The replay uses a next-Monday BTC/AUD spot proxy, not an ASX:IBIT fill. "
    "Cash yield is gross and not tax-adjusted; actual ASX spreads, brokerage, "
    "tax and personal cash flows are not fully modelled. "
    "V5.9 remains archived with its code, reports and paper tapes preserved. "
    "Production V5.8.2 remains frozen."
)

# A deliberate machine-readable label for navigation/safety regression tests.
trade_executable = False
st.caption(f"Trade executable: {trade_executable}")
