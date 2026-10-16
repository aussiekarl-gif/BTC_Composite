"""Research only: causal Day-500 sell -> later BUY-BACK in AUD, with SMSF tax.

Primary cycles: 2017 and 2021 complete observation windows; 2025 to the
available data cutoff is RIGHT-CENSORED. Deliberately exclude 2013 from
primary statistics at user's instruction; do not delete its evidence or
mislabel the remaining cycles as independent out-of-sample.

Self-financing shadow portfolios each start with AUD500,000 at the
corresponding halving date and purchase BTC on that date. This is a
MATHEMATICAL matched-start historical thought experiment, emphatically
NOT the real user's AUD500k actually starting in 2026.

Price feed: Oct-2026 archived BlockHorizon BTC/USD daily price field;
FX: Frankfurter historical USD->AUD observed on/before previous day.
Model AUD3 per fill, FIFO simplified SMSF accumulation 10% effective
tax on >12-month capital gains, 15% short, immediate cash tax escrow.
Potential CGT losses and actual SMSF fund phase can materially alter tax.
No ETF cost, FX broker spread, cash yield or executable close guarantees.

Sale schedule: existing day500 5% then dynamic 90%-core and optional
20%-holdback models, plus six-day 525..560 staged control. Buy-back
starts after sales STOP, requires a PRIOR completed close >= a threshold
below its own 365-day trailing BTC/USD high and then 24 weeks of
weighted buying. No future cycle bottom is used. Cash is never
silently forced back into BTC; report residual cash and BTC-equivalent.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd
import requests

from engines.research.day500_dynamic_dca_out import staged_day500_dynamic_exit
from engines.research.smsf_self_financing_replay import AuditSmsfAccount
from engines.research.top_signal_horse_race import HALVINGS,read_exported_history
from engines.research.verified_recent_price_bridge import parse_frankfurter_fx

INITIAL_AUD=500_000.
SCORE_DAYS=1150
BUY_WEEKS=24
BUY_DURATION_TESTS=(24,52)
WMA_BUY_DURATION_TESTS=(12,24,52)
WMA_DYNAMIC_STYLES=("adaptive_value","adaptive_recovery")
DELAY_DAYS_AFTER_LAST_SELL=14
GATES=(.40,.55,.65)
SELLERS=("fixed_525_to_560","dynamic_90pct","dynamic_90pct_holdback20pct")
PRIMARY={
    "2017":{"halving":"2016-07-09"},
    "2021":{"halving":"2020-05-11"},
    "2025":{"halving":"2024-04-20"},
}


def fetch_fx_for_cycle(halving,end,*,timeout=35):
    """Fetch ONLY the required calendar period; no future-day FX on trades."""
    beg=(pd.Timestamp(halving)-pd.Timedelta(days=10)).date()
    finish=pd.Timestamp(end).date()
    url=f"https://api.frankfurter.app/{beg}..{finish}"
    response=requests.get(url,params={"from":"USD","to":"AUD"},
                          timeout=timeout,headers={"User-Agent":"BTC-Composite-Research/1.0"})
    response.raise_for_status()
    return parse_frankfurter_fx(response.json())


def fx_before(fx,day):
    """Latest FX observation strictly BEFORE executed close day."""
    day=pd.Timestamp(day)
    if day.tzinfo is None:day=day.tz_localize("UTC")
    else:day=day.tz_convert("UTC")
    prior=fx.loc[fx.index<day]
    if prior.empty or (day-prior.index[-1]).days>7:
        raise ValueError(f"No safely prior historical USD/AUD exchange rate for {day}")
    return float(prior.iloc[-1]["aud_per_usd"])


def sell_orders(price,halving,policy):
    if policy=="fixed_525_to_560":
        days=(525,532,539,546,553,560)
        weights=np.arange(6.,0.,-1)
        weights/=weights.sum()
        return [{"day":halving+pd.Timedelta(days=i),"fraction":float(w)}
                for i,w in zip(days,weights)]
    if policy not in ("dynamic_90pct","dynamic_90pct_holdback20pct"):
        raise ValueError("Unknown sell policy")
    variant=("maturity_90pct" if policy=="dynamic_90pct"
             else "maturity_90pct_holdback20pct")
    model=staged_day500_dynamic_exit(price,halving,policy=variant,
                                     review_day=min(SCORE_DAYS,(price.index[-1]-halving).days))
    return [{"day":pd.Timestamp(x["date"],tz="UTC"),"fraction":float(x["btc_sold"])}
            for x in model["sale_detail"]]


def causal_buyback_dates(price,*,start,gate,terminal,weekly_limit=BUY_WEEKS,
                         entry_mode="drawdown",buyback_style="fixed"):
    """Strictly prior 365-day drawdown gate, followed by weekly buys.

    One-time activation; no hindsight minimum/maximum prices. Once the
    buy phase starts, fractional sizes are linked to *prior-day*
    historical drawdown, so bigger discounts acquire larger fractions.
    """
    if entry_mode not in ("drawdown","below_200wma"):
        raise ValueError("Invalid buyback entry mode")
    if entry_mode=="drawdown" and not 0<gate<1:
        raise ValueError("Invalid drawdown gate")
    i_start=price.index.searchsorted(start)
    prior_px=price.to_numpy(float)
    dates=price.index
    trigger=None
    minimum=(365 if entry_mode=="drawdown" else 1400)
    for i in range(max(minimum,i_start),len(dates)):
        now=dates[i]
        if now>terminal:break
        prior=float(prior_px[i-1])
        if entry_mode=="drawdown":
            hist=prior_px[i-365:i]
            eligible=(1-prior/float(max(hist))>=gate)
        else:
            # 200 weekly samples, exactly one per 7 days, all completed
            # BEFORE today's execution. One-day data cannot be used as
            # part of the week's pre-decision moving average.
            indexes=i-1-7*np.arange(200)
            if np.min(indexes)<0:raise AssertionError("Unwarmed WMA")
            ma200=float(np.mean(prior_px[indexes]))
            eligible=prior<ma200
        if eligible:
            trigger=now
            break
    if trigger is None:return None,[]
    potential=pd.date_range(trigger,terminal,freq="7D",tz="UTC")
    if len(potential)==0:return trigger,[]
    count=min(len(potential),weekly_limit)
    plans=[]
    for t in potential[:count]:
        pos=int(dates.searchsorted(t))
        if pos>=len(dates) or dates[pos]!=t:raise ValueError("Missing dated BTC close")
        seen=prior_px[max(0,pos-365):pos]
        drawdown=max(0.,1-prior_px[pos-1]/max(seen))
        # Cap risk-weighting to keep cash in later weekly tranches.
        threshold=gate if entry_mode=="drawdown" else .40
        weight=min(2.5,max(.5,1.+3.*(drawdown-threshold)))
        plans.append({"day":t,"weight":float(weight)})
    return trigger,plans


def simulate_roundtrip(price,fx,halving,terminal,*,seller,gate,
                       initial_aud=INITIAL_AUD,buyback_weeks=BUY_WEEKS,
                       entry_mode="drawdown"):
    """Replay FIFO SMSF with actual AUD spot conversion and bounded BTC."""
    if initial_aud<=3:raise ValueError("Cash must cover entry brokerage")
    if not isinstance(buyback_weeks,int) or buyback_weeks<1:
        raise ValueError("Invalid buyback duration")
    if buyback_style not in ("fixed",)+WMA_DYNAMIC_STYLES:
        raise ValueError("Invalid buyback policy") 
    if buyback_style!="fixed" and entry_mode!="below_200wma":
        raise ValueError("Adaptive style requires strict-prior 200WMA gate")
    start=halving
    if start not in price.index:raise ValueError("Missing dated halving price")
    if terminal not in price.index:raise ValueError("Missing dated terminal price")
    # Buy BTC at halving price for both independent accounts.
    start_aud=float(price.loc[start])*fx_before(fx,start)
    actual=AuditSmsfAccount(initial_aud,fee=3.,tax=True)
    held=AuditSmsfAccount(initial_aud,fee=3.,tax=True)
    assert actual.buy(start,start_aud,1.)
    assert held.buy(start,start_aud,1.)
    original_btc=actual.btc
    events=sell_orders(price,halving,seller)
    events=[e for e in events if e["day"]<=terminal]
    prev=None
    if events:
        if any(e["day"]<halving+pd.Timedelta(days=500) for e in events):
            raise AssertionError("Sold before day500")
        total_fraction=sum(e["fraction"] for e in events)
        if total_fraction>1+1e-8:raise ValueError("Sell schedule overdrawn")
        for e in events:
            when=e["day"]
            if when not in price.index:raise ValueError("Sell close unavailable")
            pre_qty=actual.btc
            target=min(pre_qty,original_btc*e["fraction"])
            if target>1e-12:
                assert actual.sell(when,float(price.loc[when])*fx_before(fx,when),
                                   min(1.,target/pre_qty))
            prev=when
    waiting=(prev or halving+pd.Timedelta(days=500))+pd.Timedelta(days=DELAY_DAYS_AFTER_LAST_SELL)
    trigger,plan=causal_buyback_dates(
        price,start=waiting,gate=gate,terminal=terminal,
        weekly_limit=(buyback_weeks if buyback_style=="fixed" else 10000),
        entry_mode=entry_mode)
    bought=[]
    if plan and actual.cash>100.:
        # Weighted DCA over 24 weeks; never adapt using future entry prices.
        # Predictably invest the reserved NET sale proceeds each eligible
        # weekly day. Initial cash (if any) is included; no new funding.
        # Critically, all weights are computed from prior observations.
        # Budgeting with future weights before the first order would
        # create LOOKAHEAD. Instead use a causal fractional target:
        # reserve 24 weekly tranches (not truncated to current data
        # horizon), and scale tranche from observed discount.
        initial_budget=actual.cash
        target=initial_budget/buyback_weeks
        prices=price.to_numpy(float)
        for j,e in enumerate(plan):
            day=e["day"]
            if buyback_style=="fixed":
                gross=min(actual.cash,target*e["weight"])
                # Only the final fixed-schedule week forces deployment.
                if j==buyback_weeks-1:gross=actual.cash
            else:
                pos=int(price.index.searchsorted(day))
                indexes=pos-1-7*np.arange(200)
                if np.min(indexes)<0:
                    raise AssertionError("Historical 200WMA not warmed")
                ma200=float(np.mean(prices[indexes]))
                prior=float(prices[pos-1])
                ratio=prior/ma200
                if buyback_style=="adaptive_value":
                    # Buy deepest BTC/USD discounts the most; accelerate
                    # near a modest WMA reclaim, taper into strength.
                    frac=(.10 if ratio<=.85 else
                          .035 if ratio<=1.0 else
                          .12 if ratio<=1.25 else
                          .04 if ratio<=1.5 else .01)
                else:
                    # Alternative independent momentum confirmation:
                    # reserve more in capitulation and increase pace
                    # after observable 50-day average recovery.
                    recent=float(np.mean(prices[pos-50:pos]))
                    earlier=float(np.mean(prices[pos-64:pos-14]))
                    strengthening=(prior>recent and recent>earlier)
                    frac=(.025 if ratio<=1.0 else
                          .15 if ratio<=1.25 and strengthening else
                          .045 if ratio<=1.5 else .01)
                gross=min(actual.cash,initial_budget*frac)
            if gross>100.:
                if actual.buy(day,float(price.loc[day])*fx_before(fx,day),
                              min(1.,gross/actual.cash)):
                    bought.append(str(day.date()))
    terminal_px_aud=float(price.loc[terminal])*fx_before(fx,terminal)
    terminal_mark=actual.mark(terminal_px_aud)
    held_mark=held.mark(terminal_px_aud)
    total_original=original_btc
    rebuy_orders=[
        x for x in actual.orders if x["side"]=="BUY"
        and pd.Timestamp(x["date"])>start
    ]
    total_new_btc=sum(float(x["btc"]) for x in rebuy_orders)
    total_new_usd=sum(float(x["gross_aud"])/fx_before(fx,x["date"])
                      for x in rebuy_orders)
    effective_buy_usd=(
        total_new_usd/total_new_btc if total_new_btc>1e-9 else None)
    # This is a HINDSIGHT-only scoring window, NOT a trade signal.
    # Bottom counted since final sale until available terminal observation.
    if prev is not None and prev<=terminal:
        observed_post_sale=price.loc[prev:terminal]
        hindsight_low=float(observed_post_sale.min())
        hindsight_low_date=str(observed_post_sale.idxmin().date())
    else:
        hindsight_low=hindsight_low_date=None
    return {
        "seller":seller,
        "buyback_entry_mode":entry_mode,
        "buyback_prior_drawdown_gate_pct":(
            round(100*gate,1) if entry_mode=="drawdown" else None),
        "planned_buyback_weeks":(
            buyback_weeks if buyback_style=="fixed" else None),
        "buyback_style":buyback_style,
        "average_repurchase_usd_per_btc":(
            round(effective_buy_usd,2) if effective_buy_usd is not None else None),
        "post_sale_hindsight_low_close_usd":(
            round(hindsight_low,2) if hindsight_low is not None else None),
        "post_sale_hindsight_low_date":hindsight_low_date,
        "buyback_error_above_post_sale_low_pct":(
            round(100*(effective_buy_usd/hindsight_low-1),3)
            if effective_buy_usd is not None and hindsight_low is not None
            else None),
        "initial_btc_before_selling":round(total_original,8),
        "sell_count":sum(x["side"]=="SELL" for x in actual.orders),
        "buyback_buy_count":len(bought),
        "buyback_trigger_date":str(trigger.date()) if trigger is not None else None,
        "first_buyback_execution":bought[0] if bought else None,
        "last_buyback_execution":bought[-1] if bought else None,
        "btc_held_after_buyback":round(actual.btc,8),
        "cash_remaining_aud":round(actual.cash,2),
        "btc_equivalent_at_terminal_including_cash":round(
            actual.btc+actual.cash/terminal_px_aud,8),
        "btc_equivalent_relative_to_hold_pct":round(
            100*((actual.btc+actual.cash/terminal_px_aud)/held.btc-1),3),
        "marked_account_value_aud":round(terminal_mark,2),
        "hold_same_start_value_aud":round(held_mark,2),
        "marked_value_vs_hold_pct":round(100*(terminal_mark/held_mark-1),3),
        "hypothetical_liquidated_after_cgt_aud":round(
            actual.liquidation_value(terminal,terminal_px_aud),2),
        "hold_hypothetical_liquidated_after_cgt_aud":round(
            held.liquidation_value(terminal,terminal_px_aud),2),
        "realised_smsf_cgt_paid_est_aud":round(actual.total_tax,2),
        "orders_total":len(actual.orders),
        "brokerage_aud":round(actual.total_fees,2),
        "residual_coin_share_of_original":round(actual.btc/original_btc,5),
        "entry_sold_fraction":round(sum(
            x["btc"] for x in actual.orders if x["side"]=="SELL")/original_btc,5),
    }


def evaluate(historical,*, fx_for_cycle=fetch_fx_for_cycle):
    price=historical["price_usd"].loc[:"2026-10-05"].copy()
    out=[]
    for cycle,item in PRIMARY.items():
        halving=pd.Timestamp(item["halving"],tz="UTC")
        desired=halving+pd.Timedelta(days=SCORE_DAYS)
        terminal=min(desired,price.index[-1])
        if terminal not in price.index:raise ValueError("Final sample close missing")
        fx=fx_for_cycle(halving,terminal)
        strategies=[
            simulate_roundtrip(price,fx,halving,terminal,
                               seller=seller,gate=gate,
                               buyback_weeks=duration)
            for seller in SELLERS for gate in GATES
            for duration in BUY_DURATION_TESTS
        ]
        strategies.extend(
            simulate_roundtrip(price,fx,halving,terminal,
                               seller=seller,gate=.40,
                               buyback_weeks=duration,
                               entry_mode="below_200wma")
            for seller in SELLERS
            for duration in WMA_BUY_DURATION_TESTS
        )
        strategies.extend(
            simulate_roundtrip(price,fx,halving,terminal,
                               seller=seller,gate=.40,
                               buyback_weeks=52,entry_mode="below_200wma",
                               buyback_style=style)
            for seller in SELLERS
            for style in WMA_DYNAMIC_STYLES
        )
        out.append({
            "cycle":cycle,
            "halving":str(halving.date()),
            "day500":str((halving+pd.Timedelta(days=500)).date()),
            "target_day1150":str(desired.date()),
            "asof_data_terminal":str(terminal.date()),
            "complete_day1150_observation":bool(terminal==desired),
            "days_observed_since_halving":int((terminal-halving).days),
            "initial_aud_invested_at_halving":INITIAL_AUD,
            "models":strategies,
        })
    summary=[]
    for seller in SELLERS:
      for gate in GATES:
       for duration in BUY_DURATION_TESTS:
        cohort=[next(m for m in row["models"]
                     if m["seller"]==seller and
                        m["buyback_prior_drawdown_gate_pct"]==round(100*gate,1)
                     and m["planned_buyback_weeks"]==duration)
                for row in out if row["complete_day1150_observation"]]
        summary.append({
            "seller":seller,"buyback_gate_pct":round(100*gate,1),
            "buyback_weeks":duration,
            "complete_cycles":len(cohort),
            "better_btc_equivalent_than_hold":sum(
                m["btc_equivalent_relative_to_hold_pct"]>0 for m in cohort),
            "mean_btc_equivalent_lift_pct":round(float(np.mean(
                [m["btc_equivalent_relative_to_hold_pct"] for m in cohort])),3)
                if cohort else None,
            "min_btc_equivalent_lift_pct":round(float(np.min(
                [m["btc_equivalent_relative_to_hold_pct"] for m in cohort])),3)
                if cohort else None,
        })
    for seller in SELLERS:
      for duration in WMA_BUY_DURATION_TESTS:
        cohort=[next(m for m in row["models"]
                     if m["seller"]==seller
                     and m["buyback_entry_mode"]=="below_200wma"
                     and m["planned_buyback_weeks"]==duration)
                for row in out if row["complete_day1150_observation"]]
        summary.append({
            "seller":seller,"buyback_gate_pct":None,
            "buyback_entry_mode":"below_200wma",
            "buyback_weeks":duration,
            "complete_cycles":len(cohort),
            "better_btc_equivalent_than_hold":sum(
                m["btc_equivalent_relative_to_hold_pct"]>0 for m in cohort),
            "mean_btc_equivalent_lift_pct":round(float(np.mean(
                [m["btc_equivalent_relative_to_hold_pct"] for m in cohort])),3)
                if cohort else None,
            "min_btc_equivalent_lift_pct":round(float(np.min(
                [m["btc_equivalent_relative_to_hold_pct"] for m in cohort])),3)
                if cohort else None,
        })
    for seller in SELLERS:
      for style in WMA_DYNAMIC_STYLES:
        cohort=[next(m for m in row["models"]
                     if m["seller"]==seller
                     and m["buyback_entry_mode"]=="below_200wma"
                     and m["buyback_style"]==style)
                for row in out if row["complete_day1150_observation"]]
        summary.append({
            "seller":seller,"buyback_gate_pct":None,
            "buyback_entry_mode":"below_200wma",
            "buyback_style":style,"buyback_weeks":None,
            "complete_cycles":len(cohort),
            "better_btc_equivalent_than_hold":sum(
                m["btc_equivalent_relative_to_hold_pct"]>0 for m in cohort),
            "mean_btc_equivalent_lift_pct":round(float(np.mean(
                [m["btc_equivalent_relative_to_hold_pct"] for m in cohort])),3)
                if cohort else None,
            "min_btc_equivalent_lift_pct":round(float(np.min(
                [m["btc_equivalent_relative_to_hold_pct"] for m in cohort])),3)
                if cohort else None,
        })
    return {
        "research_only":True,
        "primary_cycles":["2017","2021"],
        "partially_observed_cycle":"2025",
        "2013_excluded_from_primary":True,
        "historical_source_last_day":str(price.index[-1].date()),
        "initial_per_shadow_account_aud":INITIAL_AUD,
        "method":"Self-financing shadow BTC purchased at the historical halving date, sold after day500 and repurchased via lagged 365-day drawdown; matched hold buys at same date.",
        "strategies":out,
        "complete_cycle_summary":summary,
        "warnings":[
            "User chose to omit 2013 from PRIMARY optimisation; its historical failure remains documented and is not deleted.",
            "The user's real AUD500k BTC/ETF purchases begin 2026, not historical halving dates. These are NOT real holdings, profits or trade suggestions.",
            "2025 cycle has not reached post-halving day1150: mark RIGHT CENSORED. Scores observed to last available 2026 BTC daily record only.",
            "All thresholds already historically inspected; no untouched prospective holdout. Two complete modern sell/buyback periods are statistically inadequate.",
            "AUD500k shadow portfolio initial BTC acquired at halving; embedded starting tax basis is a hypothetical cost assumption.",
            "24- and 52-week buyback windows are fixed duration comparison controls. Buyers invest on 24/52 eligible weekly dates, with a previous-day-drawdown multiplier and no hindsight prices.",
            "The post-sale low is computed using FUTURE observed closes for EVALUATION only, never entry; 2025 remains provisional/right-censored.",
            "Strict-prior 200-week BTC/USD moving-average threshold is a separate buyer activation; each week's source is sampled 7 days apart ending at t-1, not hindsight interpolated.",
            "Whether price touches the 200WMA in a future bull/bear regime is not assured; a no-trigger scenario means no buyback and AUD cash remains.",
            "Adaptive WMA buying has NO fixed terminal deadline, and releases fixed fractions of initial after-tax cash at each qualifying observed price/WMA ratio; no future weights or forced liquidation.",
            "The adaptive-value and adaptive-recovery DCA sizing parameters were inspired by the inspected 2018/2022/2026 periods, so their apparent historical success is wholly in-sample.",
            "A low buyback VWAP error does not imply it will reproduce next cycle; variation in purchase dates, FX and 52-week periods matters.",
            "Frankfurter USD/AUD FX strictly BEFORE transaction day, no future same-day FX leakage; priced BTC/USD daily historical archive may not be executable.",
            "Fees AUD3 each buy/sell, simplified FIFO eligible 10% long-held and 15% short-held SMSF accrual held in cash immediately; not actual fund annual taxation.",
            "ETF tracking, fee, spreads, SMSF expenses, FX conversion spreads, and cash yields excluded.",
            "BTC-equivalent metric includes remaining AUD cash at final BTC/AUD; separately disclose BTC physically held and uninvested cash.",
            "No Production, portfolio, master or Google Sheets mutation.",
        ],
    }


def main():
    p=argparse.ArgumentParser()
    p.add_argument("--output",default="")
    args=p.parse_args()
    data=read_exported_history()
    result=evaluate(data)
    text=json.dumps(result,indent=2,allow_nan=False)
    if args.output:
        Path(args.output).write_text(text+"\n",encoding="utf-8")
    print(text)


if __name__=="__main__":
    main()
