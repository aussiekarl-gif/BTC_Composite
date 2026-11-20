"""V6.0 stylised path and IBIT execution-cost sensitivity research.

These are controlled scenarios, not forecasts or historical observations. The
signal-to-price paths are deliberately exogenous: they isolate delayed-bottom
and rapid-recovery path dependence without pretending a synthetic price series
can reconstruct a true rolling 200WMA. The execution-cost grid is a BTC/ETF
proxy, not observed ASX:IBIT quotes or broker fills.
"""
from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

from engines.research.v60_200wma_backtest import simulate_weekly_cohort

CAPITAL_AUD = 510_000.0
INITIAL_BTC_FRACTION = 0.41
CASH_YIELD = 0.05
RESERVE_PCT = 30.0
CUMULATIVE_CAP_PCT = 50.0
DYNAMIC_SCALE = 0.75


def _rows(price_path: list[float], discount_path: list[float]) -> list[dict]:
    if len(price_path) != 104 or len(discount_path) != 104:
        raise ValueError("Synthetic paths must contain exactly 104 weekly observations")
    rows = []
    for i, (price, discount) in enumerate(zip(price_path, discount_path)):
        if price <= 0 or not 0 <= discount < 100:
            raise ValueError("Invalid synthetic price or discount")
        signal = pd.Timestamp("2022-01-02", tz="UTC") + pd.Timedelta(weeks=i)
        execution = signal + pd.Timedelta(days=1)
        rows.append({
            "signal_date": signal.date(),
            "execution_date": execution.date(),
            "btc_usd_signal_close": float(price),
            "prior_200wma_usd": float(price) / (1.0 - float(discount) / 100.0),
            "ratio_to_200wma": 1.0 - float(discount) / 100.0,
            "discount_below_200wma_pct": float(discount),
            "btc_price_aud": float(price),
            "fx_date": signal.date(),
            "usd_per_aud": 1.0,
        })
    return rows


def _scenario_paths() -> dict[str, tuple[list[float], list[float]]]:
    # Flat-to-decline paths deliberately isolate the path after first 20% discount.
    cases = {}
    for extra_fall in (0.30, 0.40, 0.50):
        prices = [100.0] * 104
        for i in range(12, 53):
            prices[i] = 100.0 * (1.0 - extra_fall * (i - 12) / 40.0)
        for i in range(53, 104):
            prices[i] = 100.0 * (1.0 - extra_fall)
        discounts = [5.0] * 12 + [
            20.0 + 10.0 * min(1.0, (i - 12) / 40.0) for i in range(12, 53)
        ] + [30.0] * 51
        cases[f"delayed_bottom_extra_{int(extra_fall*100)}pct"] = (prices, discounts)

    # Fast V: first discount appears, price bottoms shortly afterwards and recovers.
    prices = [100.0] * 104
    for i in range(12, 21):
        prices[i] = 80.0 - 2.0 * (i - 12)
    for i in range(21, 53):
        prices[i] = 64.0 + (116.0 - 64.0) * (i - 21) / 32.0
    prices[53:] = [116.0] * 51
    discounts = [5.0] * 12 + [20.0] * 9 + [
        max(0.0, 20.0 - 20.0 * (i - 21) / 32.0) for i in range(21, 53)
    ] + [0.0] * 51
    cases["rapid_v_recovery"] = (prices, discounts)
    return cases


def run_path_comparison() -> list[dict]:
    output = []
    for name, (prices, discounts) in _scenario_paths().items():
        rows = _rows(prices, discounts)
        common = dict(
            cash_yield=CASH_YIELD,
            protected_cash_floor_pct_initial_cash=RESERVE_PCT,
            max_cumulative_buy_spend_pct_initial_cash=CUMULATIVE_CAP_PCT,
        )
        fixed = simulate_weekly_cohort(rows, policy="fixed_weekly", **common)
        dynamic = simulate_weekly_cohort(
            rows, policy="measured", thresholds=(20.0, 25.0, 30.0),
            threshold_set="20_25_30", dynamic_allocation_scale=DYNAMIC_SCALE,
            **common,
        )
        output.append({
            "scenario": name,
            "fixed_final_equity_aud": fixed["final_equity_aud"],
            "dynamic_final_equity_aud": dynamic["final_equity_aud"],
            "dynamic_minus_fixed_equity_pct": 100.0 * (
                dynamic["final_equity_aud"] / fixed["final_equity_aud"] - 1.0
            ),
            "fixed_btc": fixed["btc_held"],
            "dynamic_btc": dynamic["btc_held"],
            "dynamic_minus_fixed_btc_pct": 100.0 * (
                dynamic["btc_held"] / fixed["btc_held"] - 1.0
            ),
            "fixed_cash_remaining_pct_initial_cash": 100.0 * fixed["cash_remaining_aud"] / (
                CAPITAL_AUD * (1.0 - INITIAL_BTC_FRACTION)
            ),
            "dynamic_cash_remaining_pct_initial_cash": 100.0 * dynamic["cash_remaining_aud"] / (
                CAPITAL_AUD * (1.0 - INITIAL_BTC_FRACTION)
            ),
            "dynamic_max_drawdown_pct": dynamic["max_drawdown_pct"],
            "fixed_max_drawdown_pct": fixed["max_drawdown_pct"],
            "research_only": True,
        })
    return output


def run_execution_cost_sensitivity() -> list[dict]:
    prices, discounts = _scenario_paths()["rapid_v_recovery"]
    rows = _rows(prices, discounts)
    output = []
    for friction in (0.003, 0.006, 0.010):
        for fee in (3.0, 5.0):
            for drag in (0.0025, 0.005, 0.01):
                common = dict(
                    cash_yield=CASH_YIELD,
                    protected_cash_floor_pct_initial_cash=RESERVE_PCT,
                    max_cumulative_buy_spend_pct_initial_cash=CUMULATIVE_CAP_PCT,
                    buy_friction=friction,
                    fixed_fee_aud=fee,
                    btc_drag_annual=drag,
                )
                fixed = simulate_weekly_cohort(rows, policy="fixed_weekly", **common)
                dynamic = simulate_weekly_cohort(
                    rows, policy="measured", thresholds=(20.0, 25.0, 30.0),
                    threshold_set="20_25_30", dynamic_allocation_scale=DYNAMIC_SCALE,
                    **common,
                )
                output.append({
                    "buy_friction_pct": friction * 100.0,
                    "fixed_fee_aud": fee,
                    "annual_btc_drag_pct": drag * 100.0,
                    "fixed_btc": fixed["btc_held"],
                    "dynamic_btc": dynamic["btc_held"],
                    "dynamic_btc_uplift_vs_fixed_pct": 100.0 * (
                        dynamic["btc_held"] / fixed["btc_held"] - 1.0
                    ),
                    "dynamic_equity_uplift_vs_fixed_pct": 100.0 * (
                        dynamic["final_equity_aud"] / fixed["final_equity_aud"] - 1.0
                    ),
                    "dynamic_spend_aud": dynamic["total_buy_spend_aud"],
                    "fixed_spend_aud": fixed["total_buy_spend_aud"],
                    "research_only": True,
                })
    return output


def build_report(output_path: Path) -> dict:
    paths = run_path_comparison()
    costs = run_execution_cost_sensitivity()
    report = {
        "model_version": "V6.0",
        "research_only": True,
        "trade_executable": False,
        "scenario_type": "stylised controlled paths; not forecasts or historical backtests",
        "capital_aud": CAPITAL_AUD,
        "cash_yield_gross_annual_pct": CASH_YIELD * 100.0,
        "protected_cash_reserve_pct_initial_cash": RESERVE_PCT,
        "cumulative_spend_cap_pct_initial_cash": CUMULATIVE_CAP_PCT,
        "dynamic_ladder": "20/25/30 discount thresholds; measured ladder at 0.75x",
        "delayed_bottom_and_recovery_paths": paths,
        "rapid_recovery_execution_cost_grid": costs,
        "execution_cost_limitations": [
            "Buy friction is a scenario input, not a measured IBIT bid/ask spread.",
            "Fixed fee is a per-buy proxy; actual Stake brokerage and order routing must be verified.",
            "Annual BTC drag is a generic proxy, not an observed IBIT tracking difference.",
            "No ASX market hours, premium/discount, USD cash settlement, tax or distributions are modelled.",
            "Results depend on exogenous synthetic signal paths and do not establish a trading edge.",
        ],
        "interpretation": (
            "Use the path table to identify where delayed deployment hurts and rapid "
            "recovery helps. Use the cost grid to see whether relative BTC accumulation "
            "survives progressively harsher generic friction assumptions. Neither "
            "table is sufficient for live approval."
        ),
    }
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    return report


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", default="artifacts/v60_path_cost_sensitivity.json")
    args = parser.parse_args()
    result = build_report(Path(args.output))
    print(json.dumps(result, indent=2))
