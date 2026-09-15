#!/usr/bin/env python3
"""Streamlit UI for V5.8.2 Production. Calculation/data logic lives in production_model.py."""
from pathlib import Path as _Path
import sys as _sys

_REPO_ROOT = _Path(__file__).resolve().parents[2]
if str(_REPO_ROOT) not in _sys.path:
    _sys.path.insert(0, str(_REPO_ROOT))

from engines.production import production_model as _model

# Preserve the historical UI namespace so the unchanged Streamlit UI behaves
# exactly as before, including helpers whose names begin with an underscore.
globals().update({k: v for k, v in vars(_model).items() if not k.startswith("__")})

# ================================================================
# Streamlit UI
# ================================================================

st.set_page_config(
    page_title="BTC Dynamic DCA V5.8 FULL",
    layout="wide",
    initial_sidebar_state="expanded",
)


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
.stButton > button,.stDownloadButton > button,[data-testid="stFormSubmitButton"] button { border-radius:9px; border:1px solid #168fd0; background:linear-gradient(180deg,#129eea,#0879bd); color:white; font-weight:800; }
[data-baseweb="input"] > div,[data-baseweb="select"] > div,[data-baseweb="base-input"] { background:#091c2a!important; border-color:#174c6b!important; }
[data-testid="stDataFrame"],[data-testid="stTable"] { border:1px solid #174c6b; border-radius:10px; overflow:hidden; }
[data-testid="stAlert"] { border-radius:10px; border:1px solid #1d6085; }
hr { border-color:#174c6b!important; }
/* Robust local/NAS Streamlit header removal across old/new DOM variants. */
header[data-testid="stHeader"], [data-testid="stHeader"], .stAppHeader, [data-testid="stAppHeader"] { display:none!important; visibility:hidden!important; height:0!important; min-height:0!important; background:#071521!important; }
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

</style>
""", unsafe_allow_html=True)

# Browser-local persistence: survives normal app reruns/redeploys on the same browser/device.
# CSV export remains available as a portable backup.
PERSISTENCE_KEY = "btc_dynamic_dca_v58_state"
SHARED_PORTFOLIO_KEY = "btc_dynamic_dca_shared_portfolio_v1"
PORTFOLIO_BACKUPS_KEY = "btc_dynamic_dca_portfolio_backups_v1"
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


def _multiplier_curve_controls(default_curve, storage_key):
    """Render a safe, browser-persistent custom multiplier curve."""
    defaults = [(float(risk), float(mult)) for risk, mult in default_curve]
    saved = browser_state.get(storage_key, {}) if isinstance(browser_state, dict) else {}
    saved_points = saved.get("points", []) if isinstance(saved, dict) else []
    saved_by_risk = {}
    for point in saved_points if isinstance(saved_points, list) else []:
        try:
            saved_by_risk[round(float(point[0]), 6)] = float(point[1])
        except (TypeError, ValueError, IndexError):
            continue

    with st.expander("Advanced Multiplier Settings", expanded=False):
        st.caption(
            "Custom settings affect this model only. Multipliers must stay level or decrease as risk rises."
        )
        reset = st.button("Restore model defaults", key=f"{storage_key}_restore")
        if reset:
            st.session_state.pop(f"{storage_key}_enabled", None)
            for risk, _ in defaults:
                st.session_state.pop(f"{storage_key}_{risk:.2f}", None)
            saved = {"enabled": False, "points": []}
            saved_by_risk = {}
        enabled = st.toggle(
            "Use custom multiplier curve",
            value=bool(saved.get("enabled", False)),
            key=f"{storage_key}_enabled",
        )

        curve = []
        for risk, default_mult in defaults:
            initial = default_mult if reset else saved_by_risk.get(round(risk, 6), default_mult)
            mult = st.number_input(
                f"Risk {risk:.2f}",
                min_value=0.0,
                max_value=10.0,
                value=float(initial),
                step=0.05,
                format="%.2f",
                key=f"{storage_key}_{risk:.2f}",
                disabled=not enabled,
            )
            curve.append((risk, float(mult)))

        valid = all(curve[i][1] >= curve[i + 1][1] for i in range(len(curve) - 1))
        if enabled and not valid:
            st.error("Custom curve not applied: multipliers cannot increase as risk rises.")
        elif enabled:
            st.success("Custom curve active")
        else:
            st.caption("Model default curve active")

    active_curve = curve if enabled and valid else defaults
    browser_state[storage_key] = {
        "enabled": bool(enabled),
        "points": [[risk, mult] for risk, mult in curve],
    }
    _save_browser_state(browser_state)
    return active_curve, bool(enabled and valid)


def _load_shared_portfolio(fallback_state=None):
    """Load portfolio data shared by V5.8.2 and V5.9 on this browser/device.

    On first use, V5.8.2 is the preferred migration source so an existing production
    portfolio automatically appears in V5.9 even if V5.9 is opened first.
    """
    fallback_state = fallback_state if isinstance(fallback_state, dict) else {}
    fallback = fallback_state.get("portfolio", {}) if isinstance(fallback_state.get("portfolio", {}), dict) else {}
    if not LOCAL_STORAGE_AVAILABLE:
        return fallback.copy()
    try:
        store = LocalStorage()
        raw = store.getItem(SHARED_PORTFOLIO_KEY)
        if isinstance(raw, str) and raw.strip():
            data = json.loads(raw)
            if isinstance(data, dict):
                return data
        elif isinstance(raw, dict):
            return raw

        # One-time migration. Prefer the existing V5.8.2 production portfolio.
        migration_candidates = []
        for legacy_key in ("btc_dynamic_dca_v58_state", "btc_dynamic_dca_v59_research_state"):
            legacy_raw = store.getItem(legacy_key)
            legacy_state = None
            if isinstance(legacy_raw, str) and legacy_raw.strip():
                try:
                    legacy_state = json.loads(legacy_raw)
                except Exception:
                    legacy_state = None
            elif isinstance(legacy_raw, dict):
                legacy_state = legacy_raw
            if isinstance(legacy_state, dict) and isinstance(legacy_state.get("portfolio"), dict):
                migration_candidates.append(legacy_state["portfolio"])
        if fallback:
            migration_candidates.append(fallback)

        for candidate in migration_candidates:
            if candidate:
                store.setItem(SHARED_PORTFOLIO_KEY, json.dumps(candidate, default=str))
                return candidate.copy()
    except Exception:
        pass
    return fallback.copy()


def _decode_local_storage_value(raw):
    if isinstance(raw, str) and raw.strip():
        try:
            return json.loads(raw)
        except Exception:
            return None
    return raw if isinstance(raw, (dict, list)) else None


def _load_portfolio_snapshots(fallback_state=None):
    """Return every recoverable browser portfolio without choosing or merging it."""
    snapshots = []
    seen = set()
    fallback_state = fallback_state if isinstance(fallback_state, dict) else {}

    def add_snapshot(source, candidate):
        if not isinstance(candidate, dict):
            return
        rows = candidate.get("rows", [])
        if not isinstance(rows, list) or not rows:
            return
        fingerprint = json.dumps(candidate, sort_keys=True, default=str)
        if fingerprint in seen:
            return
        seen.add(fingerprint)
        parsed_dates = pd.to_datetime(
            [row.get("Date") for row in rows if isinstance(row, dict)],
            dayfirst=True,
            errors="coerce",
        )
        valid_dates = parsed_dates[~pd.isna(parsed_dates)]
        latest = valid_dates.max().strftime("%d/%m/%Y") if len(valid_dates) else "unknown"
        snapshots.append({
            "source": source,
            "portfolio": candidate.copy(),
            "rows": len(rows),
            "latest": latest,
        })

    add_snapshot("Current V5.8 browser state", fallback_state.get("portfolio"))
    if not LOCAL_STORAGE_AVAILABLE:
        return snapshots

    try:
        store = LocalStorage()
        shared_raw = _decode_local_storage_value(store.getItem(SHARED_PORTFOLIO_KEY))
        add_snapshot("Shared portfolio", shared_raw)

        for key, label in (
            ("btc_dynamic_dca_v58_state", "Legacy V5.8 browser state"),
            ("btc_dynamic_dca_v59_research_state", "Legacy V5.9 research state"),
        ):
            state = _decode_local_storage_value(store.getItem(key))
            if isinstance(state, dict):
                add_snapshot(label, state.get("portfolio"))

        backups = _decode_local_storage_value(store.getItem(PORTFOLIO_BACKUPS_KEY))
        if isinstance(backups, list):
            for index, item in enumerate(reversed(backups)):
                if isinstance(item, dict):
                    add_snapshot(
                        f"Automatic backup {index + 1} ({item.get('saved_at', 'unknown time')})",
                        item.get("portfolio"),
                    )
    except Exception:
        pass
    return snapshots


def _save_shared_portfolio(portfolio):
    """Persist portfolio inputs and retain rotating pre-save browser backups."""
    if not LOCAL_STORAGE_AVAILABLE or not isinstance(portfolio, dict):
        return
    try:
        store = LocalStorage()
        previous = _decode_local_storage_value(store.getItem(SHARED_PORTFOLIO_KEY))
        if isinstance(previous, dict) and previous.get("rows"):
            backups = _decode_local_storage_value(store.getItem(PORTFOLIO_BACKUPS_KEY))
            backups = backups if isinstance(backups, list) else []
            previous_fingerprint = json.dumps(previous, sort_keys=True, default=str)
            latest_fingerprint = (
                json.dumps(backups[-1].get("portfolio"), sort_keys=True, default=str)
                if backups and isinstance(backups[-1], dict)
                else None
            )
            if previous_fingerprint != latest_fingerprint:
                backups.append({
                    "saved_at": dt.datetime.now(dt.timezone.utc).isoformat(),
                    "portfolio": previous,
                })
                backups = backups[-10:]
                store.setItem(PORTFOLIO_BACKUPS_KEY, json.dumps(backups, default=str))
        store.setItem(SHARED_PORTFOLIO_KEY, json.dumps(portfolio, default=str))
    except Exception:
        pass

browser_state = _load_browser_state()
portfolio_snapshots = _load_portfolio_snapshots(browser_state)
shared_portfolio = _load_shared_portfolio(browser_state)

st.title("Bitcoin Dynamic DCA V5.8.2 FULL — Smart DCA")
st.caption("Version 5.8.2 FULL • Risk-only sizing • Cycle context • Persistent portfolio")
st.caption("Simple three-mode app • Backtest • DCA Today • My Portfolio")

# ------------------------------------------------
# Sidebar
# ------------------------------------------------

with st.sidebar:
    st.header("Mode")

    mode = st.radio(
        "Analysis Mode",
        [
            "DCA Today",
            "DCA Backtest",
            "My Portfolio",
        ],
    )

    st.divider()

    active_smart_dca_curve, custom_curve_active = _multiplier_curve_controls(
        SMART_DCA_POINTS, "production_multiplier_curve"
    )

    st.divider()

    day_map = {
        "Monday": 0,
        "Tuesday": 1,
        "Wednesday": 2,
        "Thursday": 3,
        "Friday": 4,
        "Saturday": 5,
        "Sunday": 6,
    }

    if mode == "DCA Backtest":
        st.header("DCA Backtest")

        saved_bt = browser_state.get("backtest", {}) if isinstance(browser_state, dict) else {}
        saved_freq = saved_bt.get("frequency", "Weekly")
        dca_frequency = st.radio(
            "DCA Frequency",
            ["Daily", "Weekly"],
            horizontal=True,
            index=0 if saved_freq == "Daily" else 1,
            key="dca_backtest_frequency",
        )
        dca_base_amount_aud = DEFAULT_FIXED_DCA_AUD

        intelligent_dca_budget_aud = st.number_input(
            "Total Budget (AUD)",
            min_value=10_000.0,
            max_value=10_000_000.0,
            value=float(saved_bt.get("budget_aud", DEFAULT_INTELLIGENT_DCA_BUDGET_AUD)),
            step=10_000.0,
            format="%.0f",
            help="Plain DCA and Smart DCA both receive exactly this total budget.",
        )

        # Fixed, walk-forward-tested Smart DCA curve.
        low_risk_weight = SMART_DCA_LOW_RISK_WEIGHT
        high_risk_weight = SMART_DCA_HIGH_RISK_WEIGHT
        smart_dca_curve = active_smart_dca_curve

        dca_backtest_start_date = st.date_input(
            "Start Date", value=_parse_saved_date(saved_bt.get("start_date"), dt.date(2015, 1, 1)),
            min_value=dt.date(2012, 1, 1), max_value=dt.date.today(),
            format="DD/MM/YYYY", key="sidebar_dca_backtest_start_date",
        )
        dca_backtest_end_date = st.date_input(
            "End Date", value=_parse_saved_date(saved_bt.get("end_date"), dt.date.today()),
            min_value=dt.date(2012, 1, 1), max_value=dt.date.today(),
            format="DD/MM/YYYY", key="sidebar_dca_backtest_end_date",
        )
        if dca_backtest_start_date >= dca_backtest_end_date:
            st.error("Backtest Start Date must be before Backtest End Date.")

        saved_weekday = saved_bt.get("weekday", "Monday")
        weekday_names = list(day_map.keys())
        selected_day_name = st.selectbox(
            "Weekly Execution Day",
            weekday_names,
            index=weekday_names.index(saved_weekday) if saved_weekday in weekday_names else 0,
            disabled=(dca_frequency != "Weekly"),
            key="dca_backtest_weekday",
        )
        selected_day = day_map[selected_day_name]
        total_capital_aud = 0.0
        frequency = dca_frequency

        st.caption(
            "Same budget and dates. Plain DCA invests evenly; Smart DCA uses the selected risk curve."
        )
        browser_state["backtest"] = {
            "frequency": dca_frequency,
            "budget_aud": float(intelligent_dca_budget_aud),
            "start_date": dca_backtest_start_date.isoformat(),
            "end_date": dca_backtest_end_date.isoformat(),
            "weekday": selected_day_name,
        }
        _save_browser_state(browser_state)

    elif mode == "DCA Today":
        st.header("DCA Today")

        saved_today = browser_state.get("today", {}) if isinstance(browser_state, dict) else {}
        saved_portfolio = shared_portfolio if isinstance(shared_portfolio, dict) else {}

        starting_default = float(saved_portfolio.get(
            "starting_capital_aud",
            saved_today.get("starting_capital_aud", 500_000.0)
        ))
        starting_capital_aud = st.number_input(
            "Starting Capital (AUD)",
            min_value=1_000.0, max_value=100_000_000.0,
            value=starting_default, step=10_000.0, format="%.0f",
            key="today_starting_capital",
        )

        portfolio_remaining_saved = saved_portfolio.get("capital_remaining_aud", None)
        remaining_default = saved_today.get("remaining_capital_aud", starting_capital_aud)
        if portfolio_remaining_saved is not None:
            remaining_default = portfolio_remaining_saved

        remaining_capital_aud = st.number_input(
            "Capital Remaining (AUD)",
            min_value=0.0, max_value=float(starting_capital_aud),
            value=min(float(starting_capital_aud), float(remaining_default)),
            step=5_000.0, format="%.0f",
            key="today_remaining_capital",
        )

        default_target = dt.date.today() + dt.timedelta(days=365 * 3)
        saved_target = _parse_saved_date(saved_today.get("target_date"), default_target)
        if saved_target < dt.date.today() + dt.timedelta(days=7):
            saved_target = default_target
        target_deployment_date = st.date_input(
            "Target Deployment Date",
            value=saved_target,
            min_value=dt.date.today() + dt.timedelta(days=7),
            format="DD/MM/YYYY",
            key="today_target_date",
        )

        low_risk_weight = SMART_DCA_LOW_RISK_WEIGHT
        high_risk_weight = SMART_DCA_HIGH_RISK_WEIGHT
        smart_dca_curve = active_smart_dca_curve

        st.caption(
            "Custom V5.8.2 multiplier curve is active."
            if custom_curve_active else
            "V5.8.2 default: 2.75× at risk 0.00, 1.00× at risk 0.50, and 0.05× at risk 1.00."
        )

        browser_state["today"] = {
            "starting_capital_aud": float(starting_capital_aud),
            "remaining_capital_aud": float(remaining_capital_aud),
            "target_date": target_deployment_date.isoformat(),
        }
        _save_browser_state(browser_state)

        # Compatibility values for the shared risk engine.
        total_capital_aud = float(starting_capital_aud)
        frequency = "Weekly"
        selected_day = dt.date.today().weekday()

    else:  # My Portfolio
        st.header("My Portfolio")
        # Compatibility values for the shared engine; portfolio mode does not run market calculations.
        starting_capital_aud = float(st.session_state.get("portfolio_starting_capital", 500000.0))
        remaining_capital_aud = float(st.session_state.get("portfolio_capital_remaining", starting_capital_aud))
        total_capital_aud = starting_capital_aud
        frequency = "Weekly"
        selected_day = dt.date.today().weekday()
        low_risk_weight = SMART_DCA_LOW_RISK_WEIGHT
        high_risk_weight = SMART_DCA_HIGH_RISK_WEIGHT
        smart_dca_curve = active_smart_dca_curve

    st.divider()
    st.caption(
        "The selected multiplier curve is used consistently by Backtest and DCA Today."
    )

    # Fixed calibrated engine defaults. These remain in code but are no longer user-facing.
    risk_model = "Composite V3.6"
    base_dca_pct = 0.01
    max_period_pct = 0.05
    max_sell_pct_period = min(DEFAULT_MAX_SELL_PCT_PERIOD, 0.20)
    buy_threshold = DEFAULT_BUY_THRESHOLD
    sell_risk_threshold = DEFAULT_SELL_RISK_THRESHOLD

    regime_overlay = 0.0

    valuation_strength = DEFAULT_VALUATION_STRENGTH
    min_valuation_mult = DEFAULT_MIN_VALUATION_MULT
    max_valuation_mult = min(DEFAULT_MAX_VALUATION_MULT, 2.0)
    min_cash_reserve_pct = DEFAULT_MIN_CASH_RESERVE_PCT
    min_trade_aud = DEFAULT_MIN_TRADE_AUD
    fee_pct = DEFAULT_FEE_PCT
    min_days_between_sales = DEFAULT_MIN_DAYS_BETWEEN_SALES
    min_risk_components = DEFAULT_MIN_RISK_COMPONENTS
    require_weak_trend_for_sell = False

    trend_er_period = DEFAULT_TREND_ER_PERIOD
    trend_fast = DEFAULT_TREND_FAST
    trend_slow = DEFAULT_TREND_SLOW
    trend_range_period = DEFAULT_TREND_RANGE_PERIOD
    trend_band_mult = DEFAULT_TREND_BAND_MULT
    trend_buy_bull = DEFAULT_TREND_BUY_BULL
    trend_buy_neutral = DEFAULT_TREND_BUY_NEUTRAL
    trend_buy_bear = DEFAULT_TREND_BUY_BEAR
    trend_sell_bull = DEFAULT_TREND_SELL_BULL
    trend_sell_neutral = DEFAULT_TREND_SELL_NEUTRAL
    trend_sell_bear = DEFAULT_TREND_SELL_BEAR


    # ================================================================
# Dates / Parameters
# ================================================================

today = dt.datetime.now(timezone.utc).date()
genesis = dt.date(2009, 1, 3)

if mode == "DCA Backtest":
    start_date = dca_backtest_start_date
    end_date = dca_backtest_end_date
else:
    end_date = today
    start_date = today - dt.timedelta(days=365 * 11)


params = {
    "risk_model": risk_model,
    "frequency": frequency,
    "day_of_week": selected_day,
    "fund_cheap": DEFAULT_FUND_CHEAP,
    "fund_expensive": DEFAULT_FUND_EXPENSIVE,
    "pl_cheap": DEFAULT_PL_CHEAP,
    "pl_expensive": DEFAULT_PL_EXPENSIVE,
    "total_capital_aud": total_capital_aud,
    "base_dca_pct": base_dca_pct,
    "pressure_strength": 0.0,
    "max_period_pct": max_period_pct,
    "min_cash_reserve_pct": min_cash_reserve_pct,
    "sell_threshold": 0.0,
    "max_sell_pct_period": max_sell_pct_period,
    "fee_pct": fee_pct,
    "regime_overlay": regime_overlay,
    "valuation_strength": valuation_strength,
    "min_valuation_mult": min_valuation_mult,
    "max_valuation_mult": max_valuation_mult,
    "pressure_cap": 1.0,
    "max_btc_weight": 1.0,
    "min_days_between_sales": min_days_between_sales,
    "buy_threshold": buy_threshold,
    "sell_risk_threshold": sell_risk_threshold,
    "min_trade_aud": min_trade_aud,
    "min_risk_components": min_risk_components,
    "price_position_window": DEFAULT_PRICE_POSITION_WINDOW,
    "risk_calibration_min_periods": DEFAULT_RISK_CALIBRATION_MIN_PERIODS,
    "risk_calibration_window": DEFAULT_RISK_CALIBRATION_WINDOW,
    "risk_calibration_blend": DEFAULT_RISK_CALIBRATION_BLEND,
    "absolute_risk_weight": DEFAULT_ABSOLUTE_RISK_WEIGHT,
    "relative_risk_weight": DEFAULT_RELATIVE_RISK_WEIGHT,
    "require_weak_trend_for_sell": require_weak_trend_for_sell,
    "trend_er_period": trend_er_period,
    "trend_fast": trend_fast,
    "trend_slow": trend_slow,
    "trend_range_period": trend_range_period,
    "trend_band_mult": trend_band_mult,
    "trend_buy_bull": trend_buy_bull,
    "trend_buy_neutral": trend_buy_neutral,
    "trend_buy_bear": trend_buy_bear,
    "trend_sell_bull": trend_sell_bull,
    "trend_sell_neutral": trend_sell_neutral,
    "trend_sell_bear": trend_sell_bear,
    "start_date": dt.datetime.combine(
        start_date,
        dt.time.min,
        tzinfo=timezone.utc,
    ),
    "end_date": dt.datetime.combine(
        end_date,
        dt.time.max,
        tzinfo=timezone.utc,
    ),
}


# Hard UI guard: strict BUY/HOLD/SELL requires a non-overlapping HOLD zone.
if buy_threshold >= sell_risk_threshold:
    st.error(
        "Invalid risk bands: BUY threshold must be lower than SELL threshold. "
        "Please adjust the sidebar controls."
    )
    st.stop()


# ================================================================
# Historical Backtest
# ================================================================

# ================================================================
# DCA Backtest
# ================================================================

if mode == "DCA Backtest":

    if dca_backtest_start_date >= dca_backtest_end_date:
        st.error("Backtest Start Date must be before Backtest End Date.")
        st.stop()

    params["start_date"] = dt.datetime.combine(
        dca_backtest_start_date, dt.time.min, tzinfo=timezone.utc
    )
    params["end_date"] = dt.datetime.combine(
        dca_backtest_end_date, dt.time.max, tzinfo=timezone.utc
    )
    params["day_of_week"] = selected_day

    with st.spinner("Loading historical BTC and AUD/USD data..."):
        df_full = fetch_btc_history(params["start_date"], params["end_date"])
        fx_series = fetch_aud_usd_rates(params["start_date"], params["end_date"])
        bg_token = get_bgeometrics_token()
        bg_data = fetch_bgeometrics_bundle(
            params["start_date"] - timedelta(days=300),
            params["end_date"],
            bg_token,
        )

    if df_full.empty:
        st.error("No BTC price data was returned.")
        st.stop()

    df_full = align_fx_to_dates(df_full, fx_series)
    df_full = merge_bgeometrics(df_full, bg_data)

    with st.spinner("Running equal-capital Plain DCA vs Smart DCA..."):
        plain_raw, _ = simulate_dca_backtest(
            df_full, params, DEFAULT_FIXED_DCA_AUD, dca_frequency, "Plain DCA"
        )
        smart_raw, _ = simulate_dca_backtest(
            df_full, params, DEFAULT_FIXED_DCA_AUD, dca_frequency,
            "Risk-Scaled DCA", risk_curve=smart_dca_curve
        )

        capital_target = float(intelligent_dca_budget_aud)
        plain_df, plain_sm = apply_equal_capital_allocator(
            plain_raw, total_budget_aud=capital_target,
            fee_pct=params.get("fee_pct", 0.0)
        )
        smart_df, smart_sm = apply_equal_capital_allocator(
            smart_raw, total_budget_aud=capital_target,
            fee_pct=params.get("fee_pct", 0.0)
        )
        recent_check = validate_smart_dca_recent_period(
            df_full, params, dca_frequency, capital_target, recent_fraction=0.30,
            risk_curve=smart_dca_curve
        )

    if not plain_sm or not smart_sm:
        st.error("Not enough historical data for this DCA Backtest.")
        st.stop()

    btc_adv = (
        (smart_sm["btc_held"] / plain_sm["btc_held"] - 1.0) * 100.0
        if plain_sm["btc_held"] > 0 else np.nan
    )
    cost_adv = (
        (1.0 - smart_sm["avg_cost_aud"] / plain_sm["avg_cost_aud"]) * 100.0
        if plain_sm["avg_cost_aud"] > 0 else np.nan
    )
    value_adv = (
        (smart_sm["btc_value_aud"] / plain_sm["btc_value_aud"] - 1.0) * 100.0
        if plain_sm["btc_value_aud"] > 0 else np.nan
    )

    st.header("Simple DCA Backtest")
    st.caption(
        f"Same A${capital_target:,.0f} budget • {dca_frequency} • "
        f"{dca_backtest_start_date.strftime('%d/%m/%Y')} to "
        f"{dca_backtest_end_date.strftime('%d/%m/%Y')}"
    )

    p1, p2 = st.columns(2)
    with p1:
        st.subheader("Plain DCA")
        st.metric("BTC Accumulated", f"{plain_sm['btc_held']:.6f}")
        st.metric("Average Cost", f"A${plain_sm['avg_cost_aud']:,.0f}")
        st.metric("Ending Value", f"A${plain_sm['btc_value_aud']:,.0f}")
        st.metric("ROI", f"{plain_sm['roi_pct']:+.2f}%")

    with p2:
        st.subheader("Smart DCA")
        st.metric(
            "BTC Accumulated", f"{smart_sm['btc_held']:.6f}",
            delta=f"{btc_adv:+.2f}% vs Plain"
        )
        st.metric(
            "Average Cost", f"A${smart_sm['avg_cost_aud']:,.0f}",
            delta=f"{cost_adv:+.2f}% advantage"
        )
        st.metric(
            "Ending Value", f"A${smart_sm['btc_value_aud']:,.0f}",
            delta=f"{value_adv:+.2f}% vs Plain"
        )
        st.metric("ROI", f"{smart_sm['roi_pct']:+.2f}%")

    st.subheader("Verdict")
    if btc_adv > 0:
        st.success(
            f"Smart DCA accumulated {btc_adv:+.2f}% more BTC than Plain DCA "
            f"for the same A${capital_target:,.0f}."
        )
    else:
        st.warning(
            f"Smart DCA accumulated {abs(btc_adv):.2f}% less BTC than Plain DCA. "
            "For this period, Plain DCA was the better strategy."
        )

    if recent_check:
        st.subheader("Recent 30% Validation")
        r1, r2, r3 = st.columns(3)
        r1.metric("Validation Budget", f"A${recent_check['budget_aud']:,.0f}")
        r2.metric("Plain DCA BTC", f"{recent_check['plain_btc']:.6f}")
        r3.metric(
            "Smart DCA BTC", f"{recent_check['smart_btc']:.6f}",
            delta=f"{recent_check['btc_advantage_pct']:+.2f}% vs Plain"
        )
        if recent_check["btc_advantage_pct"] > 0:
            st.success("Smart DCA also beat Plain DCA in the most recent 30% of the test period.")
        else:
            st.info("Smart DCA did not beat Plain DCA in the most recent 30% of the test period.")

    with st.expander("How Smart DCA works", expanded=False):
        st.write(
            "Smart DCA always buys, but conviction is intentionally asymmetric. "
            "Low-risk periods can receive many times more capital than high-risk periods. "
            "You control only the two endpoints; risk 0.50 stays anchored at 1.00x. "
            "The total budget is still normalized to exactly the same amount as Plain DCA."
        )
        curve_df = pd.DataFrame(smart_dca_curve, columns=["Risk", "Relative Weight"])
        curve_df["Relative Weight"] = curve_df["Relative Weight"].map(lambda x: f"{x:.2f}x")
        st.dataframe(curve_df, width="stretch", hide_index=True)

    with st.expander("Detailed activity", expanded=False):
        detail_cols = [
            "date", "price_usd", "risk_score", "actual_buy_aud",
            "btc_bought", "btc_held", "cumulative_invested_aud", "avg_cost_aud"
        ]
        smart_detail = smart_df[[c for c in detail_cols if c in smart_df.columns]].copy()
        st.dataframe(smart_detail.tail(250), width="stretch", hide_index=True)

    plain_csv = plain_df.to_csv(index=False).encode("utf-8")
    smart_csv = smart_df.to_csv(index=False).encode("utf-8")
    d1, d2 = st.columns(2)
    d1.download_button(
        "Download Plain DCA CSV", plain_csv,
        file_name="btc_v5_1_plain_dca.csv", mime="text/csv"
    )
    d2.download_button(
        "Download Smart DCA CSV", smart_csv,
        file_name="btc_v5_1_smart_dca.csv", mime="text/csv"
    )


# ================================================================

# ================================================================
# DCA Today
# ================================================================

elif mode == "DCA Today":
    now_utc = dt.datetime.now(timezone.utc)
    # Enough history for current cycle + previous two halving cycles.
    lookback_start = now_utc - timedelta(days=365 * 11)

    with st.spinner("Calculating today's BTC valuation risk..."):
        df_today = fetch_btc_history(lookback_start, now_utc)
        fx_today = fetch_aud_usd_rates(lookback_start, now_utc)
        bg_token = get_bgeometrics_token()
        bg_today = fetch_bgeometrics_bundle(
            lookback_start - timedelta(days=300), now_utc, bg_token
        )

    if df_today.empty:
        st.error("No BTC price data was returned.")
        st.stop()

    df_today = align_fx_to_dates(df_today, fx_today)
    df_today = merge_bgeometrics(df_today, bg_today)
    risk_today_df = add_risk_indicators(df_today, risk_model, params)

    # Size from the latest fully closed UTC day only. Provider APIs may
    # expose a changing partial row for the current UTC date; allowing that row
    # into risk sizing makes the weekly recommendation drift intraday.
    closed_utc_cutoff = pd.Timestamp(now_utc.date(), tz="UTC")
    risk_index_utc = pd.to_datetime(risk_today_df.index, utc=True)
    risk_today_closed = risk_today_df.loc[risk_index_utc < closed_utc_cutoff].copy()
    valid_today = risk_today_closed.dropna(subset=["risk_score", "price"])
    if valid_today.empty:
        st.error("Today's risk score could not be calculated from the available data.")
        st.stop()

    latest = valid_today.iloc[-1]
    current_risk = float(latest["risk_score"])
    current_price_usd = float(latest["price"])
    usd_per_aud = float(latest["usd_per_aud"]) if pd.notna(latest.get("usd_per_aud", np.nan)) else np.nan
    historical_price_aud = current_price_usd / usd_per_aud if np.isfinite(usd_per_aud) and usd_per_aud > 0 else np.nan

    # Display a fresh spot price where available. The risk engine continues to use
    # the historical/closed data above, so a live quote cannot change the risk score.
    live_price_aud = fetch_live_btc_aud()
    current_price_aud = live_price_aud if np.isfinite(live_price_aud) else historical_price_aud
    price_is_live = bool(np.isfinite(live_price_aud))

    risk_weight = float(interpolate(smart_dca_curve, current_risk))

    # Opportunity rarity: use weekly historical risk observations available up
    # to today. This estimates how often BTC has been at least as cheap as now.
    if isinstance(valid_today.index, pd.DatetimeIndex):
        rarity_source = valid_today["risk_score"].resample("W-MON").last().dropna()
    elif "date" in valid_today.columns:
        rarity_source = valid_today.set_index("date")["risk_score"].resample("W-MON").last().dropna()
    else:
        # Safe fallback: use observations in their existing chronological order.
        rarity_source = valid_today["risk_score"].dropna()
    rarity = opportunity_rarity_from_history(rarity_source, current_risk)
    # V5.8.2: rarity is decision-support context only. Risk Score alone controls sizing.
    effective_weight = risk_weight

    days_remaining = max((target_deployment_date - dt.date.today()).days, 7)
    weeks_remaining = max(days_remaining / 7.0, 1.0)

    opportunity = lower_risk_opportunity_stats(
        rarity_source, current_risk, min(weeks_remaining, 156.0)
    )

    normal_weekly_allowance = float(remaining_capital_aud) / weeks_remaining
    recommended_buy = min(
        float(remaining_capital_aud),
        max(0.0, normal_weekly_allowance * risk_weight),
    )

    # Better-entry probability is informational only in V5.8.2.
    # It never overrides the Risk Score sizing curve.
    extreme_all_in_eligible = False

    risk_label = (
        "VERY LOW" if current_risk <= 0.20 else
        "LOW" if current_risk <= 0.40 else
        "NEUTRAL" if current_risk <= 0.60 else
        "HIGH" if current_risk <= 0.80 else
        "VERY HIGH"
    )
    deployed = max(float(starting_capital_aud) - float(remaining_capital_aud), 0.0)
    remaining_after = max(float(remaining_capital_aud) - recommended_buy, 0.0)

    st.header("DCA Today")
    st.caption(
        ("Uses your custom V5.8.2 Risk Score multiplier curve. " if custom_curve_active else
         "Uses the default walk-forward-tested V5.8.2 Smart DCA curve. ") +
        "Opportunity Rarity and Better Entry Evidence are informational only."
    )

    # Decision-first production dashboard. UI only: the calculation above is unchanged.
    # Colour language is shared with V5.9: green=favourable/BUY, amber=neutral/caution,
    # red=high-risk/unfavourable, grey=context/inactive, blue=information.
    risk_tone = (
        "good" if current_risk <= 0.40 else
        "warn" if current_risk <= 0.60 else
        "bad"
    )
    risk_tone_label = risk_label.title()
    btc_price_main = "n/a" if not np.isfinite(current_price_aud) else f"A${current_price_aud:,.0f}"
    btc_price_sub = f"US${current_price_usd:,.0f}" if np.isfinite(current_price_usd) else ""
    better_entry_text = (
        f"{opportunity['cycle_successes']} of {opportunity['cycles_used']} cycles"
        if opportunity["cycles_used"] >= 1 else "n/a"
    )

    st.markdown(
        """
        <style>
        .v58-wrap{font-family:inherit;margin-top:.25rem}
        .v58-hero{display:grid;grid-template-columns:1.35fr .72fr 1.15fr;border:1.5px solid #19e894;border-radius:13px;background:linear-gradient(135deg,#062a29,#071c2d 58%,#062a29);overflow:hidden;box-shadow:0 0 24px rgba(25,232,148,.09)}
        .v58-hero>div{padding:18px 22px;min-height:178px}.v58-hero>div+div{border-left:1px solid rgba(69,216,196,.30)}
        .v58-title{font-size:1rem;font-weight:900;color:#f4f8fb}.v58-big{font-size:3.35rem;line-height:1.05;font-weight:950;color:#18e89a;margin:12px 0 14px}.v58-mult{font-size:3.0rem;line-height:1.05;font-weight:950;color:#4fb8ff;margin:12px 0 12px}
        .v58-buy-pill{display:inline-block;border-radius:8px;background:#18e89a;color:#04281b;font-weight:950;padding:9px 16px;font-size:.82rem}.v58-sub{font-size:.82rem;color:#cad7e2}.v58-base{font-size:1.45rem;font-weight:900;color:#f4f8fb;margin-top:4px}
        .v58-reason{display:flex;gap:10px;margin:10px 0;align-items:flex-start;color:#f0f4f8}.v58-check,.v58-off{width:24px;height:24px;flex:0 0 24px;border-radius:50%;display:flex;align-items:center;justify-content:center;font-weight:900;margin-top:1px}.v58-check{background:#19e894;color:#052b1e}.v58-off{border:1.5px solid #718397;color:#718397}.v58-reason b{display:block;font-size:.95rem}.v58-reason small{display:block;color:#b8c6d4;margin-top:1px}
        .v58-q{display:inline-flex;align-items:center;justify-content:center;width:17px;height:17px;border:1px solid #57c8ff;border-radius:50%;color:#57c8ff;font-size:.68rem;font-weight:800;margin-left:5px;vertical-align:2px;cursor:help}
        .v58-cards{display:grid;grid-template-columns:repeat(5,1fr);gap:10px;margin-top:10px}.v58-card{border:1px solid #29506b;border-radius:11px;padding:13px 15px;background:linear-gradient(180deg,#092337,#081a2b);min-height:110px}.v58-card-title{font-size:.82rem;color:#eaf1f7;font-weight:800}.v58-card-value{font-size:1.45rem;color:#f3f7fb;font-weight:900;margin-top:5px}.v58-card-value.good{color:#24e894}.v58-card-value.warn{color:#ffb43b}.v58-card-value.bad{color:#ff6476}.v58-card-sub{font-size:.80rem;color:#c1ccd8;margin-top:5px;line-height:1.35}
        .v58-badge{display:inline-block;border-radius:999px;padding:3px 13px;font-size:.76rem;font-weight:900;margin-top:4px}.v58-badge.good{background:#24e894;color:#05281b}.v58-badge.warn{background:#ffb43b;color:#382200}.v58-badge.bad{background:#ff6476;color:#35070c}.v58-badge.context{background:#26384b;color:#dce7ef;border:1px solid #64778a}
        .v58-info{display:flex;gap:14px;align-items:flex-start;border:1px solid #168fea;border-radius:10px;background:linear-gradient(90deg,#082e50,#07335c);padding:13px 16px;margin:12px 0 10px}.v58-info-icon{width:26px;height:26px;flex:0 0 26px;border-radius:50%;background:#4fb9ff;color:#06233a;display:flex;align-items:center;justify-content:center;font-weight:900}.v58-info-title{font-weight:900;color:#eef7ff;margin-bottom:3px}.v58-info-text{font-size:.84rem;color:#d5e4f0;line-height:1.45}
        .v58-explain-grid{display:grid;grid-template-columns:repeat(3,1fr);gap:10px;margin-bottom:10px}.v58-explain{border:1px solid #264b65;border-radius:10px;padding:13px 14px;background:#091d2e;min-height:142px}.v58-explain h4{margin:0 0 8px;color:#f2f7fb;font-size:.92rem}.v58-explain p{margin:0 0 7px;color:#c7d3de;font-size:.80rem;line-height:1.42}.v58-affects,.v58-context{display:inline-block;border-radius:999px;padding:3px 11px;font-size:.72rem;font-weight:900;margin:3px 0 6px}.v58-affects{background:#22e894;color:#05291c}.v58-context{background:#26394b;color:#e0e8ef;border:1px solid #5a6e82}
        @media(max-width:1100px){.v58-hero{grid-template-columns:1fr}.v58-hero>div+div{border-left:0;border-top:1px solid rgba(69,216,196,.30)}.v58-cards{grid-template-columns:repeat(2,1fr)}.v58-explain-grid{grid-template-columns:1fr}}@media(max-width:700px){.v58-cards{grid-template-columns:1fr}.v58-big{font-size:2.8rem}.v58-mult{font-size:2.6rem}}
        </style>
        """,
        unsafe_allow_html=True,
    )

    st.markdown(
        f"""
        <div class="v58-wrap">
          <div class="v58-hero">
            <div>
              <div class="v58-title">🛒 &nbsp; Recommended DCA This Week <span class="v58-q" title="This week's V5.8.2 production buy amount. Base Weekly Allowance × Smart DCA risk multiplier, capped by remaining capital.">?</span></div>
              <div class="v58-big">A$ {recommended_buy:,.0f}</div>
              <span class="v58-buy-pill">₿ &nbsp; BUY THIS WEEK</span>
              <span class="v58-sub" style="margin-left:10px;">That's {risk_weight:.2f}× your base weekly amount</span>
            </div>
            <div>
              <div class="v58-title">Current Multiplier <span class="v58-q" title="Production Smart DCA multiplier determined only by the V5.8.2 Risk Score curve.">?</span></div>
              <div class="v58-mult">{risk_weight:.2f}×</div>
              <div class="v58-sub"><b>Base Weekly Allowance</b></div>
              <div class="v58-base">A$ {normal_weekly_allowance:,.0f}</div>
            </div>
            <div>
              <div class="v58-title">Reason for This Week's Amount <span class="v58-q" title="Only the V5.8.2 Risk Score changes the production buy multiplier. Opportunity Rarity and Better Entry Evidence are context only.">?</span></div>
              <div class="v58-reason"><span class="v58-check">✓</span><div><b>Production signal: BUY</b><small>V5.8.2 always buys; size changes with valuation risk.</small></div></div>
              <div class="v58-reason"><span class="v58-check">✓</span><div><b>BTC risk: {risk_tone_label}</b><small>Risk {current_risk:.3f} → {risk_weight:.2f}× weekly base multiplier</small></div></div>
              <div class="v58-reason"><span class="v58-off">i</span><div><b>Cycle evidence: Context only</b><small>Rarity / Better Entry do not alter this week's amount.</small></div></div>
            </div>
          </div>

          <div class="v58-cards">
            <div class="v58-card"><div class="v58-card-title">BTC Price <span class="v58-q" title="Live BTC/AUD spot quote when available. Risk uses closed historical data.">?</span></div><div class="v58-card-value">{btc_price_main}</div><div class="v58-card-sub">({btc_price_sub})</div></div>
            <div class="v58-card"><div class="v58-card-title">BTC Risk <span class="v58-q" title="Production composite Risk Score. Lower risk produces a larger Smart DCA multiplier.">?</span></div><div class="v58-card-value {risk_tone}">{risk_tone_label}</div><div class="v58-card-sub">Risk score: {current_risk:.3f}<br>Multiplier: <b>{risk_weight:.2f}×</b></div></div>
            <div class="v58-card"><div class="v58-card-title">Opportunity Rarity <span class="v58-q" title="Cycle-based context comparing today's risk with comparable cycle ages. It does not change production sizing.">?</span></div><span class="v58-badge context">{rarity['rarity_label']}</span><div class="v58-card-sub">Context only<br>Does not change buy amount</div></div>
            <div class="v58-card"><div class="v58-card-title">Better Entry Evidence <span class="v58-q" title="Limited cycle evidence about whether comparable periods later produced lower risk. Context only.">?</span></div><span class="v58-badge context">{better_entry_text}</span><div class="v58-card-sub">Context only<br>No sizing override</div></div>
            <div class="v58-card"><div class="v58-card-title">Remaining Capital <span class="v58-q" title="Capital still scheduled for deployment. Base Weekly Allowance = remaining capital ÷ remaining weeks.">?</span></div><div class="v58-card-value">A$ {remaining_capital_aud:,.0f}</div><div class="v58-card-sub">~{weeks_remaining:.0f} weeks remaining<br>until {target_deployment_date.strftime('%d %b %Y')}</div></div>
          </div>

          <div class="v58-info"><span class="v58-info-icon">i</span><div><div class="v58-info-title">How this week's amount is calculated</div><div class="v58-info-text">This week's production DCA amount is your Base Weekly Allowance multiplied by the fixed V5.8.2 Smart DCA risk multiplier, capped by remaining capital. Opportunity Rarity, Better Entry Evidence and the Historical Weekly Risk Distribution are context only and do not independently change the buy amount.</div></div></div>

          <div class="v58-explain-grid">
            <div class="v58-explain"><h4>📈 Risk Score <span class="v58-q" title="The production sizing engine. It is not cycle-adjusted.">?</span></h4><p>Combines the production valuation/risk components into one 0–1 Risk Score.</p><span class="v58-affects">Affects buy amount</span><p>Lower risk = larger weekly multiplier.<br>Higher risk = smaller weekly multiplier.</p></div>
            <div class="v58-explain"><h4>📊 Opportunity Rarity <span class="v58-q" title="Cycle-based context only. It compares today's Risk Score with comparable periods in this halving cycle and the prior two cycles.">?</span></h4><p>Shows how unusual the current valuation risk is for comparable cycle ages.</p><span class="v58-context">Context only</span><p>Does not increase or reduce this week's DCA.</p></div>
            <div class="v58-explain"><h4>🔎 Better Entry Evidence <span class="v58-q" title="Cycle-based context only. It asks whether comparable cycle situations later produced materially lower Risk Scores.">?</span></h4><p>Helps judge whether historically similar cycle conditions later offered lower risk.</p><span class="v58-context">Context only</span><p>Does not override the production Risk Score curve.</p></div>
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    a, b, c, d = st.columns(4)
    a.metric("BTC Risk", f"{current_risk:.3f}", risk_label)
    b.metric(
        "BTC Price",
        "n/a" if not np.isfinite(current_price_aud) else f"A${current_price_aud:,.0f}",
        help="Live BTC/AUD spot quote (60-second cache) when available; otherwise latest historical BTC/AUD. Risk uses closed historical data."
    )
    c.metric("Opportunity Rarity", rarity["rarity_label"])
    if opportunity["cycles_used"] >= 1:
        d.metric(
            "Better Entry Evidence",
            f"{opportunity['cycle_successes']} of {opportunity['cycles_used']} cycles",
            help=(
                "Number of comparable BTC cycles that later produced a materially lower Risk Score. "
                "Each of the current + previous two cycles contributes at most one independent analogue. "
                "This is limited historical evidence, not a precise probability."
            ),
        )
    else:
        d.metric("Better Entry Evidence", "n/a")

    st.caption(
        ("BTC price: live BTC/AUD spot quote" if price_is_live else "BTC price: latest historical BTC/AUD fallback")
        + f" • checked {now_utc.strftime('%d/%m/%y %H:%M UTC')}. "
        "The valuation Risk Score remains based on closed historical data."
    )

    with st.expander("How the signals work", expanded=False):
        st.markdown(
            "**Risk Score = buy sizing.** The Smart DCA amount is determined by the BTC Risk Score "
            "using the fixed walk-forward-tested curve; the Risk Score itself is not cycle-adjusted.\n\n"
            "**Opportunity Rarity = cycle-based context.** It compares today's Risk Score with comparable "
            "periods in the current BTC halving cycle plus the previous two cycles.\n\n"
            "**Better Entry Evidence = cycle-based context.** It asks whether comparable cycle situations "
            "later produced a materially lower Risk Score.\n\n"
            "**Historical Weekly Risk Distribution = descriptive only.** It shows how often each Risk Score "
            "range occurred historically and is not cycle-adjusted.\n\n"
            "Opportunity Rarity and Better Entry Evidence are informational only and do **not** change the "
            "recommended purchase amount."
        )

    with st.expander("Opportunity Rarity Guide", expanded=False):
        rarity_guide = pd.DataFrame([
            ["EXTREME", "≤ 5%", "Exceptionally rare low-risk opportunity"],
            ["VERY HIGH", "> 5–10%", "Very rare opportunity"],
            ["HIGH", "> 10–20%", "Rare / attractive opportunity"],
            ["ABOVE AVERAGE", "> 20–35%", "Better than usual"],
            ["NORMAL", "> 35–60%", "Fairly typical opportunity"],
            ["COMMON", "> 60%", "This risk level or lower occurs frequently"],
        ], columns=["Opportunity Rarity", "Historical frequency", "Interpretation"])
        rarity_guide["Current"] = rarity_guide["Opportunity Rarity"].apply(
            lambda x: "← CURRENT" if x == rarity["rarity_label"] else ""
        )
        st.dataframe(rarity_guide, width="stretch", hide_index=True)
        st.caption(
            "V5.8 uses Opportunity Rarity for context only. It does not increase or reduce the recommended buy."
        )

    st.subheader("SMART DCA THIS WEEK")
    st.metric("Recommended DCA This Week", f"A${recommended_buy:,.0f}")

    x1, x2, x3 = st.columns(3)
    x1.metric("Normal Weekly Allowance", f"A${normal_weekly_allowance:,.0f}")
    x2.metric("Capital Remaining After Buy", f"A${remaining_after:,.0f}")
    x3.metric("Already Deployed", f"A${deployed:,.0f}")


    if current_risk <= 0.02:
        st.info(
            "EXTREME LOW RISK. V5.8 still follows the fixed Risk Score sizing curve; "
            "Better Entry Evidence does not trigger an automatic all-in purchase."
        )

    st.subheader("Historical Weekly Risk Distribution")
    occurrence = risk_occurrence_table(rarity_source)
    fig_occurrence = go.Figure()
    fig_occurrence.add_bar(
        x=occurrence["Risk range"],
        y=occurrence["Percent"],
        customdata=occurrence[["Weeks"]],
        hovertemplate=(
            "Risk %{x}<br>%{y:.1f}% of weekly observations"
            "<br>%{customdata[0]} weeks"
            "<extra></extra>"
        ),
    )
    fig_occurrence.update_layout(
        xaxis_title="BTC Risk Range",
        yaxis_title="Historical Weekly Frequency (%)",
        margin=dict(l=20, r=20, t=20, b=20),
        height=380,
    )
    st.plotly_chart(fig_occurrence, width="stretch")
    st.caption(
        f"Current risk {current_risk:.3f}. This chart is descriptive: it shows the percentage "
        "of weekly observations that fell inside each Risk Score range. It does NOT assign "
        "Opportunity Rarity to individual buckets. Opportunity Rarity is calculated separately "
        "as how often comparable cycle-phase observations were at or below today's risk "
        f"(currently: {rarity['rarity_label']})."
    )

    with st.expander("Chance of a lower-risk entry — current + previous 2 cycles", expanded=False):
        if opportunity["samples"] >= 1:
            st.write(
                f"Independent cycle analogues: **{opportunity['cycles_used']}** "
                f"(evidence: **{opportunity['evidence_label']}**). "
                f"Each cycle contributes at most one closest match within about "
                f"±{opportunity['tolerance']:.3f} risk and a comparable cycle phase."
            )
            st.write(
                f"Materially-lower outcome occurred in **{opportunity['cycle_successes']} of "
                f"{opportunity['cycles_used']}** comparable cycle analogues."
            )
            if np.isfinite(opportunity["chance_any_lower"]):
                st.write(f"Any lower risk: **{100.0 * opportunity['chance_any_lower']:.0f}%**")
            if np.isfinite(opportunity["chance_materially_lower"]):
                st.write(
                    f"Materially lower risk (≤ {opportunity['material_threshold']:.3f}): "
                    f"**{opportunity['cycle_successes']} of {opportunity['cycles_used']} cycles**"
                )
            st.write(
                "Historical chance of reaching risk ≤0.05 / ≤0.02 / ≤0.01: "
                f"**{100.0 * opportunity['chance_le_005']:.0f}% / "
                f"{100.0 * opportunity['chance_le_002']:.0f}% / "
                f"{100.0 * opportunity['chance_le_001']:.0f}%**"
            )
            st.caption(
                "This uses at most one representative analogue per BTC cycle to avoid counting "
                "overlapping weeks as independent evidence. With only up to three cycles, treat "
                "the percentage as a historical decision-support rate, not a precise probability."
            )
        else:
            st.write("Not enough comparable historical observations for a useful estimate.")

    if current_risk <= 0.40:
        st.success(
            f"BTC valuation is {risk_label.lower()} and opportunity rarity is {rarity['rarity_label'].lower()}. "
            f"The fixed Smart DCA risk weight is {risk_weight:.2f}×. Opportunity Rarity is informational only."
        )
    elif current_risk >= 0.60:
        st.info(
            f"BTC valuation is {risk_label.lower()} and opportunity rarity is {rarity['rarity_label'].lower()}. "
            f"The model is preserving capital with a Risk Score weight of {risk_weight:.2f}×."
        )
    else:
        st.info(
            f"BTC valuation is neutral and opportunity rarity is {rarity['rarity_label'].lower()}. "
            f"The Risk Score allocation weight is {risk_weight:.2f}×."
        )

    with st.expander("How this amount is calculated", expanded=False):
        st.write(
            "Normal weekly allowance = capital remaining ÷ weeks remaining. "
            "That allowance is multiplied only by the fixed Smart DCA weight from today's Risk Score, "
            "then capped at remaining capital."
        )
        st.write(
            f"A${remaining_capital_aud:,.0f} ÷ {weeks_remaining:.1f} weeks "
            f"× {risk_weight:.2f} Risk Score weight "
            f"= A${recommended_buy:,.0f}"
        )
        if np.isfinite(rarity["percentile"]):
            st.write(
                f"Historically, only about {rarity['percentile']:.1f}% of weekly observations "
                f"were at least as cheap as today's risk level. At that historical frequency, "
                f"a four-year cycle would contain roughly {rarity['expected_comparable_weeks_4y']:.0f} "
                "comparable-or-cheaper weekly observations."
            )
        st.caption(
            "This is a live capital-allocation rule, not a future-price forecast. "
            "It does not know future risk scores and does not retrospectively normalize future purchases. "
            "The experimental full-deployment gate can only open below risk 0.01 when enough historical "
            "analogues exist and the estimated chance of a materially better entry is low."
        )

# ================================================================
# My Portfolio
# ================================================================

elif mode == "My Portfolio":
    st.header("My Portfolio")
    st.caption(
        "Track direct BTC and the Australian iShares Bitcoin ETF (ASX: IBIT). "
        "IBIT entries are reported as BTC-equivalent exposure — ETF units are not direct ownership of bitcoin."
    )

    st.info(
        "Australian IBIT only: iShares Bitcoin ETF, ASX ticker IBIT, Australian domicile, "
        "ISIN AU0000424780. Default brokerage per ETF buy is A$3."
    )
    st.caption(
        "Portfolio entries are saved automatically in this browser/device when browser storage is available. "
        "CSV export remains a portable backup for another device or browser."
    )

    portfolio_cols = [
        "Date",
        "Asset",
        "AUD Spent",
        "Brokerage / Fee AUD",
        "Units / BTC Received",
        "BTC AUD Price",
    ]

    if portfolio_snapshots:
        with st.expander("Recover a browser portfolio snapshot", expanded=False):
            st.caption(
                "This reads existing browser copies only. Loading a snapshot does not overwrite storage "
                "until you inspect it and press Save Portfolio Changes."
            )
            snapshot_labels = [
                f"{item['source']} — {item['rows']} rows, latest {item['latest']}"
                for item in portfolio_snapshots
            ]
            selected_snapshot_label = st.selectbox(
                "Available browser snapshots",
                snapshot_labels,
                key="portfolio_recovery_snapshot",
            )
            if st.button(
                "Load selected snapshot into editor",
                key="portfolio_recovery_load",
                use_container_width=True,
            ):
                selected_snapshot = portfolio_snapshots[
                    snapshot_labels.index(selected_snapshot_label)
                ]["portfolio"]
                st.session_state["portfolio_live_rows"] = selected_snapshot.get("rows", [])
                st.session_state["portfolio_live_starting_capital"] = float(
                    selected_snapshot.get("starting_capital_aud", 500000.0)
                )
                st.session_state["portfolio_recovery_loaded"] = selected_snapshot_label
                st.rerun()

    saved_portfolio = shared_portfolio if isinstance(shared_portfolio, dict) else {}
    saved_rows = saved_portfolio.get("rows", [])
    if not saved_rows:
        st.warning(
            "No saved browser portfolio was loaded. The built-in starter rows ending 02/09/26 "
            "will be shown. If you expected newer transactions, do not press Save until you "
            "recover a browser snapshot or import your CSV backup."
        )

    # Reliable editing model:
    # keep one authoritative copy in Streamlit session state and submit all
    # portfolio edits as one transaction. st.form prevents data_editor from
    # triggering a rerun for every individual cell, which was the cause of
    # values sometimes needing to be entered more than once.
    if "portfolio_live_rows" not in st.session_state:
        st.session_state["portfolio_live_rows"] = (
            saved_rows if isinstance(saved_rows, list) else []
        )
    if "portfolio_live_starting_capital" not in st.session_state:
        st.session_state["portfolio_live_starting_capital"] = float(
            saved_portfolio.get("starting_capital_aud", 500000.0)
        )

    portfolio_df = (
        pd.DataFrame(st.session_state["portfolio_live_rows"])
        if st.session_state["portfolio_live_rows"]
        else pd.DataFrame(columns=portfolio_cols)
    )
    for col in portfolio_cols:
        if col not in portfolio_df.columns:
            portfolio_df[col] = "" if col in ("Date", "Asset") else 0.0
    portfolio_df = portfolio_df[portfolio_cols]

    uploaded_portfolio = st.file_uploader(
        "Load portfolio CSV (optional)", type=["csv"], key="portfolio_csv_upload"
    )
    if uploaded_portfolio is not None:
        upload_token = getattr(uploaded_portfolio, "file_id", None) or getattr(uploaded_portfolio, "name", "uploaded")
        if st.session_state.get("portfolio_last_upload_token") != upload_token:
            try:
                uploaded_df = pd.read_csv(uploaded_portfolio)
                for col in portfolio_cols:
                    if col not in uploaded_df.columns:
                        if col == "Asset":
                            uploaded_df[col] = "ASX:IBIT"
                        elif col == "Date":
                            uploaded_df[col] = ""
                        else:
                            uploaded_df[col] = 0.0
                portfolio_df = uploaded_df[portfolio_cols]
                st.session_state["portfolio_live_rows"] = portfolio_df.to_dict(orient="records")
                st.session_state["portfolio_last_upload_token"] = upload_token
            except Exception as exc:
                st.error(f"Could not read portfolio CSV: {exc}")

    st.subheader("Purchases")
    st.caption(
        "For ASX:IBIT enter the purchase date as DD/MM/YY, units bought and total AUD trade value. "
        "Brokerage defaults to A$3. The app automatically looks up BTC/AUD for the purchase date "
        "and calculates BTC-equivalent exposure. For Direct BTC, enter the actual BTC received."
    )

    # Restore the original starter rows only when there is no saved portfolio.
    if portfolio_df.empty:
        portfolio_df = pd.DataFrame([
            {
                "Date": "19/06/26",
                "Asset": "ASX:IBIT",
                "AUD Spent": 1700.0,
                "Brokerage / Fee AUD": 3.0,
                "Units / BTC Received": 100.0,
                "BTC AUD Price": 0.0,
            },
            {
                "Date": "26/08/26",
                "Asset": "ASX:IBIT",
                "AUD Spent": 2092.0,
                "Brokerage / Fee AUD": 3.0,
                "Units / BTC Received": 100.0,
                "BTC AUD Price": 0.0,
            },
            {
                "Date": "31/08/26",
                "Asset": "ASX:IBIT",
                "AUD Spent": 2061.0,
                "Brokerage / Fee AUD": 3.0,
                "Units / BTC Received": 100.0,
                "BTC AUD Price": 0.0,
            },
            {
                "Date": "01/09/26",
                "Asset": "ASX:IBIT",
                "AUD Spent": 2087.0,
                "Brokerage / Fee AUD": 3.0,
                "Units / BTC Received": 100.0,
                "BTC AUD Price": 0.0,
            },
            {
                "Date": "02/09/26",
                "Asset": "ASX:IBIT",
                "AUD Spent": 2050.0,
                "Brokerage / Fee AUD": 3.0,
                "Units / BTC Received": 100.0,
                "BTC AUD Price": 0.0,
            },
        ])
        st.session_state["portfolio_live_rows"] = portfolio_df.to_dict(orient="records")

    with st.form("portfolio_edit_form", clear_on_submit=False):
        starting_portfolio_capital = st.number_input(
            "Starting Deployment Capital (AUD)",
            min_value=0.0,
            value=float(st.session_state["portfolio_live_starting_capital"]),
            step=10000.0,
            format="%.2f",
            key="portfolio_starting_capital_form",
        )

        edited_portfolio = st.data_editor(
            portfolio_df,
            num_rows="dynamic",
            width="stretch",
            hide_index=True,
            column_config={
                "Date": st.column_config.TextColumn(
                    "Date (DD/MM/YY)",
                    help="Australian date format, e.g. 02/09/26",
                ),
                "Asset": st.column_config.SelectboxColumn(
                    "Asset",
                    options=["ASX:IBIT", "Direct BTC"],
                    required=True,
                ),
                "AUD Spent": st.column_config.NumberColumn(
                    "AUD Spent", min_value=0.0, format="A$%.2f"
                ),
                "Brokerage / Fee AUD": st.column_config.NumberColumn(
                    "Brokerage / Fee AUD", min_value=0.0, default=3.0, format="A$%.2f"
                ),
                "Units / BTC Received": st.column_config.NumberColumn(
                    "Units / BTC Received", min_value=0.0, format="%.8f"
                ),
            },
            column_order=[
                "Date",
                "Asset",
                "AUD Spent",
                "Brokerage / Fee AUD",
                "Units / BTC Received",
            ],
            key="portfolio_editor_form",
        )
        portfolio_submit = st.form_submit_button(
            "Save Portfolio Changes",
            type="primary",
            use_container_width=True,
        )

    if portfolio_submit:
        st.session_state["portfolio_live_rows"] = edited_portfolio[portfolio_cols].to_dict(orient="records")
        st.session_state["portfolio_live_starting_capital"] = float(starting_portfolio_capital)
        st.session_state["portfolio_starting_capital"] = float(starting_portfolio_capital)
        st.session_state["portfolio_save_pending"] = True
    else:
        # Outside a submit rerun, calculations use the last committed state.
        edited_portfolio = pd.DataFrame(st.session_state["portfolio_live_rows"])
        for col in portfolio_cols:
            if col not in edited_portfolio.columns:
                edited_portfolio[col] = "" if col in ("Date", "Asset") else 0.0
        edited_portfolio = edited_portfolio[portfolio_cols]
        starting_portfolio_capital = float(st.session_state["portfolio_live_starting_capital"])

    clean = edited_portfolio.copy()
    for col in ["AUD Spent", "Brokerage / Fee AUD", "Units / BTC Received", "BTC AUD Price"]:
        clean[col] = pd.to_numeric(clean[col], errors="coerce").fillna(0.0)

    # Australian date format: DD/MM/YY. Also accept ISO dates from older V5.6 CSVs.
    def _parse_portfolio_date(value):
        if pd.isna(value):
            return pd.NaT
        s = str(value).strip()
        for fmt in ("%d/%m/%y", "%d/%m/%Y", "%Y-%m-%d"):
            try:
                return pd.Timestamp(dt.datetime.strptime(s, fmt).date())
            except Exception:
                pass
        return pd.to_datetime(s, dayfirst=True, errors="coerce")

    clean["_purchase_date"] = clean["Date"].apply(_parse_portfolio_date)

    # Automatically populate BTC/AUD for ASX:IBIT rows from the same BTC + FX data
    # used elsewhere in the app. This avoids manual BTC price entry.
    ibit_dates = clean.loc[
        clean["Asset"].eq("ASX:IBIT") & clean["_purchase_date"].notna(),
        "_purchase_date"
    ]
    if not ibit_dates.empty:
        lookup_start = ibit_dates.min().date() - dt.timedelta(days=7)
        lookup_end = max(ibit_dates.max().date(), dt.date.today())
        try:
            btc_lookup = fetch_btc_history(lookup_start, lookup_end)
            fx_lookup = fetch_aud_usd_rates(lookup_start, lookup_end)
            if btc_lookup is not None and not btc_lookup.empty and fx_lookup is not None and not fx_lookup.empty:
                lookup = btc_lookup[["price"]].copy()

                # Normalize both BTC and FX lookup keys to timezone-naive midnight
                # Timestamps. This avoids comparing UTC DatetimeIndex values with
                # plain Python date objects.
                lookup_dates = pd.to_datetime(lookup.index, utc=True).tz_convert(None).normalize()
                lookup["lookup_date"] = lookup_dates

                fx_series = pd.Series(fx_lookup, dtype=float)
                fx_series.index = (
                    pd.to_datetime(fx_series.index, utc=True)
                    .tz_convert(None)
                    .normalize()
                )

                fx_aligned = fx_series.reindex(
                    pd.DatetimeIndex(lookup["lookup_date"]),
                    method="ffill"
                )
                if fx_aligned.isna().any():
                    fx_aligned = fx_aligned.bfill()
                lookup["usd_per_aud"] = fx_aligned.to_numpy()
                lookup["btc_aud_auto"] = lookup["price"] / lookup["usd_per_aud"]

                daily_btc_aud = (
                    lookup.dropna(subset=["btc_aud_auto"])
                    .groupby("lookup_date")["btc_aud_auto"]
                    .last()
                    .sort_index()
                )

                for row_idx in clean.index[clean["Asset"].eq("ASX:IBIT")]:
                    pd_date = clean.at[row_idx, "_purchase_date"]
                    if pd.isna(pd_date):
                        continue

                    d = pd.Timestamp(pd_date).tz_localize(None).normalize()

                    if d in daily_btc_aud.index:
                        clean.at[row_idx, "BTC AUD Price"] = float(daily_btc_aud.loc[d])
                    else:
                        prior = daily_btc_aud.loc[:d]
                        if not prior.empty:
                            clean.at[row_idx, "BTC AUD Price"] = float(prior.iloc[-1])
        except Exception as exc:
            st.warning(f"Could not automatically load BTC/AUD for one or more purchases: {exc}")

    # Calculate BTC-equivalent exposure per transaction.
    #
    # ASX:IBIT:
    #   trade value excluding brokerage / BTC-AUD price on transaction date
    # This is the economic BTC-equivalent represented by the AUD value committed to the ETF.
    # It is deliberately labelled equivalent exposure, not direct BTC ownership.
    #
    # Direct BTC:
    #   uses the actual BTC received entered by the user.
    clean["BTC Equivalent"] = 0.0
    ibit_mask = clean["Asset"].eq("ASX:IBIT")
    direct_mask = clean["Asset"].eq("Direct BTC")

    # Treat "AUD Spent" as the ETF trade consideration excluding brokerage.
    valid_ibit = ibit_mask & (clean["BTC AUD Price"] > 0)
    clean.loc[valid_ibit, "BTC Equivalent"] = (
        clean.loc[valid_ibit, "AUD Spent"] / clean.loc[valid_ibit, "BTC AUD Price"]
    )
    clean.loc[direct_mask, "BTC Equivalent"] = clean.loc[direct_mask, "Units / BTC Received"]

    # Useful audit fields for ETF buys.
    clean["ETF Unit Price AUD"] = np.nan
    valid_units = ibit_mask & (clean["Units / BTC Received"] > 0)
    clean.loc[valid_units, "ETF Unit Price AUD"] = (
        clean.loc[valid_units, "AUD Spent"] / clean.loc[valid_units, "Units / BTC Received"]
    )
    clean["BTC Eq / ETF Unit"] = np.nan
    valid_eq_unit = valid_units & (clean["BTC AUD Price"] > 0)
    clean.loc[valid_eq_unit, "BTC Eq / ETF Unit"] = (
        clean.loc[valid_eq_unit, "ETF Unit Price AUD"] /
        clean.loc[valid_eq_unit, "BTC AUD Price"]
    )

    total_trade_value = float(clean["AUD Spent"].sum())
    total_fees = float(clean["Brokerage / Fee AUD"].sum())
    total_cash_out = total_trade_value + total_fees
    total_btc_equivalent = float(clean["BTC Equivalent"].sum())
    direct_btc = float(clean.loc[direct_mask, "BTC Equivalent"].sum())
    ibit_btc_equivalent = float(clean.loc[ibit_mask, "BTC Equivalent"].sum())
    ibit_units = float(clean.loc[ibit_mask, "Units / BTC Received"].sum())
    capital_remaining = max(0.0, float(starting_portfolio_capital) - total_cash_out)
    avg_cost = total_cash_out / total_btc_equivalent if total_btc_equivalent > 0 else np.nan

    st.session_state["portfolio_starting_capital"] = float(starting_portfolio_capital)
    st.session_state["portfolio_capital_remaining"] = float(capital_remaining)

    p1, p2, p3, p4 = st.columns(4)
    p1.metric("Total BTC Exposure", f"{total_btc_equivalent:.8f} BTC-eq")
    p2.metric("ASX:IBIT Units", f"{ibit_units:,.4f}")
    p3.metric("Capital Remaining", f"A${capital_remaining:,.0f}")
    p4.metric(
        "Average Cost",
        "n/a" if not np.isfinite(avg_cost) else f"A${avg_cost:,.0f}/BTC-eq"
    )

    q1, q2, q3, q4 = st.columns(4)
    q1.metric("IBIT BTC-equivalent", f"{ibit_btc_equivalent:.8f}")
    q2.metric("Direct BTC", f"{direct_btc:.8f}")
    q3.metric("Trade Value", f"A${total_trade_value:,.0f}")
    q4.metric("Brokerage / Fees", f"A${total_fees:,.2f}")

    # Current portfolio valuation. For ASX:IBIT this is a BTC-equivalent estimate
    # based on live BTC/AUD, not the exact traded ASX market price of the ETF.
    portfolio_live_btc_aud = fetch_live_btc_aud()
    if not np.isfinite(portfolio_live_btc_aud) or portfolio_live_btc_aud <= 0:
        try:
            _end = dt.date.today()
            _start = _end - dt.timedelta(days=10)
            _btc_hist = fetch_btc_history(_start, _end)
            _fx_hist = fetch_aud_usd_rates(_start, _end)
            if (
                _btc_hist is not None and not _btc_hist.empty and
                _fx_hist is not None and not _fx_hist.empty
            ):
                _latest_btc_usd = float(_btc_hist["price"].dropna().iloc[-1])
                _fx_series = pd.Series(_fx_hist, dtype=float).dropna()
                _latest_usd_per_aud = float(_fx_series.iloc[-1])
                if _latest_btc_usd > 0 and _latest_usd_per_aud > 0:
                    portfolio_live_btc_aud = _latest_btc_usd / _latest_usd_per_aud
        except Exception:
            portfolio_live_btc_aud = np.nan

    current_investment_value = (
        total_btc_equivalent * portfolio_live_btc_aud
        if total_btc_equivalent > 0 and np.isfinite(portfolio_live_btc_aud) and portfolio_live_btc_aud > 0
        else np.nan
    )
    unrealized_pl = (
        current_investment_value - total_cash_out
        if np.isfinite(current_investment_value) and total_cash_out > 0
        else np.nan
    )
    total_return_pct = (
        (unrealized_pl / total_cash_out) * 100.0
        if np.isfinite(unrealized_pl) and total_cash_out > 0
        else np.nan
    )

    v1, v2, v3 = st.columns(3)
    v1.metric(
        "Current Investment Value",
        "n/a" if not np.isfinite(current_investment_value) else f"A${current_investment_value:,.0f}",
        help="Estimated from total BTC-equivalent exposure × current BTC/AUD. For ASX:IBIT this is an economic BTC-equivalent estimate, not the exact live ASX ETF market value.",
    )
    v2.metric(
        "Unrealised Return",
        "n/a" if not np.isfinite(unrealized_pl) else f"A${unrealized_pl:,.0f}",
    )
    v3.metric(
        "Return",
        "n/a" if not np.isfinite(total_return_pct) else f"{total_return_pct:+.2f}%",
        help="(Current estimated investment value − total cash paid including brokerage/fees) ÷ total cash paid.",
    )
    if np.isfinite(portfolio_live_btc_aud):
        st.caption(
            f"Portfolio valuation uses BTC/AUD ≈ A${portfolio_live_btc_aud:,.0f}. "
            "ASX:IBIT value is estimated from BTC-equivalent exposure, so it can differ from the ETF's exact live ASX market value due to tracking difference, fees and market pricing."
        )

    st.subheader("Calculated Transactions")
    clean["Date"] = clean["_purchase_date"].apply(
        lambda x: x.strftime("%d/%m/%y") if pd.notna(x) else ""
    )
    display_cols = [
        "Date", "Asset", "AUD Spent", "Brokerage / Fee AUD",
        "Units / BTC Received", "ETF Unit Price AUD", "BTC AUD Price",
        "BTC Eq / ETF Unit", "BTC Equivalent"
    ]
    st.dataframe(clean[display_cols], width="stretch", hide_index=True)

    st.caption(
        "For ASX:IBIT, the app calculates the ETF unit price from AUD spent ÷ units, automatically "
        "looks up BTC/AUD for the purchase date, then estimates BTC-equivalent exposure as AUD trade "
        "value ÷ BTC/AUD. This is an economic exposure estimate, not the exact bitcoin legally held "
        "for each ETF unit."
    )

    export_clean = clean.drop(columns=["_purchase_date"], errors="ignore")
    st.download_button(
        "Download Portfolio CSV",
        data=export_clean.to_csv(index=False).encode("utf-8"),
        file_name="btc_portfolio_asx_ibit.csv",
        mime="text/csv",
        key="portfolio_download",
    )

    st.subheader("Decision History")
    st.caption("Optional audit trail: what the model showed versus what you actually bought.")

    decision_cols = [
        "Date", "BTC Price AUD", "Risk", "Better Entry Chance %",
        "Model Recommendation AUD", "Actual Purchase AUD", "Asset"
    ]
    saved_decisions = browser_state.get("decision_rows", []) if isinstance(browser_state, dict) else []
    decision_df = pd.DataFrame(saved_decisions) if isinstance(saved_decisions, list) and saved_decisions else pd.DataFrame(columns=decision_cols)
    for col in decision_cols:
        if col not in decision_df.columns:
            decision_df[col] = ""
    decision_df = decision_df[decision_cols]

    decision_upload = st.file_uploader(
        "Load decision-history CSV (optional)", type=["csv"], key="decision_csv_upload"
    )
    if decision_upload is not None:
        try:
            decision_df = pd.read_csv(decision_upload)
            for col in decision_cols:
                if col not in decision_df.columns:
                    decision_df[col] = ""
            decision_df = decision_df[decision_cols]
        except Exception as exc:
            st.error(f"Could not read decision-history CSV: {exc}")
            decision_df = pd.DataFrame(columns=decision_cols)

    edited_decisions = st.data_editor(
        decision_df, num_rows="dynamic", width="stretch", hide_index=True,
        key="decision_history_editor"
    )
    st.download_button(
        "Download Decision History CSV",
        data=edited_decisions.to_csv(index=False).encode("utf-8"),
        file_name="btc_dca_decision_history.csv",
        mime="text/csv",
        key="decision_download",
    )

    # Automatic browser persistence for portfolio + decision history.
    # Browser-local online version: commit portfolio only after the form submit.
    # Session state remains authoritative during the current browser session.
    browser_state["decision_rows"] = edited_decisions[decision_cols].to_dict(orient="records")

    if st.session_state.pop("portfolio_save_pending", False):
        browser_state["portfolio"] = {
            "starting_capital_aud": float(starting_portfolio_capital),
            "capital_remaining_aud": float(capital_remaining),
            "rows": export_clean[portfolio_cols].to_dict(orient="records"),
        }
        _save_shared_portfolio(browser_state["portfolio"])
        shared_portfolio = browser_state["portfolio"].copy()
        _save_browser_state(browser_state)
        st.success(
            "Portfolio saved in this browser. Changes are committed only when you press “Save Portfolio Changes”."
        )
    else:
        _save_browser_state(browser_state)
        st.caption("Portfolio changes are committed only when you press “Save Portfolio Changes”.")

    if LOCAL_STORAGE_AVAILABLE:
        st.success(
            "Saved automatically in this browser. CSV download remains available as a portable backup."
        )
    else:
        st.warning(
            "Browser-local saving is unavailable in this deployment. Use the CSV download as backup."
        )
