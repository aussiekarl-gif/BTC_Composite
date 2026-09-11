"""Streamlit UI for the read-only provider capability probe."""
import pandas as pd
import streamlit as st

from engines.audit.provider_probe import run_provider_probes

st.title("BTC Data Provider Capability Probe")
st.caption(
    "Read-only diagnostic. It does not change Production, Research, the central BTC database, "
    "or any strategy setting. Secret values are never displayed."
)

st.info(
    "This makes at most one lightweight request to each enabled provider. "
    "CoinGlass tests Puell Multiple, CryptoQuant tests API discovery, CoinGecko tests its Demo ping, "
    "and Kotecharts is presence-only until its authenticated endpoint contract is verified."
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
    st.warning(
        "A blocked result only describes the tested endpoint/plan. It does not prove that every endpoint from that provider is unavailable."
    )
else:
    st.caption("No provider requests have been made yet.")
