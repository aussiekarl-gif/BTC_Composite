"""Research-only, explicit net sale cash reserve sensitivity for staged DCA.

Compare fixed 0, 25 or 40% lifetime minimum *net BTC SALE proceeds* reserve.
This is a fixed predeclared policy, NOT an oracle for the future cycle bottom.
No changes to the live BUY/HOLD/SELL rules or actual SMSF portfolio.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import pandas as pd

from engines.research.day500_aftertax_reinvestment import (
    SCORE_DAYS,PRIMARY,fetch_fx_for_cycle,
)
from engines.research.staged_dca_delayed_bottom_stress import (
    delayed_bottom_path,SHOCK_START_DAYS,SHOCK_LOSS_FRACTIONS,
    TERMINAL_FRACTIONS_OF_PRE_SHOCK_PRICE,TROUGH_DAY,
)
from engines.research.staged_tax_aware_roundtrip import replay_roundtrip
from engines.research.top_signal_horse_race import read_exported_history

CAPS=(0.,25.,40.)
COMPLETED_CYCLES=("2017","2021")
SELLER="fixed_525_to_560"


def _brief(record):
    fields=(
        "buyer","minimum_net_sale_proceeds_reserve_pct",
        "net_sale_proceeds_reinvested_pct",
        "cash_remaining_aud","btc_remaining",
        "terminal_btc_equiv_including_cash",
        "account_after_hypothetical_liquidation_cgt_aud",
        "liquidated_aud_vs_hold_pct",
        "buy_error_above_observed_bottom_pct",
        "account_max_marked_drawdown_pct",
    )
    return {key:record[key] for key in fields}


def evaluate_cash_reserves(history, *, fx_fetcher=fetch_fx_for_cycle,
                           cycles=COMPLETED_CYCLES,
                           starts=SHOCK_START_DAYS,
                           losses=SHOCK_LOSS_FRACTIONS,
                           recoveries=TERMINAL_FRACTIONS_OF_PRE_SHOCK_PRICE):
    """Run same historic and synthetic BTC/USD paths against reserve caps."""
    cohort={}
    scenarios=[]
    price=history["price_usd"].dropna().sort_index()
    for cycle in cycles:
        if cycle not in PRIMARY or cycle=="2025":
            raise ValueError("Completed 2017/2021 cycle required")
        halving=pd.Timestamp(PRIMARY[cycle]["halving"],tz="UTC")
        end=halving+pd.Timedelta(days=SCORE_DAYS)
        if end not in price.index:
            raise ValueError("Data missing complete historical stress window")
        fx=fx_fetcher(halving,end)

        def paired(series):
            baseline=replay_roundtrip(series,fx,halving,end,
                                      seller=SELLER,buyer="current_2p5pct")
            staged={k:replay_roundtrip(
                series,fx,halving,end,seller=SELLER,
                buyer="staged_value_recovery",
                min_net_sale_proceeds_reserve_pct=k)
                for k in CAPS}
            for result in staged.values():
                if result["sales"]!=baseline["sales"]:
                    raise AssertionError("Reserve variant changed historical SELL legs")
            return baseline,staged

        baseline,staged=paired(price)
        cohort[cycle]={
            "baseline_current_2p5pct":_brief(baseline),
            "staged_reserve_variants":{
                str(int(k)):_brief(v) for k,v in staged.items()
            }
        }

        for start in starts:
            for loss in losses:
                for recovery in recoveries:
                    shocked=delayed_bottom_path(
                        price,halving,shock_start_day=start,
                        loss_fraction=loss,terminal_price_fraction=recovery)
                    base,variants=paired(shocked)
                    low_date=halving+pd.Timedelta(days=TROUGH_DAY)
                    item={
                        "cycle":cycle,"start_day":int(start),
                        "loss_from_start_pct":round(100*loss),
                        "terminal_price_fraction_start_pct":round(100*recovery),
                        "same_sell_schedule":SELLER,
                        "baseline":_brief(base),
                        "staged":{},
                    }
                    for cap,rec in variants.items():
                        before=sum(float(x["gross_aud"]) for x in rec["buybacks"]
                                   if pd.Timestamp(x["date"],tz="UTC")<low_date)
                        net=float(rec["net_sell_cash_after_tax_aud"])
                        base_aud=base["account_after_hypothetical_liquidation_cgt_aud"]
                        candidate_aud=rec["account_after_hypothetical_liquidation_cgt_aud"]
                        unguarded_aud=variants[0.]["account_after_hypothetical_liquidation_cgt_aud"]
                        item["staged"][str(int(cap))]={
                            **_brief(rec),
                            "spent_before_low_pct_of_net_sale_proceeds":round(
                                100*before/net,2) if net>0 else None,
                            "aftertax_aud_vs_conservative_pct":round(
                                100*(candidate_aud/base_aud-1),2),
                            "aftertax_aud_vs_uncapped_pct":round(
                                100*(candidate_aud/unguarded_aud-1),2),
                        }
                    scenarios.append(item)
    summary={}
    for cycle in cycles:
        selected=[s for s in scenarios if s["cycle"]==cycle]
        for cap in CAPS:
            label=str(int(cap))
            variants=[s["staged"][label] for s in selected]
            worst=min(variants,key=lambda v:v["aftertax_aud_vs_conservative_pct"])
            unmodified=cohort[cycle]["staged_reserve_variants"][label]
            summary[cycle+" | reserve "+label+"%"]={
                "stress_count":len(selected),
                "bad_outcomes_vs_conservative_count":sum(
                    x["aftertax_aud_vs_conservative_pct"]<0 for x in variants),
                "worst_aftertax_aud_vs_conservative_pct":worst["aftertax_aud_vs_conservative_pct"],
                "best_aftertax_aud_vs_conservative_pct":max(
                    x["aftertax_aud_vs_conservative_pct"] for x in variants),
                "max_cash_spent_before_low_pct_sale_proceeds":max(
                    x["spent_before_low_pct_of_net_sale_proceeds"] for x in variants),
                "unmodified_historic_aftertax_vs_hold_pct":unmodified["liquidated_aud_vs_hold_pct"],
                "unmodified_historic_deployment_pct":unmodified["net_sale_proceeds_reinvested_pct"],
                "worst_vs_uncapped_pct":min(
                    x["aftertax_aud_vs_uncapped_pct"] for x in variants),
                "best_vs_uncapped_pct":max(
                    x["aftertax_aud_vs_uncapped_pct"] for x in variants),
            }
    return {
        "study":"Research only: net realised BTC sale-proceeds cash reserve versus downside and foregone upside",
        "caps_pct":list(CAPS),
        "stress_counterfactual_not_historical":True,
        "normal_historical_cohort_comparisons":cohort,
        "stress_reserve_summary":summary,
        "stress_details":scenarios,
        "caveats":[
            "Static 25/40% net-sale reserves are research hypotheses, chosen after inspection of risks, not independently validated live recommendations.",
            "Synthetic BTC future prices decline 50-70% into delayed day1060 lows, and are NOT actual history or probability estimates.",
            "Historical, pre-shock BTC prices and strictly preceding dated AUD FX preserved; real FX could differ under shock.",
            "Cash reserves can hurt BTC holdings and growth in recoveries; report both baseline and normal unmodified historical outcomes.",
            "Two past cycles plus synthetic stress scenarios cannot establish a statistical 20/25% average buy-price error bound.",
            "Simplified 10/15% FIFO SMSF accumulation CGT and close-price fills; no actual pension phase or ASX:IBIT spreads/cost basis.",
            "No changes to Production V5.8.2, Research V5.9, Streamlit, daily ntfy, portfolio or broker.",
        ],
    }


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--output",type=Path)
    args=parser.parse_args()
    results=evaluate_cash_reserves(read_exported_history())
    for name,row in results["stress_reserve_summary"].items():
        print(json.dumps({"cycle_reserve":name,**row},sort_keys=True))
    if args.output:
        args.output.parent.mkdir(parents=True,exist_ok=True)
        args.output.write_text(json.dumps(results,indent=2))
        print("Full reserve sensitivity audit:",args.output)


if __name__=="__main__":
    main()
