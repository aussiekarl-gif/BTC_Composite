"""Research-only test: reserve half original BUY cash until *deeper* 200WMA.

ONE predeclared alternative to original day500 SELL -> 200WMA weekly BUY:
- ORIGINAL first strict prior BTC close below strict prior 200 WEEK average
  (not 200 DAY), no earlier than halving+744, unchanged for both.
- Original weekly 2.5/15/4.5/1%-of-fixed-initial-aftertax-rebuy-cash
  adaptive recovery schedule continues exactly, never sized from future low.
- Candidate gates up to half of initial post-sale AUD cash until the
  FIRST eligible WEEKLY review with previous close <= 0.85 x prior 200WMA.
  Until that happens, at most half of initial budget is deployable,
  using HALF the unchanged original weekly amount; after the gate,
  original full weekly percentage applies to remaining fixed initial cash.
  Unused prior tranches are NOT caught up retroactively.
- Reserve can remain cash forever if deep discount never occurs. This
  deliberately tests a major adverse opportunity-cost scenario.

Compare matched AUD 500k hypothetical original-halving BTC accounts with
identical original SELL schedule, lagged FX, A$3 fee and simplified SMSF
FIFO tax. 2017/21 are in sample; 2025/26 right-censored. Counterfactual
50/70% crashes are synthetic, not forecasts or probabilities. NO live
IBIT orders, trading updates or ntfy changes.
"""
from __future__ import annotations

import argparse
import json
import math
from pathlib import Path

import pandas as pd

from engines.research.day500_aftertax_reinvestment import (
    INITIAL_AUD,PRIMARY,SCORE_DAYS,DELAY_DAYS_AFTER_LAST_SELL,
    fetch_fx_for_cycle,fx_before,
)
from engines.research.shared_cycle_policy import (
    REVIEW_DAY,recovery_buy_budget_fraction,
)
from engines.research.cycle_chronological_wallet import (
    previously_completed_200wma_breach,replay_chronological_wallet,
)
from engines.research.first_confirmed_top_sell_roundtrip import (
    compile_sell_plan,
)
from engines.research.smsf_self_financing_replay import AuditSmsfAccount
from engines.research.staged_dca_delayed_bottom_stress import (
    delayed_bottom_path,
)
from engines.research.top_signal_horse_race import read_exported_history

OBSERVATION_CUTOFF=pd.Timestamp("2026-10-05",tz="UTC")
ORIGINAL_POLICY="frozen_original_adaptive_recovery"
RESERVE_POLICY="half_budget_held_until_weekly_prior_close_below_0p85_200wma"
RESERVE_FRACTION=.50
DEEP_DISCOUNT_WMA_RATIO=.85
STRESS_SHOCK_DAY=900
STRESS_DROPS=(.50,.70)
STRESS_TERMINAL_RATIOS=(.55,1.05)
MIN_AUD_BUY=100.


def _utc(t):
    d=pd.Timestamp(t)
    return (d.tz_localize("UTC") if d.tz is None
            else d.tz_convert("UTC")).normalize()


def replay_buy_reserve(price,fx,halving,terminal,*,reserve_policy,
                       initial_aud=INITIAL_AUD):
    """Independent chronological original-SALES + strict weekly WMA BUYs.

    Ex-post observed LOW is used ONLY after the wallet loop to SCORE cash,
    position size and USD VWAP, never to decide allocations or dates.
    """
    if type(reserve_policy) is not bool:
        raise ValueError("Research variant must explicitly be True or False")
    h=_utc(halving)
    end=_utc(terminal)
    if (end<=h or end>h+pd.Timedelta(days=SCORE_DAYS)
            or h not in price.index or end not in price.index
            or price.index.tz is None or price.index.has_duplicates
            or not price.index.is_monotonic_increasing):
        raise ValueError("Ordered historical UTC prices and valid horizon required")
    daily=pd.date_range(h,end,tz="UTC",freq="D")
    if not daily.isin(price.index).all():
        raise ValueError("Missing daily historical BTC close")
    if not math.isfinite(float(initial_aud)) or initial_aud<=103:
        raise ValueError("Starting original position cannot be funded")
    # Zero-alert flag ensures the ORIGINAL scheduled SELLs, identical in both
    # variants. Does not bring other mutable top indicators into BUY test.
    empty_alert=pd.Series(False,index=price.index)
    plan=compile_sell_plan(price,empty_alert,h,end,candidate=False)
    scheduled={}
    for sale in plan["sell_decisions"]:
        date=_utc(sale["decision_date"])
        scheduled.setdefault(date,[]).append(sale)
    account=AuditSmsfAccount(float(initial_aud),fee=3.,tax=True)
    initial_price_aud=float(price.loc[h])*fx_before(fx,h)
    if not account.buy(h,initial_price_aud,1.):
        raise AssertionError("Missing matched historical initial BTC")
    original_btc=account.btc
    sell_fills=[]
    buy_fills=[]
    cash_day={}
    btc_day={}
    account_cash_before_buy=None
    first_below_wma=None
    deep_discount_unlocked=not reserve_policy
    first_deep_discount=None
    spent_before_unlock=0.
    low_start=h+pd.Timedelta(days=REVIEW_DAY+DELAY_DAYS_AFTER_LAST_SELL)
    for day in daily[1:]:
        px_usd=float(price.loc[day])
        if not math.isfinite(px_usd) or px_usd<=0:
            raise ValueError("BTC quote is nonpositive")
        aud_px=px_usd*fx_before(fx,day)
        for sale in scheduled.get(day,[]):
            portion=min(account.btc,original_btc*sale["fraction_original"])
            if portion>1e-12:
                if account.sell(day,aud_px,min(1.,portion/account.btc)):
                    order=account.orders[-1]
                    sell_fills.append({
                        "date":str(day.date()),
                        "btc":float(order["btc"]),
                        "gross_aud":float(order["gross_aud"]),
                        "tax_aud":float(order["tax_aud"]),
                        "original_fraction":float(order["btc"])/original_btc,
                    })
        if day>=low_start:
            if first_below_wma is None and previously_completed_200wma_breach(
                    price,day):
                first_below_wma=day
                account_cash_before_buy=float(account.cash)
            if (first_below_wma is not None and
                    (day-first_below_wma).days%7==0):
                step=recovery_buy_budget_fraction(
                    price.loc[:day],day,style="adaptive_recovery")
                fraction=float(step["fraction_of_initial_buyback_cash"])
                ratio=float(step["previous_close_to_200wma"])
                if reserve_policy and not deep_discount_unlocked and (
                        ratio<=DEEP_DISCOUNT_WMA_RATIO):
                    deep_discount_unlocked=True
                    first_deep_discount=day
                if reserve_policy and not deep_discount_unlocked:
                    remaining_early=max(0.,account_cash_before_buy*
                                        RESERVE_FRACTION-spent_before_unlock)
                    gross=min(account.cash,remaining_early,
                              account_cash_before_buy*
                              (1.-RESERVE_FRACTION)*fraction)
                else:
                    gross=min(account.cash,account_cash_before_buy*fraction)
                if gross>MIN_AUD_BUY:
                    if account.buy(day,aud_px,min(1.,gross/account.cash)):
                        order=account.orders[-1]
                        if reserve_policy and not deep_discount_unlocked:
                            spent_before_unlock+=float(order["gross_aud"])
                        buy_fills.append({
                            "date":str(day.date()),
                            "btc":float(order["btc"]),
                            "gross_aud":float(order["gross_aud"]),
                            "wma_ratio_from_completed_prices":round(ratio,6),
                            "reserved_tranche_locked":bool(
                                reserve_policy and not deep_discount_unlocked),
                            "original_budget_pct":round(
                                100*float(order["gross_aud"])/account_cash_before_buy,4),
                        })
        cash_day[day]=float(account.cash)
        btc_day[day]=float(account.btc)
        account.mark(aud_px)
    terminal_aud=float(price.loc[end])*fx_before(fx,end)
    # Ex-post LOW, after all trade decisions/marking. Never signal input.
    observed=price.loc[low_start:end]
    if observed.empty:
        low_day=None
        low_px=None
    else:
        low_day=observed.idxmin()
        low_px=float(observed.loc[low_day])
    total_btc=sum(v["btc"] for v in buy_fills)
    total_usd=sum(v["gross_aud"]/fx_before(fx,v["date"])
                  for v in buy_fills)
    bought_usd_vwap=(total_usd/total_btc if total_btc>0 else None)
    original_aftertax_budget=account_cash_before_buy
    return {
        "policy":RESERVE_POLICY if reserve_policy else ORIGINAL_POLICY,
        "research_only":True,
        "live_parity_certified":False,
        "halving_date":str(h.date()),
        "terminal_date":str(end.date()),
        "complete_day1150_observation":end==h+pd.Timedelta(days=SCORE_DAYS),
        "original_initial_aud":round(float(initial_aud),2),
        "initial_btc_before_sell":round(original_btc,8),
        "sell_count":len(sell_fills),
        "original_btc_sold_pct":round(100*sum(
            t["original_fraction"] for t in sell_fills),5),
        "buy_200wma_activation_date":(
            str(first_below_wma.date()) if first_below_wma is not None else None),
        "first_weekly_deep_discount_date":(
            str(first_deep_discount.date()) if first_deep_discount is not None else None),
        "reserved_fraction_of_initial_cash":(
            50. if reserve_policy else 0.),
        "reserved_cash_unlocked":bool(deep_discount_unlocked),
        "initial_aftertax_buyback_budget_aud":(
            round(original_aftertax_budget,2)
            if original_aftertax_budget is not None else None),
        "buy_count":len(buy_fills),
        "buy_budget_deployed_pct":(
            round(100*sum(b["gross_aud"] for b in buy_fills)/
                  original_aftertax_budget,2)
            if original_aftertax_budget is not None else None),
        "btc_end":round(account.btc,8),
        "cash_end_aud":round(account.cash,2),
        "terminal_btc_equivalent_including_cash":round(
            account.btc+account.cash/terminal_aud,8),
        "marked_equity_aud":round(
            account.cash+account.btc*terminal_aud,2),
        "after_hypothetical_liquidation_cgt_aud":round(
            account.liquidation_value(end,terminal_aud),2),
        "estimated_cgt_during_roundtrip_aud":round(account.total_tax,2),
        "fees_aud":round(account.total_fees,2),
        "max_marked_account_drawdown_pct":round(100*account.drawdown,2),
        "hindsight_low_close_date":str(low_day.date()) if low_day is not None else None,
        "hindsight_low_close_usd":round(low_px,2) if low_px is not None else None,
        "cash_aud_on_hindsight_low":(
            round(cash_day[low_day],2) if low_day in cash_day else None),
        "btc_on_hindsight_low":(
            round(btc_day[low_day],8) if low_day in btc_day else None),
        "buy_vwap_usd":(
            round(bought_usd_vwap,2) if bought_usd_vwap is not None else None),
        "buy_vwap_error_above_hindsight_low_pct":(
            round(100*(bought_usd_vwap/low_px-1),2)
            if bought_usd_vwap is not None and low_px is not None else None),
        "executed_sells":sell_fills,
        "executed_buys":buy_fills,
    }


def _matched_pair(price,fx,h,end,*,scenario):
    original=replay_buy_reserve(price,fx,h,end,reserve_policy=False)
    candidate=replay_buy_reserve(price,fx,h,end,reserve_policy=True)
    # A fair study must hold exactly constant the initial acquisition,
    # staged SELLs, taxes during SELL and first 200WMA activation.
    for key in ("initial_btc_before_sell","sell_count","original_btc_sold_pct",
                "buy_200wma_activation_date",
                "initial_aftertax_buyback_budget_aud"):
        if original[key]!=candidate[key]:
            raise AssertionError(f"Unmatched accounts differ in {key}")
    left=float(original["after_hypothetical_liquidation_cgt_aud"])
    right=float(candidate["after_hypothetical_liquidation_cgt_aud"])
    return {
        "scenario":scenario,
        "baseline_original":original,
        "half_cash_reserve_candidate":candidate,
        "reserve_vs_original_aftertax_aud_pct":round(100*(right/left-1),3),
        "reserve_minus_original_btc_end":round(
            candidate["btc_end"]-original["btc_end"],8),
        "reserve_minus_original_cash_aud":round(
            candidate["cash_end_aud"]-original["cash_end_aud"],2),
        "reserve_minus_original_cash_on_observed_low_aud":(
            round(candidate["cash_aud_on_hindsight_low"]-
                  original["cash_aud_on_hindsight_low"],2)
            if candidate["cash_aud_on_hindsight_low"] is not None and
            original["cash_aud_on_hindsight_low"] is not None else None),
    }


def audit_buy_depth_reserve(history,*,fx_fetcher=fetch_fx_for_cycle,
                            cycles=("2017","2021","2025"),
                            stress_cycles=("2017","2021"),
                            shock_losses=STRESS_DROPS,
                            terminal_ratios=STRESS_TERMINAL_RATIOS):
    prices=history["price_usd"].dropna().sort_index().loc[:OBSERVATION_CUTOFF]
    historical=[]
    shocks=[]
    fx_cache={}
    for label in set(cycles)|set(stress_cycles):
        if label not in PRIMARY:raise ValueError("Unknown historical cohort")
        h=_utc(PRIMARY[label]["halving"])
        end=min(h+pd.Timedelta(days=SCORE_DAYS),prices.index[-1])
        fx_cache[label]=(h,end,fx_fetcher(h,end))
    for label in cycles:
        h,end,fx=fx_cache[label]
        row=_matched_pair(prices,fx,h,end,scenario="observed")
        historical.append({
            "cycle":label,
            "complete_observation":end==h+pd.Timedelta(days=SCORE_DAYS),
            **row,
        })
    for label in stress_cycles:
        if label=="2025":
            raise ValueError("Cannot score incomplete 2025 cohort as completed")
        h,end,fx=fx_cache[label]
        if end!=h+pd.Timedelta(days=SCORE_DAYS):
            raise ValueError("A completed base period is required for 1150d stress")
        for loss in shock_losses:
            for terminal_ratio in terminal_ratios:
                future=delayed_bottom_path(
                    prices,h,shock_start_day=STRESS_SHOCK_DAY,
                    loss_fraction=float(loss),
                    terminal_price_fraction=float(terminal_ratio))
                shock=_matched_pair(future,fx,h,end,scenario="synthetic")
                shocks.append({
                    "cycle":label,
                    "shock_start_day_after_halving":STRESS_SHOCK_DAY,
                    "trough_day_after_halving":1060,
                    "shock_loss_pct":int(round(100*loss)),
                    "terminal_pct_of_pre_shock_usd_price":int(
                        round(100*terminal_ratio)),
                    "post_shock_prices_are_artificial":True,
                    **shock,
                })
    return {
        "hypothesis":"Reserve half original aftertax buyback cash until first weekly prior BTC close <=0.85 x previous 200WMA; freeze existing buy timing and staged SELLs",
        "reserve_fraction_original_budget":RESERVE_FRACTION,
        "deep_discount_gate_ratio_of_wma":DEEP_DISCOUNT_WMA_RATIO,
        "original_day744_200wma_activation_preserved":True,
        "cutoff":str(OBSERVATION_CUTOFF.date()),
        "fixed_original_btc_position_aud":INITIAL_AUD,
        "real_history":historical,
        "synthetic_delayed_bottom_stress":shocks,
        "limitations":[
            "Only two already-studied completed historic cohorts; 2025/26 ends at archived 5 Oct 2026 and future low unknown.",
            "The 0.85x prior 200WMA threshold and 50% reserve are predeclared illustrative research hypotheses, not validated optimal thresholds.",
            "Synthetic forced 50/70% drops and terminal recoveries after day900 are NOT predicted BTC paths or likelihood estimates.",
            "Historical synthetic AUD500k owned BTC from halving; no real 2026 user holdings have simulated past 2025 sells.",
            "BTC daily close execution is a proxy, not ASX:IBIT units/trading-hours/spread or guaranteed execution.",
            "Historical FX uses last prior dated observation; no broker currency spread, lost cash interest or verified SMSF phase.",
            "No change to live Streamlit allocation, Production V5.8.2, Research V5.9, Google Sheets or ntfy.",
        ],
        "research_only":True,
        "live_strategy_replaced":False,
    }


def main():
    args=argparse.ArgumentParser()
    args.add_argument("--output",type=Path)
    cfg=args.parse_args()
    results=audit_buy_depth_reserve(read_exported_history())
    for row in results["real_history"]:
        base=row["baseline_original"]
        test=row["half_cash_reserve_candidate"]
        print(json.dumps({
            "cycle":row["cycle"],
            "completed":row["complete_observation"],
            "original_aftertax_aud":base["after_hypothetical_liquidation_cgt_aud"],
            "reserve_aftertax_aud":test["after_hypothetical_liquidation_cgt_aud"],
            "candidate_vs_original_pct":row["reserve_vs_original_aftertax_aud_pct"],
            "original_cash_on_observed_low_aud":base["cash_aud_on_hindsight_low"],
            "reserve_cash_on_observed_low_aud":test["cash_aud_on_hindsight_low"],
            "deep_discount_reserve_unlocked":test["reserved_cash_unlocked"],
            "deep_discount_unlock_date":test["first_weekly_deep_discount_date"],
            "original_buy_vwap_error_pct":base[
                "buy_vwap_error_above_hindsight_low_pct"],
            "reserve_buy_vwap_error_pct":test[
                "buy_vwap_error_above_hindsight_low_pct"],
        },sort_keys=True))
    for row in results["synthetic_delayed_bottom_stress"]:
        print(json.dumps({
            "stress_cycle":row["cycle"],
            "synthetic_drop_pct":row["shock_loss_pct"],
            "terminal_pct_preshock":row[
                "terminal_pct_of_pre_shock_usd_price"],
            "candidate_vs_original_aftertax_pct":row[
                "reserve_vs_original_aftertax_aud_pct"],
            "candidate_unlocked":row[
                "half_cash_reserve_candidate"]["reserved_cash_unlocked"],
        },sort_keys=True))
    if cfg.output:
        cfg.output.parent.mkdir(parents=True,exist_ok=True)
        cfg.output.write_text(json.dumps(results,indent=2))
        print("Dated matched 200WMA reserve BUY audit:",cfg.output)


if __name__=="__main__":
    main()
