#!/usr/bin/env python3
"""Streamlit UI for V5.8.2 Production. Calculation/data logic lives in production_model.py."""
from pathlib import Path as _Path
from concurrent.futures import ThreadPoolExecutor
import sys as _sys

_REPO_ROOT = _Path(__file__).resolve().parents[2]
if str(_REPO_ROOT) not in _sys.path:
    _sys.path.insert(0, str(_REPO_ROOT))

from engines.production import production_model as _model
from engines.shared.dca_purchase_status import dca_purchase_display
from engines.shared.portfolio_store import load_portfolio, save_portfolio
from engines.shared.ibit_dca_display import show_ibit_dca_equivalent
from engines.shared.btc_ibit_comparison import show_btc_ibit_comparison
from engines.shared.model_settings_store import (
    load_dca_target_date,save_dca_target_date,choose_target_date,
)
from engines.shared.portfolio_transactions import merge_legacy_purchase_editor,portfolio_positions
from engines.shared.broker_portfolio_snapshot import (
    snapshot_as_portfolio_positions, render_broker_snapshot_editor, merge_broker_snapshot,
)
from engines.shared.portfolio_buy_tables import (
    add_btc_usd_reference, parse_portfolio_date, render_purchase_editor, render_calculated_transactions,
)
from engines.shared.risk_ladder_chart import risk_ladder_chart_labels
from engines.shared.portfolio_execution_accuracy import (
    calculate_portfolio_entry_error, DEFAULT_REFERENCE_USD, DEFAULT_REFERENCE_DATE,
)

# Preserve the historical UI namespace so the unchanged Streamlit UI behaves
# exactly as before, including helpers whose names begin with an underscore.
globals().update({k: v for k, v in vars(_model).items() if not k.startswith("__")})


def _fetch_market_inputs(btc_start, btc_end, fx_start, bg_start, token):
    """Fetch independent market inputs concurrently to reduce cold-load latency."""
    with ThreadPoolExecutor(max_workers=3, thread_name_prefix="btc-market-data") as pool:
        btc_future = pool.submit(fetch_btc_history, btc_start, btc_end)
        fx_future = pool.submit(fetch_aud_usd_rates, fx_start, btc_end)
        bg_future = pool.submit(fetch_bgeometrics_bundle, bg_start, btc_end, token)
        return btc_future.result(), fx_future.result(), bg_future.result()

# ================================================================
# Streamlit UI
# ================================================================

if not globals().get("BTC_SIDEBAR_ONLY", False):
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
                max_value=16.0,
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
verified_portfolio_positions = None
portfolio_verified = False
broker_snapshot_error = None
broker_snapshot_ledger_warning = None

if globals().get("BTC_SIDEBAR_ONLY", False):
    # Research dashboards need the Production controls, not its portfolio.
    # Avoid browser recovery scans and durable Google/SQLite reads on every
    # research-page rerun. Production itself retains the full verification path.
    portfolio_snapshots = []
    browser_portfolio = {}
    server_portfolio = {}
    shared_portfolio = {}
    portfolio_storage_error = "Portfolio loading is intentionally skipped in sidebar-only mode."
else:
    portfolio_snapshots = _load_portfolio_snapshots(browser_state)
    browser_portfolio = _load_shared_portfolio(browser_state)
    server_portfolio, portfolio_storage_error = load_portfolio()
    shared_portfolio = server_portfolio if server_portfolio.get("rows") else browser_portfolio
    if server_portfolio.get("broker_snapshot"):
        shared_portfolio = dict(shared_portfolio) if isinstance(shared_portfolio, dict) else {}
        shared_portfolio["broker_snapshot"] = server_portfolio["broker_snapshot"]
    # DCA Today may use only the authoritative durable portfolio. Browser snapshots
    # remain available to My Portfolio recovery, but never authorise a cash recommendation.
    if not portfolio_storage_error and isinstance(server_portfolio, dict):
        _broker_snapshot = server_portfolio.get("broker_snapshot")
        if _broker_snapshot:
            try:
                verified_portfolio_positions = snapshot_as_portfolio_positions(_broker_snapshot)
                portfolio_verified = True
                _ledger_candidate = server_portfolio
                if not _ledger_candidate.get("rows") and isinstance(browser_portfolio, dict):
                    _ledger_candidate = browser_portfolio
                if _ledger_candidate.get("rows"):
                    try:
                        _ledger_positions = portfolio_positions(_ledger_candidate)
                        if abs(float(_ledger_positions["ibit_units"]) - float(verified_portfolio_positions["ibit_units"])) > 0.5:
                            broker_snapshot_ledger_warning = (
                                f"Broker snapshot shows {verified_portfolio_positions['ibit_units']:,.0f} IBIT units; "
                                f"the selected transaction ledger records {_ledger_positions['ibit_units']:,.0f}. "
                                "Current cash sizing uses the dated broker snapshot; reconcile the historical ledger separately."
                            )
                    except (ValueError, TypeError, KeyError) as ledger_exc:
                        broker_snapshot_ledger_warning = (
                            f"The historical transaction ledger is not currently reconcilable ({ledger_exc}). "
                            "Current cash sizing uses the separate dated broker snapshot."
                        )
            except (ValueError, TypeError, KeyError) as exc:
                broker_snapshot_error = str(exc)
    if (
        not portfolio_verified
        and not portfolio_storage_error
        and isinstance(server_portfolio, dict)
        and isinstance(server_portfolio.get("rows"), list)
        and len(server_portfolio.get("rows", [])) > 0
    ):
        try:
            verified_portfolio_positions = portfolio_positions(server_portfolio)
            portfolio_verified = True
        except Exception:
            verified_portfolio_positions = None

if not globals().get("BTC_SIDEBAR_ONLY", False):
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
        SMART_DCA_POINTS, "production_multiplier_curve_v2"
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
        if not portfolio_verified:
            if globals().get("BTC_SIDEBAR_ONLY", False):
                st.info(
                    "Production portfolio verification is intentionally skipped while "
                    "its sidebar is displayed on a research dashboard. No Production "
                    "purchase recommendation or trade calculation is active here."
                )
            else:
                st.error(
                    "PURCHASE RECOMMENDATION BLOCKED — the authoritative Google/SQLite "
                    "portfolio could not be verified. Browser recovery data is not trusted "
                    "for cash sizing. Market data and risk signals remain available; "
                    "restore or verify the saved portfolio in My Portfolio, then reload."
                )
        elif verified_portfolio_positions.get("broker_snapshot"):
            _bs = verified_portfolio_positions["broker_snapshot"]
            st.info(
                f"Broker snapshot {_bs['as_of']}: A${_bs['cash_aud']:,.2f} cash now + "
                f"A${_bs['aaa_reserve_aud']:,.2f} AAA reserve "
                f"= A${_bs['deployable_reserve_aud']:,.2f} deployable. "
                "AAA is counted only because liquidation was explicitly confirmed. "
                "Snapshot is user-entered, not a live brokerage feed."
            )
            if broker_snapshot_ledger_warning:
                st.warning(broker_snapshot_ledger_warning)
        elif broker_snapshot_error:
            st.warning(f"Saved broker snapshot cannot authorise sizing: {broker_snapshot_error}")

        saved_today = browser_state.get("today", {}) if isinstance(browser_state, dict) else {}
        saved_portfolio = server_portfolio if portfolio_verified else {}

        starting_default = (
            float(verified_portfolio_positions["starting_capital_aud"])
            if portfolio_verified else 1_000.0
        )
        starting_capital_aud = st.number_input(
            "Starting Capital (AUD)",
            min_value=1_000.0, max_value=100_000_000.0,
            value=starting_default, step=10_000.0, format="%.0f",
            key="today_starting_capital",
            disabled=not portfolio_verified,
        )

        # Recompute available cash from the executed ledger; do not trust a
        # potentially stale cached capital_remaining_aud field.
        remaining_default = (
            float(verified_portfolio_positions["cash_remaining_aud"])
            if portfolio_verified else 0.0
        )

        remaining_capital_aud = st.number_input(
            "Deployable Reserve (cash + sellable AAA, AUD)" if verified_portfolio_positions and verified_portfolio_positions.get("broker_snapshot") else "Capital Remaining (AUD)",
            min_value=0.0, max_value=float(starting_capital_aud),
            value=min(float(starting_capital_aud), float(remaining_default)),
            step=5_000.0, format="%.0f",
            key="today_remaining_capital",
            disabled=not portfolio_verified,
        )
        if not portfolio_verified:
            # Ignore any stale Streamlit widget state while storage is unavailable.
            remaining_capital_aud = 0.0

        # Date persistence used to rely on browser LocalStorage only.
        # Read the independent, persistent Google/SQLite preference
        # BEFORE rendering the widget; never alter trade/portfolio rows.
        default_target = dt.date.today() + dt.timedelta(days=365 * 3)
        min_target = dt.date.today() + dt.timedelta(days=7)
        durable_target, date_load_error = load_dca_target_date("production")
        saved_target, has_user_target = choose_target_date(
            server_date=durable_target,
            browser_date=saved_today.get("target_date"),
            default_date=default_target,
            min_date=min_target,
        )
        target_deployment_date = st.date_input(
            "Target Deployment Date",
            value=saved_target,
            min_value=min_target,
            format="DD/MM/YYYY",
            key="production_today_target_date",
        )

        # Persist a real selected date immediately; migrate existing
        # browser-only choices once, but never save an autogenerated
        # three-year fallback as if the user selected it.
        if (has_user_target or target_deployment_date != default_target) and (
            durable_target != target_deployment_date.isoformat()
        ):
            saved_ok, date_save_error = save_dca_target_date(
                "production", target_deployment_date
            )
            if not saved_ok:
                st.warning(
                    "Your selected date is still available in this browser, "
                    "but could not be saved across devices: " +
                    str(date_save_error)
                )
        elif date_load_error:
            st.caption(
                "Date storage is currently unavailable. Existing "
                "browser settings are used until it reconnects."
            )


        low_risk_weight = SMART_DCA_LOW_RISK_WEIGHT
        high_risk_weight = SMART_DCA_HIGH_RISK_WEIGHT
        smart_dca_curve = active_smart_dca_curve

        st.caption(
            "Custom V5.8.2 multiplier curve is active."
            if custom_curve_active else
            "V5.8.2 uses its configured default risk multiplier curve; the zero-buy threshold is determined by that curve."
        )

        if portfolio_verified:
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
