"""Causal self-financing Cycle SELL -> later BUY-back comparison, RESEARCH ONLY.

Objective: measure (1) ACTUAL shared Streamlit/ntfy SELL market policy with
5% potentially repeating late rollover; (2) actual scheduled-only diagnostic;
(3) historic original-BTC staged sellers (two variants); (4) hold.
All trades use SAME shared market BUY WATCH of 2.5% REMAINING after-tax AUD
cash, ONLY if strict previous BTC close < previous 200-week moving average,
>=7 calendar days after last filled trade. Sale policies vary; identical
buyback policy isolates consequences of exit timing/quantity. No invented
past personal BTC/IBIT holdings: all accounts purchase BTC at 2016,2020,
2024 HALVING dates with hypothetical A$500,000. ASX:IBIT did not trade
until Nov2025; pre-2025 fills are BTC/AUD closing-price research proxies,
NOT executable ASX prices.

Sell/BUY same-day conflicts: SELL has precedence for staged exits, and
shared current Cycle WATCH itself uses BUY precedence over SELL. Stage
planned sale is reduced by remaining ORIGINAL BTC not yet disposed.
Risk of future sale of repurchased parcels is a historical modelling
limitation explicitly flagged; no original position is fabricated in
the real 2026 portfolio.

All acquisitions reinvest only after-tax realised proceeds; no leverage,
external replenishment, negative cash, price lookahead or backdated 2025
personal orders. Illustrative A$3/trade FIFO SMSF accumulation CGT escrow
NOT actual fund tax calendar/pension tax phase. Mark and hypothetical
liquidation at SAME terminal AUD BTC proxy for all policies.
"""
from __future__ import annotations

import argparse
import csv
import json
import math
from pathlib import Path

import numpy as np
import pandas as pd

from engines.research.cycle_trade_allocation import calculate_allocation_signal
from engines.research.live_cycle_sell_parity_audit import (
    POLICIES, STAGED_LOOKUP, day, sell_market_tape, _good_prices,
)
from engines.research.day500_dynamic_dca_out import staged_day500_dynamic_exit
from engines.research.day500_aftertax_reinvestment import (
    INITIAL_AUD, PRIMARY, SCORE_DAYS, fetch_fx_for_cycle, fx_before,
)
from engines.research.fresh_cash_200wma_matched_backtest import _historical_wma
from engines.research.smsf_self_financing_replay import AuditSmsfAccount
from engines.research.staged_dca_delayed_bottom_stress import delayed_bottom_path
from engines.research.top_signal_horse_race import read_exported_history

CUTOFF=pd.Timestamp("2026-10-05",tz="UTC")
FULL_DAYS=SCORE_DAYS
INITIAL_CAPITAL=INITIAL_AUD
MIN_AUD_BUY=100.
BUY_PCT_OF_REMAINING=.025
MIN_TRADE_GAP_DAYS=7
BUY_STYLES=("live_2p5_remaining_cash_strict_200wma",)
STRESS_START_DAY=900
STRESS_TROUGH_DAY=1060
BULL_PREFIX_DAY=600
BULL_TERMINAL_MULTIPLIERS=(2.,4.)
DEEP_DECLINES=(.50,.70)


def rising_bull_path(prices,halving,*,prefix_day=BULL_PREFIX_DAY,
                     terminal_day=FULL_DAYS,ending_multiple=2.):
    """Counterfactual continuing bull AFTER day560; freeze dated prefix."""
    h=day(halving)
    if not (560<prefix_day<terminal_day and
            math.isfinite(float(ending_multiple)) and ending_multiple>1):
        raise ValueError("Invalid continuation bull assumptions")
    start=h+pd.Timedelta(days=prefix_day)
    terminal=h+pd.Timedelta(days=terminal_day)
    expected=pd.date_range(start,terminal,freq="D",tz="UTC")
    if not expected.isin(prices.index).all():
        raise ValueError("Missing historical prefix and bull terminal")
    new=prices.loc[:terminal].copy()
    reference=float(new.loc[start])
    if not math.isfinite(reference) or reference<=0:
        raise ValueError("Invalid bull anchor price")
    for t in expected[1:]:
        f=(t-start).days/(terminal-start).days
        new.loc[t]=reference*ending_multiple**f
    if not (new.loc[:start]==prices.loc[:start]).all():
        raise AssertionError("Future rising path changed known past")
    return new


def _date_market_signals(prices,halving,terminal):
    """Share exact market SELL decision with Streamlit, not staged proxy."""
    h,end=day(halving),day(terminal)
    observed={}
    for t in pd.date_range(h+pd.Timedelta(days=500),end,
                           tz="UTC",freq="D"):
        prev,wma=_historical_wma(prices,t)
        if not math.isclose(prev,float(prices.loc[t-pd.Timedelta(days=1)]),
                            rel_tol=1e-12):
            raise AssertionError("Strictly prior price state mismatch")
        m={
            "price_history":prices.loc[:t],
            "previous_close_usd":prev,
            "prior_200wma_usd":wma,
            "previous_close_below_200wma":prev<wma,
            "halving_day":(t-h).days,
        }
        result=calculate_allocation_signal(m,buy_style="adaptive_recovery")
        if result["signal"]=="BUY WATCH":
            if result["buy_pct_cash"]!=BUY_PCT_OF_REMAINING*100:
                raise AssertionError("Live shared BUY sizing has changed")
        observed[t]=result
    return observed


def simulate_full_roundtrip(prices,fx,*,halving,terminal,
                            starting_cash=INITIAL_CAPITAL,
                            weekday_only=False):
    """One causal portfolio ledger per seller, SAME exact live BUY algorithm.

    weekday_only is an optimistic Mon-Fri BTC/AUD quote proxy, NOT an
    official ASX holiday schedule; no fabricated ETF prices. Neither the
    current shared WATCH nor stage exits can execute on a weekend in this
    sensitivity scenario; no carry of missed orders is silently assumed.
    """
    h,end=day(halving),day(terminal)
    _good_prices(prices,h,end)
    if (not math.isfinite(float(starting_cash)) or starting_cash<=100
            or type(weekday_only) is not bool):
        raise ValueError("Invalid cash amount or weekday execution flag")
    signals=_date_market_signals(prices,h,end)
    stage={}
    for policy,variant in STAGED_LOOKUP.items():
        staged=staged_day500_dynamic_exit(
            prices,h,policy=variant,review_day=(end-h).days)
        perdate={}
        for trade in staged["sale_detail"]:
            when=day(trade["date"])
            if when in perdate:raise ValueError("Duplicated staged exit day")
            perdate[when]=float(trade["btc_sold"])
        stage[policy]=perdate

    # A hypothetical BTC holding is purchased on the historic halving.
    # No real user holding, retroactive transaction or 2025 sale.
    entry=float(prices.loc[h])*fx_before(fx,h)
    accounts={p:AuditSmsfAccount(
        starting_cash,fee=3.,tax=True) for p in POLICIES}
    initial_btc={}
    for p,a in accounts.items():
        if not a.buy(h,entry,1.):
            raise AssertionError("Unable to create initial hypothetical BTC")
        initial_btc[p]=a.btc
    filled={p:[] for p in POLICIES}
    last_fill={p:None for p in POLICIES}
    staged_original_sold={p:0. for p in STAGED_LOOKUP}

    for t,signal in signals.items():
        aud=float(prices.loc[t])*fx_before(fx,t)
        can_trade=(not weekday_only or t.weekday()<5)
        for policy,a in accounts.items():
            if not can_trade:
                a.mark(aud)
                continue
            due=(last_fill[policy] is None or
                 (t-last_fill[policy]).days>=MIN_TRADE_GAP_DAYS)
            desired_sale_pct=0.
            reason=""
            original_qty_target=0.
            if due:
                if policy in STAGED_LOOKUP:
                    nominal=stage[policy].get(t,0.)*initial_btc[policy]
                    available_original=max(
                        0.,initial_btc[policy]-staged_original_sold[policy])
                    original_qty_target=min(nominal,available_original,a.btc)
                    if original_qty_target*aud>100:
                        desired_sale_pct=original_qty_target/a.btc
                        reason="original_btc_staged_exit"
                elif (policy!="buy_and_hold" and signal["signal"]=="SELL WATCH"
                      and (policy=="live_with_experimental_late_rollover"
                           or not signal.get("experimental"))):
                    desired_sale_pct=signal["sell_pct_held"]/100.
                    reason=("shared_experimental_late_rollover" if signal.get(
                        "experimental") else "shared_scheduled_sell")
            acted=False
            if desired_sale_pct>0:
                before=a.btc
                if a.sell(t,aud,desired_sale_pct):
                    order=a.orders[-1]
                    sold=before-a.btc
                    if policy in STAGED_LOOKUP:
                        staged_original_sold[policy]+=sold
                        if staged_original_sold[policy]>initial_btc[policy]+1e-8:
                            raise AssertionError("Sold more than original BTC")
                    filled[policy].append({
                        "date":str(t.date()),"side":"SELL",
                        "signal_origin":reason,
                        "btc":round(float(order["btc"]),9),
                        "gross_aud":round(float(order["gross_aud"]),2),
                        "estimated_cgt_aud":round(float(order["tax_aud"]),2),
                        "original_btc_sold_so_far_pct":round(
                            100*staged_original_sold[policy]/initial_btc[policy],4
                        ) if policy in STAGED_LOOKUP else None,
                    })
                    last_fill[policy]=t
                    acted=True
            # The ACTUAL live market model always prefers BUY when
            # prior close is below 200WMA. Do not use a false bought
            # earlier/2025 peak cash pool: only realised, aftertax cash
            # from this simulated portfolio can be spent.
            if (not acted and due and policy!="buy_and_hold"
                    and signal["signal"]=="BUY WATCH"):
                gross=a.cash*BUY_PCT_OF_REMAINING
                if gross>MIN_AUD_BUY:
                    if a.buy(t,aud,BUY_PCT_OF_REMAINING):
                        order=a.orders[-1]
                        filled[policy].append({
                            "date":str(t.date()),"side":"BUY",
                            "signal_origin":"shared_live_200wma_watch",
                            "btc":round(float(order["btc"]),9),
                            "gross_aud":round(float(order["gross_aud"]),2),
                            "estimated_cgt_aud":0.,
                            "original_btc_sold_so_far_pct":None,
                        })
                        last_fill[policy]=t
            a.mark(aud)
    mark=float(prices.loc[end])*fx_before(fx,end)
    result={}
    for policy,a in accounts.items():
        rows=filled[policy]
        for before,after in zip(rows,rows[1:]):
            if (day(after["date"])-day(before["date"])).days<7:
                raise AssertionError("Portfolio ledger cooldown violated")
        if weekday_only and any(day(x["date"]).weekday()>=5 for x in rows):
            raise AssertionError("Weekend ASX proxy fill")
        buybacks=[x for x in rows if x["side"]=="BUY"]
        sells=[x for x in rows if x["side"]=="SELL"]
        result[policy]={
            "original_btc":round(initial_btc[policy],8),
            "btc_left_after_buybacks":round(a.btc,8),
            "cash_remaining_aud":round(a.cash,2),
            "btc_equivalent_mark_including_cash":round(
                a.btc+a.cash/mark,8),
            "net_aud_mark":round(a.cash+a.btc*mark,2),
            "hypothetical_aftertax_liquidation_aud":round(
                a.liquidation_value(end,mark),2),
            "realised_smsf_cgt_aud":round(a.total_tax,2),
            "total_brokerage_aud":round(a.total_fees,2),
            "original_btc_sold_pct":(
                round(100*staged_original_sold[policy]/initial_btc[policy],3)
                if policy in STAGED_LOOKUP else None),
            "actual_sell_orders":len(sells),
            "actual_buyback_orders":len(buybacks),
            "first_buyback_date":buybacks[0]["date"] if buybacks else None,
            "last_buyback_date":buybacks[-1]["date"] if buybacks else None,
            "max_account_drawdown_pct":round(100*a.drawdown,2),
            "dated_orders":rows,
        }
    hold=result["buy_and_hold"]
    for policy,row in result.items():
        row["btc_equivalent_vs_hold_pct"]=round(100*(
            row["btc_equivalent_mark_including_cash"]/
            hold["btc_equivalent_mark_including_cash"]-1),3)
        row["hypothetical_aftertax_aud_vs_hold_pct"]=round(100*(
            row["hypothetical_aftertax_liquidation_aud"]/
            hold["hypothetical_aftertax_liquidation_aud"]-1),3)
    return {
        "halving":str(h.date()),"terminal":str(end.date()),
        "cycle_day":(end-h).days,
        "weekday_only_BTC_AUD_proxy":weekday_only,
        "strict_200week_prior_market_signal":True,
        "shared_live_buy_fraction_of_remaining_cash_pct":2.5,
        "seven_day_LEDGER_cooldown":True,
        "no_external_cash_for_reinvestment":True,
        "no_actual_IBIT_orders":True,
        "accounts":result,
    }


def audit(history,*,fx_fetcher=fetch_fx_for_cycle):
    price=history["price_usd"].dropna().sort_index().loc[:CUTOFF]
    real=[]
    artificial=[]
    for label,item in PRIMARY.items():
        h=day(item["halving"])
        end=min(h+pd.Timedelta(days=FULL_DAYS),price.index[-1])
        fx=fx_fetcher(h,end)
        for weekdays in (False,True):
            r=simulate_full_roundtrip(price,fx,halving=h,
                   terminal=end,weekday_only=weekdays)
            r.update({"cycle":label,"case":"historic_completed_or_censored",
                "observed_complete":end==h+pd.Timedelta(days=FULL_DAYS),
                "source_vintage_verified":False})
            real.append(r)
        if label not in ("2017","2021"):continue
        if end!=h+pd.Timedelta(days=FULL_DAYS):
            raise ValueError("Stress scenarios require completed cycle")
        for multiple in BULL_TERMINAL_MULTIPLIERS:
            new=rising_bull_path(price,h,ending_multiple=multiple)
            r=simulate_full_roundtrip(new,fx,halving=h,terminal=end,
                                      weekday_only=True)
            r.update({"cycle":label,"case":"uninterrupted_extra_bull_rally",
                      "bull_multiple_after_day600":multiple,
                      "observed_complete":False})
            artificial.append(r)
        for drop in DEEP_DECLINES:
            stressed=delayed_bottom_path(
                price,h,shock_start_day=STRESS_START_DAY,
                loss_fraction=drop,terminal_price_fraction=.55,
                trough_day=STRESS_TROUGH_DAY)
            r=simulate_full_roundtrip(stressed,fx,halving=h,terminal=end,
                                      weekday_only=True)
            r.update({"cycle":label,"case":"synthetic_extended_bear",
                      "artificial_extra_decline_pct":100*drop,
                      "observed_complete":False})
            artificial.append(r)
    return {
        "research_only":True,
        "live_model_unchanged":True,
        "start_account_is_hypothetical_halving_date_BTC":True,
        "trade_prices_are_BTC_daily_closes_not_ASX_IBIT_executable":True,
        "real_historic_complete_2017_2021_but_2025_censored":True,
        "same_2p5pct_of_remaining_CASH_strict_200WMA_buyback":True,
        "no_carry_weekend_signal_in_live_parity":True,
        "no_sale_2025_user_portfolio_backdated":True,
        "source_price_cutoff":str(price.index[-1].date()),
        "historical":real,"counterfactuals":artificial,
        "warnings":[
            "The original staged sellers are a separate rule; buybacks here use the unchanged *live* 2.5%-remaining-cash policy for all policies to isolate SELL effect.",
            "This is NOT the historical staged 24-week forced-deployment buyback; never credit those backtest results to these matched live buybacks.",
            "The original-btc staged denominator limits original fractions sold; late rebuys plus later staged sells can tax differently from the stand-alone SELL model.",
            "Even with weekend-only execution limited to Mon-Fri, ASX holidays, actual market hours, bid/ask and issuer NAV premium/discount are unverified.",
            "Starting cash is allocated completely to BTC on EACH past halving date, a counterfactual: the user did not own these portfolios and IBIT did not exist then.",
            "SMSF tax immediately set aside on each sale is illustrative (10% long/15% short), not exact fiscal year/pension phase compliance.",
            "Two completed BTC cycles are NOT independent evidence for a future unseen market; 2025/26 is right-censored.",
            "Uninterrupted extra rallies and further 50/70% declines are hypothetical stress paths, not probabilities.",
        ],
    }


def main(argv=None):
    p=argparse.ArgumentParser()
    p.add_argument("--out",type=Path,
                   default=Path("artifacts/live_cycle_roundtrip"))
    args=p.parse_args(argv)
    result=audit(read_exported_history())
    args.out.mkdir(parents=True,exist_ok=True)
    (args.out/"full_ledger.json").write_text(json.dumps(result,indent=2))
    for fname,key in (("real_cash_reinvestment.csv","historical"),
                      ("counterfactuals.csv","counterfactuals")):
        rows=[]
        for scenario in result[key]:
            for policy,account in scenario["accounts"].items():
                rows.append({
                    "cycle":scenario["cycle"],
                    "case":scenario["case"],
                    "asof_cycle_day":scenario["cycle_day"],
                    "weekday_only_proxy":scenario["weekday_only_BTC_AUD_proxy"],
                    "observed_complete":scenario["observed_complete"],
                    "policy":policy,
                    "sell_orders":account["actual_sell_orders"],
                    "buyback_orders":account["actual_buyback_orders"],
                    "first_buyback_date":account["first_buyback_date"],
                    "cash_left_aud":account["cash_remaining_aud"],
                    "net_btc_units":account["btc_left_after_buybacks"],
                    "cash_in_btc_equivalent":account["btc_equivalent_mark_including_cash"],
                    "btc_equivalent_vs_hold_pct":account["btc_equivalent_vs_hold_pct"],
                    "aftertax_aud_vs_hold_pct":account["hypothetical_aftertax_aud_vs_hold_pct"],
                    "account_liquidation_aftertax_aud":account[
                        "hypothetical_aftertax_liquidation_aud"],
                    "estimated_CGT_aud":account["realised_smsf_cgt_aud"],
                })
        with (args.out/fname).open("w",newline="") as fh:
            writer=csv.DictWriter(fh,fieldnames=list(rows[0]))
            writer.writeheader()
            writer.writerows(rows)
        for r in rows:print(json.dumps(r,sort_keys=True))
    print("RESEARCH ONLY: no live BUY/SELL changes, portfolio edits or ntfy")


if __name__=="__main__":
    main()
