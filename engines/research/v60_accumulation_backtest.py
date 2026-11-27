"""V6.0 matched-cohort accumulation ranking by BTC units and AUD equity.

Research only. Reuses the independent V6.0 weekly replay harness; no portfolio,
broker, order or notification access. This study is buy-only: no sell, tax or
top-timing overlay is modelled, so it cannot answer a max-AUD-with-sells question.
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
from engines.research.v60_200wma_policy import THRESHOLD_SETS
from engines.research.v60_historical_report import (
    load_btc_daily, fetch_usd_per_aud, assign_validation_split,
)

ROOT = Path(__file__).resolve().parents[2]

# label, simulator policy, allocation scale, discount-threshold set
POLICY_CONFIGS = (
    ("fixed_weekly", "fixed_weekly", 1.0, "none"),
    ("baseline_2_5pct", "baseline", 1.0, "none"),
    ("measured_20_25_30", "measured", 1.0, "20_25_30"),
    ("measured_10_15_20", "measured", 1.0, "10_15_20"),
    ("stepped_20_25_30", "stepped", 1.0, "20_25_30"),
    ("aggressive_20_25_30", "aggressive", 1.0, "20_25_30"),
    ("measured_0_5x_20_25_30", "measured", 0.5, "20_25_30"),
    ("aggressive_1_25x_20_25_30", "aggressive", 1.25, "20_25_30"),
    ("aggressive_1_5x_20_25_30", "aggressive", 1.5, "20_25_30"),
)
CASH_YIELDS = (0.0, 0.05)
CASH_FLOORS = (0.0, 30.0)
CUMULATIVE_CAPS = (None, 40.0, 50.0, 60.0, 70.0)
REFERENCE = {
    "cash_yield_annual_pct": 5.0,
    "protected_cash_floor_pct_initial_cash": 0.0,
    "cumulative_spend_cap_pct_initial_cash": "uncapped",
}


def _cap_key(value) -> str:
    return "uncapped" if pd.isna(value) else f"{float(value):.0f}%"


def build_ranking_results(weekly_rows: list[dict]) -> pd.DataFrame:
    """Simulate every config on every overlapping 104-week cohort."""
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
                    for label, policy, scale, threshold_set in POLICY_CONFIGS:
                        kwargs = dict(
                            cash_yield=cash_yield,
                            protected_cash_floor_pct_initial_cash=floor,
                            max_cumulative_buy_spend_pct_initial_cash=cap,
                            dynamic_allocation_scale=scale,
                        )
                        if threshold_set == "none":
                            kwargs["threshold_set"] = "none"
                        else:
                            kwargs["threshold_set"] = threshold_set
                            kwargs["thresholds"] = THRESHOLD_SETS[threshold_set]
                        result = simulate_weekly_cohort(cohort, policy=policy, **kwargs)
                        result.update(common)
                        result["split"] = assign_validation_split(result)
                        result["policy_label"] = label
                        output.append(result)
    return pd.DataFrame(output)


def summarise_ranking(frame: pd.DataFrame) -> pd.DataFrame:
    """Compare each config with fixed weekly DCA on identical cohort and limits."""
    if frame.empty:
        raise ValueError("No accumulation results supplied")
    primary = frame.loc[frame["split"].isin(["train", "holdout"])].copy()
    fixed_index = {
        (
            str(r.cohort_start), float(r.cash_yield),
            float(r.protected_cash_floor_pct_initial_cash),
            _cap_key(r.max_cumulative_buy_spend_pct_initial_cash),
        ): r
        for r in primary.loc[primary["policy"] == "fixed_weekly"].itertuples(index=False)
    }
    summaries = []
    group_keys = [
        "split", "cash_yield", "protected_cash_floor_pct_initial_cash",
        "max_cumulative_buy_spend_pct_initial_cash", "policy_label",
    ]
    dynamic = primary.loc[primary["policy"] != "fixed_weekly"]
    for label, group in dynamic.groupby(group_keys, dropna=False):
        split, cash_yield, floor, cap, policy_label = label
        peers = []
        for row in group.itertuples(index=False):
            key = (str(row.cohort_start), float(cash_yield), float(floor), _cap_key(cap))
            if key not in fixed_index:
                raise ValueError(f"Missing matched fixed-DCA cohort: {key}")
            peers.append(fixed_index[key])
        btc_uplifts = [
            100.0 * (float(r.btc_held) / float(p.btc_held) - 1.0)
            for r, p in zip(group.itertuples(index=False), peers)
        ]
        equity_uplifts = [
            100.0 * (float(r.final_equity_aud) / float(p.final_equity_aud) - 1.0)
            for r, p in zip(group.itertuples(index=False), peers)
        ]
        spend_differences = [
            100.0 * (float(r.total_buy_spend_aud) / float(p.total_buy_spend_aud) - 1.0)
            if float(p.total_buy_spend_aud) > 0 else 0.0
            for r, p in zip(group.itertuples(index=False), peers)
        ]
        drawdown_differences = [
            float(r.max_drawdown_pct) - float(p.max_drawdown_pct)
            for r, p in zip(group.itertuples(index=False), peers)
        ]
        rows = list(group.itertuples(index=False))
        summaries.append({
            "split": split,
            "cash_yield_annual_pct": 100.0 * float(cash_yield),
            "protected_cash_floor_pct_initial_cash": float(floor),
            "cumulative_spend_cap_pct_initial_cash": _cap_key(cap),
            "policy": policy_label,
            "cohort_count": int(len(group)),
            "median_btc_held": float(pd.Series([float(r.btc_held) for r in rows]).median()),
            "median_final_equity_aud": float(pd.Series([float(r.final_equity_aud) for r in rows]).median()),
            "median_btc_uplift_vs_matched_fixed_pct": float(pd.Series(btc_uplifts).median()),
            "p10_btc_uplift_vs_matched_fixed_pct": float(pd.Series(btc_uplifts).quantile(0.10)),
            "worst_btc_uplift_vs_matched_fixed_pct": float(pd.Series(btc_uplifts).min()),
            "median_final_equity_uplift_vs_matched_fixed_pct": float(pd.Series(equity_uplifts).median()),
            "p10_final_equity_uplift_vs_matched_fixed_pct": float(pd.Series(equity_uplifts).quantile(0.10)),
            "worst_final_equity_uplift_vs_matched_fixed_pct": float(pd.Series(equity_uplifts).min()),
            "cohort_win_rate_btc_pct": 100.0 * sum(x > 0 for x in btc_uplifts) / len(btc_uplifts),
            "cohort_win_rate_final_equity_pct": 100.0 * sum(x > 0 for x in equity_uplifts) / len(equity_uplifts),
            "median_spend_difference_vs_matched_fixed_pct": float(pd.Series(spend_differences).median()),
            "median_total_buy_spend_aud": float(pd.Series([float(r.total_buy_spend_aud) for r in rows]).median()),
            "median_cash_remaining_aud": float(pd.Series([float(r.cash_remaining_aud) for r in rows]).median()),
            "median_max_drawdown_pct": float(pd.Series([float(r.max_drawdown_pct) for r in rows]).median()),
            "median_max_drawdown_difference_vs_fixed_pp": float(pd.Series(drawdown_differences).median()),
            "median_equal_buy_amount_uniform_dates_btc_uplift_pct": float(
                group["same_spend_same_count_btc_timing_uplift_pct_hindsight"].median()
            ),
            "median_actual_spend_distribution_uniform_dates_btc_timing_only_pct": float(
                group["same_actual_spend_distribution_uniform_dates_btc_timing_only_pct"].median()
            ),
            "cohorts_overlap": True,
            "interpretation": "Matched cohort, capital, yield, reserve and cap; buy-only, no sell or tax timing.",
        })
    return pd.DataFrame(summaries)


def add_rank_columns(summary: pd.DataFrame) -> pd.DataFrame:
    """Rank configs within each matched setting for BTC and AUD objectives."""
    if summary.empty:
        raise ValueError("No summary rows supplied")
    keys = [
        "split", "cash_yield_annual_pct", "protected_cash_floor_pct_initial_cash",
        "cumulative_spend_cap_pct_initial_cash",
    ]
    out = summary.copy()
    out["btc_rank"] = out.groupby(keys)["median_btc_uplift_vs_matched_fixed_pct"].rank(
        ascending=False, method="min",
    ).astype(int)
    out["equity_rank"] = out.groupby(keys)["median_final_equity_uplift_vs_matched_fixed_pct"].rank(
        ascending=False, method="min",
    ).astype(int)
    out["rank_divergence"] = out["btc_rank"] - out["equity_rank"]
    return out.sort_values(keys + ["btc_rank"]).reset_index(drop=True)


def reference_leaderboards(ranked: pd.DataFrame, limit: int = 5) -> dict:
    """Top configs for each split at one fixed matched setting."""
    selected = ranked
    for column, value in REFERENCE.items():
        selected = selected.loc[selected[column] == value]
    if selected.empty:
        raise ValueError("No rows for the reference comparison setting")
    result = {}
    for split, group in selected.groupby("split"):
        result[split] = {
            "by_btc_uplift": group.nsmallest(limit, "btc_rank")[
                ["policy", "median_btc_uplift_vs_matched_fixed_pct",
                 "median_final_equity_uplift_vs_matched_fixed_pct", "btc_rank", "equity_rank"]
            ].to_dict("records"),
            "by_equity_uplift": group.nsmallest(limit, "equity_rank")[
                ["policy", "median_btc_uplift_vs_matched_fixed_pct",
                 "median_final_equity_uplift_vs_matched_fixed_pct", "btc_rank", "equity_rank"]
            ].to_dict("records"),
        }
    return result


def build_report(output_dir: Path) -> dict:
    btc, btc_hash, btc_end = load_btc_daily()
    fx, fx_hash = fetch_usd_per_aud(date(2016, 1, 1), pd.Timestamp(btc.index[-1]).date())
    weekly = build_weekly_execution_rows(btc, fx, first_execution_date=date(2017, 1, 1))
    results = build_ranking_results(weekly)
    summary = summarise_ranking(results)
    ranked = add_rank_columns(summary)
    output_dir.mkdir(parents=True, exist_ok=True)
    cohort_path = output_dir / "v60_accumulation_ranking_cohorts.csv"
    summary_path = output_dir / "v60_accumulation_ranking_summary.csv"
    metadata_path = output_dir / "v60_accumulation_ranking_metadata.json"
    results.to_csv(cohort_path, index=False)
    ranked.to_csv(summary_path, index=False)
    metadata = {
        "model_version": "V6.0",
        "research_only": True,
        "trade_executable": False,
        "no_sell_modelled": True,
        "objective": "Compare terminal BTC units and final AUD equity; not a max-AUD-with-sells study.",
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
        "protected_cash_floors_pct_initial_cash": list(CASH_FLOORS),
        "cumulative_spend_caps_pct_initial_cash": ["uncapped", *[int(x) for x in CUMULATIVE_CAPS if x is not None]],
        "policy_configs": [
            {"label": label, "policy": policy, "allocation_scale": scale, "threshold_set": ts}
            for label, policy, scale, ts in POLICY_CONFIGS
        ],
        "benchmark": "fixed weekly DCA under identical cohort, capital, yield, reserve and cumulative spend cap",
        "reference_setting": REFERENCE,
        "leaderboards": reference_leaderboards(ranked),
        "limitations": [
            "Buy-only accumulation: no top-sell, tax or re-entry timing is modelled.",
            "Leaderboard winners mainly reflect faster cash deployment, not proven 200WMA timing skill; discount tiers were inactive in the pre-2022 train era. Legacy equal-buy-amount uniform-date diagnostic mixes amount distribution with timing; the new actual-spend-distribution uniform-date metric isolates price timing, but its shifted-date cash feasibility is not modelled.",
            "Historical BTC export ends 2026-10-05 and is not a contemporaneous point-in-time vintage.",
            "Execution is a next-Monday BTC/AUD spot proxy, not an ASX:IBIT fill.",
            "Cash yield is gross and not tax-adjusted; BTC drag and buy friction are assumptions.",
            "Rolling 104-week cohorts overlap heavily and are not independent trials.",
            "Historical results are descriptive and do not prove a future trading edge.",
        ],
        "cohort_count": int(results["cohort_start"].nunique()),
        "result_rows": int(len(results)),
        "summary_rows": int(len(ranked)),
        "artifacts": [cohort_path.name, summary_path.name, metadata_path.name],
    }
    metadata_path.write_text(json.dumps(metadata, indent=2), encoding="utf-8")
    return metadata


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", default="artifacts/v60_accumulation_ranking")
    args = parser.parse_args()
    print(json.dumps(build_report(Path(args.output_dir)), indent=2))


if __name__ == "__main__":
    main()
