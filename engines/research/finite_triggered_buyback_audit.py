"""Frozen research-only challenge to cash-stranded Cycle Trading BUYBACK.

Reuse the precise historical SELL + SMSF FIFO tax + UTC Bitcoin/AUD price
simulator from #151. Compare all accounts independently under three BUY
rules, with identical past market data, historical starting BTC, SELL
policy, 7-day ledger gap, AUD3 brokerage and CGT treatment:
  - ORIGINAL live 2.5% of remaining AUD cash ONLY while strictly below
    the prior 200-week BTC/USD average.
  - CANDIDATE at most 24 weekly net-cash tranches, activated by FIRST
    executed original below-200WMA BUY WATCH; then may buy ABOVE 200WMA.
  - CANDIDATE same but at most 52 dated weekly net-cash tranches.
No weekend carry: a Sat/Sun eligible signal alone must NOT silently
activate a weekday ASX account. Weekend carry tested separately in #148.
Crucial: 24/52 extra orders are a POST-HOC hypothesis, NOT validated
equivalently to the current public market-level live rule and not a
currently authorised trading recommendation.

Synthetic 2x/4x late bull and deep bear paths are expressly different
futures from actual historical prefix, never probabilities. BTC/USD
closes are counterfactual proxies, pre-Nov2025 ASX:IBIT quotes do not
exist, and 2016/2020/2024 holdings are NOT the user's real funds.
"""
from __future__ import annotations
import argparse
import csv
import json
from pathlib import Path
import pandas as pd

from engines.research.live_cycle_self_financing_roundtrip import (
    BUY_STYLES,simulate_full_roundtrip,rising_bull_path,
    FULL_DAYS,INITIAL_CAPITAL,CUTOFF,STRESS_START_DAY,STRESS_TROUGH_DAY,
)
from engines.research.staged_dca_delayed_bottom_stress import delayed_bottom_path
from engines.research.day500_aftertax_reinvestment import (
    PRIMARY,fetch_fx_for_cycle,
)
from engines.research.top_signal_horse_race import read_exported_history
from engines.research.live_cycle_sell_parity_audit import day

EXECUTION_STYLES=(False,True)
BULL_MULTIPLIERS=(2.,4.)
DEEP_DECLINES=(.50,.70)
OBSERVED_CYCLES=("2017","2021","2025")


def compare_buyback_modes(price,fx,*,halving,terminal,
                          cycle,case,weekday_only=False,
                          stress=None):
    snapshots={}
    for mode in BUY_STYLES:
        snapshots[mode]=simulate_full_roundtrip(
            price,fx,halving=halving,terminal=terminal,
            starting_cash=INITIAL_CAPITAL,
            weekday_only=weekday_only,buyback_mode=mode)
    expected=set(snapshots[BUY_STYLES[0]]["accounts"])
    if any(set(snap["accounts"])!=expected
           for snap in snapshots.values()):
        raise AssertionError("Unmatched original SELL policy wallet set")
    rows=[]
    for policy in sorted(expected):
        old=snapshots[BUY_STYLES[0]]["accounts"][policy]
        for mode in BUY_STYLES:
            wallet=snapshots[mode]["accounts"][policy]
            if wallet["original_btc"]!=old["original_btc"]:
                raise AssertionError("Candidate changed initial BTC")
            old_btc=old["btc_left_after_buybacks"]
            now_btc=wallet["btc_left_after_buybacks"]
            rows.append({
                "cycle":cycle,
                "case":case,
                "stress":stress,
                "weekday_only_BTC_AUD_proxy":weekday_only,
                "first_day":snapshots[mode]["halving"],
                "terminal":snapshots[mode]["terminal"],
                "observed_horizon_days":snapshots[mode]["cycle_day"],
                "SELL_strategy":policy,
                "BUYBACK_strategy":mode,
                "is_current_live_BUYBACK":mode==BUY_STYLES[0],
                "original_position_BTC":wallet["original_btc"],
                "original_live_buy_count":old["actual_buyback_orders"],
                "candidate_buy_count":wallet["actual_buyback_orders"],
                "first_buyback_trigger":wallet[
                    "first_200wma_funded_buyback_trigger"],
                "total_sell_count":wallet["actual_sell_orders"],
                "actually_held_BTC":now_btc,
                "baseline_held_BTC":old_btc,
                "actual_BTC_vs_live_buyback_pct":(
                    round(100*(now_btc/old_btc-1),3) if old_btc>0 else None),
                "unspent_AUD_cash":wallet["cash_remaining_aud"],
                "baseline_unspent_AUD_cash":old["cash_remaining_aud"],
                "BTC_equivalent_including_cash":wallet[
                    "btc_equivalent_mark_including_cash"],
                "BTC_equivalent_vs_live_buyback_pct":round(100*(
                    wallet["btc_equivalent_mark_including_cash"]/
                    old["btc_equivalent_mark_including_cash"]-1),3),
                "terminal_aftertax_AUD":wallet[
                    "hypothetical_aftertax_liquidation_aud"],
                "terminal_aftertax_AUD_vs_live_buyback_pct":round(100*(
                    wallet["hypothetical_aftertax_liquidation_aud"]/
                    old["hypothetical_aftertax_liquidation_aud"]-1),3),
                "terminal_aftertax_AUD_vs_hold_pct":wallet[
                    "hypothetical_aftertax_aud_vs_hold_pct"],
                "realised_CGT_estimate_AUD":wallet["realised_smsf_cgt_aud"],
                "all_dated_orders":wallet["dated_orders"],
            })
    return rows


def evaluate(history,*,fx_fetcher=fetch_fx_for_cycle):
    px=history["price_usd"].dropna().sort_index().loc[:CUTOFF]
    historical=[]
    stressed=[]
    for cycle,record in PRIMARY.items():
        h=day(record["halving"])
        end=min(h+pd.Timedelta(days=FULL_DAYS),px.index[-1])
        fx=fx_fetcher(h,end)
        for weekday in EXECUTION_STYLES:
            historical+=compare_buyback_modes(
                px,fx,halving=h,terminal=end,
                cycle=cycle,case="observed_complete_or_censored",
                weekday_only=weekday)
        if cycle=="2025":continue
        if end!=h+pd.Timedelta(days=FULL_DAYS):
            raise ValueError("No stress test with incomplete historic cycle")
        for multiple in BULL_MULTIPLIERS:
            bull=rising_bull_path(px,h,ending_multiple=multiple)
            stressed+=compare_buyback_modes(
                bull,fx,halving=h,terminal=end,cycle=cycle,
                case="bull_continues_after_day600",weekday_only=True,
                stress=f"ending_{multiple:.1f}_times_day600")
        for drop in DEEP_DECLINES:
            bear=delayed_bottom_path(
                px,h,shock_start_day=STRESS_START_DAY,
                loss_fraction=drop,terminal_price_fraction=.55,
                trough_day=STRESS_TROUGH_DAY)
            stressed+=compare_buyback_modes(
                bear,fx,halving=h,terminal=end,cycle=cycle,
                case="new_deeper_bear_after_day900",weekday_only=True,
                stress=f"further_drop_{100*drop:.0f}_percent")
    return {
        "research_only":True,
        "no_live_trade_or_notifications_changed":True,
        "current_unmodified_buy_policy":BUY_STYLES[0],
        "tranches_predeclared_before_this_run":[24,52],
        "initial_position_historic_halving_date_counterfactual":True,
        "daily_BTC_close_not_2017_2021_IBIT_quotes":True,
        "no_weekend_ASX_order_carry_in_proxy":True,
        "cash_only_after_REAL_hypothetical_sale_CGT":True,
        "historical":historical,
        "deliberately_adverse_synthetic":stressed,
        "limitations":[
            "Both finite plans are hypotheses chosen after inspecting 2017 and 2021, not fresh out-of-sample validation.",
            "First finite-plan buy requires same actual below-WMA source WATCH and actual successful fill; in weekday-only mode weekend BUY WATCHs do not activate the plan.",
            "After first buy the 24/52 fixed-count tranche plan can continue ABOVE 200WMA, unlike the unchanged live strict gate; count of trades may extend past literal 24/52 calendar weeks if a concurrent SELL delays a buy.",
            "The full original-SMSF-stage sells are historical counterfactuals, not user owned BTC or currently broker-held IBIT.",
            "No ASX holiday calendar, real ASX:IBIT bid ask, whole units, tracking error, or actual SMSF tax-lot phase.",
            "2017/2021 completed cycles repeatedly inspected; 2025/26 only through 2026-10-05 archive and may not include ultimate bottom.",
            "Stress price paths are hypothetical 2x/4x sustained bulls or 50/70% deeper bear, not probability estimates.",
        ],
    }


def main(argv=None):
    p=argparse.ArgumentParser()
    p.add_argument("--out",type=Path,default=Path(
        "artifacts/finite_triggered_buyback"))
    cfg=p.parse_args(argv)
    report=evaluate(read_exported_history())
    cfg.out.mkdir(parents=True,exist_ok=True)
    (cfg.out/"full_ledgers.json").write_text(json.dumps(report,indent=2))
    for filename,group in (("observed_historical.csv","historical"),
                           ("adverse_futures.csv","deliberately_adverse_synthetic")):
        rows=report[group]
        if not rows:raise AssertionError("No matched entries")
        keys=[k for k in rows[0] if k not in ("all_dated_orders","stress")]
        with (cfg.out/filename).open("w",newline="") as stream:
            writer=csv.DictWriter(stream,fieldnames=keys)
            writer.writeheader()
            writer.writerows([{k:v for k,v in r.items() if k in keys}
                              for r in rows])
        for r in rows:
            if r["BUYBACK_strategy"]==BUY_STYLES[0]:continue
            print(json.dumps({k:r[k] for k in (
                "cycle","case","stress","weekday_only_BTC_AUD_proxy",
                "SELL_strategy","BUYBACK_strategy","first_buyback_trigger",
                "original_live_buy_count","candidate_buy_count",
                "actually_held_BTC","baseline_held_BTC",
                "actual_BTC_vs_live_buyback_pct","unspent_AUD_cash",
                "BTC_equivalent_vs_live_buyback_pct",
                "terminal_aftertax_AUD_vs_live_buyback_pct"
            )},sort_keys=True))
    print("RESEARCH ONLY: finite 24/52 BUYBACK not added to LIVE Cycle Trading")


if __name__=="__main__":
    main()
