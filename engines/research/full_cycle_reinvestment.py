"""Research-only full-cycle capital recycling audit (NOT trading advice or live code).

Unlike independent 55-week holdout probes, one account persists across the entire
history. Recovered AUD from sells can purchase BTC in later cycles. All signal
decisions use the PREVIOUS observation's risk score; the current price is only
used to execute an already known instruction. Plans execute one equal tranche
per observation for 1, 12, or 16 observations, even if the signal later reverses.

This is an ex-post diagnostic, NOT out-of-sample validation. The central master
risk_score's point-in-time provenance is not independently established; fees
approximate spread/slippage and tax, market impact, and cash yield are excluded.
No modifications to Production, portfolio, or the authoritative data master.
"""
import argparse
import json
import math

import numpy as np
import pandas as pd

CAPITAL = 500_000.0
COST_PER_SIDE = 0.003

# Predeclared diagnostics; the best full-history performer must NOT be treated
# as an approved parameter choice or used to claim out-of-sample performance.
SCENARIOS = (
    ("immediate_025_075", .25, .75, 1, 1),
    ("staged_12_12_025_075", .25, .75, 12, 12),
    ("staged_16_16_025_075", .25, .75, 16, 16),
    ("staged_12_12_025_070", .25, .70, 12, 12),
    ("staged_16_16_035_060", .35, .60, 16, 16),
    ("staged_12_16_025_075", .25, .75, 12, 16),
    ("staged_16_12_025_075", .25, .75, 16, 12),
)


def validate_history(data):
    """Require explicit, complete price/risk pairs; do not silently alter dates."""
    if not isinstance(data, pd.DataFrame):
        raise TypeError("History must be a DataFrame")
    if not {"btc_price_aud", "risk_score"}.issubset(data.columns):
        raise ValueError("History needs btc_price_aud and risk_score")
    if data.index.has_duplicates:
        raise ValueError("Duplicate dates are not allowed")
    if len(data) < 3:
        raise ValueError("Need at least three sequential observations")
    result = data[["btc_price_aud", "risk_score"]].copy().sort_index()
    for column in result:
        result[column] = pd.to_numeric(result[column], errors="coerce")
    if (not np.isfinite(result["btc_price_aud"].to_numpy()).all()
            or not (result["btc_price_aud"] > 0).all()
            or not np.isfinite(result["risk_score"].to_numpy()).all()
            or not result["risk_score"].between(0, 1).all()):
        raise ValueError("Invalid price or risk; investigate source, do not fill")
    return result


def simulate(data, *, buy_risk=.25, sell_risk=.75,
             buy_weeks=12, sell_weeks=12,
             initial_cash=CAPITAL, fee_rate=COST_PER_SIDE):
    """Simulate a *single* account with full proceeds retained for future cycles.

    At week t a new buy/sell plan may start using only the t-1 risk score.
    The plan commits the cash or BTC then available and trades equal gross
    tranches for N consecutive observations. This makes timing meaningful but
    can sell too early, buy too late, or trade through a reversal.
    Terminal equity includes remaining cash and marked-to-market BTC; no forced
    liquidation or terminal sale fee is imposed.
    """
    history = validate_history(data)
    if not (0 <= buy_risk < sell_risk <= 1):
        raise ValueError("Require 0 <= buy_risk < sell_risk <= 1")
    if any(not isinstance(w, int) or isinstance(w, bool) or w < 1
           for w in (buy_weeks, sell_weeks)):
        raise ValueError("Windows must be positive integer observations")
    if not math.isfinite(initial_cash) or initial_cash <= 0:
        raise ValueError("Initial cash must be positive")
    if not math.isfinite(fee_rate) or not 0 <= fee_rate < 1:
        raise ValueError("Cost per side must be between 0 and 1")

    cash, btc, total_fees = float(initial_cash), 0.0, 0.0
    peak = initial_cash
    worst_drawdown = 0.0
    plan = None
    records = []
    plans_started = []
    for i in range(1, len(history)):
        timestamp = history.index[i]
        price = float(history["btc_price_aud"].iloc[i])
        prior_risk = float(history["risk_score"].iloc[i - 1])
        # Guard against repeated microscopic purchases after fully deploying.
        if not plan and cash > 1.0 and prior_risk <= buy_risk:
            plan = {"side": "BUY", "remaining": buy_weeks,
                    "gross_unit": cash / buy_weeks}
            plans_started.append({"date": str(timestamp), "action": "BUY",
                                  "prior_risk": prior_risk, "price_aud": price})
        elif not plan and btc > 1e-10 and prior_risk >= sell_risk:
            plan = {"side": "SELL", "remaining": sell_weeks,
                    "btc_unit": btc / sell_weeks}
            plans_started.append({"date": str(timestamp), "action": "SELL",
                                  "prior_risk": prior_risk, "price_aud": price})

        action, fee = "HOLD", 0.0
        if plan:
            action = plan["side"]
            if action == "BUY":
                gross = min(cash, plan["gross_unit"])
                fee = gross * fee_rate
                btc += (gross - fee) / price
                cash = max(0.0, cash - gross)
            else:
                amount = min(btc, plan["btc_unit"])
                gross = amount * price
                fee = gross * fee_rate
                cash += gross - fee
                btc = max(0.0, btc - amount)
            total_fees += fee
            plan["remaining"] -= 1
            if plan["remaining"] == 0:
                plan = None

        equity = cash + btc * price
        peak = max(peak, equity)
        worst_drawdown = min(worst_drawdown, equity / peak - 1.0)
        records.append({"date": str(timestamp), "action": action,
                        "prior_risk": prior_risk, "price_aud": price,
                        "btc_held": btc, "cash_aud": cash,
                        "equity_aud": equity, "fee_aud": fee})

    final = records[-1]
    return {
        "ending_equity_aud": final["equity_aud"],
        "cash_remaining_aud": cash,
        "btc_held": btc,
        "total_fees_aud": total_fees,
        "max_drawdown_pct": worst_drawdown * 100,
        "trade_observations": sum(x["action"] != "HOLD" for x in records),
        "buy_plans": sum(x["action"] == "BUY" for x in plans_started),
        "sell_plans": sum(x["action"] == "SELL" for x in plans_started),
        "plans_started": plans_started,
        "incomplete_terminal_plan": plan is not None,
        "equity_path": records,
    }


def matched_hold(data, *, initial_cash=CAPITAL, fee_rate=COST_PER_SIDE):
    """Benchmark buys at the first tradable t=1, never at inaccessible t=0."""
    history = validate_history(data)
    bitcoin = initial_cash * (1 - fee_rate) / history["btc_price_aud"].iloc[1]
    return {"ending_equity_aud":
            float(bitcoin * history["btc_price_aud"].iloc[-1]),
            "btc_held": float(bitcoin), "entry_date": str(history.index[1])}


def evaluate(data, *, initial_cash=CAPITAL, fee_rate=COST_PER_SIDE):
    history = validate_history(data)
    hold = matched_hold(history, initial_cash=initial_cash, fee_rate=fee_rate)
    results = []
    for name, buy, sell, buy_w, sell_w in SCENARIOS:
        simulation = simulate(
            history, buy_risk=buy, sell_risk=sell,
            buy_weeks=buy_w, sell_weeks=sell_w,
            initial_cash=initial_cash, fee_rate=fee_rate)
        # Deliberately exclude full weekly equity series from the JSON artifact.
        results.append({
            "name": name, "buy_risk": buy, "sell_risk": sell,
            "buy_window_observations": buy_w,
            "sell_window_observations": sell_w,
            "vs_matched_hold": simulation["ending_equity_aud"]
                              / hold["ending_equity_aud"],
            **{k: v for k, v in simulation.items() if k != "equity_path"}
        })
    gaps = history.index.to_series().diff().dropna()
    return {
        "research_only": True, "observations": len(history),
        "start": str(history.index[0]), "end": str(history.index[-1]),
        "maximum_gap_days": float(gaps.max().total_seconds() / 86400)
                            if len(gaps) else None,
        "capital_aud": initial_cash, "cost_per_side": fee_rate,
        "benchmark": hold, "scenarios": results,
        "warnings": [
            "In-sample diagnostic: scenario ranking cannot justify parameter promotion.",
            "Point-in-time provenance of reconstructed historical risk_score is unverified.",
            "Each buy/sell plan commits equal tranches for N observations; not a 200WMA trigger model.",
            "Costs are a simple proportional proxy; no taxes, market impact, or cash interest.",
            "Risk signal is lagged one observation; the exact execution price is still idealised.",
            "One account and all sale proceeds are carried continuously across the entire history.",
        ],
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", default="", help="Optional path to write JSON results")
    args = parser.parse_args()
    from engines.shared.central_data import load_master
    source = load_master(columns=["btc_price_aud", "risk_score"])
    numeric = source[["btc_price_aud", "risk_score"]].apply(
        pd.to_numeric, errors="coerce")
    valid = (np.isfinite(numeric["btc_price_aud"])
             & (numeric["btc_price_aud"] > 0)
             & np.isfinite(numeric["risk_score"])
             & numeric["risk_score"].between(0, 1))
    report = evaluate(numeric.loc[valid])
    report["central_master_total_rows"] = len(source)
    report["excluded_incomplete_or_invalid_pairs"] = int((~valid).sum())
    output = json.dumps(report, indent=2, allow_nan=False)
    if args.output:
        from pathlib import Path
        Path(args.output).write_text(output + "\n", encoding="utf-8")
    print(output)


if __name__ == "__main__":
    main()
