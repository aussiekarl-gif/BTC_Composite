"""Research only: realised BTC DCA execution errors versus ex-post local extrema.

Scores existing causal-plan simulations with an ex-post +/-52 weekly observation
oracle around each plan's BTC-quantity-weighted execution midpoint. Future
prices are used for *measurement only*, NEVER for a trading instruction.

The lookback/lookahead window is fixed before inspecting the output. This
score is not a guarantee of the unknown 'true' market cycle top or bottom.
Incomplete plans and oracle windows cut by the available dataset are reported
but excluded from success-rate denominators. Stored master historical risk
provenance still requires point-in-time verification.
"""
import argparse
import json
import math

import numpy as np
import pandas as pd

from engines.research.full_cycle_reinvestment import (
    CAPITAL, simulate, validate_history,
)
from engines.research.exit_confirmation_audit import make_confirmed_signals

THRESHOLDS = (0.15, 0.25, 0.35)
ORACLE_RADIUS = 52
# Fixed research hypotheses, NOT trained or selected on the dataset.
CASES = (
    ("simple_12", "simple", 12),
    ("simple_16", "simple", 16),
    ("confirmed_12", "confirmed", 12),
    ("confirmed_16", "confirmed", 16),
)


def _numeric(x):
    return float(round(x, 6))


def score_execution_plans(prices_and_risks, simulation, *,
                          buy_weeks, sell_weeks, oracle_radius=ORACLE_RADIUS,
                          initial_cash=CAPITAL):
    """AUD-price execution-quality scores for all historical buy/sell plans.

    An oracle peak for SELL or oracle low for BUY is measured in a symmetric
    ex-post interval around the *quantity-weighted execution midpoint*.
    No future information enters action generation. The BTC-weighted VWAP
    excludes trading fees; fees are accounted separately by the simulator.
    """
    history = validate_history(prices_and_risks)
    if not isinstance(history.index, pd.DatetimeIndex):
        raise ValueError("DatetimeIndex required")
    if not isinstance(oracle_radius, int) or oracle_radius < 1:
        raise ValueError("oracle_radius must be a positive integer")
    if len(simulation["equity_path"]) != len(history) - 1:
        raise ValueError("Simulator length does not match history")
    paths = simulation["equity_path"]
    starts = simulation["plans_started"]
    positions = {str(stamp): i for i, stamp in enumerate(history.index)}
    prices = history["btc_price_aud"].to_numpy(dtype=float)
    out = []
    for number, plan in enumerate(starts):
        start = positions.get(plan["date"])
        if start is None or start < 1:
            raise ValueError("Plan start not found in indexed history")
        side = plan["action"]
        if side not in ("BUY", "SELL"):
            raise ValueError("Unexpected plan action")
        weeks = buy_weeks if side == "BUY" else sell_weeks
        last_pos_exclusive = min(len(history), start + weeks)
        quantities, quote_notionals, indices, fees = [], [], [], 0.0
        for idx in range(start, last_pos_exclusive):
            row = paths[idx - 1]
            if row["action"] != side:
                raise ValueError("Unexpected action within an execution plan")
            prev_btc = 0.0 if idx == 1 else float(paths[idx-2]["btc_held"])
            now_btc = float(row["btc_held"])
            qty = (now_btc - prev_btc) if side == "BUY" else (prev_btc - now_btc)
            if qty < -1e-7:
                raise ValueError("Negative traded quantity")
            if qty <= 1e-12:
                continue
            indices.append(idx)
            quantities.append(qty)
            quote_notionals.append(qty * prices[idx])
            fees += float(row["fee_aud"])

        total_qty = sum(quantities)
        if total_qty <= 0:
            continue
        vwap = sum(quote_notionals) / total_qty
        mean_pos = sum(i * q for i, q in zip(indices, quantities)) / total_qty
        center = int(round(mean_pos))
        left, right = center - oracle_radius, center + oracle_radius
        complete_plan = (last_pos_exclusive - start) == weeks
        full_oracle = left >= 0 and right < len(history)
        left, right = max(0, left), min(len(history) - 1, right)
        segment = prices[left:right+1]
        extremum_offset = int(np.argmax(segment) if side == "SELL"
                              else np.argmin(segment))
        ext_pos = left + extremum_offset
        extreme = float(prices[ext_pos])
        error = (1 - vwap / extreme if side == "SELL"
                 else vwap / extreme - 1)
        # No trade price can be outside extrema when the whole plan lies
        # inside the 105-week scoring range; flag inconsistent inputs.
        if error < -1e-8:
            raise ValueError("Execution outside reference extrema window")
        valid = complete_plan and full_oracle
        out.append({
            "plan": number + 1, "side": side,
            "start": str(history.index[start]),
            "end": str(history.index[last_pos_exclusive-1]),
            "weighted_mid": str(history.index[center]),
            "orders": len(quantities),
            "complete_plan": complete_plan,
            "full_105week_window": full_oracle,
            "eligible": valid,
            "quantity_btc": _numeric(total_qty),
            "aud_notional": round(sum(quote_notionals), 2),
            "execution_vwap_aud": round(vwap, 2),
            "oracle_extreme_aud": round(extreme, 2),
            "oracle_date": str(history.index[ext_pos]),
            "error_pct": round(max(0.0, 100*error), 4),
            "simulated_fee_aud": round(fees, 2),
        })
    return out


def summarize(scored):
    eligible = [x for x in scored if x["eligible"]]
    result = {
        "plans_total": len(scored),
        "plans_scorable": len(eligible),
        "plans_censored_or_incomplete": len(scored)-len(eligible),
        "by_side": {},
        "completed_sell_then_rebuy_pairs": {},
    }
    for side in ("BUY", "SELL"):
        obs = [x for x in eligible if x["side"] == side]
        result["by_side"][side] = {
            "n": len(obs),
            "mean_error_pct": round(sum(x["error_pct"] for x in obs)/len(obs), 3) if obs else None,
            "median_error_pct": round(float(np.median([x["error_pct"] for x in obs])), 3) if obs else None,
            "max_error_pct": max((x["error_pct"] for x in obs), default=None),
            "within_threshold_counts": {
                str(round(100*t)): sum(x["error_pct"] <= 100*t for x in obs)
                for t in THRESHOLDS
            },
        }
    # Each SELL pairs to the immediately following BUY only; don't cherry-pick.
    pairs = []
    for n, row in enumerate(scored[:-1]):
        following = scored[n+1]
        if row["side"] == "SELL" and following["side"] == "BUY" and (
            row["eligible"] and following["eligible"]
        ):
            pairs.append((row, following))
    result["completed_sell_then_rebuy_pairs"] = {
        "n": len(pairs),
        "both_within_threshold_counts": {
            str(round(100*t)): sum(
                sell["error_pct"] <= 100*t and buy["error_pct"] <= 100*t
                for sell, buy in pairs)
            for t in THRESHOLDS
        },
    }
    return result


def run_audit(data, *, fee_rate=0.003, oracle_radius=ORACLE_RADIUS):
    history = validate_history(data)
    output = []
    for name, variant, weeks in CASES:
        source = (history if variant == "simple"
                  else make_confirmed_signals(history, drawdown_trigger=0.25))
        sim = simulate(source, buy_risk=0.35, sell_risk=0.60,
                       buy_weeks=weeks, sell_weeks=weeks, fee_rate=fee_rate)
        scored = score_execution_plans(
            history, sim, buy_weeks=weeks, sell_weeks=weeks,
            oracle_radius=oracle_radius)
        output.append({
            "candidate": name, "weeks": weeks,
            "fee_proxy_per_side": fee_rate,
            "ending_equity_aud": round(sim["ending_equity_aud"], 2),
            "summary": summarize(scored),
            "plans": scored,
        })
    return {
        "research_only": True,
        "sample_start": str(history.index[0]),
        "sample_end": str(history.index[-1]),
        "observations": len(history),
        "oracle_half_width_observations": oracle_radius,
        "target_mean_price_errors": {"buy_pct": 25, "sell_pct": 25},
        "candidates": output,
        "warnings": [
            "Hindsight extrema are for AUDIT ONLY, not trading decisions.",
            "The local +/-52 week oracle is NOT necessarily the actual cycle peak or low.",
            "Observed prices are weekly closes and fees use an older 0.3% proxy.",
            "Small numbers of independent cycles; do not treat win rates as probabilities.",
            "Both-legs score pairs a SELL with its immediately subsequent BUY.",
            "Plans lacking a complete 105-week oracle window are excluded from rates.",
            "Historical stored risk_score causality/provenance remains unresolved.",
            "No SMSF CGT, spreads, ETF tracking costs or point-in-time data revisions.",
            "These candidate configurations have already been studied in-sample.",
        ],
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", default="")
    args = parser.parse_args()
    from engines.shared.central_data import load_master
    raw = load_master(columns=["btc_price_aud", "risk_score"])
    columns = raw[["btc_price_aud", "risk_score"]].apply(
        pd.to_numeric, errors="coerce")
    valid = (np.isfinite(columns["btc_price_aud"])
             & columns["btc_price_aud"].gt(0)
             & np.isfinite(columns["risk_score"])
             & columns["risk_score"].between(0, 1))
    report = run_audit(columns.loc[valid])
    report["source_rows"] = len(columns)
    report["valid_rows"] = int(valid.sum())
    text = json.dumps(report, indent=2, allow_nan=False)
    if args.output:
        from pathlib import Path
        Path(args.output).write_text(text + "\n", encoding="utf-8")
    print(text)


if __name__ == "__main__":
    main()
