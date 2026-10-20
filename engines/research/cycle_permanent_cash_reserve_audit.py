"""Research: genuinely PERMANENT original-AUD cash backstops for BTC weekly buys.

Unlike earlier staged reserve policies, these 15%/25% original-AUD
floors NEVER unlock, even if prior BTC is 70% below its prior 200WMA.
These are deliberately uninvestable/untouched reserves on the BUY-side
A$400,000 cash-only research account. They are NOT instructions about
the user's holdings, SMSF cash, broker access, actual IBIT fills or tax.

Existing original Cycle 2.5% conditional/7d BUY and previous tiered
3.5/5% candidate are preserved; further historic testing is NOT an
independent out-of-sample validation. No Nov 2026 or 2027 cash sweep.
"""
from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path

from engines.research.cycle_deep_value_cash_reserve_audit import (
    audit as shared_reserve_audit, RESERVE_POLICIES, REFERENCE,
)
from engines.research.top_signal_horse_race import read_exported_history

# Separate frozen post-prior-results research hypothesis. Floor remains
# the same at all valuation levels, including below 0.7x the 200WMA.
ORIGINAL_CASH_FLOORS = {
    "live_2p5_cash_floor_15pct_forever": {
        "size": "current_live_2p5_every_valid_BUY",
        "floors": ((1.00, .15),),
    },
    "live_2p5_cash_floor_25pct_forever": {
        "size": "current_live_2p5_every_valid_BUY",
        "floors": ((1.00, .25),),
    },
    "tiered_3p5_5p0_cash_floor_15pct_forever": {
        "size": "tiered_3p5_at_10pct_and_5p0_at_20pct",
        "floors": ((1.00, .15),),
    },
    "tiered_3p5_5p0_cash_floor_25pct_forever": {
        "size": "tiered_3p5_at_10pct_and_5p0_at_20pct",
        "floors": ((1.00, .25),),
    },
}
FROZEN_CASES = {
    REFERENCE: RESERVE_POLICIES[REFERENCE],
    "tiered_3p5_5p0_no_reserve": RESERVE_POLICIES["tiered_3p5_5p0_no_reserve"],
    **ORIGINAL_CASH_FLOORS,
}
OUTPUT = Path("artifacts/research_cycle_permanent_cash_floor")

def summarise_rows(rows,*,label):
    result=[]
    for policy in FROZEN_CASES:
        sub=[r for r in rows if r["policy"]==policy]
        if not sub:
            raise AssertionError("Missing matched original-capital test policy")
        values=[float(r["vs_unmodified_live_2p5_total_AUD_pct"]) for r in sub]
        drawdowns=[float(r["max_drawdown_pct"]) for r in sub]
        cash=[float(r["AUD_cash_left_pct_of_original"]) for r in sub]
        mean_exposure=[float(r["mean_daily_BTC_exposure_pct"]) for r in sub]
        floor = float(FROZEN_CASES[policy]["floors"][-1][1])
        if len(FROZEN_CASES[policy]["floors"])!=1:
            raise AssertionError("Permanent floor study introduced tier releases")
        if any(c<100*floor-.00015 for c in cash):
            raise AssertionError("Permanent reserve was spent in a matched cohort")
        result.append({
            "sample":label,"policy":policy,"research_cases":len(sub),
            "cash_floor_pct_of_original_AUD":round(floor*100,2),
            "min_whole_portfolio_aftertax_vs_unchanged_2p5_pct":round(min(values),4),
            "max_whole_portfolio_aftertax_vs_unchanged_2p5_pct":round(max(values),4),
            "mean_whole_portfolio_aftertax_vs_unchanged_2p5_pct":round(sum(values)/len(values),4),
            "cases_below_unchanged_2p5":sum(v<-.000001 for v in values),
            "worst_marked_account_drawdown_pct":round(min(drawdowns),4),
            "minimum_original_AUD_cash_remaining_pct":round(min(cash),4),
            "mean_observed_BTC_account_exposure_pct":round(sum(mean_exposure)/len(mean_exposure),4),
            "this_sample_independent_holdout":False,
            "ASX_IBIT_real_broker_fills_verified":False,
        })
    return result

def audit(history,*,fx_fetcher=None):
    kwargs={"policy_map":FROZEN_CASES}
    if fx_fetcher is not None: kwargs["fx_fetcher"]=fx_fetcher
    run=shared_reserve_audit(history,**kwargs)
    historic=run["historical"]
    stresses=run["synthetic_extended_bear"]
    # Verify matched same exact cohort+scenario and same original A$,
    # with direct uncapped 2.5% present for EVERY row.
    for rows in (historic,stresses):
        counter={}
        for r in rows:
            key=(r["cycle"],r["halving_day_entry"],
                 r["forced_extra_btc_drop"],r["forced_terminal_vs_before_shock"])
            counter.setdefault(key,set()).add(r["policy"])
        if any(v!=set(FROZEN_CASES) for v in counter.values()):
            raise AssertionError("Matched six-policy historical/stress cases incomplete")
    outcome={
        "kind":"PERMANENT_ORIGINAL_AUD_CASH_FLOOR_CYCLE_BUY_RESEARCH_ONLY",
        "assumptions_frozen_2026_10_20_post_earlier_history":FROZEN_CASES,
        "prior_stepwise_released_reserve_model_not_modified":True,
        "actual_live_Cycle_2p5_and_sell_unchanged":True,
        "user_cash_can_remain_unspent_after_2027":True,
        "original_fixed_15_25pct_reserve_never_releases":True,
        "unseen_live_performance_still_unproven":True,
        "historical_2017_2021_previously_seen":True,
        "right_censored_2025_26_data_not_a_new_cycle":True,
        "hypothetical_daily_BTC_USD_close_and_strict_prior_FX_not_ASX":True,
        "SMSF_accumulation_FIFO_tax_illustrative_not_personal":True,
        "no_interest_on_reserved_AUD_in_model":True,
        "no_portfolio_access":True,"broker_orders":0,"ntfy_sent":0,
        "promotion_approved":False,
        "summary":(
            summarise_rows(historic,label="retrospective_overlapping_2017_2021_2025")
            +summarise_rows(stresses,label="synthetic_further_50_70pct_bear")
        ),
        "historical":historic,
        "synthetic_extended_bear":stresses,
    }
    return outcome

def main(argv=None):
    p=argparse.ArgumentParser(description="Paper-only permanent BTC cash floor sensitivity")
    p.add_argument("--out",type=Path,default=OUTPUT)
    args=p.parse_args(argv)
    result=audit(read_exported_history())
    args.out.mkdir(parents=True,exist_ok=True)
    (args.out/"full_research.json").write_text(
        json.dumps(result,indent=2,sort_keys=True)+"\n",encoding="utf-8")
    for name,rows in (
        ("summary.csv",result["summary"]),
        ("historical.csv",result["historical"]),
        ("extended_bear.csv",result["synthetic_extended_bear"]),
    ):
        fields=[k for k in rows[0] if k!="paper_orders"]
        with (args.out/name).open("w",newline="",encoding="utf-8") as handle:
            w=csv.DictWriter(handle,fieldnames=fields)
            w.writeheader()
            for x in rows:
                w.writerow({k:v for k,v in x.items() if k in fields})
    for row in result["summary"]:
        print("PERMANENT_FLOOR_RESEARCH_SUMMARY "+json.dumps(row,sort_keys=True))
    print("No broker orders, ntfy, portfolio writes, schedule or LIVE model change")

if __name__=="__main__":
    main()
