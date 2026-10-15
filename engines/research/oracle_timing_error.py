"""Stress BTC cycle execution at adverse prices relative to known extrema.

This is an ex-post diagnostic, never a deployable entry/exit algorithm:
the minimum and maximum over a full window are not known at its beginning.
"""
import numpy as np
import pandas as pd


def oracle_turning_point_error_table(
    prices, error_fractions=(0.0, 0.15, 0.30), capital_aud=500_000.0,
    fee_pct=0.001,
):
    """Buy after an observed window minimum and sell after a later maximum.

    The diagnostic enforces chronological buy-before-sell, with entry
    at min_price*(1+error) and exit at max_price*(1-error). Results represent
    upper-bound timing sensitivity, not achievable backtest performance.
    """
    p = pd.to_numeric(pd.Series(prices), errors="coerce").reset_index(drop=True)
    if len(p) < 2 or not np.isfinite(p).all() or not (p > 0).all():
        raise ValueError("Need at least two finite positive prices")
    if not np.isfinite(capital_aud) or capital_aud <= 0 or not 0 <= fee_pct < 1:
        raise ValueError("Invalid capital or fees")
    buy_at = int(p.iloc[:-1].idxmin())
    sell_at = int(p.iloc[buy_at + 1:].idxmax())
    bottom = float(p.iloc[buy_at])
    top = float(p.iloc[sell_at])
    rows = []
    for error in error_fractions:
        if not np.isfinite(error) or not 0 <= error < 1:
            raise ValueError("Error fractions must be in [0, 1)")
        buy_price = bottom * (1 + error)
        sell_price = top * (1 - error)
        btc = capital_aud * (1 - fee_pct) / buy_price
        final_aud = btc * sell_price * (1 - fee_pct)
        rows.append({
            "error_fraction": float(error),
            "buy_index": buy_at,
            "sell_index": sell_at,
            "bottom_price_aud": bottom,
            "top_price_aud": top,
            "entry_price_aud": buy_price,
            "exit_price_aud": sell_price,
            "ending_cash_aud": float(final_aud),
            "return_pct": float(100 * (final_aud / capital_aud - 1)),
            "hindsight_oracle": True,
        })
    return pd.DataFrame(rows)
