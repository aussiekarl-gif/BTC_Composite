"""RESEARCH ONLY: exact live Cycle SELL market conditions vs original-BTC exits.

The Streamlit/ntfy shared SELL decision uses fractions of CURRENT REMAINING
BTC, conditional 500/525/532/539/546/553/560 calendar reviews and
experimentally repeats 5% sales weekly after day560 if a strict prior-day
90d/50DMA rollover condition remains true. The historical dynamic staged
research instead sells fractions of ORIGINAL BTC in a different calendar
and regime engine. They cannot share performance claims without parity.

Hypothetical matched accounts begin with AUD500k purchased in direct BTC
ON HALVING DATE for comparable LONG-HELD inventory, not the user's actual
IBIT position bought in 2026. No user broker holdings are loaded. Same
strictly PRIOR BTC data determines decisions; date T BTC/USD closing price
and earlier AUDFX are *proxy* fills, not an ASX:IBIT order/quotation.
A$3 per fill, simplified FIFO SMSF accumulation CGT escrow on sells and
hypothetical terminal liquidation. 2017/21 complete 730/1150 horizons.
2025/26 right-censored at latest provider price date and must not be
called a finished cycle or a sale opportunity the user actually held.

Two live candidates here are NOT optimizations: scheduled-only and
actual live schedule + repeated experimental late-rollover. Compare
historical research staged ORIGINAL denomination 90% and 20% holdback,
plus never-sell buy-and-hold. No live UI or model edit.
"""
from __future__ import annotations

import argparse
import csv
import json
import math
from pathlib import Path

import numpy as np
import pandas as pd

from engines.research.cycle_trade_allocation import (
    calculate_allocation_signal, SELL_REVIEW_DAY_WEIGHTS,
    SCHEDULE_REMAINING_IF_ALL_TRIGGERED,
)
from engines.research.fresh_cash_200wma_matched_backtest import _historical_wma
from engines.research.day500_dynamic_dca_out import staged_day500_dynamic_exit
from engines.research.day500_aftertax_reinvestment import (
    INITIAL_AUD, PRIMARY, SCORE_DAYS, fetch_fx_for_cycle, fx_before,
)
from engines.research.smsf_self_financing_replay import AuditSmsfAccount
from engines.research.top_signal_horse_race import read_exported_history

CUTOFF=pd.Timestamp("2026-10-05",tz="UTC")
EVALUATION_DAYS=(730,SCORE_DAYS)
POLICIES=(
    "live_with_experimental_late_rollover",
    "live_scheduled_only",
    "research_original_btc_90pct",
    "research_original_btc_20pct_holdback",
    "buy_and_hold",
)
STAGED_LOOKUP={
    "research_original_btc_90pct":"maturity_90pct",
    "research_original_btc_20pct_holdback":"maturity_90pct_holdback20pct",
}
FEE_AUD=3.
COOLDOWN_DAYS=7


def day(value):
    t=pd.Timestamp(value)
    return (t.tz_localize("UTC") if t.tzinfo is None
            else t.tz_convert("UTC")).normalize()


def _good_prices(price,halving,end):
    if (not isinstance(price,pd.Series) or
        not isinstance(price.index,pd.DatetimeIndex)
        or price.index.tz is None
        or price.index.has_duplicates
        or not price.index.is_monotonic_increasing
        or halving not in price.index or end not in price.index
        or end<=halving+pd.Timedelta(days=560)):
        raise ValueError("Need valid UTC ordered BTC halving and terminal dates")
    required=pd.date_range(halving-pd.Timedelta(days=100),end,
                           tz="UTC",freq="D")
    if not required.isin(price.index).all():
        raise ValueError("Missing consecutive BTC daily closes")
    v=price.loc[required].to_numpy(dtype=float)
    if not np.isfinite(v).all() or (v<=0).any():
        raise ValueError("Nonpositive or missing BTC daily prices")


def sell_market_tape(price,halving,terminal):
    """Pure daily original shared Cycle WATCH; no fabricated portfolio."""
    h,end=day(halving),day(terminal)
    _good_prices(price,h,end)
    watches=[]
    for date in pd.date_range(h+pd.Timedelta(days=500),end,
                              freq="D",tz="UTC"):
        previous,wma=_historical_wma(price,date)
        if previous != float(price.loc[date-pd.Timedelta(days=1)]):
            raise AssertionError("Prior-price WMA misaligned")
        market={
            "price_history":price.loc[:date],
            "previous_close_usd":previous,
            "prior_200wma_usd":wma,
            "previous_close_below_200wma":previous<wma,
            "halving_day":(date-h).days,
        }
        signal=calculate_allocation_signal(market,
                                           buy_style="adaptive_recovery")
        if signal["signal"]=="SELL WATCH":
            reason=("late_rollover" if signal.get("experimental")
                    else "scheduled_strong_price")
            watches.append({
                "date":date,
                "halving_day":(date-h).days,
                "percent_current_remaining":float(signal["sell_pct_held"]),
                "kind":reason,
                "prior_price_to_200wma":signal["prior_price_over_200wma"],
                "prior_drawdown90_pct":signal["prior_90day_drawdown_pct"],
                "prior_50dma_declining":signal["prior_sma50_declining"],
            })
    return watches


def replay_sellers(price,fx,*,halving,terminal,capital_aud=INITIAL_AUD):
    h,end=day(halving),day(terminal)
    _good_prices(price,h,end)
    if not math.isfinite(float(capital_aud)) or capital_aud<=100:
        raise ValueError("Valid initial AUD capital required")
    first_px=float(price.loc[h])*fx_before(fx,h)
    accounts={p:AuditSmsfAccount(capital_aud,fee=FEE_AUD,tax=True)
              for p in POLICIES}
    original={}
    for key,wallet in accounts.items():
        if not wallet.buy(h,first_px,1.):
            raise AssertionError("Cannot build equal starting portfolio")
        original[key]=wallet.btc
    signal_rows=sell_market_tape(price,h,end)
    watch_dates={}
    for r in signal_rows:
        watch_dates.setdefault(r["date"],r)
    staged={}
    for policy,kind in STAGED_LOOKUP.items():
        window=staged_day500_dynamic_exit(
            price,h,policy=kind,review_day=(end-h).days)
        orders={}
        for item in window["sale_detail"]:
            stamp=day(item["date"])
            if stamp>end:continue
            if stamp in orders:
                raise AssertionError("Multiple historical stage sells same date")
            orders[stamp]=float(item["btc_sold"])
        staged[policy]=orders
    executed_by={k:[] for k in POLICIES}
    last_by={k:None for k in POLICIES}
    for date in pd.date_range(h+pd.Timedelta(days=500),end,
                              freq="D",tz="UTC"):
        aud=float(price.loc[date])*fx_before(fx,date)
        observed=watch_dates.get(date)
        for policy,account in accounts.items():
            gross_fraction=0.
            kind=None
            if policy in STAGED_LOOKUP:
                amount_original=staged[policy].get(date,0.)
                if amount_original>0:
                    gross_fraction=min(1.,amount_original*original[policy]/
                                       account.btc) if account.btc>1e-12 else 0.
                    kind="historical_original_btc_regime"
            elif policy!="buy_and_hold" and observed:
                # Existing active real ledger blocks a new transaction
                # within seven calendar days since the LAST actual sale.
                if (last_by[policy] is None or
                    (date-last_by[policy]).days>=COOLDOWN_DAYS):
                    if (policy=="live_with_experimental_late_rollover"
                        or observed["kind"]=="scheduled_strong_price"):
                        gross_fraction=observed["percent_current_remaining"]/100.
                        kind=observed["kind"]
            if gross_fraction>1e-12:
                before_btc=account.btc
                if account.sell(date,aud,gross_fraction):
                    if account.btc>before_btc+1e-8:
                        raise AssertionError("SELL created extra BTC")
                    last_by[policy]=date
                    order=account.orders[-1]
                    executed_by[policy].append({
                        "date":str(date.date()),"day":(date-h).days,
                        "sell_kind":kind,
                        "btc_sold":round(float(order["btc"]),9),
                        "fraction_original_pct":round(
                            100*float(order["btc"])/original[policy],5),
                        "fraction_remaining_before_pct":round(
                            100*float(order["btc"])/before_btc,5),
                        "sold_at_btc_usd_close":round(float(price.loc[date]),2),
                        "estimated_smsf_tax_aud":round(float(order["tax_aud"]),2),
                        "pretrade_prior_price_ratio_200wma":(
                            observed["prior_price_to_200wma"] if observed else None),
                    })
            account.mark(aud)
    # Same liquidation PRICE, same origin & FIFO policy; buy-and-hold
    # is the only account with no exits and no taxable realised gains yet.
    last=float(price.loc[end])*fx_before(fx,end)
    out={}
    for policy,account in accounts.items():
        out[policy]={
            "original_btc":round(original[policy],8),
            "btc_left":round(account.btc,8),
            "btc_sold_total":round(original[policy]-account.btc,8),
            "original_btc_sold_pct":round(
                100*(1-account.btc/original[policy]),4),
            "cash_aud_after_tax":round(account.cash,2),
            "net_marked_aud":round(account.cash+account.btc*last,2),
            "aftertax_hypothetical_liquidation_aud":round(
                account.liquidation_value(end,last),2),
            "realised_cgt_estimate_aud":round(account.total_tax,2),
            "fees_aud":round(account.total_fees,2),
            "actual_sell_count":len(executed_by[policy]),
            "max_drawdown_pct":round(account.drawdown*100,2),
            "sell_orders":executed_by[policy],
        }
    hold=out["buy_and_hold"]
    for name,record in out.items():
        record["marked_aud_vs_hold_pct"]=round(
            100*(record["net_marked_aud"]/hold["net_marked_aud"]-1),3)
        record["aftertax_aud_vs_hold_pct"]=round(
            100*(record["aftertax_hypothetical_liquidation_aud"]/
                 hold["aftertax_hypothetical_liquidation_aud"]-1),3)
    all_reviews=[r for r in signal_rows if r["kind"]=="scheduled_strong_price"]
    late=[r for r in signal_rows if r["kind"]=="late_rollover"]
    return {
        "halving_date":str(h.date()),"terminal_date":str(end.date()),
        "score_day":(end-h).days,
        "live_schedule_pct_of_current_remaining":True,
        "historic_staged_pct_of_original_btc":True,
        "if_all_seven_reviews_trigger_live_original_pct_sold":round(
            100*(1-SCHEDULE_REMAINING_IF_ALL_TRIGGERED),4),
        "live_conditional_scheduled_review_count":len(all_reviews),
        "live_late_rollover_watch_days":len(late),
        "market_signals_from_same_shared_allocation":True,
        "real_asx_ibit_quoted_fills":False,
        "accounts":out,
    }


def audit(history,*,fx_fetcher=fetch_fx_for_cycle):
    price=history["price_usd"].dropna().sort_index().loc[:CUTOFF]
    results=[]
    for cycle,entry in PRIMARY.items():
        h=day(entry["halving"])
        latest=min(h+pd.Timedelta(days=SCORE_DAYS),price.index[-1])
        fx=fx_fetcher(h,latest)
        for test_day in EVALUATION_DAYS:
            end=min(latest,h+pd.Timedelta(days=test_day))
            if end<=h+pd.Timedelta(days=560):continue
            a=replay_sellers(price,fx,halving=h,terminal=end)
            a.update({
                "cycle":cycle,
                "desired_score_day":test_day,
                "full_desired_horizon_observed":end==h+pd.Timedelta(days=test_day),
                "user_owned_historical_position":False,
                "historic_source_point_in_time_vintage_proven":False,
                "asx_ibit_existing_at_original_buy_date":False,
                "assumed_entry":"fresh hypothetical BTC bought on historic halving date",
            })
            results.append(a)
    return {
        "study":"Original Cycle market-level SELL parity with historical original-BTC staged exits",
        "source_data_cutoff":str(price.index[-1].date()),
        "research_only":True,
        "current_200wma_buy_rules_changed":False,
        "current_streamlit_and_ntfy_rules_changed":False,
        "no_retrospective_user_holdings":True,
        "historical":results,
        "limitations":[
            "Hypothetical AUD500k direct BTC purchase on past halving, not actual 2026 user or ASX:IBIT holdings; IBIT listed Nov2025.",
            "Live SELL WATCH is a market signal; real users still need verified broker units, whole ASX shares, calendar hours, tax parcels and a7d ledger.",
            "BTC/USD day T closing price is an optimistic execution proxy, not a tradeable brokerage ASX:IBIT quote or FX spot.",
            "Illustrative FIFO SMSF accumulation CGT tax escrow; pension-phase taxation and actual SMSF fiscal-year lot accounting differ.",
            "Current 2024-halving period scored only through archived Oct5 2026; no final cycle outcome.",
            "Research historic original-denominator staged exits are a different model, not an improvement proven out-of-sample.",
            "No assumption that ANY users owned BTC at day500 or sold in 2025. This is a replayed strategy thought experiment.",
        ],
    }


def main(argv=None):
    p=argparse.ArgumentParser()
    p.add_argument("--out",type=Path,
                   default=Path("artifacts/live_cycle_sell_parity"))
    o=p.parse_args(argv)
    result=audit(read_exported_history())
    o.out.mkdir(parents=True,exist_ok=True)
    (o.out/"audit.json").write_text(json.dumps(result,indent=2))
    rows=[]
    for r in result["historical"]:
        for name,acct in r["accounts"].items():
            rows.append({
                "cycle":r["cycle"],
                "desired_score_day":r["desired_score_day"],
                "observed_day":r["score_day"],
                "complete_horizon":r["full_desired_horizon_observed"],
                "seller":name,
                "sell_count":acct["actual_sell_count"],
                "btc_sold_pct_of_original":acct["original_btc_sold_pct"],
                "cash_aud_after_tax":acct["cash_aud_after_tax"],
                "btc_left":acct["btc_left"],
                "aftertax_aud":acct["aftertax_hypothetical_liquidation_aud"],
                "aftertax_aud_vs_hold_pct":acct["aftertax_aud_vs_hold_pct"],
                "marked_aud_vs_hold_pct":acct["marked_aud_vs_hold_pct"],
                "realised_tax_aud":acct["realised_cgt_estimate_aud"],
                "scheduled_market_review_watches":r[
                    "live_conditional_scheduled_review_count"],
                "late_market_watch_days":r["live_late_rollover_watch_days"],
            })
    with (o.out/"cohort_seller_summary.csv").open("w",newline="") as stream:
        writer=csv.DictWriter(stream,fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    for row in rows:
        print(json.dumps(row,sort_keys=True))
    print("RESEARCH ONLY. NO changes to Cycle Trading, Production, portfolio or ntfy.")


if __name__=="__main__":
    main()
