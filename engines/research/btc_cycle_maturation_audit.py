"""Frozen historical BTC cycle-maturation / WMA timing *diagnostic*.

No trading changes, allocations, new price targets or parameter search.
Only dated BTC USD CLOSES enter; MVRV/NUPL/SOPR are NOT indicator inputs.

Hindsight peak (+350..+800 halving days) and post-peak low (from later
of peak and +744 to terminal) label outcomes, NEVER choose a BUY. The
original after-sell buy gate is FIRST prior-close below prior 200WMA at
halving+744 or later. Also inspect fresh-cash starts +650/+750/+850/+900
without pretending a previous halving BTC purchase/sale happened.

Historic 2017/2021 observed to +1150; 2025/26 truncated Oct 5 2026.
The comparison contains TWO completed modern historical cycles. Nominal
higher lows and shrinking absolute multiples are NOT forward proof of
shallower drawdowns or future 200WMA behavior.
"""
from __future__ import annotations

import argparse
import csv
import json
import math
from pathlib import Path

import numpy as np
import pandas as pd

from engines.research.cycle_chronological_wallet import (
    previously_completed_200wma_breach,
)
from engines.research.cycle_indicator_timing_audit import (
    original_calendar_events,
)
from engines.research.day500_aftertax_reinvestment import PRIMARY, SCORE_DAYS
from engines.research.fresh_cash_200wma_matched_backtest import (
    START_DAYS, _historical_wma,
)
from engines.research.top_signal_horse_race import read_exported_history

CUTOFF = pd.Timestamp("2026-10-05", tz="UTC")
PEAK_WINDOW = (350, 800)
EARLIEST_ORIGINAL_BUY_DAY = 744
LOW_SCORE_END_DAY = SCORE_DAYS
POST_GATE_OBSERVATION_DAYS = 90


def _utc(v):
    d = pd.Timestamp(v)
    return (d.tz_localize("UTC") if d.tzinfo is None
            else d.tz_convert("UTC")).normalize()


def first_eligible_prior_wma(price, start, end):
    """Strictly prior-completed daily close and 200 spaced weekly closes.

    This is a causal FIRST eligible date, NOT the date nearest future low.
    """
    start, end = _utc(start), _utc(end)
    if end < start:
        return None
    for date in pd.date_range(start, end, freq="D", tz="UTC"):
        previous, moving = _historical_wma(price, date)
        if previous < moving:
            return date
    return None


def verify_price(price, halving, terminal):
    h, end = _utc(halving), _utc(terminal)
    if (not isinstance(price, pd.Series)
            or not isinstance(price.index, pd.DatetimeIndex)
            or price.index.tz is None
            or not price.index.is_unique
            or not price.index.is_monotonic_increasing
            or h not in price.index or end not in price.index
            or not h < end <= h+pd.Timedelta(days=SCORE_DAYS)):
        raise ValueError("Unique ordered UTC BTC prices and cycle dates required")
    # All previous 200 weekly observation dates through the earliest
    # historical review date must be available, not fabricated.
    warmup = h + pd.Timedelta(days=EARLIEST_ORIGINAL_BUY_DAY - 1394)
    if not pd.date_range(warmup, end, freq="D", tz="UTC").isin(price.index).all():
        raise ValueError("Missing required 200WMA daily history")
    arr = price.loc[warmup:end].to_numpy(dtype=float)
    if not np.isfinite(arr).all() or np.any(arr <= 0):
        raise ValueError("Missing/nonpositive BTC historical price")
    if end < h+pd.Timedelta(days=PEAK_WINDOW[0]):
        raise ValueError("Historical top observation not yet available")
    return h, end


def gate_snapshot(price, halving, terminal):
    """First original review plus snapshots; never consult a future trough."""
    h, end = verify_price(price, halving, terminal)
    gate = first_eligible_prior_wma(
        price, h+pd.Timedelta(days=EARLIEST_ORIGINAL_BUY_DAY), end)
    if gate is None:
        return {
            "first_gate": None,
            "first_gate_price_usd": None,
            "prior_close_to_200wma_pct": None,
            "first_gate_halving_age_days": None,
            "prior_90d_drawdown_pct": None,
        }
    previous, moving = _historical_wma(price, gate)
    high = float(price.loc[
        gate-pd.Timedelta(days=90):gate-pd.Timedelta(days=1)].max())
    return {
        "first_gate": str(gate.date()),
        "first_gate_price_usd": round(float(price.loc[gate]), 2),
        "prior_close_to_200wma_pct": round(100*previous/moving, 2),
        "first_gate_halving_age_days": (gate-h).days,
        "prior_90d_drawdown_pct": round(100*(1-previous/high), 2),
    }


def cycle_maturation_metrics(price, halving, terminal, *, label):
    """Peak, low and price-floor comparisons are strictly ex-post labels."""
    h, end = verify_price(price, halving, terminal)
    top_block = price.loc[
        h+pd.Timedelta(days=PEAK_WINDOW[0]):
        min(h+pd.Timedelta(days=PEAK_WINDOW[1]),end)]
    peak_date = top_block.idxmax()
    peak = float(top_block.max())
    low_start = max(peak_date,
                    h+pd.Timedelta(days=EARLIEST_ORIGINAL_BUY_DAY))
    low_block = price.loc[low_start:end]
    if low_block.empty:
        raise ValueError("No post-peak low observation; cannot compare")
    low_date = low_block.idxmin()
    low = float(low_block.min())

    signal = gate_snapshot(price,h,end)
    # Independent historical existing research must agree with the
    # original earliest-eligible dated 200WMA gate (same prior policy).
    original = original_calendar_events(price,h,end)
    if signal["first_gate"] != original["first_buy_activation_date"]:
        raise AssertionError("Changed the original earliest 200WMA BUY date")
    gate = _utc(signal["first_gate"]) if signal["first_gate"] else None
    if gate is None:
        post_gate_low_gap = None
        gate_vs_low_price_pct = None
        first90_below_days = None
        first90_observed_days = 0
    else:
        post_gate_low_gap = (low_date-gate).days
        gate_vs_low_price_pct = round(
            100*(float(price.loc[gate])/low-1),2)
        first90_end = min(end,gate+pd.Timedelta(days=POST_GATE_OBSERVATION_DAYS-1))
        scores = pd.date_range(gate,first90_end,freq="D",tz="UTC")
        first90_below_days = sum(
            _historical_wma(price,date)[0] < _historical_wma(price,date)[1]
            for date in scores)
        first90_observed_days = len(scores)

    _, bottom_wma = _historical_wma(price,low_date)
    # This bottom-to-WMA ratio is purely retrospective; the bottom date
    # MUST NEVER enter first_eligible_prior_wma() or any trading action.
    cohorts=[]
    for offset in START_DAYS:
        start = h+pd.Timedelta(days=int(offset))
        if start>=end: continue
        first = first_eligible_prior_wma(
            price, start+pd.Timedelta(days=1),end)
        cohorts.append({
            "start_age_days": int(offset),
            "start_date":str(start.date()),
            "first_post_start_prior_wma_eligible":
                str(first.date()) if first is not None else None,
            "cash_wait_days_to_first_gate":
                (first-start).days if first is not None else None,
            "zero_gate_through_terminal": first is None,
        })

    return {
        "cycle":label,
        "halving":str(h.date()),
        "observed_through":str(end.date()),
        "full_day1150_observed":end==h+pd.Timedelta(days=SCORE_DAYS),
        "peak_window_full":end>=h+pd.Timedelta(days=PEAK_WINDOW[1]),
        "peak_date_expost":str(peak_date.date()),
        "peak_usd":round(peak,2),
        "peak_halving_age_days":(peak_date-h).days,
        "post_peak_low_date_expost":str(low_date.date()),
        "post_peak_low_usd":round(low,2),
        "low_halving_age_days":(low_date-h).days,
        "peak_to_low_days_expost":(low_date-peak_date).days,
        "peak_to_low_drawdown_pct_expost":round(100*(1-low/peak),2),
        "post_peak_low_vs_prior_200wma_pct_expost":round(
            100*(low/bottom_wma-1),2),
        **signal,
        "gate_to_observed_low_days_expost":post_gate_low_gap,
        "first_gate_execution_price_above_observed_low_pct_expost":
            gate_vs_low_price_pct,
        "below_wma_days_in_first_90_after_gate_expost":first90_below_days,
        "observed_days_in_first_90_after_gate":first90_observed_days,
        "fresh_cash_cohorts":cohorts,
        "terminal_censored_low_not_final":end<h+pd.Timedelta(days=SCORE_DAYS),
        "hindsight_peaks_lows_never_used_to_buy":True,
    }


def audit_maturation_history(history):
    if "price_usd" not in history:
        raise ValueError("Missing dated BTC USD reference price")
    price=history["price_usd"].sort_index().loc[:CUTOFF]
    if price.empty:
        raise ValueError("No completed observed historical BTC prices")
    records=[]
    previous=None
    for label,item in PRIMARY.items():
        h=_utc(item["halving"])
        end=min(h+pd.Timedelta(days=SCORE_DAYS),price.index[-1])
        item=cycle_maturation_metrics(price,h,end,label=label)
        if previous is not None:
            item["peak_multiple_prior_cohort_expost"]=round(
                item["peak_usd"]/previous["peak_usd"],3)
            item["nominal_low_multiple_prior_cohort_expost"]=round(
                item["post_peak_low_usd"]/previous["post_peak_low_usd"],3)
            item["peak_drawdown_change_pp_prior_cohort_expost"]=round(
                item["peak_to_low_drawdown_pct_expost"]-
                previous["peak_to_low_drawdown_pct_expost"],2)
        else:
            item["peak_multiple_prior_cohort_expost"]=None
            item["nominal_low_multiple_prior_cohort_expost"]=None
            item["peak_drawdown_change_pp_prior_cohort_expost"]=None
        records.append(item)
        previous=item
    return {
        "study":"BTC cycle maturation measured using ex-post peaks, low timing, and causal prior-weekly WMA signals",
        "research_only":True,
        "changes_to_live_buy_sell":False,
        "onchain_signals_used":False,
        "confirmed_complete_cycles":sum(r["full_day1150_observed"] for r in records),
        "no_out_of_sample_maturation_claim":True,
        "future_bear_low_not_known":True,
        "cutoff":str(price.index[-1].date()),
        "peak_window_halving_days":list(PEAK_WINDOW),
        "post_peak_low_window":"max(peak_day,+744) through observed cohort terminal",
        "original_buy_gate":"first original eligible review +744 strictly prior-close < prior-200WMA",
        "fresh_cash_buy_gate":"first eligible review after each fixed cash start, never synthetic prior cycle sales",
        "cycles":records,
        "limitations":[
            "Only 2017 and 2021 observed 1150-day complete windows; sample too small to infer regime-change trend reliably.",
            "2025/26 observed low is right-censored. Neither trend nor a safe price floor can be inferred.",
            "Nominal higher lows differ from smaller percentage drawdowns, shorter peak-to-trough times, and improved 200WMA accuracy.",
            "Historical October-2026 onchain CSV price field provides daily reference USD BTC close, not executable ASX IBIT orders.",
            "All peaks/lows, completed-cycle high multipliers, drawdowns and post-gate day counts are RETROSPECTIVE outcome labels, never used to make a real-time trade.",
            "First eligible prior-WMA dates can differ by declared fresh-cash start; no user holdings or 2025 proceeds assumed.",
            "2013 intentionally excluded from PRIMARY per previous user request.",
        ],
    }


def main(argv=None):
    p=argparse.ArgumentParser()
    p.add_argument("--out",type=Path,default=Path("artifacts/cycle_maturation"))
    a=p.parse_args(argv)
    result=audit_maturation_history(read_exported_history())
    a.out.mkdir(parents=True,exist_ok=True)
    (a.out/"audit.json").write_text(json.dumps(result,indent=2))
    columns=[
        "cycle","full_day1150_observed","peak_date_expost","peak_usd",
        "peak_halving_age_days","post_peak_low_date_expost",
        "post_peak_low_usd","low_halving_age_days",
        "peak_to_low_days_expost","peak_to_low_drawdown_pct_expost",
        "first_gate","first_gate_halving_age_days",
        "gate_to_observed_low_days_expost",
        "first_gate_execution_price_above_observed_low_pct_expost",
        "post_peak_low_vs_prior_200wma_pct_expost",
        "peak_multiple_prior_cohort_expost",
        "nominal_low_multiple_prior_cohort_expost",
        "peak_drawdown_change_pp_prior_cohort_expost"]
    with (a.out/"cycle_summary.csv").open("w",newline="") as stream:
        writer=csv.DictWriter(stream,fieldnames=columns,extrasaction="ignore")
        writer.writeheader()
        writer.writerows(result["cycles"])
    with (a.out/"fresh_cash_gate_timings.csv").open("w",newline="") as stream:
        cols=["cycle","full_day1150_observed","start_age_days",
              "start_date","first_post_start_prior_wma_eligible",
              "cash_wait_days_to_first_gate","zero_gate_through_terminal"]
        writer=csv.DictWriter(stream,fieldnames=cols)
        writer.writeheader()
        for cycle in result["cycles"]:
            for cohort in cycle["fresh_cash_cohorts"]:
                writer.writerow({"cycle":cycle["cycle"],
                                 "full_day1150_observed":cycle["full_day1150_observed"],
                                 **cohort})
    for row in result["cycles"]:
        print(json.dumps({k:row[k] for k in columns if k in row}))
    print("DIAGNOSTIC ONLY: no policy tuning, future-bottom claims or live trade changes")


if __name__=="__main__":
    main()
