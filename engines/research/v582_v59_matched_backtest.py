"""Matched V5.8.2 vs V5.9 weekly BTC/AUD backtest (research only).

Both versions receive identical dated BTC closes, strictly prior AUD/USD FX,
Monday execution dates, starting cash, weekly cap, costs, cash yield and review
horizon. V5.8.2 is a reconstructed Production composite proxy (BTC + exported
MVRV; historical Fear & Greed/provider vintages unavailable). V5.9 is the
current BTC-only walk-forward Power Law risk used when optional specialist
inputs are unavailable. Neither historical series is a verified as-published
provider vintage. No Production, portfolio, broker or notification writes.
"""
from __future__ import annotations

import argparse
from datetime import date, timedelta
import json
from pathlib import Path

import numpy as np
import pandas as pd

from engines.production.production_model import (
    SMART_DCA_POINTS as PROD_LADDER,
    risk_band_multiplier as prod_multiplier,
)
from engines.research import research_model
from engines.research.v59_live_signal_snapshot import live_risk_params
from engines.research.top_signal_horse_race import read_exported_history
from engines.research.production_causal_budget_audit import (
    build_production_risk_from_archived_provider,
)
from engines.research.v59_causal_timing_horse_race import (
    build_weekly_rows, cohort_windows, CAPITAL_AUD, WEEKS,
)

CASH_YIELD = 0.05
WEEKLY_CAP = 0.05
FEE_AUD = 3.0
BUY_FRICTION = 0.003
ANNUAL_DRAG = 0.0025
ARCHIVE_CUTOFF = pd.Timestamp("2026-10-05", tz="UTC")


def _fx_before(fx: pd.Series, day: pd.Timestamp) -> float:
    fx = pd.to_numeric(fx, errors="coerce").dropna().sort_index()
    pos = fx.index.searchsorted(day, side="right") - 1
    if pos < 0:
        raise ValueError("No prior AUD/USD fixing for execution")
    fx_day = pd.Timestamp(fx.index[pos])
    if (day - fx_day).days > 5:
        raise ValueError("AUD/USD fixing is stale; refusing FX fallback")
    value = float(fx.iloc[pos])
    if not np.isfinite(value) or value <= 0:
        raise ValueError("Invalid prior AUD/USD fixing")
    return value


def build_matched_rows(history: pd.DataFrame, fx: pd.Series) -> list[dict]:
    """Score both models on the same dated price observations, then match fills."""
    if not isinstance(history.index, pd.DatetimeIndex):
        raise ValueError("Historical indicators require a DatetimeIndex")
    h = history.sort_index().copy()
    h.index = pd.to_datetime(h.index, utc=True).floor("D")
    h = h.loc[:ARCHIVE_CUTOFF]
    if h.index.has_duplicates or not h.index.is_monotonic_increasing:
        raise ValueError("Historical observations must be unique and ordered")
    prod = build_production_risk_from_archived_provider(h)
    price = pd.to_numeric(h["price_usd"], errors="coerce")
    research_input = pd.DataFrame({
        "price": price,
        "mvrv_z": pd.to_numeric(h["mvrv_z"], errors="coerce"),
        "fear_greed": np.nan,
        "regime_score": np.nan,
    }, index=h.index)
    research = research_model.add_risk_indicators(
        research_input, "Research WF Power Law", live_risk_params()
    )
    # Reuse the existing strict Sunday-signal / next-Monday execution builder.
    rows = build_weekly_rows(research, fx)
    matched = []
    for row in rows:
        signal_day = pd.Timestamp(row["signal_date"], tz="UTC")
        pscore = float(prod.loc[signal_day, "risk_score"])
        rscore = float(row["risk_score"])
        if not (np.isfinite(pscore) and 0 <= pscore <= 1
                and np.isfinite(rscore) and 0 <= rscore <= 1):
            continue
        execution_day = pd.Timestamp(row["date"], tz="UTC")
        expected_aud = float(price.loc[execution_day]) / _fx_before(fx, execution_day)
        if not np.isclose(expected_aud, float(row["btc_price_aud"]), rtol=1e-10, atol=1e-8):
            raise AssertionError("Model rows do not share the same BTC/AUD execution price")
        matched.append({
            **row,
            "v582_risk": pscore,
            "v59_risk": rscore,
            "v582_components": int(prod.loc[signal_day, "risk_components_available"]),
        })
    if len(matched) < 104:
        raise ValueError("Insufficient common weekly observations for a matched study")
    return matched


def replay(rows: list[dict], *, risk_key: str, capital: float = CAPITAL_AUD,
           cash_yield: float = CASH_YIELD, fixed_weekly: bool = False) -> dict:
    """Causal self-financing replay; each signal is dated before its Monday fill."""
    if len(rows) != WEEKS:
        raise ValueError(f"Expected exactly {WEEKS} weekly observations")
    if risk_key not in {"v582_risk", "v59_risk"} and not fixed_weekly:
        raise ValueError("Unknown risk series")
    dates = [r["date"] for r in rows]
    if any((b-a).days != 7 for a, b in zip(dates, dates[1:])):
        raise ValueError("Missing or irregular Monday execution")
    cash, btc, invested, fees, fills = float(capital), 0.0, 0.0, 0.0, 0
    peak, max_dd = float(capital), 0.0
    previous = dates[0]
    orders = []
    for i, row in enumerate(rows):
        day = row["date"]
        if (day - row["signal_date"]).days != 1:
            raise ValueError("Execution must follow the previous Sunday's signal")
        elapsed = 0 if i == 0 else (day - previous).days
        cash *= (1.0 + cash_yield) ** (elapsed / 365.25)
        btc *= (1.0 - ANNUAL_DRAG) ** (elapsed / 365.25)
        previous = day
        price = float(row["btc_price_aud"])
        if not np.isfinite(price) or price <= 0:
            raise ValueError("Invalid execution price")
        risk = None if fixed_weekly else float(row[risk_key])
        if fixed_weekly:
            multiplier = 1.0
        else:
            if not np.isfinite(risk) or not 0 <= risk <= 1:
                raise ValueError("Missing or invalid prior risk")
            multiplier = float(prod_multiplier(PROD_LADDER, risk))
        weeks_left = max((pd.Timestamp(row["review_date"]) - pd.Timestamp(day)).days / 7.0, 1.0)
        allowance = float(capital) / WEEKS if fixed_weekly else cash / weeks_left * multiplier
        spend = min(cash, allowance, capital * WEEKLY_CAP)
        net = max(0.0, spend - FEE_AUD) * (1.0 - BUY_FRICTION)
        if spend > FEE_AUD:
            cash -= spend
            btc += net / price
            invested += spend
            fees += spend - net
            fills += 1
        equity = cash + btc * price
        peak = max(peak, equity)
        max_dd = max(max_dd, (peak - equity) / peak if peak else 0.0)
        orders.append({
            "date": day.isoformat(), "risk": risk, "multiplier": multiplier,
            "buy_aud": round(spend, 2), "btc_held": btc,
            "cash_aud": cash, "equity_aud": equity,
        })
    terminal_price = float(rows[-1]["btc_price_aud"])
    final_equity = cash + btc * terminal_price
    return {
        "final_equity_aud": round(final_equity, 2),
        "btc_accumulated": round(btc, 10),
        "btc_equivalent": round(btc + cash / terminal_price, 10),
        "cash_remaining_aud": round(cash, 2),
        "cash_remaining_pct": round(100.0 * cash / capital, 2),
        "capital_deployed_aud": round(invested, 2),
        "fills": fills,
        "fees_and_slippage_aud": round(fees, 2),
        "max_drawdown_pct": round(100.0 * max_dd, 2),
        "orders": orders,
    }


def evaluate(rows: list[dict], *, capital: float = CAPITAL_AUD) -> dict:
    research_ladder = tuple(tuple(map(float, point))
                             for point in research_model.SMART_DCA_POINTS)
    production_ladder = tuple(tuple(map(float, point)) for point in PROD_LADDER)
    if research_ladder != production_ladder:
        raise ValueError("V5.8.2 and V5.9 default ladders differ; matched default-ladder comparison is invalid")
    windows = cohort_windows(rows)
    trials = []
    for window in windows:
        cohort = [dict(r, review_date=window["review_date"]) for r in window["rows"]]
        results = {
            "V5.8.2": replay(cohort, risk_key="v582_risk", capital=capital),
            "V5.9": replay(cohort, risk_key="v59_risk", capital=capital),
            "Fixed weekly DCA": replay(cohort, risk_key="v59_risk", capital=capital, fixed_weekly=True),
        }
        base = results["V5.8.2"]
        for name, result in results.items():
            trials.append({
                "anchor": window["anchor"], "split": window["split"],
                "start": window["start"], "end": window["end"],
                "strategy": name, **{k: v for k, v in result.items() if k != "orders"},
                "equity_vs_v582_pct": 100.0 * (result["final_equity_aud"] / base["final_equity_aud"] - 1.0),
                "btc_vs_v582_pct": 100.0 * (result["btc_equivalent"] / base["btc_equivalent"] - 1.0),
            })
    summaries = []
    for split in ("TRAIN", "BRIDGE_EXCLUDED", "HISTORICAL_HOLDOUT"):
        for name in ("V5.8.2", "V5.9", "Fixed weekly DCA"):
            subset = [r for r in trials if r["split"] == split and r["strategy"] == name]
            if not subset:
                continue
            summaries.append({
                "split": split, "strategy": name, "cohorts": len(subset),
                "median_final_equity_aud": round(float(np.median([r["final_equity_aud"] for r in subset])), 2),
                "median_btc_accumulated": float(np.median([r["btc_accumulated"] for r in subset])),
                "median_btc_equivalent": float(np.median([r["btc_equivalent"] for r in subset])),
                "median_cash_remaining_pct": float(np.median([r["cash_remaining_pct"] for r in subset])),
                "median_drawdown_pct": float(np.median([r["max_drawdown_pct"] for r in subset])),
                "median_fills": float(np.median([r["fills"] for r in subset])),
                "median_equity_vs_v582_pct": float(np.median([r["equity_vs_v582_pct"] for r in subset])),
                "worst_equity_vs_v582_pct": min(r["equity_vs_v582_pct"] for r in subset),
                "wins_vs_v582": sum(r["equity_vs_v582_pct"] > 0 for r in subset),
            })
    return {
        "status": "RESEARCH_ONLY_MATCHED_RETROSPECTIVE_PROXY",
        "no_promotion_or_trade_authorisation": True,
        "production_modified": False,
        "starting_capital_aud": capital,
        "matched_execution": "Prior Sunday UTC risk; next Monday UTC BTC/AUD spot proxy; same date/price/FX for both versions",
        "risk_inputs": {
            "V5.8.2": "Reconstructed Production composite: BTC price, exported MVRV-Z and price-derived components; historical Fear & Greed omitted",
            "V5.9": "Walk-forward Power Law residual risk from the same BTC price series; optional specialist inputs unavailable",
        },
        "shared_assumptions": {
            "default_risk_ladder": [[float(x), float(y)] for x, y in PROD_LADDER],
            "cash_yield_annual": CASH_YIELD, "weekly_cap_fraction_initial": WEEKLY_CAP,
            "flat_fee_aud": FEE_AUD, "buy_friction_fraction": BUY_FRICTION,
            "annual_btc_drag": ANNUAL_DRAG, "sells_enabled": False,
            "taxes_included": False,
        },
        "weekly_observations": len(rows), "completed_cohorts": len(windows),
        "summary": summaries, "cohorts": trials,
        "limitations": [
            "V5.8.2 is not an exact historical live composite: Fear & Greed and point-in-time MVRV/provider vintages are unavailable.",
            "V5.9 walk-forward parameters and historical public data vintages were not independently frozen at each past date.",
            "Both strategies use the same default in-repository multiplier ladder; custom browser-saved curves are not available to this reproducible run.",
            "BTC/AUD spot closes are not ASX:IBIT executable prices; ETF history did not exist for early cohorts.",
            "Five percent cash yield, 0.30% buy friction, A$3 fee and 0.25% annual drag are illustrative assumptions, not verified historical returns/costs.",
            "No SMSF tax, AAA distribution tax, broker settlement or actual portfolio holdings are simulated.",
            "Jan/Jul 104-week cohorts overlap; they are not independent cycles. Historical holdout is retrospective, not untouched.",
        ],
    }


def fetch_and_evaluate() -> dict:
    history = read_exported_history()
    history.index = pd.to_datetime(history.index, utc=True)
    history = history.loc[:ARCHIVE_CUTOFF]
    if history.empty:
        raise RuntimeError("No archived BTC/onchain history")
    fx = research_model.fetch_aud_usd_rates(
        history.index.min().to_pydatetime(), history.index.max().to_pydatetime()
    )
    if fx is None or fx.empty:
        raise RuntimeError("Historical FX unavailable; refusing fallback")
    btc = research_model.fetch_btc_history(
        research_model.RESEARCH_PL_HISTORY_START.to_pydatetime(),
        ARCHIVE_CUTOFF.to_pydatetime(),
    )
    if btc is None or btc.empty:
        raise RuntimeError("Historical BTC price series unavailable")
    btc.index = pd.to_datetime(btc.index, utc=True).floor("D")
    history = history.join(btc[["price"]].rename(columns={"price": "_provider_price"}), how="inner")
    # Keep the MVRV export's price only after independently checking it against
    # the contemporaneous public BTC history; reject materially mismatched feeds.
    gap = (history["price_usd"] / history["_provider_price"] - 1.0).abs()
    if gap.dropna().empty or float(gap.dropna().max()) > 0.01:
        raise RuntimeError("Archived MVRV and BTC price exports fail 1% parity check")
    history = history.drop(columns=["_provider_price"])
    rows = build_matched_rows(history, fx)
    report = evaluate(rows)
    report["input_dates"] = {
        "first_common_history": str(history.index.min().date()),
        "last_common_history": str(history.index.max().date()),
        "fx_first": str(fx.index.min().date()), "fx_last": str(fx.index.max().date()),
    }
    return report


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", type=Path, default=Path("artifacts/v582_v59_matched_backtest.json"))
    args = parser.parse_args()
    report = fetch_and_evaluate()
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(report, indent=2, allow_nan=False) + "\n")
    print(json.dumps({
        "status": report["status"], "weekly_observations": report["weekly_observations"],
        "completed_cohorts": report["completed_cohorts"], "summary": report["summary"],
        "limitations": report["limitations"],
    }, indent=2, allow_nan=False))


if __name__ == "__main__":
    main()
