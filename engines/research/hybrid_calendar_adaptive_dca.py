"""Independent calendar DCA + adaptive 200WMA reserve hybrid research replay.

Research-only. The base leg buys on a fixed calendar while a separately
budgeted reserve uses the shared adaptive_recovery policy sizing helper.
A shared per-cohort-week cap constrains combined outlay. This module is
self-contained and does not depend on another open research PR.
"""
from __future__ import annotations

from datetime import date
import math
import pandas as pd

from engines.research.shared_cycle_policy import recovery_buy_budget_fraction

DEFAULT_BUDGET_AUD=292383.0
DEFAULT_CAPITAL_AUD=510000.0
DEFAULT_CASH_YIELD=0.05
DEFAULT_WEEKLY_CAP_PCT=5.0
DEFAULT_BUY_FRICTION=0.003
DEFAULT_FEE_AUD=3.0
COHORT_WEEKS=104
ENTRY_START=date(2017,1,2)
HOLDOUT_START=date(2022,1,1)
BASE_ALLOCATIONS=(25,50,75,80,90)


def _series(s,label):
    if not isinstance(s,pd.Series) or s.empty:
        raise ValueError(f"{label} dated Series required")
    x=pd.to_numeric(s,errors="coerce").dropna().copy()
    x.index=pd.to_datetime(x.index,utc=True).normalize()
    x=x.sort_index()
    if x.index.has_duplicates or not x.map(math.isfinite).all() or (x<=0).any():
        raise ValueError(f"{label} dates/values invalid")
    return x.astype(float)


def _aud_prices(btc_usd,usd_per_aud):
    btc=_series(btc_usd,"BTC/USD")
    fx=_series(usd_per_aud,"USD per AUD")
    out={}
    for day,usd in btc.items():
        pos=fx.index.searchsorted(day,side="right")-1
        if pos<0:continue
        fx_day=fx.index[pos]
        if (day-fx_day).days>5:continue
        out[day]=float(usd)/float(fx.iloc[pos])
    return pd.Series(out,name="btc_aud").sort_index()


def _prior_200wma_ratio(price,day):
    day=pd.Timestamp(day)
    if day.tzinfo is None:day=day.tz_localize("UTC")
    else:day=day.tz_convert("UTC")
    prior=day-pd.Timedelta(days=1)
    if prior not in price.index:return None
    dates=[prior-pd.Timedelta(days=7*i) for i in range(200)]
    if not pd.DatetimeIndex(dates).isin(price.index).all():return None
    ma=float(price.loc[dates].mean())
    if not math.isfinite(ma) or ma<=0:return None
    return float(price.loc[prior])/ma


def _adaptive_schedule(price,enrol,end):
    trigger=None
    start=pd.Timestamp(enrol)+pd.Timedelta(days=1)
    for day in price.index:
        if day<start or day>end:continue
        ratio=_prior_200wma_ratio(price,day)
        if ratio is not None and ratio<1.0:
            trigger=day;break
    if trigger is None:return [],None
    dates=[]
    day=trigger
    while day<=end:
        dates.append(day)
        day+=pd.Timedelta(days=7)
    return dates,trigger


def _buy(cash,price,target,weekly_cap,friction,fee):
    target=min(max(0.,target),max(0.,weekly_cap-fee),max(0.,cash-fee))
    if target<100.:
        return cash,0.,0.
    units=target*(1-friction)/price
    outlay=target+fee
    if outlay>cash+1e-8 or outlay>weekly_cap+1e-8:
        raise AssertionError("Purchase exceeds cash or weekly cap")
    return cash-outlay,units,outlay


def quarterly_enrolment_dates(first=ENTRY_START):
    dates=[]
    current=pd.Timestamp(first,tz="UTC").normalize()
    for year in range(current.year,2026):
        for month in (1,4,7,10):
            d=pd.Timestamp(date(year,month,1),tz="UTC")
            d+=pd.Timedelta(days=(7-d.weekday())%7)
            if d>=current:dates.append(d)
    return [d.date() for d in dates]


def run_fixed_weekly_reference(btc_usd,usd_per_aud,*,enrolment_date,
        budget_aud=DEFAULT_BUDGET_AUD,capital_aud=DEFAULT_CAPITAL_AUD,
        cash_yield=DEFAULT_CASH_YIELD,weekly_cap_pct=DEFAULT_WEEKLY_CAP_PCT,
        buy_friction=DEFAULT_BUY_FRICTION,fee_aud=DEFAULT_FEE_AUD):
    btc=_series(btc_usd,"BTC/USD")
    fx=_series(usd_per_aud,"USD per AUD")
    price=_aud_prices(btc,fx)
    enrol=pd.Timestamp(enrolment_date)
    enrol=enrol.tz_localize("UTC") if enrol.tzinfo is None else enrol.tz_convert("UTC")
    enrol=enrol.normalize()
    end=enrol+pd.Timedelta(days=7*COHORT_WEEKS)
    dates=[enrol+pd.Timedelta(days=7*i) for i in range(1,COHORT_WEEKS+1)]
    if enrol not in price.index or end not in price.index or any(d not in price.index for d in dates):
        raise ValueError("Missing complete weekly cohort prices; no interpolation")
    cash=float(budget_aud);units=spent=0.;count=0
    previous=enrol;weekly_cap=capital_aud*weekly_cap_pct/100.
    for day in dates:
        elapsed=(day-previous).days
        cash*=((1+cash_yield)**(elapsed/365.25));previous=day
        cash,buy_units,outlay=_buy(cash,float(price.loc[day]),budget_aud/COHORT_WEEKS,
                                   weekly_cap,buy_friction,fee_aud)
        if buy_units:units+=buy_units;spent+=outlay;count+=1
    terminal=dates[-1]
    final_btc_value=units*float(price.loc[terminal])
    return {"fixed_weekly_btc":units,"fixed_weekly_cash_remaining_aud":cash,
            "fixed_weekly_total_outlay_aud":spent,"fixed_weekly_buy_count":count,
            "fixed_weekly_terminal_equity_aud":cash+final_btc_value,
            "fixed_weekly_vwap_aud":spent/units if units else None}


def run_hybrid_cohort(btc_usd,usd_per_aud,*,enrolment_date,
                      base_allocation_pct=50,budget_aud=DEFAULT_BUDGET_AUD,
                      capital_aud=DEFAULT_CAPITAL_AUD,cash_yield=DEFAULT_CASH_YIELD,
                      weekly_cap_pct=DEFAULT_WEEKLY_CAP_PCT,
                      buy_friction=DEFAULT_BUY_FRICTION,fee_aud=DEFAULT_FEE_AUD):
    if base_allocation_pct not in BASE_ALLOCATIONS:
        raise ValueError("Base allocation must be one of the predeclared 25/50/75% variants")
    btc=_series(btc_usd,"BTC/USD")
    fx=_series(usd_per_aud,"USD per AUD")
    if not btc.index.equals(pd.date_range(btc.index[0],btc.index[-1],freq="D",tz="UTC")):
        raise ValueError("BTC/USD history must contain consecutive daily observations")
    numeric=(budget_aud,capital_aud,cash_yield,weekly_cap_pct,buy_friction,fee_aud)
    if not all(math.isfinite(float(x)) for x in numeric):
        raise ValueError("Simulation assumptions must be finite")
    if budget_aud<=0 or capital_aud<=0 or cash_yield<0:
        raise ValueError("Budget/capital must be positive and cash yield nonnegative")
    if not 0<weekly_cap_pct<=100 or not 0<=buy_friction<1 or fee_aud<0:
        raise ValueError("Invalid weekly cap, friction or fee")
    price=_aud_prices(btc,fx)
    enrol=pd.Timestamp(enrolment_date)
    enrol=enrol.tz_localize("UTC") if enrol.tzinfo is None else enrol.tz_convert("UTC")
    enrol=enrol.normalize()
    end=enrol+pd.Timedelta(days=7*COHORT_WEEKS)
    fixed_dates=[enrol+pd.Timedelta(days=7*i) for i in range(1,COHORT_WEEKS+1)]
    if enrol not in price.index or end not in price.index or any(d not in price.index for d in fixed_dates):
        raise ValueError("Missing complete weekly cohort prices; no interpolation")
    low=float(price.loc[enrol:end].min())
    fixed=run_fixed_weekly_reference(btc,fx,enrolment_date=enrol,budget_aud=budget_aud,
        capital_aud=capital_aud,cash_yield=cash_yield,weekly_cap_pct=weekly_cap_pct,
        buy_friction=buy_friction,fee_aud=fee_aud)
    weekly_cap=capital_aud*weekly_cap_pct/100.
    base_budget=budget_aud*base_allocation_pct/100.
    reserve_budget=budget_aud-base_budget
    adaptive_dates,trigger=_adaptive_schedule(price,enrol,end)
    events=[(day,"base",base_budget/COHORT_WEEKS) for day in fixed_dates]
    for day in adaptive_dates:
        fraction=recovery_buy_budget_fraction(btc,day,style="adaptive_recovery")["fraction_of_initial_buyback_cash"]
        events.append((day,"adaptive",reserve_budget*fraction))
    events.sort(key=lambda item:(item[0],0 if item[1]=="base" else 1))
    base_cash=float(base_budget);reserve_cash=float(reserve_budget)
    base_btc=reserve_btc=base_spent=reserve_spent=0.
    base_count=reserve_count=0
    weekly_spend={}
    previous=enrol
    for day,leg,target in events:
        elapsed=(day-previous).days
        if elapsed<0:raise ValueError("Hybrid event dates not monotonic")
        factor=(1+cash_yield)**(elapsed/365.25)
        base_cash*=factor;reserve_cash*=factor;previous=day
        week=int((day-enrol).days//7)
        cap_left=max(0.,weekly_cap-weekly_spend.get(week,0.))
        if leg=="base":
            base_cash,buy_units,outlay=_buy(base_cash,float(price.loc[day]),target,cap_left,buy_friction,fee_aud)
            if buy_units:
                base_btc+=buy_units;base_spent+=outlay;base_count+=1
                weekly_spend[week]=weekly_spend.get(week,0.)+outlay
        else:
            reserve_cash,buy_units,outlay=_buy(reserve_cash,float(price.loc[day]),target,cap_left,buy_friction,fee_aud)
            if buy_units:
                reserve_btc+=buy_units;reserve_spent+=outlay;reserve_count+=1
                weekly_spend[week]=weekly_spend.get(week,0.)+outlay
    elapsed=(end-previous).days
    if elapsed>0:
        factor=(1+cash_yield)**(elapsed/365.25)
        base_cash*=factor;reserve_cash*=factor
    total_btc=base_btc+reserve_btc
    total_spent=base_spent+reserve_spent
    vwap=total_spent/total_btc if total_btc else None
    terminal_price=float(price.loc[end])
    entry_period="pre_2022_calendar_entry" if enrol.date()<HOLDOUT_START else "2022plus_calendar_entry"
    result={
        "enrolment_date":str(enrol.date()),"terminal_date":str(end.date()),"entry_period":entry_period,
        "policy":f"hybrid_base_{base_allocation_pct}_adaptive_reserve_{100-base_allocation_pct}",
        "base_allocation_pct":base_allocation_pct,"adaptive_reserve_pct":100-base_allocation_pct,
        "base_budget_aud":base_budget,"adaptive_reserve_budget_aud":reserve_budget,
        "base_btc":base_btc,"adaptive_reserve_btc":reserve_btc,
        "base_buy_count":base_count,"adaptive_buy_count":reserve_count,"total_buy_count":base_count+reserve_count,
        "base_outlay_aud":base_spent,"adaptive_outlay_aud":reserve_spent,"total_cash_outlay_aud":total_spent,
        "largest_weekly_combined_outlay_aud":max(weekly_spend.values(),default=0.),
        "weekly_cap_aud":weekly_cap,"btc_accumulated":total_btc,
        "cash_remaining_aud":base_cash+reserve_cash,"base_cash_remaining_aud":base_cash,
        "adaptive_cash_remaining_aud":reserve_cash,"cash_budget_deployed_pct":100*total_spent/budget_aud,
        "effective_vwap_aud_per_btc":vwap,"cohort_104w_low_aud":low,
        "vwap_premium_to_cohort_low_pct":100*(vwap/low-1) if vwap else None,
        "terminal_btc_value_aud":total_btc*terminal_price,
        "terminal_equity_aud":base_cash+reserve_cash+total_btc*terminal_price,
        "trigger_date":str(trigger.date()) if trigger is not None else None,
        "weeks_until_trigger":(trigger-enrol).days/7 if trigger is not None else None,
    }
    result.update(fixed)
    return result


def run_all_hybrid_cohorts(btc_usd,usd_per_aud,*,budget_aud=DEFAULT_BUDGET_AUD):
    btc=_series(btc_usd,"BTC/USD");fx=_series(usd_per_aud,"USD per AUD")
    price=_aud_prices(btc,fx);rows=[]
    for start in quarterly_enrolment_dates():
        enrol=pd.Timestamp(start,tz="UTC");terminal=enrol+pd.Timedelta(days=7*COHORT_WEEKS)
        if enrol not in price.index or terminal not in price.index:continue
        for pct in BASE_ALLOCATIONS:
            try:
                rows.append(run_hybrid_cohort(btc,fx,enrolment_date=start,
                    base_allocation_pct=pct,budget_aud=budget_aud))
            except ValueError as exc:
                if "Missing complete weekly cohort prices" in str(exc):continue
                raise
    return pd.DataFrame(rows)


def hybrid_summary_table(cohorts):
    if not isinstance(cohorts,pd.DataFrame) or cohorts.empty:
        raise ValueError("Completed hybrid cohort results required")
    rows=[]
    for entry_period,group in cohorts.groupby("entry_period"):
        for policy,sub in group.groupby("policy"):
            btc_uplift=pd.Series(100*(sub.btc_accumulated.to_numpy()/sub.fixed_weekly_btc.to_numpy()-1),index=sub.index)
            equity_uplift=pd.Series(100*(sub.terminal_equity_aud.to_numpy()/sub.fixed_weekly_terminal_equity_aud.to_numpy()-1),index=sub.index)
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
                "median_paired_equity_uplift_vs_fixed_weekly_pct":float(equity_uplift.median()),
                "cohort_btc_win_rate_vs_fixed_weekly_pct":100*float((btc_uplift>0).mean()),
                "cohort_equity_win_rate_vs_fixed_weekly_pct":100*float((equity_uplift>0).mean()),
                "triggered_median_paired_btc_uplift_pct":float(btc_uplift.loc[active].median()) if active.any() else None,
                "triggered_btc_win_rate_pct":100*float((btc_uplift.loc[active]>0).mean()) if active.any() else None,
                "triggered_median_paired_equity_uplift_pct":float(equity_uplift.loc[active].median()) if active.any() else None,
                "triggered_equity_win_rate_pct":100*float((equity_uplift.loc[active]>0).mean()) if active.any() else None,
                "weekly_cap_compliant":bool(sub.largest_weekly_combined_outlay_aud.le(sub.weekly_cap_aud+1e-6).all()),
            })
    return pd.DataFrame(rows).sort_values(["entry_period","base_allocation_pct"]).reset_index(drop=True)
