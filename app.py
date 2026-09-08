#!/usr/bin/env python3
"""BTC Dynamic DCA launcher — Research, Production control, and Public Model Audit."""
from pathlib import Path
import streamlit as st

st.set_page_config(page_title="BTC Dynamic DCA", layout="wide")

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
</style>
""", unsafe_allow_html=True)

section = st.sidebar.selectbox(
    "App section",
    ["V5.9 Research", "V5.8.2 Production", "Public Model Audit"],
    index=0,
    key="combined_app_section_selector",
    help=(
        "V5.9 Research is the working development version. "
        "V5.8.2 Production remains the frozen control. "
        "Public Model Audit screens external/public Bitcoin models before any idea is allowed into Research."
    ),
)

engine_folder = {
    "V5.9 Research": "research",
    "V5.8.2 Production": "production",
    "Public Model Audit": "audit",
}[section]

engine_path = Path(__file__).parent / "engines" / engine_folder / "app.py"
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
