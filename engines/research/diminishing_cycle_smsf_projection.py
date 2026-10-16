"""RESEARCH ONLY: illustrative diminishing BTC cycles with imperfect execution.

This is a non-predictive, ex-post peak/trough *price-error* counterfactual,
NOT a causal strategy: true future peaks and bottoms are unknowable.
Normalises 2026 reference BTC/AUD price to 100, then applies scenario
bull-cycle multiples and peak-to-bottom drawdowns. No external data used.

CGT approximation: 10% on net realised AUD gains at each sale assuming
eligible >12 month SMSF accumulation-phase holdings, with loss carryforward.
Tax is paid immediately on each sale; no annual payment timing or distributions,
pension exemptions, transfer balance limitations, fund overheads, ETF spreads,
slippage, or inflation included. Fee is AUD 3 PER ORDER, not 0.3%.
A synthetic 16-week staggered leg is represented at one reference price; timing
inside those weeks is not modelled. Future results are scenarios, NOT forecasts.
"""
from __future__ import annotations

import argparse
import json
import math

SCENARIOS = {
    # Three sequential 4-year cycles, with diminishing bull multiples and
    # declining peak-to-bottom drawdowns; year ~2038 at third bottom.
    "conservative": {"bull_multiples": [3.0, 2.5, 2.0],
                     "drawdowns": [0.60, 0.45, 0.30]},
    "middle": {"bull_multiples": [4.0, 3.0, 2.5],
               "drawdowns": [0.70, 0.60, 0.45]},
    "strong": {"bull_multiples": [5.0, 4.0, 3.0],
               "drawdowns": [0.75, 0.65, 0.55]},
}


def model(scenario, *, capital_aud=500_000.0, entry_price_index=100.0,
          top_error=0.40, bottom_error=0.40, fee_per_order_aud=3.0,
          orders_per_leg=16, cgt_rate=0.10):
    """Cycle-out/cycle-in hypothetical after-tax account, matched held BTC.

    Within each hypothetical year-pair, sells at (1-top_error)*true peak;
    rebuys at (1+bottom_error)*true cycle low. This requires future extrema
    and is NOT implementable from these assumptions alone.
    """
    if not (math.isfinite(capital_aud) and capital_aud > 0):
        raise ValueError("Invalid capital")
    if not (math.isfinite(entry_price_index) and entry_price_index > 0):
        raise ValueError("Invalid reference price")
    if not (0 <= top_error < 1 and 0 <= bottom_error < 1 and 0 <= cgt_rate < 1):
        raise ValueError("Invalid timing error or CGT rate")
    if not (math.isfinite(fee_per_order_aud) and fee_per_order_aud >= 0
            and isinstance(orders_per_leg, int) and orders_per_leg >= 1):
        raise ValueError("Invalid order fees")
    factors = scenario["bull_multiples"]
    draws = scenario["drawdowns"]
    if not factors or len(factors) != len(draws):
        raise ValueError("Mismatched scenarios")
    if any(not math.isfinite(x) or x <= 1 for x in factors):
        raise ValueError("Bull multiples must exceed one")
    if any(not math.isfinite(x) or not 0 < x < 1 for x in draws):
        raise ValueError("Invalid drawdowns")

    leg_fees = fee_per_order_aud * orders_per_leg
    if capital_aud <= leg_fees:
        raise ValueError("Initial brokerage exceeds capital")
    btc = (capital_aud - leg_fees) / entry_price_index
    hold_btc = btc
    cost_basis_aud = capital_aud  # Initial buy cost INCLUDING brokerage
    loss_carry_aud = 0.0
    total_tax_aud = 0.0
    total_fees_aud = leg_fees
    price = entry_price_index
    cycles = []
    for i, (factor, draw) in enumerate(zip(factors, draws), 1):
        peak = price * factor
        trough = peak * (1 - draw)
        sale_price = peak * (1 - top_error)
        repurchase_price = trough * (1 + bottom_error)

        gross_sale = btc * sale_price
        net_sale = gross_sale - leg_fees
        if net_sale <= 0:
            raise ValueError("Sale brokerage exceeds proceeds")
        profit = net_sale - cost_basis_aud
        taxable_gain = max(0.0, profit - loss_carry_aud)
        loss_carry_aud = max(0.0, loss_carry_aud - profit)
        tax_aud = cgt_rate * taxable_gain
        after_tax_cash = net_sale - tax_aud
        if after_tax_cash <= leg_fees:
            raise ValueError("Insufficient repurchase cash after tax")
        next_btc = (after_tax_cash - leg_fees) / repurchase_price
        cycles.append({
            "cycle": i,
            "bull_multiple_from_prior_trough": factor,
            "peak_drawdown": draw,
            "peak_price_index": peak,
            "trough_price_index": trough,
            "sale_price_index": sale_price,
            "reentry_price_index": repurchase_price,
            "cgt_paid_aud": round(tax_aud, 2),
            "btc_before": round(btc, 6),
            "btc_after": round(next_btc, 6),
            "btc_multiplier": round(next_btc / btc, 6),
        })
        btc = next_btc
        cost_basis_aud = after_tax_cash
        total_tax_aud += tax_aud
        total_fees_aud += 2 * leg_fees
        price = trough
    result = {
        "research_only": True,
        "scenario": scenario,
        "start_capital_aud": capital_aud,
        "relative_reference_price": entry_price_index,
        "fee_per_order_aud": fee_per_order_aud,
        "orders_per_leg": orders_per_leg,
        "top_error": top_error,
        "bottom_error": bottom_error,
        "assumed_eligible_smsf_cgt_rate": cgt_rate,
        "end_price_index": round(price, 6),
        "total_orders": orders_per_leg * (1 + 2 * len(cycles)),
        "total_brokerage_aud": round(total_fees_aud, 2),
        "total_realised_cgt_paid_aud": round(total_tax_aud, 2),
        "end_traded_btc_index_units": round(btc, 6),
        "end_held_btc_index_units": round(hold_btc, 6),
        "trading_terminal_value_aud": round(btc * price, 2),
        "hold_terminal_value_aud": round(hold_btc * price, 2),
        "trading_vs_hold_pct": round(100 * (btc / hold_btc - 1), 4),
        "cycles": cycles,
    }
    return result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", default="")
    args = parser.parse_args()
    report = {
        "projection_is_hypothetical_not_forecast": True,
        "horizon": "2026–2038 approximately, three illustrative cycles",
        "warnings": [
            "Exact future peaks/troughs are unknowable; model uses hindsight-defined prices.",
            "Reference spot BTC/AUD of 100 is NORMALISED, not a current price quote.",
            "All sales assumed eligible for 10% SMSF CGT and reinvest after immediate tax.",
            "No ETF tracking fees, bid-ask spread, FX uncertainty, fund overhead or cash return.",
            "16 orders per leg at the same synthetic price, not real 16-week execution.",
            "Terminal assets are marked to market at the third hypothetical cycle bottom.",
            "Not a live trading recommendation or out-of-sample strategy backtest.",
        ],
        "scenarios": {name: model(case) for name, case in SCENARIOS.items()},
    }
    payload = json.dumps(report, indent=2)
    if args.output:
        from pathlib import Path
        Path(args.output).write_text(payload + "\n", encoding="utf-8")
    print(payload)


if __name__ == "__main__":
    main()
