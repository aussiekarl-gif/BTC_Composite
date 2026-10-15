#!/usr/bin/env python3
"""Research-only prefix-invariance test for the causal Power Law reconstruction.

For sampled cutoffs, the score calculated using the full available price history
must match the score at the same timestamp when calculation is limited to that
prefix. This tests future-data dependence in this reconstruction only; it does
not certify the stored composite or external indicator publication timestamps.
"""
from __future__ import annotations
import json
import math
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import numpy as np
import pandas as pd
from engines.shared.central_data import load_master

GENESIS = pd.Timestamp("2009-01-03", tz="UTC")
REFIT_DAYS = 91
MIN_WEEKS = 52
CHEAP = -0.10
EXPENSIVE = 0.20


def causal_power_law(prices: pd.Series) -> pd.Series:
    prices = pd.to_numeric(prices, errors="coerce").astype(float).sort_index()
    out = pd.Series(np.nan, index=prices.index, dtype=float)
    last_fit = None
    slope = intercept = np.nan
    for ts in prices.index:
        if last_fit is None or (ts - last_fit).days >= REFIT_DAYS:
            hist = prices.loc[prices.index < ts].dropna()
            weekly = hist.resample("W-MON").last().dropna()
            days = np.array([(x - GENESIS).days for x in weekly.index], dtype=float)
            vals = weekly.to_numpy(float)
            ok = (days > 0) & np.isfinite(vals) & (vals > 0)
            if int(ok.sum()) >= MIN_WEEKS:
                slope, intercept = np.polyfit(np.log10(days[ok]), np.log10(vals[ok]), 1)
                last_fit = ts
        px = prices.loc[ts]
        days_now = (ts - GENESIS).days
        if np.isfinite(slope) and np.isfinite(intercept) and pd.notna(px) and px > 0 and days_now > 0:
            residual = math.log10(float(px)) - (float(slope) * math.log10(days_now) + float(intercept))
            out.loc[ts] = float(np.clip((residual - CHEAP) / (EXPENSIVE - CHEAP), 0, 1))
    return out


def main() -> None:
    data = load_master(columns=["btc_price_aud"])
    price = pd.to_numeric(data["btc_price_aud"], errors="coerce")
    price = price[np.isfinite(price) & (price > 0)].sort_index()
    if len(price) < 100:
        raise RuntimeError(f"Insufficient valid price observations: {len(price)}")

    full = causal_power_law(price)
    # Test 20 chronological cutoffs from the early eligible region through the end.
    candidate_positions = np.linspace(max(80, len(price) // 5), len(price) - 1, 20, dtype=int)
    checks = []
    for pos in sorted(set(int(x) for x in candidate_positions)):
        prefix = price.iloc[:pos + 1]
        prefix_scores = causal_power_law(prefix)
        ts = prefix.index[-1]
        a, b = full.loc[ts], prefix_scores.loc[ts]
        both_nan = pd.isna(a) and pd.isna(b)
        diff = 0.0 if both_nan else (float(abs(a - b)) if pd.notna(a) and pd.notna(b) else None)
        checks.append({"cutoff": ts.isoformat(), "full_history_score": None if pd.isna(a) else float(a),
                       "prefix_only_score": None if pd.isna(b) else float(b), "absolute_difference": diff,
                       "both_unavailable": bool(both_nan)})
    comparable = [x["absolute_difference"] for x in checks if x["absolute_difference"] is not None]
    max_diff = max(comparable, default=0.0)
    mismatches = [x for x in checks if x["absolute_difference"] is None or x["absolute_difference"] > 1e-12]
    output = {
        "test": "causal_power_law_prefix_invariance",
        "dataset": {"valid_price_rows": int(len(price)), "start": price.index.min().isoformat(),
                    "end": price.index.max().isoformat()},
        "method": {"sampled_cutoffs": len(checks), "refit_days": REFIT_DAYS, "minimum_weekly_observations": MIN_WEEKS,
                   "tolerance": 1e-12},
        "result": {"passed": len(mismatches) == 0, "cutoffs_with_mismatch": len(mismatches),
                   "maximum_absolute_difference": max_diff, "checks": checks},
        "limitations": [
            "Tests only this reconstructed Power Law function, not the full risk composite.",
            "Does not prove stored risk_score inputs or external indicator values were historically available.",
            "Uses current central-master price history; provenance and any historical revisions are outside this test."
        ]
    }
    print(json.dumps(output, indent=2, allow_nan=False, default=str))
    if mismatches:
        raise SystemExit("Prefix-invariance test failed; see reported cutoffs.")


if __name__ == "__main__":
    main()
