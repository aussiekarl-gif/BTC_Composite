"""Targeted V6.0 allocation-scale synthetic stress under matched spend caps."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import pandas as pd

from engines.research.v60_200wma_backtest import simulate_weekly_cohort
from engines.research.v60_synthetic_stress import scenario_price_paths, build_scenario_rows

SCALES = (0.5, 0.75, 1.0, 1.25)
CAPS = (40.0, 50.0, 60.0, 70.0, None)
CASH_YIELD = 0.05
CASH_FLOOR = 30.0
SCENARIOS = (
    "prolonged_bear_70pct",
    "false_bottom_recovery",
    "extended_bear_then_recovery",
    "rapid_v_recovery",
    "extended_above_wma_rally",
)


def build_report(output_dir: Path) -> dict:
    scenarios = scenario_price_paths()
    rows_out = []
    for scenario_name in SCENARIOS:
        cohort = build_scenario_rows(scenarios[scenario_name]["prices"])
        for cap in CAPS:
            fixed = simulate_weekly_cohort(
                cohort, policy="fixed_weekly", cash_yield=CASH_YIELD,
                protected_cash_floor_pct_initial_cash=CASH_FLOOR,
                max_cumulative_buy_spend_pct_initial_cash=cap,
            )
            for scale in SCALES:
                dynamic = simulate_weekly_cohort(
                    cohort, policy="measured", cash_yield=CASH_YIELD,
                    protected_cash_floor_pct_initial_cash=CASH_FLOOR,
                    max_cumulative_buy_spend_pct_initial_cash=cap,
                    dynamic_allocation_scale=scale,
                )
                rows_out.append({
                    "scenario": scenario_name,
                    "scenario_description": scenarios[scenario_name]["description"],
                    "cash_yield_annual_pct": CASH_YIELD * 100.0,
                    "protected_cash_floor_pct_initial_cash": CASH_FLOOR,
                    "cumulative_spend_cap_pct_initial_cash": "uncapped" if cap is None else f"{cap:.0f}%",
                    "dynamic_allocation_scale": scale,
                    "base_buy_pct_deployable_cash": 2.5 * scale,
                    "top_tier_buy_pct_deployable_cash": 7.5 * scale,
                    "fixed_return_pct": fixed["total_return_pct"],
                    "measured_return_pct": dynamic["total_return_pct"],
                    "measured_minus_fixed_return_pp": dynamic["total_return_pct"] - fixed["total_return_pct"],
                    "fixed_btc_held": fixed["btc_held"],
                    "measured_btc_held": dynamic["btc_held"],
                    "measured_btc_uplift_vs_fixed_pct": 100.0 * (dynamic["btc_held"] / fixed["btc_held"] - 1.0),
                    "fixed_spend_aud": fixed["total_buy_spend_aud"],
                    "measured_spend_aud": dynamic["total_buy_spend_aud"],
                    "measured_spend_difference_pct": 100.0 * (dynamic["total_buy_spend_aud"] / fixed["total_buy_spend_aud"] - 1.0) if fixed["total_buy_spend_aud"] else 0.0,
                    "fixed_cash_remaining_aud": fixed["cash_remaining_aud"],
                    "measured_cash_remaining_aud": dynamic["cash_remaining_aud"],
                    "fixed_max_drawdown_pct": fixed["max_drawdown_pct"],
                    "measured_max_drawdown_pct": dynamic["max_drawdown_pct"],
                    "measured_minus_fixed_drawdown_pp": dynamic["max_drawdown_pct"] - fixed["max_drawdown_pct"],
                    "research_only": True,
                    "trade_executable": False,
                })
    frame = pd.DataFrame(rows_out)
    output_dir.mkdir(parents=True, exist_ok=True)
    csv_path = output_dir / "v60_allocation_scale_synthetic_stress.csv"
    metadata_path = output_dir / "v60_allocation_scale_synthetic_stress_metadata.json"
    frame.to_csv(csv_path, index=False)
    metadata = {
        "model_version": "V6.0",
        "research_only": True,
        "trade_executable": False,
        "scenario_count": len(SCENARIOS),
        "scenarios": {name: scenarios[name]["description"] for name in SCENARIOS},
        "cash_yield_annual_pct": CASH_YIELD * 100.0,
        "protected_cash_floor_pct_initial_cash": CASH_FLOOR,
        "cumulative_spend_caps_pct_initial_cash": ["uncapped", 40, 50, 60, 70],
        "dynamic_allocation_scales": list(SCALES),
        "benchmark": "fixed weekly DCA under identical scenario, cash yield, reserve and cumulative spend cap",
        "warning": "Synthetic price paths are not historical observations, forecasts or probability-weighted scenarios.",
        "result_rows": len(frame),
        "artifacts": [csv_path.name, metadata_path.name],
    }
    metadata_path.write_text(json.dumps(metadata, indent=2), encoding="utf-8")
    return metadata


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", default="artifacts/v60_allocation_scale_stress")
    args = parser.parse_args()
    print(json.dumps(build_report(Path(args.output_dir)), indent=2))


if __name__ == "__main__":
    main()
