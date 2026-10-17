"""Research-only matched AUD SMSF after-tax BTC sell/rebuy experiment.

The current 2.5%-of-remaining-cash 200WMA BUY rule is compared directly with
the new staged-value BUY challenger, holding the SELL policy fixed.

* Same hypothetical A$500,000 BTC purchase on a historical halving for both
  arms and same original-BTC-denominated sale dates/quantities.
* Sale proceeds recycle ONLY after an AUD 3 fill fee and simplified immediate
  10%/15% SMSF FIFO CGT escrow from the established research account.
* No additional cash, private portfolio access, ETF orders or live signals.
* Signals use strictly completed previous BTC closes and previous-date FX.
* All reported hindsight troughs/tops are metrics, NEVER signal inputs.
* Historical source vintage, fill realism, CGT timing, pension status and
  2025/26 right-censoring remain important caveats.
"""
from __future__ import annotations

import argparse
import json
import math
from pathlib import Path

import pandas as pd

from engines.research.cycle_trade_allocation import calculate_allocation_signal
from engines.research.cycle_trading_dashboard_model import build_dashboard_market
from engines.research.day500_aftertax_reinvestment import (
    INITIAL_AUD, SCORE_DAYS, PRIMARY, fetch_fx_for_cycle, fx_before, sell_orders,
)
from engines.research.smsf_self_financing_replay import AuditSmsfAccount
from engines.research.staged_value_dca_challenger import candidate_buy_signal
from engines.research.top_signal_horse_race import read_exported_history

BUYERS=("current_2p5pct","staged_value_recovery")
SELLERS=("fixed_525_to_560","dynamic_90pct_holdback20pct")
BUY_START_DAY=574
CASH_RESERVE_PCT_OF_INITIAL=2.0
FEE_AUD=3.0


def replay_roundtrip(price, fx, halving, terminal, *, seller, buyer,
                     initial_aud=INITIAL_AUD, buy_start_day=BUY_START_DAY,
                     execution_slippage_bps=0):
    """Independent self-financing account, no look-ahead trade decisions."""
    if seller not in SELLERS or buyer not in BUYERS:
        raise ValueError("Unrecognised sell/buy research policy")
    halving=pd.Timestamp(halving)
    terminal=pd.Timestamp(terminal)
    if halving.tzinfo is None:halving=halving.tz_localize("UTC")
    else:halving=halving.tz_convert("UTC")
    if terminal.tzinfo is None:terminal=terminal.tz_localize("UTC")
    else:terminal=terminal.tz_convert("UTC")
    if not isinstance(price,pd.Series) or not isinstance(price.index,pd.DatetimeIndex):
        raise ValueError("Require dated BTC/USD price series")
    if price.index.tz is None or price.index.has_duplicates or not price.index.is_monotonic_increasing:
        raise ValueError("Require strictly dated, ordered, unique BTC/USD prices")
    if terminal<halving+pd.Timedelta(days=560) or terminal>price.index.max():
        raise ValueError("Terminal outside observed post-distribution window")
    if buy_start_day<=560 or buy_start_day>=SCORE_DAYS:
        raise ValueError("Invalid predeclared post-distribution entry day")
    if not math.isfinite(float(initial_aud)) or initial_aud<=FEE_AUD:
        raise ValueError("Positive AUD capital must exceed brokerage")
    if (not math.isfinite(float(execution_slippage_bps))
            or not 0<=float(execution_slippage_bps)<=500):
        raise ValueError("Require bounded adverse execution slippage 0..500bp")
    slip=float(execution_slippage_bps)/10000.0
    price=price.loc[:terminal].copy()
    all_dates=pd.date_range(halving,terminal,freq="D",tz="UTC")
    if not all_dates.isin(price.index).all():
        raise ValueError("BTC/USD missing a required daily observation")

    entered_price_aud=float(price.loc[halving])*fx_before(fx,halving)*(1+slip)
    account=AuditSmsfAccount(float(initial_aud),fee=FEE_AUD,tax=True)
    held=AuditSmsfAccount(float(initial_aud),fee=FEE_AUD,tax=True)
    if not account.buy(halving,entered_price_aud,1.) or not held.buy(halving,entered_price_aud,1.):
        raise AssertionError("Same-date initial BTC purchases failed")
    original_btc=account.btc
    dates=sell_orders(price,halving,seller)
    dates=[x for x in dates if x["day"]<=terminal and x["fraction"]>0]
    if sum(float(x["fraction"]) for x in dates)>1.0+1e-7:
        raise ValueError("SELL plan exceeds original BTC")
    if any(x["day"]<halving+pd.Timedelta(days=500) for x in dates):
        raise ValueError("Historical SELL before day500")
    sell_map={}
    for event in dates:
        date=event["day"]
        if date in sell_map:
            raise ValueError("Multiple SELLs same calendar date")
        sell_map[date]=float(event["fraction"])
    buy_dates=set(pd.date_range(
        halving+pd.Timedelta(days=buy_start_day),terminal,freq="7D",tz="UTC"))
    buys=[]
    sales=[]
    reserve=float(initial_aud)*CASH_RESERVE_PCT_OF_INITIAL/100.0
    for day in all_dates[1:]:
        btc_usd=float(price.loc[day])
        if not math.isfinite(btc_usd) or btc_usd<=0:
            raise ValueError("Invalid execution close")
        # Obtain strictly prior USD/AUD once for every executed trade and
        # portfolio mark. For weekend marks, carry forward only dated FX
        # known before that day; fail if stale >7 calendar days.
        aud_per_usd=fx_before(fx,day)
        px_aud=btc_usd*aud_per_usd
        if day in sell_map:
            qty_target=original_btc*sell_map[day]
            existing=account.btc
            if qty_target>existing+1e-8:
                raise ArithmeticError("SELL would consume BTC not held")
            if qty_target>1e-10:
                before=len(account.orders)
                if account.sell(day,px_aud*(1-slip),
                                min(1.0,qty_target/existing)):
                    row=account.orders[-1]
                    if len(account.orders)!=before+1:
                        raise AssertionError("Sale ledger failed")
                    sales.append({
                        "date":str(day.date()),"btc":row["btc"],
                        "gross_aud":row["gross_aud"],"tax_aud":row["tax_aud"],
                        "usd_price":btc_usd*(1-slip),"aud_per_usd":aud_per_usd,
                        "fraction_original":sell_map[day],
                    })
        elif day in buy_dates and account.cash>reserve+100:
            # Signal uses the preceding day's close and the strictly
            # previous 200 weekly samples; the current day's execution
            # price cannot affect the allocation.
            market=build_dashboard_market(price.loc[:day],pd.DataFrame(),
                                          asof=str(day.date()))
            market["halving_day"]=(day-halving).days
            market["halving_date"]=str(halving.date())
            fraction=(calculate_allocation_signal(market)["buy_pct_cash"]
                      if buyer=="current_2p5pct" else
                      candidate_buy_signal(market)["buy_pct_cash"])
            if fraction>0:
                gross=min(account.cash*fraction/100.0,account.cash-reserve)
                if gross>100.0 and gross>FEE_AUD*2:
                    before=len(account.orders)
                    if account.buy(day,px_aud*(1+slip),gross/account.cash):
                        row=account.orders[-1]
                        if len(account.orders)!=before+1:
                            raise AssertionError("Buy ledger failed")
                        buys.append({
                            "date":str(day.date()),"btc":row["btc"],
                            "gross_aud":row["gross_aud"],"usd_price":btc_usd*(1+slip),
                            "aud_per_usd":aud_per_usd,
                            "pct_remaining_cash":fraction,
                        })
        account.mark(px_aud)
        held.mark(px_aud)

    last_usd=float(price.loc[terminal])
    last_aud=last_usd*fx_before(fx,terminal)
    top_window=price.loc[halving+pd.Timedelta(days=500):
                         min(terminal,halving+pd.Timedelta(days=730))]
    low_window=price.loc[halving+pd.Timedelta(days=buy_start_day):terminal]
    if top_window.empty or low_window.empty:
        raise ValueError("Invalid hindsight scoring window")
    hindsight_top=float(top_window.max())
    hindsight_bottom=float(low_window.min())
    # A full gross USD buy VWAP is more conservative than fee-excluded VWAP.
    bought_qty=sum(t["btc"] for t in buys)
    sold_qty=sum(t["btc"] for t in sales)
    bought_usd=sum(t["gross_aud"]/t["aud_per_usd"] for t in buys)
    sold_usd=sum(t["gross_aud"]/t["aud_per_usd"] for t in sales)
    buy_vwap=bought_usd/bought_qty if bought_qty>0 else None
    sell_vwap=sold_usd/sold_qty if sold_qty>0 else None
    net_proceeds=sum(t["gross_aud"]-FEE_AUD-t["tax_aud"] for t in sales)
    reinvested_aud=sum(t["gross_aud"] for t in buys)
    complete=terminal>=halving+pd.Timedelta(days=SCORE_DAYS)
    deployment_pct=100*reinvested_aud/net_proceeds if net_proceeds>0 else 0.
    target=lambda pct: (bool(buy_vwap is not None
                         and deployment_pct>=50.0
                         and buy_vwap<=hindsight_bottom*(1+pct/100.0))
                        if complete else None)

    account_btc=account.btc
    terminal_eq=account.cash+account_btc*last_aud
    held_eq=held.cash+held.btc*last_aud
    account_after_cgt=account.liquidation_value(terminal,last_aud)
    hold_after_cgt=held.liquidation_value(terminal,last_aud)
    if account.cash<-1e-7 or account_btc<-1e-7:
        raise AssertionError("Self-financing account overspent")
    if reinvested_aud>net_proceeds+1e-5:
        raise AssertionError("Purchases exceeded net sell proceeds")
    if terminal_eq<=0 or held_eq<=0 or hold_after_cgt<=0:
        raise AssertionError("Bad marked values")

    return {
        "seller":seller,"buyer":buyer,
        "execution_slippage_bps":float(execution_slippage_bps),
        "start_date":str(halving.date()),"terminal":str(terminal.date()),
        "complete_window":bool(complete),
        "initial_aud":float(initial_aud),
        "original_btc":round(original_btc,8),
        "sell_fills":len(sales),"buy_fills":len(buys),
        "btc_sold":round(sold_qty,8),
        "btc_rebought":round(bought_qty,8),
        "btc_remaining":round(account_btc,8),
        "cash_remaining_aud":round(account.cash,2),
        "net_sell_cash_after_tax_aud":round(net_proceeds,2),
        "buyback_spent_aud":round(reinvested_aud,2),
        "net_sale_proceeds_reinvested_pct":round(deployment_pct,2),
        "aud_per_btc_last":round(last_aud,2),
        "sell_vwap_usd":round(sell_vwap,2) if sell_vwap is not None else None,
        "sell_error_below_observed_top_pct":(
            round(100*(1-sell_vwap/hindsight_top),2)
            if sell_vwap is not None else None),
        "historical_top_usd":round(hindsight_top,2),
        "buy_vwap_usd":round(buy_vwap,2) if buy_vwap is not None else None,
        "buy_error_above_observed_bottom_pct":(
            round(100*(buy_vwap/hindsight_bottom-1),2)
            if buy_vwap is not None else None),
        "historical_bottom_usd":round(hindsight_bottom,2),
        "meets_25pct_vwap_with_50pct_deployment":target(25),
        "meets_20pct_vwap_with_50pct_deployment":target(20),
        "account_marked_aud":round(terminal_eq,2),
        "hold_marked_aud":round(held_eq,2),
        "marked_value_vs_hold_pct":round(100*(terminal_eq/held_eq-1),2),
        "account_after_hypothetical_liquidation_cgt_aud":round(account_after_cgt,2),
        "hold_after_hypothetical_liquidation_cgt_aud":round(hold_after_cgt,2),
        "liquidated_aud_vs_hold_pct":round(
            100*(account_after_cgt/hold_after_cgt-1),2),
        "terminal_btc_equiv_including_cash":round(
            account_btc+account.cash/last_aud,8),
        "hold_btc":round(held.btc,8),
        "terminal_btc_equiv_vs_hold_pct":round(
            100*((account_btc+account.cash/last_aud)/held.btc-1),2),
        "smsf_tax_escrow_paid_aud":round(account.total_tax,2),
        "brokerage_aud":round(account.total_fees,2),
        "no_external_cash":True,
        "orders":account.orders,
        "sales":sales,"buybacks":buys,
    }


def evaluate_saved_cycles(history, *, fx_fetcher=fetch_fx_for_cycle):
    """Three actual archived cycles; only two have fully observed horizons."""
    price=history["price_usd"].dropna().sort_index()
    cutoff=pd.Timestamp("2026-10-05",tz="UTC")
    price=price.loc[:cutoff]
    out={}
    fx_fetcher_cache={}
    for label,details in PRIMARY.items():
        halving=pd.Timestamp(details["halving"],tz="UTC")
        terminal=min(halving+pd.Timedelta(days=SCORE_DAYS),price.index.max())
        fx=fx_fetcher(halving,terminal)
        fx_fetcher_cache[label]=fx
        comparisons={}
        for seller in SELLERS:
            variants={}
            for buyer in BUYERS:
                variants[buyer]=replay_roundtrip(
                    price,fx,halving,terminal,seller=seller,buyer=buyer)
            # We compare separate accounts with identical initial and SELL
            # instructions. Sale CASH amounts may differ if their prior
            # buybacks alter tax lots, especially in the dynamic tail.
            comparisons[seller]=variants
        out[label]=comparisons
    # Adverse 1% and 2% price friction at EVERY initial BUY / staged SELL /
    # repurchase; held comparator bears the same initial buy friction.
    # Only complete historic periods are interpreted as completed tests.
    slippage_sensitivity={}
    for bps in (100,200):
        matrix={}
        for label in ("2017","2021"):
            details=PRIMARY[label]
            halving=pd.Timestamp(details["halving"],tz="UTC")
            terminal=min(halving+pd.Timedelta(days=SCORE_DAYS),price.index.max())
            fx=fx_fetcher_cache[label]
            controls={}
            for buyer in BUYERS:
                rec=replay_roundtrip(price,fx,halving,terminal,
                    seller="fixed_525_to_560",buyer=buyer,
                    execution_slippage_bps=bps)
                controls[buyer]={
                    "complete_window":rec["complete_window"],
                    "liquidated_aud_vs_hold_pct":rec["liquidated_aud_vs_hold_pct"],
                    "terminal_btc_equiv_vs_hold_pct":rec["terminal_btc_equiv_vs_hold_pct"],
                    "buy_error_above_observed_bottom_pct":rec["buy_error_above_observed_bottom_pct"],
                    "buyback_spent_aud":rec["buyback_spent_aud"],
                }
            matrix[label]=controls
        slippage_sensitivity[str(bps)]=matrix
    return {
        "study":"Matched AUD SMSF self-financing staged sell and DCA rebuy",
        "currency":"AUD",
        "cutoff":"2026-10-05",
        "cohorts":out,
        "adverse_execution_slippage_sensitivity":slippage_sensitivity,
        "assumptions":[
            "Hypothetical A$500k fully invested at historical halving; not the real portfolio.",
            "Both arms use same original-BTC-denominated sell schedule; dynamic tail can overlap rebuy window.",
            "No outside capital; fees A$3/order; prior dated USD/AUD FX; FIFO immediate 10/15% CGT escrow.",
            "Adverse 100/200bp slippage stress uses 1/2% worse filled prices for all buys and sells. Held comparator has same initial buy friction.",
            "GST, ETF brokerage spreads, pension phase, complex tax-loss treatment, annual CGT timing not modeled.",
            "Hindsight top/bottom errors are scoring only; execution is optimistic daily close proxy.",
            "2025/26 is right-censored: future low/top and end outcome unknown.",
            "Already historically inspected cycles and thresholds; not a prospective holdout.",
            "No changes to live Streamlit, portfolio, Research 5.9, Production 5.8.2, or ntfy.",
        ],
    }


def main():
    p=argparse.ArgumentParser()
    p.add_argument("--output",type=Path)
    args=p.parse_args()
    results=evaluate_saved_cycles(read_exported_history())
    for cycle,groups in results["cohorts"].items():
        for seller,variants in groups.items():
            for buyer,rec in variants.items():
                keys=("complete_window","sell_fills","buy_fills",
                      "net_sale_proceeds_reinvested_pct","btc_remaining",
                      "terminal_btc_equiv_including_cash",
                      "buy_error_above_observed_bottom_pct",
                      "sell_error_below_observed_top_pct",
                      "liquidated_aud_vs_hold_pct","terminal_btc_equiv_vs_hold_pct")
                print(json.dumps({
                    "cycle":cycle,"seller":seller,"buyer":buyer,
                    **{k:rec[k] for k in keys}
                },sort_keys=True))
    for bps,cycles in results["adverse_execution_slippage_sensitivity"].items():
        for cycle,variants in cycles.items():
            for buyer,rec in variants.items():
                print(json.dumps({
                    "slippage_bps":int(bps),"cycle":cycle,"buyer":buyer,
                    **rec,
                },sort_keys=True))
    if args.output:
        args.output.parent.mkdir(parents=True,exist_ok=True)
        args.output.write_text(json.dumps(results,indent=2))
        print("Audit saved:",args.output)


if __name__=="__main__":
    main()
