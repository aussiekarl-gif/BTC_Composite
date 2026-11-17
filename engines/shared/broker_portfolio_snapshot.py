"""User-entered broker snapshot, kept separate from the executed trade ledger.

The snapshot supports current position/cash reconciliation for DCA sizing without
inventing historical trades. It is not a live brokerage connection and is valid
only for a short, explicit as-of window.
"""
from __future__ import annotations

import datetime as dt
import math

MAX_SNAPSHOT_AGE_DAYS = 7


def _positive(value, label, *, allow_zero=False):
    try:
        number = float(value)
    except (TypeError, ValueError):
        raise ValueError(f"{label} must be numeric")
    if not math.isfinite(number) or number < 0 or (not allow_zero and number <= 0):
        qualifier = "non-negative" if allow_zero else "positive"
        raise ValueError(f"{label} must be finite and {qualifier}")
    return number


def validate_broker_snapshot(snapshot, *, today=None, max_age_days=MAX_SNAPSHOT_AGE_DAYS):
    """Validate a broker-reported snapshot and return clearly separated balances.

    Required keys: as_of, starting_capital_aud, aaa_units, aaa_market_value_aud,
    ibit_units, ibit_market_value_aud, cash_aud, aaa_liquidatable.
    """
    if not isinstance(snapshot, dict):
        raise ValueError("Broker snapshot must be a dictionary")
    try:
        as_of = dt.date.fromisoformat(str(snapshot.get("as_of", "")))
    except ValueError as exc:
        raise ValueError("Broker snapshot needs an ISO as-of date") from exc
    today = today or dt.date.today()
    age_days = (today - as_of).days
    if age_days < 0:
        raise ValueError("Broker snapshot cannot be future-dated")
    if age_days > int(max_age_days):
        raise ValueError(f"Broker snapshot is stale ({age_days} days old; maximum {max_age_days})")

    starting = _positive(snapshot.get("starting_capital_aud"), "Starting capital")
    aaa_units = _positive(snapshot.get("aaa_units"), "AAA units", allow_zero=True)
    aaa_value = _positive(snapshot.get("aaa_market_value_aud"), "AAA market value", allow_zero=True)
    ibit_units = _positive(snapshot.get("ibit_units"), "IBIT units", allow_zero=True)
    ibit_value = _positive(snapshot.get("ibit_market_value_aud"), "IBIT market value", allow_zero=True)
    cash = _positive(snapshot.get("cash_aud"), "AUD cash", allow_zero=True)
    liquidatable = snapshot.get("aaa_liquidatable")
    if not isinstance(liquidatable, bool):
        raise ValueError("AAA liquidation availability must be explicitly confirmed")
    if (aaa_units == 0) != (aaa_value == 0):
        raise ValueError("AAA units and market value must both be zero or both be positive")
    if (ibit_units == 0) != (ibit_value == 0):
        raise ValueError("IBIT units and market value must both be zero or both be positive")

    aaa_reserve = aaa_value if liquidatable else 0.0
    deployable = cash + aaa_reserve
    total_value = cash + aaa_value + ibit_value
    return {
        "valid": True,
        "as_of": as_of.isoformat(),
        "age_days": age_days,
        "starting_capital_aud": round(starting, 2),
        "aaa_units": aaa_units,
        "aaa_market_value_aud": round(aaa_value, 2),
        "aaa_liquidatable": liquidatable,
        "ibit_units": ibit_units,
        "ibit_market_value_aud": round(ibit_value, 2),
        "cash_aud": round(cash, 2),
        "aaa_reserve_aud": round(aaa_reserve, 2),
        "deployable_reserve_aud": round(deployable, 2),
        "total_market_value_aud": round(total_value, 2),
        "source": "User-entered broker snapshot; not a live brokerage connection",
    }


def snapshot_as_portfolio_positions(snapshot, *, today=None):
    """Adapt a valid broker snapshot to the small interface used by DCA sizing."""
    validated = validate_broker_snapshot(snapshot, today=today)
    return {
        "valid": True,
        "starting_capital_aud": validated["starting_capital_aud"],
        "cash_remaining_aud": validated["deployable_reserve_aud"],
        "broker_cash_aud": validated["cash_aud"],
        "aaa_reserve_aud": validated["aaa_reserve_aud"],
        "ibit_units": validated["ibit_units"],
        "direct_btc": 0.0,
        "btc_equivalent_estimate": None,
        "has_sales": False,
        "number_buys": None,
        "number_sells": None,
        "broker_snapshot": validated,
        "units_source": "User-entered broker snapshot; separate from historical executed-trade ledger",
    }
