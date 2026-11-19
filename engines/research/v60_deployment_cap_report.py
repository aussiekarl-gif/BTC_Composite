"""V6.0 cumulative deployment-cap sensitivity for selected synthetic paths."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import pandas as pd

from engines.research.v60_200wma_backtest import simulate_weekly_cohort
from engines.research.v60_synthetic_stress import build_scenario_rows, scenario_price_paths

SCENARIOS = ("prolonged_bear_70pct", "false_bottom_recovery", "rapid_v_recovery")
CASH_YIELDS = (0.0, 0.05)
CASH_FLOORS = (0.0, 30.0, 50.0)
CUMULATIVE_CAPS = (None, 40.0, 50.0, 60.0, 70.0)
POLICIES = ("fixed_weekly", "baseline", "measured", "stepped", "aggressive")


def build_deployment_cap_report(output_dir: Path) -> dict:
    paths = scenario_price_paths()
    rows_out = []
    for scenario_name in SCENARIOS:
        rows = build_scenario_rows(paths[scenario_name]["prices"])
        for cash_yield in CASH_YIELDS:
            for floor in CASH_FLOORS:
                for cap in CUMULATIVE_CAPS:
                    for policy in POLICIES:
                        result = simulate_weekly_cohort(
                            rows,
                            policy=policy,
                            cash_yield=cash_yield,
                            protected_cash_floor_pct_initial_cash=floor,
                            max_cumulative_buy_spend_pct_initial_cash=cap,
                            threshold_set="20_25_30",
                        )
                        result.update({
                            "scenario": scenario_name,
                            "cash_yield": cash_yield,
                            "cumulative_cap_label": "uncapped" if cap is None else f"{cap:.0f}%",
                            "threshold_set": "none" if policy in ("fixed_weekly", "baseline") else "20_25_30",
                        })
                        rows_out.append(result)
    frame = pd.DataFrame(rows_out)
    output_dir.mkdir(parents=True, exist_ok=True)
    results_path = output_dir / "v60_cumulative_deployment_cap_results.csv"
    metadata_path = output_dir / "v60_cumulative_deployment_cap_metadata.json"
    frame.to_csv(results_path, index=False)
    metadata = {
        "model_version": "V6.0",
        "research_only": True,
        "trade_executable": False,
        "scenarios": {name: paths[name]["description"] for name in SCENARIOS},
        "cash_yields_annual": list(CASH_YIELDS),
        "protected_cash_floors_pct_initial_cash": list(CASH_FLOORS),
        "cumulative_spend_caps_pct_initial_cash": [
            "uncapped" if x is None else x for x in CUMULATIVE_CAPS
        ],
        "policies": list(POLICIES),
        "threshold_set_for_dynamic_candidates": "20_25_30",
        "result_rows": len(frame),
        "warning": "Synthetic sensitivity only; not historical evidence, forecasts or probabilities.",
        "definition": "Cumulative cap includes purchase fees and limits total cohort spend to the selected percentage of initial cash.",
        "assumptions": {
            "capital_aud": 510000.0,
            "initial_btc_fraction": 0.41,
            "btc_drag_annual": 0.0025,
            "buy_friction": 0.003,
            "fixed_fee_aud": 3.0,
            "weekly_cap_pct_original_capital": 5.0,
        },
        "artifacts": [results_path.name, metadata_path.name],
    }
    metadata_path.write_text(json.dumps(metadata, indent=2), encoding="utf-8")
    return metadata


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", default="artifacts/v60_deployment_cap")
    args = parser.parse_args()
    print(json.dumps(build_deployment_cap_report(Path(args.output_dir)), indent=2))


if __name__ == "__main__":
    main()
