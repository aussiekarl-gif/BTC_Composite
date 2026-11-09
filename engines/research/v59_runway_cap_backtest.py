"""CLI for auditable matched 1x/1.5x/2x research backtests.

Input CSV columns: date, signal_date, btc_price_aud, raw_risk_weight.
signal_date must precede execution date; this is NOT independent proof of
provider publication or vintage. Do not supply hindsight scores.
This tool does not source data or claim a production-equivalent backtest.
"""
import argparse
import csv
import json
from datetime import date
from pathlib import Path
from engines.research.v59_runway_cap_replay import replay_runway_cap


def load_rows(path):
    rows = []
    with open(path, newline="", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        required = {"date", "signal_date", "btc_price_aud", "raw_risk_weight"}
        if not required.issubset(reader.fieldnames or []):
            raise ValueError(f"Missing CSV columns: {sorted(required - set(reader.fieldnames or []))}")
        for item in reader:
            rows.append({"date": date.fromisoformat(item["date"]),
                         "signal_date": date.fromisoformat(item["signal_date"]),
                         "btc_price_aud": float(item["btc_price_aud"]),
                         "raw_risk_weight": float(item["raw_risk_weight"])})
    if not rows:
        raise ValueError("No rows in historical dataset")
    if any(row["signal_date"] >= row["date"] for row in rows):
        raise ValueError("Each signal_date must precede its execution date")
    if any(a["date"] >= b["date"] for a, b in zip(rows, rows[1:])):
        raise ValueError("Execution dates must be strictly increasing and unique")
    return rows


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--csv", type=Path, required=True)
    p.add_argument("--capital", type=float, default=500000)
    p.add_argument("--reserve", type=float, default=0)
    p.add_argument("--review-date", type=date.fromisoformat, required=True)
    p.add_argument("--fee-pct", type=float, default=0)
    p.add_argument("--slippage-pct", type=float, default=0)
    p.add_argument("--out", type=Path)
    args = p.parse_args()
    rows = load_rows(args.csv)
    report = {
        "status": "RESEARCH_ONLY_SIGNAL_CHRONOLOGY_CHECKED_PROVENANCE_UNVERIFIED",
        "input": str(args.csv),
        "first_date": rows[0]["date"].isoformat(),
        "last_date": rows[-1]["date"].isoformat(),
        "rows": len(rows),
        "note": "Prior signal dates checked, not independently source-timestamp verified; no exceptional-event override, no historical-vintage validation",
        "results": {},
    }
    for cap in (1.0, 1.5, 2.0):
        result = replay_runway_cap(rows, capital_aud=args.capital,
                                  reserve_aud=args.reserve,
                                  review_date=args.review_date,
                                  cap=cap, fee_pct=args.fee_pct,
                                  slippage_pct=args.slippage_pct)
        result.pop("orders")
        report["results"][str(cap)] = result
    output = json.dumps(report, indent=2)
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(output + "\n", encoding="utf-8")
    print(output)


if __name__ == "__main__":
    main()
