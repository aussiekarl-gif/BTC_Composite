"""Matched research comparison of external BTC risk-band DCA ladders.

All ladders are applied to the same supplied risk series and next-observation
BTC/AUD execution prices. This does not reproduce Cowen's proprietary risk
metric, and it is not a live trading policy or an ASX:IBIT execution backtest.
"""
from __future__ import annotations

import argparse
import json
from datetime import date
from pathlib import Path

from engines.research.v59_adaptive_ceiling_backtest import load_rows
from engines.research.v59_dynamic_risk_policy import (
    BUY_POLICY_BANDS,
    replay_dynamic_dca,
)

POLICY_NOTES = {
    "v59_current": "Existing V5.9 research-only ladder.",
    "screenshot_16x": "User screenshot: 16x/8x/4x/2x/1x below 0.50; zero above.",
    "cowen_classic": "Historical Cowen-style 5x/4x/3x/2x/1x teaching example; not his private metric.",
    "cowen_2026_reported": "Secondary summary of 2026 video: 4x/3x/2x/1x below 0.30; not an authenticated official rule.",
}


def compare(rows, *, capital_aud, reserve_aud, review_date,
            fee_pct=0.003, slippage_pct=0.0, max_weekly_fraction=0.05):
    results = {}
    for name, bands in BUY_POLICY_BANDS.items():
        replay = replay_dynamic_dca(
            rows,
            capital_aud=capital_aud,
            reserve_aud=reserve_aud,
            review_date=review_date,
            fee_pct=fee_pct,
            slippage_pct=slippage_pct,
            max_weekly_fraction=max_weekly_fraction,
            buy_bands=bands,
        )
        orders = replay["orders"]
        peak = capital_aud
        worst_drawdown = 0.0
        for order in orders:
            peak = max(peak, order["equity_aud"])
            if peak > 0:
                worst_drawdown = min(
                    worst_drawdown, order["equity_aud"] / peak - 1.0
                )
        results[name] = {
            "description": POLICY_NOTES[name],
            "risk_bands": [[ceiling, multiplier] for ceiling, multiplier in bands],
            "btc_held": replay["btc_held"],
            "cash_aud": replay["cash_aud"],
            "invested_aud": capital_aud - replay["cash_aud"],
            "ending_equity_aud": replay["ending_equity_aud"],
            "worst_drawdown_pct": 100.0 * worst_drawdown,
            "weeks_with_buys": sum(o["buy_aud"] > 0 for o in orders),
            "weeks_at_weekly_cap": sum(
                o["buy_aud"] >= capital_aud * max_weekly_fraction - 1e-7
                for o in orders
            ),
            "first_buy_date": next(
                (o["date"] for o in orders if o["buy_aud"] > 0), None
            ),
            "last_buy_date": next(
                (o["date"] for o in reversed(orders) if o["buy_aud"] > 0), None
            ),
        }
    return results


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--csv", required=True, type=Path)
    parser.add_argument("--capital", required=True, type=float)
    parser.add_argument("--reserve", required=True, type=float)
    parser.add_argument("--review-date", required=True, type=date.fromisoformat)
    parser.add_argument("--fee-pct", type=float, default=0.003)
    parser.add_argument("--slippage-pct", type=float, default=0.0)
    parser.add_argument("--max-weekly-fraction", type=float, default=0.05)
    parser.add_argument("--out", type=Path)
    args = parser.parse_args()
    rows = load_rows(args.csv)
    report = {
        "status": "RESEARCH_ONLY_RISK_METRIC_NOT_EQUIVALENT",
        "risk_source": "Same supplied risk_score column for every policy",
        "execution": "Signal date strictly precedes next-observation execution date",
        "capital_aud": args.capital,
        "reserve_aud": args.reserve,
        "fee_pct": args.fee_pct,
        "slippage_pct": args.slippage_pct,
        "weekly_cap_fraction_of_initial_capital": args.max_weekly_fraction,
        "first_execution_date": rows[0]["date"].isoformat(),
        "last_execution_date": rows[-1]["date"].isoformat(),
        "observations": len(rows),
        "results": compare(
            rows,
            capital_aud=args.capital,
            reserve_aud=args.reserve,
            review_date=args.review_date,
            fee_pct=args.fee_pct,
            slippage_pct=args.slippage_pct,
            max_weekly_fraction=args.max_weekly_fraction,
        ),
        "limitations": [
            "The risk series is not Benjamin Cowen's proprietary risk metric.",
            "Cowen's metric formula is unpublished and cannot be replicated from this chart.",
            "The 2026 Cowen ladder is based on a secondary summary, not a verified official rule specification.",
            "The screenshot ladder is transcribed from the user's supplied image.",
            "Historical risk-score publication vintages and revisions require independent verification.",
            "BTC/AUD spot proxy only; no executable ASX:IBIT fills, tracking error, SMSF tax or brokerage settlement.",
            "The weekly spending cap remains in force, so large nominal multipliers can be clipped by the cap.",
            "No result from this script authorizes Production or Research live sizing changes.",
        ],
    }
    output = json.dumps(report, indent=2, allow_nan=False)
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(output + "\n", encoding="utf-8")
    print(output)


if __name__ == "__main__":
    main()
