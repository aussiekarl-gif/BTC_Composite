"""Streamlit UI for read-only provider capability and entitlement probes."""
import pandas as pd
import streamlit as st

from engines.audit.provider_probe import (
    run_provider_probes,
    run_coinglass_entitlement_probe,
    run_cryptoquant_catalogue_probe,
)
from engines.audit.provider_source_matrix import source_matrix_df, relevant_cryptoquant_paths
from engines.audit.coinglass_staging import collect_specialist_history, save_staging_csv

st.title("BTC Data Provider Capability Probe")
st.caption(
    "Read-only diagnostics. Nothing here changes Production, Research, the central BTC database, "
    "or any strategy setting. Secret values are never displayed."
)

st.info(
    "Basic capability makes at most one lightweight request to each enabled provider. "
    "Dataset entitlement tests are separate and run only when you explicitly press their buttons."
)

if st.button("RUN PROVIDER CAPABILITY PROBE", type="primary"):
    with st.spinner("Checking configured provider access..."):
        rows = run_provider_probes(st)
    st.session_state["provider_probe_rows"] = rows

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

col1,col2=st.columns(2)
with col1:
    if st.button("MAP COINGLASS BTC DATASET ACCESS"):
        with st.spinner("Testing selected CoinGlass BTC datasets..."):
            st.session_state["coinglass_entitlement_rows"] = run_coinglass_entitlement_probe(st)
with col2:
    if st.button("READ CRYPTOQUANT ENDPOINT CATALOGUE"):
        with st.spinner("Reading CryptoQuant endpoint catalogue..."):
            st.session_state["cryptoquant_catalogue"] = run_cryptoquant_catalogue_probe(st)

cg_rows=st.session_state.get("coinglass_entitlement_rows")
if cg_rows:
    st.markdown("**CoinGlass selected BTC datasets**")
    cgdf=pd.DataFrame(cg_rows)
    st.dataframe(cgdf, use_container_width=True, hide_index=True)
    st.caption("Stops immediately if CoinGlass returns HTTP 429; no automatic retry.")

cq=st.session_state.get("cryptoquant_catalogue")
if cq:
    st.markdown("**CryptoQuant discovery catalogue**")
    st.write({k:v for k,v in cq.items() if k != "btc_paths"})
    paths=cq.get("btc_paths") or []
    if paths:
        relevant = relevant_cryptoquant_paths(paths)
        if not relevant.empty:
            st.markdown("**CryptoQuant BTC endpoints relevant to our audit**")
            st.dataframe(relevant, use_container_width=True, hide_index=True)
        with st.expander("Show all CryptoQuant BTC endpoint paths", expanded=False):
            st.dataframe(pd.DataFrame({"btc_endpoint_path":paths}), use_container_width=True, hide_index=True)
    st.caption("This reads endpoint names only. It does not call each CryptoQuant metric endpoint or consume on-chain data history.")

st.divider()
st.subheader("Research source-priority matrix")
st.caption(
    "Planning only. This records the acquisition order we will use for Audit/Research: self-calculated/free first, "
    "then verified alternate providers, then BGeometrics only where needed. It does not switch Production."
)
st.dataframe(source_matrix_df(), use_container_width=True, hide_index=True)
st.info(
    "Production-source MVRV-Z and Fear & Greed remain protected by parity requirements. "
    "An alternate provider is not allowed to silently replace the exact Production source."
)

st.divider()
st.subheader("CoinGlass specialist staging")
st.caption(
    "This collects only specialist datasets where CoinGlass is now our preferred research source: STH/LTH SOPR, "
    "STH/LTH realized price, RHODL, STH/LTH supply and Reserve Risk. Results are written only to "
    "btc-audit-data/staging/coinglass_specialist.csv — never to the authoritative master and never to Production."
)
if st.button("COLLECT + SAVE COINGLASS SPECIALIST STAGING", type="secondary"):
    with st.spinner("Collecting CoinGlass specialist history and saving non-authoritative staging data..."):
        frame, statuses = collect_specialist_history(st)
        save_status = save_staging_csv(st, frame)
    st.session_state["coinglass_staging_statuses"] = statuses
    st.session_state["coinglass_staging_save_status"] = save_status
    st.session_state["coinglass_staging_shape"] = tuple(frame.shape) if frame is not None else (0, 0)

staging_statuses = st.session_state.get("coinglass_staging_statuses")
if staging_statuses:
    st.dataframe(pd.DataFrame(staging_statuses), use_container_width=True, hide_index=True)
    shape = st.session_state.get("coinglass_staging_shape", (0, 0))
    st.caption(f"Parsed staging shape: {shape[0]:,} dates × {shape[1]} provider columns")
    save_status = st.session_state.get("coinglass_staging_save_status", "")
    if save_status.startswith("SAVED + VERIFIED"):
        st.success(save_status)
    else:
        st.warning(save_status or "Staging save status unavailable")
