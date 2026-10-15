"""Research-only benchmark harness with common execution start and dates.

Every strategy starts with the same AUD cash on the first observation and may
execute no earlier than the second observation. No CGT deduction is modeled.
"""
import numpy as np
import pandas as pd

from engines.research.cycle_backtest import simulate_next_observation_strategy


def compare_lagged_cycle_to_benchmarks(
    data, starting_capital_aud=500_000.0, fee_pct=0.001,
    fixed_dca_periods=None, **strategy_kwargs,
):
    """Compare cycle timing, equal-slice DCA, and next-bar buy-and-hold fairly.

    Price at row 0 is observable for signal formation only; execution starts
    at row 1 for all policies. Invalid prices are excluded from execution.
    DCA contributions come from the same initial cash pool (no external deposits).
    """
    if not isinstance(data, pd.DataFrame) or data.empty:
        raise ValueError("Require nonempty price/risk DataFrame")
    if not {"btc_price_aud", "risk_score"}.issubset(data.columns):
        raise ValueError("Require btc_price_aud and risk_score")
    if not np.isfinite(starting_capital_aud) or not np.isfinite(fee_pct) or starting_capital_aud <= 0 or not 0 <= fee_pct < 1:
        raise ValueError("Invalid capital or fee")
    ordered = data.sort_index().copy()
    if not ordered.index.is_unique:
        raise ValueError("Duplicate observation dates are not allowed; aggregate with a documented point-in-time policy")
    if not pd.api.types.is_numeric_dtype(ordered["btc_price_aud"]):
        ordered["btc_price_aud"] = pd.to_numeric(ordered["btc_price_aud"], errors="coerce")
    if not pd.api.types.is_numeric_dtype(ordered["risk_score"]):
        ordered["risk_score"] = pd.to_numeric(ordered["risk_score"], errors="coerce")
    if (not np.isfinite(ordered["btc_price_aud"]).all()
            or not (ordered["btc_price_aud"] > 0).all()):
        raise ValueError("Every observation requires a finite positive BTC/AUD price")
    if (not np.isfinite(ordered["risk_score"]).all()
            or not ordered["risk_score"].between(0, 1).all()):
        raise ValueError("Every observation requires a finite risk score between 0 and 1")
    if len(ordered) < 2:
        raise ValueError("At least two observations required")
    cycle_rows, cycle = simulate_next_observation_strategy(
        ordered, starting_capital_aud=starting_capital_aud,
        fee_pct=fee_pct, **strategy_kwargs,
    )
    prices = pd.to_numeric(ordered["btc_price_aud"], errors="coerce")
    eligible = np.isfinite(prices) & (prices > 0)
    execution = ordered.iloc[1:].loc[eligible.iloc[1:]]
    if not eligible.iloc[-1]:
        raise ValueError("Final observation must have a valid BTC/AUD price for comparable mark-to-market")
    if execution.empty:
        raise ValueError("No valid execution prices after first observation")
    first_price = float(execution["btc_price_aud"].iloc[0])
    last_price = float(execution["btc_price_aud"].iloc[-1])
    hold_btc = starting_capital_aud * (1 - fee_pct) / first_price
    if fixed_dca_periods is None:
        fixed_dca_periods = len(execution)
    if not isinstance(fixed_dca_periods, int) or fixed_dca_periods <= 0:
        raise ValueError("fixed_dca_periods must be a positive integer")
    budget = starting_capital_aud / fixed_dca_periods
    cash = float(starting_capital_aud)
    btc = 0.0
    fees = 0.0
    purchases = 0
    for price in execution["btc_price_aud"].iloc[:fixed_dca_periods]:
        buy = min(budget, cash)
        fees += buy * fee_pct
        btc += buy * (1 - fee_pct) / float(price)
        cash -= buy
        purchases += 1
    if not cycle or not np.isfinite(cycle.get("ending_equity_aud", float("nan"))):
        raise ValueError("Cycle strategy has no valid ending equity; cannot compare benchmarks")
    results = {
        "cycle_lagged": cycle,
        "buy_and_hold_next_bar": {
            "ending_equity_aud": hold_btc * last_price,
            "btc_held": hold_btc,
            "cash_remaining_aud": 0.0,
            "fees_aud": starting_capital_aud * fee_pct,
            "buy_count": 1,
        },
        "fixed_dca_next_bar": {
            "ending_equity_aud": cash + btc * last_price,
            "btc_held": btc,
            "cash_remaining_aud": cash,
            "fees_aud": fees,
            "buy_count": purchases,
        },
    }
    return results
