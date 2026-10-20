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
from engines.research.cycle_trade_allocation import (
    SELL_REVIEW_DAY_WEIGHTS,calculate_allocation_signal,_prior_top_state,
)
from engines.research.cycle_trade_execution_safety import cooldown_check


MAX_STALE_DAYS = 3
MIN_ORDER_AUD = 100.


def _nonnegative_number(value):
    try:
        number=float(value)
    except (ValueError,TypeError):
        return None
    return number if math.isfinite(number) and number>=0 else None


def _top_state(market):
    """Backward-compatible alias; same causal signal used by ntfy."""
    return _prior_top_state(market)


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
            "Recorded sells must match broker holdings; the dashboard cannot place orders."
        ],
        "sell_signal":None,
        "buy_signal":None,
        "brokerage_aud":FEE_AUD,
        "quote_required_for_units":True,
        "market_signal":"UNAVAILABLE",
        "buy_pct_total_cash":0.,
        "sell_pct_total_holdings":0.,
        "trade_pct_of_portfolio_balance":0.,
        "trade_percentage_denominator":None,
        "effective_ibit_pct_held_after_rounding":None,
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
    # Compute the VERIFIED market-only WATCH before attempting to size a
    # user's optional, sometimes unavailable, saved portfolio. The original
    # shared Cycle signal is independent of account balances; if the ledger
    # is absent/malformed we must still show BUY WATCH / SELL WATCH / HOLD,
    # while keeping action HOLD and every trade quantity at zero. Never
    # promote unverified BTC/FX inputs to a current market WATCH.
    try:
        model_signal=calculate_allocation_signal(market,buy_style=buy_style)
    except (ValueError,KeyError,TypeError):
        base["why"].append("Insufficient or inconsistent completed prices for cycle allocation.")
        return base
    base.update({
        "market_signal":model_signal["signal"],
        "buy_pct_total_cash":model_signal["buy_pct_cash"],
        "sell_pct_total_holdings":model_signal["sell_pct_held"],
        "signal_reason":model_signal["reason"],
        "trade_percentage_denominator":(
            model_signal["denominator_buy"] if model_signal["signal"]=="BUY WATCH"
            else model_signal["denominator_sell"] if model_signal["signal"]=="SELL WATCH"
            else None
        ),
    })
    base.update({name: model_signal[name] for name in (
        "near_prior_90day_high","bearish_rollover_confirmed",
        "prior_90day_drawdown_pct","prior_price_over_200wma",
        "prior_sma50_declining"
    )})
    portfolio=portfolio_snapshot(saved_portfolio)
    if not portfolio.get("valid") or portfolio.get("rows",0)<1:
        base["why"].append("Saved My Portfolio purchases are missing; no balance assumed.")
        return base
    if portfolio["unpriced_or_unknown_rows"]:
        base["why"].append("Some portfolio rows lack valid BTC prices or asset types; reconcile before sizing.")
        return base
    # Saved cash already nets all purchases, fees AND executed SELL proceeds.
    # Do not wrongly reject a valid reinvestment after selling BTC or IBIT.
    base["data_ok"]=True
    base["portfolio_cash_remaining_aud"]=portfolio["cash_remaining_aud"]
    base["recorded_ibit_units_net"]=portfolio["ibit_units"]
    base["recorded_direct_btc_net"]=portfolio["direct_btc"]
    quote=_nonnegative_number(ibit_price_aud)
    if quote is not None and quote>0:
        base["quote_aud"]=quote
    else:
        base["warnings"].append("Enter a current broker ASX:IBIT unit quote to estimate tradeable whole units.")
    # Daily market observations are not daily DCA orders. A weekly tranche
    # requires no already-recorded BUY or SELL in the past seven days.
    # Still show the market WATCH percentage even when trading is blocked.
    try:
        cooldown=cooldown_check(saved_portfolio,today=today)
    except ValueError as exc:
        base["why"].append(f"Transaction date/ledger needs review: {exc}")
        return base
    base["next_dca_eligible_date"]=cooldown["next_eligible_date"]
    if already_traded_today:
        base["why"].append("Already executed a transaction for this signal; no repeat order.")
        return base
    if not cooldown["allowed"] and model_signal["signal"]!="HOLD":
        base["why"].append(cooldown["reason"])
        return base

    # An observed undervaluation overrides any potential post-top exit.
    # A below-200WMA environment is explicitly for ACCUMULATION research.
    if market["previous_close_below_200wma"]:
        base["buy_signal"]="Previous completed BTC close was below strict prior 200WMA."
        balance=(portfolio["cash_remaining_aud"] if usable_cash_aud is None
                 else _nonnegative_number(usable_cash_aud))
        if balance is None or balance>portfolio["cash_remaining_aud"]+0.01:
            base["why"].append("Available cash cannot exceed saved uninvested portfolio capital.")
            return base
        # Market-level BUY WATCH is not an actionable ETF BUY without
        # a genuine ASX:IBIT AUD quote. Avoid showing a large A$ order
        # when actual executable unit cost is unknown.
        if base["quote_aud"] is None:
            base["why"].append(
                "BTC buy watch only: no verified ASX:IBIT AUD quote. "
                "Wait for automatic refresh or enter a broker quote."
            )
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
        if abs(proposal["pct_available_cash"]-model_signal["buy_pct_cash"])>1e-6:
            base["action"]="HOLD"
            base["why"].append("DCA percentage disagreement between shared signal and execution sizing.")
            return base
        base["allocation_pct_of_available_cash"]=model_signal["buy_pct_cash"]
        base["trade_pct_of_portfolio_balance"]=model_signal["buy_pct_cash"]
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

    # Use EXACT same price-only research signal as the daily notification.
    # A seller must still confirm current broker ETF units, and tax lots.
    if model_signal["signal"]!="SELL WATCH":
        base["why"].append(
            "No eligible mature-cycle distribution day or confirmed late-top rollover; HOLD."
        )
        if int(market["halving_day"])>560:
            base["why"].append(
                "The last confirmed cycle day-500 sell date passed before this signal. No retroactive order."
            )
        return base
    pct=model_signal["sell_pct_held"]/100.
    base["sell_signal"]=model_signal["reason"]
    if model_signal.get("experimental"):
        base["warnings"].append(
            "Late-cycle rollover rule is unvalidated as a prospective SELL trigger."
        )
    units=_nonnegative_number(verified_current_ibit_units)
    if units is None or units<=0:
        base["why"].append(
            "SELL signal is informational until you confirm ACTUAL current ETF units "
            "at your broker; recorded transactions must still be confirmed against broker inventory."
        )
        return base
    if base["quote_aud"] is None:
        base["why"].append("SELL amount requires the current ASX:IBIT broker unit price.")
        return base
    if units>portfolio["ibit_units"]+0.000001:
        base["why"].append(
            "Broker-confirmed units exceed net recorded IBIT units. Reconcile BUY and SELL ledger."
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
    base["trade_pct_of_portfolio_balance"]=model_signal["sell_pct_held"]
    base["effective_ibit_pct_held_after_rounding"]=round(100*qty/units,3)
    # Informational BTC quantity if holdings include DIRECT BTC as well.
    base["direct_btc_sale_pct"]=model_signal["sell_pct_held"]
    base["direct_btc_sale_quantity_estimate"]=round(
        float(portfolio.get("direct_btc") or 0)*pct,8
    )
    base["action_aud"]=round(gross,2)
    base["suggested_ibit_units"]=qty
    base["estimated_ibit_units"]=qty
    base["estimated_net_sale_aud_before_cgt"]=round(gross-FEE_AUD,2)
    base["why"] += [
        base["sell_signal"],
        f"Research tranche is {pct:.0%} of current broker-confirmed holdings, rounded down to whole ETF units.",
        "CGT is not estimated without verified SMSF tax lots; review your actual tax basis before selling."
    ]
    return base
