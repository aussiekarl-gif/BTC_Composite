"""Frozen after PR #144: 3.0% remaining-cash live-like weekly BTC BUY challenger.

Exploratory follow-up selected AFTER viewing earlier 2.5/3.5/5 results.
Calls the exact same audited current market signal and 7-day cooldown
from `live_weekly_buy_parity.py`, with an in-memory private simulated AUD
cash account and NO live Streamlit, notifications or broker orders.
All 2017/2021 historical cohorts ARE in-sample. No untouched validation.
"""
from __future__ import annotations
import argparse
import csv
import json
from pathlib import Path

import pandas as pd

from engines.research.day500_aftertax_reinvestment import (
    PRIMARY,SCORE_DAYS,fetch_fx_for_cycle,
)
from engines.research.fresh_cash_200wma_matched_backtest import START_DAYS
from engines.research.live_weekly_buy_parity import (
    BASELINE_FRACTION,replay_exact_live_market_buy,
)
from engines.research.staged_dca_delayed_bottom_stress import delayed_bottom_path
from engines.research.top_signal_horse_race import read_exported_history

FRACTIONS=(.025,.03,.035)
CUTOFF=pd.Timestamp("2026-10-05",tz="UTC")
SHOCKS=(("2017",750,960),("2021",650,900))
DROPS=(.50,.70)
TERMINALS=(.55,1.05)


def _utc(x):
    x=pd.Timestamp(x)
    return x.tz_localize("UTC") if x.tzinfo is None else x.tz_convert("UTC")


def analyse_wallets(replay,*,cycle,start_day,complete,stress=None):
    w=replay["wallets"]
    reference=w[str(FRACTIONS[0])]
    rows=[]
    for fraction in FRACTIONS[1:]:
        alt=w[str(fraction)]
        rows.append({
            "cycle":cycle,"start_day":start_day,"complete":bool(complete),
            "start":replay["start"],"end":replay["terminal"],
            "stress":bool(stress),"shock_drop_pct":stress[0] if stress else None,
            "terminal_to_pre_shock_pct":stress[1] if stress else None,
            "original_weekly_fraction_pct":2.5,
            "candidate_weekly_fraction_pct":round(fraction*100,3),
            "first_below_200wma_watch":replay[
                "first_below_200wma_buy_watch"],
            "reference_fills":reference["fills"],"candidate_fills":alt["fills"],
            "reference_cash_left_aud":reference["cash_left_aud"],
            "candidate_cash_left_aud":alt["cash_left_aud"],
            "reference_btc":reference["btc_held"],
            "candidate_btc":alt["btc_held"],
            "reference_aftertax_aud":reference["aftertax_aud"],
            "candidate_aftertax_aud":alt["aftertax_aud"],
            "delta_aftertax_aud":round(
                alt["aftertax_aud"]-reference["aftertax_aud"],2),
            "delta_aftertax_pct":round(
                100*(alt["aftertax_aud"]/reference["aftertax_aud"]-1),3),
            "candidate_order_records":alt["orders"],
        })
    return rows


def audit(history,*,fx_fetcher=fetch_fx_for_cycle):
    prices=history["price_usd"].dropna().sort_index().loc[:CUTOFF]
    historical=[];adverse=[]
    for name,item in PRIMARY.items():
        halving=_utc(item["halving"])
        end=min(prices.index[-1],halving+pd.Timedelta(days=SCORE_DAYS))
        fx=fx_fetcher(halving,end)
        for offset in START_DAYS:
            start=halving+pd.Timedelta(days=int(offset))
            if start>=end:continue
            replay=replay_exact_live_market_buy(
                prices,fx,start=start,terminal=end,fractions=FRACTIONS)
            historical+=analyse_wallets(
                replay,cycle=name,start_day=int(offset),
                complete=end==halving+pd.Timedelta(days=SCORE_DAYS))
        for label,offset,shock_day in SHOCKS:
            if label!=name:continue
            if end!=halving+pd.Timedelta(days=SCORE_DAYS):
                raise ValueError("Synthetic historic base not complete")
            for decline in DROPS:
                for terminal_ratio in TERMINALS:
                    altered=delayed_bottom_path(
                        prices,halving,shock_start_day=shock_day,
                        loss_fraction=decline,
                        terminal_price_fraction=terminal_ratio,
                        trough_day=1060)
                    replay=replay_exact_live_market_buy(
                        altered,fx,start=halving+pd.Timedelta(days=offset),
                        terminal=end,fractions=FRACTIONS)
                    adverse+=analyse_wallets(
                        replay,cycle=name,start_day=int(offset),
                        complete=True,
                        stress=(100*decline,100*terminal_ratio))
    return {
        "research_only":True,
        "live_percentages_and_model_unchanged":True,
        "in_sample_parameter_selected_after_prior_results":True,
        "no_future_prices_used_for_purchase_decisions":True,
        "all_cash_cohorts_are_hypothetical":True,
        "historical":historical,
        "adverse_deeper_bear_stress":adverse,
        "warnings":[
            "3.0 percent was selected AFTER reviewing 3.5 percent; not an untouched independent test.",
            "BTC/USD closes are not executable ASX:IBIT/AUD ETF weekend/bid/ask prices.",
            "2025 cohort right-censored through Oct 5 2026; later low not known.",
            "Simple 7-day COOL DOWN uses simulated executed BUYs only, no invented older owned BTC or SELLs.",
            "Aftertax AUD assumes illustrative immediate FIFO SMSF accumulation CGT, not real fund tax phase.",
            "Historical 2017/2021 and adversarial 50/70% market declines are not future market probabilities.",
        ],
    }


def main(argv=None):
    p=argparse.ArgumentParser()
    p.add_argument("--out",type=Path,default=Path("artifacts/cycle_three_pct"))
    args=p.parse_args(argv)
    result=audit(read_exported_history())
    args.out.mkdir(parents=True,exist_ok=True)
    (args.out/"complete_audit.json").write_text(
        json.dumps(result,indent=2))
    for filename,key in (("historical.csv","historical"),
                         ("synthetic.csv","adverse_deeper_bear_stress")):
        rows=result[key]
        if rows:
            with (args.out/filename).open("w",newline="") as handle:
                writer=csv.DictWriter(
                    handle,fieldnames=[
                        k for k in rows[0] if k!="candidate_order_records"])
                writer.writeheader()
                writer.writerows([{k:v for k,v in row.items()
                                   if k!="candidate_order_records"}
                                  for row in rows])
        for row in rows:
            print(json.dumps({
                "group":key,"cycle":row["cycle"],
                "start_day":row["start_day"],"complete":row["complete"],
                "candidate_pct":row["candidate_weekly_fraction_pct"],
                "terminal_delta_aftertax_pct":row["delta_aftertax_pct"],
                "reference_btc":row["reference_btc"],
                "candidate_btc":row["candidate_btc"],
                "reference_cash_aud":row["reference_cash_left_aud"],
                "candidate_cash_aud":row["candidate_cash_left_aud"],
                "shock_drop_pct":row["shock_drop_pct"],
                "terminal_pre_shock_pct":row["terminal_to_pre_shock_pct"],
            },sort_keys=True))
    print("RESEARCH ONLY; ALL LIVE BTC DCA BUY/SELL AND NOTIFICATIONS UNCHANGED")


if __name__=="__main__":
    main()
