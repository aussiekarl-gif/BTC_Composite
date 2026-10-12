#!/usr/bin/env python3
"""Streamlit UI for V5.9 Research. Calculation/data logic lives in research_model.py."""
from pathlib import Path as _Path
import sys as _sys

_REPO_ROOT = _Path(__file__).resolve().parents[2]
if str(_REPO_ROOT) not in _sys.path:
    _sys.path.insert(0, str(_REPO_ROOT))

from engines.research import research_model as _model
from engines.shared.portfolio_store import load_portfolio, save_portfolio

# Preserve the historical UI namespace so the unchanged Streamlit UI behaves
# exactly as before, including helpers whose names begin with an underscore.
globals().update({k: v for k, v in vars(_model).items() if not k.startswith("__")})

# ================================================================
# Streamlit UI
# ================================================================



# Unified dashboard theme shared by V5.8.2 and V5.9 (UI only).
st.markdown("""
<style>
:root { --btc-bg:#071521; --btc-panel:#0a2133; --btc-border:#174c6b; --btc-blue:#13a8ff; --btc-green:#16e6a1; --btc-text:#f5f9fc; }
.stApp { background: radial-gradient(circle at 50% -15%, #0b2a3e 0%, #071521 40%, #06111b 100%); color:var(--btc-text); }
/* NAS/local Streamlit chrome: keep the dashboard dark edge-to-edge. UI only. */
[data-testid="stHeader"] { background:transparent!important; height:0!important; min-height:0!important; }
[data-testid="stToolbar"], [data-testid="stDecoration"], #MainMenu, footer { display:none!important; visibility:hidden!important; }
[data-testid="stAppViewContainer"] { background:transparent!important; }
[data-testid="stMain"] { background:transparent!important; }
.block-container { max-width:1500px; padding-top:.65rem; padding-bottom:3rem; }
h1,h2,h3,h4 { color:#f5f9fc!important; letter-spacing:-.02em; }
p,label,.stCaption { color:#dce8f0; }
[data-testid="stSidebar"] { background:#06131f; border-right:1px solid #123c57; }
[data-testid="stSidebar"] [role="radiogroup"] > label { background:#0a2133; border:1px solid #174c6b; border-radius:10px; padding:.35rem .55rem; margin:.18rem 0; }
[data-testid="stMetric"] { background:linear-gradient(180deg,#0b2638,#081d2d); border:1px solid #174c6b; border-radius:12px; padding:14px 16px; min-height:104px; box-shadow:0 6px 20px rgba(0,0,0,.16); }
[data-testid="stMetricLabel"] { color:#c9dce8; font-weight:700; }
[data-testid="stMetricValue"] { color:#f7fbff; font-weight:800; }
[data-testid="stExpander"] { background:#081d2d; border:1px solid #174c6b; border-radius:12px; overflow:hidden; margin:.45rem 0; }
[data-testid="stExpander"] summary { background:#0a2435; font-weight:700; }
[data-testid="stForm"] { background:#081d2d; border:1px solid #174c6b; border-radius:14px; padding:1rem; }
.stButton > button,.stDownloadButton > button,[data-testid="stFormSubmitButton"] button { border-radius:9px; border:1px solid #168fd0; background:linear-gradient(180deg,#129eea,#0879bd); color:white; }
[data-baseweb="input"] > div,[data-baseweb="select"] > div,[data-baseweb="base-input"] { background:#091c2a!important; border-color:#174c6b!important; }
[data-testid="stDataFrame"],[data-testid="stTable"] { border:1px solid #174c6b; border-radius:10px; overflow:hidden; }
[data-testid="stAlert"] { border-radius:10px; border:1px solid #1d6085; }
hr { border-color:#174c6b!important; }
/* Robust local/NAS Streamlit header removal across old/new DOM variants. */
header[data-testid="stHeader"], [data-testid="stHeader"], .stAppHeader, [data-testid="stAppHeader"] { display:none!important; visibility:hidden!important; height:0!important; min-height:0!important; }
.stAppToolbar, [data-testid="stToolbar"], [data-testid="stAppToolbar"], [data-testid="stDecoration"], #MainMenu { display:none!important; visibility:hidden!important; height:0!important; }
[data-testid="stMainBlockContainer"], [data-testid="stAppViewBlockContainer"], .block-container { padding-top:.45rem!important; margin-top:0!important; }
header, [class*="stAppHeader"] { background:#071521!important; }

[data-testid="stPlotlyChart"],[data-testid="stVegaLiteChart"] { background:#081d2d; border:1px solid #174c6b; border-radius:12px; padding:.35rem; }

/* DS220+ local Streamlit: remove reserved top shell, not just toolbar contents. */
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
/* Streamlit 1.50+ can reserve the header height on the main element even when the header is hidden. */
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
/* Catch any anonymous shell immediately above the main content. */
[data-testid="stAppViewContainer"] > div,
[data-testid="stAppViewContainer"] > section {
    background-color: #071521 !important;
}

/* ---------------------------------------------------------
   My Portfolio — force Streamlit input surfaces to dark theme
   --------------------------------------------------------- */
[data-baseweb="input"],
[data-baseweb="input"] > div,
[data-baseweb="base-input"],
[data-baseweb="base-input"] > div,
[data-baseweb="select"] > div {
    background-color: #071521 !important;
    color: #f5f9fc !important;
    border-color: #174c6b !important;
}
[data-baseweb="input"] input,
[data-baseweb="base-input"] input {
    background-color: #071521 !important;
    color: #f5f9fc !important;
    -webkit-text-fill-color: #f5f9fc !important;
}
[data-testid="stNumberInput"] button {
    background-color: #071521 !important;
    color: #f5f9fc !important;
    border-color: #174c6b !important;
}
[data-testid="stFileUploader"] section,
[data-testid="stFileUploader"] section > div {
    background-color: #071521 !important;
    color: #f5f9fc !important;
    border-color: #174c6b !important;
}
[data-testid="stFileUploader"] button {
    background-color: #0a2133 !important;
    color: #f5f9fc !important;
    border: 1px solid #174c6b !important;
}
[data-testid="stDataFrame"],
[data-testid="stDataEditor"],
[data-testid="stDataFrame"] > div,
[data-testid="stDataEditor"] > div {
    background-color: #071521 !important;
    border-color: #174c6b !important;
}
[data-testid="stDataFrame"] canvas,
[data-testid="stDataEditor"] canvas {
    background-color: #071521 !important;
}
div[role="listbox"],
ul[role="listbox"],
div[role="option"] {
    background-color: #071521 !important;
    color: #f5f9fc !important;
}
div[role="option"]:hover {
    background-color: #0a2133 !important;
}

</style>
""", unsafe_allow_html=True)

# Browser-local persistence: survives normal app reruns/redeploys on the same browser/device.
# CSV export remains available as a portable backup.
PERSISTENCE_KEY = "btc_dynamic_dca_v59_research_state"
SHARED_PORTFOLIO_KEY = "btc_dynamic_dca_shared_portfolio_v1"
browser_state = {}
local_storage = None

def _parse_saved_date(value, fallback):
    try:
        parsed = pd.to_datetime(value, errors="coerce")
        if pd.notna(parsed):
            return parsed.date()
    except Exception:
        pass
    return fallback


def _load_browser_state():
    if not LOCAL_STORAGE_AVAILABLE:
        return {}
    try:
        store = LocalStorage()
        raw = store.getItem(PERSISTENCE_KEY)
        if isinstance(raw, str) and raw.strip():
            data = json.loads(raw)
            return data if isinstance(data, dict) else {}
        if isinstance(raw, dict):
            return raw
    except Exception:
        return {}
    return {}


def _save_browser_state(state):
    if not LOCAL_STORAGE_AVAILABLE:
        return
    try:
        store = LocalStorage()
        store.setItem(PERSISTENCE_KEY, json.dumps(state, default=str))
    except Exception:
        pass


# Nothing else changed: file content omitted for brevity.
