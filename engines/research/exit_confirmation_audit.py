"""Research-only causal risk-arm + price-confirmed exit experiment.

Signals observed on week t are executed by the existing simulator at t+1.
The moving average and drawdown use data up to t ONLY. Every plan recycles
all actual sale proceeds; no Production changes. Retrospective exploratory
comparison only; prices and stored historical risks have provenance caveats.
"""
import argparse
import json

import pandas as pd

from engines.research.full_cycle_reinvestment import (
    CAPITAL, COST_PER_SIDE, matched_hold, simulate, validate_history,
)


def make_confirmed_signals(data, *, arm_risk=0.60, buy_risk=0.35,
                           drawdown_trigger=0.25, trend_weeks=20):
    """Transform historical risk into a causal BUY/HOLD/SELL instruction series.

    A high risk score arms a potential top. A sell is instructed ONLY after
    price retreats from the highest observed price since arming AND falls
    below its trailing moving average. A completed sell requires a new low
    risk reading before another high-risk arm is allowed.
    """
    history = validate_history(data)
    if not 0 <= buy_risk < arm_risk <= 1:
        raise ValueError("Risk levels must satisfy buy < arm")
    if not 0 < drawdown_trigger < 1:
        raise ValueError("Drawdown trigger must be in (0,1)")
    if not isinstance(trend_weeks, int) or isinstance(trend_weeks, bool) or trend_weeks < 2:
        raise ValueError("trend_weeks must be an integer >= 2")

    armed = False
    need_reset = False
    armed_peak = 0.0
    prices = history["btc_price_aud"]
    signals = []
    for i, (price, risk) in enumerate(zip(prices.to_numpy(),
                                          history["risk_score"].to_numpy())):
        price, risk = float(price), float(risk)
        if risk <= buy_risk:
            need_reset = False
        if not armed and not need_reset and risk >= arm_risk:
            armed = True
            armed_peak = price
        if armed:
            armed_peak = max(armed_peak, price)
            ma = float(prices.iloc[i + 1 - trend_weeks:i + 1].mean()) if i + 1 >= trend_weeks else None
            if (ma is not None and price <= armed_peak * (1 - drawdown_trigger)
                    and price < ma):
                signals.append(1.0)
                armed = False
                need_reset = True
                continue
        signals.append(0.0 if risk <= buy_risk else 0.5)
    output = history.copy()
    output["risk_score"] = signals
    return output


SCENARIOS = (
    ("plain_035_060_16weeks", None),
    ("confirmed_25pct_20wma", 0.25),
    ("confirmed_35pct_20wma", 0.35),
)


def evaluate_confirmations(data, *, initial_cash=CAPITAL, fee_rate=COST_PER_SIDE):
    """Compare predeclared alternatives, not optimised on these observations."""
    history = validate_history(data)
    if not isinstance(history.index, pd.DatetimeIndex):
        raise ValueError("Historical index must be datetime for era diagnostics")
    boundary = pd.Timestamp("2022-01-01", tz=history.index.tz)
    cohorts = (
        ("all_available", history),
        ("2016_to_2021", history[history.index < boundary]),
        ("2022_onward", history[history.index >= boundary]),
    )
    report = []
    for era, subset in cohorts:
        if len(subset) < 3:
            continue
        hold = matched_hold(subset, initial_cash=initial_cash, fee_rate=fee_rate)
        for name, trigger in SCENARIOS:
            source = subset if trigger is None else make_confirmed_signals(
                subset, drawdown_trigger=trigger)
            sim = simulate(source, buy_risk=0.35, sell_risk=0.60,
                           buy_weeks=16, sell_weeks=16,
                           initial_cash=initial_cash, fee_rate=fee_rate)
            report.append({
                "cohort": era, "scenario": name, "start": str(subset.index[0]),
                "end": str(subset.index[-1]), "observations": len(subset),
                "ending_equity_aud": round(sim["ending_equity_aud"], 2),
                "hold_equity_aud": round(hold["ending_equity_aud"], 2),
                "vs_hold": round(sim["ending_equity_aud"] / hold["ending_equity_aud"], 6),
                "sell_plans": sim["sell_plans"], "buy_plans": sim["buy_plans"],
                "cash_remaining_aud": round(sim["cash_remaining_aud"], 2),
                "btc_held": round(sim["btc_held"], 8),
                "fees_aud": round(sim["total_fees_aud"], 2),
                "drawdown_pct": round(sim["max_drawdown_pct"], 2),
                "first_five_sells": [
                    x for x in sim["plans_started"] if x["action"] == "SELL"
                ][:5],
            })
    return {
        "research_only": True,
        "fee_per_side": fee_rate, "starting_cash_aud": initial_cash,
        "records": report,
        "warnings": [
            "All scenarios exploratory and inspected in sample; no untouched holdout.",
            "2016/2022 split is a descriptive sensitivity, not out-of-sample proof.",
            "Historical risk_score point-in-time provenance remains unresolved.",
            "Uses trailing AUD-price 20-week MA, NOT a USD 200-week MA.",
            "Signals lag one observation; closing-price executions remain idealised.",
            "No taxes, market impact or cash interest; capital fully recycled.",
        ],
    }



def stress_test_latency_and_costs(data):
    """Predeclared 1/3/5-week total signal delays and 0.3%/1.0% per-side costs.

    This is an in-sample execution robustness diagnostic, NOT an optimisation.
    Each cohort restarts capital only to compare equivalent local regimes.
    """
    history = validate_history(data)
    if not isinstance(history.index, pd.DatetimeIndex):
        raise ValueError("Require dated historical observations")
    boundary = pd.Timestamp("2022-01-01", tz=history.index.tz)
    cohorts = (("all_available", history),
               ("2022_onward", history[history.index >= boundary]))
    rows = []
    for era, subset in cohorts:
        if len(subset) < 3:
            continue
        for strategy in ("plain", "confirmed_25pct"):
            source = (subset if strategy == "plain"
                      else make_confirmed_signals(subset, drawdown_trigger=0.25))
            for extra_delay in (0, 2, 4):
                signal = source.copy()
                if extra_delay:
                    signal["risk_score"] = signal["risk_score"].shift(extra_delay).fillna(0.5)
                for fee in (0.003, 0.01):
                    hold = matched_hold(subset, fee_rate=fee)
                    sim = simulate(signal, buy_risk=0.35, sell_risk=0.60,
                                   buy_weeks=16, sell_weeks=16, fee_rate=fee)
                    rows.append({
                        "cohort": era, "strategy": strategy,
                        "total_signal_delay_weeks": 1 + extra_delay,
                        "fee_per_side": fee,
                        "ending_equity_aud": round(sim["ending_equity_aud"], 2),
                        "vs_hold": round(sim["ending_equity_aud"] / hold["ending_equity_aud"], 6),
                        "buy_plans": sim["buy_plans"], "sell_plans": sim["sell_plans"],
                    })
    return rows

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", default="")
    args = parser.parse_args()
    from engines.shared.central_data import load_master
    raw = load_master(columns=["btc_price_aud", "risk_score"])
    clean = raw[["btc_price_aud", "risk_score"]].apply(pd.to_numeric, errors="coerce")
    valid = (clean["btc_price_aud"].notna()
             & clean["btc_price_aud"].gt(0)
             & clean["risk_score"].between(0, 1))
    result = evaluate_confirmations(clean.loc[valid])
    result["latency_and_cost_stress"] = stress_test_latency_and_costs(clean.loc[valid])
    result["source_valid_rows"] = int(valid.sum())
    result["source_excluded_rows"] = int((~valid).sum())
    output = json.dumps(result, indent=2, allow_nan=False)
    if args.output:
        from pathlib import Path
        Path(args.output).write_text(output + "\n", encoding="utf-8")
    print(output)


if __name__ == "__main__":
    main()
