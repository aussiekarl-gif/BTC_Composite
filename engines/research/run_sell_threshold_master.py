"""Run read-only historical threshold audits on the central BTC research master.

This script does not place orders, update the master, access portfolios, or
promote models. Print only aggregate diagnostics; the master remains private.
Usage (requires read access to btc-audit-data):
    python -m engines.research.run_sell_threshold_master
"""
import json
import numpy as np
import pandas as pd

from engines.shared.central_data import load_master
from engines.research.sell_threshold_robustness import run_probe
from engines.research.sell_threshold_walkforward import expanding_walk_forward
from engines.research.fixed_sell_sensitivity import fixed_threshold_matrix


def main():
    master = load_master(columns=["btc_price_aud", "risk_score", "risk_score_source"])
    raw_rows = len(master)
    valid = master[["btc_price_aud", "risk_score"]].apply(
        pd.to_numeric, errors="coerce")
    mask = (
        np.isfinite(valid["btc_price_aud"])
        & (valid["btc_price_aud"] > 0)
        & np.isfinite(valid["risk_score"])
        & valid["risk_score"].between(0, 1)
    )
    if int(mask.sum()) < 100:
        raise ValueError("Fewer than 100 valid historical price-risk observations")
    data = valid.loc[mask].copy().sort_index()
    if data.index.has_duplicates:
        raise ValueError("Duplicate historical timestamps")
    if not data.index.is_monotonic_increasing:
        raise ValueError("Dates must be ascending")
    # Explicitly report missing-week issues rather than making weekly claims.
    gaps = data.index.to_series().diff().dropna().dt.days
    sources = (master.loc[mask, "risk_score_source"]
               .fillna("unknown").astype(str).value_counts().to_dict())

    split = run_probe(data)
    rolling = expanding_walk_forward(data)
    sensitivity = fixed_threshold_matrix(data)
    summary = {
        "research_only": True,
        "raw_master_rows": raw_rows,
        "valid_price_risk_pairs": len(data),
        "valid_start": str(data.index.min()),
        "valid_end": str(data.index.max()),
        "risk_sources": sources,
        "largest_interval_days": int(gaps.max()) if len(gaps) else None,
        "intervals_over_8_days": int((gaps > 8).sum()),
        "single_holdout": {
            "train_start": split["train_start"],
            "train_end": split["train_end"],
            "holdout_start": split["holdout_start"],
            "holdout_end": split["holdout_end"],
            "selected_threshold": split["selected_sell_threshold"],
            "scenarios": split["holdout_scenarios"],
        },
        "fixed_threshold_sensitivity": sensitivity,
        "expanding_walk_forward": {
            "fold_count": rolling["fold_count"],
            "summary_by_cost": rolling["summary_by_cost"],
            "folds": rolling["folds"],
        },
        "warnings": [
            "Historical risk-score causality is NOT established by this audit.",
            "No reinvestment interest, tax, order-book impact or exchange limits.",
            "Results are independent fresh-capital folds, not a compounded portfolio.",
            "Threshold choice must remain Research-only pending validation."
        ],
    }
    print(json.dumps(summary, indent=2, allow_nan=False))


if __name__ == "__main__":
    main()
