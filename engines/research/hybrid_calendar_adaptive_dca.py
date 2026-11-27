"""Calendar DCA + adaptive 200WMA reserve hybrid research replay.

Research-only. The base leg buys on a fixed calendar while a separately
budgeted reserve uses the existing prospective adaptive_recovery policy.
A shared per-cohort-week cap constrains combined outlay.
"""
from __future__ import annotations

import math
import pandas as pd

from engines.research.prospective_adaptive_recovery_replay import (
    DEFAULT_BUDGET_AUD,DEFAULT_CAPITAL_AUD,DEFAULT_CASH_YIELD,
    DEFAULT_WEEKLY_CAP_PCT,DEFAULT_BUY_FRICTION,DEFAULT_FEE_AUD,
    COHORT_WEEKS,ENTRY_START,HOLDOUT_START,
    _series,_aud_prices,_adaptive_schedule,_buy,run_cohort,
    quarterly_enrolment_dates,
)
from engines.research.shared_cycle_policy import recovery_buy_budget_fraction

BASE_ALLOCATIONS=(25,50,75)


def run_hybrid_cohort(btc_usd,usd_per_aud,*,enrolment_date,
                      base_allocation_pct=50,budget_aud=DEFAULT_BUDGET_AUD,
                      capital_aud=DEFAULT_CAPITAL_AUD,cash_yield=DEFAULT_CASH_YIELD,
                      weekly_cap_pct=DEFAULT_WEEKLY_CAP_PCT,
                      buy_friction=DEFAULT_BUY_FRICTION,fee_aud=DEFAULT_FEE_AUD):
    if base_allocation_pct not in BASE_ALLOCATIONS:
        raise ValueError("Base allocation must be one of the predeclared 25/50/75% variants")
    # Reuse the validated 104-week cohort construction and baseline references.
    baseline=run_cohort(btc_usd,usd_per_aud,enrolment_date=enrolment_date,
                        budget_aud=budget_aud,capital_aud=capital_aud,
                        cash_yield=cash_yield,weekly_cap_pct=weekly_cap_pct,
                        buy_friction=buy_friction,fee_aud=fee_aud)
    btc=_series(btc_usd,"BTC/USD")
    fx=_series(usd_per_aud,"USD per AUD")
    price=_aud_prices(btc,fx)
    enrol=pd.Timestamp(enrolment_date,tz="UTC").normalize()
    end=pd.Timestamp(baseline["terminal_date"],tz="UTC")
    low=float(price.loc[enrol:end].min())
    weekly_cap=capital_aud*weekly_cap_pct/100.
    base_budget=budget_aud*base_allocation_pct/100.
    reserve_budget=budget_aud-base_budget
    fixed_dates=[enrol+pd.Timedelta(days=7*i) for i in range(1,COHORT_WEEKS+1)]
    adaptive_dates,trigger=_adaptive_schedule(price,enrol,end)
    events=[]
    for day in fixed_dates:
        events.append((day,"base",base_budget/COHORT_WEEKS))
    for day in adaptive_dates:
        pct=recovery_buy_budget_fraction(btc,day,style="adaptive_recovery")["fraction_of_initial_buyback_cash"]
        events.append((day,"adaptive",reserve_budget*pct))
    events.sort(key=lambda item:(item[0],0 if item[1]=="base" else 1))
    base_cash=float(base_budget)
    reserve_cash=float(reserve_budget)
    base_btc=reserve_btc=base_spent=reserve_spent=base_gross=reserve_gross=0.
    base_count=reserve_count=0
    base_largest=reserve_largest=0.
    weekly_spend={}
    previous=enrol
    for day,leg,target in events:
        elapsed=(day-previous).days
        if elapsed<0:raise ValueError("Hybrid event dates are not monotonic")
        factor=(1+cash_yield)**(elapsed/365.25)
        base_cash*=factor
        reserve_cash*=factor
        previous=day
        week=int((day-enrol).days//7)
        cap_left=max(0.,weekly_cap-weekly_spend.get(week,0.))
        if leg=="base":
            base_cash,units,outlay,gross=_buy(base_cash,day,float(price.loc[day]),target,
                weekly_cap=cap_left,friction=buy_friction,fee=fee_aud)
            if units:
                base_btc+=units;base_spent+=outlay;base_gross+=gross;base_count+=1
                base_largest=max(base_largest,outlay);weekly_spend[week]=weekly_spend.get(week,0.)+outlay
        else:
            reserve_cash,units,outlay,gross=_buy(reserve_cash,day,float(price.loc[day]),target,
                weekly_cap=cap_left,friction=buy_friction,fee=fee_aud)
            if units:
                reserve_btc+=units;reserve_spent+=outlay;reserve_gross+=gross;reserve_count+=1
                reserve_largest=max(reserve_largest,outlay);weekly_spend[week]=weekly_spend.get(week,0.)+outlay
    elapsed=(end-previous).days
    if elapsed>0:
        factor=(1+cash_yield)**(elapsed/365.25)
        base_cash*=factor;reserve_cash*=factor
    total_btc=base_btc+reserve_btc
    total_spent=base_spent+reserve_spent
    total_gross=base_gross+reserve_gross
    terminal_price=float(price.loc[end])
    vwap=total_spent/total_btc if total_btc else None
    result={
        "policy":f"hybrid_base_{base_allocation_pct}_adaptive_reserve_{100-base_allocation_pct}",
        "base_allocation_pct":base_allocation_pct,"adaptive_reserve_pct":100-base_allocation_pct,
        "base_budget_aud":base_budget,"adaptive_reserve_budget_aud":reserve_budget,
        "base_btc":base_btc,"adaptive_reserve_btc":reserve_btc,
        "base_buy_count":base_count,"adaptive_buy_count":reserve_count,
        "total_buy_count":base_count+reserve_count,
        "base_outlay_aud":base_spent,"adaptive_outlay_aud":reserve_spent,
        "total_cash_outlay_aud":total_spent,"gross_buy_consideration_aud":total_gross,
        "largest_weekly_combined_outlay_aud":max(weekly_spend.values(),default=0.),
        "weekly_cap_aud":weekly_cap,
        "btc_accumulated":total_btc,"cash_remaining_aud":base_cash+reserve_cash,
        "base_cash_remaining_aud":base_cash,"adaptive_cash_remaining_aud":reserve_cash,
        "cash_budget_deployed_pct":100*total_spent/budget_aud,
        "effective_vwap_aud_per_btc":vwap,
        "cohort_104w_low_aud":low,
        "vwap_premium_to_cohort_low_pct":100*(vwap/low-1) if vwap else None,
        "terminal_btc_value_aud":total_btc*terminal_price,
        "terminal_equity_aud":base_cash+reserve_cash+total_btc*terminal_price,
        "trigger_date":str(trigger.date()) if trigger is not None else None,
        "weeks_until_trigger":(trigger-enrol).days/7 if trigger is not None else None,
    }
    return {k:v for k,v in baseline.items() if k!="results"}|result


def run_all_hybrid_cohorts(btc_usd,usd_per_aud,*,budget_aud=DEFAULT_BUDGET_AUD):
    btc=_series(btc_usd,"BTC/USD")
    fx=_series(usd_per_aud,"USD per AUD")
    price=_aud_prices(btc,fx)
    rows=[]
    for start in quarterly_enrolment_dates():
        enrol=pd.Timestamp(start,tz="UTC")
        terminal=enrol+pd.Timedelta(days=7*COHORT_WEEKS)
        if enrol not in price.index or terminal not in price.index:continue
        try:
            for pct in BASE_ALLOCATIONS:
                rows.append(run_hybrid_cohort(btc,fx,enrolment_date=start,
                    base_allocation_pct=pct,budget_aud=budget_aud))
        except ValueError as exc:
            if "Missing weekly execution price" in str(exc):continue
            raise
    return pd.DataFrame(rows)


def hybrid_summary_table(cohorts,fixed_weekly_reference):
    if cohorts.empty or fixed_weekly_reference.empty:
        raise ValueError("Hybrid and fixed-weekly reference cohorts required")
    fixed=fixed_weekly_reference.loc[fixed_weekly_reference.policy=="fixed_weekly"].set_index("enrolment_date")
    rows=[]
    for entry_period,group in cohorts.groupby("entry_period"):
        for policy,sub in group.groupby("policy"):
            peers=fixed.loc[sub.enrolment_date]
            btc_uplift=pd.Series([100*(float(a)/float(b)-1) for a,b in zip(sub.btc_accumulated,peers.btc_accumulated)],index=sub.index)
            eq_uplift=pd.Series([100*(float(a)/float(b)-1) for a,b in zip(sub.terminal_equity_aud,peers.terminal_equity_aud)],index=sub.index)
            active=sub.trigger_date.notna()
            rows.append({
                "entry_period":entry_period,"policy":policy,"base_allocation_pct":int(sub.base_allocation_pct.iloc[0]),
                "cohort_count":len(sub),"trigger_rate_pct":100*float(active.mean()),
                "median_trigger_delay_weeks":float(sub.weeks_until_trigger.dropna().median()) if sub.weeks_until_trigger.notna().any() else None,
                "median_btc_accumulated":float(sub.btc_accumulated.median()),
                "median_vwap_aud":float(sub.effective_vwap_aud_per_btc.dropna().median()) if sub.effective_vwap_aud_per_btc.notna().any() else None,
                "median_cash_remaining_aud":float(sub.cash_remaining_aud.median()),
                "median_cash_deployed_pct":float(sub.cash_budget_deployed_pct.median()),
                "median_vwap_premium_to_cohort_low_pct":float(sub.vwap_premium_to_cohort_low_pct.dropna().median()) if sub.vwap_premium_to_cohort_low_pct.notna().any() else None,
                "median_terminal_equity_aud":float(sub.terminal_equity_aud.median()),
                "median_paired_btc_uplift_vs_fixed_weekly_pct":float(btc_uplift.median()),
                "median_paired_equity_uplift_vs_fixed_weekly_pct":float(eq_uplift.median()),
                "cohort_btc_win_rate_vs_fixed_weekly_pct":100*float((btc_uplift>0).mean()),
                "cohort_equity_win_rate_vs_fixed_weekly_pct":100*float((eq_uplift>0).mean()),
                "triggered_median_paired_btc_uplift_pct":float(btc_uplift.loc[active].median()) if active.any() else None,
                "triggered_btc_win_rate_pct":100*float((btc_uplift.loc[active]>0).mean()) if active.any() else None,
                "triggered_median_paired_equity_uplift_pct":float(eq_uplift.loc[active].median()) if active.any() else None,
                "triggered_equity_win_rate_pct":100*float((eq_uplift.loc[active]>0).mean()) if active.any() else None,
                "weekly_cap_compliant":bool(sub.largest_weekly_combined_outlay_aud.le(sub.weekly_cap_aud+1e-6).all()),
            })
    return pd.DataFrame(rows).sort_values(["entry_period","base_allocation_pct"]).reset_index(drop=True)
