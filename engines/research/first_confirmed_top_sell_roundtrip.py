"""First price-confirmed mature-cycle top SELL versus frozen original wallet.

ONE predeclared candidate, no hindsight/optimization:
On the FIRST fresh rising edge of the already-existing lagged
maturity_confirmed_reversal indicator between halving+500 and +730,
sell up to an additional 20% of ORIGINAL BTC position. Maintain the
same day500/anchor/tail staged original policy, total sales <=100%
original, original 200WMA recovery-buy gate no earlier than day744.
If the alert never occurs, the candidate is IDENTICAL to baseline.

Historical indicator exports were fetched October 2026 and may be
revised vs original vintage. BTC close execution proxy is NOT IBIT price.
Research-only; never apply to user's real 2026 holdings or ntfy.
"""
from __future__ import annotations

import argparse
import json
import math
from pathlib import Path

import pandas as pd

from engines.research.cycle_chronological_wallet import (
    replay_chronological_wallet,previously_completed_200wma_breach,
)
from engines.research.day500_aftertax_reinvestment import (
    INITIAL_AUD,PRIMARY,SCORE_DAYS,DELAY_DAYS_AFTER_LAST_SELL,
    fetch_fx_for_cycle,fx_before,
)
from engines.research.shared_cycle_policy import (
    START_DAY,REVIEW_DAY,exit_review_days,staged_exit_decision,
    recovery_buy_budget_fraction,
)
from engines.research.smsf_self_financing_replay import AuditSmsfAccount
from engines.research.top_signal_horse_race import (
    read_exported_history,build_daily_signals,
)

SELL_TRIGGER="maturity_confirmed_reversal"
POLICY="maturity_90pct_holdback20pct"
PREDECLARED_ACCELERATOR_FRACTION_ORIGINAL=.20
EXECUTION_DELAYS_DAYS=(0,1,3,7)
OBSERVATION_CUTOFF=pd.Timestamp("2026-10-05",tz="UTC")


def _utc(t):
    d=pd.Timestamp(t)
    return (d.tz_localize("UTC") if d.tz is None
            else d.tz_convert("UTC")).normalize()


def compile_sell_plan(price,alert,halving,terminal,*,candidate):
    """Causal decisions for all predetermined maturity review dates.

    Relative to baseline, the accelerator may only add a *single*
    max-20%-original tranche on FIRST fresh confirmed-reversal edge.
    Current-day BTC close is never used to decide a day's sale.
    """
    h=_utc(halving)
    end=_utc(terminal)
    if (h not in price.index or end not in price.index
            or not price.index.is_monotonic_increasing or
            price.index.has_duplicates or price.index.tz is None):
        raise ValueError("Missing or invalid UTC daily price history")
    dates=pd.date_range(h,end,freq="D",tz="UTC")
    if not dates.isin(price.index).all():
        raise ValueError("Missing daily BTC observation")
    if not isinstance(alert,pd.Series) or not dates.isin(alert.index).all():
        raise ValueError("Missing dated original trend confirmation")
    reviews=set(exit_review_days())
    planned_fraction=0.
    planned=[]
    used_alert=False
    first_alert=None
    for date in dates[1:]:
        elapsed=(date-h).days
        if elapsed<START_DAY or elapsed>REVIEW_DAY:
            continue
        baseline_step=None
        if elapsed in reviews:
            baseline_step=staged_exit_decision(
                price.loc[:date],h,day=elapsed,
                sold_original_fraction=planned_fraction,
                policy=POLICY)
            qty=min(1.-planned_fraction,float(baseline_step["fraction_original"]))
            if qty>1e-12:
                planned.append({
                    "decision_date":str(date.date()),
                    "fraction_original":qty,
                    "reason":"original_staged_review",
                    "regime":baseline_step["regime"],
                })
                planned_fraction+=qty
        if not candidate:
            continue
        prev_day=date-pd.Timedelta(days=1)
        is_new=(bool(alert.loc[date])
                and prev_day in alert.index and
                not bool(alert.loc[prev_day]))
        if is_new and not used_alert:
            # Use strictly lagged original family (signal on T uses T-1).
            used_alert=True
            first_alert=str(date.date())
            qty=min(1.-planned_fraction,PREDECLARED_ACCELERATOR_FRACTION_ORIGINAL)
            if qty>1e-12:
                planned.append({
                    "decision_date":str(date.date()),
                    "fraction_original":qty,
                    "reason":"first_maturity_confirmed_reversal",
                    "regime":"confirmed_reversal",
                })
                planned_fraction+=qty
    if planned_fraction>1.+1e-9:
        raise AssertionError("Sold more than original BTC inventory")
    return {
        "policy":"first_maturity_confirmed_reversal_accelerate_20pct"
                 if candidate else "frozen_original_staged_exit",
        "first_fresh_confirmation_date":first_alert,
        "confirmation_seen_during_window":used_alert,
        "fraction_original_scheduled":round(planned_fraction,10),
        "sell_decisions":planned,
        "signal_uses_prior_day":True,
        "research_only":True,
    }


def chronological_sell_rebuy(price,fx,alert,halving,terminal,*,
                             candidate,sale_delay_days=0,
                             initial_aud=INITIAL_AUD):
    """One self-financing, dated, FIFO, after-tax AUD wallet per strategy.

    Decisions frozen at T; a 1/3/7 day execution delay only changes
    settlement price at T+delay. Original post-day730 buy entry remains
    strict previous-close-below-200WMA and fixed-budget weekly recovery.
    """
    if sale_delay_days not in EXECUTION_DELAYS_DAYS:
        raise ValueError("Unexpected sell execution delay")
    if not math.isfinite(float(initial_aud)) or initial_aud<=103.:
        raise ValueError("Unfunded hypothetical original position")
    h=_utc(halving)
    end=_utc(terminal)
    plan=compile_sell_plan(price,alert,h,end,candidate=candidate)
    account=AuditSmsfAccount(float(initial_aud),fee=3.,tax=True)
    start_aud=float(price.loc[h])*fx_before(fx,h)
    if not account.buy(h,start_aud,1.):
        raise AssertionError("Cannot establish matched initial BTC lot")
    initial_btc=account.btc
    planned_by_execution={}
    for trade in plan["sell_decisions"]:
        day=_utc(trade["decision_date"])+pd.Timedelta(days=sale_delay_days)
        if day>end:
            # Never execute after the observation cutoff.
            continue
        planned_by_execution.setdefault(day,[]).append(trade)
    # Must wait 14 days AFTER all potential scheduled sales, without
    # knowledge of future sale decisions or the ultimate low.
    activation=None
    original_rebuy_budget=None
    buys=[]
    sells=[]
    for day in pd.date_range(h+pd.Timedelta(days=1),end,
                             freq="D",tz="UTC"):
        usd=float(price.loc[day])
        if not math.isfinite(usd) or usd<=0:
            raise ValueError("Invalid execution price")
        aud=usd*fx_before(fx,day)
        for trade in planned_by_execution.get(day,[]):
            qty=min(account.btc,initial_btc*trade["fraction_original"])
            if qty>1e-12 and account.sell(
                    day,aud,min(1.,qty/account.btc)):
                order=account.orders[-1]
                sells.append({
                    "decision_date":trade["decision_date"],
                    "execution_date":str(day.date()),
                    "reason":trade["reason"],
                    "fraction_original":float(order["btc"])/initial_btc,
                    "btc":float(order["btc"]),
                    "gross_aud":float(order["gross_aud"]),
                    "tax_est_aud":float(order["tax_aud"]),
                })
        if day>=h+pd.Timedelta(days=REVIEW_DAY+DELAY_DAYS_AFTER_LAST_SELL):
            if activation is None and previously_completed_200wma_breach(
                    price,day):
                activation=day
                original_rebuy_budget=float(account.cash)
            if activation is not None and (day-activation).days%7==0:
                step=recovery_buy_budget_fraction(
                    price.loc[:day],day,style="adaptive_recovery")
                gross=min(account.cash,original_rebuy_budget*
                          step["fraction_of_initial_buyback_cash"])
                if gross>100.:
                    if account.buy(day,aud,min(1.,gross/account.cash)):
                        order=account.orders[-1]
                        buys.append({
                            "date":str(day.date()),
                            "gross_aud":float(order["gross_aud"]),
                            "btc":float(order["btc"]),
                            "pct_original_budget":step[
                                "pct_of_initial_buyback_cash"],
                        })
        account.mark(aud)
    final_aud=float(price.loc[end])*fx_before(fx,end)
    return {
        "policy":plan["policy"],
        "sale_delay_days":sale_delay_days,
        "hypothetical_initial_aud":float(initial_aud),
        "initial_btc":round(initial_btc,8),
        "sell_count":len(sells),
        "fraction_original_sold":round(
            sum(x["fraction_original"] for x in sells),8),
        "first_fresh_confirmation_date":plan["first_fresh_confirmation_date"],
        "confirmation_seen_during_window":plan["confirmation_seen_during_window"],
        "first_wma_buy_activation_date":(
            str(activation.date()) if activation is not None else None),
        "original_aftertax_buyback_cash_aud":(
            round(original_rebuy_budget,2)
            if original_rebuy_budget is not None else None),
        "buy_count":len(buys),
        "btc_end":round(account.btc,8),
        "cash_end_aud":round(account.cash,2),
        "btc_equivalent_including_cash":round(
            account.btc+account.cash/final_aud,8),
        "after_hypothetical_liquidation_cgt_aud":round(
            account.liquidation_value(end,final_aud),2),
        "estimated_cgt_paid_during_roundtrip_aud":round(account.total_tax,2),
        "brokerage_fees_aud":round(account.total_fees,2),
        "marked_equity_aud":round(
            account.cash+account.btc*final_aud,2),
        "max_marked_account_drawdown_pct":round(100*account.drawdown,2),
        "sell_decisions":plan["sell_decisions"],
        "executed_sells":sells,
        "executed_buys":buys,
        "terminal_date":str(end.date()),
        "research_only":True,
        "live_buy_sell_parity_verified":False,
    }


def audit_confirmation(history,*,fx_fetcher=fetch_fx_for_cycle,
                       cycles=("2017","2021","2025"),
                       sale_delays=EXECUTION_DELAYS_DAYS):
    """Matched original vs one candidate for fixed, previously studied cycles."""
    df=history.copy().sort_index().loc[:OBSERVATION_CUTOFF]
    for name in ("price_usd","mvrv_z","nupl","sopr"):
        if name not in df:
            raise ValueError(f"Missing archived indicator column {name}")
    price=df["price_usd"]
    signals=build_daily_signals(df)
    alert=signals[SELL_TRIGGER].fillna(False).astype(bool)
    rows=[]
    for label in cycles:
        if label not in PRIMARY:
            raise ValueError("Unknown historical cohort")
        h=_utc(PRIMARY[label]["halving"])
        end=min(h+pd.Timedelta(days=SCORE_DAYS),price.index[-1])
        fx=fx_fetcher(h,end)
        pairs=[]
        for delay in sale_delays:
            frozen=chronological_sell_rebuy(
                price,fx,alert,h,end,candidate=False,sale_delay_days=delay)
            challenger=chronological_sell_rebuy(
                price,fx,alert,h,end,candidate=True,sale_delay_days=delay)
            base=float(frozen["after_hypothetical_liquidation_cgt_aud"])
            new=float(challenger["after_hypothetical_liquidation_cgt_aud"])
            pairs.append({
                "delay_days":delay,
                "matched_original":frozen,
                "one_confirmation_candidate":challenger,
                "candidate_vs_original_aftertax_pct":round(100*(new/base-1),3),
                "candidate_extra_sell_count":challenger["sell_count"]-
                                            frozen["sell_count"],
                "candidate_original_position_sold_delta_pct":round(
                    100*(challenger["fraction_original_sold"]-
                         frozen["fraction_original_sold"]),4),
                "same_wma_buy_gate":(
                    frozen["first_wma_buy_activation_date"]==
                    challenger["first_wma_buy_activation_date"]),
            })
        rows.append({
            "cycle":label,"halving":str(h.date()),"terminal":str(end.date()),
            "completed_historical_day1150":end==h+pd.Timedelta(days=SCORE_DAYS),
            "first_top_confirmation_during_sell_window":pairs[0][
                "one_confirmation_candidate"]["first_fresh_confirmation_date"],
            "delay_matched_replays":pairs,
        })
    return {
        "question":"Does FIRST mature-cycle confirmed-reversal 20%-original-BTC extra sale improve full aftertax AUD roundtrip vs original 200WMA/day500?",
        "candidate_trigger":SELL_TRIGGER,
        "candidate_only_one_predeclared_extra_tranche_of_original_btc_pct":20.,
        "sell_date_age_window":[START_DAY,REVIEW_DAY],
        "buy_gate":"earliest day744 with previous BTC close below strict prior 200WMA; weekly original aftertax cash budget",
        "execution_delay_days":list(sale_delays),
        "observation_cutoff":str(OBSERVATION_CUTOFF.date()),
        "synthetic_start_aud":INITIAL_AUD,
        "historical_hypothesis_tested_in_sample":True,
        "indicators_may_have_revised_historical_values":True,
        "research_only":True,
        "live_signal_replacement":False,
        "cycles":rows,
    }


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--output",type=Path)
    args=parser.parse_args()
    audit=audit_confirmation(read_exported_history())
    for item in audit["cycles"]:
        print(json.dumps({
            "cycle":item["cycle"],
            "complete":item["completed_historical_day1150"],
            "first_confirmed_reversal":item[
                "first_top_confirmation_during_sell_window"],
            "outcomes":[{
                "execution_delay":x["delay_days"],
                "aftertax_original_aud":x["matched_original"][
                    "after_hypothetical_liquidation_cgt_aud"],
                "aftertax_confirmed_aud":x["one_confirmation_candidate"][
                    "after_hypothetical_liquidation_cgt_aud"],
                "confirmed_minus_original_pct":x[
                    "candidate_vs_original_aftertax_pct"],
                "candidate_minus_original_sold_pct":x[
                    "candidate_original_position_sold_delta_pct"],
            } for x in item["delay_matched_replays"]],
        },sort_keys=True))
    if args.output:
        args.output.parent.mkdir(parents=True,exist_ok=True)
        args.output.write_text(json.dumps(audit,indent=2))
        print("Dated confirmed SELL vs original aftertax audit:",args.output)


if __name__=="__main__":
    main()
