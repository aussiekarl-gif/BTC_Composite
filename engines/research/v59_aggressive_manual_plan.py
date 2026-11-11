"""Opt-in, read-only aggressive V5.9 DCA manual IBIT purchase planner.

This is not an executable broker order or a live-ntfy/Production change. It
checks exact existing portfolio ledger, recently verified broker holdings/cash,
valid last-completed V5.9 R2 sizing score, ASX market session, and cash runway.
Missing input fails closed. It never falls back to default A$500,000 holdings.
"""
from __future__ import annotations

from datetime import datetime, date, timezone, timedelta
import hashlib
import json
import math
from zoneinfo import ZoneInfo

from engines.shared.portfolio_transactions import portfolio_positions, parse_date
from engines.research.v59_dynamic_risk_policy import risk_buy_multiplier

_ASX_TZ = ZoneInfo("Australia/Sydney")
_MAX_QUOTE_AGE = timedelta(minutes=15)
_FIXED_FEE_DEFAULT_AUD = 3.00


def broker_fields_fingerprint(*, ledger: dict, cash: float, ibit_units: int,
                              ibit_ask: float, brokerage_fee: float,
                              protected_aud: float, target: date) -> str:
    payload = {
        "portfolio": ledger, "cash": cash, "ibit_units": ibit_units,
        "ibit_ask": ibit_ask, "brokerage_fee": brokerage_fee,
        "protected_aud": protected_aud, "target": target.isoformat(),
    }
    return hashlib.sha256(
        json.dumps(payload, sort_keys=True, default=str).encode("utf-8")
    ).hexdigest()


def manual_ibit_plan(*, saved_portfolio: dict, risk_snapshot: dict,
                     now_utc: datetime, verified_at_utc: datetime | None,
                     broker_cash_aud: float, broker_ibit_units: int,
                     broker_ask_aud: float, protected_cash_aud: float,
                     review_date: date, brokerage_fee_aud: float = _FIXED_FEE_DEFAULT_AUD,
                     expected_fields_hash: str | None = None) -> dict:
    """Return manual-only quantity and reasons; never modify portfolio or place order."""
    if now_utc.tzinfo is None:
        raise ValueError("now_utc must be timezone-aware")
    now = now_utc.astimezone(timezone.utc)
    blocked = []
    if not isinstance(saved_portfolio, dict) or "starting_capital_aud" not in saved_portfolio:
        return {"ready": False, "status": "NO_SAVED_REAL_LEDGER", "blockers": ["No saved real portfolio opening capital"],
                "order_sent": False}
    if not isinstance(risk_snapshot, dict):
        raise ValueError("risk_snapshot required")
    if not isinstance(review_date, date) or isinstance(review_date, datetime):
        raise ValueError("Need an explicit date for strategy review")
    if review_date <= now.date():
        blocked.append("STRATEGY_REVIEW_DATE_NOT_FUTURE")
    if verified_at_utc is None or verified_at_utc.tzinfo is None:
        blocked.append("STAKE_BROKER_FIELDS_NOT_RECENTLY_CONFIRMED")
    else:
        age = now - verified_at_utc.astimezone(timezone.utc)
        if not timedelta(0) <= age <= _MAX_QUOTE_AGE:
            blocked.append("STAKE_BROKER_FIELDS_NOT_RECENTLY_CONFIRMED")
    try:
        cash, ask, reserve, fee = (
            float(broker_cash_aud), float(broker_ask_aud),
            float(protected_cash_aud), float(brokerage_fee_aud)
        )
        if not all(math.isfinite(v) for v in (cash, ask, reserve, fee)):
            raise ValueError
        if cash < 0 or ask <= 0 or reserve < 0 or fee < 0:
            raise ValueError
        if isinstance(broker_ibit_units, bool) or int(broker_ibit_units) != broker_ibit_units or broker_ibit_units < 0:
            raise ValueError
    except (TypeError, ValueError, OverflowError):
        return {"ready": False, "status": "INVALID_BROKER_INPUT",
                "blockers": ["Broker cash, whole IBIT units, quote and fees must be finite and valid"],
                "order_sent": False}
    if not risk_snapshot.get("risk_and_fx_fresh", False):
        blocked.append("RISK_AND_AUD_FX_NOT_VERIFIED_FRESH")
    if risk_snapshot.get("risk_score_source") != "Walk-forward Power Law":
        blocked.append("RISK_IS_NOT_ACTUAL_V59_MODEL")
    if not risk_snapshot.get("risk_signal_ready", False):
        blocked.append("RISK_SIGNAL_NOT_READY")
    if not risk_snapshot.get("ready_for_live_aggressive_orders") is False:
        blocked.append("RESEARCH_SNAPSHOT_SAFETY_FLAG_INVALID")
    try:
        risk = float(risk_snapshot["r2_sizing_risk"])
        multiplier = risk_buy_multiplier(risk)
    except (KeyError, ValueError, TypeError):
        multiplier = None
        blocked.append("R2_SIZING_RISK_INVALID")
    if multiplier == 0:
        blocked.append("RISK_ABOVE_0_50_NO_BUY")
    asx_now = now.astimezone(_ASX_TZ)
    # Market session test is necessary, NOT proof of an ASX holiday/calendar.
    # The user's fresh live Stake ask quote is separately required.
    if not (asx_now.weekday() < 5 and
            (10, 0) <= (asx_now.hour, asx_now.minute) < (16, 0)):
        blocked.append("ASX_MARKET_NOT_IN_NORMAL_DAY_SESSION")
    try:
        positions = portfolio_positions(saved_portfolio)
    except (ValueError, TypeError, KeyError):
        return {"ready": False, "status": "INVALID_PORTFOLIO_LEDGER",
                "blockers": blocked + ["Recorded purchase/sale ledger cannot reconcile"],
                "order_sent": False}
    start_capital = float(positions["starting_capital_aud"])
    ledger_cash = float(positions["cash_remaining_aud"])
    if start_capital <= 0:
        blocked.append("ORIGINAL_PROGRAMME_CAPITAL_NOT_SET")
    if abs(int(broker_ibit_units) - float(positions["ibit_units"])) > 1e-9:
        blocked.append("BROKER_IBIT_UNITS_DISAGREE_WITH_SAVED_LEDGER")
    if reserve > ledger_cash:
        blocked.append("PRESERVED_CASH_EXCEEDS_LEDGER_BALANCE")
    if cash > ledger_cash + 0.01:
        # Broker can contain other funds, but they are NOT automatically part
        # of the fixed user DCA programme; the ledger cap still prevails.
        cash = min(cash, ledger_cash)
    if expected_fields_hash is None or expected_fields_hash != broker_fields_fingerprint(
        ledger=saved_portfolio, cash=float(broker_cash_aud),
        ibit_units=int(broker_ibit_units), ibit_ask=ask,
        brokerage_fee=fee, protected_aud=reserve, target=review_date):
        blocked.append("BROKER_CONFIRMATION_DOES_NOT_MATCH_CURRENT_FIELDS")
    # Do not recommend a second purchase in the same Brisbane Monday-Sunday week.
    today = asx_now.date()
    monday = today - timedelta(days=today.weekday())
    for entry in saved_portfolio.get("rows", []):
        try:
            day = parse_date(entry.get("Date"))
        except (ValueError, TypeError):
            blocked.append("UNPARSEABLE_BUY_DATE")
            continue
        if day > today:
            blocked.append("FUTURE_DATED_PORTFOLIO_BUY")
        if monday <= day <= today:
            blocked.append("BUY_ALREADY_RECORDED_THIS_WEEK")
            break

    investable = max(0.0, min(ledger_cash, cash) - reserve)
    weeks_left = max((review_date - today).days / 7.0, 1.0)
    base = investable / weeks_left
    ceiling = max(0.0, 0.05 * start_capital)
    proposed = min(investable, max(0.0, base * (multiplier or 0)), ceiling)
    units = math.floor((proposed - fee) / ask) if proposed > fee else 0
    if units <= 0:
        blocked.append("NO_AFFORDABLE_WHOLE_IBIT_SHARES_WITHIN_WEEKLY_BUDGET")
    result = {
        "ready": len(blocked) == 0,
        "status": "MANUAL_ORDER_PLAN_ONLY" if not blocked else "BLOCKED_NO_ORDER_PLAN",
        "blockers": sorted(set(blocked)),
        "r2_sizing_risk": risk if multiplier is not None else None,
        "multiplier": multiplier,
        "starting_capital_aud": start_capital,
        "ledger_cash_aud": ledger_cash,
        "stake_free_cash_aud_confirmed": broker_cash_aud,
        "cash_preserved_aud": reserve,
        "spendable_aud": investable,
        "base_weekly_aud": base,
        "weekly_cap_aud": ceiling,
        "proposed_max_spend_aud": round(proposed, 2) if not blocked else None,
        "indicative_ibit_ask_aud": ask,
        "indicative_whole_ibit_units": max(0, units) if not blocked else None,
        "indicative_order_total_inc_fee_aud": round(max(0,units) * ask + fee, 2) if not blocked else None,
        "signal_observation_utc": risk_snapshot.get("closed_risk_observation_utc"),
        "broker_quote_executable_confirmed_by_platform": False,
        "portfolio_and_broker_cash_must_remain_verified_at_order_time": True,
        "not_tax_or_personal_investment_advice": True,
        "order_sent": False,
    }
    return result
