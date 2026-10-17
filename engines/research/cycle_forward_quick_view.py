"""Read-only, fail-closed forward summary for the ORIGINAL BTC cycle model.

This is presentation of ALREADY EXISTING research policies, not another
strategy. An original-position SELL needs holdings actually recorded before
the day500 review. The 200WMA recovery BUY programme needs an actual
original-position sale, historical 200WMA trigger and reconciled after-tax
cash; future weekly fractions CANNOT be known before their prior BTC close.

The separate simplified daily 2.5%-cash/remaining-unit LIVE market watch is
clearly identified as not historically backtest-parity verified.
No new trade, broker call, ntfy or Google Sheets write occurs here.
"""
from __future__ import annotations

import pandas as pd

from engines.shared.portfolio_transactions import portfolio_positions
from engines.research.cycle_position_anchor import original_cycle_inventory
from engines.research.cycle_account_shadow import shadow_original_btc_exit
from engines.research.cycle_real_sale_budget import original_sale_cash_reconciliation
from engines.research.cycle_weekly_buyback_audit import weekly_original_buyback_ledger
from engines.research.shared_cycle_policy import (
    START_DAY, REVIEW_DAY, cycle_exit_stage_status, exit_review_days,
)


def _utc_day(raw):
    day=pd.Timestamp(raw)
    if pd.isna(day):
        raise ValueError("Dated BTC/halving reference is required")
    day=day.tz_localize("UTC") if day.tzinfo is None else day.tz_convert("UTC")
    return day.normalize()


def cycle_forward_quick_view(market, saved, simplified_decision, *, feed_verified):
    """Summarise recorded eligibility and next *observable* research review.

    A date from a confirmed halving is a scheduled REVIEW only.
    200WMA future triggers and FUTURE halving dates are NEVER fabricated.
    Any portfolio/market inconsistency remains an explicit unverified status.
    """
    seen=_utc_day(market["asof_date"])
    halving=_utc_day(market["halving_date"])
    if seen<halving:
        raise ValueError("Confirmed BTC halving is newer than observed price")
    elapsed=(seen-halving).days
    signal=simplified_decision.get("market_signal","UNAVAILABLE")
    if not feed_verified:
        signal="UNAVAILABLE"
    pct_buy=(float(simplified_decision.get("buy_pct_total_cash",0) or 0)
             if signal!="UNAVAILABLE" else None)
    pct_sell=(float(simplified_decision.get("sell_pct_total_holdings",0) or 0)
              if signal!="UNAVAILABLE" else None)
    result={
        "research_only":True,
        "place_order":False,
        "historical_to_live_parity_verified":False,
        "market_observation_date":str(seen.date()),
        "halving_date":str(halving.date()),
        "halving_day":elapsed,
        "feed_verified":bool(feed_verified),
        "simplified_market_signal":signal,
        "simplified_buy_pct_remaining_cash":pct_buy,
        "simplified_sell_pct_remaining_holdings":pct_sell,
        "simplified_action":(
            simplified_decision.get("action","HOLD") if feed_verified else "HOLD"),
        "simplified_action_aud":(
            float(simplified_decision.get("action_aud",0) or 0) if feed_verified else 0.),
        "recorded_available_cash_before_tax_aud":None,
        "recorded_ibit_units":None,
        "recorded_direct_btc":None,
        "original_position_ibit_units":None,
        "original_position_btc":None,
        "recorded_original_sale_cash_before_cgt_aud":None,
        "verified_aftertax_original_buyback_budget_aud":None,
        "original_position_eligible":False,
        "original_phase":"PORTFOLIO_UNAVAILABLE",
        "original_next_review_date":None,
        "original_next_review_label":"Unavailable until portfolio is reconciled",
        "original_next_pct_original_holdings":None,
        "original_next_pct_original_budget":None,
        "last_completed_recovery_review_date":None,
        "last_completed_recovery_pct_original_budget":None,
        "original_readiness":"Recorded holdings could not be verified.",
        "original_blocker":"Recorded portfolio missing or inconsistent.",
    }
    if not isinstance(saved,dict):
        return result
    try:
        positions=portfolio_positions(saved)
    except (ValueError,TypeError,KeyError) as exc:
        result["original_blocker"]="Portfolio ledger cannot be reconciled: "+str(exc)
        return result
    result.update(
        recorded_available_cash_before_tax_aud=float(positions["cash_remaining_aud"]),
        recorded_ibit_units=float(positions["ibit_units"]),
        recorded_direct_btc=float(positions["direct_btc"]),
    )
    if elapsed<START_DAY:
        proposed=halving+pd.Timedelta(days=START_DAY)
        result.update(
            original_phase="BEFORE_ORIGINAL_EXIT_WINDOW",
            original_next_review_date=str(proposed.date()),
            original_next_review_label="Day500 original-position SELL review (not a guaranteed sale)",
            original_readiness="Original inventory is frozen only when day500 arrives.",
            original_blocker="Future SELL percentage depends on the previous completed BTC close.",
        )
        return result

    try:
        inventory=original_cycle_inventory(saved,halving,asof=seen)
    except (ValueError,TypeError,KeyError) as exc:
        result["original_blocker"]="Original day500 holdings unavailable: "+str(exc)
        return result
    eligible=bool(inventory["eligible"])
    result.update(
        original_position_eligible=eligible,
        original_position_ibit_units=float(inventory["original_holdings"]["ASX:IBIT"]),
        original_position_btc=float(inventory["original_holdings"]["Direct BTC"]),
    )
    if not eligible:
        result.update(
            original_phase="NO_PRE_DAY500_HOLDINGS",
            original_next_review_label="Future halving +500 days, after that halving is confirmed",
            original_readiness="No recorded BTC/IBIT held before this cycle's day500.",
            original_blocker=(
                "The previous cycle's SELL is not available to positions bought later. "
                "No historical sale proceeds or BUY budget can be attributed to them."
            ),
        )
        return result

    if elapsed<=REVIEW_DAY:
        next_stage=cycle_exit_stage_status(halving,seen)
        result.update(
            original_phase="ORIGINAL_SELL_REVIEWS",
            original_next_review_label="Original-position SELL review; prior-close conditions required",
            original_next_review_date=next_stage["next_exit_review_date"],
            original_readiness="Original holdings recorded; broker units and CGT must still be checked.",
            original_blocker="Future SELL quantity and percentage cannot be computed until its review.",
        )
        if not feed_verified or elapsed not in exit_review_days():
            return result
        history=market.get("price_history")
        if history is None:
            result["original_blocker"]="BTC reference prices unavailable for dated review."
            return result
        # Only show an ORIGINAL-position review percentage on the actual
        # review date, and only when the source is verified.
        try:
            per_asset=[
                shadow_original_btc_exit(history,halving,saved,asof=seen,asset=a)
                for a in ("ASX:IBIT","Direct BTC")
            ]
        except (ValueError,TypeError,KeyError):
            result["original_blocker"]="Original SELL review cannot be reconciled."
            return result
        if per_asset[0]["action"]=="SELL REVIEW" or per_asset[1]["action"]=="SELL REVIEW":
            result["original_next_pct_original_holdings"]=float(
                per_asset[0]["pct_original"] or per_asset[1]["pct_original"])
            result["original_blocker"]=(
                "Research SELL review only: confirm original units, SMSF tax and broker fills."
            )
        return result

    result.update(
        original_phase="AFTER_ORIGINAL_EXIT_WINDOW",
        original_next_review_label="No further day500–730 SELL reviews in this confirmed cycle",
        original_readiness="Original SELL window has ended; future sales cannot be backdated.",
        original_blocker="Reconciled actual original-position sales and after-tax cash required.",
    )
    try:
        proceeds=original_sale_cash_reconciliation(saved,halving,asof=seen)
    except (ValueError,TypeError,KeyError) as exc:
        result["original_blocker"]="Sale ledger unavailable: "+str(exc)
        return result
    amount=float(proceeds["original_net_sale_proceeds_before_cgt_aud"])
    result["recorded_original_sale_cash_before_cgt_aud"]=amount
    if amount<=0.0:
        result["original_phase"]="NO_ORIGINAL_SALE_PROCEEDS"
        result["original_next_review_label"]="No personal historical BUY programme without actual original sales"
        return result
    if not feed_verified:
        result["original_phase"]="ORIGINAL_SALE_CASH_UNVERIFIED_FEED"
        result["original_blocker"]="Market/feed stale or unverified; past weekly dates not actionable."
        return result
    try:
        weekly=weekly_original_buyback_ledger(
            market["price_history"],halving,saved,asof=seen)
    except (ValueError,TypeError,KeyError,AssertionError) as exc:
        result["original_blocker"]="Weekly original BUY reconciliation unavailable: "+str(exc)
        return result
    if weekly["review_count"]==0:
        result.update(
            original_phase="WAITING_FOR_FIRST_PRIOR_200WMA_BUY_TRIGGER",
            original_next_review_label="First BUY date unknown — needs future close below the prior 200WMA",
            original_blocker="No initial historical 200WMA recovery BUY trigger observed.",
        )
        return result
    result.update(
        original_phase="WEEKLY_ORIGINAL_REBUY_RESEARCH",
        original_next_review_date=weekly["next_review_date"],
        original_next_review_label="Next 7-day recovery BUY research review — NOT an order",
        last_completed_recovery_review_date=weekly["current_review_date"],
        last_completed_recovery_pct_original_budget=float(
            weekly["review_history"][-1]["pct_original_aftertax_buyback_budget"]),
        original_readiness=(
            "Historical BUY phase observed, but the tax-adjusted original "
            "cash budget and broker balance still require confirmation."
        ),
        original_blocker=(
            "Next week's dynamic percentage will depend on BTC prices observed "
            "BEFORE that review. No future amount or fill is known."
        ),
    )
    return result
