from engines.research.v60_path_cost_sensitivity import (
    run_execution_cost_sensitivity,
    run_path_comparison,
)


def test_path_comparison_covers_delayed_bottom_severity_and_fast_recovery():
    rows = run_path_comparison()
    names = {row["scenario"] for row in rows}
    assert names == {
        "delayed_bottom_extra_30pct",
        "delayed_bottom_extra_40pct",
        "delayed_bottom_extra_50pct",
        "rapid_v_recovery",
    }
    assert all(row["research_only"] for row in rows)
    assert all(row["fixed_btc"] > 0 and row["dynamic_btc"] > 0 for row in rows)


def test_execution_cost_grid_is_complete_and_keeps_outputs_finite():
    rows = run_execution_cost_sensitivity()
    assert len(rows) == 18
    assert {row["buy_friction_pct"] for row in rows} == {0.3, 0.6, 1.0}
    assert {row["fixed_fee_aud"] for row in rows} == {3.0, 5.0}
    assert {row["annual_btc_drag_pct"] for row in rows} == {0.25, 0.5, 1.0}
    assert all(row["dynamic_btc"] > 0 and row["fixed_btc"] > 0 for row in rows)
    assert all(row["research_only"] for row in rows)
