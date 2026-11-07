"""Research-only same-window sell threshold audit: stored versus reconstructed risk.

The reconstructed series uses earlier weekly fit observations. Historical source
publication/revision provenance remains unverified; never promote based on this.
"""
import json
import numpy as np
import pandas as pd

from engines.shared.central_data import load_master
from engines.research.run_point_in_time_risk_comparison import causal_power_law
from engines.research.fixed_sell_sensitivity import fixed_threshold_matrix
from engines.research.sell_threshold_walkforward import expanding_walk_forward, _simulate


def compare(master):
    price = pd.to_numeric(master["btc_price_aud"], errors="coerce")
    stored = pd.to_numeric(master["risk_score"], errors="coerce")
    prices = price[(price > 0) & np.isfinite(price)].sort_index()
    causal = causal_power_law(prices).reindex(master.index)
    valid = ((price > 0) & np.isfinite(price) & stored.between(0, 1)
             & np.isfinite(stored) & np.isfinite(causal))
    if valid.sum() < 100:
        raise ValueError("Insufficient paired scores for meaningful comparison")
    base = pd.DataFrame({"btc_price_aud": price.loc[valid],
                         "risk_score": stored.loc[valid]}).sort_index()
    alternate = base.copy()
    alternate["risk_score"] = causal.loc[base.index]
    output = {"research_only": True, "rows": len(base),
              "start": str(base.index.min()), "end": str(base.index.max()),
              "stored": {}, "reconstructed": {},
              "warning": "Power Law only; historical input availability and revisions not independently verified"}
    for name, data in (("stored", base), ("reconstructed", alternate)):
        wf = expanding_walk_forward(data)
        fixed = fixed_threshold_matrix(data)
        selected = [x for x in wf["folds"] if x["cost_per_side"] == 0.003]
        fixed_rows = fixed["results"]
        full_window = {}
        for cost in (0.001, 0.003, 0.006):
            full_window[str(cost)] = [
                {"threshold": t, "result": _simulate(data, 500_000, t, cost)}
                for t in (0.55, 0.60, 0.65, 0.70, 0.75)
            ]
        output[name] = {"full_window_descriptive_not_holdout": full_window,
                        "sell_event_coverage": {
            "selected_baseline_folds_with_sells": sum(x["candidate_sell_count"] > 0 for x in selected),
            "selected_baseline_total_sells": sum(x["candidate_sell_count"] for x in selected),
            "fixed_threshold_sells_by_threshold": {
                str(t): sum(x["sell_count"] for x in fixed_rows
                            if x["cost_per_side"] == 0.003 and x["sell_threshold"] == t)
                for t in (0.55, 0.60, 0.65, 0.70, 0.75)
            },
            "warning": "Zero-event thresholds and folds cannot identify an optimal sell policy"
        }, "selected_thresholds": [
            {"fold": x["fold"], "threshold": x["sell_threshold"],
             "test_start": x["test_start"], "test_end": x["test_end"],
             "candidate_minus_hold_aud": x["candidate_minus_hold_aud"],
             "candidate_minus_baseline_aud": x["candidate_minus_baseline_aud"],
             "candidate_buy_count": x["candidate_buy_count"],
             "candidate_sell_count": x["candidate_sell_count"]}
            for x in wf["folds"] if x["cost_per_side"] == 0.003],
            "fixed_threshold_matrix": fixed}
    return output


if __name__ == "__main__":
    master = load_master(columns=["btc_price_aud", "risk_score"])
    print(json.dumps(compare(master), indent=2, allow_nan=False, default=str))
