"""Build reproducible V6.0 matched 104-week BTC/AUD cohort results.

Uses only the dated BTC/USD Price column from the archived October-2026
BGeometrics MVRV export plus Frankfurter historical USD/AUD observations.
No V5.9 or Production imports. Outputs are research-only, not trading signals.
"""
from __future__ import annotations

import argparse
from datetime import date
import hashlib
import json
from pathlib import Path

import pandas as pd
import requests

from engines.research.v60_200wma_backtest import (
    build_weekly_execution_rows, rolling_104_week_comparison,
)

ROOT = Path(__file__).resolve().parents[2]
BTC_FILE = ROOT / "data" / "mvrv_z_score_2026-10-06T21-46-14.csv"
HOLDOUT_START = date(2022, 1, 1)
CASH_YIELDS = (0.0, 0.05)
CASH_FLOORS = (0.0, 10.0, 20.0, 30.0)


def load_btc_daily(path: Path = BTC_FILE) -> tuple[pd.Series, str, str]:
    raw = path.read_bytes()
    frame = pd.read_csv(path)
    if not {"timestamp", "Price"}.issubset(frame.columns):
        raise ValueError("BTC export must contain timestamp and Price columns")
    frame["date"] = pd.to_datetime(
        pd.to_numeric(frame["timestamp"], errors="coerce"),
        unit="ms", utc=True, errors="coerce",
    ).dt.normalize()
    frame["Price"] = pd.to_numeric(frame["Price"], errors="coerce")
    frame = frame.dropna(subset=["date", "Price"]).sort_values("date")
    if frame["date"].duplicated().any() or frame["Price"].le(0).any():
        raise ValueError("BTC export has duplicate dates or invalid prices")
    series = frame.set_index("date")["Price"].astype(float)
    if len(series) < 200 * 7:
        raise ValueError("BTC export does not contain 200 completed weekly closes")
    return series, hashlib.sha256(raw).hexdigest(), str(series.index[-1].date())


def fetch_usd_per_aud(start: date, end: date) -> tuple[pd.Series, str]:
    url = f"https://api.frankfurter.app/{start.isoformat()}..{end.isoformat()}"
    response = requests.get(
        url, params={"from": "USD", "to": "AUD"}, timeout=45,
        headers={"User-Agent": "BTC-Composite-V6.0-Research/1.0"},
    )
    response.raise_for_status()
    payload = response.json()
    rates = payload.get("rates", {})
    if not rates:
        raise ValueError("Frankfurter returned no historical USD/AUD rates")
    values = {}
    for day, quote in rates.items():
        aud_per_usd = float(quote["AUD"])
        if aud_per_usd <= 0:
            raise ValueError("Invalid Frankfurter USD/AUD rate")
        values[pd.Timestamp(day, tz="UTC")] = 1.0 / aud_per_usd
    fx = pd.Series(values, name="usd_per_aud").sort_index()
    if fx.index.has_duplicates:
        raise ValueError("Duplicate Frankfurter FX dates")
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    return fx, hashlib.sha256(canonical).hexdigest()


def assign_validation_split(row: dict) -> str:
    start = date.fromisoformat(row["cohort_start"])
    end = date.fromisoformat(row["cohort_end"])
    if end < HOLDOUT_START:
        return "train"
    if start >= HOLDOUT_START:
        return "holdout"
    return "bridge_excluded"


def discount_activation_counts(weekly_rows: list[dict]) -> dict:
    """Count distinct completed signal weeks reaching each 200WMA discount."""
    periods = {
        "pre_2022_train_era": [
            r for r in weekly_rows
            if r["execution_date"] < HOLDOUT_START
        ],
        "2022_onward_holdout_era": [
            r for r in weekly_rows
            if r["execution_date"] >= HOLDOUT_START
        ],
    }
    result = {}
    for period, rows in periods.items():
        counts = {}
        for threshold in (10, 15, 20, 25, 30):
            hits = [
                r for r in rows
                if float(r["ratio_to_200wma"]) <= 1.0 - threshold / 100.0
            ]
            counts[f"at_least_{threshold}_pct_below_200wma"] = {
                "signal_week_count": len(hits),
                "execution_dates": sorted(
                    str(r["execution_date"]) for r in hits
                ),
                "calendar_years": sorted({
                    r["execution_date"].year for r in hits
                }),
            }
        result[period] = counts
    return result


def summarise(results: list[dict]) -> pd.DataFrame:
    frame = pd.DataFrame(results)
    if frame.empty:
        raise ValueError("No matched cohort results were produced")
    frame["split"] = frame.apply(lambda r: assign_validation_split(r.to_dict()), axis=1)
    fixed = {
        (float(r.cash_yield), float(r.protected_cash_floor_pct_initial_cash),
         str(r.cohort_start)): r
        for r in frame.itertuples(index=False) if r.policy == "fixed_weekly"
    }
    rows = []
    primary = frame.loc[frame["split"].isin(["train", "holdout"])]
    for (split, yield_pct, floor, threshold_set, policy), group in primary.groupby(
        ["split", "cash_yield", "protected_cash_floor_pct_initial_cash", "threshold_set", "policy"]
    ):
        peers = [fixed[(float(yield_pct), float(floor), str(r.cohort_start))]
                 for r in group.itertuples(index=False)]
        equity_uplifts = [
            100.0 * (float(r.final_equity_aud) / float(peer.final_equity_aud) - 1.0)
            for r, peer in zip(group.itertuples(index=False), peers)
        ]
        btc_uplifts = [
            100.0 * (float(r.btc_held) / float(peer.btc_held) - 1.0)
            for r, peer in zip(group.itertuples(index=False), peers)
        ]
        rows.append({
            "split": split,
            "cash_yield_annual_pct": float(yield_pct) * 100.0,
            "protected_cash_floor_pct_initial_cash": float(floor),
            "policy": policy,
            "threshold_set": threshold_set,
            "cohort_count": int(len(group)),
            "median_final_equity_aud": float(group["final_equity_aud"].median()),
            "median_btc_held": float(group["btc_held"].median()),
            "median_cash_remaining_aud": float(group["cash_remaining_aud"].median()),
            "median_total_buy_spend_aud": float(group["total_buy_spend_aud"].median()),
            "median_buy_count": float(group["buy_count"].median()),
            "median_max_drawdown_pct": float(group["max_drawdown_pct"].median()),
            "median_final_equity_uplift_vs_fixed_weekly_pct": float(pd.Series(equity_uplifts).median()),
            "median_btc_uplift_vs_fixed_weekly_pct": float(pd.Series(btc_uplifts).median()),
            "cohort_win_rate_final_equity_vs_fixed_weekly_pct": 100.0 * sum(x > 0 for x in equity_uplifts) / len(equity_uplifts),
            "cohort_win_rate_btc_vs_fixed_weekly_pct": 100.0 * sum(x > 0 for x in btc_uplifts) / len(btc_uplifts),
            "median_same_spend_timing_uplift_pct_hindsight": float(
                group["same_spend_same_count_btc_timing_uplift_pct_hindsight"].median()
            ),
            "cohorts_overlap": True,
            "interpretation": "Overlapping rolling cohorts; descriptive robustness only, not independent trials",
        })
    return pd.DataFrame(rows).sort_values(
        ["split", "cash_yield_annual_pct", "protected_cash_floor_pct_initial_cash", "threshold_set", "policy"]
    ).reset_index(drop=True)


def build_report(output_dir: Path) -> dict:
    btc, btc_hash, btc_end = load_btc_daily()
    fx_start = date(2016, 1, 1)
    fx_end = pd.Timestamp(btc.index[-1]).date()
    fx, fx_hash = fetch_usd_per_aud(fx_start, fx_end)
    weekly = build_weekly_execution_rows(
        btc, fx, first_execution_date=date(2017, 1, 1)
    )
    all_results = []
    for cash_yield in CASH_YIELDS:
        cohort_results = rolling_104_week_comparison(
            weekly, floors_pct=CASH_FLOORS, cash_yield=cash_yield,
            threshold_sets=("20_25_30", "10_15_20"),
        )
        for row in cohort_results:
            row["cash_yield"] = cash_yield
            row["split"] = assign_validation_split(row)
            all_results.append(row)
    cohort_frame = pd.DataFrame(all_results)
    summary_frame = summarise(all_results)
    output_dir.mkdir(parents=True, exist_ok=True)
    cohort_path = output_dir / "v60_104_week_cohort_results.csv"
    summary_path = output_dir / "v60_train_holdout_summary.csv"
    metadata_path = output_dir / "v60_research_metadata.json"
    cohort_frame.to_csv(cohort_path, index=False)
    summary_frame.to_csv(summary_path, index=False)
    metadata = {
        "model_version": "V6.0",
        "research_only": True,
        "trade_executable": False,
        "btc_source": BTC_FILE.name,
        "btc_export_sha256": btc_hash,
        "btc_last_observation_date": btc_end,
        "btc_export_caveat": "October-2026 historical export; not a contemporaneous point-in-time vintage and may contain retrospective revisions",
        "fx_source": "Frankfurter historical rates API",
        "fx_base_quote": "USD/AUD inverted to USD per AUD",
        "fx_sha256": fx_hash,
        "fx_start": fx_start.isoformat(),
        "fx_end": fx_end.isoformat(),
        "first_execution_date": "2017-01-01",
        "signal_definition": "Completed Sunday BTC/USD close divided by mean of previous 200 completed Sunday closes; signal Sunday excluded",
        "execution_proxy": "Next Monday BTC/USD daily close divided by latest USD/AUD FX observation on or before signal Sunday; not ASX:IBIT fill",
        "cohort_window_weeks": 104,
        "cohort_step_weeks": 1,
        "train_rule": "Cohort end date before 2022-01-01",
        "bridge_rule": "Cohorts spanning 2022-01-01 excluded from primary train and holdout summaries",
        "holdout_rule": "Cohort start date on or after 2022-01-01",
        "cohorts_overlap": True,
        "overlap_warning": "Adjacent 104-week windows overlap heavily and are not independent observations",
        "cash_yields_annual": list(CASH_YIELDS),
        "protected_cash_floors_pct_initial_cash": list(CASH_FLOORS),
        "policies": ["fixed_weekly", "baseline", "measured", "stepped", "aggressive"],
        "threshold_sets_tested": {
            "20_25_30": [20.0, 25.0, 30.0],
            "10_15_20": [10.0, 15.0, 20.0],
        },
        "account_assumptions": {
            "capital_aud": 510000.0,
            "initial_btc_fraction": 0.41,
            "btc_drag_annual": 0.0025,
            "buy_friction": 0.003,
            "fixed_fee_aud": 3.0,
            "weekly_cap_pct_original_capital": 5.0,
        },
        "discount_activation_counts": discount_activation_counts(weekly),
        "unmodelled_factors": [
            "ASX:IBIT tracking premium/discount and intraday execution timing",
            "Actual ASX brokerage, bid/ask spread and market impact beyond the generic friction assumption",
            "Tax on cash yield, ETF distributions and realised capital gains",
            "Personal contributions, withdrawals and actual portfolio cash movements",
        ],
        "cash_yield_caveat": "0% and 5% gross annual scenarios; the 5% case is not guaranteed and is not tax-adjusted",
        "btc_drag_caveat": "0.25% annual generic holding drag; this is a modelling assumption, not an observed ASX:IBIT tracking result",
        "cohort_count_total": int(len(cohort_frame)),
        "summary_rows": int(len(summary_frame)),
        "artifacts": [cohort_path.name, summary_path.name, metadata_path.name],
    }
    metadata_path.write_text(json.dumps(metadata, indent=2), encoding="utf-8")
    return metadata


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", default="artifacts/v60_historical")
    args = parser.parse_args()
    metadata = build_report(Path(args.output_dir))
    print(json.dumps(metadata, indent=2))


if __name__ == "__main__":
    main()
