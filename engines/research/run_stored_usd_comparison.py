"""Research-only historical USD comparison from archived provider CSV.

IMPORTANT: This does NOT report AUD returns. Starting capital is USD 500,000.
It uses the archived BTC/USD prices and the contemporaneous MVRV Z-score
as a transparent historical signal; independent provider point-in-time
revision history is not established. Never promote based on this report.
"""
import argparse
import json
from pathlib import Path
import numpy as np
import pandas as pd
from engines.research.benchmark_harness import compare_lagged_cycle_to_benchmarks
from engines.research.strategy_selection_report import optimize_and_compare

def main():
    p = argparse.ArgumentParser()
    p.add_argument("--capital-usd", type=float, default=500000)
    p.add_argument("--out", default="research_outputs/stored_usd_comparison.json")
    a = p.parse_args()
    source = Path("data/mvrv_z_score_2026-10-06T21-46-14.csv")
    df = pd.read_csv(source)
    df["date"] = pd.to_datetime(df["timestamp"], unit="ms", utc=True)
    df = df.set_index("date").sort_index()
    df = df.loc[~df.index.duplicated(keep="last")]
    df["btc_price_aud"] = pd.to_numeric(df["Price"], errors="coerce")
    z = pd.to_numeric(df["MVRV Z-Score"], errors="coerce")
    # Fixed ex-ante transform; NOT optimised against the backtest outcome.
    df["risk_score"] = np.clip((z + 1.0) / 8.0, 0.0, 1.0)
    df = df[["btc_price_aud", "risk_score"]].replace([np.inf, -np.inf], np.nan).dropna()
    df = df[(df["btc_price_aud"] > 0) & df["risk_score"].between(0, 1)]
    df = df.loc["2015-01-01":"2026-10-06"].resample("W-MON").last().dropna()
    if len(df) < 200:
        raise ValueError(f"Insufficient historical rows: {len(df)}")
    results = compare_lagged_cycle_to_benchmarks(df, starting_capital_aud=a.capital_usd)
    report = {"currency": "USD", "capital_usd": a.capital_usd,
              "signal": "Archived MVRV Z-score, fixed mapping clip((z+1)/8,0,1)",
              "caution": "Provider revisions not audited; NOT AUD and NOT a live validated strategy",
              "rows": len(df), "start": str(df.index.min()), "end": str(df.index.max()),
              "strategies": {name: {
                  "ending_equity_usd": float(v["ending_equity_aud"]),
                  "btc_held": float(v["btc_held"]),
                  "cash_usd": float(v.get("cash_remaining_aud", v.get("ending_cash_aud", 0))),
                  "fees_usd": float(v["fees_aud"])}
                  for name, v in results.items()}}
    folds = optimize_and_compare(df, starting_capital_aud=a.capital_usd)
    report["walk_forward"] = {"folds": int(len(folds)),
                              "beat_hold_folds": int(folds["beat_hold"].sum()),
                              "beat_dca_folds": int(folds["beat_dca"].sum()),
                              "median_excess_vs_hold_usd": float(folds["cycle_minus_hold_aud"].median())}
    out = Path(a.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, indent=2, allow_nan=False))
    print(json.dumps(report, indent=2))

if __name__ == "__main__":
    main()
