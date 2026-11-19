"""Research-only 200WMA discount-tier dynamic DCA.

Signals use the latest completed Sunday BTC/USD close divided by the mean of
the PREVIOUS 200 completed weekly closes (the signal Sunday is excluded).
Hypothetical execution is the next Monday BTC/AUD spot proxy, never an IBIT fill.
No Power Law/risk field is read by the allocation or simulation path.
"""
from __future__ import annotations

import argparse
from datetime import date, timedelta, datetime, timezone
import json
import math
from pathlib import Path
from statistics import median

import pandas as pd

from engines.research import research_model as model
from engines.research import v59_causal_timing_horse_race as base

CAPITAL_AUD = 510_000.0
INITIAL_BTC_FRACTION = 0.41
CASH_YIELD = 0.05
CASH_YIELDS = (0.0, 0.05)  # zero-yield stress and AAA-like reference case
ETF_DRAG = 0.0025
BUY_FRICTION = 0.003
FIXED_FEE_AUD = 3.0
MAX_WEEKLY_CAPITAL_FRACTION = 0.05
MIN_TICKET_AUD = FIXED_FEE_AUD + 0.01
COOLDOWN_DAYS = 7
HORIZON_WEEKS = 104

# Every percentage is a fraction of the cash actually available immediately
# before that buy. These are hypotheses, not approved settings.
LADDERS = {
    "current_2_5pct": (0.025, 0.025, 0.025, 0.025),
    "A_measured": (0.025, 0.035, 0.050, 0.075),
    "B_stepped": (0.025, 0.050, 0.075, 0.100),
    "C_aggressive": (0.025, 0.075, 0.100, 0.150),
}
THRESHOLDS = (0.20, 0.25, 0.30)


def discount_pct(ratio_to_200wma: float) -> float:
    ratio = float(ratio_to_200wma)
    if not math.isfinite(ratio) or ratio <= 0:
        raise ValueError("A valid positive prior 200WMA ratio is required")
    return max(0.0, (1.0 - ratio) * 100.0)


def allocation_pct(ratio_to_200wma: float, ladder: tuple[float, ...]) -> float:
    """Return the cash percentage for the deepest reached discount tier."""
    if len(ladder) != 4 or any(not math.isfinite(float(x)) or not 0 < x <= 1
                               for x in ladder):
        raise ValueError("Ladder must contain four valid cash percentages")
    if any(float(b) < float(a) for a, b in zip(ladder, ladder[1:])):
        raise ValueError("Deeper discounts cannot reduce allocation")
    discount = discount_pct(ratio_to_200wma)
    tier = 0
    for index, threshold in enumerate(THRESHOLDS, start=1):
        if discount + 1e-12 >= threshold * 100.0:
            tier = index
    return float(ladder[tier])


def build_weekly_rows(btc: pd.DataFrame, fx: pd.Series) -> list[dict]:
    """Build prior-Sunday signal / next-Monday proxy rows without any risk inputs."""
    if btc is None or btc.empty or fx is None or fx.empty or "price" not in btc:
        raise ValueError("BTC price history and dated AUD/USD FX are required")
    prices = pd.to_numeric(btc["price"], errors="coerce").copy()
    prices.index = pd.to_datetime(prices.index, utc=True).floor("D")
    prices = prices.dropna().sort_index()
    fx = pd.to_numeric(fx, errors="coerce").dropna().copy()
    fx.index = pd.to_datetime(fx.index, utc=True).floor("D")
    fx = fx.sort_index()
    if prices.index.has_duplicates or fx.index.has_duplicates:
        raise ValueError("BTC and FX observations must have unique dates")
    weekly_close = prices.resample("W-SUN").last()
    # Shift by one completed week: signal Sunday's close is NOT in its WMA.
    prior_wma = weekly_close.rolling(200, min_periods=200).mean().shift(1)
    rows = []
    for monday in prices.index:
        if monday.weekday() != 0 or monday.date() < date(2017, 1, 1):
            continue
        sunday = monday - pd.Timedelta(days=1)
        if sunday not in prices.index:
            continue
        fx_pos = fx.index.searchsorted(sunday, side="right") - 1
        if fx_pos < 0:
            continue
        fx_day = fx.index[fx_pos]
        usd_per_aud = float(fx.iloc[fx_pos])
        if not (0 <= (monday - fx_day).days <= 5 and
                math.isfinite(usd_per_aud) and usd_per_aud > 0):
            continue
        wma = float(prior_wma.loc[sunday]) if sunday in prior_wma.index else math.nan
        sunday_close = float(prices.loc[sunday])
        monday_close = float(prices.loc[monday])
        if not all(math.isfinite(x) and x > 0 for x in (sunday_close, monday_close)):
            continue
        rows.append({
            "date": monday.date(), "signal_date": sunday.date(),
            "btc_price_aud": monday_close / usd_per_aud,
            "btc_usd_signal_close": sunday_close,
            "prior_200wma_usd": wma,
            "ratio_to_200wma": sunday_close / wma if math.isfinite(wma) and wma > 0 else math.nan,
            "usd_per_aud": usd_per_aud, "fx_date": fx_day.date(),
        })
    if len(rows) < 100:
        raise ValueError("Insufficient dated weekly BTC/FX history")
    return rows


def simulate(rows: list[dict], *, policy: str, capital: float = CAPITAL_AUD,
             cash_yield: float = CASH_YIELD, initial_btc_fraction: float = INITIAL_BTC_FRACTION,
             max_weekly_fraction: float = MAX_WEEKLY_CAPITAL_FRACTION) -> dict:
    """Self-financing 104-week replay with percentage-of-remaining-cash sizing."""
    if policy not in (*LADDERS, "fixed_weekly"):
        raise ValueError("Unknown policy")
    if len(rows) != HORIZON_WEEKS:
        raise ValueError("A complete 104-week cohort is required")
    if not (capital > 0 and 0 <= cash_yield < 1 and
            0 <= initial_btc_fraction <= 1 and 0 < max_weekly_fraction <= 1):
        raise ValueError("Invalid account or guardrail input")

    starting_cash = capital * (1.0 - initial_btc_fraction)
    cash = starting_cash
    first_price = float(rows[0]["btc_price_aud"])
    if not math.isfinite(first_price) or first_price <= 0:
        raise ValueError("Invalid first execution price")
    btc = capital * initial_btc_fraction / first_price
    last_buy_date = None
    buys = spent = net_btc_bought = net_cost = 0.0
    buy_count = 0
    peak = capital
    max_drawdown = 0.0
    previous_day = rows[0]["date"]
    biggest_buy = 0.0
    weekly_cap = capital * max_weekly_fraction

    for index, row in enumerate(rows):
        day = row["date"]
        if day != rows[0]["date"] + timedelta(weeks=index):
            raise ValueError("Missing or irregular weekly execution observation")
        if (day - row["signal_date"]).days != 1:
            raise ValueError("Signal must be the strictly previous Sunday")
        price = float(row["btc_price_aud"])
        if not math.isfinite(price) or price <= 0:
            raise ValueError("Invalid execution price")
        elapsed = (day - previous_day).days if index else 0
        if index and elapsed != 7:
            raise ValueError("Weekly observations must be seven days apart")
        cash *= (1.0 + cash_yield) ** (elapsed / 365.25)
        btc *= (1.0 - ETF_DRAG) ** (elapsed / 365.25)
        previous_day = day

        ratio = float(row["ratio_to_200wma"])
        if not math.isfinite(ratio) or ratio <= 0:
            raise ValueError("Missing strictly prior 200WMA; refusing fallback")
        if last_buy_date is not None and (day - last_buy_date).days < COOLDOWN_DAYS:
            target_pct = 0.0
        elif policy == "fixed_weekly":
            target_pct = min(1.0, starting_cash / HORIZON_WEEKS / max(cash, 1e-12))
        else:
            target_pct = allocation_pct(ratio, LADDERS[policy])

        target_spend = cash * target_pct
        spend = min(cash, target_spend, weekly_cap)
        if spend >= MIN_TICKET_AUD and spend > FIXED_FEE_AUD:
            net = (spend - FIXED_FEE_AUD) * (1.0 - BUY_FRICTION)
            cash -= spend
            btc += net / price
            net_btc_bought += net / price
            net_cost += net
            spent += spend
            buys += spend
            buy_count += 1
            biggest_buy = max(biggest_buy, spend)
            last_buy_date = day

        equity = cash + btc * price
        peak = max(peak, equity)
        max_drawdown = min(max_drawdown, equity / peak - 1.0)
        if cash < -1e-6 or btc < 0 or spend > weekly_cap + 1e-6:
            raise AssertionError("Capital guardrail violated")

    terminal_price = float(rows[-1]["btc_price_aud"])
    equity = cash + btc * terminal_price
    # Hindsight-only timing diagnostic: same gross spend AND same number
    # of transactions, but equal-sized buys spread across the full period.
    uniform_btc_units = 0.0
    if buy_count:
        uniform_gross_per_buy = spent / buy_count
        uniform_net_per_buy = max(0.0, uniform_gross_per_buy - FIXED_FEE_AUD) * (1.0 - BUY_FRICTION)
        if buy_count == 1:
            uniform_indices = [len(rows) // 2]
        else:
            uniform_indices = [
                round(k * (len(rows) - 1) / (buy_count - 1))
                for k in range(buy_count)
            ]
        uniform_btc_units = sum(
            uniform_net_per_buy / float(rows[i]["btc_price_aud"])
            for i in uniform_indices
        )
    same_spend_btc_uplift = (
        100.0 * (net_btc_bought / uniform_btc_units - 1.0)
        if uniform_btc_units > 0 else 0.0
    )
    return {
        "policy": policy,
        "equity_aud": equity,
        "btc_units": btc,
        "terminal_btc_equivalent": btc + cash / terminal_price,
        "cash_aud": cash,
        "spent_aud": spent,
        "deployed_pct_initial_cash": 100.0 * spent / starting_cash if starting_cash else 0.0,
        "remaining_cash_pct_initial_cash": 100.0 * cash / starting_cash if starting_cash else 0.0,
        "buy_count": buy_count,
        "biggest_buy_pct_original_capital": 100.0 * biggest_buy / capital,
        "average_net_entry_aud": net_cost / net_btc_bought if net_btc_bought else None,
        "new_btc_bought_before_drag": net_btc_bought,
        "same_spend_uniform_btc_units_hindsight": uniform_btc_units,
        "same_spend_btc_timing_uplift_pct_hindsight": same_spend_btc_uplift,
        "max_drawdown_pct": 100.0 * max_drawdown,
    }


def evaluate(rows: list[dict], *, capital: float = CAPITAL_AUD) -> dict:
    windows = base.cohort_windows(rows)
    trials = []
    for cohort in windows:
        for cash_yield in CASH_YIELDS:
            for policy in (*LADDERS, "fixed_weekly"):
                result = simulate(cohort["rows"], policy=policy, capital=capital,
                                  cash_yield=cash_yield)
                trials.append({k: cohort[k] for k in ("anchor", "start", "end", "split")} |
                              {"cash_yield_annual": cash_yield} | result)
    lookup = {(r["anchor"], r["cash_yield_annual"], r["policy"]): r for r in trials}
    for result in trials:
        control = lookup[(result["anchor"], result["cash_yield_annual"], "current_2_5pct")]
        result["equity_uplift_vs_current_pct"] = 100.0 * (
            result["equity_aud"] / control["equity_aud"] - 1.0)
        result["btc_equivalent_uplift_vs_current_pct"] = 100.0 * (
            result["terminal_btc_equivalent"] / control["terminal_btc_equivalent"] - 1.0)

    summary = []
    for split in ("TRAIN", "HISTORICAL_HOLDOUT"):
      for cash_yield in CASH_YIELDS:
        for policy in (*LADDERS, "fixed_weekly"):
            selected = [r for r in trials if r["split"] == split and
                        r["cash_yield_annual"] == cash_yield and r["policy"] == policy]
            if not selected:
                continue
            summary.append({
                "split": split, "cash_yield_annual": cash_yield, "policy": policy, "cohorts": len(selected),
                "median_equity_uplift_vs_current_pct": median(
                    r["equity_uplift_vs_current_pct"] for r in selected),
                "worst_equity_uplift_vs_current_pct": min(
                    r["equity_uplift_vs_current_pct"] for r in selected),
                "positive_equity_cohorts": sum(
                    r["equity_uplift_vs_current_pct"] > 0 for r in selected),
                "median_btc_equivalent_uplift_vs_current_pct": median(
                    r["btc_equivalent_uplift_vs_current_pct"] for r in selected),
                "worst_btc_equivalent_uplift_vs_current_pct": min(
                    r["btc_equivalent_uplift_vs_current_pct"] for r in selected),
                "median_deployed_pct_initial_cash": median(
                    r["deployed_pct_initial_cash"] for r in selected),
                "median_remaining_cash_pct_initial_cash": median(
                    r["remaining_cash_pct_initial_cash"] for r in selected),
                "median_drawdown_pct": median(r["max_drawdown_pct"] for r in selected),
                "median_same_spend_btc_timing_uplift_pct_hindsight": median(
                    r["same_spend_btc_timing_uplift_pct_hindsight"] for r in selected),
                "median_buy_count": median(r["buy_count"] for r in selected),
            })
    return {
        "status": "RESEARCH_ONLY_RETROSPECTIVE_NOT_LIVE",
        "signal": "Prior Sunday BTC/USD close / mean of previous 200 completed Sunday closes",
        "execution": "Next Monday BTC/AUD spot proxy; not ASX:IBIT fills",
        "allocation_denominator": "Available AUD cash immediately before each hypothetical buy",
        "weekly_hard_cap": "5% of original contributed capital",
        "minimum_ticket_aud": MIN_TICKET_AUD,
        "cooldown_calendar_days": COOLDOWN_DAYS,
        "cash_yield_scenarios_annual": list(CASH_YIELDS),
        "initial_btc_fraction": INITIAL_BTC_FRACTION,
        "weekly_rows": len(rows),
        "completed_cohorts": len(windows),
        "candidate_ladders": {k: list(v) for k, v in LADDERS.items()},
        "summary": summary,
        "cohort_results": trials,
        "limitations": [
            "Historical BTC/AUD spot is a proxy, not executable ASX:IBIT pricing.",
            "Historical provider publication vintages are not independently attested.",
            "Jan/July two-year cohorts overlap and are not independent cycles.",
            "Candidate thresholds were proposed after reviewing BTC history; holdout is not pristine.",
            "Same-spend equal-sized/equal-transaction-count BTC comparison is a hindsight attribution diagnostic, not a deployable policy.",
            "Cash yield, ETF drag, spread and fee assumptions are illustrative.",
            "No Production, live V5.9, portfolio, dashboard, notification, brokerage or order changes.",
        ],
    }


def fetch_and_evaluate() -> dict:
    now = datetime.now(timezone.utc)
    start = model.RESEARCH_PL_HISTORY_START.to_pydatetime()
    btc = model.fetch_btc_history(start, now)
    fx = model.fetch_aud_usd_rates(start, now)
    if btc is None or btc.empty or fx is None or fx.empty:
        raise RuntimeError("BTC/FX history unavailable; refusing synthetic fallback")
    rows = build_weekly_rows(btc, fx)
    return evaluate(rows)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", type=Path,
                        default=Path("artifacts/v59_200wma_distance_dynamic_dca.json"))
    args = parser.parse_args()
    try:
        report = fetch_and_evaluate()
    except Exception as exc:
        report = {"status": "RESEARCH_RUN_BLOCKED", "error_type": type(exc).__name__,
                  "error": str(exc), "no_promotion_or_trade_authorisation": True}
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(report, indent=2, default=str, allow_nan=False) + "\n")
    print(json.dumps({
        "status": report.get("status"),
        "weekly_rows": report.get("weekly_rows"),
        "completed_cohorts": report.get("completed_cohorts"),
        "summary": report.get("summary"),
        "error": report.get("error"),
    }, default=str))
    return 0 if report.get("status") != "RESEARCH_RUN_BLOCKED" else 2


if __name__ == "__main__":
    raise SystemExit(main())
