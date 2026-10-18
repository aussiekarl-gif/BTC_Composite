"""Frozen first-below-200WMA 10%-budget BUY (fresh AUD CASH, not legacy BTC).

Test exactly ONE new first-gate fraction: 10% of ORIGINAL AUD cash
instead of the original 2.5% on the FIRST eligible prior-close-below-
prior-200WMA review. All subsequent fixed-original-budget weekly
adaptive-recovery tiers, gate, fees, tax and execution assumptions match.
The 10% is an additional 7.5% invested at the same initial gate:
do not claim unchanged later total deployment, or that the change
protects from a later, deeper trough.

No retrospective BTC holdings, top selling, personal trade instruction,
repainting, production/ntfy or Google Sheets writes.
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

EXPERIMENTAL_FIRST_GATE_FRACTION = .10
ORIGINAL_FIRST_GATE_FRACTION = .025
ALLOWED_FIRST_FRACTIONS = (ORIGINAL_FIRST_GATE_FRACTION,
                           EXPERIMENTAL_FIRST_GATE_FRACTION)
OBSERVED_CUTOFF = pd.Timestamp("2026-10-05", tz="UTC")
STRESS_SCENARIOS = (("2017", 750, 960), ("2021", 650, 900))
STRESS_DROPS = (.50, .70)
STRESS_TERMINALS = (.55, 1.05)
STRESS_TROUGH_DAY = 1060
REFERENCE_POLICIES = ("forward_original_budget_weekly",
                      "current_2p5_remaining_cash_daily",
                      "fixed_52_week_equal_cash", "immediate_lump_sum")


def _utc(value):
    date = pd.Timestamp(value)
    return (date.tz_localize("UTC") if date.tz is None
            else date.tz_convert("UTC")).normalize()


def replay_first_gate_allocation(price, fx, *, start, terminal,
                                 first_gate_fraction=EXPERIMENTAL_FIRST_GATE_FRACTION,
                                 budget_aud=BUDGET_AUD, fee_aud=FEE_AUD,
                                 min_order_aud=MIN_ORDER_AUD):
    """One chronological self-financing fresh-cash-only buy ledger."""
    if first_gate_fraction not in ALLOWED_FIRST_FRACTIONS:
        raise ValueError("Not a predeclared first-gate fraction")
    start, terminal = _utc(start), _utc(terminal)
    if (not isinstance(price, pd.Series)
            or not isinstance(price.index, pd.DatetimeIndex)
            or price.index.tz is None or price.index.has_duplicates
            or not price.index.is_monotonic_increasing
            or start not in price.index or terminal not in price.index
            or start >= terminal):
        raise ValueError("Invalid ordered dated BTC entry/endpoints")
    dates = pd.date_range(start-pd.Timedelta(days=1394),terminal,
                          freq="D",tz="UTC")
    if not dates.isin(price.index).all():
        raise ValueError("Missing continuous 200WMA historical prices")
    checks = price.loc[dates].to_numpy(dtype=float)
    if not np.isfinite(checks).all() or np.any(checks <= 0):
        raise ValueError("Invalid historical/forward BTC prices")
    if (not math.isfinite(float(budget_aud))
            or budget_aud <= 100 or not math.isfinite(float(fee_aud))
            or fee_aud < 0 or not math.isfinite(float(min_order_aud))
            or min_order_aud <= fee_aud):
        raise ValueError("Invalid cash/fee/minimum order")
    account = AuditSmsfAccount(float(budget_aud), fee=float(fee_aud), tax=True)
    first_gate = None
    initial = float(account.cash)
    orders = []
    bought_usd = 0.
    for date in pd.date_range(start+pd.Timedelta(days=1),
                              terminal,freq="D",tz="UTC"):
        prev, wma = _historical_wma(price, date)
        if first_gate is None and prev < wma:
            first_gate = date
        if first_gate is not None and (date-first_gate).days%7 == 0:
            step = recovery_buy_budget_fraction(
                price.loc[:date],date,style="adaptive_recovery")
            frac = (first_gate_fraction if date == first_gate else
                    step["fraction_of_initial_buyback_cash"])
            gross = min(account.cash,initial*frac)
            if gross > min_order_aud and gross > 2*fee_aud:
                spot_usd = float(price.loc[date])
                fx_rate = fx_before(fx,date)
                if account.buy(date,spot_usd*fx_rate,
                               min(1.,gross/account.cash)):
                    order = account.orders[-1]
                    bought_usd += float(order["gross_aud"])/fx_rate
                    orders.append({
                        "date": str(date.date()),
                        "gross_aud":round(float(order["gross_aud"]),2),
                        "btc":round(float(order["btc"]),10),
                        "pct_original_budget":round(100*frac,4),
                        "first_gate_order": date==first_gate,
                        "prior_btc_usd_to_prior_200wma":round(prev/wma,5),
                    })
        account.mark(float(price.loc[date])*fx_before(fx,date))
    end_px=float(price.loc[terminal])*fx_before(fx,terminal)
    lowest=float(price.loc[start+pd.Timedelta(days=1):terminal].min())
    quantity=sum(float(o["btc"]) for o in account.orders if o["side"]=="BUY")
    avg_usd=bought_usd/quantity if quantity>0 else None
    return {
        "research_only":True,
        "live_trading_parity_validated":False,
        "fresh_cash_only":True,
        "start_date":str(start.date()),
        "terminal_date":str(terminal.date()),
        "first_gate_fraction_pct_original":round(100*first_gate_fraction,4),
        "first_wma_gate":str(first_gate.date()) if first_gate is not None else None,
        "fill_count":len(orders),
        "btc_purchased_and_held":round(account.btc,8),
        "cash_left_aud":round(account.cash,2),
        "cash_left_pct":round(100*account.cash/initial,2),
        "after_hypothetical_liquidation_cgt_aud":round(
            account.liquidation_value(terminal,end_px),2),
        "terminal_btc_equivalent_including_cash":round(
            account.btc+account.cash/end_px,8),
        "average_buy_usd_vwap":round(avg_usd,2) if avg_usd is not None else None,
        "average_buy_error_above_observed_future_low_pct":(
            round(100*(avg_usd/lowest-1),2) if avg_usd is not None else None),
        "observed_low_usd":round(lowest,2),
        "fee_total_aud":round(account.total_fees,2),
        "max_drawdown_pct":round(100*account.drawdown,2),
        "orders":orders,
    }


def _compare(price,fx,*,start,terminal,full=False):
    benchmark={name:matched_fresh_cash_replay(
        price,fx,start=start,terminal=terminal,policy=name)
        for name in REFERENCE_POLICIES}
    original = replay_first_gate_allocation(
        price,fx,start=start,terminal=terminal,
        first_gate_fraction=ORIGINAL_FIRST_GATE_FRACTION)
    ref = benchmark["forward_original_budget_weekly"]
    for field in ("first_wma_gate","fill_count","btc_purchased_and_held",
                  "cash_left_aud","cash_left_pct",
                  "after_hypothetical_liquidation_cgt_aud",
                  "fee_total_aud"):
        expected = ("first_valid_200wma_activation_date"
                    if field=="first_wma_gate" else field)
        if original[field] != ref[expected]:
            raise AssertionError(
                f"Original 2.5% parity failed {field}: "
                f"{original[field]} vs {ref[expected]}")
    candidate=replay_first_gate_allocation(
        price,fx,start=start,terminal=terminal)
    if candidate["first_wma_gate"] != original["first_wma_gate"]:
        raise AssertionError("First gate timing unexpectedly changed")
    if original["first_wma_gate"] is None and (
        candidate["fill_count"] or candidate["cash_left_pct"] != 100):
        raise AssertionError("Candidate bought without a strictly prior-WMA gate")
    baseline_aud=ref["after_hypothetical_liquidation_cgt_aud"]
    candidate_aud=candidate["after_hypothetical_liquidation_cgt_aud"]
    return {
        "start":str(_utc(start).date()),"end":str(_utc(terminal).date()),
        "first_gate":candidate["first_wma_gate"],
        "first_order_10pct":(
            candidate["orders"][0]["gross_aud"] if candidate["orders"]
            else None),
        "original_first_order_2p5pct":(
            ref["orders"][0]["gross_aud"] if ref["orders"] else None),
        "candidate_aud":candidate_aud,
        "original_aud":baseline_aud,
        "candidate_vs_original_aud":round(candidate_aud-baseline_aud,2),
        "candidate_vs_original_pct":round(
            100*(candidate_aud/baseline_aud-1),3),
        "candidate_vs_current_daily_pct":round(
            100*(candidate_aud/benchmark[
                "current_2p5_remaining_cash_daily"
            ]["after_hypothetical_liquidation_cgt_aud"]-1),3),
        "candidate_vs_fixed_dca_pct":round(
            100*(candidate_aud/benchmark[
                "fixed_52_week_equal_cash"
            ]["after_hypothetical_liquidation_cgt_aud"]-1),3),
        "candidate_vs_lump_pct":round(
            100*(candidate_aud/benchmark[
                "immediate_lump_sum"
            ]["after_hypothetical_liquidation_cgt_aud"]-1),3),
        "candidate_buy_error_pct":candidate[
            "average_buy_error_above_observed_future_low_pct"],
        "original_buy_error_pct":ref[
            "average_buy_error_above_observed_future_low_pct"],
        "candidate_cash_left_pct":candidate["cash_left_pct"],
        "original_cash_left_pct":ref["cash_left_pct"],
        "candidate_drawdown_pct":candidate["max_drawdown_pct"],
        "candidate_btc":candidate["btc_purchased_and_held"],
        "original_btc":ref["btc_purchased_and_held"],
        **({"candidate":candidate,"original":original,
            "comparators":benchmark} if full else {}),
    }


def audit_10pct_gate(history, *, fx_fetcher=fetch_fx_for_cycle):
    price=history["price_usd"].sort_index().loc[:OBSERVED_CUTOFF]
    if price.empty:
        raise ValueError("Empty dated BTC research prices")
    real=[]
    stress=[]
    for label,meta in PRIMARY.items():
        h=_utc(meta["halving"])
        end=min(h+pd.Timedelta(days=SCORE_DAYS),price.index[-1])
        fx=fx_fetcher(h,end)
        for offset in START_DAYS:
            start=h+pd.Timedelta(days=offset)
            if start>=end: continue
            result=_compare(price,fx,start=start,terminal=end)
            result.update({
                "cycle":label,
                "complete":end==h+pd.Timedelta(days=SCORE_DAYS),
                "start_day":offset,
                "synthetic":False,
            })
            real.append(result)
        for name,day,shock_day in STRESS_SCENARIOS:
            if name!=label:continue
            start=h+pd.Timedelta(days=day)
            if end!=h+pd.Timedelta(days=SCORE_DAYS):
                raise AssertionError("Synthetic stress requires full completed cycle")
            for loss in STRESS_DROPS:
                for recovery in STRESS_TERMINALS:
                    modified=delayed_bottom_path(
                        price,h,shock_start_day=shock_day,
                        loss_fraction=loss,
                        terminal_price_fraction=recovery)
                    result=_compare(modified,fx,start=start,terminal=end)
                    result.update({
                        "cycle":label,"complete":True,
                        "start_day":day,"synthetic":True,
                        "shock_day":shock_day,
                        "forced_trough_day":STRESS_TROUGH_DAY,
                        "shock_drop_pct":round(100*loss),
                        "terminal_pct_of_preschock_price":round(100*recovery),
                    })
                    stress.append(result)
    if not real or len(stress)!=(
            len(STRESS_SCENARIOS)*len(STRESS_DROPS)*len(STRESS_TERMINALS)):
        raise AssertionError("Incomplete frozen research scenarios")
    for case in stress:
        if case["first_gate"] is None:
            raise AssertionError("Stress does not expose a post-trigger first buy")
    return {
        "research_only":True,
        "policy_frozen":"10% original cash first STRICT prior-close below prior 200WMA, original normal weekly subsequent fractions",
        "reference_unchanged":True,
        "cash_starts_only_no_historical_sell":True,
        "btc_close_execution_proxy_not_ASX_IBIT":True,
        "aftertax":"Illustrative FIFO immediate SMSF CGT, dated prior FX, AUD3 fees",
        "observed_through":str(price.index[-1].date()),
        "completed_score_windows":["2017","2021"],
        "incomplete_cycle":"2025/26",
        "already_inspected_not_out_of_sample":True,
        "historical":real,"synthetic_stress":stress,
    }


def main(argv=None):
    p=argparse.ArgumentParser()
    p.add_argument("--out",type=Path,
                   default=Path("artifacts/first_gate_10pct"))
    args=p.parse_args(argv)
    result=audit_10pct_gate(read_exported_history())
    args.out.mkdir(parents=True,exist_ok=True)
    (args.out/"summary.json").write_text(json.dumps(result,indent=2))
    columns=("cycle","start_day","start","end","complete","first_gate",
             "candidate_vs_original_pct","candidate_vs_current_daily_pct",
             "candidate_buy_error_pct","original_buy_error_pct",
             "candidate_cash_left_pct","original_cash_left_pct")
    for title,rows in (("historical.csv",result["historical"]),
                       ("synthetic_stress.csv",result["synthetic_stress"])):
        with (args.out/title).open("w",newline="") as output:
            writer=csv.DictWriter(output,fieldnames=columns,extrasaction="ignore")
            writer.writeheader()
            writer.writerows(rows)
    for row in result["historical"]:
        print(json.dumps({k:row[k] for k in (
            "cycle","start_day","complete","first_gate",
            "candidate_vs_original_pct","candidate_vs_current_daily_pct",
            "candidate_buy_error_pct","original_buy_error_pct")}))
    for row in result["synthetic_stress"]:
        print(json.dumps({k:row[k] for k in (
            "cycle","start_day","shock_day","shock_drop_pct",
            "terminal_pct_of_preschock_price","candidate_vs_original_pct",
            "candidate_vs_current_daily_pct")}))
    print("RESEARCH ONLY; no live trading change")


if __name__=="__main__":
    main()
