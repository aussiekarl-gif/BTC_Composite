"""Frozen, causal cycle-top indicator FIRST-alert selling screen.

Compare the ORIGINAL chronological day500 staged SELL + 200WMA weekly
BUY wallet against a single declared, identical supplemental sale:
  on the FIRST TRUE indicator on day 350..730 after halving, SELL 20%
  of ORIGINAL BTC before normal same-day staged sales (never double count).
  Same baseline staged exit review dates, post-730 buy activation, weekly
  fixed-original-cash rebuy fractions, same AUD FIFO/SMSF model for all.

This is an EXPLORATORY indicator timing screen, not an optimized rule,
verified out-of-sample result or a replacement for live Cycle Trading.
The BlockHorizon on-chain exports were obtained in 2026: observations
are dated, but historical publication vintage/revision is UNVERIFIED.
"""
from __future__ import annotations

import argparse
import json
import math
from pathlib import Path

import pandas as pd

from engines.research.day500_aftertax_reinvestment import (
    INITIAL_AUD,PRIMARY,SCORE_DAYS,fx_before,fetch_fx_for_cycle,
    DELAY_DAYS_AFTER_LAST_SELL,
)
from engines.research.shared_cycle_policy import (
    START_DAY,REVIEW_DAY,exit_review_days,staged_exit_decision,
    recovery_buy_budget_fraction,
)
from engines.research.cycle_chronological_wallet import (
    previously_completed_200wma_breach,replay_chronological_wallet,
)
from engines.research.smsf_self_financing_replay import AuditSmsfAccount
from engines.research.top_signal_horse_race import (
    read_exported_history,build_daily_signals,SIGNALS,
)

SELL_FRACTION_OF_ORIGINAL=.20
SIGNAL_START_DAY=350
SIGNAL_END_DAY=730
CUTOFF=pd.Timestamp("2026-10-05",tz="UTC")
FEE_AUD=3.
MIN_ORDER_AUD=100.
FROZEN_BUY_STYLE="adaptive_recovery"
POLICY="maturity_90pct_holdback20pct"
FAMILIES=("original_no_extra_sell",)+SIGNALS


def _utc(value):
    day=pd.Timestamp(value)
    return day.tz_localize("UTC") if day.tzinfo is None else day.tz_convert("UTC")


def replay_first_alert_overlay(price,fx,signals,halving,terminal,*,family,
                               initial_aud=INITIAL_AUD):
    """Single chronological account; never select best ex-post signal."""
    if family not in FAMILIES:
        raise ValueError("Unknown frozen alert family")
    halving=_utc(halving).normalize()
    terminal=_utc(terminal).normalize()
    if (terminal<=halving or terminal not in price.index
            or halving not in price.index
            or terminal>halving+pd.Timedelta(days=SCORE_DAYS)):
        raise ValueError("Invalid observed cycle endpoints")
    if (not isinstance(price,pd.Series)
            or not isinstance(price.index,pd.DatetimeIndex)
            or price.index.tz is None or not price.index.is_unique
            or not price.index.is_monotonic_increasing):
        raise ValueError("Price history must be unique chronological UTC days")
    expected=pd.date_range(halving,terminal,freq="D",tz="UTC")
    if not expected.isin(price.index).all():
        raise ValueError("Missing daily BTC execution close")
    if not isinstance(signals,pd.DataFrame) or not price.index.equals(signals.index):
        raise ValueError("Dated indicators must align exactly to price history")
    if family!="original_no_extra_sell" and (
            family not in signals or signals[family].isna().any()):
        raise ValueError("Missing or invalid indicator history")
    account=AuditSmsfAccount(float(initial_aud),fee=FEE_AUD,tax=True)
    first_px=float(price.loc[halving])*fx_before(fx,halving)
    if not account.buy(halving,first_px,1.):
        raise AssertionError("Initial buy could not execute")
    original_btc=account.btc
    sold_original_btc=0.
    overlay_date=None
    overlay_px_usd=None
    overlay_qty=0.
    first_activation=None
    fixed_rebuy_budget=None
    executions=[]
    review_dates=set(exit_review_days())
    buy_phase_start=halving+pd.Timedelta(days=REVIEW_DAY+DELAY_DAYS_AFTER_LAST_SELL)
    for date in expected[1:]:
        elapsed=int((date-halving).days)
        close_usd=float(price.loc[date])
        if not math.isfinite(close_usd) or close_usd<=0:
            raise ValueError("BTC close must be finite and positive")
        aud_per_btc=close_usd*fx_before(fx,date)
        if (family!="original_no_extra_sell"
                and overlay_date is None
                and SIGNAL_START_DAY<=elapsed<=SIGNAL_END_DAY
                and bool(signals.loc[date,family])):
            qty=min(account.btc,original_btc*SELL_FRACTION_OF_ORIGINAL)
            if qty>1e-12 and account.sell(date,aud_per_btc,qty/account.btc):
                sold_original_btc+=float(account.orders[-1]["btc"])
                overlay_date=date
                overlay_px_usd=close_usd
                overlay_qty=float(account.orders[-1]["btc"])
                executions.append({
                    "date":str(date.date()),"side":"SELL",
                    "reason":family,"btc":round(overlay_qty,8),
                    "pct_original":round(100*overlay_qty/original_btc,4),
                    "gross_aud":round(account.orders[-1]["gross_aud"],2),
                })
        if START_DAY<=elapsed<=REVIEW_DAY and elapsed in review_dates:
            decision=staged_exit_decision(
                price.loc[:date],halving,day=elapsed,
                sold_original_fraction=min(1.,sold_original_btc/original_btc),
                policy=POLICY)
            qty=min(account.btc,original_btc*decision["fraction_original"])
            if qty>1e-12 and account.sell(date,aud_per_btc,qty/account.btc):
                sold_original_btc+=float(account.orders[-1]["btc"])
                executions.append({
                    "date":str(date.date()),"side":"SELL",
                    "reason":"original_staged","btc":round(
                        float(account.orders[-1]["btc"]),8),
                    "pct_original":round(
                        100*float(account.orders[-1]["btc"])/original_btc,4),
                    "gross_aud":round(account.orders[-1]["gross_aud"],2),
                })
        if date>=buy_phase_start:
            if first_activation is None:
                if previously_completed_200wma_breach(price,date):
                    first_activation=date
                    fixed_rebuy_budget=float(account.cash)
            if first_activation is not None and (date-first_activation).days%7==0:
                fraction=recovery_buy_budget_fraction(
                    price.loc[:date],date,style=FROZEN_BUY_STYLE)
                gross=min(account.cash, fixed_rebuy_budget*
                          fraction["fraction_of_initial_buyback_cash"])
                if gross>MIN_ORDER_AUD and account.buy(
                        date,aud_per_btc,min(1.,gross/account.cash)):
                    executions.append({
                        "date":str(date.date()),"side":"BUY",
                        "reason":"original_weekly_200wma",
                        "btc":round(float(account.orders[-1]["btc"]),8),
                        "original_budget_fraction":round(
                            fraction["fraction_of_initial_buyback_cash"],7),
                        "gross_aud":round(account.orders[-1]["gross_aud"],2),
                    })
        account.mark(aud_per_btc)
    terminal_aud=float(price.loc[terminal])*fx_before(fx,terminal)
    return {
        "family":family,
        "research_only":True,
        "live_execution_parity_verified":False,
        "halving":str(halving.date()),
        "terminal":str(terminal.date()),
        "completed_horizon":terminal==halving+pd.Timedelta(days=SCORE_DAYS),
        "overlay_first_date":str(overlay_date.date()) if overlay_date is not None else None,
        "overlay_first_trade_usd":round(overlay_px_usd,2) if overlay_px_usd is not None else None,
        "overlay_fraction_original_pct":round(100*overlay_qty/original_btc,4),
        "original_btc":round(original_btc,8),
        "original_btc_sold_pct":round(100*min(1.,sold_original_btc/original_btc),3),
        "sell_count":sum(x["side"]=="SELL" for x in account.orders),
        "buyback_count":sum(x["side"]=="BUY" for x in account.orders)-1,
        "first_200wma_rebuy":str(first_activation.date()) if first_activation is not None else None,
        "initial_aftertax_rebuy_cash_aud":round(fixed_rebuy_budget,2) if fixed_rebuy_budget is not None else None,
        "ending_btc":round(account.btc,8),
        "ending_cash_aud":round(account.cash,2),
        "terminal_btc_equivalent_incl_cash":round(
            account.btc+account.cash/terminal_aud,8),
        "terminal_after_illustrative_cgt_aud":round(
            account.liquidation_value(terminal,terminal_aud),2),
        "realised_tax_escrow_aud":round(account.total_tax,2),
        "total_brokerage_aud":round(account.total_fees,2),
        "max_drawdown_pct":round(100*account.drawdown,2),
        "executions":executions,
    }


def audit_first_alert_horse_race(history,*,fx_fetcher=fetch_fx_for_cycle):
    """Frozen all-families evidence; NEVER choose an ex-post winner as live."""
    full=history.loc[history.index<=CUTOFF].copy()
    if "price_usd" not in full:
        raise ValueError("Dated BTC/indicator columns required")
    if full.empty:
        raise ValueError("BTC dated research history empty")
    signals=build_daily_signals(full)
    price=full["price_usd"]
    records=[]
    sanity=[]
    for cycle,meta in PRIMARY.items():
        halving=_utc(meta["halving"])
        terminal=min(halving+pd.Timedelta(days=SCORE_DAYS),full.index[-1])
        if terminal not in full.index or halving not in full.index:
            raise ValueError("Missing observed halving or terminal BTC price")
        fx=fx_fetcher(halving,terminal)
        baseline=replay_chronological_wallet(
            price,fx,halving,terminal,buy_style=FROZEN_BUY_STYLE)
        for family in FAMILIES:
            v=replay_first_alert_overlay(
                price,fx,signals,halving,terminal,family=family)
            if family=="original_no_extra_sell":
                assert_fields=(
                    ("terminal_after_illustrative_cgt_aud",
                     "after_hypothetical_liquidation_cgt_aud"),
                    ("ending_btc","btc_held"),
                    ("ending_cash_aud","cash_remaining_aud"),
                    ("original_btc","original_btc"),
                    ("sell_count","sell_count"),
                    ("buyback_count","buyback_count"),
                )
                for our,reference in assert_fields:
                    if abs(v[our]-baseline[reference])>.03:
                        raise AssertionError(
                            f"Chronological original baseline mismatch {cycle}: "
                            f"{our} {v[our]} != {reference} {baseline[reference]}")
                sanity.append({"cycle":cycle,"matches_prior_chronological_wallet":True})
            delta=v["terminal_after_illustrative_cgt_aud"]-baseline[
                "after_hypothetical_liquidation_cgt_aud"]
            records.append({
                "cycle":cycle,
                "full_window_observed":v["completed_horizon"],
                "family":family,
                "first_extra_sell_date":v["overlay_first_date"],
                "first_extra_sell_price_usd":v["overlay_first_trade_usd"],
                "aftertax_aud":v["terminal_after_illustrative_cgt_aud"],
                "vs_original_aud":round(delta,2),
                "vs_original_pct":round(
                    100*delta/baseline["after_hypothetical_liquidation_cgt_aud"],3),
                "btc_equivalent_incl_cash":v["terminal_btc_equivalent_incl_cash"],
                "btc_held":v["ending_btc"],
                "cash_aud":v["ending_cash_aud"],
                "original_sold_pct":v["original_btc_sold_pct"],
                "buyback_count":v["buyback_count"],
                "realised_cgt_escrow_aud":v["realised_tax_escrow_aud"],
                "max_drawdown_pct":v["max_drawdown_pct"],
            })
    summaries=[]
    for family in FAMILIES[1:]:
        completed=[x for x in records
                   if x["family"]==family and x["full_window_observed"]]
        summary={
            "family":family,
            "completed_n":len(completed),
            "better_than_original_n":sum(x["vs_original_aud"]>0 for x in completed),
            "worse_than_original_n":sum(x["vs_original_aud"]<0 for x in completed),
            "worst_completed_delta_pct":min(
                (x["vs_original_pct"] for x in completed),default=None),
            "mean_completed_delta_pct":round(
                sum(x["vs_original_pct"] for x in completed)/len(completed),3)
                if completed else None,
            "first_alerts_during_completed":sum(
                x["first_extra_sell_date"] is not None for x in completed),
        }
        summaries.append(summary)
    return {
        "research_only":True,
        "policy_freeze":{
            "base_strategy":POLICY,
            "original_buy_style":FROZEN_BUY_STYLE,
            "supplemental_sell_size_pct_original_btc":
                SELL_FRACTION_OF_ORIGINAL*100,
            "first_signal_eligibility_day_range":[
                SIGNAL_START_DAY,SIGNAL_END_DAY],
            "signal_uses_strict_prior_observations":True,
            "buy_activation":"strict prior 200WMA below breach after day744",
            "sell_overlay_applies_once":True,
            "historical_onchain_vintages_verified":False,
            "decision_selected_by_eventual_cycle_peak":False,
            "production_and_ntfy_unchanged":True,
        },
        "observed_through":str(full.index[-1].date()),
        "baseline_invariants":sanity,
        "completed_cycles":sum(
            x["full_window_observed"] for x in records
            if x["family"]=="original_no_extra_sell"),
        "censored_cycles":sum(
            not x["full_window_observed"] for x in records
            if x["family"]=="original_no_extra_sell"),
        "summary":summaries,
        "per_cycle":records,
        "warnings":[
            "Thresholds, alert families and 20% supplemental sale rule were "
            "predeclared for this research experiment; they are NOT prospectively "
            "validated or fitted with genuine unseen historical-vintage inputs.",
            "October 2026 on-chain exports may contain backfilled/revised readings. "
            "Strict prior-date access prevents computational lookahead, "
            "not publication-vintage revision bias.",
            "Expected terminal BTC and AUD depend on when hypothetical trading "
            "starts at each past halving; user actual 2026 holdings were not "
            "present in 2016, 2020 or early 2025.",
            "2025/26 is right-censored as of 2026-10-05, not a full cycle.",
            "A$3 per synthetic BTC fill, dated historical AUD FX and simplified "
            "FIFO 10/15% SMSF gains escrow are not executable ASX:IBIT orders, "
            "ETF tracking/spreads or a verified SMSF tax return.",
            "This screens FIRST signals only, not hindsight-nearest peak events. "
            "Few complete cycles mean no reliable statistical win-rate inference.",
        ],
    }


def main(argv=None):
    p=argparse.ArgumentParser()
    p.add_argument("--out",type=Path,default=Path("artifacts/sell_top_first_alert"))
    args=p.parse_args(argv)
    args.out.mkdir(parents=True,exist_ok=True)
    out=audit_first_alert_horse_race(read_exported_history())
    (args.out/"sell_first_alert_audit.json").write_text(
        json.dumps(out,indent=2),encoding="utf8")
    pd.DataFrame(out["per_cycle"]).to_csv(
        args.out/"sell_first_alert_per_cycle.csv",index=False)
    pd.DataFrame(out["summary"]).to_csv(
        args.out/"sell_first_alert_summary.csv",index=False)
    print("completed",out["completed_cycles"],"censored",out["censored_cycles"])
    print(pd.DataFrame(out["per_cycle"])[[
        "cycle","family","first_extra_sell_date","aftertax_aud",
        "vs_original_pct","btc_equivalent_incl_cash"]].to_string(index=False))
    print("SUMMARY")
    print(pd.DataFrame(out["summary"]).to_string(index=False))


if __name__=="__main__":
    main()
