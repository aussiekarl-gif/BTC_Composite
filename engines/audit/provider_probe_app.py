"""Streamlit UI for read-only provider capability and entitlement probes."""
import pandas as pd
import streamlit as st

from engines.audit.provider_probe import (
    run_provider_probes,
    run_coinglass_entitlement_probe,
    run_cryptoquant_catalogue_probe,
)

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
        st.dataframe(pd.DataFrame({"btc_endpoint_path":paths}), use_container_width=True, hide_index=True)
    st.caption("This reads endpoint names only. It does not call each CryptoQuant metric endpoint or consume on-chain data history.")
