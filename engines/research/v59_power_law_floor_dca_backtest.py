"""Matched V5.9 DCA backtest for alternative Power Law cheap floors.

Research-only. Same causal BTC/USD + prior FX weekly signal / next-Monday BTC/AUD
proxy execution as the existing V5.9 timing horse race. No live or Production writes.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

from engines.research import research_model as model
from engines.research.v59_causal_timing_horse_race import (
    CAPITAL_AUD,
    build_weekly_rows,
    cohort_windows,
    simulate,
)
from engines.research.v59_dynamic_risk_policy import BUY_POLICY_BANDS, risk_buy_multiplier
from engines.research.v59_live_signal_snapshot import live_risk_params


CANDIDATE_CHEAP_FLOORS = (-0.10, -0.20, -0.24, -0.25, -0.30, -0.31, -0.33, -0.35)
CASH_YIELDS = (0.0, 0.05)
# 100% reproduces the unconstrained timing study; 5% is the ordinary weekly cap.
WEEKLY_CAP_FRACTIONS = (1.0, 0.05)
EXPENSIVE_FLOOR = model.DEFAULT_PL_EXPENSIVE
TAIL_STRETCHED_VARIANTS = {
    # 10x is reserved for the deepest tail; moderate undervaluation retains
    # more buying weight. All variants preserve the no-buy boundary at +0.02.
    "tail_stretched_aggressive": (
        (-0.32, 0.00), (-0.31, 0.01), (-0.30, 0.02), (-0.25, 0.05),
        (-0.10, 0.05), (-0.04, 0.20), (0.02, 0.40), (0.20, 1.00),
    ),
    "tail_stretched_3x_mid": (
        (-0.32, 0.00), (-0.31, 0.01), (-0.30, 0.02), (-0.25, 0.03),
        (-0.10, 0.049), (-0.04, 0.20), (0.02, 0.40), (0.20, 1.00),
    ),
    "tail_stretched_balanced": (
        (-0.32, 0.00), (-0.31, 0.01), (-0.30, 0.02), (-0.25, 0.05),
        (-0.10, 0.10), (-0.04, 0.25), (0.02, 0.40), (0.20, 1.00),
    ),
    "tail_stretched_conservative": (
        (-0.32, 0.00), (-0.31, 0.01), (-0.30, 0.02), (-0.25, 0.05),
        (-0.10, 0.20), (-0.04, 0.30), (0.02, 0.40), (0.20, 1.00),
    ),
    # Boundary sensitivity: reserve zero-risk/10x for unusually deep residuals.
    "tail_stretched_deep_floor": (
        (-0.40, 0.00), (-0.35, 0.01), (-0.30, 0.02), (-0.25, 0.05),
        (-0.20, 0.10), (-0.10, 0.20), (0.02, 0.40), (0.20, 1.00),
    ),
    "tail_stretched_mid_floor": (
        (-0.35, 0.00), (-0.32, 0.01), (-0.30, 0.02), (-0.25, 0.05),
        (-0.20, 0.10), (-0.10, 0.20), (0.02, 0.40), (0.20, 1.00),
    ),
}


def main() -> None:
    now = datetime.now(timezone.utc)
    start = model.RESEARCH_PL_HISTORY_START.to_pydatetime()
    btc = model.fetch_btc_history(start, now)
    fx = model.fetch_aud_usd_rates(start, now)
    if btc is None or btc.empty or fx is None or fx.empty:
        raise RuntimeError("BTC or historical AUD/USD FX unavailable; no synthetic fallback")

    priced = model.merge_bgeometrics(btc.copy(), pd.DataFrame())
    scored = model.add_risk_indicators(priced, "Research WF Power Law", live_risk_params())
    if "power_law_residual" not in scored or "risk_score" not in scored:
        raise RuntimeError("Required V5.9 walk-forward risk/residual columns missing")

    # Prove the −0.10 candidate exactly reproduces the current score before
    # comparing alternative cheap floors.
    residual = pd.to_numeric(scored["power_law_residual"], errors="coerce")
    current_score = pd.to_numeric(scored["risk_score"], errors="coerce")
    reconstructed = ((residual - model.DEFAULT_PL_CHEAP) /
                     (EXPENSIVE_FLOOR - model.DEFAULT_PL_CHEAP)).clip(0.0, 1.0)
    aligned = current_score.notna() & reconstructed.notna()
    max_diff = float((current_score.loc[aligned] - reconstructed.loc[aligned]).abs().max())
    if not np.isfinite(max_diff) or max_diff > 1e-9:
        raise AssertionError(f"−0.10 reconstruction did not match live R2 score: {max_diff}")

    results = []
    cohort_anchors = None
    mappings = [
        (f"linear_floor_{cheap:.2f}", cheap, None)
        for cheap in CANDIDATE_CHEAP_FLOORS
    ] + [
        (name, None, knots)
        for name, knots in TAIL_STRETCHED_VARIANTS.items()
    ]

    mapping_bucket_counts = {}
    for mapping_name, cheap, knots in mappings:
        candidate = scored.copy()
        residual_values = pd.to_numeric(candidate["power_law_residual"], errors="coerce")
        if cheap is not None:
            candidate["risk_score"] = (
                (residual_values - cheap) / (EXPENSIVE_FLOOR - cheap)
            ).clip(0.0, 1.0)
        else:
            # Candidate nonlinear mapping: only the deepest residual tail gets
            # the 10x/5x bands. Above −0.10 the ordinary risk scale is stretched
            # while preserving the existing no-buy boundary at residual +0.02.
            valid = residual_values.notna()
            candidate["risk_score"] = np.nan
            xp = np.array([x for x, _ in knots], dtype=float)
            fp = np.array([y for _, y in knots], dtype=float)
            candidate.loc[valid, "risk_score"] = np.interp(
                residual_values.loc[valid].to_numpy(), xp, fp
            )
        # Keep the validated source label; candidates transform the same causal
        # WF residual, not a fallback risk series.
        candidate["risk_score_source"] = "Walk-forward Power Law"
        rows = build_weekly_rows(candidate, fx)
        weekly_distribution = model.risk_occurrence_table([row["risk_score"] for row in rows])
        weekly_by_bucket = weekly_distribution.set_index("Risk range")
        multiplier_counts_by_ladder = {}
        for ladder_name, ladder_bands in BUY_POLICY_BANDS.items():
            multiplier_counts = {}
            for row in rows:
                multiplier = risk_buy_multiplier(float(row["risk_score"]), bands=ladder_bands)
                key = f"{multiplier:g}x"
                multiplier_counts[key] = multiplier_counts.get(key, 0) + 1
            multiplier_counts_by_ladder[ladder_name] = dict(sorted(
                multiplier_counts.items(), key=lambda item: float(item[0][:-1]), reverse=True
            ))
        mapping_bucket_counts[mapping_name] = {
            "weekly_observations": len(rows),
            "lowest_bucket_weeks": int(weekly_by_bucket.loc["0.00–0.01", "Weeks"]),
            "lowest_bucket_percent": float(weekly_by_bucket.loc["0.00–0.01", "Percent"]),
            "second_bucket_weeks": int(weekly_by_bucket.loc["0.01–0.02", "Weeks"]),
            "second_bucket_percent": float(weekly_by_bucket.loc["0.01–0.02", "Percent"]),
            "buy_multiplier_counts_by_ladder": multiplier_counts_by_ladder,
        }
        windows = cohort_windows(rows)
        anchors = [w["anchor"] for w in windows]
        if cohort_anchors is None:
            cohort_anchors = anchors
        elif anchors != cohort_anchors:
            raise AssertionError("Candidate mappings changed the matched cohort sample")

        for w in windows:
            for cash_yield in CASH_YIELDS:
                for weekly_cap_fraction in WEEKLY_CAP_FRACTIONS:
                    for buy_ladder_name, buy_bands in BUY_POLICY_BANDS.items():
                        baseline = simulate(
                            w["rows"], policy="plain_1x", cash_yield=cash_yield,
                            reserve_fraction=0.0, capital=CAPITAL_AUD,
                            review_date=w["review_date"], max_fraction=weekly_cap_fraction,
                        )
                        candidate_result = simulate(
                            w["rows"], policy="plain_1x", cash_yield=cash_yield,
                            reserve_fraction=0.0, capital=CAPITAL_AUD,
                            review_date=w["review_date"], max_fraction=weekly_cap_fraction,
                            weight_fn=lambda row, bands=buy_bands: risk_buy_multiplier(
                                float(row["risk_score"]), bands=bands
                            ),
                        )
                        results.append({
                            "mapping_name": mapping_name,
                            "candidate_cheap_floor": cheap,
                            "anchor": w["anchor"],
                            "start": w["start"],
                            "end": w["end"],
                            "split": w["split"],
                            "cash_yield": cash_yield,
                            "weekly_cap_fraction": weekly_cap_fraction,
                            "buy_ladder_name": buy_ladder_name,
                        "baseline_policy": "fixed_1x",
                        "candidate_policy": f"{buy_ladder_name}_ladder_on_remapped_risk",
                        "equity_uplift_vs_fixed_1x_pct": (
                            100.0 * (candidate_result["equity_aud"] / baseline["equity_aud"] - 1.0)
                        ),
                        "btc_equivalent_uplift_vs_fixed_1x_pct": (
                            100.0 * (
                                candidate_result["terminal_btc_equivalent"]
                                / baseline["terminal_btc_equivalent"] - 1.0
                            )
                        ),
                        "btc_units": candidate_result["btc_units"],
                        "terminal_btc_equivalent": candidate_result["terminal_btc_equivalent"],
                        "equity_aud": candidate_result["equity_aud"],
                        "cash_aud": candidate_result["cash_aud"],
                        "net_invested_aud": candidate_result["net_invested_aud"],
                        "deployed_fraction_of_initial": candidate_result["deployed_fraction_of_initial"],
                        "drawdown_pct": candidate_result["drawdown_pct"],
                        "buy_count": candidate_result["buy_count"],
                        "spent_first_26weeks_pct_initial": (
                            100.0 * candidate_result["spent_first_26weeks_pct_initial"]
                        ),
                    })

    summaries = []
    for mapping_name, cheap, knots in mappings:
        for split in ("TRAIN", "HISTORICAL_HOLDOUT"):
            for cash_yield in CASH_YIELDS:
                for weekly_cap_fraction in WEEKLY_CAP_FRACTIONS:
                    for buy_ladder_name in BUY_POLICY_BANDS:
                        selected = [
                        r for r in results
                        if r["mapping_name"] == mapping_name
                        and r["split"] == split
                        and r["cash_yield"] == cash_yield
                        and r["weekly_cap_fraction"] == weekly_cap_fraction
                        and r["buy_ladder_name"] == buy_ladder_name
                        ]
                        if not selected:
                        continue
                        summaries.append({
                        "mapping_name": mapping_name,
                        "candidate_cheap_floor": cheap,
                        "risk_distribution": mapping_bucket_counts[mapping_name],
                        "split": split,
                        "cash_yield": cash_yield,
                        "weekly_cap_fraction": weekly_cap_fraction,
                        "buy_ladder_name": buy_ladder_name,
                        "cohorts": len(selected),
                        "median_equity_uplift_vs_fixed_1x_pct": float(np.median([
                        r["equity_uplift_vs_fixed_1x_pct"] for r in selected
                        ])),
                        "worst_equity_uplift_vs_fixed_1x_pct": min(
                        r["equity_uplift_vs_fixed_1x_pct"] for r in selected
                        ),
                        "equity_win_fraction": sum(
                        r["equity_uplift_vs_fixed_1x_pct"] > 0 for r in selected
                        ) / len(selected),
                        "median_btc_equivalent_uplift_vs_fixed_1x_pct": float(np.median([
                        r["btc_equivalent_uplift_vs_fixed_1x_pct"] for r in selected
                        ])),
                        "worst_btc_equivalent_uplift_vs_fixed_1x_pct": min(
                        r["btc_equivalent_uplift_vs_fixed_1x_pct"] for r in selected
                        ),
                        "median_deployed_fraction": float(np.median([
                        r["deployed_fraction_of_initial"] for r in selected
                        ])),
                        "median_drawdown_pct": float(np.median([
                        r["drawdown_pct"] for r in selected
                        ])),
                        "median_buy_count": float(np.median([r["buy_count"] for r in selected])),
                        "median_first_26w_spend_pct_initial": float(np.median([
                        r["spent_first_26weeks_pct_initial"] for r in selected
                        ])),
                        })
                        
                        report = {
                        "status": "RESEARCH_ONLY_MATCHED_COHORT_THRESHOLD_BACKTEST",
        "generated_at_utc": now.isoformat(),
        "btc_history_first_last": [str(btc.index.min()), str(btc.index.max())],
        "fx_history_first_last": [str(fx.index.min()), str(fx.index.max())],
        "starting_capital_aud": CAPITAL_AUD,
        "cohort_weeks": 104,
        "completed_cohorts": len(cohort_anchors or []),
        "cohort_anchors": cohort_anchors,
        "cash_yield_scenarios": CASH_YIELDS,
        "protected_reserve_fraction": 0.0,
        "weekly_cap_fractions": WEEKLY_CAP_FRACTIONS,
        "entry_cost_fraction": 0.003,
        "flat_fee_aud": 3.0,
        "illustrative_annual_etf_drag": 0.0025,
        "candidate_cheap_floors": CANDIDATE_CHEAP_FLOORS,
        "piecewise_tail_stretched_variants": TAIL_STRETCHED_VARIANTS,
        "risk_bucket_counts_by_mapping": mapping_bucket_counts,
        "expensive_floor": EXPENSIVE_FLOOR,
        "current_score_reconstruction_max_abs_difference": max_diff,
        "signal_execution": "Prior Sunday UTC risk; next Monday BTC/AUD spot proxy execution",
        "buy_ladders_compared": {
            name: [[float(ceiling), float(multiplier)] for ceiling, multiplier in bands]
            for name, bands in BUY_POLICY_BANDS.items()
        },
        "results_vs_fixed_1x": summaries,
        "cohort_results": results,
        "caveats": [
            "Retrospective public BTC/USD and AUD/USD data; provider publication vintages are not attested.",
            "Historical holdout cohorts are not truly untouched because model research has examined these cycles.",
            "Jan/Jul 104-week cohorts overlap and are not independent cycle observations.",
            "BTC/AUD spot proxy only; no executable ASX:IBIT fills, tracking, spreads or market-hours effects.",
            "5% cash yield and 0.25% annual ETF drag are illustrative assumptions, not guaranteed returns.",
            "No taxes, AAA distributions, personal cash constraints or live portfolio data are modelled.",
            "No claim of optimality or live-trading authorisation.",
        ],
        "safety": {
            "changes_live_model": False,
            "changes_dca_sizing": False,
            "changes_production": False,
            "portfolio_or_order_writes": False,
            "notifications_sent": False,
        },
    }
    output = Path("artifacts/v59_power_law_floor_dca_backtest.json")
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2, default=str, allow_nan=False) + "\n", encoding="utf-8")
    print(json.dumps({
        "status": report["status"],
        "completed_cohorts": report["completed_cohorts"],
        "score_reconstruction_max_abs_difference": max_diff,
        "summary_rows": len(summaries),
        "output": str(output),
    }, indent=2))


if __name__ == "__main__":
    main()
