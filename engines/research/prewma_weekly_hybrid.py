"""Research-only fresh-cash hybrid BUY: capped weekly starter then original 200WMA.

ONE FROZEN candidate. From the first day after a declared fresh cash start,
buy 1% of ORIGINAL AUD budget each 7 calendar days before the first eligible
prior-BTC-close-below-prior-200WMA, MAXIMUM 10% of original cash in all
pre-gate purchases. If first gate arrives, stop starter and start unchanged
2.5/15/4.5/1%-of-original-budget weekly adaptive recovery ON gate date.
Never use the eventual bottom as a trigger or move completed historical
order dates. No leverage; real 2026 IBIT positions and historic hypothetical
2016/2020/2024 initial BTC positions must NOT be conflated.

Compared with original weekly gated BUY, current 2.5%-of-remaining-cash
daily BUY below WMA, fixed 52-week DCA, and instant lump sum using same
USD BTC closes, strictly prior FX, AUD3/fill and simplified AUD FIFO SMSF
CGT. Shallow-no-cross and delayed 50/70% bottoms are NOT forecasts.
Historical data, thresholds, crash settings are already researcher-visible;
any observed win is IN SAMPLE, not evidence of a reliable future edge.
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

OBSERVED_CUTOFF = pd.Timestamp("2026-10-05", tz="UTC")
FROZEN_WEEKLY_PRE_GATE_FRACTION_ORIGINAL = .01
FROZEN_MAX_PRE_GATE_FRACTION_ORIGINAL = .10
BENCHMARKS = (
    "forward_original_budget_weekly",
    "current_2p5_remaining_cash_daily",
    "fixed_52_week_equal_cash",
    "immediate_lump_sum",
)
# Preset scenarios selected to expose 10% starter BEFORE a shock.
SHOCK_COHORTS = (
    ("2017", 900, 990),
    ("2017", 750, 960),
    ("2021", 650, 900),
)
SHOCK_LOSSES = (.50, .70)
TERMINAL_RECOVERIES = (.55, 1.05)
FORCED_TROUGH_DAY = 1060


def _utc(v):
    day = pd.Timestamp(v)
    return (day.tz_localize("UTC") if day.tz is None
            else day.tz_convert("UTC")).normalize()


def replay_capped_pre_gate_hybrid(price, fx, *, start, terminal,
                                  budget_aud=BUDGET_AUD, fee_aud=FEE_AUD,
                                  min_order_aud=MIN_ORDER_AUD):
    """Fully dated fresh cash AUD account; no earlier imaginary BTC lot."""
    start, terminal = _utc(start), _utc(terminal)
    if (not isinstance(price, pd.Series)
            or not isinstance(price.index, pd.DatetimeIndex)
            or price.index.tz is None or price.index.has_duplicates
            or not price.index.is_monotonic_increasing
            or start >= terminal or start not in price.index
            or terminal not in price.index):
        raise ValueError("Invalid chronological UTC start and terminal")
    required = pd.date_range(
        start-pd.Timedelta(days=1394), terminal, freq="D", tz="UTC")
    if not required.isin(price.index).all():
        raise ValueError("Missing continuous prior 200WMA or execution closes")
    vals = price.loc[required].to_numpy(dtype=float)
    if not np.isfinite(vals).all() or (vals <= 0).any():
        raise ValueError("BTC close nonfinite or nonpositive")
    if (not math.isfinite(float(budget_aud))
            or float(budget_aud) <= 100
            or not math.isfinite(float(fee_aud))
            or float(fee_aud) < 0
            or not math.isfinite(float(min_order_aud))
            or float(min_order_aud) <= fee_aud):
        raise ValueError("Invalid cash, fee or minimum order")

    account = AuditSmsfAccount(float(budget_aud), fee=float(fee_aud), tax=True)
    original_cash = float(account.cash)
    first_gate = None
    starter_spent = 0.
    orders = []
    bought_usd = 0.
    starter_fills = 0
    post_gate_fills = 0
    for date in pd.date_range(
            start+pd.Timedelta(days=1), terminal, freq="D", tz="UTC"):
        previous, wma = _historical_wma(price, date)
        if first_gate is None and previous < wma:
            first_gate = date
        pct = None
        mode = None
        gross = 0.
        if first_gate is not None:
            if (date-first_gate).days % 7 == 0:
                pct = recovery_buy_budget_fraction(
                    price.loc[:date], date, style="adaptive_recovery")[
                        "fraction_of_initial_buyback_cash"]
                gross = min(account.cash, original_cash*pct)
                mode = "unchanged_post_gate"
        elif (date-start).days % 7 == 1:
            pct = FROZEN_WEEKLY_PRE_GATE_FRACTION_ORIGINAL
            gross = min(
                account.cash,
                original_cash*pct,
                max(0.,original_cash*FROZEN_MAX_PRE_GATE_FRACTION_ORIGINAL
                    -starter_spent))
            mode = "capped_pre_gate"
        if gross > min_order_aud and gross > 2*fee_aud:
            spot_usd = float(price.loc[date])
            rate = fx_before(fx, date)
            if account.buy(date, spot_usd*rate,
                           min(1., gross/account.cash)):
                order=account.orders[-1]
                real_gross=float(order["gross_aud"])
                bought_usd+=real_gross/rate
                if mode=="capped_pre_gate":
                    starter_spent+=real_gross
                    starter_fills+=1
                    if starter_spent>original_cash*(
                            FROZEN_MAX_PRE_GATE_FRACTION_ORIGINAL+1e-9):
                        raise ArithmeticError("Exceeded fixed 10% starter budget")
                else:
                    post_gate_fills+=1
                orders.append({
                    "date":str(date.date()),
                    "mode":mode,
                    "gross_aud":round(real_gross,2),
                    "btc":round(float(order["btc"]),10),
                    "pct_original_cash":round(100*pct,4),
                    "prior_close_div_prior_200wma":round(previous/wma,5),
                })
        account.mark(float(price.loc[date])*fx_before(fx,date))
    final_usd=float(price.loc[terminal])
    final_aud=final_usd*fx_before(fx,terminal)
    original_bought=sum(float(x["btc"]) for x in account.orders
                        if x["side"]=="BUY")
    mean_price_usd=bought_usd/original_bought if original_bought>0 else None
    later_low=float(price.loc[start+pd.Timedelta(days=1):terminal].min())
    return {
        "policy":"pre_gate_1pct_weekly_max_10pct_then_original_recovery",
        "research_only":True,
        "live_ibit_parity_verified":False,
        "no_earlier_btc_sells_or_lots":True,
        "start_date":str(start.date()),
        "terminal_date":str(terminal.date()),
        "first_wma_gate_date":(
            str(first_gate.date()) if first_gate is not None else None),
        "pre_gate_gross_aud":round(starter_spent,2),
        "pre_gate_spent_pct_original":round(
            100*starter_spent/original_cash,4),
        "pre_gate_fills":starter_fills,
        "post_gate_fills":post_gate_fills,
        "fill_count":len(orders),
        "btc_purchased_and_held":round(account.btc,8),
        "cash_left_aud":round(account.cash,2),
        "cash_left_pct":round(100*account.cash/original_cash,2),
        "average_buy_usd_vwap":round(mean_price_usd,2)
            if mean_price_usd is not None else None,
        "buy_vwap_above_observed_low_pct":round(
            100*(mean_price_usd/later_low-1),2)
            if mean_price_usd is not None else None,
        "account_drawdown_pct":round(100*account.drawdown,2),
        "fee_total_aud":round(account.total_fees,2),
        "ending_after_illustrative_cgt_aud":round(
            account.liquidation_value(terminal,final_aud),2),
        "btc_equivalent_including_cash":round(
            account.btc+account.cash/final_aud,8),
        "orders":orders,
    }


def comparison(price,fx,*,start,terminal):
    """Fully matched independent benchmark simulations; no hindsight pick."""
    benchmarks={key:matched_fresh_cash_replay(
        price,fx,start=start,terminal=terminal,policy=key)
        for key in BENCHMARKS}
    candidate=replay_capped_pre_gate_hybrid(
        price,fx,start=start,terminal=terminal)
    orig=benchmarks["forward_original_budget_weekly"]
    if candidate["first_wma_gate_date"] != orig[
            "first_valid_200wma_activation_date"]:
        raise AssertionError("Hybrid changed the first original 200WMA gate")
    if candidate["pre_gate_spent_pct_original"] > (
            FROZEN_MAX_PRE_GATE_FRACTION_ORIGINAL*100+.0001):
        raise AssertionError("Pre-gate budget cap invalid")
    first=_utc(candidate["first_wma_gate_date"]) if candidate[
        "first_wma_gate_date"] else None
    if any(_utc(o["date"]) >= first for o in candidate["orders"]
           if o["mode"]=="capped_pre_gate") if first is not None else False:
        raise AssertionError("Pre-gate starter placed on/after first gate")
    if first is None and candidate["post_gate_fills"]:
        raise AssertionError("Post-gate buying without a trigger")
    vals={key:float(v["after_hypothetical_liquidation_cgt_aud"])
          for key,v in benchmarks.items()}
    value=candidate["ending_after_illustrative_cgt_aud"]
    return {
        "start":str(_utc(start).date()),
        "terminal":str(_utc(terminal).date()),
        "first_gate":candidate["first_wma_gate_date"],
        "pre_gate_spent_pct":candidate["pre_gate_spent_pct_original"],
        "pre_gate_fills":candidate["pre_gate_fills"],
        "hybrid_aftertax_aud":value,
        "original_aftertax_aud":vals[BENCHMARKS[0]],
        "hybrid_vs_original_pct":round(100*(value/vals[BENCHMARKS[0]]-1),3),
        "hybrid_vs_current_daily_pct":round(
            100*(value/vals[BENCHMARKS[1]]-1),3),
        "hybrid_vs_fixed_52week_pct":round(
            100*(value/vals[BENCHMARKS[2]]-1),3),
        "hybrid_vs_lump_pct":round(100*(value/vals[BENCHMARKS[3]]-1),3),
        "hybrid_btc":candidate["btc_purchased_and_held"],
        "original_btc":orig["btc_purchased_and_held"],
        "hybrid_cash_pct":candidate["cash_left_pct"],
        "original_cash_pct":orig["cash_left_pct"],
        "hybrid_buy_error_pct":candidate["buy_vwap_above_observed_low_pct"],
        "original_buy_error_pct":orig[
            "average_buy_error_above_observed_future_low_pct"],
        "hybrid_max_drawdown_pct":candidate["account_drawdown_pct"],
        "candidate":candidate,
        "benchmarks":benchmarks,
    }


def audit_weekly_hybrid(history,*,fx_fetcher=fetch_fx_for_cycle):
    if "price_usd" not in history:
        raise ValueError("Historical dated BTC USD close required")
    price=history["price_usd"].dropna().sort_index().loc[:OBSERVED_CUTOFF]
    if price.empty:
        raise ValueError("Missing historical prices")
    cohorts=[]
    stress=[]
    for label,meta in PRIMARY.items():
        h=_utc(meta["halving"])
        end=min(h+pd.Timedelta(days=SCORE_DAYS),price.index[-1])
        fx=fx_fetcher(h,end)
        for offset in START_DAYS:
            start=h+pd.Timedelta(days=int(offset))
            if start>=end:continue
            result=comparison(price,fx,start=start,terminal=end)
            result.update({
                "cycle":label,"cash_start_day":offset,
                "complete":end==h+pd.Timedelta(days=SCORE_DAYS),
                "synthetic":False,
            })
            cohorts.append(result)
        if label=="2025":
            continue
        if end!=h+pd.Timedelta(days=SCORE_DAYS):
            raise ValueError("Delayed-bottom shocks need full completed cycle")
        for name,startday,shockday in SHOCK_COHORTS:
            if label!=name:continue
            start=h+pd.Timedelta(days=startday)
            for loss in SHOCK_LOSSES:
                for recovery in TERMINAL_RECOVERIES:
                    prices=delayed_bottom_path(
                        price,h,shock_start_day=shockday,
                        loss_fraction=loss,
                        terminal_price_fraction=recovery,
                        trough_day=FORCED_TROUGH_DAY)
                    result=comparison(prices,fx,start=start,terminal=end)
                    result.update({
                        "cycle":label,"cash_start_day":startday,
                        "complete":True,"synthetic":True,
                        "shock_day":shockday,"forced_trough_day":FORCED_TROUGH_DAY,
                        "shock_drop_pct":100*loss,
                        "terminal_fraction_of_preshock_pct":100*recovery,
                    })
                    stress.append(result)
    if not stress or not cohorts:
        raise AssertionError("Incomplete matched audit")
    # Critical: call 'exposed to shock' ONLY if a starter buy happened
    # at or before the historical pre-shock prefix date.
    for x in stress:
        h=_utc(PRIMARY[x["cycle"]]["halving"])
        shockday=h+pd.Timedelta(days=x["shock_day"])
        pre=[o for o in x["candidate"]["orders"]
             if o["mode"]=="capped_pre_gate" and _utc(o["date"])<=shockday]
        x["starter_fills_before_shock"]=len(pre)
        x["starter_cash_pct_before_shock"]=round(
            sum(o["gross_aud"] for o in pre)/BUDGET_AUD*100,4)
    if not any(x["starter_fills_before_shock"] for x in stress):
        raise AssertionError("Vacuous shock: no hybrid starter actually exposed")
    return {
        "study":"Capped 1% original weekly first-cash deployment before first 200WMA gate",
        "research_only":True,
        "production_and_daily_notifications_unchanged":True,
        "available_history_through":str(price.index[-1].date()),
        "cash_start_budget_aud":BUDGET_AUD,
        "pre_gate_buy_pct_original_each_7days":1.,
        "pre_gate_budget_cap_pct_original":10.,
        "after_first_gate":"unchanged 200WMA adaptive recovery original budget",
        "onchain_signals_used":False,
        "lookahead_in_decisions":False,
        "already_inspected_out_of_sample":False,
        "completed_periods":["2017","2021"],
        "right_censored_period":"2025/26",
        "historical":cohorts,
        "synthetic_delayed_bottom":stress,
        "warnings":[
            "Earlier historical BTC cycles and alternative pre-gate starters have already been analysed; results are in sample.",
            "Pre-gate cap is 10% of original budget; subsequent original DCA can invest the remainder fully before a later trough.",
            "A higher BTC nominal low is not a guarantee of fewer percentage declines or no new 200WMA crossing.",
            "The 2025/26 low and score horizon after 5 October 2026 remain unobserved.",
            "BTC USD close is not an executable IBIT/AUD quote. FX and FIFO SMSF taxes are illustrative.",
            "No prior cycle BTC sale is attributed to a fresh 2026 cash portfolio.",
        ],
    }


def main(argv=None):
    p=argparse.ArgumentParser()
    p.add_argument("--out",type=Path,
                   default=Path("artifacts/prewma_weekly_hybrid"))
    args=p.parse_args(argv)
    result=audit_weekly_hybrid(read_exported_history())
    args.out.mkdir(parents=True,exist_ok=True)
    (args.out/"audit.json").write_text(json.dumps(result,indent=2))
    keys=(
        "cycle","cash_start_day","start","terminal","complete",
        "first_gate","pre_gate_spent_pct","hybrid_aftertax_aud",
        "original_aftertax_aud","hybrid_vs_original_pct",
        "hybrid_vs_current_daily_pct","hybrid_vs_fixed_52week_pct",
        "hybrid_vs_lump_pct","hybrid_btc","original_btc",
        "hybrid_cash_pct","original_cash_pct","hybrid_buy_error_pct",
        "original_buy_error_pct",
    )
    for name,rows in (("historic.csv",result["historical"]),
                      ("synthetic_delayed_bottom.csv",
                       result["synthetic_delayed_bottom"])):
        with (args.out/name).open("w",newline="") as handle:
            writer=csv.DictWriter(handle,fieldnames=keys,extrasaction="ignore")
            writer.writeheader()
            writer.writerows(rows)
    for group in ("historical","synthetic_delayed_bottom"):
        for r in result[group]:
            print(json.dumps({
                "group":group,"cycle":r["cycle"],
                "startday":r["cash_start_day"],
                "complete":r["complete"],
                "gate":r["first_gate"],
                "pre_gate_pct":r["pre_gate_spent_pct"],
                "vs_original_pct":r["hybrid_vs_original_pct"],
                "vs_current_daily_pct":r["hybrid_vs_current_daily_pct"],
                "vs_fixed_weekly_pct":r["hybrid_vs_fixed_52week_pct"],
                "vs_lump_pct":r["hybrid_vs_lump_pct"],
                "btc_hybrid":r["hybrid_btc"],
                "btc_original":r["original_btc"],
                "cash_hybrid_pct":r["hybrid_cash_pct"],
                "synthetic":r["synthetic"],
                "starter_before_shock":r.get("starter_cash_pct_before_shock"),
            }))
    print("NO LIVE TRADING RULES CHANGED")


if __name__=="__main__":
    main()
