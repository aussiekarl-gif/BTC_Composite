"""Historical V6.0 base-allocation scale sensitivity.

Tests slower/faster versions of the measured 20/25/30 ladder. Fixed weekly DCA
is matched by cohort, initial capital, reserve, gross cash yield and cumulative
spend cap. This is retrospective research, not a live recommendation.
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

SCALES = (0.5, 0.75, 1.0, 1.25, 1.5)
CASH_FLOOR_PCTS = (0.0, 30.0)
CUMULATIVE_CAPS = (None, 40.0, 50.0, 60.0, 70.0)
CASH_YIELDS = (0.0, 0.05)
THRESHOLDS = (20.0, 25.0, 30.0)


def _cap_key(value) -> str:
    return "uncapped" if pd.isna(value) else f"{float(value):.0f}%"


def build_scale_results(weekly_rows: list[dict]) -> pd.DataFrame:
    if len(weekly_rows) < COHORT_WEEKS:
        raise ValueError("Insufficient weekly observations for 104-week cohorts")
    output = []
    for start in range(len(weekly_rows) - COHORT_WEEKS + 1):
        cohort = weekly_rows[start:start + COHORT_WEEKS]
        for cash_yield in CASH_YIELDS:
            for floor in CASH_FLOOR_PCTS:
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
                    )
                    fixed.update(common)
                    fixed["split"] = assign_validation_split(fixed)
                    output.append(fixed)
                    for scale in SCALES:
                        dynamic = simulate_weekly_cohort(
                            cohort, policy="measured", cash_yield=cash_yield,
                            protected_cash_floor_pct_initial_cash=floor,
                            max_cumulative_buy_spend_pct_initial_cash=cap,
                            thresholds=THRESHOLDS, threshold_set="20_25_30",
                            dynamic_allocation_scale=scale,
                        )
                        dynamic.update(common)
                        dynamic["split"] = assign_validation_split(dynamic)
                        output.append(dynamic)
    return pd.DataFrame(output)


def summarise_scale_results(frame: pd.DataFrame) -> pd.DataFrame:
    primary = frame.loc[frame["split"].isin(["train", "holdout"])].copy()
    fixed = primary.loc[primary["policy"] == "fixed_weekly"]
    fixed_index = {
        (
            str(r.cohort_start), float(r.cash_yield),
            float(r.protected_cash_floor_pct_initial_cash),
            _cap_key(r.max_cumulative_buy_spend_pct_initial_cash),
        ): r
        for r in fixed.itertuples(index=False)
    }
    summaries = []
    dynamic = primary.loc[primary["policy"] == "measured"]
    for label, group in dynamic.groupby(
        ["split", "cash_yield", "protected_cash_floor_pct_initial_cash",
         "max_cumulative_buy_spend_pct_initial_cash", "dynamic_allocation_scale"],
        dropna=False,
    ):
        split, cash_yield, floor, cap, scale = label
        peers = []
        for row in group.itertuples(index=False):
            key = (str(row.cohort_start), float(cash_yield), float(floor), _cap_key(cap))
            if key not in fixed_index:
                raise ValueError(f"Missing matched fixed-DCA cohort: {key}")
            peers.append(fixed_index[key])
        eq = [100.0 * (float(r.final_equity_aud) / float(p.final_equity_aud) - 1.0)
              for r, p in zip(group.itertuples(index=False), peers)]
        btc = [100.0 * (float(r.btc_held) / float(p.btc_held) - 1.0)
               for r, p in zip(group.itertuples(index=False), peers)]
        spend = [100.0 * (float(r.total_buy_spend_aud) / float(p.total_buy_spend_aud) - 1.0)
                 if float(p.total_buy_spend_aud) > 0 else 0.0
                 for r, p in zip(group.itertuples(index=False), peers)]
        dd = [float(r.max_drawdown_pct) - float(p.max_drawdown_pct)
              for r, p in zip(group.itertuples(index=False), peers)]
        summaries.append({
            "split": split,
            "cash_yield_annual_pct": float(cash_yield) * 100.0,
            "protected_cash_floor_pct_initial_cash": float(floor),
            "cumulative_spend_cap_pct_initial_cash": _cap_key(cap),
            "dynamic_allocation_scale": float(scale),
            "base_buy_pct_deployable_cash": 2.5 * float(scale),
            "top_tier_buy_pct_deployable_cash": 7.5 * float(scale),
            "cohort_count": int(len(group)),
            "median_final_equity_uplift_vs_matched_fixed_pct": float(pd.Series(eq).median()),
            "p10_final_equity_uplift_vs_matched_fixed_pct": float(pd.Series(eq).quantile(0.10)),
            "worst_final_equity_uplift_vs_matched_fixed_pct": float(pd.Series(eq).min()),
            "median_btc_uplift_vs_matched_fixed_pct": float(pd.Series(btc).median()),
            "p10_btc_uplift_vs_matched_fixed_pct": float(pd.Series(btc).quantile(0.10)),
            "worst_btc_uplift_vs_matched_fixed_pct": float(pd.Series(btc).min()),
            "cohort_win_rate_final_equity_pct": 100.0 * sum(x > 0 for x in eq) / len(eq),
            "median_spend_difference_vs_matched_fixed_pct": float(pd.Series(spend).median()),
            "median_total_buy_spend_aud": float(group["total_buy_spend_aud"].median()),
            "median_cash_remaining_aud": float(group["cash_remaining_aud"].median()),
            "median_max_drawdown_difference_vs_fixed_pp": float(pd.Series(dd).median()),
            "median_same_spend_same_count_timing_uplift_pct_hindsight": float(
                group["same_spend_same_count_btc_timing_uplift_pct_hindsight"].median()
            ),
            "cohorts_overlap": True,
            "interpretation": "Matched fixed DCA uses identical cohort, initial capital, cash yield, reserve and spend cap; realised spend can differ.",
        })
    return pd.DataFrame(summaries).sort_values(
        ["split", "cash_yield_annual_pct", "protected_cash_floor_pct_initial_cash",
         "cumulative_spend_cap_pct_initial_cash", "dynamic_allocation_scale"]
    ).reset_index(drop=True)


def build_report(output_dir: Path) -> dict:
    root = Path(__file__).resolve().parents[2]
    btc, btc_hash, btc_end = load_btc_daily()
    fx, fx_hash = fetch_usd_per_aud(date(2016, 1, 1), pd.Timestamp(btc.index[-1]).date())
    weekly = build_weekly_execution_rows(btc, fx, first_execution_date=date(2017, 1, 1))
    results = build_scale_results(weekly)
    summary = summarise_scale_results(results)
    output_dir.mkdir(parents=True, exist_ok=True)
    cohort_path = output_dir / "v60_allocation_scale_cohorts.csv"
    summary_path = output_dir / "v60_allocation_scale_summary.csv"
    metadata_path = output_dir / "v60_allocation_scale_metadata.json"
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
        "cash_yields_annual_pct": [x * 100.0 for x in CASH_YIELDS],
        "protected_cash_floors_pct_initial_cash": list(CASH_FLOOR_PCTS),
        "cumulative_spend_caps_pct_initial_cash": ["uncapped", 40, 50, 60, 70],
        "dynamic_allocation_scales": list(SCALES),
        "base_buy_percentages": [2.5 * x for x in SCALES],
        "top_tier_buy_percentages": [7.5 * x for x in SCALES],
        "benchmark": "fixed weekly DCA under the identical starting capital, reserve, gross cash yield and cumulative spending cap",
        "limitations": [
            "Historical BTC export ends 2026-10-05 and is not a contemporaneous point-in-time vintage.",
            "0% and 5% cash yields are tested; the 5% yield is gross, not guaranteed and not tax-adjusted.",
            "Execution is a next-Monday BTC/AUD spot proxy, not an ASX:IBIT fill.",
            "Rolling 104-week cohorts overlap heavily and are not independent trials.",
            "Synthetic prolonged-bear stress must be considered alongside historical holdout results.",
            "Historical results are descriptive and do not prove future trading edge.",
        ],
        "cohort_count": int(len(results)),
        "summary_rows": int(len(summary)),
        "artifacts": [cohort_path.name, summary_path.name, metadata_path.name],
    }
    metadata_path.write_text(json.dumps(metadata, indent=2), encoding="utf-8")
    return metadata


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", default="artifacts/v60_allocation_scale")
    args = parser.parse_args()
    print(json.dumps(build_report(Path(args.output_dir)), indent=2))


if __name__ == "__main__":
    main()
