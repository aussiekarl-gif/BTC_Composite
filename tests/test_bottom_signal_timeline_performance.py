"""Keep Bottom Signal Timeline optional provider fetches parallel and failure-tolerant."""
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SOURCE = (ROOT / "engines" / "audit" / "bottom_signal_timeline_app.py").read_text(encoding="utf-8")


def test_optional_timeline_sources_are_fetched_concurrently():
    assert "ThreadPoolExecutor(" in SOURCE
    assert "pool.map(_load_optional_digitized, digitized_artifacts)" in SOURCE
    assert "max_workers=len(digitized_artifacts)" in SOURCE


def test_optional_timeline_source_failures_do_not_abort_the_master_dataset():
    assert "return chart_col, None" in SOURCE
    assert "if chart_values is not None:" in SOURCE
    assert "@st.cache_data(ttl=900, show_spinner=False)" in SOURCE
