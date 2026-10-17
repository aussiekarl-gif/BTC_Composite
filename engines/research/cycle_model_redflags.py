"""Quiet, read-only cross-check of Cycle Trading percentages against V5.8.2/5.9.

Production and Research report 0..1 *risk scores*, not Cycle Trading's
percent of current cash/holdings. NEVER compare the numerical percentages
directly. Only strong contradictory risk regimes are material warnings.

No orders, Google Sheets access, portfolio data, ntfy sender or mutations.
Missing, stale or mismatched scores are UNKNOWN, never a fake all-clear.
"""
from __future__ import annotations

import datetime as dt
import logging
import math

LOGGER=logging.getLogger(__name__)
MODELS=("Production V5.8.2","Research V5.9")
MAX_MODEL_AGE_DAYS=3
MAX_SOURCE_ASOF_GAP_DAYS=1
EXTREME_HIGH=0.80
EXTREME_LOW=0.20
SPLIT_HIGH=0.85
SPLIT_LOW=0.15


def _date(raw):
    if isinstance(raw,dt.datetime):
        return raw.date()
    if isinstance(raw,dt.date):
        return raw
    if not isinstance(raw,str):
        raise ValueError("Expected dated model observation")
    for fmt in ("%Y-%m-%d","%d/%m/%y","%d/%m/%Y"):
        try:
            return dt.datetime.strptime(raw,fmt).date()
        except ValueError:
            continue
    raise ValueError("Invalid reference model observation date")


def evaluate_major_red_flags(*, buy_pct_cash, sell_pct_held, snapshots,
                             market_asof, today, confirmed_halving_date="2024-04-20"):
    """Return zero or one MAJOR warning, or silence.

    One missing/stale model -> no verified comparison and NO invented pass.
    5.82/5.9 default reference risk models are not identical to trading
    instructions or production/research portfolio sizing, and are not
    independent sources of price data.
    """
    result={"warnings":[],"status":"not_checked"}
    try:
        buy=float(buy_pct_cash)
        sell=float(sell_pct_held)
        if not all(math.isfinite(x) and x>=0 for x in (buy,sell)):
            return result
        if (buy>0)==(sell>0):
            # HOLD or contradictory simultaneous directional allocations
            return result
        asof=_date(market_asof)
        date=_date(today)
        if (date-asof).days<0 or (date-asof).days>MAX_MODEL_AGE_DAYS:
            return result
        # The archived 5.82/5.9 reference implementations still use 2024
        # in their cycle calibration. Disable the comparison at the next epoch
        # rather than promote invalid 'agreement' about a future cycle.
        if _date(confirmed_halving_date)>dt.date(2024,4,20):
            return {"warnings":[],"status":"unsupported_new_cycle"}
        if not isinstance(snapshots,dict) or set(snapshots)!=set(MODELS):
            return result
        scores=[]
        for name in MODELS:
            item=snapshots[name]
            risk=float(item["risk"])
            stamp=_date(item["risk_data_date"])
            if not 0<=risk<=1 or not math.isfinite(risk):
                return result
            if not 0<=(date-stamp).days<=MAX_MODEL_AGE_DAYS:
                return result
            # Do not use new information after the cycle's reference close
            # or misalign two models by multiple market days.
            if not 0<=(asof-stamp).days<=MAX_SOURCE_ASOF_GAP_DAYS:
                return result
            scores.append(risk)
    except (KeyError,ValueError,TypeError,OverflowError):
        return result

    production,research=scores
    result["status"]="checked"
    if buy>0 and min(scores)>=EXTREME_HIGH:
        result["warnings"]=[
            f"MAJOR RED FLAG — Cycle Trading proposes BUY {buy:.2f}% of cash, "
            f"but Production (risk {production:.2f}) and Research (risk {research:.2f}) "
            "both rate Bitcoin VERY HIGH risk. Review the signal before buying."
        ]
    elif sell>0 and max(scores)<=EXTREME_LOW:
        result["warnings"]=[
            f"MAJOR RED FLAG — Cycle Trading proposes SELL {sell:.2f}% of holdings, "
            f"but Production (risk {production:.2f}) and Research (risk {research:.2f}) "
            "both rate Bitcoin VERY LOW risk. Review the signal before selling."
        ]
    elif min(scores)<=SPLIT_LOW and max(scores)>=SPLIT_HIGH:
        result["warnings"]=[
            f"MAJOR RED FLAG — Production (risk {production:.2f}) and Research "
            f"(risk {research:.2f}) give opposite extreme market assessments "
            "while Cycle Trading proposes a DCA percentage. Review model/data divergence."
        ]
    return result



def validated_reference_risk_scores(*, snapshots, market_asof, today,
                                     confirmed_halving_date="2024-04-20"):
    """Validate model scores independently with the same dated cutoff as Cycle.

    Returns only fresh scores, with no imaginary agreement on HOLD.
    """
    scores={}
    try:
        asof=_date(market_asof)
        current=_date(today)
        if not 0<=(current-asof).days<=MAX_MODEL_AGE_DAYS:
            return scores
        if _date(confirmed_halving_date)>dt.date(2024,4,20):
            return scores
        if not isinstance(snapshots,dict):
            return scores
    except (TypeError,ValueError,OverflowError):
        return scores
    for name in MODELS:
        try:
            item=snapshots[name]
            score=float(item["risk"])
            observed=_date(item["risk_data_date"])
            if (math.isfinite(score) and 0<=score<=1
                and 0<=(current-observed).days<=MAX_MODEL_AGE_DAYS
                and 0<=(asof-observed).days<=MAX_SOURCE_ASOF_GAP_DAYS):
                scores[name]=score
        except (TypeError,KeyError,ValueError,OverflowError):
            pass
    return scores


def daily_reference_labels(*, buy_pct_cash, sell_pct_held, snapshots,
                           market_asof, today,
                           confirmed_halving_date="2024-04-20"):
    """Explain HOLD without mistaking *no trade to compare* for missing data.

    Agreement on BUY/SELL only means no extreme opposing risk regime,
    never identical recommendations, and non-actionable HOLD is not agreement.
    """
    output={name:"no data" for name in MODELS}
    scores=validated_reference_risk_scores(
        snapshots=snapshots,market_asof=market_asof,today=today,
        confirmed_halving_date=confirmed_halving_date)
    try:
        buy=float(buy_pct_cash)
        sell=float(sell_pct_held)
        valid=math.isfinite(buy) and math.isfinite(sell) and buy>=0 and sell>=0
        directional=(buy>0)!=(sell>0) if valid else False
        hold=(buy==0 and sell==0) if valid else False
    except (ValueError,TypeError):
        directional=hold=False
    comparisons=(model_agreement_statuses(
        buy_pct_cash=buy_pct_cash,sell_pct_held=sell_pct_held,
        snapshots=snapshots,market_asof=market_asof,today=today,
        confirmed_halving_date=confirmed_halving_date)
        if directional else {})
    for name,score in scores.items():
        risk_str=f"risk {score:.2f}"
        if name==MODELS[1] and score<.005:
            risk_str+="; near Power Law floor, not zero investment risk"
        if directional:
            output[name]=f"{comparisons[name]} ({risk_str})"
        elif hold:
            output[name]=f"no trade to compare ({risk_str})"
    return output


def model_agreement_statuses(*, buy_pct_cash, sell_pct_held, snapshots,
                             market_asof, today,
                             confirmed_halving_date="2024-04-20"):
    """For the DAILY summary: one label for EACH model, independently.

    Here 'agrees' means **no extreme contradictory risk** to the Cycle
    Trading BUY/SELL direction. It is NOT a claim that the model advocates
    the same DCA percentage or independently recommends the trade.

    'no data' also covers missing/stale reference inputs, the absence of
    a comparable Cycle BUY/SELL, or an unsupported new halving cycle.
    The latter are not silently called agreements.
    """
    output={name:"no data" for name in MODELS}
    try:
        buy=float(buy_pct_cash)
        sell=float(sell_pct_held)
        if (not math.isfinite(buy) or not math.isfinite(sell)
                or buy<0 or sell<0 or (buy>0)==(sell>0)):
            return output
        asof=_date(market_asof)
        current=_date(today)
        if not 0<=(current-asof).days<=MAX_MODEL_AGE_DAYS:
            return output
        if _date(confirmed_halving_date)>dt.date(2024,4,20):
            # V5.82/V5.9 epoch-calibrations are not verified in later cycles.
            return output
        if not isinstance(snapshots,dict):
            return output
    except (TypeError,ValueError,OverflowError):
        return output

    for name in MODELS:
        try:
            snapshot=snapshots[name]
            score=float(snapshot["risk"])
            observed=_date(snapshot["risk_data_date"])
            if (not math.isfinite(score) or not 0<=score<=1
                    or not 0<=(current-observed).days<=MAX_MODEL_AGE_DAYS
                    or not 0<=(asof-observed).days<=MAX_SOURCE_ASOF_GAP_DAYS):
                continue
            extreme_opposition=(buy>0 and score>=EXTREME_HIGH) or (
                sell>0 and score<=EXTREME_LOW)
            output[name]="disagrees" if extreme_opposition else "agrees"
        except (KeyError,TypeError,ValueError,OverflowError):
            continue
    return output


def fetch_reference_model_risks():
    """Invoke existing exact V5.8.2 and V5.9 default risk calculations.

    Kept separate from ntfy publishing; the former dual-model script's
    calculation helper is still valid and its sender has been retired.
    External provider failure is reported internally as missing evidence,
    NOT as an explicit 'all clear'. This is deliberately not a trade gate.
    """
    from dca_model_compare_notify import (
        PROD_MODEL, RESEARCH_MODEL, calculate_model_summary,
    )
    summaries={}
    for name,module,model in (
        (MODELS[0],PROD_MODEL,"Composite V3.6"),
        (MODELS[1],RESEARCH_MODEL,"Research WF Power Law"),
    ):
        try:
            summary, _, _=calculate_model_summary(module,model)
            summaries[name]={
                "risk":summary["risk"],
                "risk_data_date":summary["risk_data_date"],
            }
        except Exception as exc:
            LOGGER.warning("%s cross-check unavailable (%s)",name,type(exc).__name__)
    return summaries
