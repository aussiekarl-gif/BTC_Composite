"""Pure prior-data cycle exit and recovery-buy rules shared across Research.

Exactly reproduces the model variants used by historic day500 replay:
- Exit weights are in fractions of the ORIGINAL starting BTC position,
  NOT fractions of the CURRENT holdings or ASX IBIT ETF units.
- '20% holdback' is a *pre-day560* cap of 80% sold, not a
  permanent minimum reserve: a confirmed later breakdown can sell more.
- Decision for date T uses only closes strictly BEFORE T; execution
  simulation separately prices orders at T's observed closing price.
- 200WMA dynamic recovery BUY budget percentages are percentages of the
  ORIGINAL available post-exit buyback budget, not remaining cash.

Research simulations use hypothetical legacy positions. They cannot
create retrospective 2025 orders on a real 2026 purchase account.
"""
from __future__ import annotations

import math
import pandas as pd

START_DAY=500
REVIEW_DAY=730
ANCHORS=(525,532,539,546,553,560)
ANCHOR_WEIGHTS=(6.,5.,4.,3.,2.,1.)
STAGED_POLICIES={
    "maturity_80pct":{"initial":.05,"core_fraction":.80},
    "maturity_90pct":{"initial":.05,"core_fraction":.90},
    "maturity_90pct_holdback20pct":{
        "initial":.05,"core_fraction":.90,
        "pre560_sold_cap":.80,
        "tail_confirm_only":True,
    },
}
RECOVERY_BUY_STYLES=("adaptive_value","adaptive_recovery")


def prior_price_regime(price,day):
    """90 completed daily closes through day-1, no current day leakage."""
    date=pd.Timestamp(day)
    if date.tzinfo is None:date=date.tz_localize("UTC")
    observed=price.loc[date-pd.Timedelta(days=90):
                       date-pd.Timedelta(days=1)]
    if len(observed)!=90:
        raise ValueError("90 consecutive completed daily closes required")
    if not (observed.index==pd.date_range(
        date-pd.Timedelta(days=90),periods=90,tz="UTC",freq="D"
    )).all():
        raise ValueError("Missing prior daily BTC close")
    prior=float(observed.iloc[-1])
    hi=float(observed.max())
    ma50=float(observed.iloc[-50:].mean())
    previous_ma50=float(price.loc[
        date-pd.Timedelta(days=64):date-pd.Timedelta(days=15)].mean())
    if not all(math.isfinite(x) and x>0 for x in
               (prior,hi,ma50,previous_ma50)):
        raise ValueError("Invalid historical prices")
    drawdown=1-prior/hi
    if drawdown>=.15 and prior<ma50 and ma50<previous_ma50:
        regime="breakdown"
    elif prior>=.95*hi and prior>ma50:
        regime="high"
    else:
        regime="neutral"
    return regime,{
        "prior_close":prior,
        "trailing_high":hi,
        "drawdown_from_prior_90d_high_pct":100*drawdown,
        "prior_sma50":ma50,
        "prior_sma50_14days_ago":previous_ma50,
    }


def exit_review_days(*,review_day=REVIEW_DAY):
    if not isinstance(review_day,int) or review_day<START_DAY:
        raise ValueError("Invalid exit review day")
    return tuple(sorted(set(
        [START_DAY]+list(range(START_DAY+7,review_day+1,7))+list(ANCHORS)
    )))


def staged_exit_decision(price,halving,*,day,sold_original_fraction,
                         policy="maturity_90pct_holdback20pct"):
    """One deterministic exit transition, fraction of ORIGINAL position.

    Must be invoked with previously executed/simulated original fractions
    subtracted, in calendar order. Repeated same-day actions are not
    protected by this pure step; caller handles order deduplication.
    """
    if policy not in STAGED_POLICIES:raise ValueError("Unknown sell policy")
    if not isinstance(day,int) or day<START_DAY:
        raise ValueError("Cycle review day must be >=500")
    previous=float(sold_original_fraction)
    if not math.isfinite(previous) or not 0<=previous<=1:
        raise ValueError("Prior total original BTC sold outside 0..1")
    config=STAGED_POLICIES[policy]
    left=1-previous
    if left<=1e-10:
        return {"fraction_original":0.,"regime":"fully distributed",
                "day":day,"sold_before":previous,"sold_after":previous}
    # Important: no price action before day500.
    if day==START_DAY:
        regime="maturity-start"
        target=float(config["initial"])
    else:
        date=pd.Timestamp(halving)
        if date.tzinfo is None:date=date.tz_localize("UTC")
        else:date=date.tz_convert("UTC")
        date+=pd.Timedelta(days=day)
        regime,metrics=prior_price_regime(price,date)
        if day in ANCHORS:
            weight=dict(zip(ANCHORS,ANCHOR_WEIGHTS))[day]
            core=float(config["core_fraction"])
            factor={"high":1.20,"neutral":.75,"breakdown":1.30}[regime]
            target=core*weight/sum(ANCHOR_WEIGHTS)*factor
        elif day<525 and day in exit_review_days(review_day=day):
            target=.025 if regime=="breakdown" else 0.
        elif day>560 and day in exit_review_days(review_day=day):
            if config.get("tail_confirm_only",False):
                target=.070 if regime=="breakdown" else 0.
            else:
                target={"high":.045,"neutral":.012,"breakdown":.070}[regime]
        else:
            target=0.
    target=min(left,target)
    if day<=560:
        limit=float(config.get("pre560_sold_cap",1.))
        target=min(target,max(0.,limit-previous))
    target=max(0.,target)
    return {
        "fraction_original":target,
        "regime":regime,
        "day":day,
        "sold_before":previous,
        "sold_after":min(1.,previous+target),
        "policy":policy,
        "reference_denominator":"original BTC before day500",
        "pre560_sold_cap_original_pct":
            100*float(config.get("pre560_sold_cap",1.)),
        "holdback_can_sell_after_day560":
            bool(config.get("tail_confirm_only",False)),
    }


def recovery_buy_budget_fraction(price,day,*,style):
    """Fraction of INITIAL AFTER-TAX BUYBACK CASH budget for one weekly step.

    Mirrors historical adaptive-recovery/value tiers, not residual-cash
    percentages in the earlier simplified Streamlit dashboard.
    """
    if style not in RECOVERY_BUY_STYLES:
        raise ValueError("Unknown recovery style")
    date=pd.Timestamp(day)
    if date.tzinfo is None:date=date.tz_localize("UTC")
    else:date=date.tz_convert("UTC")
    date=date.normalize()
    if date not in price.index:
        raise ValueError("Execution date missing from price index")
    # Need 200 exact prior weekly closes and prior 64 daily closes.
    weeks=[date-pd.Timedelta(days=1+7*i) for i in range(200)]
    if not pd.DatetimeIndex(weeks).isin(price.index).all():
        raise ValueError("Insufficient causal 200WMA observations")
    previous=float(price.loc[date-pd.Timedelta(days=1)])
    ma200=float(price.loc[weeks].mean())
    ratio=previous/ma200
    if style=="adaptive_value":
        amount=(.10 if ratio<=.85 else
                .035 if ratio<=1.0 else
                .12 if ratio<=1.25 else
                .04 if ratio<=1.5 else .01)
        recovery=False
    else:
        recent=float(price.loc[date-pd.Timedelta(days=50):
                               date-pd.Timedelta(days=1)].mean())
        earlier=float(price.loc[date-pd.Timedelta(days=64):
                                date-pd.Timedelta(days=15)].mean())
        strengthening=(previous>recent and recent>earlier)
        amount=(.025 if ratio<=1.0 else
                .15 if ratio<=1.25 and strengthening else
                .045 if ratio<=1.5 else .01)
        recovery=strengthening and 1.0<ratio<=1.25
    return {
        "fraction_of_initial_buyback_cash":float(amount),
        "pct_of_initial_buyback_cash":round(100*amount,2),
        "previous_close_to_200wma":ratio,
        "recovery_confirmation":recovery,
        "requires_active_buyback_phase":True,
        "research_only":True,
    }


def cycle_exit_stage_status(halving,asof,*,next_event_only=True):
    """Readable policy applicability; never backdate legacy sale on 2026 holdings."""
    date=pd.Timestamp(asof)
    start=pd.Timestamp(halving)
    if date.tzinfo is None:date=date.tz_localize("UTC")
    if start.tzinfo is None:start=start.tz_localize("UTC")
    age=(date.normalize()-start.normalize()).days
    reviews=exit_review_days()
    future=next((d for d in reviews if d>=age and d<=REVIEW_DAY),None)
    return {
        "halving_day":age,
        "next_exit_review_day":future,
        "next_exit_review_date":(
            str((start+pd.Timedelta(days=future)).date())
            if future is not None else None
        ),
        "exit_window_expired":age>REVIEW_DAY,
        "policy":"maturity_90pct_holdback20pct",
        "historical_context_only":True,
    }
