"""Research-only matched V6.0 replay using Firsthand vs Coin Metrics BTC prices.

The only changed input is the BTC/USD daily price source. FX, capital,
cash-yield scenarios, weekly cap, friction, fees, policies and cohorts are
identical. Outputs are diagnostic only and never feed Production or live signals.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from datetime import date, datetime, timezone
from pathlib import Path

import pandas as pd

from engines.research.firsthand_cross_source_validation import (
    fetch_firsthand, fetch_coinmetrics,
)
from engines.research.v60_200wma_backtest import (
    build_weekly_execution_rows, rolling_104_week_comparison,
)

CASH_YIELDS = (0.0, 0.05)
CASH_FLOORS = (0.0, 20.0)
THRESHOLD_SETS = ("20_25_30",)


def fetch_usd_per_aud(start: date, end: date) -> tuple[pd.Series, str]:
    url = f"https://api.frankfurter.app/{start.isoformat()}..{end.isoformat()}"
    import requests
    response = requests.get(
        url, params={"from": "USD", "to": "AUD"}, timeout=45,
        headers={"User-Agent": "BTC-Composite-Firsthand-Price-Sensitivity/1.0"},
    )
    response.raise_for_status()
    payload = response.json()
    rates = payload.get("rates", {})
    if not rates:
        raise ValueError("Frankfurter returned no USD/AUD observations")
    values = {}
    for day, quote in rates.items():
        aud_per_usd = float(quote["AUD"])
        if aud_per_usd <= 0:
            raise ValueError("Invalid USD/AUD FX rate")
        values[pd.Timestamp(day, tz="UTC")] = 1.0 / aud_per_usd
    fx = pd.Series(values, name="usd_per_aud").sort_index()
    if fx.index.has_duplicates:
        raise ValueError("Duplicate FX dates")
    digest = hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    return fx, digest


def _cohort_key(row: dict) -> tuple:
    return (
        row["cohort_start"], row["cohort_end"], row["policy"],
        float(row["protected_cash_floor_pct_initial_cash"]),
        str(row.get("threshold_set", "none")),
    )


def compare_replays(firsthand_results: list[dict], coinmetrics_results: list[dict]) -> dict:
    """Pair identical cohort/policy rows and report provider-source outcome deltas."""
    fh = {_cohort_key(r): r for r in firsthand_results}
    cm = {_cohort_key(r): r for r in coinmetrics_results}
    if len(fh) != len(firsthand_results) or len(cm) != len(coinmetrics_results):
        raise ValueError("Duplicate provider cohort keys")
    if set(fh) != set(cm):
        raise ValueError("Provider replays do not have identical matched cohorts")
    paired = []
    for key in sorted(fh):
        a, b = fh[key], cm[key]
        paired.append({
            "cohort_start": a["cohort_start"],
            "cohort_end": a["cohort_end"],
            "policy": a["policy"],
            "cash_floor_pct_initial_cash": key[3],
            "threshold_set": key[4],
            "firsthand_final_equity_aud": a["final_equity_aud"],
            "coinmetrics_final_equity_aud": b["final_equity_aud"],
            "final_equity_delta_pct_firsthand_vs_coinmetrics":
                100.0 * (a["final_equity_aud"] / b["final_equity_aud"] - 1.0),
            "firsthand_btc_held": a["btc_held"],
            "coinmetrics_btc_held": b["btc_held"],
            "btc_held_delta_pct_firsthand_vs_coinmetrics":
                100.0 * (a["btc_held"] / b["btc_held"] - 1.0),
            "firsthand_buy_count": a["buy_count"],
            "coinmetrics_buy_count": b["buy_count"],
            "buy_count_delta": a["buy_count"] - b["buy_count"],
            "firsthand_total_buy_spend_aud": a["total_buy_spend_aud"],
            "coinmetrics_total_buy_spend_aud": b["total_buy_spend_aud"],
        })
    frame = pd.DataFrame(paired)
    summaries = []
    grouping = ["policy", "cash_floor_pct_initial_cash", "threshold_set"]
    for key, group in frame.groupby(grouping, dropna=False):
        eq = group["final_equity_delta_pct_firsthand_vs_coinmetrics"]
        btc = group["btc_held_delta_pct_firsthand_vs_coinmetrics"]
        summaries.append({
            "policy": key[0], "cash_floor_pct_initial_cash": float(key[1]),
            "threshold_set": key[2], "matched_cohorts": int(len(group)),
            "median_final_equity_delta_pct": float(eq.median()),
            "mean_final_equity_delta_pct": float(eq.mean()),
            "p95_abs_final_equity_delta_pct": float(eq.abs().quantile(0.95)),
            "max_abs_final_equity_delta_pct": float(eq.abs().max()),
            "firsthand_higher_equity_cohorts": int((eq > 0).sum()),
            "median_btc_held_delta_pct": float(btc.median()),
            "mean_btc_held_delta_pct": float(btc.mean()),
            "p95_abs_btc_held_delta_pct": float(btc.abs().quantile(0.95)),
            "max_abs_btc_held_delta_pct": float(btc.abs().max()),
            "firsthand_higher_btc_cohorts": int((btc > 0).sum()),
            "median_buy_count_delta": float(group["buy_count_delta"].median()),
        })
    return {
        "paired_cohort_count": int(len(frame)),
        "summary": summaries,
        "cohort_results": paired,
    }



def summarise_price_observations(firsthand: pd.Series, coinmetrics: pd.Series,
                                 weekday: int | None = None) -> dict:
    pair = pd.concat({
        "firsthand": firsthand.rename("firsthand"),
        "coinmetrics": coinmetrics.rename("coinmetrics"),
    }, axis=1).dropna()
    if weekday is not None:
        pair = pair.loc[pair.index.dayofweek == weekday]
    ape = ((pair["firsthand"] / pair["coinmetrics"]) - 1.0).abs() * 100.0
    worst = ape.nlargest(10)
    return {
        "observations": int(len(pair)),
        "mean_ape_pct": float(ape.mean()),
        "median_ape_pct": float(ape.median()),
        "p95_ape_pct": float(ape.quantile(0.95)),
        "max_ape_pct": float(ape.max()),
        "worst_dates": [
            {"date": d.date().isoformat(), "ape_pct": float(v),
             "firsthand": float(pair.loc[d, "firsthand"]),
             "coinmetrics": float(pair.loc[d, "coinmetrics"])}
            for d, v in worst.items()
        ],
    }


def build_report(output_dir: Path) -> dict:
    retrieved = datetime.now(timezone.utc).isoformat()
    firsthand = fetch_firsthand(keys=("btc",))
    coinmetrics = fetch_coinmetrics(start_date=str(firsthand.index.min().date()))
    if "PriceUSD" not in coinmetrics:
        raise ValueError("Coin Metrics PriceUSD missing")
    start = max(firsthand.index.min(), coinmetrics.index.min()).date()
    end = min(firsthand.index.max(), coinmetrics.index.max()).date()
    fx, fx_hash = fetch_usd_per_aud(date(2016, 1, 1), end)

    fh_price = firsthand["btc"].dropna()
    cm_price = coinmetrics["PriceUSD"].dropna()
    # Limit both to their common date span before building the weekly tape.
    common_start = max(fh_price.index.min(), cm_price.index.min())
    common_end = min(fh_price.index.max(), cm_price.index.max())
    fh_price = fh_price.loc[common_start:common_end]
    cm_price = cm_price.loc[common_start:common_end]
    price_observations = {
        "all_days": summarise_price_observations(fh_price, cm_price),
        "completed_sunday_signal_closes": summarise_price_observations(fh_price, cm_price, weekday=6),
        "next_monday_execution_closes": summarise_price_observations(fh_price, cm_price, weekday=0),
    }
    fh_rows = build_weekly_execution_rows(
        fh_price, fx, first_execution_date=date(2017, 1, 1)
    )
    cm_rows = build_weekly_execution_rows(
        cm_price, fx, first_execution_date=date(2017, 1, 1)
    )
    if [(r["signal_date"], r["execution_date"]) for r in fh_rows] != [
        (r["signal_date"], r["execution_date"]) for r in cm_rows
    ]:
        raise ValueError("BTC price sources do not produce identical weekly dates")

    all_comparisons = []
    for cash_yield in CASH_YIELDS:
        fh_results = rolling_104_week_comparison(
            fh_rows, floors_pct=CASH_FLOORS, cash_yield=cash_yield,
            threshold_sets=THRESHOLD_SETS,
        )
        cm_results = rolling_104_week_comparison(
            cm_rows, floors_pct=CASH_FLOORS, cash_yield=cash_yield,
            threshold_sets=THRESHOLD_SETS,
        )
        result = compare_replays(fh_results, cm_results)
        result["cash_yield_annual"] = cash_yield
        all_comparisons.append(result)

    output_dir.mkdir(parents=True, exist_ok=True)
    result_path = output_dir / "firsthand_v60_price_sensitivity.json"
    result_path.write_text(json.dumps(all_comparisons, indent=2) + "\n", encoding="utf-8")
    metadata = {
        "purpose": "Research-only paired V6.0 portfolio replay; not source approval",
        "retrieved_at_utc": retrieved,
        "firsthand_price_source": "Firsthand Bitcoin public daily BTC price series",
        "coinmetrics_price_source": "Coin Metrics Community PriceUSD",
        "common_btc_date_start": common_start.date().isoformat(),
        "common_btc_date_end": common_end.date().isoformat(),
        "firsthand_daily_observations": int(fh_price.notna().sum()),
        "coinmetrics_daily_observations": int(cm_price.notna().sum()),
        "firsthand_price_sha256": hashlib.sha256(fh_price.to_csv().encode()).hexdigest(),
        "coinmetrics_price_sha256": hashlib.sha256(cm_price.to_csv().encode()).hexdigest(),
        "fx_source": "Frankfurter USD/AUD inverted to USD per AUD",
        "fx_sha256": fx_hash,
        "matched_daily_price_comparison": price_observations,
        "weekly_signal": "Completed Sunday close / mean of previous 200 completed Sunday closes; signal Sunday excluded",
        "execution_proxy": "Next Monday BTC/USD daily close / latest USD per AUD observation on or before signal Sunday; not ASX:IBIT fill",
        "capital_aud": 510000,
        "initial_btc_fraction": 0.41,
        "cash_yield_scenarios": list(CASH_YIELDS),
        "cash_floors_pct_initial_cash": list(CASH_FLOORS),
        "threshold_sets": list(THRESHOLD_SETS),
        "policies": ["fixed_weekly", "baseline", "measured", "stepped", "aggressive"],
        "weekly_cap_pct_original_capital": 5.0,
        "btc_drag_annual": 0.0025,
        "buy_friction": 0.003,
        "fixed_fee_aud": 3.0,
        "cohort_length_weeks": 104,
        "cohorts_overlap": True,
        "limitations": [
            "Firsthand price history has unexplained historical outliers; this replay measures their downstream effect but does not explain them.",
            "Coin Metrics is a reference comparator, not ground truth.",
            "Overlapping 104-week cohorts are not independent observations.",
            "Execution is a BTC/AUD spot proxy, not an ASX:IBIT fill.",
            "No taxes, personal cash movements or IBIT tracking premium/discount.",
        ],
        "research_only": True,
        "production_inputs_changed": False,
        "notifications_changed": False,
        "artifact": result_path.name,
    }
    (output_dir / "metadata.json").write_text(json.dumps(metadata, indent=2) + "\n")
    return metadata


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", default="artifacts/firsthand_v60_price_sensitivity")
    args = parser.parse_args()
    print(json.dumps(build_report(Path(args.output_dir)), indent=2))


if __name__ == "__main__":
    main()
