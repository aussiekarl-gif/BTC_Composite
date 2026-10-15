"""Point-in-time signal-delay robustness for BTC cycle trades."""
import pandas as pd
from engines.research.cycle_backtest import simulate_cycle_strategy


def signal_delay_sweep(data, delays=(1, 2, 4, 8, 13, 26),
                       starting_capital_aud=500_000.0, fee_pct=0.001, **kwargs):
    """Delay observed risk by N bars; decisions never use future observations."""
    if not isinstance(data, pd.DataFrame) or not {"btc_price_aud", "risk_score"}.issubset(data):
        raise ValueError("Require dated BTC/AUD price and risk score DataFrame")
    ordered = data.sort_index().copy()
    if not ordered.index.is_unique or ordered.empty:
        raise ValueError("Duplicate dates or empty history")
    price = pd.to_numeric(ordered["btc_price_aud"], errors="coerce")
    risk = pd.to_numeric(ordered["risk_score"], errors="coerce")
    if not (price.notna().all() and price.gt(0).all() and risk.between(0, 1).all()):
        raise ValueError("Invalid BTC/AUD price or risk history")
    results = []
    for delay in delays:
        if not isinstance(delay, int) or delay < 1 or delay >= len(ordered):
            raise ValueError("Delay must be at least one and shorter than the series")
        delayed = ordered.copy()
        delayed["risk_score"] = risk.shift(delay)
        _, summary = simulate_cycle_strategy(
            delayed, starting_capital_aud=starting_capital_aud,
            fee_pct=fee_pct, **kwargs,
        )
        results.append({
            "delay_observations": delay,
            "ending_equity_aud": summary["ending_equity_aud"],
            "btc_held": summary["btc_held"],
            "cash_remaining_aud": summary["cash_remaining_aud"],
            "fees_aud": summary["fees_aud"],
            "buy_count": summary["buy_count"],
            "sell_count": summary["sell_count"],
        })
    return pd.DataFrame(results)
