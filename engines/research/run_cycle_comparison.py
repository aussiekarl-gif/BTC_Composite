"""Run reproducible point-in-time BTC cycle research from an input CSV.

Example:
 python -m engines.research.run_cycle_comparison --csv data/risk_history.csv

Required columns: btc_price_aud, risk_score; optional date column.
Never interpret backfilled risk scores as causal without provenance validation.
"""
import argparse
import json

import pandas as pd

from engines.research.benchmark_harness import compare_lagged_cycle_to_benchmarks


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--csv", required=True)
    parser.add_argument("--date-column", default="date")
    parser.add_argument("--capital", type=float, default=500_000)
    parser.add_argument("--fee", type=float, default=0.001)
    args = parser.parse_args()
    data = pd.read_csv(args.csv)
    if args.date_column in data:
        data[args.date_column] = pd.to_datetime(data[args.date_column], errors="raise")
        data = data.set_index(args.date_column)
    results = compare_lagged_cycle_to_benchmarks(
        data, starting_capital_aud=args.capital, fee_pct=args.fee
    )
    for label, result in results.items():
        print(json.dumps({
            "strategy": label,
            "ending_equity_aud": float(result["ending_equity_aud"]),
            "btc_held": float(result["btc_held"]),
            "cash_aud": float(result.get("cash_remaining_aud", result.get("ending_cash_aud", 0))),
            "fees_aud": float(result["fees_aud"]),
        }, sort_keys=True))


if __name__ == "__main__":
    main()
