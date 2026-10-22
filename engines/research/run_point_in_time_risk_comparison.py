#!/usr/bin/env python3
"""Compare stored risk scores with a causal, point-in-time Power Law reconstruction.

Research-only. Reads the audit master without modifying it. The reconstructed score
fits log-price ~ log(days since genesis) using only weekly closes strictly before
each decision date, refitting every 91 days after at least 52 weekly observations.
"""
from __future__ import annotations
import json, math, sys
from pathlib import Path
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
from engines.shared.central_data import load_master

CAPITAL = 500_000.0
FEE = 0.001
GENESIS = pd.Timestamp("2009-01-03", tz="UTC")
THRESHOLDS = (0.15, 0.25, 0.35, 0.45, 0.55)
MULTIPLIER = 3.0


def causal_power_law(prices: pd.Series) -> pd.Series:
    prices = pd.to_numeric(prices, errors="coerce").astype(float).sort_index()
    out = pd.Series(np.nan, index=prices.index, dtype=float)
    last_fit = None
    slope = intercept = np.nan
    for ts in prices.index:
        if last_fit is None or (ts - last_fit).days >= 91:
            hist = prices.loc[prices.index < ts].dropna()
            weekly = hist.resample("W-MON").last().dropna()
            days = np.array([(x - GENESIS).days for x in weekly.index], dtype=float)
            vals = weekly.to_numpy(float)
            ok = (days > 0) & np.isfinite(vals) & (vals > 0)
            if int(ok.sum()) >= 52:
                slope, intercept = np.polyfit(np.log10(days[ok]), np.log10(vals[ok]), 1)
                last_fit = ts
        px = prices.loc[ts]
        days_now = (ts - GENESIS).days
        if np.isfinite(slope) and np.isfinite(intercept) and pd.notna(px) and px > 0 and days_now > 0:
            residual = math.log10(float(px)) - (float(slope) * math.log10(days_now) + float(intercept))
            out.loc[ts] = float(np.clip((residual + 0.10) / 0.30, 0, 1))
    return out


def run_strategy(data: pd.DataFrame, score_col: str, threshold: float, multiplier: float = MULTIPLIER):
    scores = pd.to_numeric(data[score_col], errors="coerce").shift(1).to_numpy(float)
    prices = data["btc_price_aud"].to_numpy(float)
    n = len(data)
    installment = CAPITAL / n
    cash = CAPITAL
    btc = fees = spent = 0.0
    buys = 0
    for px, score in zip(prices, scores):
        if np.isfinite(score) and score < threshold and cash > 0:
            strength = (threshold - score) / threshold
            gross = min(cash, installment * multiplier * strength)
            if gross >= 100:
                fee = gross * FEE
                btc += gross * (1 - FEE) / px
                cash -= gross
                spent += gross
                fees += fee
                buys += 1
    equity = cash + btc * prices[-1]
    return {"threshold": threshold, "ending_equity_aud": equity, "return_pct": (equity / CAPITAL - 1) * 100,
            "btc_held": btc, "cash_remaining_aud": cash, "gross_spent_aud": spent, "fees_aud": fees, "buys": buys}


def main():
    raw = load_master(columns=["btc_price_aud", "risk_score"])
    raw["btc_price_aud"] = pd.to_numeric(raw["btc_price_aud"], errors="coerce")
    raw["risk_score"] = pd.to_numeric(raw["risk_score"], errors="coerce")
    raw = raw.sort_index()
    price = raw.loc[np.isfinite(raw["btc_price_aud"]) & (raw["btc_price_aud"] > 0), "btc_price_aud"]
    reconstructed = causal_power_law(price)
    raw["reconstructed_risk_score"] = reconstructed.reindex(raw.index)
    valid = raw[np.isfinite(raw["btc_price_aud"]) & (raw["btc_price_aud"] > 0)
                & np.isfinite(raw["risk_score"]) & raw["risk_score"].between(0, 1)].copy()
    valid["reconstructed_risk_score"] = raw["reconstructed_risk_score"].reindex(valid.index)
    # Compare on identical price/risk dates, keeping reconstructed score availability explicit.
    paired = valid[np.isfinite(valid["reconstructed_risk_score"])].copy()
    if len(paired) < 20:
        raise RuntimeError(f"Only {len(paired)} paired stored/reconstructed scores available")
    corr = float(paired["risk_score"].corr(paired["reconstructed_risk_score"]))
    mae = float((paired["risk_score"] - paired["reconstructed_risk_score"]).abs().mean())
    rmse = float(np.sqrt(((paired["risk_score"] - paired["reconstructed_risk_score"]) ** 2).mean()))
    results = []
    for threshold in THRESHOLDS:
        a = run_strategy(paired, "risk_score", threshold)
        b = run_strategy(paired, "reconstructed_risk_score", threshold)
        results.append({"threshold": threshold, "stored_score": a, "causal_reconstructed_score": b,
                        "equity_difference_reconstructed_minus_stored_aud": b["ending_equity_aud"] - a["ending_equity_aud"],
                        "btc_difference_reconstructed_minus_stored": b["btc_held"] - a["btc_held"]})
    result = {
        "dataset": {"paired_rows": len(paired), "start": paired.index.min().isoformat(), "end": paired.index.max().isoformat(),
                    "capital_aud": CAPITAL, "fee_per_side_pct": FEE * 100,
                    "reconstructed_score_coverage_pct_of_stored_valid": len(paired) / len(valid) * 100},
        "score_comparison": {"correlation": corr, "mae": mae, "rmse": rmse,
                             "stored_score_mean": float(paired["risk_score"].mean()),
                             "reconstructed_score_mean": float(paired["reconstructed_risk_score"].mean())},
        "strategy_results": results,
        "benchmarks": {
            "fixed_dca": "Equal gross installment at every paired observation, fees deducted from invested amount.",
            "buy_and_hold": "All capital invested at the first paired observation, fees deducted from invested amount."
        },
        "limitations": [
            "This reconstructs only the causal Power Law risk score, not the full multi-component production composite.",
            "The reconstruction uses BTC prices available in the master; price revision/provenance and historical timestamp availability are not independently verified.",
            "Signals are shifted by one paired observation before execution. Fee is included; spread, slippage, tax, and terminal liquidation costs are excluded.",
            "Each threshold is a diagnostic comparison, not an optimised or deployable rule."
        ]
    }
    # Benchmarks use same paired window.
    prices = paired["btc_price_aud"].to_numpy(float)
    n = len(paired); installment = CAPITAL / n
    fixed_btc = float(np.sum(installment * (1-FEE) / prices))
    hold_btc = CAPITAL * (1-FEE) / prices[0]
    result["benchmarks"]["fixed_dca_btc"] = fixed_btc
    result["benchmarks"]["fixed_dca_ending_equity_aud"] = fixed_btc * prices[-1]
    result["benchmarks"]["buy_and_hold_btc"] = hold_btc
    result["benchmarks"]["buy_and_hold_ending_equity_aud"] = hold_btc * prices[-1]
    print("POINT-IN-TIME RISK RECONSTRUCTION COMPARISON")
    print(json.dumps(result, indent=2, allow_nan=False, default=str))

if __name__ == "__main__":
    main()
