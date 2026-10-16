"""Offline, reproducible AUD comparison of 12/16-week 200WMA windows.

Input CSV must contain date, btc_price_aud and wma_200_aud. No implicit
USD/AUD conversion and no central-master writes. Example:
python -m engines.research.compare_wma_windows --csv aud_weekly.csv
"""
import argparse
import json

import numpy as np
import pandas as pd

from engines.research.wma_window_backtest import simulate_wma_windows


def compare(frame, *, capital=500_000., fee=0.001):
    needed = {"btc_price_aud", "wma_200_aud"}
    if not needed.issubset(frame.columns):
        raise ValueError("AUD price AND AUD 200WMA required; USD values are not accepted")
    data = frame.copy().sort_index()
    if data.index.has_duplicates:
        raise ValueError("Duplicate week dates are not allowed")
    data = data.rename(columns={"wma_200_aud": "wma_200"})
    data["btc_price_aud"] = pd.to_numeric(data["btc_price_aud"], errors="coerce")
    data["wma_200"] = pd.to_numeric(data["wma_200"], errors="coerce")
    # Do not backfill missing observations from future weeks.
    data = data.replace([np.inf, -np.inf], np.nan)
    valid = data.dropna(subset=["btc_price_aud", "wma_200"])
    if len(valid) < 20 or (valid[["btc_price_aud", "wma_200"]] <= 0).any().any():
        raise ValueError("Insufficient or invalid weekly AUD pricing / moving average")
    results = []
    for weeks in (12, 16):
        for buy, sell in ((-10., 75.), (0., 100.), (10., 125.)):
            history, summary = simulate_wma_windows(
                data, weeks=weeks, buy_trigger_pct=buy,
                sell_trigger_pct=sell, starting_capital_aud=capital,
                fee_pct=fee,
            )
            equity = pd.to_numeric(history.equity_aud, errors="coerce").dropna()
            peak = equity.cummax()
            drawdown = float((equity / peak - 1).min()) if len(equity) else np.nan
            results.append(dict(
                weeks=weeks, buy_trigger_pct=buy, sell_trigger_pct=sell,
                start=str(data.index.min()), end=str(data.index.max()),
                ending_equity_aud=summary["ending_equity_aud"],
                btc_held=summary["btc_held"], cash_aud=summary["cash_aud"],
                fees_aud=summary["fees_aud"],
                buy_count=summary["buy_count"],
                sell_count=summary["sell_count"],
                max_drawdown_pct=100 * drawdown,
            ))
    # Reporting only: parameter ranking must be repeated on held-out dates
    # before claiming an optimal rule.
    return pd.DataFrame(results)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--csv", required=True)
    parser.add_argument("--output", default="")
    args = parser.parse_args()
    frame = pd.read_csv(args.csv)
    if "date" not in frame:
        raise SystemExit("CSV must include an explicit date column")
    frame["date"] = pd.to_datetime(frame["date"], errors="raise", utc=True)
    frame = frame.set_index("date").sort_index()
    results = compare(frame)
    if args.output:
        results.to_csv(args.output, index=False)
    print(json.dumps(results.to_dict(orient="records"), indent=2, default=str))


if __name__ == "__main__":
    main()
