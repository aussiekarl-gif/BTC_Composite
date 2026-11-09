"""Exploratory, matched BTC/AUD spot proxy: 1x, 2x, 3x risk-gated DCA.

No access to provider publication vintages: imported 'Walk-forward Power Law'
scores may be retrospectively revised, and are NOT Production V5.8.2 or V5.9
composite risk. This is NOT a verified executable trading backtest.

Input: private btc-audit-data/btc_audit_backup.csv or same-schema local export.
Never uploads its raw records or writes a portfolio/notification.
All trade decisions use the PRIOR weekly risk row, executed at the NEXT
weekly BTC/AUD observation. Results are matched on cash, dates and cost.
"""
from __future__ import annotations

import argparse
import csv
import json
import math
from datetime import date
from pathlib import Path

from engines.research.v59_dynamic_risk_policy import risk_buy_multiplier

INITIAL_CAPITAL_AUD = 500_000.0
SOURCE_LABEL = "Walk-forward Power Law"
PERIOD_STARTS = (2016, 2018, 2020, 2022, 2024, 2026)


def load_proxy_weekly(path: Path) -> list[dict]:
    rows = []
    with Path(path).open("r", encoding="utf-8-sig", newline="") as stream:
        reader = csv.DictReader(stream)
        expected = {"date", "btc_price_aud", "risk_score", "risk_score_source"}
        if not expected.issubset(reader.fieldnames or []):
            raise ValueError(f"Missing columns {sorted(expected - set(reader.fieldnames or []))}")
        for line, entry in enumerate(reader, 2):
            if not entry["btc_price_aud"] or not entry["risk_score"]:
                continue
            source = entry["risk_score_source"]
            if source != SOURCE_LABEL:
                raise ValueError(f"Line {line}: unexpected risk source {source!r}")
            day = date.fromisoformat(entry["date"][:10])
            price, risk = float(entry["btc_price_aud"]), float(entry["risk_score"])
            if not (math.isfinite(price) and price > 0 and math.isfinite(risk)
                    and 0 <= risk <= 1):
                raise ValueError(f"Line {line}: invalid proxy price or risk")
            if rows and (day - rows[-1]["date"]).days != 7:
                raise ValueError(f"Line {line}: missing, repeated or unsorted weekly dates")
            rows.append({"date": day, "btc_price_aud": price,
                         "risk_score": risk, "risk_score_source": source})
    if len(rows) < 2:
        raise ValueError("At least two adjacent weekly observations required")
    return rows


def simulate(
    rows: list[dict], *,
    capital_aud: float,
    reserve_aud: float,
    review_date: date,
    policy: str,
    weekly_cap_fraction: float = 0.05,
    variable_cost_fraction: float = 0.003,
    flat_fee_aud: float = 3.0,
) -> dict:
    """Execute with previous-week risk, next-week price, cash-funded trades.

    Policies: risk_1x, risk_2x, risk_3x, plain_weekly, lump_next_week.
    Pacing is based on deployable remaining cash / weeks to review; no
    forced investment, no sales, no leverage, no unsupported IBIT fills.
    """
    permitted = {"risk_1x": 1., "risk_2x": 2., "risk_3x": 3.,
                 "plain_weekly": None, "lump_next_week": None}
    if policy not in permitted:
        raise ValueError(f"Invalid policy {policy}")
    nums = (capital_aud, reserve_aud, weekly_cap_fraction,
            variable_cost_fraction, flat_fee_aud)
    if not all(math.isfinite(v) for v in nums):
        raise ValueError("Nonfinite financial parameter")
    if not (capital_aud > 0 and 0 <= reserve_aud <= capital_aud
            and 0 < weekly_cap_fraction <= 1 and 0 <= variable_cost_fraction < 1
            and 0 <= flat_fee_aud < capital_aud):
        raise ValueError("Invalid financial parameters")
    if len(rows) < 2 or not isinstance(review_date, date):
        raise ValueError("Invalid history or review date")
    cash, btc, paid_costs = capital_aud, 0., 0.
    peak, worst_dd, orders = capital_aud, 0., 0
    first_fill, last_fill = None, None
    for i in range(1, len(rows)):
        prior, obs = rows[i-1], rows[i]
        day, prior_day = obs["date"], prior["date"]
        if not (isinstance(day, date) and isinstance(prior_day, date)
                and (day - prior_day).days == 7):
            raise ValueError("Execution must follow exactly seven days after signal")
        # No current-week risk or price is used to determine trade size.
        risk, price = float(prior["risk_score"]), float(obs["btc_price_aud"])
        if not (math.isfinite(risk) and 0 <= risk <= 1
                and math.isfinite(price) and price > 0):
            raise ValueError("Nonfinite or invalid dated historical observation")
        available = max(0., cash - reserve_aud)
        if policy.startswith("risk_"):
            weeks_left = max((review_date - day).days / 7., 1.)
            multiplier = min(risk_buy_multiplier(risk), permitted[policy])
            spend = min(available, available / weeks_left * multiplier,
                        capital_aud * weekly_cap_fraction)
        elif policy == "plain_weekly":
            spend = min(available, (capital_aud - reserve_aud) / (len(rows) - 1))
        else:
            spend = available if i == 1 else 0.
        if spend > flat_fee_aud + 0.01:
            cash -= spend
            # Variable transaction cost includes the assumed spread/slippage
            # proxy: applied once after flat fee, identical for every policy.
            net_aud = (spend - flat_fee_aud) * (1 - variable_cost_fraction)
            btc += net_aud / price
            paid_costs += spend - net_aud
            orders += 1
            if first_fill is None:
                first_fill = day.isoformat()
            last_fill = day.isoformat()
        equity = cash + btc * price
        peak = max(peak, equity)
        worst_dd = min(worst_dd, equity / peak - 1.)
        if cash + 1e-7 < reserve_aud or btc < 0:
            raise ArithmeticError("Cash reserve or BTC holdings violated")
    terminal_price = float(rows[-1]["btc_price_aud"])
    return {
        "btc_held": btc,
        "cash_aud": cash,
        "invested_aud": capital_aud - cash,
        "equity_aud": cash + btc * terminal_price,
        "worst_drawdown_pct": worst_dd * 100.,
        "filled_orders": orders,
        "total_cost_aud": paid_costs,
        "first_fill_date": first_fill,
        "last_fill_date": last_fill,
        "equity_after_immediate_50pct_btc_drop_aud":
            cash + btc * terminal_price * 0.5,
    }


def compare_windows(
    weekly: list[dict], *,
    capital_aud: float = INITIAL_CAPITAL_AUD,
    reserves: tuple[float, ...] = (0., 100_000.),
    fee_aud: float = 3.,
    variable_cost_fraction: float = 0.003,
    weekly_cap_fraction: float = 0.05,
) -> dict:
    results = {}
    for start_year in PERIOD_STARTS:
        subset = [r for r in weekly
                  if start_year <= r["date"].year < start_year + 2]
        if len(subset) < 2:
            continue
        completed = subset[-1]["date"].year == start_year + 1 and (
            subset[-1]["date"].month == 12 and subset[-1]["date"].day >= 24)
        review = subset[-1]["date"] if completed else date(start_year + 1, 12, 31)
        key = f"{start_year}-{start_year+1}" + ("" if completed else "-PARTIAL")
        period = {
            "start": subset[0]["date"].isoformat(),
            "last_observation": subset[-1]["date"].isoformat(),
            "weeks": len(subset),
            "completed_window": completed,
            "review_date": review.isoformat(),
            "risk_source": SOURCE_LABEL,
            "prior_observation_executions": len(subset) - 1,
            "risk_below_or_equal_half_weeks":
                sum(risk_buy_multiplier(r["risk_score"]) > 0 for r in subset[:-1]),
            "reserves": {},
        }
        for reserve in reserves:
            sims = {
                name: simulate(
                    subset, capital_aud=capital_aud, reserve_aud=reserve,
                    review_date=review, policy=name,
                    variable_cost_fraction=variable_cost_fraction,
                    flat_fee_aud=fee_aud,
                    weekly_cap_fraction=weekly_cap_fraction)
                for name in ("risk_1x", "risk_2x", "risk_3x",
                             "plain_weekly", "lump_next_week")
            }
            base, alt = sims["risk_1x"], sims["risk_3x"]
            sims["aggressive_vs_1x"] = {
                "btc_uplift_pct": (100. * (alt["btc_held"] / base["btc_held"] - 1)
                                   if base["btc_held"] else None),
                "equity_uplift_pct": 100. * (alt["equity_aud"] / base["equity_aud"] - 1),
                "worst_drawdown_increase_pp":
                    alt["worst_drawdown_pct"] - base["worst_drawdown_pct"],
            }
            period["reserves"][str(int(reserve))] = sims
        results[key] = period
    return {
        "status": "EXPLORATORY_RETROSPECTIVE_RISK_PROVENANCE_UNVERIFIED",
        "data_source": "btc-audit-data/btc_audit_backup.csv (private input, not embedded)",
        "risk_source": SOURCE_LABEL,
        "not_production_v582_or_v59": True,
        "not_historical_asx_ibit_executions": True,
        "not_verified_point_in_time_provider_vintages": True,
        "fees": {"fixed_aud_per_order": fee_aud,
                 "variable_cost_fraction_per_fill": variable_cost_fraction},
        "capital_aud": capital_aud,
        "weekly_cap_fraction_of_initial_capital": weekly_cap_fraction,
        "first_observation": weekly[0]["date"].isoformat(),
        "last_observation": weekly[-1]["date"].isoformat(),
        "source_rows": len(weekly),
        "method": "Risk known on prior weekly row; next weekly BTC/AUD spot proxy execution. No future signal data in decisions.",
        "caveats": [
            "Historical risk scores are retrospectively stored Power Law proxy, not full Production composite.",
            "Original provider publication times, historical vintages and revisions are not independently verified.",
            "No ASX:IBIT executable spreads, fund tracking differences, FX settlement, or SMSF taxes.",
            "Two-year disjoint calendar windows are not independent BTC economic regimes.",
            "The partial 2026 window stops when observations end and uses December 2027 review.",
            "50% BTC shock is mechanical mark-to-market only: no new trades or predicted path.",
            "These examples cannot authorize any live production, Streamlit or ntfy sizing change.",
        ],
        "windows": results,
    }


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--csv", type=Path, required=True)
    p.add_argument("--out", type=Path)
    args = p.parse_args()
    report = compare_windows(load_proxy_weekly(args.csv))
    output = json.dumps(report, indent=2, allow_nan=False)
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(output + "\n", encoding="utf-8")
    print(output)


if __name__ == "__main__":
    main()
