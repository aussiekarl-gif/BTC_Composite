"""Streamlit dashboard for the isolated V6.0 200WMA research programme.

No portfolio, broker, order, notification or Production integration.
"""
import pandas as pd
import streamlit as st

from engines.research.v60_200wma_policy import (
    CANDIDATE_LADDERS, DISCOUNT_THRESHOLDS_PCT,
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

st.subheader("Validation status")
st.info(
    "The isolated policy and matched weekly replay engines are in place. "
    "Historical matched-cohort results, stress testing and prospective "
    "V6.0 paper validation are still required before any candidate can be "
    "considered for use."
)
st.caption(
    "The replay uses a next-Monday BTC/AUD spot proxy, not an ASX:IBIT fill. "
    "V5.9 remains archived with its code, reports and paper tapes preserved. "
    "Production V5.8.2 remains frozen."
)

# A deliberate machine-readable label for navigation/safety regression tests.
trade_executable = False
st.caption(f"Trade executable: {trade_executable}")
