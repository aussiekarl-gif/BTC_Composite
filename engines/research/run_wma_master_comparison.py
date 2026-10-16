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
    report = {
        "source": "read-only central BTC research master, btc_price_aud",
        "currency": "AUD",
        "date_start": weekly.index.min().isoformat(),
        "date_end": weekly.index.max().isoformat(),
        "observations": len(weekly),
        "all_variants": result.to_dict(orient="records"),
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
