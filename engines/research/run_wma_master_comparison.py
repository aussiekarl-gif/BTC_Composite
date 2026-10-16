"""Read-only historical AUD research runner using the central master.

Run (with central-data read permissions):
python -m engines.research.run_wma_master_comparison
No CSV uploads, secrets printed, portfolio writes, or Production changes.
"""
import json

import pandas as pd

from engines.shared.central_data import load_master
from engines.research.wma_window_backtest import prepare_weekly_wma
from engines.research.compare_wma_windows import compare, chronological_holdout


def main():
    master = load_master(columns=["btc_price_aud"])
    price = pd.to_numeric(master["btc_price_aud"], errors="coerce")
    price = price.where(price > 0)
    weekly = prepare_weekly_wma(price)
    if len(weekly) < 100:
        raise ValueError("Insufficient post-200WMA weekly AUD data for comparison")
    weekly = weekly.rename(columns={"wma_200": "wma_200_aud"})
    # All missing post-warmup prices must remain explicit: missing weeks cannot
    # be compressed into an invented 12/16-calendar-week execution schedule.
    if not weekly.index.to_series().diff().dropna().eq(pd.Timedelta(days=7)).all():
        raise ValueError("Discontinuous AUD weekly observations; refusing backtest")
    result = compare(weekly)
    holdout = chronological_holdout(weekly)
    # Equal-start capital benchmark, including the same initial 0.10% fee.
    first_price = float(weekly["btc_price_aud"].iloc[0])
    hold_btc = 500_000.0 * (1.0 - 0.001) / first_price
    hold_equity = hold_btc * weekly["btc_price_aud"].astype(float)
    hold_drawdown = (hold_equity / hold_equity.cummax() - 1.0).min()
    benchmark = {
        "ending_equity_aud": float(hold_equity.iloc[-1]),
        "btc_held": float(hold_btc),
        "max_drawdown_pct": float(100.0 * hold_drawdown),
        "fees_aud": 500.0,
    }
    # Reject a promotion recommendation if performance has not beaten the
    # no-trading benchmark, or if the out-of-sample simulation made no trades.
    holdout_trade_count = int(holdout.get("test_buy_count", 0)) + int(holdout.get("test_sell_count", 0))
    research_gates = {
        "out_of_sample_outperformance": bool(holdout["test_excess_equity_aud"] > 0),
        "holdout_has_trades": bool(holdout_trade_count > 0),
        "automatically_promotable": False,
        "reason": "Further independent tests and explicit approval required.",
    }
    report = {
        "source": "read-only central BTC research master, btc_price_aud",
        "currency": "AUD",
        "date_start": weekly.index.min().isoformat(),
        "date_end": weekly.index.max().isoformat(),
        "observations": len(weekly),
        "all_variants": result.to_dict(orient="records"),
        "full_period_buy_and_hold": benchmark,
        "research_gates": research_gates,
        "holdout": holdout,
        "limitations": [
            "Closing-price fills are hypothetical; add spreads/slippage before promotion.",
            "Central master provenance and historical revision checks remain required.",
            "A single 70/30 chronological split is insufficient to establish robustness.",
            "Training and holdout simulations each begin with fresh capital.",
        ],
    }
    print(json.dumps(report, indent=2, default=str, allow_nan=False))


if __name__ == "__main__":
    main()
