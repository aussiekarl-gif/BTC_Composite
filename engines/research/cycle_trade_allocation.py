"""Shared prior-data-only market signal and portfolio PERCENT allocations.

Used identically by Streamlit and the one daily ntfy summary.
This module is intentionally portfolio-agnostic: ntfy has no credentials
to the user's private Google Sheet and MUST NOT fabricate account sizes.

A BUY allocation applies to *available uninvested AUD cash*, not
total lifetime starting capital. SELL applies to *currently held units
of each crypto-linked asset*, subject to whole ASX:IBIT units and actual
tax lot review. Neither signal submits orders.

The 2017/2021/2025-fitted calendar and late-top hypotheses are Research
only; there is no demonstrated prospective top-detection reliability.
"""
from __future__ import annotations

import math
import pandas as pd

# These sell percentages are % of the holdings CURRENTLY REMAINING on
# each signal date, NOT % of the original starting BTC or total assets.
SELL_REVIEW_DAY_WEIGHTS = {
    500: 0.05, 525: 0.24, 532: 0.20, 539: 0.16,
    546: 0.12, 553: 0.08, 560: 0.05,
}
DEFAULT_BUY_STYLE="adaptive_recovery"
BUY_STYLES=("adaptive_recovery","adaptive_value")


def _prior_top_state(market):
    prices=market["price_history"]
    if not isinstance(prices,pd.Series) or len(prices)<120:
        raise ValueError("Need at least 120 dated BTC/USD observations")
    # Last observation is execution/asof close, exclude it strictly.
    seen=prices.iloc[:-1]
    if len(seen)<104:
        raise ValueError("Not enough prior closes")
    prev=float(seen.iloc[-1])
    high90=float(seen.iloc[-90:].max())
    sma50=float(seen.iloc[-50:].mean())
    old_sma50=float(seen.iloc[-64:-14].mean())
    wma=float(market["prior_200wma_usd"])
    if not all(math.isfinite(x) and x>0
               for x in (prev,high90,sma50,old_sma50,wma)):
        raise ValueError("Invalid BTC observation or moving averages")
    if "previous_close_usd" in market and not math.isclose(
        prev,float(market["previous_close_usd"]),rel_tol=1e-10,abs_tol=1e-8
    ):
        raise ValueError("Market previous-close data does not match historical closes")
    drawdown=max(0.,1-prev/high90)
    return {
        "near_prior_90day_high":prev>=.95*high90,
        "bearish_rollover_confirmed":(
            drawdown>=.15 and prev<sma50 and sma50<old_sma50),
        "prior_90day_drawdown_pct":round(drawdown*100,2),
        "prior_price_over_200wma":round(prev/wma,4),
        "prior_sma50_declining":sma50<old_sma50,
    }


def calculate_allocation_signal(market,*,buy_style=DEFAULT_BUY_STYLE):
    """Market-level BUY/SELL/HOLD: NO fictitious private account quantities.

    Signal percentages are returned even if the user has not yet supplied
    cash, holdings, an IBIT quote or consent to trade.
    """
    if buy_style not in BUY_STYLES:
        raise ValueError("Unknown Dynamic DCA-in style")
    data=_prior_top_state(market)
    ratio=float(data["prior_price_over_200wma"])
    eligible=float(market["previous_close_usd"]) < float(market["prior_200wma_usd"])
    if eligible != bool(market["previous_close_below_200wma"]):
        raise ValueError("Inconsistent historical 200WMA buy-gate observation")
    result={
        "signal":"HOLD",
        "buy_pct_cash":0.,
        "sell_pct_held":0.,
        "buy_style":buy_style,
        "reason":"No eligible Cycle Trading research signal.",
        "denominator_buy":"remaining available AUD cash",
        "denominator_sell":"current net BTC/IBIT holdings (per asset)",
        "rule_research_only":True,
        "requires_portfolio_confirmation":True,
        **data,
    }
    if eligible:
        fraction=(.025 if buy_style=="adaptive_recovery"
                  else .10 if ratio<=.85 else .035)
        result.update({
            "signal":"BUY WATCH",
            "buy_pct_cash":round(100*fraction,2),
            "reason":"Previous fully observed BTC close below strict prior 200WMA.",
        })
        return result

    cycle_day=int(market["halving_day"])
    if cycle_day in SELL_REVIEW_DAY_WEIGHTS and data["near_prior_90day_high"] and ratio>=1.25:
        fraction=SELL_REVIEW_DAY_WEIGHTS[cycle_day]
        result.update({
            "signal":"SELL WATCH",
            "sell_pct_held":round(100*fraction,2),
            "reason":(
                f"Halving day {cycle_day} research maturity review; prior BTC close "
                "within 5% of observed 90-day high and >=1.25×200WMA."
            ),
        })
    elif cycle_day>560 and ratio>=1.4 and data["bearish_rollover_confirmed"]:
        result.update({
            "signal":"SELL WATCH",
            "sell_pct_held":5.,
            "experimental":True,
            "reason":(
                "EXPERIMENTAL late-cycle rollover: prior BTC close >=1.4×200WMA, "
                "at least 15% below 90-day high and below declining 50DMA."
            ),
        })
    return result
