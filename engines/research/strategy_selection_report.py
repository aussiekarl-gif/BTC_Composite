"""Compare train-selected BTC cycle parameters on untouched chronological holdouts.

The test window is never used to select parameters. Each fold is a fresh-capital
experiment, not a continuous portfolio across folds. This report explicitly
includes the buy-and-hold opportunity cost.
"""
import pandas as pd

from engines.research.cycle_backtest import walk_forward_parameter_sweep
from engines.research.benchmark_harness import compare_lagged_cycle_to_benchmarks


def optimize_and_compare(data, splits=(0.55, 0.65, 0.75, 0.85),
                         starting_capital_aud=500_000.0, fee_pct=0.001,
                         **grid_kwargs):
    """Train a cycle rule on each prefix; test against equal-capital baselines."""
    if not isinstance(data, pd.DataFrame) or data.empty:
        raise ValueError("Require dated price/risk observations")
    ordered = data.sort_index()
    if not {"btc_price_aud", "risk_score"}.issubset(ordered.columns):
        raise ValueError("Missing BTC/AUD price or risk score")
    if not ordered.index.is_unique:
        raise ValueError("Duplicate observation dates")
    if len(ordered) < 5:
        raise ValueError("Insufficient observations for chronological evaluation")
    output = []
    for split in splits:
        leaderboard, winner, holdout, cycle, hold_benchmark = walk_forward_parameter_sweep(
            ordered, split_fraction=float(split),
            starting_capital_aud=starting_capital_aud, fee_pct=fee_pct,
            **grid_kwargs,
        )
        if not winner or not cycle or holdout.empty:
            continue
        n_train = int(len(ordered) * split)
        # The final training risk is known before the first holdout execution.
        test_with_context = ordered.iloc[n_train - 1:].copy()
        params = {k: winner[k] for k in (
            "buy_threshold", "sell_threshold", "max_buy_pct_period", "max_sell_pct_period"
        )}
        comparable = compare_lagged_cycle_to_benchmarks(
            test_with_context, starting_capital_aud=starting_capital_aud,
            fee_pct=fee_pct, **params,
        )
        cycle_equity = comparable["cycle_lagged"]["ending_equity_aud"]
        hold_equity = comparable["buy_and_hold_next_bar"]["ending_equity_aud"]
        dca_equity = comparable["fixed_dca_next_bar"]["ending_equity_aud"]
        output.append({
            "split_fraction": float(split),
            "train_observations": n_train,
            "test_observations": len(holdout),
            "test_start": str(holdout.index[0]),
            "test_end": str(holdout.index[-1]),
            **params,
            "cycle_equity_aud": cycle_equity,
            "hold_equity_aud": hold_equity,
            "fixed_dca_equity_aud": dca_equity,
            "cycle_minus_hold_aud": cycle_equity - hold_equity,
            "cycle_minus_dca_aud": cycle_equity - dca_equity,
            "beat_hold": bool(cycle_equity > hold_equity),
            "beat_dca": bool(cycle_equity > dca_equity),
        })
    return pd.DataFrame(output)
