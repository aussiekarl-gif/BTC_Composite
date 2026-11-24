"""V6.0 independent weekly BTC/AUD DCA replay and matched-cohort harness.

No V5.9 or Production imports. Uses a strictly prior 200WMA signal and a
next-Monday BTC/AUD spot proxy. The proxy is not an ASX:IBIT fill.
"""
from __future__ import annotations

from datetime import date, timedelta
import math
from statistics import median

import pandas as pd

from engines.research.v60_200wma_policy import (
    CANDIDATE_LADDERS, DISCOUNT_THRESHOLDS_PCT, THRESHOLD_SETS,
    allocation_for_discount, weekly_prior_200wma_signals,
)

DEFAULT_CAPITAL_AUD = 510_000.0
DEFAULT_INITIAL_BTC_FRACTION = 0.41
DEFAULT_CASH_YIELD = 0.05
DEFAULT_BTC_DRAG_ANNUAL = 0.0025
DEFAULT_BUY_FRICTION = 0.003
DEFAULT_FIXED_FEE_AUD = 3.0
DEFAULT_WEEKLY_CAP_PCT_ORIGINAL_CAPITAL = 5.0
DEFAULT_MIN_TICKET_AUD = 100.0
COHORT_WEEKS = 104


def _normalise_series(series: pd.Series, label: str) -> pd.Series:
    if not isinstance(series, pd.Series) or series.empty:
        raise ValueError(f"{label} Series is required")
    out = pd.to_numeric(series, errors="coerce").dropna().copy()
    out.index = pd.to_datetime(out.index, utc=True).floor("D")
    out = out.sort_index()
    if out.index.has_duplicates:
        raise ValueError(f"{label} dates must be unique")
    if not out.map(math.isfinite).all() or (out <= 0).any():
        raise ValueError(f"{label} values must be finite and positive")
    return out


def build_weekly_execution_rows(
    daily_btc_usd: pd.Series,
    daily_usd_per_aud: pd.Series,
    *,
    first_execution_date: date = date(2017, 1, 1),
) -> list[dict]:
    """Create Sunday-signal / next-Monday BTC/AUD proxy rows from dated closes.

    FX is the latest observation on or before the signal Sunday (max age 5d),
    avoiding use of a later Monday FX close. BTC execution proxy is the Monday
    BTC/USD close divided by that prior FX rate.
    """
    btc = _normalise_series(daily_btc_usd, "Daily BTC/USD")
    fx = _normalise_series(daily_usd_per_aud, "Daily USD/AUD")
    signals = weekly_prior_200wma_signals(btc)
    rows = []
    for signal in signals.itertuples(index=False):
        sunday = pd.Timestamp(signal.signal_date)
        if pd.isna(signal.prior_200wma_usd) or not math.isfinite(float(signal.ratio_to_200wma)):
            continue
        monday = sunday + pd.Timedelta(days=1)
        if monday.date() < first_execution_date or monday not in btc.index:
            continue
        fx_pos = fx.index.searchsorted(sunday, side="right") - 1
        if fx_pos < 0:
            continue
        fx_date = fx.index[fx_pos]
        usd_per_aud = float(fx.iloc[fx_pos])
        if (sunday - fx_date).days < 0 or (sunday - fx_date).days > 5:
            continue
        price_aud = float(btc.loc[monday]) / usd_per_aud
        if not math.isfinite(price_aud) or price_aud <= 0:
            continue
        rows.append({
            "signal_date": sunday.date(),
            "execution_date": monday.date(),
            "btc_usd_signal_close": float(signal.btc_usd_sunday_close),
            "prior_200wma_usd": float(signal.prior_200wma_usd),
            "ratio_to_200wma": float(signal.ratio_to_200wma),
            "discount_below_200wma_pct": float(signal.discount_below_200wma_pct),
            "btc_price_aud": price_aud,
            "fx_date": fx_date.date(),
            "usd_per_aud": usd_per_aud,
        })
    if len(rows) < COHORT_WEEKS:
        raise ValueError("Insufficient dated weekly BTC/FX history for a 104-week cohort")
    return rows


def validate_weekly_cohort(rows: list[dict]) -> None:
    if len(rows) != COHORT_WEEKS:
        raise ValueError("A complete 104-week cohort is required")
    for i, row in enumerate(rows):
        execution = row["execution_date"]
        signal = row["signal_date"]
        if (execution - signal).days != 1 or signal.weekday() != 6 or execution.weekday() != 0:
            raise ValueError("Each execution must follow its strictly prior Sunday signal")
        if i and (execution - rows[i-1]["execution_date"]).days != 7:
            raise ValueError("Weekly cohort has a missing or irregular observation")
        ratio = float(row["ratio_to_200wma"])
        price = float(row["btc_price_aud"])
        if not math.isfinite(ratio) or ratio <= 0 or not math.isfinite(price) or price <= 0:
            raise ValueError("Invalid prior 200WMA ratio or BTC/AUD execution proxy")


def _prior_week_momentum_nonnegative(rows: list[dict], execution_index: int) -> bool:
    """Use only the two completed weekly observations before this execution.

    The current row is the execution-price proxy and is deliberately excluded
    from the decision. Insufficient prior history fails closed.
    """
    if execution_index < 2:
        return False
    latest_completed = float(rows[execution_index - 1]["btc_price_aud"])
    previous_completed = float(rows[execution_index - 2]["btc_price_aud"])
    return latest_completed >= previous_completed


def simulate_weekly_cohort(
    rows: list[dict],
    *,
    policy: str = "measured",
    capital_aud: float = DEFAULT_CAPITAL_AUD,
    initial_btc_fraction: float = DEFAULT_INITIAL_BTC_FRACTION,
    cash_yield: float = DEFAULT_CASH_YIELD,
    btc_drag_annual: float = DEFAULT_BTC_DRAG_ANNUAL,
    protected_cash_floor_pct_initial_cash: float = 0.0,
    weekly_cap_pct_original_capital: float = DEFAULT_WEEKLY_CAP_PCT_ORIGINAL_CAPITAL,
    buy_friction: float = DEFAULT_BUY_FRICTION,
    fixed_fee_aud: float = DEFAULT_FIXED_FEE_AUD,
    min_ticket_aud: float = DEFAULT_MIN_TICKET_AUD,
    thresholds: tuple[float, float, float] = DISCOUNT_THRESHOLDS_PCT,
    threshold_set: str = "20_25_30",
    max_cumulative_buy_spend_pct_initial_cash: float | None = None,
    dynamic_allocation_scale: float = 1.0,
    require_nonnegative_weekly_momentum: bool = False,
) -> dict:
    """Replay one 104-week cohort with cash yield, BTC drag and buy friction.

    dynamic_allocation_scale proportionally scales every V6.0 candidate tier.
    A value of 0.5 halves the normal and discount-tier cash percentages; it
    does not change fixed weekly DCA, the 5% original-capital weekly hard cap,
    the protected reserve or the cumulative spend cap.
    """
    validate_weekly_cohort(rows)
    if policy not in (*CANDIDATE_LADDERS, "fixed_weekly"):
        raise ValueError("Unknown V6.0 policy")
    if threshold_set not in (*THRESHOLD_SETS, "none"):
        raise ValueError("Unknown V6.0 discount threshold set")
    if policy in ("fixed_weekly", "baseline"):
        threshold_set = "none"
    numeric = (capital_aud, initial_btc_fraction, cash_yield, btc_drag_annual,
               protected_cash_floor_pct_initial_cash, weekly_cap_pct_original_capital,
               buy_friction, fixed_fee_aud, min_ticket_aud, dynamic_allocation_scale)
    if not all(math.isfinite(float(x)) for x in numeric):
        raise ValueError("Simulation inputs must be finite")
    if capital_aud <= 0 or not 0 <= initial_btc_fraction <= 1:
        raise ValueError("Invalid capital or initial BTC fraction")
    if cash_yield < 0 or btc_drag_annual < 0 or not 0 <= buy_friction < 1:
        raise ValueError("Invalid yield, BTC drag or buy friction")
    if not 0 <= protected_cash_floor_pct_initial_cash < 100:
        raise ValueError("Protected cash floor must be in [0, 100)")
    if not 0 < weekly_cap_pct_original_capital <= 100:
        raise ValueError("Weekly cap must be in (0, 100]")
    if fixed_fee_aud < 0 or min_ticket_aud < 0:
        raise ValueError("Fees and minimum ticket cannot be negative")
    if not 0 < dynamic_allocation_scale <= 3.0:
        raise ValueError("Dynamic allocation scale must be in (0, 3]")
    if max_cumulative_buy_spend_pct_initial_cash is not None:
        cap_pct = float(max_cumulative_buy_spend_pct_initial_cash)
        if not math.isfinite(cap_pct) or not 0 <= cap_pct <= 100:
            raise ValueError("Cumulative spend cap must be between 0 and 100% of initial cash")

    initial_cash = capital_aud * (1.0 - initial_btc_fraction)
    cash = initial_cash
    reserve = initial_cash * protected_cash_floor_pct_initial_cash / 100.0
    first_price = float(rows[0]["btc_price_aud"])
    btc = capital_aud * initial_btc_fraction / first_price
    starting_equity = capital_aud
    weekly_cap = capital_aud * weekly_cap_pct_original_capital / 100.0
    fixed_weekly_spend = max(0.0, initial_cash - reserve) / COHORT_WEEKS
    cumulative_budget = (
        initial_cash * float(max_cumulative_buy_spend_pct_initial_cash) / 100.0
        if max_cumulative_buy_spend_pct_initial_cash is not None else None
    )
    total_spend = 0.0
    net_btc_bought = 0.0
    buy_count = 0
    biggest_buy = 0.0
    peak_equity = starting_equity
    max_drawdown = 0.0
    previous_date = rows[0]["execution_date"]
    execution_prices = []
    actual_buy_dates = []

    for i, row in enumerate(rows):
        day = row["execution_date"]
        price = float(row["btc_price_aud"])
        elapsed = (day - previous_date).days if i else 0
        if i and elapsed != 7:
            raise ValueError("Weekly observations must be seven days apart")
        cash *= (1.0 + cash_yield) ** (elapsed / 365.25)
        btc *= (1.0 - btc_drag_annual) ** (elapsed / 365.25)
        previous_date = day
        execution_prices.append(price)

        deployable = max(0.0, cash - reserve)
        if policy == "fixed_weekly":
            target_spend = fixed_weekly_spend
        else:
            pct = allocation_for_discount(
                float(row["ratio_to_200wma"]), candidate=policy, thresholds=thresholds
            )
            # Decide before the current row's execution: use only the two
            # most recent completed weekly observations. Never inspect the
            # current execution-price proxy when selecting its own tier.
            if require_nonnegative_weekly_momentum and not _prior_week_momentum_nonnegative(rows, i):
                pct = 2.5
            target_spend = deployable * pct * dynamic_allocation_scale / 100.0
        remaining_cumulative_budget = (
            max(0.0, cumulative_budget - total_spend)
            if cumulative_budget is not None else float("inf")
        )
        spend = min(deployable, target_spend, weekly_cap, remaining_cumulative_budget)
        if spend >= min_ticket_aud and spend > fixed_fee_aud:
            net_consideration = (spend - fixed_fee_aud) * (1.0 - buy_friction)
            units = net_consideration / price
            cash -= spend
            btc += units
            total_spend += spend
            net_btc_bought += units
            buy_count += 1
            biggest_buy = max(biggest_buy, spend)
            actual_buy_dates.append(day)

        equity = cash + btc * price
        peak_equity = max(peak_equity, equity)
        max_drawdown = min(max_drawdown, equity / peak_equity - 1.0)
        if cash < reserve - 1e-6 or btc < 0 or spend > weekly_cap + 1e-6:
            raise AssertionError("V6.0 cash reserve or weekly capital guardrail violated")
        if cumulative_budget is not None and total_spend > cumulative_budget + 1e-6:
            raise AssertionError("V6.0 cumulative buy budget violated")

    terminal_price = execution_prices[-1]
    final_equity = cash + btc * terminal_price
    uniform_btc_bought = 0.0
    if buy_count:
        uniform_gross = total_spend / buy_count
        uniform_net = max(0.0, uniform_gross - fixed_fee_aud) * (1.0 - buy_friction)
        if buy_count == 1:
            indices = [len(execution_prices) // 2]
        else:
            indices = [round(k * (len(execution_prices)-1) / (buy_count-1))
                       for k in range(buy_count)]
        uniform_btc_bought = sum(uniform_net / execution_prices[j] for j in indices)
    same_spend_timing_uplift = (
        100.0 * (net_btc_bought / uniform_btc_bought - 1.0)
        if uniform_btc_bought > 0 else 0.0
    )
    return {
        "model_version": "V6.0",
        "policy": policy,
        "dynamic_allocation_scale": float(dynamic_allocation_scale),
        "require_nonnegative_weekly_momentum": bool(require_nonnegative_weekly_momentum),
        "threshold_set": threshold_set,
        "discount_thresholds_pct": list(thresholds) if threshold_set != "none" else [],
        "cohort_start": rows[0]["execution_date"].isoformat(),
        "cohort_end": rows[-1]["execution_date"].isoformat(),
        "observations": len(rows),
        "starting_equity_aud": starting_equity,
        "final_equity_aud": final_equity,
        "total_return_pct": 100.0 * (final_equity / starting_equity - 1.0),
        "btc_held": btc,
        "cash_remaining_aud": cash,
        "total_buy_spend_aud": total_spend,
        "buy_count": buy_count,
        "biggest_buy_aud": biggest_buy,
        "biggest_buy_pct_original_capital": 100.0 * biggest_buy / capital_aud,
        "protected_cash_floor_pct_initial_cash": protected_cash_floor_pct_initial_cash,
        "protected_cash_floor_aud": reserve,
        "max_cumulative_buy_spend_pct_initial_cash": max_cumulative_buy_spend_pct_initial_cash,
        "max_cumulative_buy_budget_aud": cumulative_budget,
        "cumulative_buy_budget_remaining_aud": (
            max(0.0, cumulative_budget - total_spend) if cumulative_budget is not None else None
        ),
        "max_drawdown_pct": 100.0 * max_drawdown,
        "same_spend_same_count_btc_timing_uplift_pct_hindsight": same_spend_timing_uplift,
        "research_only": True,
        "trade_executable": False,
        "execution_proxy": "next_Monday_BTC_AUD_spot_close_not_ASX_IBIT_fill",
    }


def rolling_104_week_comparison(
    rows: list[dict],
    *,
    floors_pct: tuple[float, ...] = (0.0, 10.0, 20.0, 30.0),
    cash_yield: float = DEFAULT_CASH_YIELD,
    threshold_sets: tuple[str, ...] = ("20_25_30",),
) -> list[dict]:
    """Compare fixed DCA/base policy and V6.0 candidate threshold sets.

    Fixed weekly DCA and the 2.5% base policy are emitted once per cohort;
    only the measured/stepped/aggressive ladders are repeated for each
    threshold set, avoiding duplicate benchmark rows.
    """
    if len(rows) < COHORT_WEEKS:
        raise ValueError("At least 104 weekly rows are required")
    for floor in floors_pct:
        if not 0 <= floor < 100:
            raise ValueError("Cash floors must be in [0, 100)")
    if not threshold_sets or any(x not in THRESHOLD_SETS for x in threshold_sets):
        raise ValueError("Unknown or empty V6.0 threshold-set selection")
    policies = ("measured", "stepped", "aggressive")
    results = []
    for start in range(0, len(rows) - COHORT_WEEKS + 1):
        cohort = rows[start:start+COHORT_WEEKS]
        validate_weekly_cohort(cohort)
        for floor in floors_pct:
            results.append(simulate_weekly_cohort(
                cohort, policy="fixed_weekly", cash_yield=cash_yield,
                protected_cash_floor_pct_initial_cash=floor, threshold_set="none",
            ))
            results.append(simulate_weekly_cohort(
                cohort, policy="baseline", cash_yield=cash_yield,
                protected_cash_floor_pct_initial_cash=floor, threshold_set="none",
            ))
            for threshold_name in threshold_sets:
                for name in policies:
                    results.append(simulate_weekly_cohort(
                        cohort, policy=name, cash_yield=cash_yield,
                        protected_cash_floor_pct_initial_cash=floor,
                        thresholds=THRESHOLD_SETS[threshold_name],
                        threshold_set=threshold_name,
                    ))
    return results

def summarise_matched_cohorts(results: list[dict]) -> list[dict]:
    """Summarise overlapping cohort results; they are not independent samples."""
    grouped: dict[tuple[str, float], list[dict]] = {}
    for row in results:
        key = (str(row["policy"]), float(row["protected_cash_floor_pct_initial_cash"]), str(row.get("threshold_set", "20_25_30")))
        grouped.setdefault(key, []).append(row)
    summary = []
    for (policy, floor, threshold_set), rows in sorted(grouped.items()):
        summary.append({
            "policy": policy,
            "threshold_set": threshold_set,
            "protected_cash_floor_pct_initial_cash": floor,
            "cohort_count": len(rows),
            "median_final_equity_aud": median(r["final_equity_aud"] for r in rows),
            "median_btc_held": median(r["btc_held"] for r in rows),
            "median_cash_remaining_aud": median(r["cash_remaining_aud"] for r in rows),
            "median_total_buy_spend_aud": median(r["total_buy_spend_aud"] for r in rows),
            "median_buy_count": median(r["buy_count"] for r in rows),
            "median_max_drawdown_pct": median(r["max_drawdown_pct"] for r in rows),
            "median_same_spend_timing_uplift_pct_hindsight": median(
                r["same_spend_same_count_btc_timing_uplift_pct_hindsight"] for r in rows
            ),
            "overlapping_cohorts_not_independent": True,
        })
    return summary
