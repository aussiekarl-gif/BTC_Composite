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


def render_broker_snapshot_editor(st, portfolio):
    """Render explicit broker snapshot entry; return a validated snapshot on submit."""
    import copy

    saved = portfolio.get("broker_snapshot", {}) if isinstance(portfolio, dict) else {}
    with st.expander("Current broker holdings and deployable reserve", expanded=not bool(saved)):
        st.caption(
            "Enter the latest Stake figures. This snapshot is stored separately from "
            "historical buys/sells; it does not create or alter transactions. "
            "It is user-entered, not a live brokerage connection."
        )
        left, right = st.columns(2)
        with left:
            as_of = st.date_input(
                "Broker snapshot date",
                value=dt.date.fromisoformat(saved["as_of"]) if saved.get("as_of") else dt.date.today(),
                key="broker_snapshot_as_of",
            )
            starting = st.number_input(
                "Original starting capital (AUD)",
                min_value=1.0,
                value=float(saved.get("starting_capital_aud", portfolio.get("starting_capital_aud", 500000.0))),
                step=10000.0,
                key="broker_snapshot_starting_capital",
            )
            cash = st.number_input(
                "Stake cash available now (AUD)",
                min_value=0.0,
                value=float(saved.get("cash_aud", 0.0)),
                step=500.0,
                key="broker_snapshot_cash",
            )
        with right:
            aaa_units = st.number_input(
                "AAA units",
                min_value=0.0,
                value=float(saved.get("aaa_units", 0.0)),
                step=1.0,
                key="broker_snapshot_aaa_units",
            )
            aaa_value = st.number_input(
                "AAA market value (AUD)",
                min_value=0.0,
                value=float(saved.get("aaa_market_value_aud", 0.0)),
                step=1000.0,
                key="broker_snapshot_aaa_value",
            )
            aaa_liquidatable = st.checkbox(
                "AAA can be sold to release funds for IBIT",
                value=bool(saved.get("aaa_liquidatable", True)),
                key="broker_snapshot_aaa_liquidatable",
            )
        ibit_left, ibit_right = st.columns(2)
        with ibit_left:
            ibit_units = st.number_input(
                "IBIT units",
                min_value=0.0,
                value=float(saved.get("ibit_units", 0.0)),
                step=1.0,
                key="broker_snapshot_ibit_units",
            )
        with ibit_right:
            ibit_value = st.number_input(
                "IBIT market value (AUD)",
                min_value=0.0,
                value=float(saved.get("ibit_market_value_aud", 0.0)),
                step=1000.0,
                key="broker_snapshot_ibit_value",
            )
        if st.button("Save broker snapshot", key="save_broker_snapshot", use_container_width=True):
            candidate = {
                "as_of": as_of.isoformat(),
                "starting_capital_aud": float(starting),
                "aaa_units": float(aaa_units),
                "aaa_market_value_aud": float(aaa_value),
                "aaa_liquidatable": bool(aaa_liquidatable),
                "ibit_units": float(ibit_units),
                "ibit_market_value_aud": float(ibit_value),
                "cash_aud": float(cash),
            }
            validate_broker_snapshot(candidate, today=dt.date.today())
            return copy.deepcopy(candidate)
    return None


def merge_broker_snapshot(fresh_portfolio, snapshot):
    """Attach a validated current snapshot without touching the trade ledger."""
    import copy

    validate_broker_snapshot(snapshot)
    if not isinstance(fresh_portfolio, dict):
        raise ValueError("Persistent portfolio must be a dictionary")
    result = copy.deepcopy(fresh_portfolio)
    result.setdefault("rows", [])
    result.setdefault("sales", [])
    result["broker_snapshot"] = copy.deepcopy(snapshot)
    if not result.get("starting_capital_aud"):
        result["starting_capital_aud"] = float(snapshot["starting_capital_aud"])
    return result
