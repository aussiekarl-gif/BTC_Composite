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

/* Sidebar fail-safe: the installed Streamlit build places its sidebar control
   inside the toolbar. Keep the native header/toolbar interactive so the
   sidebar can always be opened and closed. */
header[data-testid="stHeader"], [data-testid="stHeader"], .stAppHeader,
[data-testid="stAppHeader"] {
    display: block !important;
    visibility: visible !important;
    pointer-events: auto !important;
}
.stAppToolbar, [data-testid="stToolbar"], [data-testid="stAppToolbar"] {
    display: flex !important;
    visibility: visible !important;
    position: relative !important;
    top: auto !important;
    width: auto !important;
    height: auto !important;
    min-height: 0 !important;
    max-height: none !important;
    opacity: 1 !important;
    pointer-events: auto !important;
}
[data-testid="stSidebarCollapsedControl"],
[data-testid="collapsedControl"],
button[data-testid="stSidebarCollapseButton"] {
    display: flex !important;
    visibility: visible !important;
    opacity: 1 !important;
    pointer-events: auto !important;
}

/* Phone layout for all four dashboards. Desktop columns remain unchanged.
   Avoid forcing full desktop-width KPI rows on a narrow Android viewport. */
@media (max-width: 767px) {
  html, body, #root, .stApp, [data-testid="stAppViewContainer"],
  [data-testid="stMain"], [data-testid="stMainBlockContainer"],
  [data-testid="stAppViewBlockContainer"] {
    max-width: 100% !important;
    overflow-x: clip !important;
  }
  [data-testid="stMainBlockContainer"], [data-testid="stAppViewBlockContainer"],
  .main .block-container, .block-container {
    width: 100% !important;
    max-width: 100% !important;
    padding-left: .7rem !important;
    padding-right: .7rem !important;
  }
  /* Streamlit's horizontal columns must stack on phones. */
  [data-testid="stHorizontalBlock"] {
    flex-wrap: wrap !important;
    gap: .65rem !important;
    min-width: 0 !important;
  }
  [data-testid="stHorizontalBlock"] > [data-testid="stColumn"] {
    flex: 1 1 100% !important;
    width: 100% !important;
    min-width: 0 !important;
    max-width: 100% !important;
  }
  [data-testid="stMetric"], [data-testid="stMetric"] > div {
    min-width: 0 !important;
    max-width: 100% !important;
  }
  [data-testid="stMetricValue"] {
    font-size: clamp(1.45rem, 7vw, 2rem) !important;
    line-height: 1.25 !important;
    overflow-wrap: anywhere !important;
    white-space: normal !important;
  }
  [data-testid="stMetricLabel"] {
    white-space: normal !important;
    overflow-wrap: anywhere !important;
  }
  /* Tables retain horizontal scroll INSIDE their own container. */
  [data-testid="stDataFrame"], [data-testid="stTable"],
  [data-testid="stPlotlyChart"], [data-testid="stVegaLiteChart"] {
    max-width: 100% !important;
    min-width: 0 !important;
  }
  [data-testid="stTable"] { overflow-x: auto !important; }
  h1 { font-size: clamp(1.55rem, 7vw, 2rem) !important; overflow-wrap: anywhere; }
  h2 { font-size: clamp(1.3rem, 6vw, 1.65rem) !important; overflow-wrap: anywhere; }
}

/* Streamlit may expose a ~980px layout viewport on Android when the browser
   requests desktop rendering. Handle that viewport too, and never ellipsize
   financial KPI numbers. These rules are presentation-only. */
@media (max-width: 1100px) {
  [data-testid="stHorizontalBlock"] {
    flex-wrap: wrap !important;
    align-items: stretch !important;
  }
  [data-testid="stHorizontalBlock"] > [data-testid="stColumn"],
  [data-testid="stHorizontalBlock"] > div[data-testid="column"] {
    flex: 1 1 100% !important;
    flex-grow: 1 !important;
    flex-shrink: 1 !important;
    flex-basis: 100% !important;
    width: 100% !important;
    min-width: 0 !important;
    max-width: 100% !important;
  }
  [data-testid="stMetric"] {
    width: 100% !important;
    max-width: 100% !important;
    min-width: 0 !important;
    height: auto !important;
  }
  [data-testid="stMetricLabel"],
  [data-testid="stMetricLabel"] *,
  [data-testid="stMetricValue"],
  [data-testid="stMetricValue"] *,
  [data-testid="stMetricDelta"],
  [data-testid="stMetricDelta"] * {
    white-space: normal !important;
    overflow: visible !important;
    text-overflow: clip !important;
    overflow-wrap: anywhere !important;
    word-break: normal !important;
    max-width: 100% !important;
  }
  [data-testid="stMetricValue"] {
    font-size: clamp(1.35rem, 3vw, 2rem) !important;
    line-height: 1.3 !important;
  }
  [data-testid="stMainBlockContainer"], .block-container {
    min-width: 0 !important;
    max-width: 100% !important;
  }
}

</style>
""", unsafe_allow_html=True)

# Keep each strategy independently selectable. Production remains the default
# and unchanged; research pages remain isolated from Production.
MODEL_SELECTOR_KEY = "combined_app_section_selector"
MODEL_OPTIONS = [
    "Production",
    "Research 10.0",
    "Cycle Trading — Research",
    "Bottom Signal Timeline",
]
# Streamlit can retain widget state across a code redeploy. Remove a retired
# page selection (or any other stale value) before constructing the radio;
# otherwise the stored value is no longer a member of the available options.
if st.session_state.get(MODEL_SELECTOR_KEY) not in MODEL_OPTIONS:
    st.session_state.pop(MODEL_SELECTOR_KEY, None)

section = st.sidebar.radio(
    "Model",
    MODEL_OPTIONS,
    index=0,
    key=MODEL_SELECTOR_KEY,
    help=(
        "Production is frozen at V5.8.2. Cycle Trading "
        "preserves the original halving Day-500 sell / 200WMA recovery research. "
        "All research pages remain separate from Production."
    ),
)

# Ensure audit quota guards never leak into either user-facing model.
uninstall_bgeometrics_guard()

# Keep the Production sidebar identical on every dashboard. Execute only the
# Production module's setup + sidebar section on research pages; stop before
# dates, market-data downloads, model calculations, or Production main content.
if section != "Production":
    production_path = Path(__file__).parent / "engines" / "production" / "production_app.py"
    production_source = production_path.read_text(encoding="utf-8")
    sidebar_end = "# BTC_SHARED_PRODUCTION_SIDEBAR_END"
    if sidebar_end not in production_source:
        st.error("Shared Production sidebar section is unavailable.")
        st.stop()
    sidebar_source = production_source.split(sidebar_end, 1)[0]
    sidebar_globals = {
        "__name__": "__main__",
        "__file__": str(production_path),
        "__package__": None,
        "BTC_SIDEBAR_ONLY": True,
    }
    sidebar_code = compile(sidebar_source, str(production_path), "exec")
    exec(sidebar_code, sidebar_globals)

engine_path = {
    "Production": Path(__file__).parent / "engines" / "production" / "production_app.py",
    "Research 10.0": Path(__file__).parent / "engines" / "research" / "cowen_onchain_risk_app.py",
    "Cycle Trading — Research": Path(__file__).parent / "engines" / "research" / "cycle_trading_app.py",
    "Bottom Signal Timeline": Path(__file__).parent / "engines" / "audit" / "bottom_signal_timeline_app.py",
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
