"""Frozen evidence inventory for original 200WMA BUY / day-500 SELL policy.

This is not a new optimized model. It simply reruns the ALREADY-IMPLEMENTED
historical research functions, reports what was measured, and rejects false
claims of equivalence with the simplified Streamlit and ntfy allocations.

One canonical original-BTC-denominated historical exit:
maturity_90pct_holdback20pct (day500 start, reviewed through day730).
BUY after last sale +14 days: strictly prior 200WMA eligibility, weekly
adaptive recovery fractions of ORIGINAL net after-tax buyback budget.

Hypothetical A$500k BTC purchased at each historical halving; actual 2026
user holdings were NOT available then. 2017/2021 are retrospectively
observed; 2025/26 is right-censored.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import pandas as pd

from engines.research.cycle_trade_allocation import (
    BACKTEST_LIVE_PARITY_VERIFIED,SELL_REVIEW_DAY_WEIGHTS,
    DEFAULT_BUY_STYLE,
)
from engines.research.day500_aftertax_reinvestment import (
    INITIAL_AUD,PRIMARY,SCORE_DAYS,fetch_fx_for_cycle,simulate_roundtrip,
)
from engines.research.shared_cycle_policy import (
    START_DAY,REVIEW_DAY,STAGED_POLICIES,recovery_buy_budget_fraction,
)
from engines.research.top_signal_horse_race import read_exported_history

ORIGINAL_SELLER="dynamic_90pct_holdback20pct"
ORIGINAL_BUYER="adaptive_recovery"
BUYBACK_ENTRY="below_200wma"
ALTERNATIVE_BUYER="adaptive_value"


def frozen_policy_facts():
    """Capture identity and explicit differences; do not auto-promote results."""
    if (DEFAULT_BUY_STYLE!=ORIGINAL_BUYER or
            START_DAY!=500 or REVIEW_DAY!=730 or
            not ("maturity_90pct_holdback20pct" in STAGED_POLICIES)):
        raise AssertionError("Original research configuration changed; manual review needed")
    if BACKTEST_LIVE_PARITY_VERIFIED:
        raise AssertionError("Cannot certify historical-to-live parity without full wallet replay")
    # Live sells 5/24/20/... % of REMAINING holdings, whereas historical
    # staged exits are % of ORIGINAL holdings with 80% pre560 cap.
    remain=1.
    for pct in SELL_REVIEW_DAY_WEIGHTS.values():
        remain*=1-float(pct)
    if abs(remain-.37316471808)>1e-9:
        raise AssertionError("Simplified live SELL denominator changed")
    return {
        "strategy":"Original historical below-200WMA recovery BUY and day500 original-BTC SELL",
        "historical_seller":ORIGINAL_SELLER,
        "historical_buy_style":ORIGINAL_BUYER,
        "start_sell_day":START_DAY,
        "last_exit_review_day":REVIEW_DAY,
        "original_position_pre560_sold_cap_pct":80.,
        "historical_buy_activation":"strictly prior completed BTC close below prior 200WMA",
        "historical_buy_budget":"original net after-tax sale proceeds, then continuing weekly recovery",
        "actual_streamlit_ntfy_buy_budget":"remaining available AUD cash, 2.5% when below 200WMA",
        "actual_streamlit_ntfy_sell_budget":"currently remaining holdings; not original-BTC fractions",
        "live_seven_stages_original_btc_remaining_if_all_fill_pct":round(100*remain,2),
        "historical_parity_with_live_verified":BACKTEST_LIVE_PARITY_VERIFIED,
        "user_2026_holdings_recreated_at_2025_day500":False,
    }


def run_original_evidence(history, *, fx_fetcher=fetch_fx_for_cycle):
    """Reuse original self-financing research code with identical-date hold."""
    facts=frozen_policy_facts()
    source=history["price_usd"].loc[:pd.Timestamp("2026-10-05",tz="UTC")]
    if source.empty or not source.index.is_monotonic_increasing:
        raise ValueError("Missing/scrambled price archive")
    results=[]
    for cycle,meta in PRIMARY.items():
        halving=pd.Timestamp(meta["halving"],tz="UTC")
        expected=halving+pd.Timedelta(days=SCORE_DAYS)
        observed=min(expected,source.index[-1])
        if observed not in source.index:
            raise ValueError("Missing historic scoring-date price")
        fx=fx_fetcher(halving,observed)
        records={}
        for style in (ORIGINAL_BUYER,ALTERNATIVE_BUYER):
            outcome=simulate_roundtrip(
                source,fx,halving,observed,
                seller=ORIGINAL_SELLER,
                gate=.40,
                entry_mode=BUYBACK_ENTRY,
                buyback_style=style,
                buyback_weeks=52,
            )
            if outcome["seller"]!=ORIGINAL_SELLER or outcome["buyback_style"]!=style:
                raise AssertionError("Canonical original research definition drift")
            fields=(
                "sell_count","buyback_buy_count","entry_sold_fraction",
                "buyback_trigger_date","average_repurchase_usd_per_btc",
                "post_sale_hindsight_low_close_usd",
                "buyback_error_above_post_sale_low_pct",
                "btc_held_after_buyback","cash_remaining_aud",
                "btc_equivalent_at_terminal_including_cash",
                "btc_equivalent_relative_to_hold_pct",
                "hypothetical_liquidated_after_cgt_aud",
                "hold_hypothetical_liquidated_after_cgt_aud",
                "realised_smsf_cgt_paid_est_aud","brokerage_aud",
            )
            records[style]={name:outcome[name] for name in fields}
        results.append({
            "historic_cycle":cycle,
            "halving_date":str(halving.date()),
            "historical_day500_date":str((halving+pd.Timedelta(days=500)).date()),
            "observation_ends":str(observed.date()),
            "complete_window":bool(observed==expected),
            "hypothetical_initial_aud":INITIAL_AUD,
            "same_hold_account":True,
            "outcomes":records,
        })
    return {
        "version":"original-200wma-day500-evidence-v1",
        "status":"RESEARCH ONLY; no live trading recommendation changes",
        "historical_price_observation_through":str(source.index[-1].date()),
        "policy":facts,
        "cycles":results,
        "caveats":[
            "Only two complete modern retrospective cycles; not independent out-of-sample success.",
            "Real user's 2026 purchases did not exist at the 2024-halving day500 in September 2025.",
            "The original historical adaptive BUY policy continues after first strict 200WMA crossing; it uses original after-tax sale cash rather than current remaining cash.",
            "The simplified Streamlit and ntfy trades have NOT been backtested identically to this account-level historical replay.",
            "FX taken from strictly earlier dated USD/AUD; A$3 per fill and simplified immediate FIFO SMSF accumulation CGT 10/15%. Not verified real broker fills or annual fund taxation.",
            "No ASX:IBIT tracking error, market impact, pension tax context or original account inventory.",
            "2025/26 cycle truncated through historic archive, its bottom and outcomes are right-censored.",
            "No new model optimization or hypothetical early-200WMA buys from other PRs introduced.",
        ],
    }


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--output",type=Path)
    args=parser.parse_args()
    result=run_original_evidence(read_exported_history())
    print("HISTORICAL POLICY PARITY WITH LIVE:",result["policy"]["historical_parity_with_live_verified"])
    for item in result["cycles"]:
        for name,entry in item["outcomes"].items():
            print(json.dumps({
                "cycle":item["historic_cycle"],"complete":item["complete_window"],
                "buy_style":name,
                "buyback_fills":entry["buyback_buy_count"],
                "buy_vwap_error_pct":entry["buyback_error_above_post_sale_low_pct"],
                "btc_equivalent_vs_hold_pct":entry["btc_equivalent_relative_to_hold_pct"],
                "btc_actually_held":entry["btc_held_after_buyback"],
                "cash_left_aud":entry["cash_remaining_aud"],
                "liquidated_after_cgt_aud":entry["hypothetical_liquidated_after_cgt_aud"],
                "hold_liquidated_after_cgt_aud":entry["hold_hypothetical_liquidated_after_cgt_aud"],
            },sort_keys=True))
    if args.output:
        args.output.parent.mkdir(parents=True,exist_ok=True)
        args.output.write_text(json.dumps(result,indent=2,allow_nan=False))
        print("Audit saved:",args.output)


if __name__=="__main__":
    main()
