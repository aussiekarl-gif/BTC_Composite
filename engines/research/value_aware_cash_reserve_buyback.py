"""Research ONLY: cash-reserved 52wk BTC buyback, market 200WMA valuation.

Identical selected SELL history, CGT, FX and original 200WMA triggering
BUY. Compare original live 2.5%-remaining-cash, fixed24/52, and opt-in
value-aware 52 tranche core50/reserve50:
  - first purchase ONLY after actually executing shared original BUY WATCH
  - commit 50% of real net of CGT cash to 52 weekly scheduled core buys
  - keep other 50% in cash unless PRIOR BTC close <=0.85 * PRIOR 200WMA
  - on qualifying deep-discount weeks, release extra reserve up to
    2x the scheduled core tranche, maintaining 7d filled cooldown
  - any later executed SELL net cash is split 50/50 into core/reserve
No chance of market BACKTEST lookahead beyond the execution-day quote.
This is NOT live advice; parameter values were selected after seeing
historic 2017/2021 outcomes and bear stress. No real ASX bid/ask available
before ETF listing Nov2025; weekday proxy not official exchange calendar.
"""
from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path

import pandas as pd
from engines.research.live_cycle_self_financing_roundtrip import (
    BUY_STYLES,VALUE_RESERVE_MODE,VALUE_CORE_SHARE,
    VALUE_RESERVE_WMA_RATIO,VALUE_RESERVE_EXTRA_CORE_MULT,
    simulate_full_roundtrip,rising_bull_path,
    INITIAL_CAPITAL,FULL_DAYS,CUTOFF,
    STRESS_START_DAY,STRESS_TROUGH_DAY,
)
from engines.research.staged_dca_delayed_bottom_stress import delayed_bottom_path
from engines.research.day500_aftertax_reinvestment import PRIMARY,fetch_fx_for_cycle
from engines.research.live_cycle_sell_parity_audit import day
from engines.research.top_signal_horse_race import read_exported_history

ALL_MODES=(*BUY_STYLES,VALUE_RESERVE_MODE)
REFERENCE=BUY_STYLES[0]
STRESS_LEVELS=(.50,.70)
BULL_ENDINGS=(2.,4.)


def compare(price,fx,*,halving,terminal,cycle,case,weekday,scenario=None):
    paths={}
    for mode in ALL_MODES:
        paths[mode]=simulate_full_roundtrip(
            price,fx,halving=halving,terminal=terminal,
            starting_cash=INITIAL_CAPITAL,weekday_only=weekday,
            buyback_mode=mode)
    result=[]
    for seller in paths[REFERENCE]["accounts"]:
        control=paths[REFERENCE]["accounts"][seller]
        for mode in ALL_MODES:
            r=paths[mode]["accounts"][seller]
            if r["original_btc"]!=control["original_btc"]:
                raise AssertionError("Unequal original BTC holdings")
            if mode==REFERENCE and r!=control:
                raise AssertionError("Baseline drift")
            result.append({
                "cycle":cycle,
                "case":case,
                "scenario":scenario,
                "weekday_only_btc_close_proxy":weekday,
                "terminal":str(day(terminal).date()),
                "cycle_day":(day(terminal)-day(halving)).days,
                "SELL_policy":seller,
                "BUY_policy":mode,
                "starting_BTC":r["original_btc"],
                "buy_count":r["actual_buyback_orders"],
                "sell_count":r["actual_sell_orders"],
                "first_prior200WMA_buy":r["first_200wma_funded_buyback_trigger"],
                "BTC_ACTUALLY_HELD":r["btc_left_after_buybacks"],
                "BTC_equivalent_including_cash":r[
                    "btc_equivalent_mark_including_cash"],
                "AUD_cash_left":r["cash_remaining_aud"],
                "value_core_spent_AUD":r["research_value_core_spent_aud"],
                "value_reserve_used_AUD":r["research_value_reserve_spent_aud"],
                "value_reserve_remaining_AUD":r["research_value_reserve_left_aud"],
                "aftertax_AUD":r["hypothetical_aftertax_liquidation_aud"],
                "BTC_held_vs_original_live_buy_pct":round(
                    100*(r["btc_left_after_buybacks"]/
                         control["btc_left_after_buybacks"]-1),3)
                    if control["btc_left_after_buybacks"]>0 else None,
                "BTC_equiv_including_cash_vs_live_pct":round(
                    100*(r["btc_equivalent_mark_including_cash"]/
                         control["btc_equivalent_mark_including_cash"]-1),3),
                "aftertax_AUD_vs_live_pct":round(
                    100*(r["hypothetical_aftertax_liquidation_aud"]/
                         control["hypothetical_aftertax_liquidation_aud"]-1),3),
                "orders":r["dated_orders"],
            })
    return result


def audit(history,*,fx_fetcher=fetch_fx_for_cycle):
    p=history["price_usd"].dropna().sort_index().loc[:CUTOFF]
    real=[]
    stress=[]
    for cycle,metadata in PRIMARY.items():
        halving=day(metadata["halving"])
        terminal=min(halving+pd.Timedelta(days=FULL_DAYS),p.index[-1])
        fx=fx_fetcher(halving,terminal)
        for weekday in (False,True):
            real+=compare(p,fx,halving=halving,terminal=terminal,cycle=cycle,
                          case="observed_complete_or_censored",weekday=weekday)
        if cycle=="2025":continue
        if terminal!=halving+pd.Timedelta(days=FULL_DAYS):
            raise ValueError("Incomplete baseline cannot be stressed")
        for multiple in BULL_ENDINGS:
            bull=rising_bull_path(p,halving,ending_multiple=multiple)
            stress+=compare(
                bull,fx,halving=halving,terminal=terminal,
                cycle=cycle,case="uninterrupted_late_bull",
                weekday=True,scenario=f"ending_x{multiple:g}")
        for decline in STRESS_LEVELS:
            bear=delayed_bottom_path(
                p,halving,shock_start_day=STRESS_START_DAY,
                loss_fraction=decline,terminal_price_fraction=.55,
                trough_day=STRESS_TROUGH_DAY)
            stress+=compare(
                bear,fx,halving=halving,terminal=terminal,
                cycle=cycle,case="deeper_late_bear",
                weekday=True,scenario=f"additional_minus_{100*decline:.0f}pct")
    return {
        "research_only":True,
        "new_mode":VALUE_RESERVE_MODE,
        "unchanged_baselines":list(BUY_STYLES),
        "core_budget_share":VALUE_CORE_SHARE,
        "protected_cash_share":1-VALUE_CORE_SHARE,
        "deep_discount_prior_200wma_ratio":VALUE_RESERVE_WMA_RATIO,
        "extra_reserve_tranche_multiple":VALUE_RESERVE_EXTRA_CORE_MULT,
        "no_live_streamlit_notifications_or_production_changed":True,
        "source_cutoff":str(p.index[-1].date()),
        "historical":real,
        "synthetic_counterfactual":stress,
        "limits":[
            "Research parameters chosen after historical observations; no independent out-of-sample validation.",
            "This cash reserve exists only AFTER first actually executed below-200 WEEK MA BUY; weekend signal alone never activates weekday candidate.",
            "The 50% core plan can continue buying ABOVE 200WMA; therefore differs from current live WATCH and needs explicit separate authorization.",
            "All original SELL policies and test accounts are hypothetical earlier-historical BTC, NOT user actual holdings.",
            "BTC/USD close plus strictly older dated AUD FX is not executable ASX:IBIT bid/ask; public holidays, ETF NAV and tax regime not exact.",
            "The 2025/26 period remains right-censored at Oct5 2026; first visible archive trough may not be final.",
            "Stress paths are chosen plausible adversarial counterfactuals and not frequencies or predictions.",
            "BTC actually held, cash BTC equivalent, AUD unspent and aftertax wealth are separate metrics.",
        ],
    }


def main(argv=None):
    parser=argparse.ArgumentParser()
    parser.add_argument("--out",type=Path,
                        default=Path("artifacts/value_aware_buyback"))
    args=parser.parse_args(argv)
    out=audit(read_exported_history())
    args.out.mkdir(parents=True,exist_ok=True)
    (args.out/"full_ledgers.json").write_text(json.dumps(out,indent=2))
    for group,filename in (
        ("historical","historical_comparison.csv"),
        ("synthetic_counterfactual","stress_comparison.csv"),
    ):
        rows=out[group]
        keys=[k for k in rows[0] if k!="orders"]
        with (args.out/filename).open("w",newline="") as stream:
            w=csv.DictWriter(stream,fieldnames=keys)
            w.writeheader()
            w.writerows([{k:v for k,v in x.items() if k!="orders"}
                         for x in rows])
        for x in rows:
            if x["BUY_policy"]==REFERENCE:continue
            print(json.dumps({k:x[k] for k in (
                "cycle","case","scenario","weekday_only_btc_close_proxy",
                "SELL_policy","BUY_policy","first_prior200WMA_buy",
                "buy_count","BTC_ACTUALLY_HELD","AUD_cash_left",
                "value_reserve_remaining_AUD","BTC_held_vs_original_live_buy_pct",
                "BTC_equiv_including_cash_vs_live_pct",
                "aftertax_AUD_vs_live_pct",
            )},sort_keys=True))
    print("RESEARCH ONLY: no actual live BUY/SELL or Cash/IBIT changes")


if __name__=="__main__":
    main()
