"""Research only: isolate the value of dynamic order SIZING (not entry timing).

For every actual variable-duration DCA leg from the existing causal engine,
construct an *equal-notional counterfactual on the EXACT SAME trade dates*:
  - BUY: same total gross AUD outlay, same number of A$3 orders,
    equally divided cash between those executed weeks.
  - SELL: same number of A$3 orders and same total BTC disposed,
    divided equally between those executed weeks.

The resulting VWAP comparison therefore measures only order weighting,
not different market signals, exposure or timing of the leg. It is NOT
a second fully funded portfolio: independently equalising every leg
does not preserve cashflows and Bitcoin balances across cycles.

Hindsight high/low references used for scoring ONLY, never orders.
Historical risk_score point-in-time provenance remains unverified.
"""
import argparse
import json
import math

import numpy as np
import pandas as pd

from engines.research.adaptive_dca_execution import (
    audit_error_rates, group_trade_legs, simulate_adaptive,
)
from engines.research.full_cycle_reinvestment import (
    CAPITAL, validate_history,
)

FEE_AUD = 3.0
CONFIRMATION = .10
ERROR_LEVELS = (15, 20, 25, 35)


def split_trade_legs(trades):
    groups = []
    for item in trades:
        if not groups or groups[-1][0]["side"] != item["side"]:
            groups.append([])
        groups[-1].append(item)
    return groups


def equal_weight_same_dates(trades, *, fee_aud=FEE_AUD):
    """Equal AUD buy or equal BTC sell on each actual traded date.

    Trade direction and number of transactions never change. Capital is
    normalized within each leg: **not** a self-financing portfolio replay.
    """
    if not trades or len({t["side"] for t in trades}) != 1:
        raise ValueError("Exactly one single-direction leg required")
    if fee_aud < 0 or not math.isfinite(fee_aud):
        raise ValueError("Invalid flat fee")
    prices = [float(t["executed_price_aud"]) for t in trades]
    if any(not math.isfinite(p) or p <= 0 for p in prices):
        raise ValueError("Invalid execution price")
    n = len(trades)
    side = trades[0]["side"]
    if side == "BUY":
        total_gross_aud = sum(float(t["gross_notional_aud"]) for t in trades)
        per_order = total_gross_aud / n
        if per_order <= fee_aud:
            raise ValueError("Equal cash order too small to cover fee")
        qty = sum((per_order - fee_aud) / p for p in prices)
        gross_cash = total_gross_aud
        equal_vwap = gross_cash / qty  # fee charged through purchased BTC
    elif side == "SELL":
        total_btc = sum(float(t["btc_quantity"]) for t in trades)
        if total_btc <= 0:
            raise ValueError("No BTC sold")
        per_order = total_btc / n
        equal_vwap = sum(per_order*p for p in prices)/total_btc - n*fee_aud/total_btc
        gross_cash = sum(per_order*p for p in prices)
        qty = total_btc
        if equal_vwap <= 0:
            raise ValueError("Fees exceed sale receipts")
    else:
        raise ValueError("Unknown direction")
    return {
        "side":side,
        "start":trades[0]["date"],
        "end":trades[-1]["date"],
        "orders":n,
        "btc_quantity":qty,
        "gross_notional_aud":gross_cash,
        "fees_aud":n*fee_aud,
        "net_effective_price_aud":equal_vwap,
    }


def compare_one_leg(dynamic, equal):
    if dynamic["side"] != equal["side"] or dynamic["start"] != equal["start"]:
        raise ValueError("Mismatch in execution dates")
    d = dynamic["net_effective_price_aud"]
    e = equal["net_effective_price_aud"]
    if d <= 0 or e <= 0:
        raise ValueError("Invalid VWAP")
    side = dynamic["side"]
    # Positive = more BTC for the same AUD if BUY, more proceeds for
    # the same BTC if SELL. No future reference price required.
    pct = (e/d-1)*100 if side == "BUY" else (d/e-1)*100
    return {
        "side":side, "start":dynamic["start"],"end":dynamic["end"],
        "orders":dynamic["orders"],
        "total_gross_aud":round(dynamic["gross_notional_aud"],2),
        "dynamic_price_aud":round(d,2),
        "equal_price_aud":round(e,2),
        "dynamic_advantage_pct":round(pct,4),
        "dynamic_improves":bool(pct > 1e-9),
    }


def evaluate(data, *, confirm_drawdown=CONFIRMATION, fee_aud=FEE_AUD):
    if fee_aud != FEE_AUD:
        raise ValueError("Current trade engine assumes A$3 per filled order")
    history = validate_history(data)
    res = simulate_adaptive(history,confirm_drawdown=confirm_drawdown,
                            fee_aud=fee_aud)
    groups = split_trade_legs(res["trades"])
    dynam_legs = group_trade_legs(res["trades"])
    equal_legs = [equal_weight_same_dates(g,fee_aud=fee_aud) for g in groups]
    if len(dynam_legs) != len(equal_legs):
        raise AssertionError("Leg count mismatch")
    comparison = [compare_one_leg(d,e) for d,e in zip(dynam_legs,equal_legs)]
    # Use *identical* ex-post future window references for both sets of
    # execution prices. Do not optimize thresholds after the fact.
    scored_dynamic = audit_error_rates(history,dynam_legs)
    scored_equal = audit_error_rates(history,equal_legs)
    if len(scored_dynamic["pairs"]) != len(scored_equal["pairs"]):
        raise AssertionError("Same-dates scored pairs mismatch")
    pairs = []
    for d,e in zip(scored_dynamic["pairs"],scored_equal["pairs"]):
        if (d["sell_start"]!=e["sell_start"] or
                d["buy_start"]!=e["buy_start"] or
                d["eligible"]!=e["eligible"] or
                d["oracle_high_date"]!=e["oracle_high_date"] or
                d["oracle_low_date"]!=e["oracle_low_date"]):
            raise AssertionError("Mismatched historical oracle dates")
        out = {
            "sell_start":d["sell_start"],
            "buy_start":d["buy_start"],
            "eligible":d["eligible"],
            "dynamic_sell_error_pct":d["sell_error_pct"],
            "equal_sell_error_pct":e["sell_error_pct"],
            "dynamic_buy_error_pct":d["buy_error_pct"],
            "equal_buy_error_pct":e["buy_error_pct"],
        }
        for target in ERROR_LEVELS:
            tag=str(target)
            out["dynamic_both_within_"+tag+"pct"] = bool(
                d["eligible"] and d["sell_error_pct"]<=target and
                d["buy_error_pct"]<=target)
            out["equal_both_within_"+tag+"pct"] = bool(
                e["eligible"] and e["sell_error_pct"]<=target and
                e["buy_error_pct"]<=target)
        pairs.append(out)
    eligible=[p for p in pairs if p["eligible"]]
    summary = {}
    for side in ("BUY","SELL"):
        legs = [c for c in comparison if c["side"]==side]
        summary[side] = {
            "n":len(legs),
            "dynamic_better_legs":sum(x["dynamic_improves"] for x in legs),
            "median_dynamic_advantage_pct":round(float(np.median(
                [x["dynamic_advantage_pct"] for x in legs])),3) if legs else None,
            "mean_dynamic_advantage_pct":round(float(np.mean(
                [x["dynamic_advantage_pct"] for x in legs])),3) if legs else None,
        }
    accuracy={}
    for target in ERROR_LEVELS:
        tag=str(target)
        accuracy[tag+"pct"]={
            "eligible_pairs":len(eligible),
            "dynamic_both":sum(p["dynamic_both_within_"+tag+"pct"] for p in eligible),
            "equal_both":sum(p["equal_both_within_"+tag+"pct"] for p in eligible),
            "dynamic_better":sum(
                p["dynamic_both_within_"+tag+"pct"] and not
                p["equal_both_within_"+tag+"pct"] for p in eligible),
            "equal_better":sum(
                p["equal_both_within_"+tag+"pct"] and not
                p["dynamic_both_within_"+tag+"pct"] for p in eligible),
        }
    return {
        "research_only":True,
        "start":str(history.index[0]),"end":str(history.index[-1]),
        "observations":len(history),
        "target_levels_pct":list(ERROR_LEVELS),
        "exit_confirmation_pct":confirm_drawdown*100,
        "flat_order_fee_aud":fee_aud,
        "original_adaptive_terminal_equity_before_cgt_aud":
            round(res["ending_equity_aud"],2),
        "original_adaptive_filled_orders":res["trade_count"],
        "weighting_by_leg":comparison,
        "weighted_vs_equal_leg_summary":summary,
        "paired_accuracy":accuracy,
        "paired_detail":pairs,
        "warnings":[
            "This is a NORMALIZED same-trade-date VWAP test, not a second capital-reinvested equity backtest.",
            "Buy equal weights use same total AUD, sell equal weights use same BTC.",
            "Independent equal weights per leg do not propagate counterfactual cash and BTC.",
            "Both schemes pay exactly A$3 per executed order.",
            "Hindsight extrema enter scoring only, never live position sizing.",
            "Weekly price/risk are archived; historical risk point-in-time provenance is unverified.",
            "15/20/25/35% score targets are measurements, not training or risk constraints.",
            "No SMSF CGT, ETF fees, spreads, or after-tax portfolio comparison.",
        ],
    }


def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--output", default="")
    args=ap.parse_args()
    from engines.shared.central_data import load_master
    raw=load_master(columns=["btc_price_aud","risk_score"])
    frame=raw[["btc_price_aud","risk_score"]].apply(pd.to_numeric,errors="coerce")
    mask=np.isfinite(frame["btc_price_aud"])&frame["btc_price_aud"].gt(0)&frame["risk_score"].between(0,1)
    report=evaluate(frame.loc[mask])
    report["source_valid_rows"]=int(mask.sum())
    text=json.dumps(report,indent=2,allow_nan=False,
                    default=lambda x:x.item() if isinstance(x,np.generic) else str(x))
    if args.output:
        from pathlib import Path
        Path(args.output).write_text(text+"\n",encoding="utf-8")
    print(text)


if __name__=="__main__":
    main()
