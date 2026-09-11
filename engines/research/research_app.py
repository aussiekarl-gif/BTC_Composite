#!/usr/bin/env python3
"""Streamlit UI for V5.9 Research. Calculation/data logic lives in research_model.py."""
from pathlib import Path as _Path
import sys as _sys

_REPO_ROOT = _Path(__file__).resolve().parents[2]
if str(_REPO_ROOT) not in _sys.path:
    _sys.path.insert(0, str(_REPO_ROOT))

from engines.research import research_model as _model

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


def _save_shared_portfolio(portfolio):
    """Persist only portfolio inputs in a cross-version shared namespace."""
    if not LOCAL_STORAGE_AVAILABLE or not isinstance(portfolio, dict):
        return
    try:
        store = LocalStorage()
        store.setItem(SHARED_PORTFOLIO_KEY, json.dumps(portfolio, default=str))
    except Exception:
        pass

browser_state = _load_browser_state()
shared_portfolio = _load_shared_portfolio(browser_state)

st.title("Bitcoin Dynamic DCA V5.9 — Three-Pillar Research")
st.caption("Version 5.9 RESEARCH • R2 Valuation • Exceptional Bottom Zone • Halving Accumulation Zone • Persistent portfolio")
st.caption("Simple three-mode app • DCA Today • DCA Backtest • My Portfolio")

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

    if mode == "DCA Backtest":
        st.header("DCA Backtest")

        saved_bt = browser_state.get("backtest", {}) if isinstance(browser_state, dict) else {}
        # Execution timing is intentionally fixed after historical testing:
        # one purchase each Monday. Keep the internal engine value as "Weekly"
        # so the proven weekly calculations remain unchanged.
        dca_frequency = "Weekly"
        selected_day_name = "Monday"
        selected_day = 0
        dca_base_amount_aud = DEFAULT_FIXED_DCA_AUD
        st.markdown("**Execution: Monday DCA**")
        st.caption("One purchase each Monday. Daily and split execution were tested and did not improve BTC accumulation.")

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
        smart_dca_curve = SMART_DCA_POINTS

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

        total_capital_aud = 0.0
        frequency = dca_frequency

        st.caption(
            "Same budget and dates. Both strategies deploy sequentially every Monday; Smart DCA uses only information available at each execution."
        )
        browser_state["backtest"] = {
            "frequency": "Monday DCA",
            "budget_aud": float(intelligent_dca_budget_aud),
            "start_date": dca_backtest_start_date.isoformat(),
            "end_date": dca_backtest_end_date.isoformat(),
            "weekday": "Monday",
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
        smart_dca_curve = SMART_DCA_POINTS

        st.caption(
            "V5.9 Research sizing: causal walk-forward Power Law risk with a moderate curve — "
            "2.00× at risk 0.00, 1.00× at risk 0.50, and 0.80× at risk 1.00."
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
        smart_dca_curve = SMART_DCA_POINTS

    st.divider()
    st.caption(
        "Engine settings are fixed internally for consistency between Backtest and DCA Today."
    )

    # Fixed calibrated engine defaults. These remain in code but are no longer user-facing.
    risk_model = "Research WF Power Law"
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
    "research_pl_min_weeks": RESEARCH_PL_MIN_WEEKS,
    "research_pl_refit_days": RESEARCH_PL_REFIT_DAYS,
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
        research_fetch_start = min(pd.Timestamp(params["start_date"], tz="UTC") if pd.Timestamp(params["start_date"]).tzinfo is None else pd.Timestamp(params["start_date"]).tz_convert("UTC"), RESEARCH_PL_HISTORY_START)
        df_full = fetch_btc_history(research_fetch_start, params["end_date"])
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

    with st.spinner("Running causal equal-budget Plain DCA vs V5.9 Research Smart DCA..."):
        plain_raw, _ = simulate_dca_backtest(
            df_full, params, DEFAULT_FIXED_DCA_AUD, dca_frequency, "Plain DCA"
        )
        smart_raw, _ = simulate_dca_backtest(
            df_full, params, DEFAULT_FIXED_DCA_AUD, dca_frequency,
            "Risk-Scaled DCA", risk_curve=smart_dca_curve
        )

        capital_target = float(intelligent_dca_budget_aud)
        plain_df, plain_sm = apply_causal_budget_allocator(
            plain_raw, total_budget_aud=capital_target,
            fee_pct=params.get("fee_pct", 0.0)
        )
        smart_df, smart_sm = apply_causal_budget_allocator(
            smart_raw, total_budget_aud=capital_target,
            fee_pct=params.get("fee_pct", 0.0)
        )
        challenger_df, challenger_sm = apply_three_pillar_allocator(
            smart_raw, total_budget_aud=capital_target,
            fee_pct=params.get("fee_pct", 0.0)
        )
        recent_check = validate_smart_dca_recent_period(
            df_full, params, dca_frequency, capital_target, recent_fraction=0.30,
            risk_curve=smart_dca_curve
        )

    if not plain_sm or not smart_sm or not challenger_sm:
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
    challenger_vs_r2 = (
        (challenger_sm["btc_held"] / smart_sm["btc_held"] - 1.0) * 100.0
        if smart_sm["btc_held"] > 0 else np.nan
    )
    challenger_vs_plain = (
        (challenger_sm["btc_held"] / plain_sm["btc_held"] - 1.0) * 100.0
        if plain_sm["btc_held"] > 0 else np.nan
    )
    challenger_events = int((challenger_df.get("bottom_challenger_event", pd.Series(dtype=str)) != "NONE").sum())

    st.header("Simple DCA Backtest")
    st.caption(
        f"Same A${capital_target:,.0f} budget • Monday DCA • "
        f"{dca_backtest_start_date.strftime('%d/%m/%Y')} to "
        f"{dca_backtest_end_date.strftime('%d/%m/%Y')}"
    )

    p1, p2, p3 = st.columns(3)
    with p1:
        st.subheader("Plain DCA")
        st.metric("BTC Accumulated", f"{plain_sm['btc_held']:.6f}")
        st.metric("Average Cost", f"A${plain_sm['avg_cost_aud']:,.0f}")
        st.metric("Ending Value", f"A${plain_sm['btc_value_aud']:,.0f}")
        st.metric("ROI", f"{plain_sm['roi_pct']:+.2f}%")

    with p2:
        st.subheader("Frozen R2")
        st.metric("BTC Accumulated", f"{smart_sm['btc_held']:.6f}", delta=f"{btc_adv:+.2f}% vs Plain")
        st.metric("Average Cost", f"A${smart_sm['avg_cost_aud']:,.0f}")
        st.metric("Ending Value", f"A${smart_sm['btc_value_aud']:,.0f}")
        st.metric("ROI", f"{smart_sm['roi_pct']:+.2f}%")

    with p3:
        st.subheader("Bottom Challenger")
        st.metric("BTC Accumulated", f"{challenger_sm['btc_held']:.6f}", delta=f"{challenger_vs_r2:+.2f}% vs R2")
        st.metric("Average Cost", f"A${challenger_sm['avg_cost_aud']:,.0f}")
        st.metric("Ending Value", f"A${challenger_sm['btc_value_aud']:,.0f}")
        st.metric("Staged Events", f"{challenger_events}")


    st.subheader("Verdict")
    if challenger_vs_r2 > 0:
        st.success(
            f"Bottom Challenger accumulated {challenger_vs_r2:+.2f}% more BTC than frozen R2 "
            f"and {challenger_vs_plain:+.2f}% versus Plain DCA for the same A${capital_target:,.0f} budget."
        )
    elif challenger_vs_r2 < 0:
        st.warning(
            f"Bottom Challenger accumulated {abs(challenger_vs_r2):.2f}% less BTC than frozen R2 in this period. "
            "R2 remains the control; the challenger is not promoted automatically."
        )
    else:
        st.info("Bottom Challenger and frozen R2 accumulated the same BTC in this period.")
    st.caption(
        "Research-only overlay: 3x initial exceptional entry • 4x each new ≥15% lower capitulation stage "
        "while confluence remains exceptional • 3x recent recovery confirmation • no fixed reserve • no all-in."
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
            "date", "price_usd", "risk_score", "continuous_valuation_risk",
            "bottom_challenger_exceptional_zone", "bottom_challenger_category_votes",
            "bottom_challenger_price_position", "bottom_challenger_event",
            "r2_dca_multiplier", "challenger_multiplier_applied",
            "actual_buy_aud", "btc_bought", "btc_held",
            "cumulative_invested_aud", "avg_cost_aud"
        ]
        challenger_detail = challenger_df[[c for c in detail_cols if c in challenger_df.columns]].copy()
        st.dataframe(challenger_detail.tail(250), width="stretch", hide_index=True)

    plain_csv = plain_df.to_csv(index=False).encode("utf-8")
    smart_csv = smart_df.to_csv(index=False).encode("utf-8")
    challenger_csv = challenger_df.to_csv(index=False).encode("utf-8")
    d1, d2, d3 = st.columns(3)
    d1.download_button(
        "Download Plain DCA CSV", plain_csv,
        file_name="btc_v5_1_plain_dca.csv", mime="text/csv"
    )
    d2.download_button(
        "Download Frozen R2 CSV", smart_csv,
        file_name="btc_v5_9_r2_frozen.csv", mime="text/csv"
    )
    d3.download_button(
        "Download Bottom Challenger CSV", challenger_csv,
        file_name="btc_v5_9_r2_bottom_challenger.csv", mime="text/csv"
    )


# ================================================================

# ================================================================
# DCA Today
# ================================================================

elif mode == "DCA Today":
    now_utc = dt.datetime.now(timezone.utc)
    # V5.9 Research Power Law is expanding from the fixed research-history start.
    # This makes today's fit consistent with historical backtests regardless of the
    # selected DCA start date.
    lookback_start = RESEARCH_PL_HISTORY_START.to_pydatetime()

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

    valid_today = risk_today_df.dropna(subset=["risk_score", "price"])
    if valid_today.empty:
        st.error("Today's risk score could not be calculated from the available data.")
        st.stop()

    latest = valid_today.iloc[-1]
    current_risk = float(latest["risk_score"])
    current_display_risk = float(latest.get("continuous_valuation_risk", np.nan))
    current_bottom_zone = float(latest.get("bottom_zone_score", np.nan))
    current_bottom_confidence = float(latest.get("bottom_confidence_score", np.nan))
    current_bottom_label = str(latest.get("bottom_confidence_label", "n/a"))
    current_bull = bool(latest.get("weekly_bull_confirmed", False))
    current_bull_age = float(latest.get("bull_age_weeks", np.nan))
    current_cycle_stage = str(latest.get("cycle_stage", "BEAR / UNCONFIRMED"))
    current_challenger_zone = bool(latest.get("bottom_challenger_exceptional_zone", False))
    current_challenger_votes = int(latest.get("bottom_challenger_category_votes", 0) or 0)
    current_challenger_price_position = float(latest.get("bottom_challenger_price_position", np.nan))
    current_challenger_event = str(latest.get("bottom_challenger_week_event", latest.get("bottom_challenger_event", "NONE")))
    current_challenger_event_mult = float(latest.get("bottom_challenger_week_multiplier", latest.get("bottom_challenger_event_multiplier", np.nan)))
    current_weekly_ma50 = float(latest.get("weekly_ma50", np.nan))
    current_weekly_ma200 = float(latest.get("weekly_ma200", np.nan))

    # V5.9 R2 visibility layer: preserve the bounded 0..1 sizing score, but also
    # expose the underlying Power Law residual so Risk 0 / Risk 1 do not hide
    # how far valuation sits beyond the clamp boundary. This is DISPLAY ONLY.
    current_pl_residual = float(latest.get("power_law_residual", np.nan))
    current_pl_fair_usd = float(latest.get("fair_value", np.nan))
    current_pl_slope = float(latest.get("power_law_slope", np.nan))
    current_pl_intercept = float(latest.get("power_law_intercept", np.nan))
    pl_cheap_threshold = float(params.get("pl_cheap", DEFAULT_PL_CHEAP))
    pl_expensive_threshold = float(params.get("pl_expensive", DEFAULT_PL_EXPENSIVE))
    pl_span = pl_expensive_threshold - pl_cheap_threshold
    unclipped_pl_position = (
        (current_pl_residual - pl_cheap_threshold) / pl_span
        if np.isfinite(current_pl_residual) and pl_span > 0 else np.nan
    )
    price_vs_pl_fair_pct = (
        (10.0 ** current_pl_residual - 1.0) * 100.0
        if np.isfinite(current_pl_residual) else np.nan
    )
    risk0_boundary_ratio = 10.0 ** pl_cheap_threshold
    risk1_boundary_ratio = 10.0 ** pl_expensive_threshold
    if np.isfinite(current_pl_residual) and current_pl_residual <= pl_cheap_threshold:
        boundary_depth_pct = (1.0 - 10.0 ** (current_pl_residual - pl_cheap_threshold)) * 100.0
        boundary_depth_label = "Below Risk-0 boundary"
        boundary_depth_text = f"{boundary_depth_pct:.1f}% deeper"
    elif np.isfinite(current_pl_residual) and current_pl_residual >= pl_expensive_threshold:
        boundary_depth_pct = (10.0 ** (current_pl_residual - pl_expensive_threshold) - 1.0) * 100.0
        boundary_depth_label = "Above Risk-1 boundary"
        boundary_depth_text = f"{boundary_depth_pct:.1f}% higher"
    elif np.isfinite(current_pl_residual):
        boundary_depth_pct = np.nan
        boundary_depth_label = "Clamp status"
        boundary_depth_text = "Inside 0–1 range"
    else:
        boundary_depth_pct = np.nan
        boundary_depth_label = "Clamp status"
        boundary_depth_text = "n/a"

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
    # V5.9 Research: rarity is decision-support context only. Risk Score alone controls sizing.
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
    # Three-pillar research sizing: R2 base + broad causal halving accumulation zone
    # + staged Bottom Challenger events. The +500 marker remains context only.
    current_halving_clock_days = int((pd.Timestamp(now_utc.date()) - pd.Timestamp("2024-04-20")).days)
    current_halving_accumulation_zone = (
        HALVING_ACCUMULATION_START_DAY <= current_halving_clock_days <= HALVING_ACCUMULATION_END_DAY
    )
    halving_timing_weight = (
        max(risk_weight, HALVING_ACCUMULATION_FLOOR_MULT)
        if current_halving_accumulation_zone else risk_weight
    )
    challenger_weight = (
        max(halving_timing_weight, current_challenger_event_mult)
        if np.isfinite(current_challenger_event_mult) else halving_timing_weight
    )
    challenger_recommended_buy = min(
        float(remaining_capital_aud),
        max(0.0, normal_weekly_allowance * challenger_weight),
    )

    # Better-entry probability is informational only in V5.9 Research.
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
    remaining_after = max(float(remaining_capital_aud) - challenger_recommended_buy, 0.0)

    st.header("DCA Today")

    # ------------------------------------------------------------------
    # Decision-first visual dashboard (UI only)
    # ------------------------------------------------------------------
    # This section intentionally uses lightweight HTML/CSS so the live
    # Streamlit app closely matches the approved dashboard mock-up. It does
    # not alter any strategy calculations or state.
    st.markdown(
        """
        <style>
        .v59-wrap {margin-top:.15rem; margin-bottom:.55rem;}
        .v59-hero {
            display:grid; grid-template-columns:1.25fr .78fr 1.22fr;
            gap:0; border:1.5px solid #00e58b; border-radius:15px;
            background:linear-gradient(135deg,#06291f 0%,#071c23 45%,#061922 100%);
            box-shadow:0 0 0 1px rgba(0,229,139,.08), 0 8px 26px rgba(0,0,0,.22);
            overflow:hidden;
        }
        .v59-hero > div {padding:20px 24px; min-height:188px;}
        .v59-hero > div + div {border-left:1px solid rgba(69,216,196,.38);}
        .v59-title {font-size:1.15rem; font-weight:800; margin-bottom:4px; color:#f4f7fb;}
        .v59-big {font-size:3.55rem; line-height:1.03; font-weight:900; color:#23e99a; letter-spacing:-.035em;}
        .v59-mult {font-size:3.25rem; line-height:1.05; font-weight:900; color:#52bfff; letter-spacing:-.035em;}
        .v59-sub {font-size:.92rem; color:#c7d3df; margin-top:8px;}
        .v59-base {font-size:1.35rem; font-weight:800; color:#f5f7fb; margin-top:4px;}
        .v59-buy-pill {display:inline-block; padding:8px 18px; margin-top:14px; border-radius:8px; background:#18e991; color:#062419; font-weight:900; font-size:.88rem;}
        .v59-reason {display:flex; gap:10px; margin:10px 0; align-items:flex-start; color:#f0f4f8;}
        .v59-check,.v59-off {width:24px; height:24px; flex:0 0 24px; border-radius:50%; display:flex; align-items:center; justify-content:center; font-weight:900; margin-top:1px;}
        .v59-check {background:#19e894; color:#052b1e;}
        .v59-off {border:1.5px solid #718397; color:#718397;}
        .v59-reason b {display:block; font-size:.95rem;}
        .v59-reason small {display:block; color:#b8c6d4; margin-top:1px;}
        .v59-q {display:inline-flex; align-items:center; justify-content:center; width:17px; height:17px; border:1px solid #57c8ff; border-radius:50%; color:#57c8ff; font-size:.68rem; font-weight:800; margin-left:5px; vertical-align:2px; cursor:help;}
        .v59-cards {display:grid; grid-template-columns:repeat(5,1fr); gap:10px; margin-top:10px;}
        .v59-card {border:1px solid #29506b; border-radius:11px; padding:13px 15px; background:linear-gradient(180deg,#092337,#081a2b); min-height:110px;}
        .v59-card-title {font-size:.82rem; color:#eaf1f7; font-weight:800;}
        .v59-card-value {font-size:1.45rem; color:#f3f7fb; font-weight:900; margin-top:5px;}
        .v59-card-value.good {color:#24e894;}
        .v59-card-sub {font-size:.80rem; color:#c1ccd8; margin-top:5px; line-height:1.35;}
        .v59-badge {display:inline-block; border-radius:999px; padding:3px 13px; font-size:.78rem; font-weight:900; margin-top:4px;}
        .v59-badge.active {background:#24e894; color:#05281b;}
        .v59-badge.inactive {background:#26384b; color:#dce7ef; border:1px solid #64778a;}
        .v59-pills {display:flex; flex-wrap:wrap; gap:8px; margin:12px 0 10px 0;}
        .v59-pill {padding:8px 22px; border-radius:8px; border:1px solid #294d67; background:#091d2e; color:#dce6ee; font-size:.86rem;}
        .v59-pill.active {background:#129cf3; color:white; border-color:#129cf3; font-weight:800;}
        .v59-info {display:flex; gap:14px; align-items:flex-start; border:1px solid #168fea; border-radius:10px; background:linear-gradient(90deg,#082e50,#07335c); padding:13px 16px; margin-bottom:10px;}
        .v59-info-icon {width:26px; height:26px; flex:0 0 26px; border-radius:50%; background:#4fb9ff; color:#06233a; display:flex; align-items:center; justify-content:center; font-weight:900;}
        .v59-info-title {font-weight:900; color:#eef7ff; margin-bottom:3px;}
        .v59-info-text {font-size:.84rem; color:#d5e4f0; line-height:1.45;}
        .v59-explain-grid {display:grid; grid-template-columns:repeat(4,1fr); gap:10px; margin-bottom:10px;}
        .v59-explain {border:1px solid #264b65; border-radius:10px; padding:13px 14px; background:#091d2e; min-height:170px;}
        .v59-explain h4 {margin:0 0 8px 0; color:#f2f7fb; font-size:.92rem;}
        .v59-explain p {margin:0 0 7px 0; color:#c7d3de; font-size:.80rem; line-height:1.42;}
        .v59-affects,.v59-context {display:inline-block; border-radius:999px; padding:3px 11px; font-size:.72rem; font-weight:900; margin:3px 0 6px 0;}
        .v59-affects {background:#22e894; color:#05291c;}
        .v59-context {background:#26394b; color:#e0e8ef; border:1px solid #5a6e82;}
        @media (max-width:1100px) {
            .v59-hero {grid-template-columns:1fr;}
            .v59-hero > div + div {border-left:0; border-top:1px solid rgba(69,216,196,.30);}
            .v59-cards {grid-template-columns:repeat(2,1fr);}
            .v59-explain-grid {grid-template-columns:repeat(2,1fr);}
        }
        @media (max-width:700px) {
            .v59-cards,.v59-explain-grid {grid-template-columns:1fr;}
            .v59-big {font-size:2.8rem;} .v59-mult {font-size:2.6rem;}
        }
        </style>
        """,
        unsafe_allow_html=True,
    )

    # Human-readable reason lines for the top hero card.
    halving_reason_icon = "✓" if current_halving_accumulation_zone else "○"
    halving_reason_cls = "v59-check" if current_halving_accumulation_zone else "v59-off"
    halving_reason_title = "Halving Accumulation Zone active" if current_halving_accumulation_zone else "Halving Accumulation Zone inactive"
    halving_reason_sub = (
        f"Raises R2 to at least {HALVING_ACCUMULATION_FLOOR_MULT:.2f}×"
        if current_halving_accumulation_zone else "No timing floor applied this week"
    )
    bottom_reason_icon = "✓" if current_challenger_zone else "○"
    bottom_reason_cls = "v59-check" if current_challenger_zone else "v59-off"
    bottom_reason_title = "Exceptional Bottom Zone active" if current_challenger_zone else "Exceptional Bottom Zone: Not active"
    bottom_reason_sub = (
        current_challenger_event if current_challenger_event != "NONE"
        else ("Zone active; no new staged event this week" if current_challenger_zone else "No additional 3× / 4× event this week")
    )
    btc_price_main = "n/a" if not np.isfinite(current_price_aud) else f"A${current_price_aud:,.0f}"
    btc_price_sub = f"US${current_price_usd:,.0f}" if np.isfinite(current_price_usd) else ""
    halving_badge_cls = "active" if current_halving_accumulation_zone else "inactive"
    halving_badge_text = "ACTIVE" if current_halving_accumulation_zone else "INACTIVE"
    bottom_badge_cls = "active" if current_challenger_zone else "inactive"
    bottom_badge_text = "ACTIVE" if current_challenger_zone else "Not Active"

    st.markdown(
        f"""
        <div class="v59-wrap">
          <div class="v59-hero">
            <div>
              <div class="v59-title">🛒 &nbsp; Recommended DCA This Week <span class="v59-q" title="This week's research-challenger buy amount. Base weekly allowance × effective V5.9 multiplier, capped by remaining capital. No automatic all-in.">?</span></div>
              <div class="v59-big">A$ {challenger_recommended_buy:,.0f}</div>
              <span class="v59-buy-pill">₿ &nbsp; BUY THIS WEEK</span>
              <span class="v59-sub" style="margin-left:10px;">That's {challenger_weight:.2f}× your base weekly amount</span>
            </div>
            <div>
              <div class="v59-title">Current Multiplier <span class="v59-q" title="Effective V5.9 multiplier after R2, Halving Accumulation Zone and any staged Exceptional Bottom event.">?</span></div>
              <div class="v59-mult">{challenger_weight:.2f}×</div>
              <div class="v59-sub"><b>Base Monday DCA</b></div>
              <div class="v59-base">A$ {normal_weekly_allowance:,.0f}</div>
            </div>
            <div>
              <div class="v59-title">Reason for This Week's Amount <span class="v59-q" title="Only R2 valuation, the Halving Accumulation Zone and explicit Exceptional Bottom staged events can change this week's V5.9 recommendation.">?</span></div>
              <div class="v59-reason"><span class="{halving_reason_cls}">{halving_reason_icon}</span><div><b>{halving_reason_title}</b><small>{halving_reason_sub}</small></div></div>
              <div class="v59-reason"><span class="v59-check">✓</span><div><b>R2 valuation risk: {risk_label.title()}</b><small>R2 sizing risk {current_risk:.3f} → {risk_weight:.2f}× base multiplier</small></div></div>
              <div class="v59-reason"><span class="{bottom_reason_cls}">{bottom_reason_icon}</span><div><b>{bottom_reason_title}</b><small>{bottom_reason_sub}</small></div></div>
            </div>
          </div>

          <div class="v59-cards">
            <div class="v59-card">
              <div class="v59-card-title">BTC Price <span class="v59-q" title="Live BTC/AUD spot quote when available. R2 valuation uses closed historical data.">?</span></div>
              <div class="v59-card-value">{btc_price_main}</div>
              <div class="v59-card-sub">({btc_price_sub})</div>
            </div>
            <div class="v59-card">
              <div class="v59-card-title">R2 Valuation Risk <span class="v59-q" title="Frozen causal walk-forward Power-Law sizing score. Lower risk means a larger DCA multiplier.">?</span></div>
              <div class="v59-card-value good">{risk_label.title()}</div>
              <div class="v59-card-sub">R2 Multiplier: <b style="color:#24e894">{risk_weight:.2f}×</b></div>
            </div>
            <div class="v59-card">
              <div class="v59-card-title">Halving Accumulation Zone <span class="v59-q" title="Causal timing zone from day +800 to +1000 after the prior halving. While active, ordinary R2 is raised to at least 2.50×.">?</span></div>
              <span class="v59-badge {halving_badge_cls}">{halving_badge_text}</span>
              <div class="v59-card-sub">Day +{current_halving_clock_days} (in +{HALVING_ACCUMULATION_START_DAY}–+{HALVING_ACCUMULATION_END_DAY} range)<br>R2 raised to at least {HALVING_ACCUMULATION_FLOOR_MULT:.2f}×</div>
            </div>
            <div class="v59-card">
              <div class="v59-card-title">Exceptional Bottom Zone <span class="v59-q" title="Independent capitulation/confluence layer. Only a new staged event changes sizing: 3× initial, 4× deeper capitulation, 3× recovery.">?</span></div>
              <span class="v59-badge {bottom_badge_cls}">{bottom_badge_text}</span>
              <div class="v59-card-sub">{current_challenger_votes}/3 confirming categories<br>{'Event: ' + current_challenger_event if current_challenger_event != 'NONE' else 'No 3× / 4× event this week'}</div>
            </div>
            <div class="v59-card">
              <div class="v59-card-title">Remaining Capital <span class="v59-q" title="Portfolio capital still scheduled for deployment. Base allowance = remaining capital ÷ remaining deployment weeks.">?</span></div>
              <div class="v59-card-value">A$ {remaining_capital_aud:,.0f}</div>
              <div class="v59-card-sub">~{weeks_remaining:.0f} weeks remaining<br>until {target_deployment_date.strftime('%d %b %Y')}</div>
            </div>
          </div>

          <div class="v59-pills">
            <span class="v59-pill active">Key Information</span>
            <span class="v59-pill">Valuation (R2)</span>
            <span class="v59-pill">Halving Cycle</span>
            <span class="v59-pill">Exceptional Bottom Zone</span>
            <span class="v59-pill">Opportunity &amp; Context</span>
            <span class="v59-pill">FAQs</span>
          </div>

          <div class="v59-info">
            <span class="v59-info-icon">i</span>
            <div><div class="v59-info-title">How this week's amount is calculated</div>
            <div class="v59-info-text">Monday's DCA amount is your Base Monday DCA multiplied by the current R2 multiplier, with tested adjustments from the Halving Accumulation Zone and Exceptional Bottom Zone. Cycle-based context such as the exact +500-day marker, Opportunity Rarity, Better Entry Evidence, Bull Age and other descriptive indicators do not independently change the buy amount.</div></div>
          </div>

          <div class="v59-explain-grid">
            <div class="v59-explain"><h4>📈 R2 Valuation Risk <span class="v59-q" title="The causal walk-forward Power-Law score is the base sizing engine in V5.9.">?</span></h4><p>Compares BTC with the causal walk-forward Power-Law valuation and determines the base DCA multiplier.</p><span class="v59-affects">Affects buy amount</span><p>Lower risk = larger base multiplier.<br>Higher risk = smaller base multiplier.</p></div>
            <div class="v59-explain"><h4>📅 Halving Accumulation Zone <span class="v59-q" title="Broad research timing zone designed to avoid over-fitting to an exact −500-day date.">?</span></h4><p>Active approximately day +{HALVING_ACCUMULATION_START_DAY}–+{HALVING_ACCUMULATION_END_DAY} after the previous halving. While active, ordinary R2 is raised to at least {HALVING_ACCUMULATION_FLOOR_MULT:.2f}×.</p><span class="v59-affects">Affects buy amount</span><p>Provides a timing boost to ordinary R2 sizing.</p></div>
            <div class="v59-explain"><h4>⚠️ Exceptional Bottom Zone <span class="v59-q" title="Requires deep valuation, low trailing price position and multiple independent stress categories.">?</span></h4><p>Identifies exceptional capitulation using independent categories. A new event can override ordinary sizing with 3× initial, 4× deeper, or 3× recovery.</p><span class="v59-affects">Affects buy amount</span><p>No new staged event = no additional override.</p></div>
            <div class="v59-explain"><h4>📊 Opportunity Rarity <span class="v59-q" title="Cycle-based context. It does not modify DCA sizing in V5.9.">?</span></h4><p>Shows how unusual this week's R2 risk is versus comparable periods in this halving cycle and previous cycles.</p><span class="v59-context">Context only</span><p>Helps interpret the opportunity; does not change this week's amount.</p></div>
          </div>
          <div class="v59-explain-grid" style="grid-template-columns:repeat(3,1fr);">
            <div class="v59-explain" style="min-height:130px"><h4>🗓️ Halving Cycle ±500 Day Markers <span class="v59-q" title="Original 500/500 theory dates remain visible as a reference, but do not automatically buy or sell.">?</span></h4><p>Shows the theoretical −500-day BUY and +500-day SELL dates based on the next estimated halving.</p><span class="v59-context">Context only</span><p>Informational only. No automatic buy or sell.</p></div>
            <div class="v59-explain" style="min-height:130px"><h4>📊 Historical Weekly Risk Distribution <span class="v59-q" title="Descriptive historical context, not cycle-adjusted sizing.">?</span></h4><p>Shows how this week's R2 risk compares with historical weeks.</p><span class="v59-context">Context only</span><p>Does not change the buy amount.</p></div>
            <div class="v59-explain" style="min-height:130px"><h4>ℹ️ Other Indicators <span class="v59-q" title="MVRV, Mayer, RSI, trend and Bull Age are shown for context and research visibility.">?</span></h4><p>MVRV, Mayer, RSI, weekly trend and Bull Age provide additional context.</p><span class="v59-context">Context only</span><p>Do not independently change the V5.9 buy amount.</p></div>
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    a, b, c, d = st.columns(4)
    a.metric(
        "BTC Valuation Risk",
        format_continuous_risk(current_display_risk, current_price_usd),
        risk_label,
        help=(
            "Continuous display risk. 0.000 is reserved for a BTC price of zero. "
            f"The frozen R2 sizing score is {current_risk:.3f} and still controls the DCA multiplier."
        ),
    )
    b.metric(
        "BTC Price",
        "n/a" if not np.isfinite(current_price_aud) else f"A${current_price_aud:,.0f}",
        help="Live BTC/AUD spot quote (60-second cache) when available; otherwise latest historical BTC/AUD. Risk uses closed historical data."
    )
    c.metric(
        "Opportunity Rarity", rarity["rarity_label"],
        help="Cycle-based context showing how unusual this week's R2 risk is versus comparable periods in the current and previous two halving cycles. Context only: it does NOT change this week's buy amount."
    )
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

    st.subheader("Cycle / Bottom Intelligence — Research Context")
    q1, q2, q3, q4 = st.columns(4)
    q1.metric(
        "Exceptional Bottom Zone",
        "ACTIVE" if current_challenger_zone else "INACTIVE",
        current_challenger_event if current_challenger_event != "NONE" else f"{current_challenger_votes}/3 confirming categories",
        help=(
            "Research challenger. Requires deep causal Power-Law valuation, BTC in the lowest 20% of its trailing "
            "52-week range, and at least two additional strongly-stressed categories."
        ),
    )
    q2.metric(
        "Weekly Trend",
        "BULL CONFIRMED" if current_bull else "UNCONFIRMED / BEAR",
        help=(
            "Research proxy for your weekly yellow/bull transition: 3 consecutive weekly closes above "
            "the causal 50-week moving average. A 3-week break below resets the bull state."
        ),
    )
    q3.metric(
        "Bull Age",
        "n/a" if not np.isfinite(current_bull_age) else f"{int(current_bull_age)} weeks",
        help="Weeks since the current weekly bull confirmation. Research context only; no DCA adjustment.",
    )
    q4.metric(
        "Cycle Stage",
        current_cycle_stage,
        help="Display classification from bull age. It is not hard-coded into the R2 sizing curve.",
    )

    ma50_text = "n/a" if not np.isfinite(current_weekly_ma50) else f"US${current_weekly_ma50:,.0f}"
    ma200_text = "n/a" if not np.isfinite(current_weekly_ma200) else f"US${current_weekly_ma200:,.0f}"
    zone_text = "n/a" if not np.isfinite(current_bottom_zone) else f"{current_bottom_zone:.0f}/100"
    st.caption(
        f"Current bottom-zone evidence: {zone_text} • 50-week MA: {ma50_text} • 200-week MA: {ma200_text}. "
        "Exceptional Bottom Zone is a causal research signal, not a guarantee that the exact cycle low is in."
    )

    st.info(
        f"Frozen R2: Risk {current_risk:.3f} → {risk_weight:.2f}×. "
        f"Three-Pillar Challenger today: {challenger_weight:.2f}×"
        + (f" ({current_challenger_event})" if current_challenger_event != "NONE" else " (no staged event this week)")
        + ". Production V5.8.2 and the R2 control are unchanged."
    )

    with st.expander("📅 Halving Cycle — key dates & ±500-day theory", expanded=False):
        current_halving = pd.Timestamp("2024-04-20")
        current_day = pd.Timestamp(now_utc.date())
        days_from_halving = int((current_day - current_halving).days)
        pre500 = current_halving - pd.Timedelta(days=500)
        post500 = current_halving + pd.Timedelta(days=500)
        zone_start_date = current_halving + pd.Timedelta(days=HALVING_ACCUMULATION_START_DAY)
        zone_end_date = current_halving + pd.Timedelta(days=HALVING_ACCUMULATION_END_DAY)

        st.caption(
            f"Research Halving Accumulation Zone: {zone_start_date.strftime('%d %b %Y')} to {zone_end_date.strftime('%d %b %Y')} "
            f"(day +{HALVING_ACCUMULATION_START_DAY} to +{HALVING_ACCUMULATION_END_DAY}); "
            f"currently {'ACTIVE' if current_halving_accumulation_zone else 'INACTIVE'}. "
            "The exact −500/+500 dates remain visible in the table below as the original theory reference. "
            "+500 is informational only and never triggers an automatic sale."
        )

        # Future-cycle planning markers. Bitcoin halvings occur at block-height milestones,
        # not fixed calendar dates, so these dates are intentionally approximate and should
        # be refreshed as the network approaches block 1,050,000.
        next_halving_est = pd.Timestamp("2028-04-13")
        next_pre500 = next_halving_est - pd.Timedelta(days=500)
        next_post500 = next_halving_est + pd.Timedelta(days=500)
        st.markdown("**Next halving cycle — approximate planning dates**")
        n1, n2, n3 = st.columns(3)
        n1.metric("Approx. −500 Accumulation Start", next_pre500.strftime("%d %b %Y"))
        n2.metric("Approx. 2028 Halving", next_halving_est.strftime("%d %b %Y"))
        n3.metric("Approx. +500 Marker", next_post500.strftime("%d %b %Y"))
        st.caption(
            "The next Bitcoin halving is currently estimated for roughly early-to-mid April 2028. "
            "The app uses 13 April 2028 as a planning estimate, giving approximate ±500-day markers. "
            "The actual halving date will move with block production speed."
        )

        st.markdown(
            "**Theory:** accumulate from about 500 days before a Bitcoin halving, hold through the halving, "
            "consider the period around 500 days after the halving as a historical take-profit zone, then wait "
            "for the next accumulation window. This panel is research context only and does not change R2 or "
            "trigger an automatic sale."
        )

        # Empirical timing check using only BTC prices available in the app. A broad ±900-day
        # window is used to locate the preceding bear-market low and the following cycle high.
        px_hist = df_today[["price"]].copy()
        px_hist.index = pd.to_datetime(px_hist.index).tz_localize(None) if getattr(pd.to_datetime(px_hist.index), "tz", None) is not None else pd.to_datetime(px_hist.index)
        px_hist["price"] = pd.to_numeric(px_hist["price"], errors="coerce")
        px_hist = px_hist.dropna(subset=["price"])
        cycle_rows = []
        for halving_date in [pd.Timestamp("2016-07-09"), pd.Timestamp("2020-05-11"), pd.Timestamp("2024-04-20")]:
            before = px_hist[(px_hist.index >= halving_date - pd.Timedelta(days=900)) & (px_hist.index <= halving_date)]
            after_end = min(halving_date + pd.Timedelta(days=900), current_day)
            after = px_hist[(px_hist.index >= halving_date) & (px_hist.index <= after_end)]
            if before.empty or after.empty:
                continue
            low_date = before["price"].idxmin()
            high_date = after["price"].idxmax()
            cycle_rows.append({
                "Halving": halving_date.strftime("%d %b %Y"),
                "Theory BUY (−500d)": (halving_date - pd.Timedelta(days=500)).strftime("%d %b %Y"),
                "Theory SELL (+500d)": (halving_date + pd.Timedelta(days=500)).strftime("%d %b %Y"),
                "Actual prior low": low_date.strftime("%d %b %Y"),
                "Low vs halving": f"{int((low_date-halving_date).days):+d} d",
                "Actual post-halving high": high_date.strftime("%d %b %Y"),
                "High vs halving": f"{int((high_date-halving_date).days):+d} d",
                "Status": "cycle-to-date" if halving_date.year == 2024 else "historical",
            })
        if cycle_rows:
            cycle_table = pd.DataFrame(cycle_rows)
            future_row = pd.DataFrame([{
                "Halving": "≈ " + next_halving_est.strftime("%d %b %Y"),
                "Theory BUY (−500d)": "≈ " + next_pre500.strftime("%d %b %Y"),
                "Theory SELL (+500d)": "≈ " + next_post500.strftime("%d %b %Y"),
                "Actual prior low": "future / unknown",
                "Low vs halving": "—",
                "Actual post-halving high": "future / unknown",
                "High vs halving": "—",
                "Status": "future estimate",
            }])
            cycle_table = pd.concat([cycle_table, future_row], ignore_index=True)
            st.dataframe(cycle_table, width="stretch", hide_index=True)
            st.caption(
                "Theory BUY and SELL dates are the simple −500/+500-day rule; they are shown explicitly for each cycle. "
                "The 2024 row is cycle-to-date and can change. The 2028 BUY/Halving/SELL dates are approximate planning dates; "
                "the actual halving occurs at a block-height milestone. "
                "Historical low/high searches use a broad ±900-day window so we can test whether the simple ±500-day "
                "idea roughly aligns with actual macro turning points rather than assuming it does."
            )

        st.warning(
            "Bitcoin has only a small number of independent halving cycles. Spot ETFs, institutional flows, "
            "market maturation and diminishing percentage returns may shift or weaken historical cycle timing. "
            "Do not treat ±500 days as a guaranteed bottom or top."
        )

    st.subheader("Power Law Risk Visibility")
    v1, v2, v3, v4 = st.columns(4)
    v1.metric(
        "R2 Sizing Risk",
        f"{current_risk:.3f}",
        help="Frozen bounded 0–1 R2 score used for DCA sizing. This may clamp at 0 or 1; the continuous valuation risk above does not.",
    )
    v2.metric(
        "Unclipped PL Position",
        "n/a" if not np.isfinite(unclipped_pl_position) else f"{unclipped_pl_position:.3f}",
        help=(
            "Same Power Law position before clamping. 0.000 is the Risk-0 boundary, "
            "1.000 is the Risk-1 boundary; negative values show how far below Risk 0 BTC sits."
        ),
    )
    v3.metric(
        "Price vs PL Fair Value",
        "n/a" if not np.isfinite(price_vs_pl_fair_pct) else f"{price_vs_pl_fair_pct:+.1f}%",
        help="Closed-data BTC price relative to the causal walk-forward Power Law fair value.",
    )
    v4.metric(
        boundary_depth_label,
        boundary_depth_text,
        help="Shows depth beyond a clamp boundary without increasing the DCA multiplier beyond its fixed cap.",
    )

    fair_text = "n/a" if not np.isfinite(current_pl_fair_usd) else f"US${current_pl_fair_usd:,.0f}"
    st.caption(
        f"Walk-forward PL fair value: {fair_text}. Risk 0 begins at about "
        f"{risk0_boundary_ratio * 100:.1f}% of fair value; Risk 1 begins at about "
        f"{risk1_boundary_ratio * 100:.1f}% of fair value. The R2 strategy is unchanged: "
        f"maximum DCA weight remains {interpolate(smart_dca_curve, 0.0):.2f}×."
    )

    if np.isfinite(current_pl_residual):
        view_min = min(-0.50, current_pl_residual - 0.08)
        view_max = max(0.50, current_pl_residual + 0.08)
        pl_fig = go.Figure()
        pl_fig.add_scatter(
            x=[current_pl_residual], y=["Current"], mode="markers+text",
            text=[f"Residual {current_pl_residual:+.3f}"], textposition="top center",
            marker={"size": 14},
            hovertemplate=(
                f"Current residual: {current_pl_residual:+.4f}<br>"
                f"Unclipped position: {unclipped_pl_position:+.3f}<br>"
                f"Price vs fair value: {price_vs_pl_fair_pct:+.1f}%<extra></extra>"
            ),
        )
        pl_fig.add_vline(x=pl_cheap_threshold, line_dash="dash", annotation_text="Risk 0 boundary")
        pl_fig.add_vline(x=0.0, line_dash="dot", annotation_text="PL fair value")
        pl_fig.add_vline(x=pl_expensive_threshold, line_dash="dash", annotation_text="Risk 1 boundary")
        pl_fig.update_layout(
            xaxis_title="Power Law residual (log10 price ÷ fair value)",
            yaxis_title="",
            yaxis={"showticklabels": False},
            xaxis={"range": [view_min, view_max]},
            height=230,
            margin=dict(l=20, r=20, t=45, b=45),
            showlegend=False,
        )
        st.plotly_chart(pl_fig, width="stretch")
        st.caption(
            "This chart is visibility only. A displayed Risk of 0 can represent anything below the left boundary; "
            "the marker and unclipped position show how deep into that zone BTC actually is."
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
            "**Continuous Valuation Risk = visibility.** It is a smooth Power-Law-relative display score; "
            "0.000 is reserved for a zero BTC price. It does not replace the frozen R2 sizing score.\n\n"
            "**Exceptional Bottom Zone = challenger trigger.** Deep Power-Law valuation and a low trailing-year price "
            "position are mandatory; at least two independent confirming categories must also be strongly stressed.\n\n"
            "**Staged deployment = 3x / 4x / 3x.** Initial exceptional entry uses 3x, each new ≥15% lower "
            "capitulation stage while confluence remains exceptional uses 4x, and a recent recovery confirmation uses 3x.\n\n"
            "**Bull Age / Cycle Stage = context.** They describe how long the current confirmed weekly bull trend "
            "has been active and do not alter sizing.\n\n"
            "**Halving Accumulation Zone = sizing input.** This is the broad causal day +800 to +1000 research window. "
            "While active, it raises ordinary R2 sizing to at least 2.50x. The exact −500/+500 dates remain context markers and do not themselves trigger a trade.\n\n"
            "Opportunity Rarity and Better Entry Evidence remain informational only. Bull Age remains context only. "
            "The Halving Accumulation Zone and explicit Bottom Challenger staged events are the only research overlays that can raise the purchase above frozen R2."
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
            "V5.9 R2 uses Opportunity Rarity for context only. It does not increase or reduce the recommended buy."
        )

    st.subheader("R2 Control vs Three-Pillar Challenger — audit view")
    y1, y2 = st.columns(2)
    y1.metric("Frozen R2 Buy", f"A${recommended_buy:,.0f}", help=f"{risk_weight:.2f}× normal weekly allowance")
    y2.metric(
        "Three-Pillar Buy", f"A${challenger_recommended_buy:,.0f}",
        delta=(f"A${challenger_recommended_buy-recommended_buy:+,.0f} vs R2" if challenger_recommended_buy != recommended_buy else "same as R2"),
        help=f"{challenger_weight:.2f}× normal weekly allowance; R2 + causal halving zone + staged bottom events"
    )

    x1, x2, x3 = st.columns(3)
    x1.metric("Normal Monday DCA", f"A${normal_weekly_allowance:,.0f}")
    x2.metric("Capital Remaining After Challenger Buy", f"A${remaining_after:,.0f}")
    x3.metric("Already Deployed", f"A${deployed:,.0f}")

    pos_text = "n/a" if not np.isfinite(current_challenger_price_position) else f"{current_challenger_price_position*100:.1f}%"
    st.caption(
        f"Halving Accumulation Zone: {'ACTIVE' if current_halving_accumulation_zone else 'inactive'} • "
        f"day +{current_halving_clock_days} since 20 Apr 2024 • research floor "
        f"{HALVING_ACCUMULATION_FLOOR_MULT:.2f}× when day +{HALVING_ACCUMULATION_START_DAY} to +{HALVING_ACCUMULATION_END_DAY}. "
        "The exact ±500 rule remains visible below as historical context; +500 does not trigger an automatic sale."
    )
    st.caption(
        f"Bottom Challenger: {'EXCEPTIONAL ZONE ACTIVE' if current_challenger_zone else 'no exceptional zone'} • "
        f"confirming categories {current_challenger_votes}/3 • trailing-year price position {pos_text}. "
        "No fixed reserve and no automatic all-in."
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

    saved_portfolio = shared_portfolio if isinstance(shared_portfolio, dict) else {}
    saved_rows = saved_portfolio.get("rows", [])

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

