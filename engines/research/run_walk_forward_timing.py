#!/usr/bin/env python3
"""Research-only expanding walk-forward validation for BTC entry timing.

For each chronological fold, parameters are selected using only observations
before the test block. The chosen parameters are frozen during the next block.
Each test block starts with fresh AUD 500,000 so results are comparable by fold.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from engines.shared.central_data import load_master

CAPITAL = 500_000.0
FEE = 0.001
THRESHOLDS = (0.15, 0.25, 0.35, 0.45, 0.55, 0.65, 0.75)
MULTIPLIERS = (1.0, 2.0, 3.0, 4.0, 6.0, 8.0)


def run_strategy(data: pd.DataFrame, threshold: float | None, multiplier: float,
                 mode: str) -> dict:
    prices = data["btc_price_aud"].to_numpy(float)
    risks = data["decision_risk"].to_numpy(float)
    n = len(data)
    installment = CAPITAL / n
    cash = CAPITAL
    btc = 0.0
    gross_spent = 0.0
    buys = 0
    for i, (price, risk) in enumerate(zip(prices, risks)):
        spend = 0.0
        if mode == "fixed_dca":
            spend = min(cash, installment)
        elif mode == "buy_hold":
            spend = cash if i == 0 else 0.0
        elif mode == "signal" and threshold is not None and risk < threshold:
            strength = (threshold - risk) / threshold
            spend = min(cash, installment * multiplier * strength)
        if spend >= 1.0:
            btc += spend * (1.0 - FEE) / price
            cash -= spend
            gross_spent += spend
            buys += 1
    ending_equity = cash + btc * prices[-1]
    return {
        "ending_equity_aud": float(ending_equity),
        "return_pct": float((ending_equity / CAPITAL - 1.0) * 100.0),
        "btc_held": float(btc),
        "cash_remaining_aud": float(cash),
        "gross_spent_aud": float(gross_spent),
        "fees_aud": float(gross_spent * FEE),
        "buy_observations": int(buys),
    }


def main() -> None:
    raw = load_master(columns=["btc_price_aud", "risk_score"])
    raw["btc_price_aud"] = pd.to_numeric(raw["btc_price_aud"], errors="coerce")
    raw["risk_score"] = pd.to_numeric(raw["risk_score"], errors="coerce")
    raw = raw.sort_index()
    valid = raw[
        np.isfinite(raw["btc_price_aud"])
        & (raw["btc_price_aud"] > 0)
        & np.isfinite(raw["risk_score"])
        & raw["risk_score"].between(0, 1)
    ].copy()
    valid["decision_risk"] = valid["risk_score"].shift(1)
    data = valid[np.isfinite(valid["decision_risk"])].copy()
    if len(data) < 100:
        raise RuntimeError(f"Insufficient lagged observations: {len(data)}")

    n = len(data)
    folds = []
    # Expanding training window: first 50%, then test successive 10% blocks.
    # Final 10% is held back as the last unseen block.
    for fold_num, (train_end_frac, test_end_frac) in enumerate(
        ((0.50, 0.60), (0.60, 0.70), (0.70, 0.80), (0.80, 0.90), (0.90, 1.00)),
        start=1,
    ):
        train_end = int(n * train_end_frac)
        test_end = min(n, int(n * test_end_frac))
        train = data.iloc[:train_end]
        test = data.iloc[train_end:test_end]
        if len(test) < 5:
            continue

        # Split each historical training window chronologically: fit candidates
        # on the first 80%, then select parameters on the final 20% validation slice.
        # The outer test block remains completely unseen until parameters are frozen.
        fit_end = max(1, int(len(train) * 0.80))
        train_fit = train.iloc[:fit_end]
        train_validation = train.iloc[fit_end:]
        if len(train_validation) < 5:
            train_validation = train.iloc[-max(5, len(train) // 5):]
            train_fit = train.iloc[:len(train) - len(train_validation)]

        candidates = []
        for threshold in THRESHOLDS:
            for multiplier in MULTIPLIERS:
                fit_metrics = run_strategy(train_fit, threshold, multiplier, "signal")
                validation_metrics = run_strategy(train_validation, threshold, multiplier, "signal")
                candidates.append({
                    "threshold": threshold,
                    "multiplier": multiplier,
                    "fit_ending_equity_aud": fit_metrics["ending_equity_aud"],
                    "validation_ending_equity_aud": validation_metrics["ending_equity_aud"],
                    "validation_return_pct": validation_metrics["return_pct"],
                    "validation_cash_remaining_aud": validation_metrics["cash_remaining_aud"],
                    "validation_btc_held": validation_metrics["btc_held"],
                    "validation_buy_observations": validation_metrics["buy_observations"],
                })
        # Select using the inner validation slice, not fit performance or outer test.
        candidates.sort(
            key=lambda x: (x["validation_ending_equity_aud"], -x["validation_cash_remaining_aud"], -x["validation_buy_observations"]),
            reverse=True,
        )
        winner = candidates[0]
        test_signal = run_strategy(test, winner["threshold"], winner["multiplier"], "signal")
        test_fixed = run_strategy(test, None, 1.0, "fixed_dca")
        test_hold = run_strategy(test, None, 1.0, "buy_hold")
        folds.append({
            "fold": fold_num,
            "train_start": train.index[0].isoformat(),
            "train_end": train.index[-1].isoformat(),
            "test_start": test.index[0].isoformat(),
            "test_end": test.index[-1].isoformat(),
            "train_observations": int(len(train)),
            "test_observations": int(len(test)),
            "selected_parameters": {
                "threshold": winner["threshold"],
                "multiplier": winner["multiplier"],
                "threshold_at_grid_boundary": winner["threshold"] in (min(THRESHOLDS), max(THRESHOLDS)),
                "multiplier_at_grid_boundary": winner["multiplier"] in (min(MULTIPLIERS), max(MULTIPLIERS)),
                "inner_validation_ending_equity_aud": winner["validation_ending_equity_aud"],
                "inner_validation_return_pct": winner["validation_return_pct"],
                "inner_validation_cash_remaining_aud": winner["validation_cash_remaining_aud"],
                "inner_validation_buy_observations": winner["validation_buy_observations"],
            },
            "test": {
                "signal": test_signal,
                "fixed_dca": test_fixed,
                "buy_hold": test_hold,
                "signal_minus_fixed_dca_aud": test_signal["ending_equity_aud"] - test_fixed["ending_equity_aud"],
                "signal_minus_buy_hold_aud": test_signal["ending_equity_aud"] - test_hold["ending_equity_aud"],
            },
            "training_top_5": candidates[:5],
        })

    signal_wins_fixed = sum(f["test"]["signal_minus_fixed_dca_aud"] > 0 for f in folds)
    signal_wins_hold = sum(f["test"]["signal_minus_buy_hold_aud"] > 0 for f in folds)
    output = {
        "title": "BTC EXPANDING WALK-FORWARD TIMING VALIDATION",
        "dataset": {
            "valid_lagged_observations": int(n),
            "start": data.index[0].isoformat(),
            "end": data.index[-1].isoformat(),
            "capital_per_test_block_aud": CAPITAL,
            "fee_per_side_pct": FEE * 100,
            "risk_lag": "one prior valid joint price/risk observation",
        },
        "method": {
            "folds": "Expanding training window; each next 10% chronological block is unseen test data",
            "selection_objective": "Inner chronological validation terminal equity after fees, including unspent cash; candidate fit uses earlier 80% of each outer training window",
            "parameter_grid": {"thresholds": list(THRESHOLDS), "multipliers": list(MULTIPLIERS)},
            "boundary_warning": "A winner at a grid boundary means the chosen range may not contain an optimum; treat it as a model-stability warning, not evidence the boundary value is best.",
            "capital": "Fresh AUD 500,000 for each test block and each benchmark",
        },
        "aggregate": {
            "fold_count": len(folds),
            "signal_beats_fixed_dca_folds": int(signal_wins_fixed),
            "signal_beats_buy_hold_folds": int(signal_wins_hold),
            "selected_thresholds": [f["selected_parameters"]["threshold"] for f in folds],
            "selected_multipliers": [f["selected_parameters"]["multiplier"] for f in folds],
            "threshold_boundary_wins": int(sum(f["selected_parameters"]["threshold_at_grid_boundary"] for f in folds)),
            "multiplier_boundary_wins": int(sum(f["selected_parameters"]["multiplier_at_grid_boundary"] for f in folds)),
            "sum_test_ending_equity_signal_aud": float(sum(f["test"]["signal"]["ending_equity_aud"] for f in folds)),
            "sum_test_ending_equity_fixed_dca_aud": float(sum(f["test"]["fixed_dca"]["ending_equity_aud"] for f in folds)),
            "sum_test_ending_equity_buy_hold_aud": float(sum(f["test"]["buy_hold"]["ending_equity_aud"] for f in folds)),
            "warning": "Summed fold values are comparisons across separate fresh-capital experiments, not one continuous portfolio.",
        },
        "folds": folds,
        "caveats": [
            "This is an expanding walk-forward research test, not a guarantee of future returns.",
            "Risk-score availability timestamps and upstream lookahead still require independent audit.",
            "Uses close prices; spread, slippage, market impact, tax and terminal liquidation costs excluded.",
            "Each test block is a separate fresh-capital experiment, not a continuous account.",
            "Each outer training window is split chronologically into an earlier fit slice and a later inner validation slice for parameter selection; both slices start with fresh capital, so this is a selection diagnostic rather than a continuous portfolio simulation.",",
            "Threshold/multiplier grid is limited; performance can be sensitive to the tested parameter choices.",
        ],
    }
    print(json.dumps(output, indent=2, allow_nan=False))


if __name__ == "__main__":
    main()
