"""Calendar-enrolled replay of the existing prospective adaptive-recovery policy.

Research-only. Uses the exact existing adaptive_recovery percentage helper,
but tests it from declared calendar enrolment dates with a fresh fixed AUD
budget. No cohort starts at a retrospectively selected cycle low.
"""
from __future__ import annotations

from datetime import date
import math
from pathlib import Path
import hashlib
import json

import pandas as pd

from engines.research.shared_cycle_policy import recovery_buy_budget_fraction

POLICIES=("fixed_weekly","remaining_cash_2_5pct_below_200wma","adaptive_recovery")
DEFAULT_BUDGET_AUD=292_383.0
DEFAULT_CAPITAL_AUD=510_000.0
DEFAULT_CASH_YIELD=0.05
DEFAULT_WEEKLY_CAP_PCT=5.0
DEFAULT_BUY_FRICTION=0.003
DEFAULT_FEE_AUD=3.0
COHORT_WEEKS=104
ENTRY_START=date(2017,1,2)
HOLDOUT_START=date(2022,1,1)


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
        rate=float(fx.iloc[pos])
        if rate<=0:continue
        out[day]=float(usd)/rate
    return pd.Series(out,name="btc_aud").sort_index()


def _prior_200wma_ratio(price,day):
    day=pd.Timestamp(day)
    if day.tzinfo is None:day=day.tz_localize("UTC")
    else:day=day.tz_convert("UTC")
    prior=day-pd.Timedelta(days=1)
    if prior not in price.index:
        return None
    dates=[prior-pd.Timedelta(days=7*i) for i in range(200)]
    if not pd.DatetimeIndex(dates).isin(price.index).all():
        return None
    ma=float(price.loc[dates].mean())
    if not math.isfinite(ma) or ma<=0:return None
    return float(price.loc[prior])/ma


def _buy(cash,day,price,target,*,weekly_cap,friction,fee):
    target=min(max(0.,target),max(0.,weekly_cap-fee),max(0.,cash-fee))
    if target<100.:
        return cash,0.,0.,0.
    units=target*(1-friction)/price
    outlay=target+fee
    if outlay>cash+1e-8 or outlay>weekly_cap+1e-8:
        raise AssertionError("Purchase cap or cash exceeded")
    return cash-outlay,units,outlay,target


def _simulate(name,dates,price,budget,capital,cash_yield,weekly_cap,friction,fee,cohort_low,enrolment):
    cash=float(budget)
    btc=0.
    spent=0.
    gross=0.
    buys=0
    amounts=[]
    buy_dates=[]
    previous=pd.Timestamp(enrolment)
    for day in dates:
        day=pd.Timestamp(day)
        elapsed=(day-previous).days
        if elapsed<0:raise ValueError("Execution dates not monotonic")
        cash*=((1+cash_yield)**(elapsed/365.25))
        previous=day
        if day not in price.index:continue
        px=float(price.loc[day])
        ratio=_prior_200wma_ratio(price,day)
        if name=="fixed_weekly":
            target=budget/COHORT_WEEKS
        elif name=="remaining_cash_2_5pct_below_200wma":
            target=0.025*cash if ratio is not None and ratio<1.0 else 0.
        elif name=="adaptive_recovery":
            target=0.
        else:raise ValueError("Unknown policy")
        if target<=0:continue
        cash,units,outlay,consideration=_buy(
            cash,day,px,target,weekly_cap=weekly_cap,friction=friction,fee=fee)
        if units:
            btc+=units;spent+=outlay;gross+=consideration;buys+=1
            amounts.append(outlay);buy_dates.append(day)
    terminal=dates[-1]
    elapsed=(terminal-previous).days
    if elapsed>0:cash*=((1+cash_yield)**(elapsed/365.25))
    final_btc_value=btc*float(price.loc[terminal]) if terminal in price.index else None
    final_equity=cash+final_btc_value if final_btc_value is not None else None
    vwap=spent/btc if btc else None
    premium=100*(vwap/cohort_low-1) if btc and cohort_low>0 else None
    return {
        "policy":name,"btc_accumulated":btc,"cash_remaining_aud":cash,
        "total_cash_outlay_aud":spent,"gross_buy_consideration_aud":gross,
        "buy_count":buys,"effective_vwap_aud_per_btc":vwap,
        "cohort_104w_low_aud":cohort_low,"vwap_premium_to_cohort_low_pct":premium,
        "terminal_btc_value_aud":final_btc_value,"terminal_equity_aud":final_equity,
        "cash_budget_deployed_pct":100*spent/budget,
        "buy_dates":[str(d.date()) for d in buy_dates],
    }


def _adaptive_schedule(price,enrol,end):
    start=pd.Timestamp(enrol)+pd.Timedelta(days=1)
    trigger=None
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


def run_cohort(btc_usd,usd_per_aud,*,enrolment_date,budget_aud=DEFAULT_BUDGET_AUD,
               capital_aud=DEFAULT_CAPITAL_AUD,cash_yield=DEFAULT_CASH_YIELD,
               weekly_cap_pct=DEFAULT_WEEKLY_CAP_PCT,buy_friction=DEFAULT_BUY_FRICTION,
               fee_aud=DEFAULT_FEE_AUD):
    btc=_series(btc_usd,"BTC/USD")
    fx=_series(usd_per_aud,"USD per AUD")
    price=_aud_prices(btc,fx)
    enrol=pd.Timestamp(enrolment_date,tz="UTC").normalize()
    end=enrol+pd.Timedelta(days=7*COHORT_WEEKS)
    dates=[enrol+pd.Timedelta(days=7*i) for i in range(1,COHORT_WEEKS+1)]
    if enrol not in price.index or end not in price.index:
        raise ValueError("Calendar cohort requires dated enrolment and 104-week terminal prices")
    if any(d not in price.index for d in dates):
        raise ValueError("Missing weekly execution price; cohort not imputed")
    window=price.loc[enrol:end]
    low=float(window.min())
    weekly_cap=capital_aud*weekly_cap_pct/100.
    fixed=_simulate("fixed_weekly",dates,price,budget_aud,capital_aud,cash_yield,weekly_cap,buy_friction,fee_aud,low)
    below=_simulate("remaining_cash_2_5pct_below_200wma",dates,price,budget_aud,capital_aud,cash_yield,weekly_cap,buy_friction,fee_aud,low)
    schedule,trigger=_adaptive_schedule(price,enrol,end)
    adaptive_dates=schedule
    adaptive=_simulate("adaptive_recovery",adaptive_dates,price,budget_aud,capital_aud,cash_yield,weekly_cap,buy_friction,fee_aud,low) if adaptive_dates else {
        "policy":"adaptive_recovery","btc_accumulated":0.,"cash_remaining_aud":budget_aud*((1+cash_yield)**(7*COHORT_WEEKS/365.25)),
        "total_cash_outlay_aud":0.,"gross_buy_consideration_aud":0.,"buy_count":0,
        "effective_vwap_aud_per_btc":None,"cohort_104w_low_aud":low,"vwap_premium_to_cohort_low_pct":None,
        "terminal_btc_value_aud":0.,"terminal_equity_aud":budget_aud*((1+cash_yield)**(7*COHORT_WEEKS/365.25)),
        "cash_budget_deployed_pct":0.,"buy_dates":[],
    }
    # Replace generic adaptive targets with exact original-budget weekly fractions,
    # retaining existing signal/size helper, 5%-capital cap and cash yield.
    adaptive_cash=float(budget_aud);adaptive_btc=adaptive_spent=adaptive_gross=0.;adaptive_count=0
    adaptive_dates=[];previous=enrol
    for day in schedule:
        elapsed=(day-previous).days
        adaptive_cash*=((1+cash_yield)**(elapsed/365.25));previous=day
        px=float(price.loc[day])
        signal=recovery_buy_budget_fraction(btc,day,style="adaptive_recovery")
        target=budget_aud*signal["fraction_of_initial_buyback_cash"]
        adaptive_cash,units,outlay,consideration=_buy(
            adaptive_cash,day,px,target,weekly_cap=weekly_cap,buy_friction=buy_friction,fee=fee_aud)
        if units:
            adaptive_btc+=units;adaptive_spent+=outlay;adaptive_gross+=consideration
            adaptive_count+=1;adaptive_dates.append(day)
    if schedule:
        elapsed=(end-previous).days
        if elapsed>0:adaptive_cash*=((1+cash_yield)**(elapsed/365.25))
    adaptive_vwap=adaptive_spent/adaptive_btc if adaptive_btc else None
    adaptive.update({
        "btc_accumulated":adaptive_btc,"cash_remaining_aud":adaptive_cash,
        "total_cash_outlay_aud":adaptive_spent,"gross_buy_consideration_aud":adaptive_gross,
        "buy_count":adaptive_count,"effective_vwap_aud_per_btc":adaptive_vwap,
        "vwap_premium_to_cohort_low_pct":100*(adaptive_vwap/low-1) if adaptive_vwap else None,
        "terminal_btc_value_aud":adaptive_btc*float(price.loc[end]),
        "terminal_equity_aud":adaptive_cash+adaptive_btc*float(price.loc[end]),
        "cash_budget_deployed_pct":100*adaptive_spent/budget_aud,
        "buy_dates":[str(d.date()) for d in adaptive_dates],
    })
    return {
        "enrolment_date":str(enrol.date()),"terminal_date":str(end.date()),
        "validation_split":"train" if enrol.date()<HOLDOUT_START else "holdout",
        "trigger_date":str(trigger.date()) if trigger is not None else None,
        "weeks_until_trigger":(trigger-enrol).days/7 if trigger is not None else None,
        "cohort_104w_low_aud":low,"terminal_btc_aud_price":float(price.loc[end]),
        "cash_yield_annual_pct":100*cash_yield,"budget_aud":budget_aud,
        "weekly_cap_aud":weekly_cap,"results":[fixed,below,adaptive],
    }


def quarterly_enrolment_dates(first=ENTRY_START):
    dates=[]
    current=pd.Timestamp(first,tz="UTC").normalize()
    # first Monday of each calendar quarter, predeclared and not optimized.
    for year in range(current.year,2026):
        for month in (1,4,7,10):
            d=pd.Timestamp(date(year,month,1),tz="UTC")
            d+=pd.Timedelta(days=(7-d.weekday())%7)
            if d>=current:dates.append(d)
    return [d.date() for d in dates]


def run_all_cohorts(btc_usd,usd_per_aud,*,budget_aud=DEFAULT_BUDGET_AUD):
    btc=_series(btc_usd,"BTC/USD")
    fx=_series(usd_per_aud,"USD per AUD")
    price=_aud_prices(btc,fx)
    rows=[]
    for start in quarterly_enrolment_dates():
        terminal=pd.Timestamp(start,tz="UTC")+pd.Timedelta(days=7*COHORT_WEEKS)
        if start not in price.index or terminal not in price.index:continue
        try:
            cohort=run_cohort(btc,fx,enrolment_date=start,budget_aud=budget_aud)
        except ValueError as exc:
            if "Missing weekly execution price" in str(exc):continue
            raise
        for result in cohort["results"]:
            rows.append({k:v for k,v in cohort.items() if k!="results"}|result)
    return pd.DataFrame(rows)


def summary_table(cohorts):
    if not isinstance(cohorts,pd.DataFrame) or cohorts.empty:
        raise ValueError("Completed cohort results required")
    rows=[]
    for split,group in cohorts.groupby("validation_split"):
        for policy,sub in group.groupby("policy"):
            rows.append({
                "split":split,"policy":policy,"cohort_count":len(sub),
                "median_btc_accumulated":float(sub.btc_accumulated.median()),
                "median_vwap_aud":float(sub.effective_vwap_aud_per_btc.dropna().median()) if sub.effective_vwap_aud_per_btc.notna().any() else None,
                "median_cash_remaining_aud":float(sub.cash_remaining_aud.median()),
                "median_cash_deployed_pct":float(sub.cash_budget_deployed_pct.median()),
                "median_vwap_premium_to_104w_low_pct":float(sub.vwap_premium_to_cohort_low_pct.dropna().median()) if sub.vwap_premium_to_cohort_low_pct.notna().any() else None,
                "median_terminal_equity_aud":float(sub.terminal_equity_aud.median()),
                "cohort_win_rate_btc_vs_fixed_weekly_pct":100*float((sub.btc_accumulated>group.loc[group.enrolment_date.isin(sub.enrolment_date),"btc_accumulated"].median()).mean()) if policy!="fixed_weekly" else 0.,
            })
    return pd.DataFrame(rows).sort_values(["split","policy"]).reset_index(drop=True)
