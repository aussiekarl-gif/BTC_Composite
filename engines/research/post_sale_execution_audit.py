"""Supplement to execution_error_audit: post-sale, causally feasible hindsight windows.

This report compares each recorded SELL to the next recorded BUY, looking for
possible sell opportunities only after SELL starts and until BUY begins, and
possible rebuy opportunities only after SELL finishes until 26 observations
after BUY finishes. True future lows are used *only for audit*. The oracle
is NOT a trading algorithm or evidence any rule can predict those prices.

A valid ideal round trip must have its reference high before its reference low.
A censored pair is reported but excluded from the >=25% success denominator.
"""
import argparse
import json
import math

import numpy as np
import pandas as pd

from engines.research.full_cycle_reinvestment import validate_history
from engines.research.execution_error_audit import run_audit

TARGET = 0.25
FUTURE_REENTRY_LOOKAHEAD_WEEKS = 26


def score_roundtrips(data, plans, *, lookahead_weeks=26, threshold=TARGET):
    history = validate_history(data)
    if not isinstance(history.index, pd.DatetimeIndex):
        raise ValueError("DatetimeIndex required")
    if not isinstance(lookahead_weeks, int) or lookahead_weeks < 0:
        raise ValueError("Invalid lookahead")
    if not 0 <= threshold < 1:
        raise ValueError("Invalid threshold")
    price = history["btc_price_aud"].to_numpy(dtype=float)
    index_map = {str(t): i for i,t in enumerate(history.index)}
    report = []

    # Adjacent plan matching is fixed before observing outcomes; don't pick
    # the most successful sell or subsequent buy.
    for i in range(len(plans)-1):
        s, b = plans[i], plans[i+1]
        if s["side"] != "SELL" or b["side"] != "BUY":
            continue
        s_begin, s_end = index_map[s["start"]], index_map[s["end"]]
        b_begin, b_end = index_map[b["start"]], index_map[b["end"]]
        if not (s_begin <= s_end < b_begin <= b_end):
            raise ValueError("Plan dates overlap or are not sequential")
        hi_segment = price[s_begin:b_begin+1]  # opportunity to delay sale
        hi_pos = s_begin + int(np.argmax(hi_segment))
        lo_right = b_end + lookahead_weeks
        complete = (s["complete_plan"] and b["complete_plan"] and
                    lo_right < len(price))
        lo_right_clipped = min(lo_right, len(price)-1)
        lo_segment = price[s_end:lo_right_clipped+1]
        lo_pos = s_end + int(np.argmin(lo_segment))
        high = float(price[hi_pos])
        low = float(price[lo_pos])
        sell_vwap = float(s["execution_vwap_aud"])
        buy_vwap = float(b["execution_vwap_aud"])
        sell_error = max(0.0, 1.0 - sell_vwap/high)
        buy_error = max(0.0, buy_vwap/low - 1.0)
        valid_order = hi_pos <= lo_pos
        eligible = complete and valid_order
        report.append({
            "sell_start": s["start"], "sell_end": s["end"],
            "buy_start": b["start"], "buy_end": b["end"],
            "selling_vwap_aud": round(sell_vwap, 2),
            "buying_vwap_aud": round(buy_vwap, 2),
            "achievable_reference_high_aud": round(high, 2),
            "reference_high_date": str(history.index[hi_pos]),
            "achievable_reference_low_aud": round(low, 2),
            "reference_low_date": str(history.index[lo_pos]),
            "sell_error_pct": round(100*sell_error, 3),
            "buy_error_pct": round(100*buy_error, 3),
            "complete_lookahead": complete,
            "chronological_high_before_low": valid_order,
            "eligible": eligible,
            "both_within_25pct": bool(eligible and sell_error <= threshold and
                                      buy_error <= threshold),
        })
    eligible = [p for p in report if p["eligible"]]
    return {
        "all_matched_pairs": len(report),
        "eligible_pairs": len(eligible),
        "censored_or_chronologically_invalid": len(report)-len(eligible),
        "both_under_25pct": sum(p["both_within_25pct"] for p in eligible),
        "selling_under_25pct": sum(p["sell_error_pct"] <= 25 for p in eligible),
        "buying_under_25pct": sum(p["buy_error_pct"] <= 25 for p in eligible),
        "paired_results": report,
    }


def evaluate_pairs(data):
    scores = run_audit(data)
    output = {}
    for candidate in scores["candidates"]:
        output[candidate["candidate"]] = score_roundtrips(
            data, candidate["plans"])
    return {
        "research_only": True,
        "sample_start": scores["sample_start"],
        "sample_end": scores["sample_end"],
        "observations": scores["observations"],
        "reference": "Within actual post-sale cash-availability interval; fixed +26-week buy-lag audit",
        "results": output,
        "warnings": [
            "Uses the same historical simulated equal-tranche 12/16-week plans.",
            "True future extrema are NOT known when decisions are made.",
            "Oracle highs restricted to sell start through next buy start.",
            "Oracle lows restricted to sale end through buy end + 26 weekly observations.",
            "A reference high after low is excluded: no time-travel round trips.",
            "Unobserved 26-week future after buy completion is censored.",
            "This metric differs from the +/-52-week independent local-extrema metric.",
            "The 0.3% historical fee proxy applies, NOT 3 AUD per order, and no CGT.",
            "Existing risk-score time-of-availability is NOT independently validated.",
            "Do not infer forecast skill or deploy into Production.",
        ]
    }


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--output", default="")
    args=parser.parse_args()
    from engines.shared.central_data import load_master
    raw=load_master(columns=["btc_price_aud","risk_score"])
    numeric=raw[["btc_price_aud","risk_score"]].apply(pd.to_numeric,errors="coerce")
    valid=(np.isfinite(numeric["btc_price_aud"])
           & numeric["btc_price_aud"].gt(0)
           & np.isfinite(numeric["risk_score"])
           & numeric["risk_score"].between(0,1))
    result=evaluate_pairs(numeric.loc[valid])
    result["source_valid_rows"]=int(valid.sum())
    content=json.dumps(result,indent=2,allow_nan=False,
                       default=lambda value: value.item() if isinstance(value,np.generic) else str(value))
    if args.output:
        from pathlib import Path
        Path(args.output).write_text(content+"\n", encoding="utf-8")
    print(content)


if __name__=="__main__":
    main()
