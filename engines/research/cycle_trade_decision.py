"""Research-only single current BUY/HOLD/SELL decision, never an order.

Pure read-only adapter. It does NOT automatically operate on SMSF assets.
- BUY: observed strictly PRIOR daily BTC/USD close below 200-week MA,
  using the already-researched value/recovery sizing for user cash.
- SELL: predeclared cycle maturity review dates from known halving only
  if price is strong; OR a separately labeled EXPERIMENTAL post-window
  late-top breakdown safeguard. No historic 2025 backdated trade.
- HOLD: no rule, insufficient confidence, insufficient cash or inventory,
  already executed day, unverified portfolio, stale price/FX, missing quote.

Broker ASX:IBIT units MUST be priced using a user-entered executable AUD
quote, not Bitcoin/USD, model-implied BTC-equivalent or an invented ETF
conversion. CGT is NOT guessed without lot-level tax history.
Existing My Portfolio supports buy entries, NOT sale tracking: verified
current broker units and manual "already traded" safeguard required to
propose a SELL quantity; no persistent order ledger or execution exists.
"""
from __future__ import annotations

import math
from datetime import date

import pandas as pd

from engines.research.cycle_trading_dashboard_model import (
    FEE_AUD, planned_buy_order,
    portfolio_snapshot,
)


SELL_REVIEW_DAY_WEIGHTS = {
    500: 0.05, 525: 0.24, 532: 0.20, 539: 0.16,
    546: 0.12, 553: 0.08, 560: 0.05,
}
# 5% on day500 + 85% in 525..560, remainder outside fixed
# schedule retained for independently confirmed conditions.
MAX_STALE_DAYS = 3
MIN_ORDER_AUD = 100.


def _nonnegative_number(value):
    try:
        number=float(value)
    except (ValueError,TypeError):
        return None
    return number if math.isfinite(number) and number>=0 else None


def _top_state(market):
    """Strictly completed previous closes for all momentum inputs."""
    history=market["price_history"]
    if not isinstance(history,pd.Series) or len(history)<120:
        raise ValueError("Insufficient completed trend history")
    # Current market asof close is NEVER used to determine today's action.
    completed=history.iloc[:-1]
    if len(completed)<104:
        raise ValueError("Insufficient prior price history")
    prev=float(completed.iloc[-1])
    high90=float(completed.iloc[-90:].max())
    recent50=float(completed.iloc[-50:].mean())
    old50=float(completed.iloc[-64:-14].mean())
    ma200=float(market["prior_200wma_usd"])
    if min(prev,high90,recent50,old50,ma200)<=0:
        raise ValueError("Invalid market price history")
    drawdown=max(0.,1-prev/high90)
    near_high=(prev>=.95*high90)
    breakdown=(drawdown>=.15 and prev<recent50 and recent50<old50)
    return {
        "near_prior_90day_high":near_high,
        "bearish_rollover_confirmed":breakdown,
        "prior_90day_drawdown_pct":round(drawdown*100,2),
        "prior_price_over_200wma":round(prev/ma200,4),
        "prior_sma50_declining":bool(recent50<old50),
    }


def make_current_decision(
    market, saved_portfolio, *,
    today, usable_cash_aud=None,
    buy_style="adaptive_recovery",
    ibit_price_aud=None,
    verified_current_ibit_units=None,
    already_traded_today=False,
    feed_verified=True,
):
    """Compute an explainable candidate; HOLD is the safe default.

    Values are research suggestions, NEVER automatic trades.
    The "SELL" state requires user confirmation of current broker unit
    balance because saved My Portfolio contains only PURCHASE entries.
    No model uses today/current market close for action selection; all
    rolling price conditions use previous completed daily close.
    """
    base={
        "action":"HOLD","action_aud":0.,"estimated_ibit_units":None,
        "suggested_ibit_units":0,"btc_equivalent_estimate":None,
        "quote_aud":None,
        "research_only":True,"place_order":False,
        "data_ok":False,"why":[],"warnings":[
            "Research illustration only; not an executable broker order.",
            "Actual SMSF CGT depends on fund phase, parcel purchase dates and cost bases.",
            "This dashboard does not save or reconcile completed SALE orders."
        ],
        "sell_signal":None,
        "buy_signal":None,
        "brokerage_aud":FEE_AUD,
        "quote_required_for_units":True,
    }
    try:
        day=pd.Timestamp(today)
        last=pd.Timestamp(market["asof_date"])
    except (TypeError,KeyError,ValueError) as e:
        base["why"].append(f"Missing reliable observation date: {type(e).__name__}")
        return base
    if day.tzinfo is not None:
        day=day.tz_convert("UTC").tz_localize(None)
    if last.tzinfo is not None:
        last=last.tz_convert("UTC").tz_localize(None)
    age=(day.normalize()-last.normalize()).days
    base["signal_age_days"]=age
    if not feed_verified:
        base["why"].append("BTC/USD provider overlap could not be verified; no transaction proposed.")
        return base
    if age<0 or age>MAX_STALE_DAYS:
        base["why"].append(f"Signal is {age} days old; needs a verified current price refresh.")
        return base
    if (market.get("usd_aud_prior") is None or
            _nonnegative_number(market.get("usd_aud_prior")) in (None,0)):
        base["why"].append("No validated preceding USD/AUD exchange rate.")
        return base
    portfolio=portfolio_snapshot(saved_portfolio)
    if not portfolio.get("valid") or portfolio.get("rows",0)<1:
        base["why"].append("Saved My Portfolio purchases are missing; no balance assumed.")
        return base
    if portfolio["unpriced_or_unknown_rows"]:
        base["why"].append("Some portfolio rows lack valid BTC prices or asset types; reconcile before sizing.")
        return base
    if portfolio["spent_aud"]+portfolio["fees_aud"]>portfolio["capital_aud"]+0.01:
        base["why"].append("Recorded purchases exceed starting capital; cash needs reconciliation.")
        return base
    base["data_ok"]=True
    base["portfolio_cash_remaining_aud"]=portfolio["cash_remaining_aud"]
    base["recorded_ibit_units_purchases_only"]=portfolio["ibit_units"]
    quote=_nonnegative_number(ibit_price_aud)
    if quote is not None and quote>0:
        base["quote_aud"]=quote
    else:
        base["warnings"].append("Enter a current broker ASX:IBIT unit quote to estimate tradeable whole units.")
    if already_traded_today:
        base["why"].append("You marked this signal date as already traded; no duplicate transaction.")
        return base
    try:
        top=_top_state(market)
    except (ValueError,KeyError):
        base["why"].append("Insufficient prior completed prices for sell-top confirmation.")
        return base
    base.update(top)

    # An observed undervaluation overrides any potential post-top exit.
    # A below-200WMA environment is explicitly for ACCUMULATION research.
    if market["previous_close_below_200wma"]:
        base["buy_signal"]="Previous completed BTC close was below strict prior 200WMA."
        balance=(portfolio["cash_remaining_aud"] if usable_cash_aud is None
                 else _nonnegative_number(usable_cash_aud))
        if balance is None or balance>portfolio["cash_remaining_aud"]+0.01:
            base["why"].append("Available cash cannot exceed saved uninvested portfolio capital.")
            return base
        proposal=planned_buy_order(market,cash_available=balance,
                                   style=buy_style)
        if proposal["action"]!="ILLUSTRATIVE BUY":
            base["why"].append(proposal["reason"])
            return base
        amount=min(balance,proposal["amount_aud"])
        if amount<MIN_ORDER_AUD+FEE_AUD:
            base["why"].append("Cash allocation too small after AUD 3 fee.")
            return base
        base["action"]="BUY"
        base["action_aud"]=round(amount,2)
        base["btc_equivalent_estimate"]=proposal["btc_equivalent_estimate"]
        base["allocation_pct_of_available_cash"]=proposal["pct_available_cash"]
        base["why"] += [
            base["buy_signal"],
            f"{buy_style}: allocate {proposal['pct_available_cash']}% of available AUD cash.",
            "Bitcoin price-based signal, not an ASX:IBIT purchase quote."
        ]
        if base["quote_aud"] is not None:
            n=int(math.floor((amount-FEE_AUD)/quote+1e-10))
            base["suggested_ibit_units"]=max(0,n)
            base["estimated_ibit_units"]=max(0,n)
            base["estimated_gross_ibit_aud"]=round(n*quote+FEE_AUD,2)
            if n<1:
                base["action"]="HOLD"
                base["action_aud"]=0.
                base["why"].append("The amount is insufficient for one whole ETF unit at the entered price.")
        return base

    # After 200WMA recovery there is no trustworthy persisted active-
    # buyback trade state; do NOT pretend today's session knows whether
    # previous rebuy orders were already executed.
    elapsed=int(market["halving_day"])
    near=top["near_prior_90day_high"]
    ratio=top["prior_price_over_200wma"]
    rollover=top["bearish_rollover_confirmed"]
    if elapsed in SELL_REVIEW_DAY_WEIGHTS and near and ratio>=1.25:
        pct=SELL_REVIEW_DAY_WEIGHTS[elapsed]
        base["sell_signal"]=(
            f"Halving day {elapsed} scheduled distribution review; "
            "prior BTC close near its 90-day high and above 1.25×200WMA."
        )
    elif elapsed>560 and ratio>=1.40 and rollover:
        pct=.05
        base["sell_signal"]=(
            "EXPERIMENTAL late-cycle price rollover: previous close >1.4×200WMA, "
            "15% below prior 90-day high and below a declining 50-day average."
        )
        base["warnings"].append(
            "Late-cycle rollover rule is unvalidated as a prospective SELL trigger."
        )
    else:
        base["why"].append(
            "No eligible mature-cycle distribution day or confirmed late-top rollover; HOLD."
        )
        if elapsed>560:
            base["why"].append(
                "The 2024-halving day-500 sell date passed before your actual 2026 deployment."
            )
        return base

    units=_nonnegative_number(verified_current_ibit_units)
    if units is None or units<=0:
        base["why"].append(
            "SELL signal is informational until you confirm ACTUAL current ETF units "
            "at your broker; purchase-only portfolio cannot prove unsold inventory."
        )
        return base
    if base["quote_aud"] is None:
        base["why"].append("SELL amount requires the current ASX:IBIT broker unit price.")
        return base
    if units>portfolio["ibit_units"]+0.000001:
        base["why"].append(
            "Verified units exceed saved purchased units. Reconcile portfolio before sell sizing."
        )
        return base
    qty=int(math.floor(units*pct+1e-9))
    if qty<=0:
        base["why"].append("Position too small for a one-unit staged sale; no order proposed.")
        return base
    gross=qty*quote
    if gross<FEE_AUD+MIN_ORDER_AUD:
        base["why"].append("Sell consideration too small relative to minimum transaction.")
        return base
    base["action"]="SELL"
    base["action_aud"]=round(gross,2)
    base["suggested_ibit_units"]=qty
    base["estimated_ibit_units"]=qty
    base["estimated_net_sale_aud_before_cgt"]=round(gross-FEE_AUD,2)
    base["why"] += [
        base["sell_signal"],
        f"Research tranche is {pct:.0%} of broker-confirmed holdings, rounded down to whole ETF units.",
        "CGT is not estimated without verified SMSF tax lots; review your actual tax basis before selling."
    ]
    return base
