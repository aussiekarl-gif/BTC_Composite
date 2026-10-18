"""Research ONLY: replay *actual* Cycle market BUY + 7-day ledger cooldown.

Previous research comparison (#126) compared a daily unthrottled 2.5%-
remaining-cash proxy to the historical weekly model. But Streamlit's
current BUY engine and manually recorded ledger now impose seven days
between any executed BUY/SELL. Daily proxy was NOT live-rule parity.

This model REPLAYS existing shared `calculate_allocation_signal` and
`cooldown_check` policy's date separation for a hypothetical FRESH AUD
cash-only account with NO legacy BTC or invented historical sale. It
compares the actual 2.5% remaining-cash *weekly eligible order* to two
predeclared candidate sizes 3.5% and 5%. Exact live market BUY percentage
is independently asserted at each BTC-eligible day; no live code changes.

ASX:IBIT cannot execute on weekends, tax-lot reality and ETF spread are
not represented; this replay is a BTC/USD next-close proxy (not a
backtest-proven live IBIT order). No 2026 user's private portfolio read.
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
from engines.research.day500_aftertax_reinvestment import (
    PRIMARY,SCORE_DAYS,fetch_fx_for_cycle,fx_before,
)
from engines.research.fresh_cash_200wma_matched_backtest import (
    BUDGET_AUD,FEE_AUD,START_DAYS,MIN_ORDER_AUD,_historical_wma,
)
from engines.research.smsf_self_financing_replay import AuditSmsfAccount
from engines.research.staged_dca_delayed_bottom_stress import delayed_bottom_path
from engines.research.top_signal_horse_race import read_exported_history

CUTOFF=pd.Timestamp("2026-10-05",tz="UTC")
TRADE_COOLDOWN_DAYS=7
BASELINE_FRACTION=.025
FROZEN_CHALLENGERS=(.035,.05)
ALL_FRACTIONS=(BASELINE_FRACTION,)+FROZEN_CHALLENGERS
SHOCK_COHORTS=(("2017",750,960),("2021",650,900))
SHOCK_DROPS=(.50,.70)
SHOCK_TERMINALS=(.55,1.05)
SHOCK_TROUGH_DAY=1060


def _utc(value):
    t=pd.Timestamp(value)
    return (t.tz_localize("UTC") if t.tz is None else
            t.tz_convert("UTC")).normalize()


def replay_exact_live_market_buy(price,fx,*,start,terminal,
                                 fractions=ALL_FRACTIONS,
                                 budget_aud=BUDGET_AUD):
    """Same first below-200WMA trigger, same 7d actual-trade cooldown.

    Important: date T's signal uses T-1 data; first BTC fill is T
    close, an optimistic proxy for ASX:IBIT trading hours. Since this
    is a fresh cash account, SELL WATCH signals cannot execute.
    """
    start,end=_utc(start),_utc(terminal)
    if (not isinstance(price,pd.Series) or
            not isinstance(price.index,pd.DatetimeIndex) or
            price.index.tz is None or
            not price.index.is_monotonic_increasing or
            price.index.has_duplicates or
            start not in price.index or end not in price.index or start>=end):
        raise ValueError("Chronological UTC cash start/terminal required")
    required=pd.date_range(start-pd.Timedelta(days=1394),end,
                           freq="D",tz="UTC")
    if not required.isin(price.index).all():
        raise ValueError("Strictly prior price warmup missing")
    arr=price.loc[required].to_numpy(float)
    if not np.isfinite(arr).all() or (arr<=0).any():
        raise ValueError("Invalid BTC market prices")
    if (not math.isfinite(float(budget_aud)) or budget_aud<=100
            or not fractions or
            not all(math.isfinite(float(p)) and 0<float(p)<=1
                    for p in fractions) or len(set(fractions))!=len(fractions)):
        raise ValueError("Invalid account and challenger fractions")
    wallets={f:AuditSmsfAccount(float(budget_aud),fee=FEE_AUD,tax=True)
             for f in fractions}
    filled={f:[] for f in fractions}
    last_fill={f:None for f in fractions}
    market_eligible_days=0
    first_signal=None
    sell_watch_days=0
    for date in pd.date_range(start+pd.Timedelta(days=1),end,freq="D",tz="UTC"):
        prev,wma=_historical_wma(price,date)
        eligible=prev<wma
        # Make the SAME market-level engine as Streamlit/ntfy, rather
        # than assume our independently constructed below-WMA is enough.
        market={
            "price_history":price.loc[:date],
            "previous_close_usd":prev,
            "prior_200wma_usd":wma,
            "previous_close_below_200wma":eligible,
            "halving_day":9999,  # never used in BUY override
        }
        actual=calculate_allocation_signal(
            market,buy_style="adaptive_recovery")
        if eligible:
            if (actual["signal"]!="BUY WATCH" or
                    actual["buy_pct_cash"]!=2.5):
                raise AssertionError("Current Cycle market BUY rule drifted")
            market_eligible_days+=1
            if first_signal is None:first_signal=date
        elif actual["signal"]=="SELL WATCH":
            sell_watch_days+=1  # not tradable: initially BTC-free account
        # Mark before/after orders identically to BTC wallet full ledger.
        spot=float(price.loc[date])
        rate=fx_before(fx,date)
        for fraction,wallet in wallets.items():
            # Exact 7-day recorded fill cooldown; NOT fixed weekly reviews.
            due=(last_fill[fraction] is None or
                 (date-last_fill[fraction]).days>=TRADE_COOLDOWN_DAYS)
            if eligible and due:
                gross=float(wallet.cash)*fraction
                if gross>MIN_ORDER_AUD and gross>2*FEE_AUD:
                    success=wallet.buy(date,spot*rate,
                                       min(1.,gross/wallet.cash))
                    if success:
                        order=wallet.orders[-1]
                        filled[fraction].append({
                            "date":str(date.date()),
                            "gross_aud":round(float(order["gross_aud"]),2),
                            "btc":round(float(order["btc"]),10),
                            "previous_close_200wma_ratio":round(prev/wma,6),
                            "pct_remaining_cash":round(fraction*100,3),
                            "actual_same_day_live_market_pct":actual[
                                "buy_pct_cash"],
                        })
                        last_fill[fraction]=date
            wallet.mark(spot*rate)
    spot=float(price.loc[end])*fx_before(fx,end)
    output={}
    for fraction,wallet in wallets.items():
        orders=filled[fraction]
        final=wallet.liquidation_value(end,spot)
        spent=sum(o["gross_aud"] for o in orders)
        output[str(fraction)]={
            "fraction_remaining_cash_pct":round(fraction*100,3),
            "original_live_market_allocation_pct":2.5,
            "is_actual_simplified_live_allocation":fraction==BASELINE_FRACTION,
            "first_market_buy_watch":(
                str(first_signal.date()) if first_signal is not None else None),
            "first_executed_buy":orders[0]["date"] if orders else None,
            "fills":len(orders),
            "btc_held":round(wallet.btc,8),
            "cash_left_aud":round(wallet.cash,2),
            "cash_left_pct":round(100*wallet.cash/budget_aud,2),
            "aftertax_aud":round(final,2),
            "fees_aud":round(wallet.total_fees,2),
            "mean_aud_spend_aud":round(spent/len(orders),2) if orders else None,
            "orders":orders,
        }
        for i in range(1,len(orders)):
            if (_utc(orders[i]["date"])-_utc(orders[i-1]["date"])).days<7:
                raise AssertionError("Disallowed duplicate weekly trades")
        if any(order["actual_same_day_live_market_pct"]!=2.5
               for order in orders):
            raise AssertionError("Live signal 2.5pct parity lost")
    return {
        "start":str(start.date()),
        "terminal":str(end.date()),
        "first_below_200wma_buy_watch":(
            str(first_signal.date()) if first_signal is not None else None),
        "eligible_daily_watch_count":market_eligible_days,
        "no_fabricated_historical_sale":True,
        "market_sell_watch_not_executable_days":sell_watch_days,
        "wallets":output,
    }


def match_rows(replay,*,cycle,start_day,synthetic=False,
               shock_drop_pct=None,terminal_pct=None,
               complete=True):
    base=replay["wallets"][str(BASELINE_FRACTION)]
    rows=[]
    for fraction in FROZEN_CHALLENGERS:
        challenger=replay["wallets"][str(fraction)]
        rows.append({
            "cycle":cycle,"start_day":int(start_day),
            "synthetic":synthetic,"shock_drop_pct":shock_drop_pct,
            "terminal_pct":terminal_pct,"complete":complete,
            "start":replay["start"],"terminal":replay["terminal"],
            "first_below_200wma":replay["first_below_200wma_buy_watch"],
            "fraction_candidate_pct":fraction*100,
            "aftertax_live_baseline_aud":base["aftertax_aud"],
            "aftertax_candidate_aud":challenger["aftertax_aud"],
            "candidate_relative_aftertax_pct":round(
                100*(challenger["aftertax_aud"]/base["aftertax_aud"]-1),3),
            "btc_baseline":base["btc_held"],
            "btc_candidate":challenger["btc_held"],
            "candidate_btc_units_relative_pct":(
                round(100*(challenger["btc_held"]/base["btc_held"]-1),3)
                if base["btc_held"] else None),
            "cash_baseline_pct":base["cash_left_pct"],
            "cash_candidate_pct":challenger["cash_left_pct"],
            "baseline_fills":base["fills"],
            "candidate_fills":challenger["fills"],
        })
    return rows


def audit(history,*,fx_fetcher=fetch_fx_for_cycle):
    price=history["price_usd"].dropna().sort_index().loc[:CUTOFF]
    real=[];stressed=[]
    for label,item in PRIMARY.items():
        halving=_utc(item["halving"])
        terminal=min(halving+pd.Timedelta(days=SCORE_DAYS),price.index[-1])
        fx=fx_fetcher(halving,terminal)
        for start_day in START_DAYS:
            start=halving+pd.Timedelta(days=int(start_day))
            if start>=terminal:continue
            replay=replay_exact_live_market_buy(
                price,fx,start=start,terminal=terminal)
            real.extend(match_rows(
                replay,cycle=label,start_day=start_day,
                complete=terminal==halving+pd.Timedelta(days=SCORE_DAYS)))
        for cycle,startday,shockday in SHOCK_COHORTS:
            if cycle!=label:continue
            if terminal!=halving+pd.Timedelta(days=SCORE_DAYS):
                raise ValueError("Historical stress horizon not complete")
            for decline in SHOCK_DROPS:
                for terminal_ratio in SHOCK_TERMINALS:
                    altered=delayed_bottom_path(
                        price,halving,shock_start_day=shockday,
                        loss_fraction=decline,
                        terminal_price_fraction=terminal_ratio,
                        trough_day=SHOCK_TROUGH_DAY)
                    re=replay_exact_live_market_buy(
                        altered,fx,
                        start=halving+pd.Timedelta(days=startday),
                        terminal=terminal)
                    stressed.extend(match_rows(
                        re,cycle=label,start_day=startday,
                        synthetic=True,shock_drop_pct=100*decline,
                        terminal_pct=100*terminal_ratio))
    if not real or not stressed:
        raise AssertionError("Missing historical/stress outcomes")
    return {
        "research_only":True,
        "live_trading_files_unchanged":True,
        "claim_of_end_to_end_actual_IBIT_parity":False,
        "confirmed_market_level_buy_pct_remaining":2.5,
        "confirmed_trade_cooldown_days":TRADE_COOLDOWN_DAYS,
        "historical_daily_2p5_not_live_rule_parity":True,
        "previous_2017_149pct_advantage_not_live_parity":True,
        "historical":real,
        "synthetic_delayed_bottom":stressed,
        "notes":[
            "Original 2.5%-remaining-cash BUY is replayed WITH 7-day cooldown; no daily stacking.",
            "Only BUY side; hypothetical cash-only start, no legacy historical sale or user-held IBIT inventory.",
            "Alternative 3.5%/5% are frozen candidates, not live allocations.",
            "Original SELL stages are percentage-of-remaining units, not the historical original-BTC-denominator model.",
            "BTC USD closes on weekends are not executable IBIT/AUD quotes; illustrative FIFO CGT only.",
            "2017/2021 completed periods were previously inspected; 2025/26 right-censored at Oct5.",
            "Synthetic 50/70% downside paths test vulnerability, not probabilities.",
        ],
    }


def main(argv=None):
    p=argparse.ArgumentParser()
    p.add_argument("--out",type=Path,
                   default=Path("artifacts/live_weekly_buy_parity"))
    opts=p.parse_args(argv)
    result=audit(read_exported_history())
    opts.out.mkdir(parents=True,exist_ok=True)
    (opts.out/"audit.json").write_text(json.dumps(result,indent=2))
    keys=tuple(result["historical"][0].keys())
    for file,rows in (("historical.csv",result["historical"]),
                      ("shock.csv",result["synthetic_delayed_bottom"])):
        with (opts.out/file).open("w",newline="") as output:
            w=csv.DictWriter(output,fieldnames=keys)
            w.writeheader()
            w.writerows(rows)
    for group in ("historical","synthetic_delayed_bottom"):
        for row in result[group]:
            print(json.dumps({
                "group":group,"cycle":row["cycle"],"start":row["start_day"],
                "candidate_pct":row["fraction_candidate_pct"],
                "relative_aftertax_pct":row["candidate_relative_aftertax_pct"],
                "btc_change_pct":row["candidate_btc_units_relative_pct"],
                "base_fills":row["baseline_fills"],
                "candidate_fills":row["candidate_fills"],
                "baseline_cash_pct":row["cash_baseline_pct"],
                "candidate_cash_pct":row["cash_candidate_pct"],
                "shock_drop_pct":row["shock_drop_pct"],
                "terminal_pct":row["terminal_pct"],
            },sort_keys=True))
    print("RESEARCH ONLY; CYCLE STREAMLIT + NTFY NOT MODIFIED")


if __name__=="__main__":
    main()
