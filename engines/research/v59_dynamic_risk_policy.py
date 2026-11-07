"""Experimental risk-responsive BTC accumulation and staged selling.

Research-only. No live dashboard, production or notification integration.
Input risk is assumed point-in-time and must be independently validated.
"""
from __future__ import annotations
from datetime import date
import math

# (risk ceiling, ordinary weekly buy multiplier); upper bound inclusive.
BUY_BANDS = ((0.10, 3.0), (0.20, 2.0), (0.40, 1.5),
             (0.50, 1.0), (1.0, 0.0))
# Selling is disabled by default until independently validated.
SELL_BANDS = ((0.90, 0.02), (1.0, 0.05))


def risk_buy_multiplier(risk):
    if not math.isfinite(risk) or not 0 <= risk <= 1:
        raise ValueError("Risk must be between 0 and 1")
    return next(mult for ceiling, mult in BUY_BANDS if risk <= ceiling)


def risk_sell_fraction(risk):
    if not math.isfinite(risk) or not 0 <= risk <= 1:
        raise ValueError("Risk must be between 0 and 1")
    if risk <= 0.80:
        return 0.0
    return next((fraction for ceiling, fraction in SELL_BANDS if risk <= ceiling), 0.0)


def risk_weekly_ceiling(risk, scenario="fixed_5"):
    """Research hypotheses, not calibrated trading limits; fraction of initial capital."""
    risk_buy_multiplier(risk)  # Validate finite range.
    scenarios = {
        "fixed_5": (0.05, 0.05, 0.05, 0.05),
        "adaptive_7_5": (0.075, 0.06, 0.05, 0.05),
        "adaptive_10": (0.10, 0.075, 0.06, 0.05),
    }
    if scenario not in scenarios:
        raise ValueError("Unknown weekly ceiling scenario")
    limits = scenarios[scenario]
    return limits[0] if risk <= 0.10 else limits[1] if risk <= 0.20 else limits[2] if risk <= 0.40 else limits[3]


def replay_dynamic_dca(rows, *, capital_aud, reserve_aud, review_date,
                       fee_pct=0.0, slippage_pct=0.0, enable_selling=False,
                       sell_confirmation_weeks=2, max_weekly_fraction=0.05,\n                       ceiling_scenario=None):
    """Replay ordered weekly observations, spending only available unreserved cash.

    Selling requires consecutive high-risk weekly readings; each sell is a
    fraction of BTC holdings, not a fraction of initial capital.
    """
    if not isinstance(review_date, date) or capital_aud < 0 or not 0 <= reserve_aud <= capital_aud:
        raise ValueError("Invalid capital, reserve or review date")
    if ceiling_scenario is not None:\n        risk_weekly_ceiling(0.5, ceiling_scenario)\n    if not 0 < max_weekly_fraction <= 1:
        raise ValueError("Invalid weekly budget ceiling")
    if not 0 <= fee_pct < 1 or not 0 <= slippage_pct < 1 or sell_confirmation_weeks < 1:
        raise ValueError("Invalid costs or sell confirmation")
    cash, btc, orders = float(capital_aud), 0.0, []
    prev, high_risk_weeks = None, 0
    for row in rows:
        day, price, risk = row["date"], float(row["btc_price_aud"]), float(row["risk_score"])
        if not isinstance(day, date) or (prev is not None and day <= prev):
            raise ValueError("Dates must be strictly increasing")
        if not math.isfinite(price) or price <= 0:
            raise ValueError("Invalid BTC/AUD price")
        mult = risk_buy_multiplier(risk)
        prev = day
        weeks_left = max((review_date-day).days / 7.0, 1.0)
        high_risk_weeks = high_risk_weeks + 1 if risk > 0.80 else 0
        buy = 0.0
        sell_btc = 0.0
        if enable_selling and high_risk_weeks >= sell_confirmation_weeks:
            sell_btc = btc * risk_sell_fraction(risk)
            btc -= sell_btc
            cash += sell_btc * price * (1-slippage_pct) * (1-fee_pct)
        else:
            available = max(0.0, cash-reserve_aud)
            buy = min(available, available/weeks_left * mult, capital_aud * (risk_weekly_ceiling(risk, ceiling_scenario) if ceiling_scenario is not None else max_weekly_fraction))
            cash -= buy
            btc += buy * (1-fee_pct) / (price*(1+slippage_pct))
        orders.append(dict(date=day.isoformat(), risk_score=risk,
                           multiplier=mult, buy_aud=buy, sell_btc=sell_btc,
                           cash_aud=cash, btc_held=btc, equity_aud=cash+btc*price))
    return dict(cash_aud=cash, btc_held=btc,
                ending_equity_aud=orders[-1]["equity_aud"] if orders else capital_aud,
                orders=orders, selling_enabled=enable_selling)
