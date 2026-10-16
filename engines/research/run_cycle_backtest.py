#!/usr/bin/env python3
"""Run the research-only cycle backtest against the validated central audit master.

This script is deliberately read-only and does not change Production or the data master.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import numpy as np
import pandas as pd

from engines.shared.central_data import load_master
from engines.research.cycle_backtest import (
    simulate_buy_and_hold_benchmark,
    simulate_next_observation_strategy,
    walk_forward_parameter_sweep,
)


def rounded_summary(summary):
    return {
        key: round(float(value), 4) if isinstance(value, (float, np.floating)) else value
        for key, value in summary.items()
    }


def main():
    data = load_master(columns=["btc_price_aud", "risk_score"])
    data["btc_price_aud"] = pd.to_numeric(data["btc_price_aud"], errors="coerce")
    data["risk_score"] = pd.to_numeric(data["risk_score"], errors="coerce")
    raw_rows = len(data)
    valid = data[
        np.isfinite(data["btc_price_aud"])
        & (data["btc_price_aud"] > 0)
        & np.isfinite(data["risk_score"])
        & data["risk_score"].between(0, 1)
    ].sort_index()

    if len(valid) < 20:
        raise RuntimeError(
            f"Insufficient valid observations for meaningful backtest: {len(valid)} "
            f"valid of {raw_rows} loaded."
        )

    capital = 500_000.0
    fee = 0.001
    default_df, default_summary = simulate_next_observation_strategy(
        valid,
        starting_capital_aud=capital,
        fee_pct=fee,
    )
    benchmark = simulate_buy_and_hold_benchmark(
        valid[["btc_price_aud"]],
        starting_capital_aud=capital,
        fee_pct=fee,
    )
    leaderboard, winner, holdout_df, holdout_summary, holdout_benchmark = (
        walk_forward_parameter_sweep(
            valid,
            starting_capital_aud=capital,
            fee_pct=fee,
            split_fraction=0.70,
        )
    )

    output = {
        "dataset": {
            "repository": "aussiekarl-gif/btc-audit-data",
            "master": "btc_audit_backup.csv",
            "raw_rows_after_master_date_dedup": int(raw_rows),
            "valid_rows": int(len(valid)),
            "excluded_rows": int(raw_rows - len(valid)),
            "start_date": valid.index.min().isoformat(),
            "end_date": valid.index.max().isoformat(),
            "capital_aud": capital,
            "fee_per_side_pct": fee * 100,
            "risk_score_range": [
                float(valid["risk_score"].min()),
                float(valid["risk_score"].max()),
            ],
        },
        "full_history_default_thresholds": rounded_summary(default_summary),
        "full_history_buy_and_hold": rounded_summary(benchmark),
        "walk_forward": {
            "method": "Chronological 70% training / 30% holdout; fresh AUD 500,000 in holdout",
            "train_start": str(valid.index[0]),
            "train_end": str(valid.index[int(len(valid) * 0.70) - 1]),
            "holdout_start": str(holdout_df["date"].min()) if len(holdout_df) else None,
            "holdout_end": str(holdout_df["date"].max()) if len(holdout_df) else None,
            "selected_parameters": winner,
            "holdout_strategy": rounded_summary(holdout_summary),
            "holdout_buy_and_hold": rounded_summary(holdout_benchmark),
            "parameter_combinations_tested": int(len(leaderboard)),
            "top_10_training_candidates": (
                leaderboard.head(10).replace({np.nan: None}).to_dict(orient="records")
            ),
        },
        "limitations": [
            "Risk scores are assumed to have been available at the prior observation; upstream point-in-time publication timing is not independently proven here.",
            "Uses daily/observational closing prices, not intraday fills; spread, slippage, market impact and tax are excluded.",
            "Walk-forward holdout starts with fresh capital and is not a continuous account carried forward from training.",
            "A single chronological split is a first validation, not proof of future profitability.",
            "Buy-and-hold is marked to market at the final close; no terminal liquidation fee is applied, making that comparison conservative for the strategy.",
        ],
    }
    print("BTC CYCLE BACKTEST RESULTS")
    print(json.dumps(output, indent=2, default=str, allow_nan=False))


if __name__ == "__main__":
    main()
