"""Streamlit UI for read-only provider capability and entitlement probes."""
import pandas as pd
import streamlit as st

from engines.audit.provider_probe import (
    run_provider_probes, run_coinglass_entitlement_probe,
    run_cryptoquant_catalogue_probe, run_cryptoquant_targeted_entitlement_probe,
)
from engines.audit.provider_source_matrix import source_matrix_df, relevant_cryptoquant_paths

st.title("BTC Data Provider Capability Probe")
st.caption("Read-only diagnostics. Nothing here changes Production, Research, the central BTC database, or any strategy setting. Secret values are never displayed.")
st.info("Basic capability makes at most one lightweight request to each enabled provider. Dataset entitlement tests are separate and run only when you explicitly press their buttons.")

if st.button("RUN PROVIDER CAPABILITY PROBE", type="primary"):
    with st.spinner("Checking configured provider access..."):
        st.session_state["provider_probe_rows"] = run_provider_probes(st)
rows = st.session_state.get("provider_probe_rows")
if rows:
    df = pd.DataFrame(rows)
    st.dataframe(df, use_container_width=True, hide_index=True)
    accessible = int((df["status"] == "ACCESSIBLE").sum()) if "status" in df else 0
    configured = int(df["configured"].sum()) if "configured" in df else 0
    st.caption(f"Configured providers checked: {configured}. Accessible probe endpoints: {accessible}.")
    st.warning("A blocked result only describes the tested endpoint/plan; it does not prove every endpoint from that provider is unavailable.")
else:
    st.caption("No provider requests have been made yet.")

st.divider()
st.subheader("Dataset entitlement mapping")
st.caption("These checks are read-only and provider-specific. They do not write any returned data to the central database.")
col1, col2 = st.columns(2)
with col1:
    if st.button("MAP COINGLASS BTC DATASET ACCESS"):
        with st.spinner("Testing selected CoinGlass BTC datasets..."):
            st.session_state["coinglass_entitlement_rows"] = run_coinglass_entitlement_probe(st)
with col2:
    if st.button("READ CRYPTOQUANT ENDPOINT CATALOGUE"):
        with st.spinner("Reading CryptoQuant endpoint catalogue..."):
            st.session_state["cryptoquant_catalogue"] = run_cryptoquant_catalogue_probe(st)

cg_rows = st.session_state.get("coinglass_entitlement_rows")
if cg_rows:
    st.markdown("**CoinGlass selected BTC datasets**")
    st.dataframe(pd.DataFrame(cg_rows), use_container_width=True, hide_index=True)
    st.caption("Stops immediately if CoinGlass returns HTTP 429; no automatic retry.")

cq = st.session_state.get("cryptoquant_catalogue")
if cq:
    st.markdown("**CryptoQuant discovery catalogue**")
    st.write({k: v for k, v in cq.items() if k != "btc_paths"})
    paths = cq.get("btc_paths") or []
    if paths:
        relevant = relevant_cryptoquant_paths(paths)
        if not relevant.empty:
            st.markdown("**CryptoQuant BTC endpoints relevant to our audit**")
            st.dataframe(relevant, use_container_width=True, hide_index=True)
        if st.button("TEST CRYPTOQUANT TARGETED DATA ACCESS"):
            with st.spinner("Testing at most 12 catalogue-confirmed CryptoQuant audit endpoints..."):
                st.session_state["cryptoquant_targeted_rows"] = run_cryptoquant_targeted_entitlement_probe(st, paths)
        with st.expander("Show all CryptoQuant BTC endpoint paths", expanded=False):
            st.dataframe(pd.DataFrame({"btc_endpoint_path": paths}), use_container_width=True, hide_index=True)
    st.caption("Catalogue reads endpoint names only. Targeted access testing is bounded to at most 12 minimal requests and stops on HTTP 429.")

cq_targeted = st.session_state.get("cryptoquant_targeted_rows")
if cq_targeted:
    st.markdown("**CryptoQuant targeted entitlement results**")
    st.dataframe(pd.DataFrame(cq_targeted), use_container_width=True, hide_index=True)

st.divider()
st.subheader("Research source-priority matrix")
st.caption("Planning only. Audit/Research uses self-calculated/free first, then verified alternate providers, then BGeometrics only where needed. It does not switch Production.")
st.dataframe(source_matrix_df(), use_container_width=True, hide_index=True)
st.info("Production-source MVRV-Z and Fear & Greed remain protected by parity requirements. An alternate provider is not allowed to silently replace the exact Production source.")
