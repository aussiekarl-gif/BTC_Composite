"""Ensure Bottom Signal Timeline builds detailed plots only when requested."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE = (ROOT / "engines" / "audit" / "bottom_signal_timeline_app.py").read_text(encoding="utf-8")


def test_timeline_indicator_histories_are_lazy():
    selector = 'timeline_detail_view = st.radio('
    assert selector in SOURCE
    assert '["Overview", "Individual indicator histories"]' in SOURCE
    branch = SOURCE.split('if timeline_detail_view == "Individual indicator histories":', 1)[1]
    assert 'for chart_index, label in enumerate(indicator_rows):' in branch
    assert 'st.plotly_chart(' in branch


def test_overview_still_shows_heatmap_and_selected_week_values():
    assert "st.plotly_chart(heat, use_container_width=True)" in SOURCE
    assert 'st.subheader("Indicator values — selected week")' in SOURCE
    assert 'st.dataframe(detail, use_container_width=True, hide_index=True)' in SOURCE


def test_causal_timeline_classification_is_cached():
    assert '@st.cache_data(ttl=900, show_spinner=False)\ndef build_timeline(master):' in SOURCE
    assert "pct = _expanding_percentile(series, min_periods=52)" in SOURCE
    assert 'states["Bottom Consensus"] = consensus' in SOURCE
