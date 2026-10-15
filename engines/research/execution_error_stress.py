"""Stress-test imperfect BTC trade execution without changing signal history.

Adverse slippage is measured as a fraction of the contemporaneous market price:
buy orders pay more, sell orders receive less. This is *execution-price error*,
not a claim to model a 30% cycle-bottom/top identification error.
"""
import numpy as np
import pandas as pd

from engines.research.cycle_backtest import simulate_next_observation_strategy


def execution_error_sweep(
    data,
    error_fractions=(0.0, 0.15, 0.30),
    starting_capital_aud=500_000.0,
    fee_pct=0.001,
    **strategy_kwargs,
):
    """Revalue each executed buy/sell using adverse prices; keep decisions fixed.

    This fixed-action sensitivity deliberately does not re-optimise signal timing.
    Returns rows with final equity, BTC, cash, fees and trade counts.
    """
    history, _ = simulate_next_observation_strategy(
        data, starting_capital_aud=starting_capital_aud,
        fee_pct=fee_pct, **strategy_kwargs,
    )
    if history.empty:
        raise ValueError("No observations")
    results = []
    for error in error_fractions:
        if not np.isfinite(error) or not 0 <= error < 1:
            raise ValueError("Execution error fractions must be finite and in [0, 1)")
        cash = float(starting_capital_aud)
        btc = 0.0
        total_fees = 0.0
        buys = sells = 0
        for _, row in history.iterrows():
            price = float(row["btc_price_aud"])
            if not np.isfinite(price) or price <= 0:
                continue
            if row["action"] == "BUY":
                gross = min(cash, float(row["buy_gross_aud"]))
                fee = gross * fee_pct
                btc += (gross - fee) / (price * (1 + error))
                cash -= gross
                total_fees += fee
                buys += 1
            elif row["action"] == "SELL":
                # Sell the same fraction of *current* holdings as the base strategy.
                previous_btc = float(row["btc_held"]) + float(row["btc_sold"])
                fraction = float(row["btc_sold"]) / previous_btc if previous_btc > 0 else 0.0
                quantity = btc * fraction
                gross = quantity * price * (1 - error)
                fee = gross * fee_pct
                cash += gross - fee
                btc -= quantity
                total_fees += fee
                sells += 1
        last_price = float(history["btc_price_aud"].iloc[-1])
        if not np.isfinite(last_price) or last_price <= 0:
            raise ValueError("Final price must be positive")
        results.append({
            "execution_error_fraction": float(error),
            "ending_equity_aud": float(cash + btc * last_price),
            "btc_held": float(btc),
            "cash_remaining_aud": float(cash),
            "fees_aud": float(total_fees),
            "buy_count": buys,
            "sell_count": sells,
        })
    return pd.DataFrame(results)
