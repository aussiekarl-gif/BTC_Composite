"""Leakage-resistant anchored walk-forward cycle validation (research only).

For each fold, tune on historical training data and report an independent
fresh-capital test period with the final training signal available for first
test execution. Benchmarks enter at the identical first test observation.
"""
import pandas as pd

from engines.research.cycle_backtest import walk_forward_parameter_sweep


def anchored_walk_forward_report(
    data,
    train_fractions=(0.50, 0.60, 0.70, 0.80),
    starting_capital_aud=500_000.0,
    fee_pct=0.001,
    **sweep_kwargs,
):
    """Return chronological out-of-sample fold metrics; never optimise on test data.

    Each fold is a separate fresh-capital experiment, NOT a continuous portfolio
    simulation. Fold returns must not be summed or compounded as a live track
    record. Inputs must contain point-in-time causal risk scores.
    """
    if not isinstance(data, pd.DataFrame) or len(data) < 6:
        raise ValueError("Need at least six historical observations")
    ordered = data.sort_index()
    rows = []
    for frac in train_fractions:
        if not 0.50 <= frac <= 0.90:
            raise ValueError("Train fractions must be between 0.50 and 0.90")
        board, winner, trades, cycle, hold = walk_forward_parameter_sweep(
            ordered,
            split_fraction=float(frac),
            starting_capital_aud=starting_capital_aud,
            fee_pct=fee_pct,
            **sweep_kwargs,
        )
        if not winner or not cycle or not hold or trades.empty:
            continue
        rows.append({
            "train_fraction": frac,
            "train_end": trades.attrs.get("train_end"),
            "test_start": trades.attrs.get("test_start"),
            "test_end": trades.attrs.get("test_end"),
            "test_observations": len(trades),
            "buy_threshold": winner["buy_threshold"],
            "sell_threshold": winner["sell_threshold"],
            "max_buy_pct_period": winner["max_buy_pct_period"],
            "max_sell_pct_period": winner["max_sell_pct_period"],
            "cycle_equity_aud": cycle["ending_equity_aud"],
            "hold_equity_aud": hold["ending_equity_aud"],
            "cycle_btc": cycle["btc_held"],
            "hold_btc": hold["btc_held"],
            "cycle_fees_aud": cycle["fees_aud"],
            "hold_fees_aud": hold["fees_aud"],
            "cycle_beats_hold": cycle["ending_equity_aud"] > hold["ending_equity_aud"],
        })
    return pd.DataFrame(rows)
