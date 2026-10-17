"""Research-only small fallback before a new below-200WMA BUY activation.

PREDECLARED ONE CANDIDATE (no optimisation, no score-based tuning):
- Only if there has been NO prior-completed-close-below-200WMA trigger
  since the investor's declared fresh-cash start.
- On exactly start+56, +63, +70 and +77 days, invest 2.5% of the ORIGINAL
  fresh AUD budget per date, capped at 10% gross. Trade only when previous
  day's BTC close is between 1.0 and 1.5 times previous 200WMA.
- Never chase BTC >1.5x prior WMA. Missing a scheduled eligible fallback
  is skipped, NOT accumulated into a later catch-up transaction.
- The first subsequent strict close-below-200WMA activates the ORIGINAL
  weekly adaptive_recovery regime, and suppresses any remaining fallback.
- No synthetic past positions, 2025 sales, outside cash, orders or alerts.

Benchmark with matched, actual earlier-start AUD accounts from PR#126;
stress the same pre-shock market prefix with hypothetical delayed 50/70%
bear bottoms (counterfactual, not historical probabilities).
"""
from __future__ import annotations

import argparse
import json
import math
from pathlib import Path

import pandas as pd

from engines.research.day500_aftertax_reinvestment import (
    PRIMARY,SCORE_DAYS,fetch_fx_for_cycle,fx_before,
)
from engines.research.fresh_cash_200wma_matched_backtest import (
    BUDGET_AUD,FEE_AUD,MIN_ORDER_AUD,START_DAYS,
    _historical_wma,matched_fresh_cash_replay,
)
from engines.research.shared_cycle_policy import recovery_buy_budget_fraction
from engines.research.smsf_self_financing_replay import AuditSmsfAccount
from engines.research.staged_dca_delayed_bottom_stress import delayed_bottom_path
from engines.research.top_signal_horse_race import read_exported_history

FALLBACK_REVIEW_DAYS=(56,63,70,77)
FALLBACK_CHUNK_PCT_ORIGINAL=2.5
FALLBACK_MAX_TOTAL_PCT_ORIGINAL=10.
FALLBACK_MAX_WMA_RATIO=1.5
OBSERVATION_CUTOFF=pd.Timestamp("2026-10-05",tz="UTC")
# Include one post-fallback crash: 2017 day900 cash start buys its
# 10% starter by day977, BEFORE the day990 synthetic shock.
STRESS_CYCLE_STARTS=((750,900),(850,960),(900,990))
STRESS_DROP_FRACTIONS=(.50,.70)
STRESS_TERMINAL_FRACTIONS=(.55,1.05)
STRESS_TROUGH_DAY=1060
BENCHMARKS=(
    "forward_original_budget_weekly",
    "current_2p5_remaining_cash_daily",
    "fixed_52_week_equal_cash",
    "immediate_lump_sum",
)


def _date(value):
    value=pd.Timestamp(value)
    return (value.tz_localize("UTC") if value.tzinfo is None
            else value.tz_convert("UTC")).normalize()


def fallback_fresh_cash_replay(price,fx,*,start,terminal,
                               budget_aud=BUDGET_AUD,
                               fee_aud=FEE_AUD,min_order_aud=MIN_ORDER_AUD):
    """Fixed 10% starter plus original weekly DCA once actual gate occurs.

    Execution date T close is only a PRICE proxy; decisions always use
    prior close/WMA and prior 50DMA metrics, without hindsight. The
    starter cannot permanently consume >10% ORIGINAL budget.
    """
    start=_date(start)
    terminal=_date(terminal)
    if (not isinstance(price,pd.Series)
            or not isinstance(price.index,pd.DatetimeIndex)
            or price.index.tz is None or price.index.has_duplicates
            or not price.index.is_monotonic_increasing
            or terminal<=start or start not in price.index
            or terminal not in price.index):
        raise ValueError("Missing ordered, UTC BTC observation dates")
    warmup=start-pd.Timedelta(days=1394)
    full=pd.date_range(warmup,terminal,freq="D",tz="UTC")
    if not full.isin(price.index).all():
        raise ValueError("Continuous 200WMA warmup and trading history required")
    for label,value in (("Original cash budget",budget_aud),
                        ("Fee",fee_aud),("Minimum buy",min_order_aud)):
        if not math.isfinite(float(value)) or float(value)<0:
            raise ValueError(f"{label} is not finite/nonnegative")
    if budget_aud<=min_order_aud or min_order_aud<=fee_aud:
        raise ValueError("Invalid funded minimum order or fee")
    account=AuditSmsfAccount(float(budget_aud),fee=float(fee_aud),tax=True)
    fixed_cash=float(account.cash)
    gate=None
    starter_gross_aud=0.
    executed=[]
    gross_usd=0.
    for day in pd.date_range(start+pd.Timedelta(days=1),terminal,
                             freq="D",tz="UTC"):
        days=(day-start).days
        prev,wma=_historical_wma(price,day)
        if gate is None and prev<wma:
            gate=day
        kind=None
        frac=None
        allocation=0.
        if gate is not None:
            if (day-gate).days%7==0:
                frac=recovery_buy_budget_fraction(
                    price.loc[:day],day,style="adaptive_recovery")[
                        "fraction_of_initial_buyback_cash"]
                allocation=min(account.cash,fixed_cash*frac)
                kind="original_after_gate"
        elif days in FALLBACK_REVIEW_DAYS and wma<=prev<=FALLBACK_MAX_WMA_RATIO*wma:
            # No compensation for earlier missed dates: max 4*2.5%.
            frac=FALLBACK_CHUNK_PCT_ORIGINAL/100.
            allocation=min(account.cash,fixed_cash*frac,
                           max(0.,fixed_cash*FALLBACK_MAX_TOTAL_PCT_ORIGINAL/100.-
                               starter_gross_aud))
            kind="limited_starter"
        if allocation>min_order_aud and allocation>2*fee_aud:
            usd=float(price.loc[day])
            if not math.isfinite(usd) or usd<=0:
                raise ValueError("Missing positive BTC execution-day close")
            rate=fx_before(fx,day)
            if account.buy(day,usd*rate,min(1.,allocation/account.cash)):
                order=account.orders[-1]
                gross=float(order["gross_aud"])
                gross_usd+=gross/rate
                if kind=="limited_starter":
                    starter_gross_aud+=gross
                    if starter_gross_aud>fixed_cash*.100001:
                        raise AssertionError("Fallback used more than 10% cash")
                executed.append({
                    "date":str(day.date()),"kind":kind,
                    "gross_aud":round(gross,2),
                    "btc":round(float(order["btc"]),10),
                    "spot_usd":round(usd,2),
                    "aud_per_usd":rate,
                    "pct_original_budget":round(100*frac,2),
                    "prior_close_to_prior_wma":round(prev/wma,4),
                })
        account.mark(float(price.loc[day])*fx_before(fx,day))
    end_usd=float(price.loc[terminal])
    end_aud=end_usd*fx_before(fx,terminal)
    low=float(price.loc[start+pd.Timedelta(days=1):terminal].min())
    qty=sum(float(x["btc"]) for x in account.orders if x["side"]=="BUY")
    avg_usd=gross_usd/qty if qty>0 else None
    equity=account.cash+account.btc*end_aud
    return {
        "policy":"capped_10pct_fallback_then_original_weekly",
        "start_date":str(start.date()),
        "terminal_date":str(terminal.date()),
        "initial_cash_aud":fixed_cash,
        "original_200wma_gate_date":str(gate.date()) if gate is not None else None,
        "fallback_max_pct_original_cash":FALLBACK_MAX_TOTAL_PCT_ORIGINAL,
        "fallback_cash_spent_aud":round(starter_gross_aud,2),
        "fallback_cash_spent_pct_original":round(100*starter_gross_aud/fixed_cash,2),
        "fallback_fills":sum(o["kind"]=="limited_starter" for o in executed),
        "after_gate_fills":sum(o["kind"]=="original_after_gate" for o in executed),
        "fill_count":len(executed),
        "btc_purchased_and_held":round(account.btc,8),
        "cash_left_aud":round(account.cash,2),
        "cash_left_pct":round(100*account.cash/fixed_cash,2),
        "marked_terminal_aud":round(equity,2),
        "after_hypothetical_liquidation_cgt_aud":round(
            account.liquidation_value(terminal,end_aud),2),
        "terminal_btc_equivalent_including_cash":round(
            account.btc+account.cash/end_aud,8),
        "average_buy_usd_vwap":round(avg_usd,2) if avg_usd else None,
        "average_buy_error_above_observed_future_low_pct":(
            round(100*(avg_usd/low-1),2) if avg_usd else None),
        "observed_post_start_low_usd":round(low,2),
        "terminal_btc_usd":round(end_usd,2),
        "account_max_marked_drawdown_pct":round(100*account.drawdown,2),
        "fee_total_aud":round(account.total_fees,2),
        "no_historical_btc_or_sell":True,
        "research_only":True,
        "orders":executed,
    }


def _report_summary(candidate,baselines,*,trough_date=None):
    """Compare exact same terminal BTC close, AUD FX and starting cash."""
    minimum={k:float(baselines[k]["after_hypothetical_liquidation_cgt_aud"])
             for k in BENCHMARKS}
    after=float(candidate["after_hypothetical_liquidation_cgt_aud"])
    sample={
        "fallback_10pct":{k:candidate[k] for k in (
            "original_200wma_gate_date","fallback_cash_spent_pct_original",
            "fallback_fills","after_gate_fills","btc_purchased_and_held",
            "cash_left_aud","cash_left_pct",
            "after_hypothetical_liquidation_cgt_aud",
            "average_buy_error_above_observed_future_low_pct",
            "terminal_btc_equivalent_including_cash",
            "account_max_marked_drawdown_pct")},
        "comparators":{
            k:{field:baselines[k][field] for field in (
                "fill_count","btc_purchased_and_held","cash_left_aud",
                "cash_left_pct","after_hypothetical_liquidation_cgt_aud",
                "average_buy_error_above_observed_future_low_pct",
                "terminal_btc_equivalent_including_cash")}
            for k in BENCHMARKS
        },
        "fallback_vs_baselines_aftertax_pct":{
            k:round(100*(after/v-1),2) for k,v in minimum.items()
        },
    }
    if trough_date is not None:
        date=_date(trough_date)
        prior=sum(float(o["gross_aud"]) for o in candidate["orders"]
                  if _date(o["date"])<date)
        sample["fallback_cash_spent_before_forced_low_pct"]=round(
            100*prior/candidate["initial_cash_aud"],2)
    return sample


def _baseline_prices(price,fx,*,start,terminal):
    return {
        policy:matched_fresh_cash_replay(
            price,fx,start=start,terminal=terminal,policy=policy,
            budget_aud=BUDGET_AUD)
        for policy in BENCHMARKS
    }


def run_fallback_audit(history,*,fx_fetcher=fetch_fx_for_cycle,
                       cycles=("2017","2021","2025"),
                       starts=START_DAYS,
                       stress_cycles=("2017","2021"),
                       stress_pairs=STRESS_CYCLE_STARTS,
                       drops=STRESS_DROP_FRACTIONS,
                       terminals=STRESS_TERMINAL_FRACTIONS):
    """Real observed matched starts PLUS deliberately adverse invented shocks.

    Freeze 8w no-trigger wait/10% cap/1.5WMA threshold BEFORE observing
    outcomes; never recalibrate or choose parameters using test results.
    """
    price=history["price_usd"].dropna().sort_index().loc[:OBSERVATION_CUTOFF]
    historic=[]
    stresses=[]
    cache={}
    for label in set(cycles)|set(stress_cycles):
        if label not in PRIMARY:raise ValueError("Unsupported Bitcoin cycle label")
        h=_date(PRIMARY[label]["halving"])
        final=min(h+pd.Timedelta(days=SCORE_DAYS),price.index[-1])
        if final not in price.index:raise ValueError("Missing dated final BTC close")
        cache[label]=(h,final,fx_fetcher(h,final))
    for label in cycles:
        h,final,fx=cache[label]
        for offset in starts:
            begin=h+pd.Timedelta(days=int(offset))
            if begin>=final:continue
            baselines=_baseline_prices(price,fx,start=begin,terminal=final)
            candidate=fallback_fresh_cash_replay(
                price,fx,start=begin,terminal=final)
            historic.append({
                "cycle":label,"start_day":int(offset),
                "start_date":str(begin.date()),"terminal_date":str(final.date()),
                "complete_cycle_window":final==h+pd.Timedelta(days=SCORE_DAYS),
                **_report_summary(candidate,baselines),
                "candidate_orders":candidate["orders"],
            })
    for label in stress_cycles:
        if label=="2025":
            raise ValueError("Right-censored 2025 cycle cannot be shock-scored")
        h,final,fx=cache[label]
        if final!=h+pd.Timedelta(days=SCORE_DAYS):
            raise ValueError("Stress needs a completed historical prefix")
        for start_day,shock_day in stress_pairs:
            if not start_day+1<shock_day<STRESS_TROUGH_DAY:
                raise ValueError("Shock must occur after cash-start and before trough")
            begin=h+pd.Timedelta(days=int(start_day))
            for loss in drops:
                for recovery in terminals:
                    shock=delayed_bottom_path(
                        price,h,shock_start_day=shock_day,
                        loss_fraction=loss,
                        terminal_price_fraction=recovery)
                    candidate=fallback_fresh_cash_replay(
                        shock,fx,start=begin,terminal=final)
                    baselines=_baseline_prices(
                        shock,fx,start=begin,terminal=final)
                    stresses.append({
                        "cycle":label,"start_day":int(start_day),
                        "shock_day":int(shock_day),
                        "trough_day":STRESS_TROUGH_DAY,
                        "loss_pct_from_shock_price":round(100*loss),
                        "terminal_pct_of_shock_price":round(100*recovery),
                        "synthetic_not_history":True,
                        **_report_summary(
                            candidate,baselines,
                            trough_date=h+pd.Timedelta(days=STRESS_TROUGH_DAY)),
                        "candidate_orders":candidate["orders"],
                    })
    if not historic or not stresses:
        raise ValueError("Missing research observations")
    # Ensure crash testing actually contains at least one scenario in
    # which the fallback purchased BTC BEFORE the artificial crash.
    # Otherwise a passing "stress" is vacuous: both policies were identical.
    exposed=[s for s in stresses if s[
        "fallback_10pct"]["fallback_cash_spent_pct_original"]>0]
    if (tuple(stress_pairs)==tuple(STRESS_CYCLE_STARTS)
            and tuple(stress_cycles)==("2017","2021") and not exposed):
        raise AssertionError("No adverse scenario exposed the capped fallback")
    summary={}
    for label in stress_cycles:
        cases=[x for x in stresses if x["cycle"]==label]
        vs_current=[x["fallback_vs_baselines_aftertax_pct"][
            "current_2p5_remaining_cash_daily"] for x in cases]
        vs_original=[x["fallback_vs_baselines_aftertax_pct"][
            "forward_original_budget_weekly"] for x in cases]
        summary[label]={
            "synthetic_stress_scenarios":len(cases),
            "worst_fallback_vs_current_pct":min(vs_current),
            "best_fallback_vs_current_pct":max(vs_current),
            "worst_fallback_vs_original_pct":min(vs_original),
            "best_fallback_vs_original_pct":max(vs_original),
            "maximum_fallback_cash_spent_before_forced_low_pct":max(
                x["fallback_cash_spent_before_forced_low_pct"] for x in cases),
            "minimum_fallback_ending_cash_pct":min(
                x["fallback_10pct"]["cash_left_pct"] for x in cases),
            "exposed_starter_scenarios":sum(
                x["fallback_10pct"]["fallback_cash_spent_pct_original"]>0 for x in cases),
            "worst_exposed_fallback_vs_original_pct":(
                min(x["fallback_vs_baselines_aftertax_pct"][
                    "forward_original_budget_weekly"] for x in cases
                    if x["fallback_10pct"]["fallback_cash_spent_pct_original"]>0)
                if any(x["fallback_10pct"][
                    "fallback_cash_spent_pct_original"]>0 for x in cases)
                else None),
        }
    return {
        "study":"ONE predeclared capped 10% above-200WMA cash starter stress",
        "policy":"Eight-week wait; up to 4 weekly 2.5%-original-budget buys when previous BTC close 1.0–1.5x prior 200WMA; original weekly dynamic DCA after first below-WMA observation",
        "budget_aud":BUDGET_AUD,
        "historical_observation_cutoff":str(OBSERVATION_CUTOFF.date()),
        "not_optimized_after_observing_data":True,
        "historical_matched_entries":historic,
        "synthetic_stress":stresses,
        "synthetic_stress_summary":summary,
        "caveats":[
            "Starter is a NEW predeclared research hypothesis, NOT part of original historical 200WMA BUY rule.",
            "Stress shocks and terminal recoveries after given historic dates are SYNTHETIC, NOT observed, predictions or probability scenarios.",
            "Proposed 10% starter risks losing money when BTC continues to fall, and will not fix missed upside if prior close >1.5x200WMA.",
            "Historical 2017 and 2021 observations were previously inspected; 2025/26 truncated at 2026-10-05 is not completed.",
            "Same matched hypothetical A$400k of fresh cash and initial date; NO BTC owned at halving or retrospective 2025 sale assumed.",
            "Simplified immediate SMSF FIFO terminal CGT only, BTC daily closing price execution proxy, AUD3/fill; no actual IBIT ASX quotes or fees/FX spreads.",
            "Comparison does not implement real 2026 SMSF holdings, pension-phase status, transfers, withdrawals or tax return.",
            "Never automatically apply fallback to Streamlit, ntfy, Production V5.8.2 or Research V5.9.",
        ],
    }


def main():
    p=argparse.ArgumentParser()
    p.add_argument("--output",type=Path)
    a=p.parse_args()
    out=run_fallback_audit(read_exported_history())
    for row in out["historical_matched_entries"]:
        print(json.dumps({
            "cycle":row["cycle"],"start":row["start_date"],
            "complete":row["complete_cycle_window"],
            "fallback_aud":row["fallback_10pct"]["after_hypothetical_liquidation_cgt_aud"],
            "fallback_cash_pct":row["fallback_10pct"]["cash_left_pct"],
            "fallback_spent_pct":row["fallback_10pct"]["fallback_cash_spent_pct_original"],
            "fallback_gate":row["fallback_10pct"]["original_200wma_gate_date"],
            "relative_aftertax_pct":row["fallback_vs_baselines_aftertax_pct"],
        },sort_keys=True))
    for name,row in out["synthetic_stress_summary"].items():
        print(json.dumps({"stress_cycle":name,**row},sort_keys=True))
    if a.output:
        a.output.parent.mkdir(parents=True,exist_ok=True)
        a.output.write_text(json.dumps(out,indent=2))
        print("Full fallback orders and matched stress archive:",a.output)


if __name__=="__main__":
    main()
