"""Research-only matched replay of V5.9 ordinary runway caps.

Consumes point-in-time weekly rows with date, btc_price_aud and raw_risk_weight.
Does NOT calculate risk, simulate exceptional events, or change live allocations.
"""
from __future__ import annotations
from datetime import date
import math


def replay_runway_cap(rows, *, capital_aud, reserve_aud, review_date,
                      cap, fee_pct=0.0, slippage_pct=0.0):
    if cap <= 0 or capital_aud < 0 or not 0 <= reserve_aud <= capital_aud:
        raise ValueError("Invalid capital, reserve, or cap")
    if fee_pct < 0 or slippage_pct < 0 or fee_pct + slippage_pct >= 1:
        raise ValueError("Invalid costs")
    if not isinstance(review_date, date):
        raise TypeError("review_date must be a date")
    cash, btc, fees, orders = float(capital_aud), 0.0, 0.0, []
    peak_equity, worst_drawdown = float(capital_aud), 0.0
    prev = None
    for row in rows:
        day, price = row["date"], float(row["btc_price_aud"])
        risk_weight = float(row["raw_risk_weight"])
        if not isinstance(day, date) or (prev is not None and day <= prev):
            raise ValueError("Rows must have strictly increasing dates")
        if not math.isfinite(price) or price <= 0 or not math.isfinite(risk_weight):
            raise ValueError("Invalid price or risk weight")
        prev = day
        weeks_remaining = max((review_date - day).days / 7.0, 1.0)
        deployable = max(0.0, cash - reserve_aud)
        base = deployable / weeks_remaining
        multiplier = min(max(0.0, risk_weight), cap)
        spend = min(deployable, base * multiplier)
        fee = spend * fee_pct
        net = spend - fee
        btc_bought = net / (price * (1.0 + slippage_pct))
        cash -= spend
        btc += btc_bought
        fees += fee
        equity = cash + btc * price
        peak_equity = max(peak_equity, equity)
        worst_drawdown = min(worst_drawdown, equity / peak_equity - 1.0) if peak_equity else 0.0
        orders.append(dict(date=day.isoformat(), price_aud=price,
                           raw_multiplier=risk_weight, effective_multiplier=multiplier,
                           spend_aud=spend, cash_aud=cash, btc_held=btc,
                           equity_aud=equity))
    final_price = float(rows[-1]["btc_price_aud"]) if rows else float("nan")
    return dict(cap=cap, btc_held=btc, cash_aud=cash,
                invested_aud=capital_aud-cash, fees_aud=fees,
                ending_equity_aud=(cash+btc*final_price) if rows else capital_aud,
                worst_drawdown_pct=100*worst_drawdown,
                orders=orders,
                exhausted_date=next((r["date"] for r in orders if r["cash_aud"] <= reserve_aud + 1e-6), None),
                note="Ordinary sizing only; exceptional bottom events excluded")
