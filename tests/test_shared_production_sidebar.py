"""Guard the frozen research sidebar copy and Production isolation."""
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
LAUNCHER = (ROOT / "app.py").read_text(encoding="utf-8")
PRODUCTION = (ROOT / "engines" / "production" / "production_app.py").read_text(encoding="utf-8")
SNAPSHOT = (ROOT / "engines" / "shared" / "production_sidebar_snapshot.py").read_text(encoding="utf-8")
BOUNDARY = "# BTC_SHARED_PRODUCTION_SIDEBAR_END"


def test_research_pages_load_a_standalone_frozen_sidebar_copy():
    assert 'if section != "Production":' in LAUNCHER
    assert 'engines" / "shared" / "production_sidebar_snapshot.py' in LAUNCHER
    assert 'sidebar_path.read_text(encoding="utf-8")' in LAUNCHER
    assert '"BTC_SIDEBAR_ONLY": True' in LAUNCHER
    assert "production_source.read_text" not in LAUNCHER


def test_frozen_sidebar_is_an_exact_snapshot_of_the_production_sidebar():
    assert BOUNDARY in PRODUCTION
    assert SNAPSHOT == PRODUCTION.split(BOUNDARY, 1)[0]


def test_snapshot_stops_before_production_market_data_and_model_calculations():
    assert "_fetch_market_inputs(" not in SNAPSHOT
    assert "fetch_btc_history(" not in SNAPSHOT
    assert "params =" not in SNAPSHOT
    assert "if globals().get(\"BTC_SIDEBAR_ONLY\", False):" in SNAPSHOT


def test_snapshot_skips_portfolio_recovery_and_durable_storage_reads():
    sidebar_mode = SNAPSHOT.split('if globals().get("BTC_SIDEBAR_ONLY", False):', 1)[1]
    sidebar_mode = sidebar_mode.split("else:", 1)[0]
    assert "_load_portfolio_snapshots(" not in sidebar_mode
    assert "_load_shared_portfolio(" not in sidebar_mode
    assert "load_portfolio()" not in sidebar_mode
    assert 'portfolio_storage_error = "Portfolio loading is intentionally skipped in sidebar-only mode."' in sidebar_mode


def test_full_production_path_retains_portfolio_verification():
    assert "server_portfolio, portfolio_storage_error = load_portfolio()" in PRODUCTION
    assert "snapshot_as_portfolio_positions(_broker_snapshot)" in PRODUCTION
    assert "portfolio_positions(server_portfolio)" in PRODUCTION
