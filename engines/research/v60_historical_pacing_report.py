"""Historical V6.0 cumulative-spending pace study with matched budgets.

Uses the same archived BTC/FX sources and rolling 104-week cohorts as the
primary V6.0 replay. Each dynamic policy is compared with fixed weekly DCA
under the SAME reserve, cash-yield and cumulative-spend cap. Research only.
"""
from __future__ import annotations

import argparse
from datetime import date
import json
from pathlib import Path

import pandas as pd

from engines.research.v60_200wma_backtest import (
    build_weekly_execution_rows, simulate_weekly_cohort, COHORT_WEEKS,
)
from engines.research.v60_historical_report import (
    load_btc_daily, fetch_usd_per_aud, assign_validation_split,
)

ROOT = Path(__file__).resolve().parents[2]
HOLDOUT_START = date(2022, 1, 1)
CASH_YIELDS = (0.0, 0.05)
CASH_FLOORS = (0.0, 30.0)
CUMULATIVE_CAPS = (None, 40.0, 50.0, 60.0, 70.0)
DYNAMIC_POLICIES = (
    ("measured", "20_25_30"),
    ("measured", "10_15_20"),
    ("stepped", "20_25_30"),
)


def _cap_key(value) -> str:
    return "uncapped" if pd.isna(value) else f"{float(value):.0f}%"


def build_pacing_results(weekly_rows: list[dict]) -> pd.DataFrame:
    if len(weekly_rows) < COHORT_WEEKS:
        raise ValueError("Insufficient weekly observations for 104-week cohorts")
    output = []
    for start in range(len(weekly_rows) - COHORT_WEEKS + 1):
        cohort = weekly_rows[start:start + COHORT_WEEKS]
        for cash_yield in CASH_YIELDS:
            for floor in CASH_FLOORS:
                for cap in CUMULATIVE_CAPS:
                    common = {
                        "cash_yield": cash_yield,
                        "protected_cash_floor_pct_initial_cash": floor,
                        "max_cumulative_buy_spend_pct_initial_cash": cap,
                    }
                    fixed = simulate_weekly_cohort(
                        cohort, policy="fixed_weekly", cash_yield=cash_yield,
                        protected_cash_floor_pct_initial_cash=floor,
                        max_cumulative_buy_spend_pct_initial_cash=cap,
                        threshold_set="none",
                    )
                    fixed.update(common)
                    fixed["split"] = assign_validation_split(fixed)
                    fixed["policy_label"] = "fixed_weekly"
                    output.append(fixed)

                    baseline = simulate_weekly_cohort(
                        cohort, policy="baseline", cash_yield=cash_yield,
                        protected_cash_floor_pct_initial_cash=floor,
                        max_cumulative_buy_spend_pct_initial_cash=cap,
                        threshold_set="none",
                    )
                    baseline.update(common)
                    baseline["split"] = assign_validation_split(baseline)
                    baseline["policy_label"] = "baseline"
                    output.append(baseline)

                    for policy, threshold_set in DYNAMIC_POLICIES:
                        thresholds = (20.0, 25.0, 30.0) if threshold_set == "20_25_30" else (10.0, 15.0, 20.0)
                        result = simulate_weekly_cohort(
                            cohort, policy=policy, cash_yield=cash_yield,
                            protected_cash_floor_pct_initial_cash=floor,
                            max_cumulative_buy_spend_pct_initial_cash=cap,
                            thresholds=thresholds, threshold_set=threshold_set,
                        )
                        result.update(common)
                        result["split"] = assign_validation_split(result)
                        result["policy_label"] = f"{policy}_{threshold_set}"
                        output.append(result)
    return pd.DataFrame(output)


def summarise_pacing(frame: pd.DataFrame) -> pd.DataFrame:
    if frame.empty:
        raise ValueError("No pacing results supplied")
    primary = frame.loc[frame["split"].isin(["train", "holdout"])].copy()
    fixed_rows = primary.loc[primary["policy"] == "fixed_weekly"]
    fixed_index = {
        (
            str(r.cohort_start), float(r.cash_yield),
            float(r.protected_cash_floor_pct_initial_cash), _cap_key(r.max_cumulative_buy_spend_pct_initial_cash),
        ): r
        for r in fixed_rows.itertuples(index=False)
    }
    summaries = []
    for label, group in primary.loc[primary["policy"] != "fixed_weekly"].groupby(
        ["split", "cash_yield", "protected_cash_floor_pct_initial_cash",
         "max_cumulative_buy_spend_pct_initial_cash", "policy_label"],
        dropna=False,
    ):
        split, cash_yield, floor, cap, policy_label = label
        peers = []
        for row in group.itertuples(index=False):
            key = (str(row.cohort_start), float(cash_yield), float(floor), _cap_key(cap))
            if key not in fixed_index:
                raise ValueError(f"Missing matched fixed-DCA cohort: {key}")
            peers.append(fixed_index[key])
        equity_uplifts = [
            100.0 * (float(r.final_equity_aud) / float(p.final_equity_aud) - 1.0)
            for r, p in zip(group.itertuples(index=False), peers)
        ]
        btc_uplifts = [
            100.0 * (float(r.btc_held) / float(p.btc_held) - 1.0)
            for r, p in zip(group.itertuples(index=False), peers)
        ]
        spend_differences = [
            100.0 * (float(r.total_buy_spend_aud) / float(p.total_buy_spend_aud) - 1.0)
            if float(p.total_buy_spend_aud) > 0 else 0.0
            for r, p in zip(group.itertuples(index=False), peers)
        ]
        summaries.append({
            "split": split,
            "cash_yield_annual_pct": 100.0 * float(cash_yield),
            "protected_cash_floor_pct_initial_cash": float(floor),
            "cumulative_spend_cap_pct_initial_cash": _cap_key(cap),
            "policy": policy_label,
            "cohort_count": int(len(group)),
            "median_final_equity_uplift_vs_matched_fixed_pct": float(pd.Series(equity_uplifts).median()),
            "median_btc_uplift_vs_matched_fixed_pct": float(pd.Series(btc_uplifts).median()),
            "cohort_win_rate_final_equity_pct": 100.0 * sum(x > 0 for x in equity_uplifts) / len(equity_uplifts),
            "cohort_win_rate_btc_pct": 100.0 * sum(x > 0 for x in btc_uplifts) / len(btc_uplifts),
            "median_spend_difference_vs_matched_fixed_pct": float(pd.Series(spend_differences).median()),
            "median_policy_total_spend_aud": float(group["total_buy_spend_aud"].median()),
            "median_fixed_count_buy_count": float(group["buy_count"].median()),
            "median_cash_remaining_aud": float(group["cash_remaining_aud"].median()),
            "median_max_drawdown_pct": float(group["max_drawdown_pct"].median()),
            "median_same_spend_same_count_timing_uplift_pct_hindsight": float(
                group["same_spend_same_count_btc_timing_uplift_pct_hindsight"].median()
            ),
            "cohorts_overlap": True,
            "interpretation": "Matched starting capital, reserve, yield and cumulative-spend cap; overlapping cohorts are not independent.",
        })
    return pd.DataFrame(summaries).sort_values(
        ["split", "cash_yield_annual_pct", "protected_cash_floor_pct_initial_cash",
         "cumulative_spend_cap_pct_initial_cash", "policy"]
    ).reset_index(drop=True)


def build_report(output_dir: Path) -> dict:
    btc, btc_hash, btc_end = load_btc_daily()
    fx_start = date(2016, 1, 1)
    fx_end = pd.Timestamp(btc.index[-1]).date()
    fx, fx_hash = fetch_usd_per_aud(fx_start, fx_end)
    weekly = build_weekly_execution_rows(btc, fx, first_execution_date=date(2017, 1, 1))
    results = build_pacing_results(weekly)
    summary = summarise_pacing(results)
    output_dir.mkdir(parents=True, exist_ok=True)
    cohort_path = output_dir / "v60_historical_pacing_cohorts.csv"
    summary_path = output_dir / "v60_historical_pacing_summary.csv"
    metadata_path = output_dir / "v60_historical_pacing_metadata.json"
    results.to_csv(cohort_path, index=False)
    summary.to_csv(summary_path, index=False)
    metadata = {
        "model_version": "V6.0",
        "research_only": True,
        "trade_executable": False,
        "btc_source": "data/mvrv_z_score_2026-10-06T21-46-14.csv",
        "btc_export_sha256": btc_hash,
        "btc_last_observation_date": btc_end,
        "fx_source": "Frankfurter historical rates API",
        "fx_sha256": fx_hash,
        "cohort_window_weeks": COHORT_WEEKS,
        "cohort_step_weeks": 1,
        "train_rule": "Cohort end before 2022-01-01",
        "holdout_rule": "Cohort start on or after 2022-01-01",
        "bridge_cohorts_excluded": True,
        "cash_yields_annual": list(CASH_YIELDS),
        "protected_cash_floors_pct_initial_cash": list(CASH_FLOORS),
        "cumulative_spend_caps_pct_initial_cash": ["uncapped", *[int(x) for x in CUMULATIVE_CAPS if x is not None]],
        "dynamic_policies": [{"policy": p, "threshold_set": t} for p, t in DYNAMIC_POLICIES],
        "benchmark": "fixed weekly DCA under the identical starting capital, cash yield, protected cash floor and cumulative spend cap",
        "timing_diagnostic": "Same total spend and same transaction count, compared with evenly spaced purchases across the cohort; hindsight diagnostic, not a tradable benchmark.",
        "limitations": [
            "BTC export ends 2026-10-05 and is not a contemporaneous point-in-time vintage.",
            "Frankfurter FX is the latest observation on or before signal Sunday.",
            "Execution is a next-Monday BTC/AUD spot proxy, not ASX:IBIT execution.",
            "5% cash yield is gross and not tax-adjusted.",
            "Rolling 104-week cohorts overlap heavily and are not independent trials.",
            "Historical results are descriptive and do not prove a future trading edge.",
        ],
        "cohort_count": int(len(results)),
        "summary_rows": int(len(summary)),
        "artifacts": [cohort_path.name, summary_path.name, metadata_path.name],
    }
    metadata_path.write_text(json.dumps(metadata, indent=2), encoding="utf-8")
    return metadata


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", default="artifacts/v60_historical_pacing")
    args = parser.parse_args()
    print(json.dumps(build_report(Path(args.output_dir)), indent=2))


if __name__ == "__main__":
    main()
