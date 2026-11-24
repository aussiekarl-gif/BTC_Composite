"""Guard the lightweight static research sidebar and Production isolation."""
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
LAUNCHER = (ROOT / "app.py").read_text(encoding="utf-8")
PRODUCTION = (ROOT / "engines" / "production" / "production_app.py").read_text(encoding="utf-8")
SNAPSHOT = (ROOT / "engines" / "shared" / "production_sidebar_snapshot.py").read_text(encoding="utf-8")
STATIC = (ROOT / "engines" / "shared" / "static_production_sidebar.py").read_text(encoding="utf-8")
BOUNDARY = "# BTC_SHARED_PRODUCTION_SIDEBAR_END"


def test_production_mode_keeps_the_frozen_full_sidebar_snapshot():
    assert 'if section == "Production":' in LAUNCHER
    assert 'production_sidebar_snapshot.py' in LAUNCHER
    assert '"BTC_SIDEBAR_ONLY": False' in LAUNCHER


def test_research_modes_use_only_the_lightweight_static_sidebar():
    assert 'from engines.shared.static_production_sidebar import render_static_production_sidebar' in LAUNCHER
    assert 'render_static_production_sidebar(st)' in LAUNCHER
    assert 'if section == "Production":' in LAUNCHER
    research_branch = LAUNCHER.split("else:", 1)[1].split("# Production snapshot renders", 1)[0]
    assert "production_sidebar_snapshot.py" not in research_branch
    assert "production_model" not in research_branch


def test_static_sidebar_has_no_production_or_data_dependencies_or_widgets():
    assert "production_model" not in STATIC
    assert "portfolio_store" not in STATIC
    assert "fetch_" not in STATIC
    assert "st.radio" not in STATIC
    assert "st.selectbox" not in STATIC
    assert "st.number_input" not in STATIC
    assert "st.date_input" not in STATIC
    assert "st.button" not in STATIC
    assert "with st.sidebar:" in STATIC
    assert "unsafe_allow_html=True" in STATIC
    assert "Static reference panel on research pages" in STATIC


def test_frozen_sidebar_snapshot_remains_an_exact_copy_of_production_sidebar():
    assert BOUNDARY in PRODUCTION
    assert SNAPSHOT == PRODUCTION.split(BOUNDARY, 1)[0]


def test_snapshot_stops_before_production_market_data_and_model_calculations():
    assert "_fetch_market_inputs(" not in SNAPSHOT
    assert "fetch_btc_history(" not in SNAPSHOT
    assert "params =" not in SNAPSHOT


def test_production_portfolio_verification_path_is_unchanged():
    assert "server_portfolio, portfolio_storage_error = load_portfolio()" in PRODUCTION
    assert "snapshot_as_portfolio_positions(_broker_snapshot)" in PRODUCTION
    assert "portfolio_positions(server_portfolio)" in PRODUCTION
