"""Research-only comparison of fixed and adaptive weekly BTC DCA ceilings.

Input weekly CSV columns: date, btc_price_aud, risk_score.
Risk scores MUST be calculated with data available on the observation date.
No production-equivalence or predictive performance claim is implied.
"""
import argparse
import csv
import json
from datetime import date
from pathlib import Path
from engines.research.v59_dynamic_risk_policy import replay_dynamic_dca

SCENARIOS = ("fixed_5", "adaptive_7_5", "adaptive_10")


def load_rows(path):
    with open(path, newline="", encoding="utf-8-sig") as handle:
        reader = csv.DictReader(handle)
        required = {"date", "btc_price_aud", "risk_score"}
        if not required.issubset(reader.fieldnames or []):
            raise ValueError("Missing required columns: " + ", ".join(sorted(required - set(reader.fieldnames or []))))
        rows = [dict(date=date.fromisoformat(row["date"]),
                     btc_price_aud=float(row["btc_price_aud"]),
                     risk_score=float(row["risk_score"])) for row in reader]
    if not rows:
        raise ValueError("Historical dataset is empty")
    return rows


def compare(rows, *, capital_aud, reserve_aud, review_date, fee_pct=0, slippage_pct=0):
    results = {}
    for scenario in SCENARIOS:
        result = replay_dynamic_dca(
            rows, capital_aud=capital_aud, reserve_aud=reserve_aud,
            review_date=review_date, fee_pct=fee_pct, slippage_pct=slippage_pct,
            ceiling_scenario=scenario)
        orders = result["orders"]
        peak = float(capital_aud)
        drawdown = 0.0
        for order in orders:
            peak = max(peak, order["equity_aud"])
            drawdown = min(drawdown, order["equity_aud"] / peak - 1)
        results[scenario] = {
            "btc_held": result["btc_held"],
            "cash_aud": result["cash_aud"],
            "invested_aud": capital_aud - result["cash_aud"],
            "ending_equity_aud": result["ending_equity_aud"],
            "worst_drawdown_pct": drawdown * 100,
            "first_buy_date": next((o["date"] for o in orders if o["buy_aud"] > 0), None),
            "weeks_with_buys": sum(o["buy_aud"] > 0 for o in orders),
            "cash_at_reserve_date": next((o["date"] for o in orders if o["cash_aud"] <= reserve_aud + 1e-6), None),
        }
    return results


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--csv", required=True, type=Path)
    parser.add_argument("--capital", type=float, default=500000)
    parser.add_argument("--reserve", type=float, default=0)
    parser.add_argument("--review-date", required=True, type=date.fromisoformat)
    parser.add_argument("--fee-pct", type=float, default=0)
    parser.add_argument("--slippage-pct", type=float, default=0)
    parser.add_argument("--out", type=Path)
    parser.add_argument("--risk-provenance-verified", action="store_true",
                        help="Assert externally audited point-in-time publication and revision provenance")
    args = parser.parse_args()
    rows = load_rows(args.csv)
    report = {
        "status": ("RESEARCH_ONLY_USER_ATTESTED_RISK_PROVENANCE" if args.risk_provenance_verified
                   else "RESEARCH_ONLY_UNVALIDATED_HISTORICAL_RISK"),
        "source_csv": str(args.csv),
        "first_date": rows[0]["date"].isoformat(),
        "last_date": rows[-1]["date"].isoformat(),
        "observations": len(rows),
        "risk_provenance": ("USER_ATTESTED_NOT_INDEPENDENTLY_VERIFIED_BY_SCRIPT" if args.risk_provenance_verified
                            else "UNVERIFIED_DO_NOT_INTERPRET_AS_TRADABLE"),
        "weekly_ceiling_basis": "INITIAL_CAPITAL",
        "execution_lag": "NOT ENFORCED: supply pre-lagged risk_score values for execution dates",
        "results": compare(rows, capital_aud=args.capital, reserve_aud=args.reserve,
                           review_date=args.review_date, fee_pct=args.fee_pct,
                           slippage_pct=args.slippage_pct),
    }
    output = json.dumps(report, indent=2)
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(output + "\n", encoding="utf-8")
    print(output)


if __name__ == "__main__":
    main()
