"""The launcher reuses the real Production sidebar without running Production."""
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
LAUNCHER = (ROOT / "app.py").read_text(encoding="utf-8")
PRODUCTION = (ROOT / "engines" / "production" / "production_app.py").read_text(encoding="utf-8")


def test_research_pages_execute_production_sidebar_prefix_only():
    assert 'if section != "Production":' in LAUNCHER
    assert 'sidebar_end = "# BTC_SHARED_PRODUCTION_SIDEBAR_END"' in LAUNCHER
    assert 'sidebar_source = production_source.split(sidebar_end, 1)[0]' in LAUNCHER
    assert '"BTC_SIDEBAR_ONLY": True' in LAUNCHER


def test_production_sidebar_only_mode_skips_page_config_and_main_title():
    assert 'if not globals().get("BTC_SIDEBAR_ONLY", False):' in PRODUCTION
    assert "# BTC_SHARED_PRODUCTION_SIDEBAR_END" in PRODUCTION
    assert PRODUCTION.index("# BTC_SHARED_PRODUCTION_SIDEBAR_END") < PRODUCTION.index("# Dates / Parameters")
    assert 'st.title("Bitcoin Dynamic DCA V5.8.2 FULL — Smart DCA")' in PRODUCTION


def test_sidebar_only_execution_stops_before_market_data_and_model_calculations():
    sidebar = PRODUCTION.split("# BTC_SHARED_PRODUCTION_SIDEBAR_END", 1)[0]
    assert "_fetch_market_inputs(" not in sidebar
    assert "fetch_btc_history(" not in sidebar
    assert "params =" not in sidebar
