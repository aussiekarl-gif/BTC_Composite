#!/usr/bin/env python3
"""BTC Dynamic DCA launcher — streamlined everyday UI with optional maintenance tools."""
from pathlib import Path
import streamlit as st

from engines.audit.bgeometrics_guard import (
    guard_status,
    install_bgeometrics_guard,
    uninstall_bgeometrics_guard,
)

st.set_page_config(
    page_title="BTC Dynamic DCA",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Shared top chrome/theme fix. Applied before any engine widgets render.
st.markdown("""
<style>
html, body, [data-testid="stAppViewContainer"], .stApp { background:#071521 !important; }
header[data-testid="stHeader"], [data-testid="stHeader"], .stAppHeader, [data-testid="stAppHeader"] {
    display:none !important; visibility:hidden !important; height:0 !important; min-height:0 !important;
    background:#071521 !important;
}
.stAppToolbar, [data-testid="stToolbar"], [data-testid="stAppToolbar"], [data-testid="stDecoration"], #MainMenu {
    display:none !important; visibility:hidden !important; height:0 !important;
}
[data-testid="stMain"], .main { background:#071521 !important; padding-top:0 !important; margin-top:0 !important; }
[data-testid="stMainBlockContainer"], [data-testid="stAppViewBlockContainer"], .block-container {
    padding-top:.45rem !important; margin-top:0 !important;
}
header, [class*="stAppHeader"] { background:#071521 !important; }
:root, html, body, #root {
    --header-height: 0rem !important;
    background: #071521 !important;
    margin: 0 !important;
    padding: 0 !important;
}
#root, #root > div, .stApp, [data-testid="stAppViewContainer"] {
    background: #071521 !important;
    margin-top: 0 !important;
    padding-top: 0 !important;
    top: 0 !important;
}
header[data-testid="stHeader"], [data-testid="stHeader"], .stAppHeader,
[data-testid="stAppHeader"], .stAppToolbar, [data-testid="stToolbar"],
[data-testid="stAppToolbar"], [data-testid="stDecoration"], #MainMenu {
    display: none !important;
    visibility: hidden !important;
    position: absolute !important;
    top: 0 !important;
    height: 0 !important;
    min-height: 0 !important;
    max-height: 0 !important;
    margin: 0 !important;
    padding: 0 !important;
    border: 0 !important;
}
.stMain, [data-testid="stMain"], main, section.main {
    background: #071521 !important;
    margin-top: 0 !important;
    padding-top: 0 !important;
    top: 0 !important;
}
[data-testid="stMainBlockContainer"], [data-testid="stAppViewBlockContainer"],
.main .block-container, .block-container {
    margin-top: 0 !important;
    padding-top: 0.35rem !important;
}
[data-testid="stAppViewContainer"] > div,
[data-testid="stAppViewContainer"] > section {
    background-color: #071521 !important;
}
/* Keep Streamlit's sidebar recovery control available.
   The launcher lives in the sidebar, so hiding the header must never strand a
   user after the sidebar is collapsed (Streamlit 1.50+ moved the reopen
   control into the header). */
header[data-testid="stHeader"], [data-testid="stHeader"], .stAppHeader,
[data-testid="stAppHeader"] {
    display: block !important;
    visibility: visible !important;
    position: fixed !important;
    top: 0 !important;
    height: 3rem !important;
    min-height: 3rem !important;
    max-height: 3rem !important;
    background: transparent !important;
    pointer-events: none !important;
}
[data-testid="stSidebarCollapsedControl"],
[data-testid="collapsedControl"] {
    display: flex !important;
    visibility: visible !important;
    opacity: 1 !important;
    pointer-events: auto !important;
}

</style>
""", unsafe_allow_html=True)

# Everyday sections stay visible. Diagnostic/maintenance pages remain available
# behind one opt-in toggle so we keep the tools without cluttering the normal UI.
primary_sections = [
    "V5.8.2 Production",
    "V5.9 Research",
    "Bottom Signal Timeline",
]
maintenance_sections = [
    "Public Model Audit",
    "Provider Capability Probe",
    "Central Data Parity",
]

show_maintenance = st.sidebar.toggle(
    "Show maintenance tools",
    value=False,
    help="Show audit, provider and data-parity diagnostics. These tools do not change Production sizing.",
)

section_options = primary_sections + (maintenance_sections if show_maintenance else [])
section = st.sidebar.selectbox(
    "App section",
    section_options,
    index=0,
    key="combined_app_section_selector",
    help=(
        "V5.8.2 Production is the frozen live model. "
        "V5.9 Research is the working development version. "
        "Bottom Signal Timeline visualises historical multi-indicator states. "
        "Enable maintenance tools only when audit/provider/parity diagnostics are needed."
    ),
)

if section == "Public Model Audit":
    install_bgeometrics_guard(st)
    active, text = guard_status(st)
    if active:
        st.warning(text)
else:
    # Never let the research quota wrapper leak into Production/Research/Timeline/Parity sections.
    uninstall_bgeometrics_guard()

engine_path = {
    "V5.8.2 Production": Path(__file__).parent / "engines" / "production" / "production_app.py",
    "V5.9 Research": Path(__file__).parent / "engines" / "research" / "research_app.py",
    "Bottom Signal Timeline": Path(__file__).parent / "engines" / "audit" / "bottom_signal_timeline_app.py",
    "Public Model Audit": Path(__file__).parent / "engines" / "audit" / "public_model_audit.py",
    "Provider Capability Probe": Path(__file__).parent / "engines" / "audit" / "provider_probe_app.py",
    "Central Data Parity": Path(__file__).parent / "engines" / "shared" / "parity_app.py",
}[section]

if not engine_path.exists():
    st.error(f"Missing engine file: {engine_path}")
    st.stop()

engine_globals = {
    "__name__": "__main__",
    "__file__": str(engine_path),
    "__package__": None,
}
code = compile(engine_path.read_text(encoding="utf-8"), str(engine_path), "exec")
exec(code, engine_globals)
