"""Research-only earlier-selling robustness probe (never writes portfolio/state).

Input CSV needs date, btc_price_aud, risk_score. Risk scores MUST be genuinely
point-in-time, not retrospectively revised. This probe cannot establish that.
Run: python -m engines.research.sell_threshold_robustness --csv PATH.csv
"""
import argparse
import json

import numpy as np
import pandas as pd

from engines.research.cycle_backtest import (
    simulate_buy_and_hold_benchmark,
    simulate_next_observation_strategy,
)

SELL_THRESHOLDS = (0.55, 0.60, 0.65, 0.70, 0.75)
COSTS = (0.001, 0.003, 0.006)  # all-in per-side fee + spread/slippage proxy


def load_data(path):
    frame = pd.read_csv(path)
    needed = {"date", "btc_price_aud", "risk_score"}
    if not needed.issubset(frame.columns):
        raise ValueError(f"CSV missing columns: {sorted(needed - set(frame.columns))}")
    frame["date"] = pd.to_datetime(frame["date"], errors="raise", utc=True)
    if frame["date"].duplicated().any():
        raise ValueError("Duplicate dates: unsafe for point-in-time evaluation")
    frame = frame.set_index("date").sort_index()
    for col in ("btc_price_aud", "risk_score"):
        frame[col] = pd.to_numeric(frame[col], errors="coerce")
    if not (np.isfinite(frame["btc_price_aud"]).all()
            and (frame["btc_price_aud"] > 0).all()
            and np.isfinite(frame["risk_score"]).all()
            and frame["risk_score"].between(0, 1).all()):
        raise ValueError("Invalid price or risk values; do not silently drop dates")
    if len(frame) < 40:
        raise ValueError("At least 40 sequential observations required")
    return frame


def strategy(frame, sell_threshold, fee, capital):
    _, summary = simulate_next_observation_strategy(
        frame, starting_capital_aud=capital, buy_threshold=0.25,
        sell_threshold=sell_threshold, max_buy_pct_period=0.05,
        max_sell_pct_period=0.20, fee_pct=fee, min_trade_aud=100,
    )
    return summary


def run_probe(data, capital=500000, train_fraction=0.70):
    """Select threshold only on training data; freeze it for untouched holdout."""
    if not 0.5 <= train_fraction <= 0.9:
        raise ValueError("train_fraction must be in [0.5, 0.9]")
    split = int(len(data) * train_fraction)
    if split < 20 or len(data) - split < 10:
        raise ValueError("Insufficient training or holdout observations")
    train = data.iloc[:split]
    holdout = data.iloc[split:]
    # Full training-window next-observation evaluation; no peek into holdout.
    train_results = [
        {"sell_threshold": t, **strategy(train, t, COSTS[1], capital)}
        for t in SELL_THRESHOLDS
    ]
    # Stable tie-break prefers baseline rather than gratuitous earlier selling.
    winner = max(train_results, key=lambda r: (r["ending_equity_aud"], r["sell_threshold"]))
    selected = winner["sell_threshold"]
    # The prior train row supplies ONLY the prior-week signal. Drop its account
    # row from metrics by marking results based on final holdout equity, not
    # counts from the prepended row (which is non-trading).
    window = pd.concat([train.iloc[[-1]], holdout])
    records = []
    for fee in COSTS:
        hold_benchmark = simulate_buy_and_hold_benchmark(
            holdout, starting_capital_aud=capital, fee_pct=fee)
        for label, threshold in (("selected", selected), ("baseline_075", 0.75)):
            result = strategy(window, threshold, fee, capital)
            records.append({
                "scenario": label, "sell_threshold": threshold,
                "all_in_cost_per_side": fee,
                "holdout_return_pct": result["total_return_pct"],
                "holdout_equity_aud": result["ending_equity_aud"],
                "buy_and_hold_equity_aud": hold_benchmark["ending_equity_aud"],
                "excess_over_hold_aud": result["ending_equity_aud"]
                                       - hold_benchmark["ending_equity_aud"],
                "cash_remaining_aud": result["cash_remaining_aud"],
                "btc_held": result["btc_held"],
                "fees_aud": result["fees_aud"],
                "buy_count": result["buy_count"],
                "sell_count": result["sell_count"],
            })
    return {
        "train_start": str(train.index[0]), "train_end": str(train.index[-1]),
        "holdout_start": str(holdout.index[0]), "holdout_end": str(holdout.index[-1]),
        "selected_sell_threshold": selected,
        "training_results": train_results,
        "holdout_scenarios": records,
        "limitations": [
            "Risk-score publication timing and historical revisions must be audited.",
            "Cost is an all-in proportional proxy, not order-book slippage or market impact.",
            "Single holdout split is not proof of robustness; rolling walk-forward needed.",
            "Cash earns zero interest; CGT and funding costs excluded.",
            "The benchmark buys at holdout start; timing strategies trade from the next observation.",
        ],
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--csv", required=True)
    parser.add_argument("--capital", type=float, default=500000)
    parser.add_argument("--train-fraction", type=float, default=0.70)
    args = parser.parse_args()
    print(json.dumps(run_probe(load_data(args.csv), args.capital,
                               args.train_fraction), indent=2, allow_nan=False))


if __name__ == "__main__":
    main()
