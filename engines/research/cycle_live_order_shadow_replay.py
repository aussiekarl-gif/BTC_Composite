"""Cycle Trading LIVE-rule shadow execution parity pilot (not a new strategy).

Reuse the actual Streamlit decision function on dated market snapshots, then
simulate hypothetical whole ASX:IBIT purchases/sales through the SAME portfolio
FIFO ledger. No trades are placed and no user portfolio is read/written.

No historical 2017/21 ASX:IBIT fills can exist. An explicit observed BID/ASK
(or clearly marked synthetic fixture) is needed for every quoted ASX session.
This does not grant the historical day500 backtest parity with live rules.
"""
from __future__ import annotations

import copy
import datetime as dt
import math
from dataclasses import dataclass
from typing import Sequence
from zoneinfo import ZoneInfo

import pandas as pd

from engines.research.cycle_trade_allocation import calculate_allocation_signal
from engines.research.cycle_trade_decision import make_current_decision
from engines.shared.portfolio_transactions import (
    append_executed_trade, parse_date, portfolio_positions,
)

SYDNEY = ZoneInfo("Australia/Sydney")
ASX_IBIT_INCEPTION = dt.date(2025, 11, 14)
MAX_QUOTE_LAG = dt.timedelta(minutes=15)


@dataclass(frozen=True)
class Session:
    """Caller provides a dated, pre-observed BTC market and an independent quote."""
    trading_date_sydney: dt.date
    execution_at_utc: dt.datetime
    quote_at_utc: dt.datetime
    bid_aud: float
    ask_aud: float
    market: dict
    asx_session_verified: bool
    quote_provenance: str = "synthetic_research"
    # Quotes from a broker would still NOT be actual confirmed fills.


def aware_utc(instant: dt.datetime) -> dt.datetime:
    if (not isinstance(instant, dt.datetime) or instant.tzinfo is None
            or instant.utcoffset() is None):
        raise ValueError("Timezone-aware quote/execution times required")
    return instant.astimezone(dt.timezone.utc)


def _verify_session(s: Session, prior_date: dt.date | None):
    if not isinstance(s, Session):
        raise ValueError("Explicit research Session required")
    day = s.trading_date_sydney
    if not isinstance(day, dt.date) or isinstance(day, dt.datetime):
        raise ValueError("Exact Sydney session date required")
    if day < ASX_IBIT_INCEPTION or day.weekday() >= 5 or not s.asx_session_verified:
        raise ValueError("ASX:IBIT session not verified; never invent a weekend/holiday fill")
    if prior_date is not None and day <= prior_date:
        raise ValueError("Session dates must be strictly increasing")
    executed, seen = aware_utc(s.execution_at_utc), aware_utc(s.quote_at_utc)
    if executed.astimezone(SYDNEY).date() != day or seen.astimezone(SYDNEY).date() != day:
        raise ValueError("Quote and hypothetical execution must share the ASX Sydney session")
    if seen > executed or executed-seen > MAX_QUOTE_LAG:
        raise ValueError("Missing or stale point-in-time executable quote")
    for v in (s.bid_aud, s.ask_aud):
        if not isinstance(v, (int,float)) or not math.isfinite(v) or v <= 0:
            raise ValueError("Positive finite AUD bid/ask required")
    if s.ask_aud < s.bid_aud:
        raise ValueError("Crossed ASX spread")
    if not isinstance(s.market, dict) or "price_history" not in s.market:
        raise ValueError("Explicit dated BTC market history required")
    market_date = pd.Timestamp(s.market["asof_date"])
    market_date = (market_date.tz_localize("UTC") if market_date.tzinfo is None
                   else market_date.tz_convert("UTC"))
    history = s.market["price_history"]
    if (not isinstance(history, pd.Series)
        or not isinstance(history.index, pd.DatetimeIndex)
        or history.index.tz is None or len(history)==0):
        raise ValueError("Dated BTC price history required")
    last = history.index[-1].tz_convert("UTC")
    if (history.index.has_duplicates or not history.index.is_monotonic_increasing
        or market_date.normalize() != last.normalize()
        or market_date.date() >= day
        or market_date > executed
        or s.market.get("usd_aud_prior") is None):
        raise ValueError("Future BTC close or incomplete market vintage")
    fx_date = s.market.get("fx_source_date")
    if not fx_date:
        raise ValueError("Date of prior FX rate required")
    fx = dt.date.fromisoformat(str(fx_date))
    if fx >= day or (day-fx).days > 7:
        raise ValueError("Stale or future FX price")
    if s.quote_provenance not in ("synthetic_research","archived_broker_bid_ask"):
        raise ValueError("Quote provenance must be auditable or explicit synthetic research")


def run_shadow(
    initial_portfolio: dict, sessions: Sequence[Session], *,
    tax_escrow_fraction_of_sale_proceeds: float = 0.0,
    buy_style: str = "adaptive_recovery",
) -> dict:
    """Actual LIVE rule --> whole units --> existing FIFO ledger, all simulated.

    The tax reserve is an explicitly chosen blocked portion of cash, NOT an
    SMSF CGT calculation. A zero rate means PRE-TAX and never after-tax P&L.
    """
    if (not isinstance(tax_escrow_fraction_of_sale_proceeds, (float,int))
        or not math.isfinite(tax_escrow_fraction_of_sale_proceeds)
        or not 0 <= tax_escrow_fraction_of_sale_proceeds < 1):
        raise ValueError("User-defined tax cash escrow fraction 0..1 required")
    if not sessions:
        raise ValueError("No known ASX market sessions; refuse to fabricate trades")
    if buy_style not in ("adaptive_recovery","adaptive_value"):
        raise ValueError("Unsupported shared live buy style")
    portfolio = copy.deepcopy(initial_portfolio)
    if not isinstance(portfolio, dict) or not portfolio.get("rows"):
        raise ValueError("Explicit starting portfolio with dated original executed lots required")
    opening = portfolio_positions(portfolio)
    first = sessions[0].trading_date_sydney
    for entry in list(portfolio.get("rows", [])) + list(portfolio.get("sales", [])):
        if parse_date(entry["Date"]) >= first:
            raise ValueError("Starting lots must precede the shadow evaluation")
    if opening["missing_exposure_lots"]:
        raise ValueError("Starting ETF exposure unknown; synthetic starting lots require BTC AUD reference")
    rows=[]
    escrow=0.0
    previous=None
    last_bid=None
    for session in sessions:
        _verify_session(session,previous)
        previous = session.trading_date_sydney
        last_bid = session.bid_aud
        balance = portfolio_positions(portfolio)
        spendable = max(0.0, round(balance["cash_remaining_aud"]-escrow,2))
        market_vote=calculate_allocation_signal(session.market,buy_style=buy_style)
        # Real market WATCH is the only upstream signal. BID for sell and ASK
        # for buy; cannot use a favourable mid-price as a synthetic fill.
        candidate_price=(session.ask_aud if market_vote["signal"]=="BUY WATCH"
                         else session.bid_aud)
        decision=make_current_decision(
            session.market,portfolio,today=session.trading_date_sydney,
            usable_cash_aud=spendable,buy_style=buy_style,
            ibit_price_aud=candidate_price,
            verified_current_ibit_units=balance["ibit_units"],
            feed_verified=True,
        )
        if decision["market_signal"] != market_vote["signal"]:
            raise AssertionError("Streamlit sizing and market signal disagree")
        action=decision["action"]
        qty=int(decision["suggested_ibit_units"])
        if action in ("BUY","SELL"):
            if qty <= 0:
                raise AssertionError("Non-positive simulated trade quantity")
            price=session.ask_aud if action=="BUY" else session.bid_aud
            gross=round(qty*price,2)
            if action=="BUY" and gross+float(decision["brokerage_aud"])>spendable+0.01:
                raise AssertionError("Live quantity exceeds cash net of escrow")
            if action=="SELL" and qty>balance["ibit_units"]:
                raise AssertionError("Live quantity exceeds recorded net inventory")
            portfolio, after=append_executed_trade(
                portfolio,side=action,asset="ASX:IBIT",
                trade_date=session.trading_date_sydney,quantity=qty,
                trade_price_aud=price,fee_aud=float(decision["brokerage_aud"]),
                btc_aud_price=(session.market["btc_price_aud_estimate"]
                               if action=="BUY" else None),
                note=f"SHADOW_NOT_REAL_{session.trading_date_sydney}_{action}",
            )
            if action=="SELL":
                escrow += gross*tax_escrow_fraction_of_sale_proceeds
            # Taxes are NOT charged from ledger, merely escrowed from spendable cash.
            if after["cash_remaining_aud"]+0.005 < escrow:
                raise AssertionError("Tax escrow exceeds net cash")
        after=portfolio_positions(portfolio)
        rows.append({
            "session_sydney":session.trading_date_sydney.isoformat(),
            "market_asof_date_utc":str(session.market["asof_date"]),
            "market_signal":market_vote["signal"],
            "shared_live_rule_action":action,
            "hypothetical_ibit_units_executed":qty if action in ("BUY","SELL") else 0,
            "hypothetical_ibit_unit_price_aud":(
                round(session.ask_aud if action=="BUY" else session.bid_aud,6)
                if action in ("BUY","SELL") else None),
            "quote_provenance":session.quote_provenance,
            "hypothetical_net_ibit_units":int(after["ibit_units"]),
            "cash_before_tax_aud":after["cash_remaining_aud"],
            "tax_cash_escrow_aud":round(escrow,2),
            "free_cash_after_escrow_aud":round(max(0.,after["cash_remaining_aud"]-escrow),2),
            "execution_not_real":True,
        })
    ending=portfolio_positions(portfolio)
    return {
        "status":"LIVE_RULES_SHADOW_REPLAY_NOT_AN_EXECUTION",
        "policy":"unchanged_cycle_market_signal_plus_current_Streamlit_make_current_decision",
        "historical_day500_backtest_parity_verified":False,
        "actual_ASX_IBIT_broker_fills_verified":False,
        "tax_liability_calculated":False,
        "tax_cash_escrow_not_CGT":round(escrow,2),
        "gross_before_tax_mark_to_bid_aud":round(
            ending["cash_remaining_aud"]+ending["ibit_units"]*last_bid,2),
        "free_cash_after_escrow_aud":round(
            max(0.,ending["cash_remaining_aud"]-escrow),2),
        "remaining_ibit_whole_units":int(ending["ibit_units"]),
        "total_recorded_synthetic_execution_fees_aud":ending["fees_aud"],
        "new_actual_orders":0,
        "new_notifications":0,
        "portfolio_writes":0,
        "sessions":rows,
    }
