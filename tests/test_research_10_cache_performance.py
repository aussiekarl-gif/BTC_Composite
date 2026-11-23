"""Regression checks for Research 10.0 rerun performance caches."""
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SOURCE = (ROOT / "engines" / "research" / "cowen_onchain_risk_app.py").read_text(encoding="utf-8")


def test_raw_research_candidates_are_cached_for_interactive_reruns():
    assert '@st.cache_data(ttl=900, show_spinner=False)' in SOURCE
    assert "def cached_raw_candidates(data_dir):" in SOURCE
    assert "raw = cached_raw_candidates(str(DATA_DIR))" in SOURCE


def test_expensive_prior_only_risk_ranks_are_cached_separately():
    assert "def cached_prior_risk_frame(series_map):" in SOURCE
    assert "cached_prior_risk_frame(series_map)" in SOURCE
    assert "window_observations=1825, min_prior_observations=365" in SOURCE
    assert "higher_is_riskier=True" in SOURCE


def test_risk_cache_does_not_change_missing_data_or_composite_policy():
    assert "if series_map" in SOURCE
    assert "else pd.DataFrame(index=raw.index)" in SOURCE
    assert 'result["composite_risk"] = (weighted / float(weight_series.sum())).where(complete)' in (
        (ROOT / "engines" / "research" / "cowen_onchain_risk.py").read_text(encoding="utf-8")
    )
