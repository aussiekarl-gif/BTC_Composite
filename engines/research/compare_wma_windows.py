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



def chronological_holdout(frame, *, split_fraction=0.70, capital=500_000.,
                          fee=0.001):
    """Select on earlier weekly data, report a fresh-capital held-out comparison.

    Training and holdout runs start with independent capital. The test segment
    includes one preceding row only to provide the last known crossing state;
    its equity is excluded. No use of test outcomes for selection.
    """
    if not 0.5 <= split_fraction <= 0.9:
        raise ValueError("split_fraction must be between 0.5 and 0.9")
    if not {"btc_price_aud", "wma_200_aud"}.issubset(frame):
        raise ValueError("AUD columns required")
    ordered = frame.sort_index()
    cut = int(len(ordered) * split_fraction)
    if cut < 20 or len(ordered) - cut < 20:
        raise ValueError("Need at least 20 weeks in each chronological segment")
    train = ordered.iloc[:cut].copy()
    test = ordered.iloc[cut:].copy()
    ranking = compare(train, capital=capital, fee=fee).sort_values(
        ["ending_equity_aud", "max_drawdown_pct"],
        ascending=[False, False], kind="stable",
    )
    winner = ranking.iloc[0]
    test_input = pd.concat([train.iloc[[-1]], test])
    # Need the preceding signal row, but trade cash must not be deployed there.
    history, result = simulate_wma_windows(
        test_input.rename(columns={"wma_200_aud": "wma_200"}),
        weeks=int(winner["weeks"]),
        buy_trigger_pct=float(winner["buy_trigger_pct"]),
        sell_trigger_pct=float(winner["sell_trigger_pct"]),
        starting_capital_aud=capital, fee_pct=fee,
    )
    test_history = history.iloc[1:].copy()
    price = pd.to_numeric(test["btc_price_aud"], errors="coerce")
    first_price = float(price.iloc[0])
    last_price = float(price.iloc[-1])
    if not np.isfinite(first_price) or not np.isfinite(last_price) or min(first_price, last_price) <= 0:
        raise ValueError("Holdout benchmark requires valid start/end AUD prices")
    hold_value = capital * (1-fee) * last_price / first_price
    return {
        "train_start": str(train.index[0]), "train_end": str(train.index[-1]),
        "test_start": str(test.index[0]), "test_end": str(test.index[-1]),
        "selected_parameters": {
            "weeks": int(winner["weeks"]),
            "buy_trigger_pct": float(winner["buy_trigger_pct"]),
            "sell_trigger_pct": float(winner["sell_trigger_pct"]),
        },
        "test_strategy_ending_equity_aud": float(test_history.equity_aud.iloc[-1]),
        "test_buy_hold_ending_equity_aud": float(hold_value),
        "test_excess_equity_aud": float(test_history.equity_aud.iloc[-1] - hold_value),
        "test_fees_aud": float(test_history.fee_aud.sum()),
        "test_buy_count": int((test_history.action == "BUY").sum()),
        "test_sell_count": int((test_history.action == "SELL").sum()),
        "test_btc_exposure_weeks": int((test_history.btc_held > 1e-10).sum()),
        "test_btc_exposure_pct": float(100*(test_history.btc_held > 1e-10).mean()),
        "test_max_drawdown_pct": float(100*(test_history.equity_aud /
                                      test_history.equity_aud.cummax()-1).min()),
    }

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--csv", required=True)
    parser.add_argument("--output", default="")
    parser.add_argument("--holdout", action="store_true")
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
    if args.holdout:
        print(json.dumps(chronological_holdout(frame), indent=2, default=str))


if __name__ == "__main__":
    main()
