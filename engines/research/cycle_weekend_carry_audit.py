"""Post-hoc separate Cycle weekend BUY WATCH carry-forward experiment.

Hypothesis inspired by research PR147: 2017 completed cash cohort's sole
fresh WMA gate landed on Sunday and zero ASX-weekday trades occurred.
Never use this as unseen or independently prospectively validated proof.

Model: preserve original WMA market WATCH on closed BTC prices. If
WATCH happens Sat/Sun, pending market opportunity can be considered on
the FIRST subsequent WEEKDAY (ASX holiday calendar missing) only if:
  - still no actual recent executed BUY (7-calendar-day cooldown),
  - signal source is <= 3 elapsed calendar days old,
  - strict prior-day BTC close is <= 1.03 * prior strict 200 WEEK MA,
  - pending signal expires immediately after FIRST weekday review.
Do not retroactively execute on the weekend; fill at weekday T BTC/AUD
CLOSE PROXY + explicitly assumed spread, not an actual ASX:IBIT bid/ask.
This is an additional candidate LIVE policy that may contradict the
original Monday HOLD. Never silently deploy or send an ntfy message.
"""
from __future__ import annotations
import argparse
import csv
import json
from pathlib import Path

import pandas as pd

from engines.research.cycle_asx_weekday_execution_proxy import replay_proxy
from engines.research.day500_aftertax_reinvestment import (
    PRIMARY,SCORE_DAYS,fetch_fx_for_cycle,
)
from engines.research.fresh_cash_200wma_matched_backtest import START_DAYS
from engines.research.staged_dca_delayed_bottom_stress import delayed_bottom_path
from engines.research.top_signal_horse_race import read_exported_history

CUTOFF=pd.Timestamp("2026-10-05",tz="UTC")
FRACTIONS=(.025,.03)
COST_STYLES=(("zero_spread_no_nav_drag",0,0.),
             ("assumed_25bps_per_side_nav039",25,.0039),
             ("assumed_50bps_per_side_nav039",50,.0039))
STRESS_PREFIX=(("2017",750,960),("2021",650,900))
STRESS_DECLINES=(.50,.70)
STRESS_TERMINALS=(.55,1.05)


def _utc(s):
    d=pd.Timestamp(s)
    return (d.tz_localize("UTC") if d.tzinfo is None
            else d.tz_convert("UTC")).normalize()


def compare(price,fx,*,start,terminal,cycle,cohort,shock=None):
    outputs=[]
    for cost_name,bps,navfee in COST_STYLES:
        original=replay_proxy(
            price,fx,start=start,terminal=terminal,
            fractions=FRACTIONS,weekday_only=True,
            one_side_cost_bps=bps,annual_nav_fee=navfee,
            carry_weekend=False)
        carry=replay_proxy(
            price,fx,start=start,terminal=terminal,
            fractions=FRACTIONS,weekday_only=True,
            one_side_cost_bps=bps,annual_nav_fee=navfee,
            carry_weekend=True,carry_max_days=3,
            rebound_cap_over_200wma=.03)
        if original["market_buy_watch_dates"]!=carry["market_buy_watch_dates"]:
            raise AssertionError("Market model WATCH changed")
        for frac in FRACTIONS:
            old=original["account"][str(frac)]
            new=carry["account"][str(frac)]
            extra=[o for o in new["orders"]
                   if o["entry_reason"]=="last_weekend_prior_200wma_watch_carried"]
            outputs.append({
                "cycle":cycle,
                "halving_cohort_startday":cohort,
                "start":str(_utc(start).date()),
                "terminal":str(_utc(terminal).date()),
                "synthetic":shock is not None,
                "synthetic_drop_pct":shock[0] if shock else None,
                "synthetic_terminal_pct_prior_shock":shock[1] if shock else None,
                "fee_scenario":cost_name,
                "one_side_bps":bps,
                "assumed_nav_drag_annual_pct":navfee*100,
                "existing_or_challenger_fraction_pct":round(frac*100,3),
                "original_wma_watches":carry["market_buy_watch_dates"],
                "original_weekend_watches":carry["buy_watch_weekend_dates"],
                "unmodified_weekday_buy_count":old["purchases"],
                "carried_weekend_buy_count":new["purchases"],
                "new_carried_buy_count":len(extra),
                "new_carried_dates":";".join(x["date"] for x in extra),
                "original_aftertax_aud":old[
                    "hypothetical_aud_aftertax_liquidation"],
                "carried_aftertax_aud":new[
                    "hypothetical_aud_aftertax_liquidation"],
                "carried_vs_strict_weekday_aftertax_pct":round(
                    100*(new["hypothetical_aud_aftertax_liquidation"]/
                         old["hypothetical_aud_aftertax_liquidation"]-1),3),
                "original_btc":old["btc_equivalent"],
                "carried_btc":new["btc_equivalent"],
                "original_cash_aud":old["remaining_cash_aud"],
                "carried_cash_aud":new["remaining_cash_aud"],
                "carried_buy_orders":new["orders"],
            })
    return outputs


def audit(history,*,fx_fetcher=fetch_fx_for_cycle):
    prices=history["price_usd"].dropna().sort_index().loc[:CUTOFF]
    historical=[]
    shocks=[]
    for label,metadata in PRIMARY.items():
        halving=_utc(metadata["halving"])
        terminal=min(prices.index[-1],halving+pd.Timedelta(days=SCORE_DAYS))
        fx=fx_fetcher(halving,terminal)
        for offset in START_DAYS:
            start=halving+pd.Timedelta(days=int(offset))
            if start>=terminal:continue
            historical+=compare(
                prices,fx,start=start,terminal=terminal,
                cycle=label,cohort=int(offset))
        for cycle,offset,shockday in STRESS_PREFIX:
            if label!=cycle:continue
            if terminal!=halving+pd.Timedelta(days=SCORE_DAYS):
                raise ValueError("Stress requires full historical cycle")
            for decline in STRESS_DECLINES:
                for end_ratio in STRESS_TERMINALS:
                    alt=delayed_bottom_path(
                        prices,halving,shock_start_day=shockday,
                        loss_fraction=decline,
                        terminal_price_fraction=end_ratio,trough_day=1060)
                    shocks+=compare(
                        alt,fx,start=halving+pd.Timedelta(days=offset),
                        terminal=terminal,cycle=label,cohort=offset,
                        shock=(100*decline,100*end_ratio))
    return {
        "research_only":True,
        "policy_proposed_after_sunday_missed_signal_discovery":True,
        "unmodified_market_model":True,
        "candidate_weekend_only_on_first_weekday":True,
        "candidate_max_age_days":3,
        "candidate_rebound_cap_above_200wma_pct":3,
        "calendar_not_real_asx_holidays":True,
        "btc_aud_price_proxy_not_real_asx_ibit":True,
        "2025_26_right_censored_at":str(prices.index[-1].date()),
        "historical":historical,
        "synthetic_bear_shocks":shocks,
        "warnings":[
            "The candidate is post-hoc and fails if weekend low does not persist sufficiently; actual market WATCH can say HOLD when a queued weekday purchase is considered.",
            "Old 2017 and 2021 bottoms have been examined repeatedly: no untouched holdout.",
            "The first available weekday excludes actual ASX holidays; prices are BTC/USD close converted via dated prior USD/AUD FX, not an IBIT executable quote.",
            "Prior-day close and WMA are never revised using future data; the trade fill price is next-close proxy.",
            "Synthetic crashes, ETF expense assumptions and illustrative SMSF FIFO liquidation are not forecasts or broker statements.",
            "No actual purchases, alerts, Google Sheets data, Streamlit or Production were modified.",
        ],
    }


def main(argv=None):
    p=argparse.ArgumentParser()
    p.add_argument("--out",type=Path,
                   default=Path("artifacts/cycle_weekend_carry"))
    opts=p.parse_args(argv)
    report=audit(read_exported_history())
    opts.out.mkdir(parents=True,exist_ok=True)
    (opts.out/"audit.json").write_text(json.dumps(report,indent=2))
    for tag,rows in (("historical.csv",report["historical"]),
                     ("synthetic_stress.csv",report["synthetic_bear_shocks"])):
        with (opts.out/tag).open("w",newline="") as f:
            cols=[x for x in rows[0] if x!="carried_buy_orders"]
            w=csv.DictWriter(f,fieldnames=cols)
            w.writeheader()
            w.writerows([{k:v for k,v in r.items()
                           if k!="carried_buy_orders"} for r in rows])
        for r in rows:
            print(json.dumps({k:r[k] for k in (
                "cycle","halving_cohort_startday","synthetic",
                "fee_scenario","existing_or_challenger_fraction_pct",
                "original_weekend_watches","unmodified_weekday_buy_count",
                "carried_weekend_buy_count","new_carried_buy_count",
                "new_carried_dates","carried_vs_strict_weekday_aftertax_pct",
                "synthetic_drop_pct","synthetic_terminal_pct_prior_shock")},sort_keys=True))
    print("RESEARCH ONLY: Weekend signal carry not added to live Cycle Trading")


if __name__=="__main__":
    main()
