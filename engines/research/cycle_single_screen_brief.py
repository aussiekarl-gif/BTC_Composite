"""One read-only Cycle Trading briefing from EXISTING signal and saved account.

Deliberately do not calculate another BTC model signal or promote a BUY
WATCH into an order. Broker cash/quote verification must occur via the
separate existing user-consented preview; unverified headline amounts are
left blank, not populated from potentially untaxed ledger sale proceeds.

The historical day500 SELL/original-budget strategy remains distinct from
the current simplified live BUY/HOLD/SELL. No broker or notification action.
"""
from __future__ import annotations

import math

from engines.research.cycle_broker_cash_review import fifo_sales_and_inventory


def _safe_number(value):
    try:
        x=float(value)
    except (ValueError,TypeError):
        return None
    return x if math.isfinite(x) and x>=0 else None


def one_screen_cycle_brief(saved,decision,*,asof,
                           confirmed_broker_preview=None):
    """Current recorded holdings, money, tax warning and one decision line.

    A previously submitted verified preview is intentionally NEVER saved
    here; Streamlit recomputes its value on explicit form submission only.
    This function does not modify decision, portfolio or pending broker
    balances; does not call a market feed or invent future allocations.
    """
    result={
        "research_only":True,"place_order":False,
        "action":decision.get("action","HOLD"),
        "market_signal":decision.get("market_signal","UNAVAILABLE"),
        "signal_pct_cash":_safe_number(decision.get("buy_pct_total_cash")),
        "signal_pct_holdings":_safe_number(decision.get("sell_pct_total_holdings")),
        "next_eligible_review":decision.get("next_dca_eligible_date"),
        "recorded_cash_aud":None,
        "recorded_ibit_units":None,
        "recorded_direct_btc":None,
        "illustrative_realized_gains_cgt_aud":None,
        "reconciled_available_cash_aud":None,
        "confirmed_research_gross_aud":None,
        "confirmed_whole_ibit_units":None,
        "estimated_whole_unit_cost_aud":None,
        "estimated_net_after_cgt_aud":None,
        "broker_verification":False,
        "original_historical_policy_parity_verified":False,
        "status":"PORTFOLIO_UNAVAILABLE",
        "message":"Recorded executed trades are unavailable or inconsistent.",
    }
    try:
        audit=fifo_sales_and_inventory(saved,asof=asof)
    except (ValueError,KeyError,TypeError,AttributeError) as exc:
        result["message"]=(
            f"Cannot verify recorded holdings: {type(exc).__name__}: {exc}"
        )
        return result
    result.update(
        recorded_cash_aud=audit["recorded_cash_before_tax_aud"],
        recorded_ibit_units=audit["recorded_net_ibit_units"],
        recorded_direct_btc=audit["recorded_direct_btc_units"],
        illustrative_realized_gains_cgt_aud=audit[
            "gross_positive_only_tax_projection_aud"],
    )
    action=result["action"]
    if action not in ("BUY","SELL"):
        result.update(
            status="HOLD",
            message=(
                "The existing Cycle Trading decision is HOLD or unavailable. "
                "Cash confirmation must never turn HOLD into a trade."
            ),
        )
        return result
    if not confirmed_broker_preview:
        result.update(
            status="BROKER_VERIFICATION_REQUIRED",
            message=(
                "The model has a research signal, but the recorded ledger "
                "balance and delayed IBIT quote are NOT verified spendable "
                "cash or a broker execution price. Expand the broker check."
            ),
        )
        return result
    check=confirmed_broker_preview
    if (not isinstance(check,dict)
            or check.get("research_only") is not True
            or check.get("place_order") is not False
            or check.get("new_trade_authorized") is not False
            or check.get("model_action")!=action):
        result.update(
            status="BROKER_PREVIEW_MISMATCH",
            message="Broker check does not match this model decision; verify again.",
        )
        return result
    phase=check.get("phase")
    if action=="BUY" and phase=="BUY_RESEARCH_PREVIEW":
        value=_safe_number(check.get("reconciled_research_gross_aud"))
        spend=_safe_number(check.get(
            "estimated_whole_unit_spend_including_fee_aud"))
        units=check.get("reconciled_whole_ibit_units")
        cash=_safe_number(check.get("max_cash_without_reconciling_other_liabilities_aud"))
        model_limit=_safe_number(decision.get("action_aud"))
        if (value is None or spend is None or cash is None
                or model_limit is None or not isinstance(units,int)
                or units<1 or spend>value+.015 or
                value>model_limit+.015 or value>cash+.015):
            result.update(
                status="BROKER_PREVIEW_MISMATCH",
                message="Inconsistent broker amount, whole units or existing model cap.",
            )
            return result
        result.update(
            status="BUY_RESEARCH_VERIFIED",
            broker_verification=True,
            reconciled_available_cash_aud=cash,
            confirmed_research_gross_aud=value,
            confirmed_whole_ibit_units=units,
            estimated_whole_unit_cost_aud=spend,
            message=(
                "Broker cash AFTER liabilities and an IBIT unit quote were "
                "manually confirmed for this read-only review. No trade was placed."
            ),
        )
        return result
    if action=="SELL" and phase=="SELL_RESEARCH_PREVIEW":
        qty=check.get("reconciled_whole_ibit_units")
        gross=_safe_number(check.get("reconciled_research_gross_aud"))
        net=_safe_number(check.get(
            "reconciled_research_net_sale_aud_after_illustrative_tax"))
        if (not isinstance(qty,int) or qty<=0
                or qty!=decision.get("suggested_ibit_units")
                or gross is None or net is None or net>gross+.015):
            result.update(
                status="BROKER_PREVIEW_MISMATCH",
                message="Broker SELL preview does not match current confirmed units.",
            )
            return result
        result.update(
            status="SELL_RESEARCH_VERIFIED",
            broker_verification=True,
            confirmed_research_gross_aud=gross,
            confirmed_whole_ibit_units=qty,
            estimated_net_after_cgt_aud=net,
            message=(
                "User-entered broker price reconciled with the existing "
                "SELL quantity. After-CGT AUD is an illustrative accumulation-"
                "phase estimate, NOT a verified SMSF tax assessment."
            ),
        )
        return result
    if action=="BUY" and phase=="BROKER_CASH_TOO_SMALL":
        result.update(
            status="BROKER_CASH_INSUFFICIENT",
            message=(
                "Confirmed cash/IBIT quote is insufficient for the minimum "
                "whole-ETF purchase. No research order amount is available."
            ),
        )
        return result
    result.update(
        status="BROKER_VERIFICATION_REQUIRED",
        message="No current eligible broker-confirmed review; check again.",
    )
    return result
