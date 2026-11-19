"""V6.0 synthetic 104-week stress scenarios for the 200WMA DCA policy.

These are deliberately constructed price paths, not historical observations,
forecasts or probability-weighted scenarios. The 200WMA is calculated
causally from 200 prior weekly closes in each scenario.
"""
from __future__ import annotations

import argparse
import json
from datetime import date, timedelta
from pathlib import Path
from statistics import mean

import pandas as pd

from engines.research.v60_200wma_backtest import simulate_weekly_cohort
from engines.research.v60_200wma_policy import THRESHOLD_SETS

START_SUNDAY = date(2020, 1, 5)
WARMUP_WEEKS = 200
SCENARIO_WEEKS = 104
CASH_YIELDS = (0.0, 0.05)
CASH_FLOORS = (0.0, 30.0, 40.0, 50.0, 60.0)


def linear_path(start: float, end: float, count: int) -> list[float]:
    if count < 1:
        raise ValueError("Path count must be positive")
    if count == 1:
        return [float(end)]
    return [float(start + (end-start)*i/(count-1)) for i in range(count)]


def scenario_price_paths() -> dict[str, dict]:
    return {
        "prolonged_bear_70pct": {
            "description": "BTC/AUD declines linearly by 70% over 104 weeks",
            "prices": linear_path(100_000, 30_000, 104),
        },
        "false_bottom_recovery": {
            "description": "Four-week 30% fall, then rapid recovery to +20% above start",
            "prices": linear_path(100_000, 70_000, 4)
                       + linear_path(70_000, 120_000, 8)[1:]
                       + [120_000.0] * 93,
        },
        "extended_bear_then_recovery": {
            "description": "12-week fall to 60%, 66-week base, then 26-week recovery",
            "prices": linear_path(100_000, 60_000, 12)
                       + [60_000.0] * 66
                       + linear_path(60_000, 100_000, 26),
        },
        "rapid_v_recovery": {
            "description": "Eight-week fall to 50%, 16-week recovery to 130%, then flat",
            "prices": linear_path(100_000, 50_000, 8)
                       + linear_path(50_000, 130_000, 16)[1:]
                       + [130_000.0] * 81,
        },
        "extended_above_wma_rally": {
            "description": "Steady 50% rally while remaining above the prior 200WMA",
            "prices": linear_path(100_000, 150_000, 104),
        },
    }


def build_scenario_rows(prices: list[float]) -> list[dict]:
    if len(prices) != SCENARIO_WEEKS:
        raise ValueError("Every stress scenario must contain 104 weekly closes")
    if any(not isinstance(x, (int, float)) or x <= 0 for x in prices):
        raise ValueError("Scenario prices must be positive")
    history = [100_000.0] * WARMUP_WEEKS
    rows = []
    for i, price in enumerate(prices):
        prior_200wma = mean(history[-WARMUP_WEEKS:])
        signal_date = START_SUNDAY + timedelta(weeks=i)
        rows.append({
            "signal_date": signal_date,
            "execution_date": signal_date + timedelta(days=1),
            "ratio_to_200wma": float(price) / prior_200wma,
            "btc_price_aud": float(price),
            "prior_200wma_aud": prior_200wma,
        })
        history.append(float(price))
    return rows


def build_stress_report(output_dir: Path) -> dict:
    results = []
    descriptions = {}
    for name, scenario in scenario_price_paths().items():
        descriptions[name] = scenario["description"]
        rows = build_scenario_rows(scenario["prices"])
        for cash_yield in CASH_YIELDS:
            for floor in CASH_FLOORS:
                for policy in ("fixed_weekly", "baseline"):
                    result = simulate_weekly_cohort(
                        rows, policy=policy, cash_yield=cash_yield,
                        protected_cash_floor_pct_initial_cash=floor,
                        threshold_set="none",
                    )
                    result.update({
                        "scenario": name,
                        "cash_yield": cash_yield,
                        "threshold_set": "none",
                    })
                    results.append(result)
                for threshold_set, thresholds in THRESHOLD_SETS.items():
                    for policy in ("measured", "stepped", "aggressive"):
                        result = simulate_weekly_cohort(
                            rows, policy=policy, cash_yield=cash_yield,
                            protected_cash_floor_pct_initial_cash=floor,
                            thresholds=thresholds, threshold_set=threshold_set,
                        )
                        result.update({
                            "scenario": name,
                            "cash_yield": cash_yield,
                            "threshold_set": threshold_set,
                        })
                        results.append(result)
    frame = pd.DataFrame(results)
    output_dir.mkdir(parents=True, exist_ok=True)
    result_path = output_dir / "v60_synthetic_stress_results.csv"
    metadata_path = output_dir / "v60_synthetic_stress_metadata.json"
    frame.to_csv(result_path, index=False)
    metadata = {
        "model_version": "V6.0",
        "research_only": True,
        "trade_executable": False,
        "scenario_count": len(descriptions),
        "scenario_weeks": SCENARIO_WEEKS,
        "warmup_weeks": WARMUP_WEEKS,
        "scenarios": descriptions,
        "cash_yields_annual": list(CASH_YIELDS),
        "protected_cash_floors_pct_initial_cash": list(CASH_FLOORS),
        "threshold_sets": {k: list(v) for k, v in THRESHOLD_SETS.items()},
        "policies": ["fixed_weekly", "baseline", "measured", "stepped", "aggressive"],
        "result_rows": len(frame),
        "warning": "Synthetic paths are stress tests, not historical evidence, forecasts or probability-weighted outcomes.",
        "wma_method": "Each signal uses the mean of the 200 prior weekly closes; current signal week excluded.",
        "execution_proxy": "Next Monday scenario BTC/AUD close; synthetic, not an ASX:IBIT fill.",
        "assumptions": {
            "capital_aud": 510000.0,
            "initial_btc_fraction": 0.41,
            "btc_drag_annual": 0.0025,
            "buy_friction": 0.003,
            "fixed_fee_aud": 3.0,
            "weekly_cap_pct_original_capital": 5.0,
        },
        "artifacts": [result_path.name, metadata_path.name],
    }
    metadata_path.write_text(json.dumps(metadata, indent=2), encoding="utf-8")
    return metadata


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", default="artifacts/v60_stress")
    args = parser.parse_args()
    print(json.dumps(build_stress_report(Path(args.output_dir)), indent=2))


if __name__ == "__main__":
    main()
