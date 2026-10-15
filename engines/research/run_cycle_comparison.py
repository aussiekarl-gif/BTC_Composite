"""Run reproducible point-in-time BTC cycle research from an input CSV.

Example (with a validated, point-in-time dataset):
 python -m engines.research.run_cycle_comparison --csv my_weekly_signals.csv

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
    parser.add_argument("--out", help="Optional JSONL output path for auditable strategy metrics")
    args = parser.parse_args()
    data = pd.read_csv(args.csv)
    required = {'btc_price_aud', 'risk_score'}
    if not required.issubset(data.columns):
        parser.error('Input requires btc_price_aud and risk_score in AUD. Do not use data/risk_history.csv directly: it contains USD prices and mixed audit records.')
    if args.date_column not in data:
        parser.error("Explicit date column required to preserve historical execution order")
    data[args.date_column] = pd.to_datetime(data[args.date_column], errors="raise", utc=True)
    data = data.set_index(args.date_column)
    if data.index.has_duplicates:
        parser.error("Duplicate historical dates; supply a verified one-observation-per-period series")
    results = compare_lagged_cycle_to_benchmarks(
        data, starting_capital_aud=args.capital, fee_pct=args.fee
    )
    records = []
    for label, result in results.items():
        record = {
            "strategy": label,
            "ending_equity_aud": float(result["ending_equity_aud"]),
            "btc_held": float(result["btc_held"]),
            "cash_aud": float(result.get("cash_remaining_aud", result.get("ending_cash_aud", 0))),
            "fees_aud": float(result["fees_aud"]),
        }
        records.append(record)
        print(json.dumps(record, sort_keys=True))
    if args.out:
        from pathlib import Path
        output = Path(args.out)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text("".join(json.dumps(item, sort_keys=True) + "\n" for item in records), encoding="utf-8")


if __name__ == "__main__":
    main()
