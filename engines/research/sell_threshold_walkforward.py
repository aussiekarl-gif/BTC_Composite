"""Read-only expanding walk-forward sensitivity analysis for sell thresholds.

Every fold trains on past rows and tests a disjoint future segment with a
fresh, identical AUD cash balance. No tuning on the holdout segment. Uses the
existing cycle engine with previous-observation signal execution.
"""
import numpy as np
import pandas as pd

from engines.research.cycle_backtest import (
    simulate_buy_and_hold_benchmark,
    simulate_next_observation_strategy,
)
from engines.research.sell_threshold_robustness import COSTS, SELL_THRESHOLDS


def fixed_dca_benchmark(data, starting_capital_aud=500_000, fee_pct=0.001):
    """Equal gross AUD purchases at every holdout observation; no future signals."""
    prices = pd.to_numeric(data["btc_price_aud"], errors="coerce").to_numpy()
    if len(prices) == 0 or not np.isfinite(prices).all() or (prices <= 0).any():
        raise ValueError("Need valid, nonempty holdout BTC price observations")
    if not (0 <= fee_pct < 1) or starting_capital_aud <= 0:
        raise ValueError("Invalid fee or starting capital")
    amount = starting_capital_aud / len(prices)
    btc = float(np.sum((amount * (1 - fee_pct)) / prices))
    return {"ending_equity_aud": btc * float(prices[-1]), "btc_held": btc,
            "fees_aud": starting_capital_aud * fee_pct}


def _simulate(data, capital, threshold, fee):
    return simulate_next_observation_strategy(
        data, starting_capital_aud=capital, buy_threshold=0.25,
        sell_threshold=threshold, max_buy_pct_period=0.05,
        max_sell_pct_period=0.20, fee_pct=fee, min_trade_aud=100,
    )[1]


def expanding_walk_forward(
    data, starting_capital_aud=500_000, initial_train_fraction=0.5,
    holdout_fraction=0.1, min_test_rows=10,
):
    """Produce rolling disjoint out-of-sample outcomes and grouped diagnostics.

    Thresholds are selected using 0.3% all-in training cost and trained
    on the entire prefix of each fold. Period results are *not* a continuous
    compounded portfolio: capital resets at each disjoint test window.
    """
    if not isinstance(data, pd.DataFrame) or not {
        "btc_price_aud", "risk_score"
    }.issubset(data.columns):
        raise ValueError("Data must contain btc_price_aud and risk_score")
    if not (0.4 <= initial_train_fraction <= 0.8):
        raise ValueError("initial_train_fraction must be in [0.4, 0.8]")
    if not (0.05 <= holdout_fraction <= 0.25):
        raise ValueError("holdout_fraction must be in [0.05, 0.25]")
    if not np.isfinite(starting_capital_aud) or starting_capital_aud <= 0:
        raise ValueError("starting_capital_aud must be positive")
    clean = data.copy().sort_index()
    if clean.index.has_duplicates:
        raise ValueError("Duplicate timestamps")
    for col in ("btc_price_aud", "risk_score"):
        clean[col] = pd.to_numeric(clean[col], errors="coerce")
    if (not np.isfinite(clean["btc_price_aud"]).all()
            or not (clean["btc_price_aud"] > 0).all()
            or not np.isfinite(clean["risk_score"]).all()
            or not clean["risk_score"].between(0, 1).all()):
        raise ValueError("Invalid prices or risk signals; investigate provenance")
    n = len(clean)
    first_test = int(n * initial_train_fraction)
    step = max(min_test_rows, int(n * holdout_fraction))
    if first_test < 20 or n - first_test < min_test_rows:
        raise ValueError("Not enough observations for out-of-sample folds")
    results = []
    for start in range(first_test, n, step):
        stop = min(start + step, n)
        if stop - start < min_test_rows:
            break
        train = clean.iloc[:start]
        test = clean.iloc[start:stop]
        selection_fee = 0.003
        scores = [(t, _simulate(train, starting_capital_aud, t, selection_fee)
                   ["ending_equity_aud"]) for t in SELL_THRESHOLDS]
        selected = max(scores, key=lambda item: (item[1], item[0]))[0]
        execution = pd.concat([train.iloc[[-1]], test])
        for cost in COSTS:
            baseline = _simulate(execution, starting_capital_aud, 0.75, cost)
            candidate = _simulate(execution, starting_capital_aud, selected, cost)
            hold = simulate_buy_and_hold_benchmark(
                test[["btc_price_aud"]], starting_capital_aud, fee_pct=cost)
            dca = fixed_dca_benchmark(test, starting_capital_aud, fee_pct=cost)
            results.append({
                "fold": len(set(r["fold"] for r in results)) + 1 if cost == COSTS[0]
                        else results[-1]["fold"],
                "train_end": str(train.index[-1]),
                "test_start": str(test.index[0]),
                "test_end": str(test.index[-1]),
                "test_rows": len(test),
                "sell_threshold": selected,
                "cost_per_side": cost,
                "candidate_equity_aud": candidate["ending_equity_aud"],
                "baseline_equity_aud": baseline["ending_equity_aud"],
                "buy_hold_equity_aud": hold["ending_equity_aud"],
                "fixed_dca_equity_aud": dca["ending_equity_aud"],
                "candidate_minus_baseline_aud": candidate["ending_equity_aud"]
                                                 - baseline["ending_equity_aud"],
                "candidate_minus_hold_aud": candidate["ending_equity_aud"]
                                             - hold["ending_equity_aud"],
                "candidate_minus_dca_aud": candidate["ending_equity_aud"]
                                            - dca["ending_equity_aud"],
                "candidate_cash_remaining_aud": candidate["cash_remaining_aud"],
                "candidate_btc_held": candidate["btc_held"],
                "candidate_buy_count": candidate["buy_count"],
                "candidate_sell_count": candidate["sell_count"],
            })
    if not results:
        raise ValueError("No valid walk-forward folds")
    rows = pd.DataFrame(results)
    aggregates = []
    for fee, group in rows.groupby("cost_per_side", sort=True):
        aggregates.append({
            "cost_per_side": float(fee), "folds": len(group),
            "candidate_beats_baseline_folds": int(
                (group["candidate_minus_baseline_aud"] > 0).sum()),
            "candidate_beats_hold_folds": int(
                (group["candidate_minus_hold_aud"] > 0).sum()),
            "candidate_beats_dca_folds": int(
                (group["candidate_minus_dca_aud"] > 0).sum()),
            "median_edge_vs_baseline_aud": float(
                group["candidate_minus_baseline_aud"].median()),
            "mean_edge_vs_baseline_aud": float(
                group["candidate_minus_baseline_aud"].mean()),
            "worst_edge_vs_baseline_aud": float(
                group["candidate_minus_baseline_aud"].min()),
            "mean_edge_vs_hold_aud": float(
                group["candidate_minus_hold_aud"].mean()),
            "mean_edge_vs_dca_aud": float(
                group["candidate_minus_dca_aud"].mean()),
        })
    return {"folds": results, "summary_by_cost": aggregates,
            "fold_count": int(rows["fold"].nunique()),
            "caution": "Historical point-in-time risk inputs require separate proof; not an approved live strategy."}
