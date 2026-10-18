"""Frozen *research-only* BTC volatility + declining-trend recovery-BUY guard.

Fresh AUD cash only; NO backdated BTC sales / user IBIT purchases. Enter
only after FIRST strict T-1 BTC/USD close < exact prior 200 WEEK MA.
On each original weekly recovery review:
  - use unchanged original fixed-budget 2.5/15/4.5/1% percentage;
  - if 30 preceding daily log returns have >=80% annualised realised vol,
    prior close is below prior 50-day SMA, AND that SMA is lower than
    its value 14 days before, spend HALF of original weekly allocation.
  - otherwise use the unchanged allocation.
No missed weekly tranche is later caught up. There is no new BUY on a
non-weekly date or before an original WMA crossing. A future low, peak
or revised onchain indicator cannot generate a decision.

One non-optimized exploratory hypothesis; 2017/2021 are already examined.
2025/26 remains right-censored at the archived 2026-10-05 BTC close.
Not executable ASX:IBIT prices, financial advice or live 2026 portfolio.
"""
from __future__ import annotations

import argparse
import csv
import json
import math
from pathlib import Path

import numpy as np
import pandas as pd

from engines.research.day500_aftertax_reinvestment import (
    PRIMARY, SCORE_DAYS, fetch_fx_for_cycle, fx_before,
)
from engines.research.fresh_cash_200wma_matched_backtest import (
    BUDGET_AUD, FEE_AUD, MIN_ORDER_AUD, START_DAYS,
    _historical_wma, matched_fresh_cash_replay,
)
from engines.research.shared_cycle_policy import recovery_buy_budget_fraction
from engines.research.smsf_self_financing_replay import AuditSmsfAccount
from engines.research.staged_dca_delayed_bottom_stress import delayed_bottom_path
from engines.research.top_signal_horse_race import read_exported_history

CUTOFF = pd.Timestamp("2026-10-05", tz="UTC")
VOL_LOOKBACK_RETURNS = 30
VOL_ANNUALISE_DAYS = 365
VOL_ANNUALISED_THRESHOLD = .80
TREND_SMA_DAYS = 50
TREND_SLOPE_LAG_DAYS = 14
CAUTIOUS_MULTIPLIER = .50
BENCHMARKS = (
    "forward_original_budget_weekly",
    "current_2p5_remaining_cash_daily",
    "fixed_52_week_equal_cash",
    "immediate_lump_sum",
)
# Fixed stress-path geometry, no parameter optimisation.
STRESS_COHORTS = (("2017", 750, 960), ("2021", 650, 900))
STRESS_LOSSES = (.50, .70)
STRESS_TERMINALS = (.55, 1.05)
STRESS_TROUGH_DAY = 1060


def _utc(v):
    t = pd.Timestamp(v)
    return (t.tz_localize("UTC") if t.tz is None
            else t.tz_convert("UTC")).normalize()


def lagged_volatility_trend(price, date):
    """Risk signal for order date T sees exclusively 64 prior BTC closes.

    Annualised log-return standard deviation uses 30 daily differences
    formed from 31 dates through T-1. The 50DMA and its 14-day lag use
    64 exact previous daily observations; no T price or future record.
    """
    date = _utc(date)
    required = pd.date_range(
        date-pd.Timedelta(days=64),
        date-pd.Timedelta(days=1), freq="D", tz="UTC")
    if not required.isin(price.index).all():
        raise ValueError("64 exact prior BTC daily closes required")
    p = price.loc[required].to_numpy(dtype=float)
    if not np.isfinite(p).all() or (p <= 0).any():
        raise ValueError("Prior BTC close invalid")
    returns = np.diff(np.log(p[-31:]))
    annual_vol = float(returns.std(ddof=1) * math.sqrt(VOL_ANNUALISE_DAYS))
    prior = float(p[-1])
    ma = float(p[-50:].mean())
    old_ma = float(p[:50].mean())
    downtrend = bool(prior < ma and ma < old_ma)
    guarded = bool(annual_vol >= VOL_ANNUALISED_THRESHOLD and downtrend)
    return {
        "annual_volatility_30d_pct":round(100*annual_vol,3),
        "prior_close":prior,
        "prior_50dma":ma,
        "prior_50dma_14_days_earlier":old_ma,
        "downtrend":downtrend,
        "high_volatility":annual_vol >= VOL_ANNUALISED_THRESHOLD,
        "guard_active":guarded,
        "uses_only_prior_closes":True,
    }


def replay_guarded_cash(price, fx, *, start, terminal,
                        guard=False, budget_aud=BUDGET_AUD,
                        fee_aud=FEE_AUD, min_order_aud=MIN_ORDER_AUD):
    if type(guard) is not bool:
        raise ValueError("Guard must be an explicit Boolean")
    start, terminal = _utc(start), _utc(terminal)
    if (not isinstance(price,pd.Series)
            or not isinstance(price.index,pd.DatetimeIndex)
            or price.index.tz is None or price.index.has_duplicates
            or not price.index.is_monotonic_increasing
            or start not in price.index or terminal not in price.index
            or start >= terminal):
        raise ValueError("Ordered UTC BTC price and valid endpoints required")
    required = pd.date_range(
        start-pd.Timedelta(days=1394),terminal,freq="D",tz="UTC")
    if not required.isin(price.index).all():
        raise ValueError("Continuous prior WMA/wallet history required")
    values = price.loc[required].to_numpy(dtype=float)
    if not np.isfinite(values).all() or (values <= 0).any():
        raise ValueError("Nonfinite/nonpositive historical BTC closes")
    if (not math.isfinite(float(budget_aud)) or budget_aud <= 100
            or not math.isfinite(float(fee_aud)) or fee_aud < 0
            or not math.isfinite(float(min_order_aud))
            or min_order_aud <= fee_aud):
        raise ValueError("Invalid original cash/fee bounds")
    account = AuditSmsfAccount(float(budget_aud),fee=float(fee_aud),tax=True)
    original_cash = float(account.cash)
    first_gate = None
    orders = []
    reduction_count = 0
    would_spend_without_guard = 0.
    skipped_gross = 0.
    observed_guard_reviews = 0
    gross_usd = 0.
    for date in pd.date_range(
            start+pd.Timedelta(days=1),terminal,freq="D",tz="UTC"):
        prior, wma = _historical_wma(price,date)
        if first_gate is None and prior < wma:
            first_gate = date
        if first_gate is not None and (date-first_gate).days%7 == 0:
            orig = recovery_buy_budget_fraction(
                price.loc[:date],date,style="adaptive_recovery")[
                    "fraction_of_initial_buyback_cash"]
            signal = lagged_volatility_trend(price,date)
            mult = CAUTIOUS_MULTIPLIER if guard and signal[
                "guard_active"] else 1.
            gross = min(account.cash,original_cash*orig*mult)
            if guard and signal["guard_active"]:
                observed_guard_reviews+=1
                # Reference budget share withheld on this review,
                # before cash-shortfall effects; NOT "protected gains".
                would_spend_without_guard += original_cash*orig
                skipped_gross += original_cash*orig*(1-mult)
            if gross > min_order_aud and gross > 2*fee_aud:
                spot = float(price.loc[date])
                fx_rate = fx_before(fx,date)
                if account.buy(date,spot*fx_rate,
                               min(1.,gross/account.cash)):
                    o=account.orders[-1]
                    real=float(o["gross_aud"])
                    gross_usd += real/fx_rate
                    orders.append({
                        "date":str(date.date()),
                        "gross_aud":round(real,2),
                        "btc":round(float(o["btc"]),10),
                        "original_weekly_pct_budget":round(orig*100,3),
                        "actual_weekly_pct_budget":round(orig*mult*100,3),
                        "guard_active":bool(signal["guard_active"] and guard),
                        "prior_volatility_annualised_pct":signal[
                            "annual_volatility_30d_pct"],
                        "prior_50dma_downtrend":signal["downtrend"],
                        "previous_close_200wma_ratio":round(prior/wma,5),
                    })
                    if signal["guard_active"] and guard:
                        reduction_count+=1
        account.mark(float(price.loc[date])*fx_before(fx,date))
    final_usd=float(price.loc[terminal])
    terminal_aud=final_usd*fx_before(fx,terminal)
    qty=sum(float(o["btc"]) for o in account.orders if o["side"]=="BUY")
    vwap=gross_usd/qty if qty>0 else None
    observed_low=float(price.loc[
        start+pd.Timedelta(days=1):terminal].min())
    return {
        "guard":guard,
        "research_only":True,
        "no_historical_btc_lots_or_sales":True,
        "initial_cash_aud":original_cash,
        "first_200wma_gate":str(first_gate.date()) if first_gate is not None else None,
        "guard_active_weekly_reviews":observed_guard_reviews,
        "guard_affected_executed_buys":reduction_count,
        "hypothetical_original_budget_withheld_aud":round(skipped_gross,2),
        "fill_count":len(orders),
        "btc_held":round(account.btc,8),
        "cash_left_aud":round(account.cash,2),
        "cash_left_pct":round(account.cash/original_cash*100,3),
        "average_buy_usd_vwap":round(vwap,2) if vwap is not None else None,
        "average_buy_error_vs_observed_low_pct":(
            round(100*(vwap/observed_low-1),3) if vwap is not None else None),
        "aftertax_liquidation_aud":round(
            account.liquidation_value(terminal,terminal_aud),2),
        "max_drawdown_pct":round(account.drawdown*100,2),
        "total_fees_aud":round(account.total_fees,2),
        "btc_equivalent_with_cash":round(
            account.btc+account.cash/terminal_aud,8),
        "orders":orders,
    }


def compare(price,fx,*,start,terminal):
    refs = {name:matched_fresh_cash_replay(
        price,fx,start=start,terminal=terminal,policy=name)
        for name in BENCHMARKS}
    plain = replay_guarded_cash(
        price,fx,start=start,terminal=terminal,guard=False)
    protected = replay_guarded_cash(
        price,fx,start=start,terminal=terminal,guard=True)
    baseline=refs["forward_original_budget_weekly"]
    parity=(
        ("first_200wma_gate","first_valid_200wma_activation_date"),
        ("fill_count","fill_count"),
        ("btc_held","btc_purchased_and_held"),
        ("cash_left_aud","cash_left_aud"),
        ("aftertax_liquidation_aud","after_hypothetical_liquidation_cgt_aud"),
        ("total_fees_aud","fee_total_aud"),
    )
    for k, ref in parity:
        if plain[k] != baseline[ref]:
            raise AssertionError(
                f"Independent original fresh-cash parity {k}: "
                f"{plain[k]} differs from {baseline[ref]}")
    if protected["first_200wma_gate"] != plain["first_200wma_gate"]:
        raise AssertionError("Regime guard changed 200WMA first entry date")
    if protected["first_200wma_gate"] is None and protected["fill_count"]:
        raise AssertionError("Bought without previous close below 200WMA")
    a=protected["aftertax_liquidation_aud"]
    r=baseline["after_hypothetical_liquidation_cgt_aud"]
    def delta(value):
        return round(100*(a/value-1),3)
    return {
        "start":str(_utc(start).date()),
        "terminal":str(_utc(terminal).date()),
        "first_gate":protected["first_200wma_gate"],
        "guard_triggered_buy_count":protected["guard_affected_executed_buys"],
        "guard_active_reviews":protected["guard_active_weekly_reviews"],
        "guarded_aftertax_aud":a,
        "original_aftertax_aud":r,
        "guard_vs_original_aftertax_pct":delta(r),
        "guard_vs_current_daily_aftertax_pct":delta(
            refs["current_2p5_remaining_cash_daily"][
                "after_hypothetical_liquidation_cgt_aud"]),
        "guard_vs_fixed_dca_aftertax_pct":delta(
            refs["fixed_52_week_equal_cash"][
                "after_hypothetical_liquidation_cgt_aud"]),
        "guard_vs_lump_aftertax_pct":delta(
            refs["immediate_lump_sum"][
                "after_hypothetical_liquidation_cgt_aud"]),
        "guard_btc":protected["btc_held"],
        "original_btc":baseline["btc_purchased_and_held"],
        "guard_cash_aud":protected["cash_left_aud"],
        "original_cash_aud":baseline["cash_left_aud"],
        "guard_buy_error_pct":protected["average_buy_error_vs_observed_low_pct"],
        "original_buy_error_pct":baseline[
            "average_buy_error_above_observed_future_low_pct"],
        "guard_drawdown_pct":protected["max_drawdown_pct"],
        "guard":protected,
        "unchanged_original":plain,
        "benchmarks":refs,
    }


def audit_guard(history, *, fx_fetcher=fetch_fx_for_cycle):
    price=history["price_usd"].dropna().sort_index().loc[:CUTOFF]
    if price.empty:
        raise ValueError("Missing BTC daily history")
    historic=[]
    synthetic=[]
    for name,meta in PRIMARY.items():
        h=_utc(meta["halving"])
        end=min(h+pd.Timedelta(days=SCORE_DAYS),price.index[-1])
        fx=fx_fetcher(h,end)
        for offset in START_DAYS:
            start=h+pd.Timedelta(days=offset)
            if start>=end:continue
            row=compare(price,fx,start=start,terminal=end)
            row.update({
                "cycle":name,"start_day":offset,
                "complete":end==h+pd.Timedelta(days=SCORE_DAYS),
                "synthetic":False})
            historic.append(row)
        for label,startday,shockday in STRESS_COHORTS:
            if name!=label:continue
            if end!=h+pd.Timedelta(days=SCORE_DAYS):
                raise ValueError("Stress must have full historical score")
            start=h+pd.Timedelta(days=startday)
            for decline in STRESS_LOSSES:
                for finish in STRESS_TERMINALS:
                    alternative=delayed_bottom_path(
                        price,h,shock_start_day=shockday,
                        loss_fraction=decline,
                        terminal_price_fraction=finish,
                        trough_day=STRESS_TROUGH_DAY)
                    row=compare(alternative,fx,start=start,terminal=end)
                    row.update({
                        "cycle":name,"start_day":startday,"complete":True,
                        "synthetic":True,"shock_day":shockday,
                        "forced_trough_day":STRESS_TROUGH_DAY,
                        "shock_decline_pct":round(decline*100),
                        "terminal_pct_original_shock_spot":round(finish*100),
                    })
                    synthetic.append(row)
    return {
        "research_only":True,
        "hypothesis":"reduce unchanged original weekly spend by 50% only during a prior-30d 80%+ annualised vol and prior-50DMA falling downtrend",
        "volatility_definition":"30 strictly prior log returns, std ddof1 * sqrt(365)",
        "trend_definition":"prior price < prior50DMA < same SMA 14d earlier",
        "original_200wma_first_gate_unchanged":True,
        "earlier_historical_cycles_already_inspected":True,
        "2025_right_censored_at":str(price.index[-1].date()),
        "historical":historic,
        "synthetic_shocks":synthetic,
        "warnings":[
            "The guard is a newly proposed hypothesis with arbitrarily frozen thresholds; positive in-sample results are not predictive.",
            "Missed 50% spending is not caught up; a sharp recovery can make this worse than unguarded weekly DCA.",
            "Synthetic deep bear-market shocks are explicit counterfactuals, never probabilities or forecasts.",
            "The same post-start 200WMA crossing is needed in both models; the guard cannot solve no-cross missed-upside risk.",
            "Cash starts have no fictitious 2025 cycle SELL proceeds; BTC close and simplified SMSF FIFO tax are not executable IBIT returns.",
            "No production, portfolio, ntfy or real trades were modified.",
        ],
    }


def main(argv=None):
    parser=argparse.ArgumentParser()
    parser.add_argument("--out",type=Path,
                        default=Path("artifacts/volatility_trend_guard"))
    args=parser.parse_args(argv)
    result=audit_guard(read_exported_history())
    args.out.mkdir(parents=True,exist_ok=True)
    (args.out/"audit.json").write_text(json.dumps(result,indent=2))
    fields=("cycle","start_day","complete","start","terminal","first_gate",
            "guard_triggered_buy_count","guard_active_reviews",
            "guard_vs_original_aftertax_pct","guard_vs_current_daily_aftertax_pct",
            "guard_btc","original_btc","guard_cash_aud","original_cash_aud",
            "guard_buy_error_pct","original_buy_error_pct")
    for file,rows in (("historical.csv",result["historical"]),
                      ("synthetic_deeper_bottom.csv",result["synthetic_shocks"])):
        with (args.out/file).open("w",newline="") as handle:
            w=csv.DictWriter(handle,fieldnames=fields,extrasaction="ignore")
            w.writeheader()
            w.writerows(rows)
    for group in ("historical","synthetic_shocks"):
        for x in result[group]:
            print(json.dumps({
                "group":group,"cycle":x["cycle"],"startday":x["start_day"],
                "complete":x["complete"],
                "first_wma":x["first_gate"],
                "guard_active_reviews":x["guard_active_reviews"],
                "guarded_buys":x["guard_triggered_buy_count"],
                "relative_aftertax_pct":x["guard_vs_original_aftertax_pct"],
                "guard_btc":x["guard_btc"],"baseline_btc":x["original_btc"],
                "guard_cash_aud":x["guard_cash_aud"],
                "stress_drop":x.get("shock_decline_pct"),
                "stress_terminal_pct":x.get("terminal_pct_original_shock_spot"),
            }))
    print("RESEARCH ONLY - ORIGINAL STRATEGY AND ALL NOTIFICATIONS UNCHANGED")


if __name__=="__main__":
    main()
