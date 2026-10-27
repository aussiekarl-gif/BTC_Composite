"""Fixed selling-threshold diagnostics on the SAME untouched fold windows.

This is a sensitivity matrix, NOT a second parameter selection pass.
Never choose an allegedly optimal threshold using these holdout outcomes.
"""
import pandas as pd

from engines.research.sell_threshold_robustness import COSTS, SELL_THRESHOLDS
from engines.research.sell_threshold_walkforward import (
    _simulate, expanding_walk_forward,
)


def fixed_threshold_matrix(
    data, starting_capital_aud=500_000,
    initial_train_fraction=0.5, holdout_fraction=0.1,
):
    report = expanding_walk_forward(
        data, starting_capital_aud=starting_capital_aud,
        initial_train_fraction=initial_train_fraction,
        holdout_fraction=holdout_fraction,
    )
    source = data.copy().sort_index()
    # The 0.3% rows define the non-overlapping chronological test windows.
    windows = [row for row in report["folds"]
               if row["cost_per_side"] == 0.003]
    records = []
    for fold in windows:
        test_start = pd.Timestamp(fold["test_start"])
        test_end = pd.Timestamp(fold["test_end"])
        location = source.index.get_loc(test_start)
        if not isinstance(location, (int,)):
            raise ValueError("Expected unique test_start in ordered index")
        if location < 1:
            raise ValueError("Missing previous observation for test signal")
        test = source.loc[test_start:test_end]
        window = pd.concat([source.iloc[[location - 1]], test])
        for fee in COSTS:
            baseline = _simulate(window, starting_capital_aud, 0.75, fee)
            for threshold in SELL_THRESHOLDS:
                candidate = _simulate(window, starting_capital_aud, threshold, fee)
                records.append({
                    "fold": fold["fold"],
                    "test_start": fold["test_start"],
                    "test_end": fold["test_end"],
                    "sell_threshold": threshold,
                    "cost_per_side": fee,
                    "ending_equity_aud": candidate["ending_equity_aud"],
                    "baseline_equity_aud": baseline["ending_equity_aud"],
                    "edge_vs_baseline_aud": candidate["ending_equity_aud"]
                                            - baseline["ending_equity_aud"],
                    "btc_held": candidate["btc_held"],
                    "cash_aud": candidate["cash_remaining_aud"],
                    "sell_count": candidate["sell_count"],
                })
    rows = pd.DataFrame(records)
    aggregate = []
    for (cost, threshold), group in rows.groupby(
        ["cost_per_side", "sell_threshold"], sort=True
    ):
        edge = group["edge_vs_baseline_aud"]
        aggregate.append({
            "cost_per_side": float(cost),
            "sell_threshold": float(threshold),
            "folds": len(group),
            "wins_vs_baseline": int((edge > 0).sum()),
            "losses_vs_baseline": int((edge < 0).sum()),
            "ties_vs_baseline": int((edge == 0).sum()),
            "mean_edge_vs_baseline_aud": float(edge.mean()),
            "median_edge_vs_baseline_aud": float(edge.median()),
            "worst_edge_vs_baseline_aud": float(edge.min()),
            "best_edge_vs_baseline_aud": float(edge.max()),
        })
    return {"results": records, "summary": aggregate,
            "warning": "Comparisons are holdout diagnostics, not permissible parameter-selection feedback."}
