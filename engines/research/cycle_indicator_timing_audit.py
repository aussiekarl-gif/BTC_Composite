"""Frozen research audit of ORIGINAL cycle top and bottom signal TIMING.

No new thresholds, portfolios, trading suggestions, or indicator optimisation.
Critically, evaluate the FIRST alert in an ex-ante known halving-relative
observation window. Previous peak-horse-race research could report the
RETROSPECTIVELY nearest alert, which is NOT prospectively selectable.

The eventual high/low and "days relative to high/low" are hindsight
SCORING LABELS only; they never select trading times. Close execution
T is optimistic for IBIT ASX, so compare 1/3/7 calendar-day delays as
timing sensitivities rather than claim executable ETF prices.
2017/2021 are previously inspected; 2025/26 is right-censored after
the real observed archive. October-2026 exported onchain values may be
revised vs historical publication vintages, even with causal shifting.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd

from engines.research.shared_cycle_policy import (
    START_DAY,REVIEW_DAY,
    exit_review_days,staged_exit_decision,recovery_buy_budget_fraction,
)
from engines.research.cycle_chronological_wallet import (
    previously_completed_200wma_breach,
)
from engines.research.day500_aftertax_reinvestment import (
    PRIMARY,SCORE_DAYS,DELAY_DAYS_AFTER_LAST_SELL,
)
from engines.research.top_signal_horse_race import (
    SIGNALS,distinct_events,build_daily_signals,read_exported_history,
)

PEAK_WINDOW=(350,800)
BUY_EARLIEST_DAY=REVIEW_DAY+DELAY_DAYS_AFTER_LAST_SELL
EXECUTION_DELAYS_DAYS=(0,1,3,7)
CUTOFF=pd.Timestamp("2026-10-05",tz="UTC")


def _utc(t):
    t=pd.Timestamp(t)
    return (t.tz_localize("UTC") if t.tzinfo is None
            else t.tz_convert("UTC")).normalize()


def _window_peak(price,halving,terminal):
    """Hindsight evaluation only; never used to generate any trade or alert."""
    start=halving+pd.Timedelta(days=PEAK_WINDOW[0])
    finish=min(terminal,halving+pd.Timedelta(days=PEAK_WINDOW[1]))
    observed=price.loc[start:finish]
    if observed.empty:
        raise ValueError("Peak scoring window has no observed prices")
    day=observed.idxmax()
    return {
        "date":str(day.date()),"usd":round(float(observed.max()),2),
        "full_350_to_800_window_observed":bool(
            terminal>=halving+pd.Timedelta(days=PEAK_WINDOW[1])),
    }


def _window_low(price,halving,terminal):
    """Hindsight bottom evaluation only, can be right censored."""
    start=halving+pd.Timedelta(days=BUY_EARLIEST_DAY)
    if terminal<start:
        return None
    observed=price.loc[start:terminal]
    if observed.empty:return None
    day=observed.idxmin()
    return {
        "date":str(day.date()),"usd":round(float(observed.min()),2),
        "complete_day1150_observed":bool(
            terminal>=halving+pd.Timedelta(days=SCORE_DAYS)),
    }


def first_alert_timing(signals,price,halving,terminal,*,family):
    """First ACTUAL actionable alert in a predeclared age window.

    No filtering by or selection of the eventual cycle peak.
    In particular this is not the retrospectively nearest signal.
    """
    if family not in SIGNALS:raise ValueError("Unrecognised frozen signal")
    h=_utc(halving)
    end=_utc(terminal)
    first=h+pd.Timedelta(days=PEAK_WINDOW[0])
    last=min(end,h+pd.Timedelta(days=PEAK_WINDOW[1]))
    block=signals.loc[first:last,family]
    events=distinct_events(block)
    all_alerts=[str(x.date()) for x in events]
    if not events:
        return {"family":family,"first_alert_date":None,
                "first_alert_execution_close_usd":None,
                "alerts_in_window":0,"event_dates":[],
                "first_alert_selected_without_peak_knowledge":True}
    first_event=events[0]
    if first_event not in price.index:
        raise ValueError("Signal refers to missing date in price feed")
    return {
        "family":family,
        "first_alert_date":str(first_event.date()),
        "first_alert_execution_close_usd":round(float(price.loc[first_event]),2),
        "alerts_in_window":len(events),
        "event_dates":all_alerts,
        "first_alert_selected_without_peak_knowledge":True,
    }


def original_calendar_events(price,halving,terminal):
    """Strict prior-observation original SELL and persistent 200WMA BUY.

    This is a price-only signal-timing replay, not a cash+BTC/tax wallet.
    SELL sizes are fractions of the original BTC; BUY sizes fractions of a
    hypothetical fixed after-tax proceeds budget. Price-only VWAP is NOT
    AUD FX-adjusted actual BTC execution.
    """
    h=_utc(halving)
    end=_utc(terminal)
    if not (isinstance(price,pd.Series)
            and isinstance(price.index,pd.DatetimeIndex)
            and price.index.tz is not None
            and price.index.is_unique and price.index.is_monotonic_increasing):
        raise ValueError("Observed BTC price history must be uniquely UTC dated")
    if end not in price.index or h not in price.index:
        raise ValueError("Missing initial or terminal observed BTC close")
    span=pd.date_range(h,end,freq="D",tz="UTC")
    if not span.isin(price.index).all():
        raise ValueError("Missing historical daily BTC closes")
    sells=[]
    sold=0.
    for offset in exit_review_days():
        if offset>min(REVIEW_DAY,(end-h).days):
            continue
        day=h+pd.Timedelta(days=offset)
        step=staged_exit_decision(
            price.loc[:day],h,day=offset,sold_original_fraction=sold)
        qty=float(step["fraction_original"])
        sold+=qty
        if qty>1e-10:
            sells.append({
                "date":str(day.date()),"halving_day":offset,
                "original_btc_fraction":qty,
                "regime":step["regime"],
                "execution_close_usd":float(price.loc[day]),
            })
    buys=[]
    trigger=None
    first=h+pd.Timedelta(days=BUY_EARLIEST_DAY)
    remaining_budget=1.0
    for day in span:
        if day<first:continue
        if trigger is None and previously_completed_200wma_breach(
                price.loc[:day],day):
            trigger=day
        if trigger is not None and (day-trigger).days%7==0:
            step=recovery_buy_budget_fraction(
                price.loc[:day],day,style="adaptive_recovery")
            frac=min(remaining_budget,float(step[
                "fraction_of_initial_buyback_cash"]))
            remaining_budget-=frac
            if frac>1e-10:
                buys.append({
                    "date":str(day.date()),"halving_day":(day-h).days,
                    "original_aftertax_budget_fraction":frac,
                    "model_pct_of_original_budget":step[
                        "pct_of_initial_buyback_cash"],
                    "previous_close_to_prior_200wma":step[
                        "previous_close_to_200wma"],
                    "execution_close_usd":float(price.loc[day]),
                })
    return {
        "original_sell_events":sells,
        "original_sold_btc_fraction":round(sold,9),
        "first_buy_activation_date":str(trigger.date()) if trigger is not None else None,
        "buy_events":buys,
        "total_buy_budget_deployed_pct":round(100*(1-remaining_budget),3),
        "research_only":True,
        "denominators":"SELL fraction ORIGINAL BTC; BUY fraction original aftertax budget",
    }


def _weighted_prices(price,events,*,kind):
    if kind not in ("SELL","BUY"):raise ValueError("Unknown event kind")
    weight_key=("original_btc_fraction" if kind=="SELL"
                else "original_aftertax_budget_fraction")
    out={}
    for lag in EXECUTION_DELAYS_DAYS:
        valid=[e for e in events if _utc(e["date"])+pd.Timedelta(days=lag)
               in price.index]
        weight=sum(float(e[weight_key]) for e in valid)
        if not weight:
            out[str(lag)]={"usd_weighted_close":None,"event_count":0,
                           "portfolio_fraction_scored":0.}
            continue
        if kind=="SELL":
            vwap=sum(
                float(e[weight_key])*float(price.loc[
                    _utc(e["date"])+pd.Timedelta(days=lag)])
                for e in valid)/weight
        else:
            # Spending fixed USD fraction on execution day buys weights/price
            # BTC. Price-weighted harmonic mean, NOT an AUD FX equivalent.
            units=sum(float(e[weight_key])/float(price.loc[
                _utc(e["date"])+pd.Timedelta(days=lag)])
                for e in valid)
            vwap=weight/units
        out[str(lag)]={
            "usd_weighted_close":round(vwap,2),
            "event_count":len(valid),
            "portfolio_fraction_scored":round(weight,8),
        }
    return out


def audit_timing(history,*,cycles=("2017","2021","2025")):
    """Frozen original events and first warnings: no signal selection via peak."""
    data=history.copy().sort_index().loc[:CUTOFF]
    if not {"price_usd","mvrv_z","nupl","sopr"}.issubset(data.columns):
        raise ValueError("Archived price and existing risk indicator series needed")
    price=data["price_usd"].astype(float)
    signals=build_daily_signals(data)
    records=[]
    for label in cycles:
        if label not in PRIMARY:raise ValueError("Unrecognised inspected cycle")
        h=_utc(PRIMARY[label]["halving"])
        end=min(h+pd.Timedelta(days=SCORE_DAYS),price.index[-1])
        if end not in price.index or h not in price.index:
            raise ValueError("Historical start/end missing")
        peak=_window_peak(price,h,end)
        low=_window_low(price,h,end)
        baseline=original_calendar_events(price,h,end)
        sells=baseline["original_sell_events"]
        buys=baseline["buy_events"]
        sell_prices=_weighted_prices(price.loc[:end],sells,kind="SELL")
        buy_prices=_weighted_prices(price.loc[:end],buys,kind="BUY")
        peakday=_utc(peak["date"])
        lowday=_utc(low["date"]) if low else None
        warnings=[]
        for family in SIGNALS:
            alert=first_alert_timing(
                signals,price,h,end,family=family)
            alertday=(_utc(alert["first_alert_date"])
                      if alert["first_alert_date"] else None)
            alert["first_alert_days_before_observed_peak"]=(
                (peakday-alertday).days if alertday is not None else None)
            alert["first_alert_price_below_peak_pct"]=(
                round(100*(1-alert["first_alert_execution_close_usd"]/
                            peak["usd"]),2)
                if alertday is not None else None)
            warnings.append(alert)
        firstbuy=(_utc(baseline["first_buy_activation_date"])
                  if baseline["first_buy_activation_date"] else None)
        records.append({
            "cycle":label,"halving_date":str(h.date()),"terminal":str(end.date()),
            "complete_historical_window":end==h+pd.Timedelta(days=SCORE_DAYS),
            "observed_peak_in_age350_800":peak,
            "observed_low_after_day744":low,
            "original_sold_btc_pct":round(100*baseline["original_sold_btc_fraction"],2),
            "original_sell_first_day":sells[0]["date"] if sells else None,
            "original_sell_last_day":sells[-1]["date"] if sells else None,
            "original_sell_fill_count":len(sells),
            "original_sell_pct_original_position_before_peak":round(
                100*sum(x["original_btc_fraction"] for x in sells
                        if _utc(x["date"])<peakday),2),
            "original_sell_pct_original_position_within_60d_peak":round(
                100*sum(x["original_btc_fraction"] for x in sells
                        if abs((_utc(x["date"])-peakday).days)<=60),2),
            "original_sell_weighted_close_vs_peak_pct":(
                round(100*sell_prices["0"]["usd_weighted_close"]/peak["usd"],2)
                if sell_prices["0"]["usd_weighted_close"] is not None else None),
            "original_buy_activation_date":baseline["first_buy_activation_date"],
            "first_buy_days_relative_to_future_low":(
                (firstbuy-lowday).days if firstbuy is not None and lowday is not None
                else None),
            "original_buy_fill_count":len(buys),
            "original_buy_budget_deployed_pct":baseline["total_buy_budget_deployed_pct"],
            "original_buy_vwap_vs_future_low_pct":(
                round(100*(buy_prices["0"]["usd_weighted_close"]/low["usd"]-1),2)
                if low and buy_prices["0"]["usd_weighted_close"] is not None else None),
            "sell_execution_close_delay_days_sensitivity":sell_prices,
            "buy_execution_close_delay_days_sensitivity":buy_prices,
            "first_warning_by_existing_indicator":warnings,
            "dated_original_events":baseline,
        })
    return {
        "purpose":"Measure first actionable indicator warnings and frozen original 200WMA/day500 timing, NOT select retrospectively nearest alerts",
        "scoring_peak_window_days_after_halving":list(PEAK_WINDOW),
        "sell_review_days_after_halving":[d for d in exit_review_days() if d<=REVIEW_DAY],
        "buy_activation_no_earlier_than_day":BUY_EARLIEST_DAY,
        "execution_calendar_delay_days":list(EXECUTION_DELAYS_DAYS),
        "historical_price_cutoff":str(CUTOFF.date()),
        "research_only":True,
        "live_signal_replacement":False,
        "cycles":records,
        "limitations":[
            "No retrospective selection of nearest peak alert: first indicator event after day350 is counted even when very early/false.",
            "Top peak day350..800 and future low day744..1150 are HINDSIGHT SCORE LABELS only, not signal inputs.",
            "Onchain histories saved in October 2026 may be retrospectively revised; prefix invariance does not certify historical live data vintages.",
            "SELL price VWAP weights original BTC fractions; BUY USD VWAP weights fractions of hypothetical original aftertax budget. Neither is AUD/SMSF aftertax performance.",
            "Same BTC daily close and lagged prices as original simulations; ASX ETF quotes, market hours, slippage, brokerage/tax, USD/AUD and spread are NOT represented.",
            "Timing stress delays the PRICE of the SAME frozen original signal event by 1/3/7 calendar days; does not rebalance tax lots or reoptimise signal conditions.",
            "All data/historical 2017/2021 thresholds are in sample; 2025/26 BUY to day1150 is right censored.",
            "Actual holdings acquired in 2026 cannot be retrospectively sold in September 2025.",
            "Existing Streamlit simplified allocations, Production V5.8.2/Research V5.9, Google Sheets and ntfy remain unchanged.",
        ],
    }


def main():
    args=argparse.ArgumentParser()
    args.add_argument("--output",type=Path)
    opts=args.parse_args()
    result=audit_timing(read_exported_history())
    for item in result["cycles"]:
        print(json.dumps({
            "cycle":item["cycle"],"complete":item["complete_historical_window"],
            "peak":item["observed_peak_in_age350_800"],
            "original_sell_vwap_vs_peak_pct":item["original_sell_weighted_close_vs_peak_pct"],
            "pct_original_sold_before_peak":item["original_sell_pct_original_position_before_peak"],
            "pct_original_sold_near_peak":item["original_sell_pct_original_position_within_60d_peak"],
            "pct_original_sold_in_historical_window":item["original_sold_btc_pct"],
            "original_buy_activation":item["original_buy_activation_date"],
            "days_buy_trigger_vs_low":item["first_buy_days_relative_to_future_low"],
            "buy_vwap_above_low_pct":item["original_buy_vwap_vs_future_low_pct"],
            "first_indicators":{
                w["family"]:w["first_alert_date"]
                for w in item["first_warning_by_existing_indicator"]},
            "lagged_sell_vwap_usd":{
                k:v["usd_weighted_close"] for k,v in item[
                    "sell_execution_close_delay_days_sensitivity"].items()},
        },sort_keys=True))
    if opts.output:
        opts.output.parent.mkdir(parents=True,exist_ok=True)
        opts.output.write_text(json.dumps(result,indent=2))
        print("Full causal indicator timing event audit:",opts.output)


if __name__=="__main__":
    main()
