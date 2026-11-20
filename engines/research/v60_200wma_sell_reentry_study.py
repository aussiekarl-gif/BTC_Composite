"""V6.0 research-only buy/sell/re-entry studies on the weekly execution tape.

Extends the independent harness in engines.research.v60_200wma_backtest and
v60_200wma_policy; there is no V5.9 or Production import and no parallel model.

Every study replays matched rolling 104-week cohorts (validated by
validate_weekly_cohort) against an explicit fixed_weekly DCA benchmark
(simulate_weekly_cohort). Sell/re-entry semantics:

- "return_to_200wma_sell_then_discount_reentry": while holding, sell when the
  prior-200WMA ratio reaches sell_ratio (default 1.0: the price returns to the
  prior WMA); re-enter only when the ratio falls back to reentry_ratio
  (default 0.90) or below.
- "return_to_200wma_sell_then_immediate_reentry": the same sell; re-enter on
  the next ladder buy regardless of the ratio.
- "take_profit_sell_then_discount_reentry" and
  "take_profit_sell_then_immediate_reentry": while holding, sell when the cost
  basis gains take_profit_pct (default 10%); re-entry rules as above.

While holding, each week stacks the candidate ladder buy (the same
percentage-first discipline as the base harness); the 5% original-capital
weekly hard cap, the min-ticket/fee floor and the optional protected-cash floor
from the base harness apply as guardrails. Strictly prior signals: every ratio
is the ratio_to_200wma computed by weekly_prior_200wma_signals, where the
signal week is excluded from its own moving average and execution is the
following Monday close.

All outputs carry research_only=True and trade_executable=False; these are
research diagnostics only, never executable trades and no trading edge.
"""
from __future__ import annotations

import math
from statistics import median

from engines.research.v60_200wma_backtest import (
    COHORT_WEEKS, DEFAULT_BTC_DRAG_ANNUAL, DEFAULT_BUY_FRICTION,
    DEFAULT_CAPITAL_AUD, DEFAULT_CASH_YIELD, DEFAULT_FIXED_FEE_AUD,
    DEFAULT_INITIAL_BTC_FRACTION, DEFAULT_MIN_TICKET_AUD,
    DEFAULT_WEEKLY_CAP_PCT_ORIGINAL_CAPITAL, simulate_weekly_cohort,
    validate_weekly_cohort,
)
from engines.research.v60_200wma_policy import (
    DISCOUNT_THRESHOLDS_PCT, THRESHOLD_SETS, allocation_for_discount,
)

BENCHMARK_POLICY = "fixed_weekly"
DEFAULT_SELL_RATIO = 1.0
DEFAULT_TAKE_PROFIT_PCT = 10.0
DEFAULT_REENTRY_RATIO = 0.90
STUDY_NAMES = (
    "return_to_200wma_sell_then_discount_reentry",
    "return_to_200wma_sell_then_immediate_reentry",
    "take_profit_sell_then_discount_reentry",
    "take_profit_sell_then_immediate_reentry",
)


def study_spec(study: str) -> dict:
    """Resolve and validate a study name into its sell/re-entry semantics."""
    if study not in STUDY_NAMES:
        raise ValueError(f"Unknown V6.0 buy/sell/re-entry study: {study}")
    if study.startswith("return_to_200wma"):
        sell_rule = "return_to_200wma"
    else:
        sell_rule = "take_profit"
    reentry_rule = "immediate" if "immediate_reentry" in study else "discount_threshold"
    return {
        "study": study,
        "sell_rule": sell_rule,
        "reentry_rule": reentry_rule,
        "research_only": True,
        "trade_executable": False,
    }


def _median_or_none(values) -> float | None:
    vals = [float(v) for v in values if v is not None]
    if not vals:
        return None
    return float(median(vals))


def _finite(value, label: str) -> float:
    result = float(value)
    if not math.isfinite(result):
        raise ValueError(f"{label} must be finite")
    return result


def simulate_sell_reentry(
    rows: list[dict],
    *,
    study: str = "return_to_200wma_sell_then_discount_reentry",
    sell_fraction: float = 1.0,
    sell_ratio: float = DEFAULT_SELL_RATIO,
    take_profit_pct: float = DEFAULT_TAKE_PROFIT_PCT,
    reentry_ratio: float = DEFAULT_REENTRY_RATIO,
    candidate: str = "measured",
    thresholds: tuple[float, float, float] = DISCOUNT_THRESHOLDS_PCT,
    threshold_set: str = "20_25_30",
    capital_aud: float = DEFAULT_CAPITAL_AUD,
    initial_btc_fraction: float = DEFAULT_INITIAL_BTC_FRACTION,
    cash_yield: float = DEFAULT_CASH_YIELD,
    btc_drag_annual: float = DEFAULT_BTC_DRAG_ANNUAL,
    buy_friction: float = DEFAULT_BUY_FRICTION,
    fixed_fee_aud: float = DEFAULT_FIXED_FEE_AUD,
    min_ticket_aud: float = DEFAULT_MIN_TICKET_AUD,
    weekly_cap_pct_original_capital: float = DEFAULT_WEEKLY_CAP_PCT_ORIGINAL_CAPITAL,
    protected_cash_floor_pct_initial_cash: float = 0.0,
) -> dict:
    """Replay one matched 104-week cohort with a sell rule and re-entry gate.

    While holding, each week stacks the candidate ladder buy. While flat, the
    study buys only when its re-entry rule allows (discount-threshold gate) or
    always (immediate re-entry). Sellable: full position on a trigger.
    Guardrails: 5% original-capital weekly hard cap, min-ticket/fee floor and
    the protected-cash floor apply exactly as in the base harness.
    """
    spec = study_spec(study)
    validate_weekly_cohort(rows)
    sell_fraction = _finite(sell_fraction, "sell_fraction")
    sell_ratio = _finite(sell_ratio, "sell_ratio")
    take_profit_pct = _finite(take_profit_pct, "take_profit_pct")
    reentry_ratio = _finite(reentry_ratio, "reentry_ratio")
    if not 0 < sell_fraction <= 1:
        raise ValueError("sell_fraction must be in (0, 1]")
    if not 0 < sell_ratio < 10:
        raise ValueError("sell_ratio must be in (0, 10)")
    if spec["sell_rule"] == "return_to_200wma":
        if not 0 < reentry_ratio < sell_ratio:
            raise ValueError(
                "reentry_ratio must lie in (0, sell_ratio) for return_to_200wma studies"
            )
    elif not 0 < reentry_ratio <= 1:
        raise ValueError("reentry_ratio must be in (0, 1] for take_profit studies")
    if not 0 < take_profit_pct:
        raise ValueError("take_profit_pct must be positive")
    numeric = (capital_aud, initial_btc_fraction, cash_yield, btc_drag_annual,
               protected_cash_floor_pct_initial_cash, weekly_cap_pct_original_capital,
               buy_friction, fixed_fee_aud, min_ticket_aud)
    if not all(math.isfinite(float(x)) for x in numeric):
        raise ValueError("Simulation inputs must be finite")
    if capital_aud <= 0 or not 0 <= initial_btc_fraction <= 1:
        raise ValueError("Invalid capital or initial BTC fraction")
    if cash_yield < 0 or btc_drag_annual < 0 or not 0 <= buy_friction < 1:
        raise ValueError("Invalid yield, BTC drag or buy friction")
    if not 0 < weekly_cap_pct_original_capital <= 100:
        raise ValueError("Weekly cap must be in (0, 100]")
    if fixed_fee_aud < 0 or min_ticket_aud < 0:
        raise ValueError("Fees and minimum ticket cannot be negative")
    if not 0 <= protected_cash_floor_pct_initial_cash < 100:
        raise ValueError("Protected cash floor must be in [0, 100)")
    if threshold_set not in (*THRESHOLD_SETS, "none"):
        raise ValueError("Unknown V6.0 discount threshold set")
    if threshold_set != "none" and tuple(
        float(x) for x in thresholds
    ) != tuple(float(x) for x in THRESHOLD_SETS[threshold_set]):
        raise ValueError("threshold_set and thresholds must agree for matched studies")
    allocation_for_discount(1.0, candidate=candidate, thresholds=thresholds)

    initial_cash = capital_aud * (1.0 - initial_btc_fraction)
    cash = initial_cash
    reserve = initial_cash * protected_cash_floor_pct_initial_cash / 100.0
    first_price = float(rows[0]["btc_price_aud"])
    btc = capital_aud * initial_btc_fraction / first_price
    entry_price = None
    holding = False
    last_sell_date = None
    weekly_cap = capital_aud * weekly_cap_pct_original_capital / 100.0
    peak_equity = capital_aud
    max_drawdown = 0.0
    total_spend = 0.0
    buy_count = 0
    hold_weeks = 0
    flat_weeks = 0
    sales = []
    reentries = []
    weekly_spends = []
    execution_prices = []
    previous_date = rows[0]["execution_date"]

    for i, row in enumerate(rows):
        day = row["execution_date"]
        price = float(row["btc_price_aud"])
        ratio = float(row["ratio_to_200wma"])
        elapsed = (day - previous_date).days if i else 0
        if i and elapsed != 7:
            raise ValueError("Weekly observations must be seven days apart")
        cash *= (1.0 + cash_yield) ** (elapsed / 365.25)
        btc *= (1.0 - btc_drag_annual) ** (elapsed / 365.25)
        previous_date = day
        execution_prices.append(price)
        equity = cash + btc * price
        peak_equity = max(peak_equity, equity)
        max_drawdown = min(max_drawdown, equity / peak_equity - 1.0)

        # Sell: applies each week while holding, at the market price.
        should_sell = False
        if holding and btc > 1e-12:
            if spec["sell_rule"] == "return_to_200wma":
                should_sell = ratio >= sell_ratio
            elif entry_price and entry_price > 0:
                should_sell = (
                    (price - entry_price) / entry_price >= take_profit_pct / 100.0
                )
        if should_sell:
            sell_units = btc * sell_fraction
            realized = (
                100.0 * (price - entry_price) / entry_price
                if entry_price and entry_price > 0 else 0.0
            )
            cash += sell_units * price
            btc -= sell_units
            sales.append({
                "date": day,
                "price": price,
                "units_sold": sell_units,
                "realized_return_pct": realized,
                "reason": spec["sell_rule"],
            })
            last_sell_date = day
            if btc <= 1e-12:
                holding = False
                entry_price = None

        # Buy: ladder stack while holding; re-entry gate while flat.
        was_holding = holding
        if holding:
            hold_weeks += 1
            buy_gate = True
        else:
            flat_weeks += 1
            if spec["reentry_rule"] == "discount_threshold":
                buy_gate = ratio <= reentry_ratio
            else:
                buy_gate = True
        if not buy_gate:
            continue
        deployable = max(0.0, cash - reserve)
        pct = allocation_for_discount(
            ratio, candidate=candidate, thresholds=thresholds
        )
        spend = min(deployable * pct / 100.0, weekly_cap)
        if spend < min_ticket_aud or spend <= fixed_fee_aud or spend <= 0:
            continue
        net = (spend - fixed_fee_aud) * (1.0 - buy_friction)
        units = net / price
        new_btc = btc + units
        if btc > 1e-12 and entry_price and entry_price > 0:
            entry_price = (btc * entry_price + units * price) / new_btc
        elif units > 0:
            entry_price = price
        cash -= spend
        btc = new_btc
        if btc > 1e-12 and not was_holding:
            holding = True
        total_spend += spend
        buy_count += 1
        weekly_spends.append(spend)
        if not was_holding and last_sell_date is not None:
            reentries.append({
                "date": day,
                "price": price,
                "weeks_after_sell": (day - last_sell_date).days / 7.0,
            })
        if cash < reserve - 1e-6 or btc < 0 or spend > weekly_cap + 1e-6:
            raise AssertionError("V6.0 cash reserve or weekly capital guardrail violated")

    final_price = execution_prices[-1]
    final_equity = cash + btc * final_price
    starting_equity = capital_aud
    study_total_return = 100.0 * (final_equity / starting_equity - 1.0)
    benchmark = simulate_weekly_cohort(
        rows, policy=BENCHMARK_POLICY, cash_yield=cash_yield,
        protected_cash_floor_pct_initial_cash=protected_cash_floor_pct_initial_cash,
        buy_friction=buy_friction, fixed_fee_aud=fixed_fee_aud,
        min_ticket_aud=min_ticket_aud,
        weekly_cap_pct_original_capital=weekly_cap_pct_original_capital,
        capital_aud=capital_aud, initial_btc_fraction=initial_btc_fraction,
    )
    benchmark_total_return = 100.0 * (
        benchmark["final_equity_aud"] / benchmark["starting_equity_aud"] - 1.0
    )
    return {
        "model_version": "V6.0",
        "study": spec["study"],
        "sell_rule": spec["sell_rule"],
        "reentry_rule": spec["reentry_rule"],
        "candidate": candidate,
        "threshold_set": threshold_set,
        "discount_thresholds_pct": list(thresholds) if threshold_set != "none" else [],
        "sell_fraction": sell_fraction,
        "sell_ratio": sell_ratio,
        "take_profit_pct": take_profit_pct,
        "reentry_ratio": reentry_ratio,
        "protected_cash_floor_pct_initial_cash": protected_cash_floor_pct_initial_cash,
        "cohort_start": rows[0]["execution_date"].isoformat(),
        "cohort_end": rows[-1]["execution_date"].isoformat(),
        "observations": len(rows),
        "starting_equity_aud": starting_equity,
        "final_equity_aud": final_equity,
        "total_return_pct": study_total_return,
        "btc_held": btc,
        "cash_remaining_aud": cash,
        "total_buy_spend_aud": total_spend,
        "buy_count": buy_count,
        "sales_count": len(sales),
        "round_trips": len(reentries),
        "hold_weeks": hold_weeks,
        "flat_weeks": flat_weeks,
        "weeks_holding_fraction": hold_weeks / len(rows),
        "median_realized_sell_return_pct": _median_or_none(
            [r["realized_return_pct"] for r in sales]
        ),
        "median_reentry_weeks_after_sell": _median_or_none(
            [r["weeks_after_sell"] for r in reentries]
        ),
        "final_position_unrealised_return_pct": (
            100.0 * (final_price - entry_price) / entry_price
            if holding and entry_price and entry_price > 0 else 0.0
        ),
        "biggest_weekly_spend_aud": max(weekly_spends) if weekly_spends else 0.0,
        "biggest_weekly_spend_pct_original_capital": (
            100.0 * max(weekly_spends) / weekly_cap if weekly_spends else 0.0
        ),
        "max_drawdown_pct": 100.0 * max_drawdown,
        "benchmark_policy": BENCHMARK_POLICY,
        "benchmark_fixed_weekly": benchmark,
        "delta_total_return_pct": study_total_return - benchmark_total_return,
        "research_only": True,
        "trade_executable": False,
    }


def roll_sell_reentry_cohorts(
    rows: list[dict],
    *,
    study: str = "return_to_200wma_sell_then_discount_reentry",
    floors_pct: tuple[float, ...] = (0.0,),
    threshold_sets: tuple[str, ...] = ("20_25_30",),
    **study_kwargs,
) -> list[dict]:
    """Replay matched rolling 104-week cohorts; overlaps are disclosed."""
    if len(rows) < COHORT_WEEKS:
        raise ValueError("At least 104 weekly rows are required")
    for floor in floors_pct:
        if not 0 <= floor < 100:
            raise ValueError("Cash floors must be in [0, 100)")
    if not threshold_sets or any(x not in THRESHOLD_SETS for x in threshold_sets):
        raise ValueError("Unknown or empty V6.0 threshold-set selection")
    study_spec(study)
    results = []
    for start in range(0, len(rows) - COHORT_WEEKS + 1):
        cohort = rows[start:start + COHORT_WEEKS]
        validate_weekly_cohort(cohort)
        for floor in floors_pct:
            for name in threshold_sets:
                results.append(simulate_sell_reentry(
                    cohort, study=study,
                    thresholds=THRESHOLD_SETS[name], threshold_set=name,
                    protected_cash_floor_pct_initial_cash=floor,
                    **study_kwargs,
                ))
    return results


def summarise_study(results: list[dict]) -> list[dict]:
    """Summarise overlapping cohort results; they are not independent samples."""
    grouped: dict[tuple, list[dict]] = {}
    for row in results:
        key = (
            row["study"], row["candidate"], row["threshold_set"],
            row["sell_ratio"], row["take_profit_pct"], row["reentry_ratio"],
            row["sell_fraction"], row["protected_cash_floor_pct_initial_cash"],
        )
        grouped.setdefault(key, []).append(row)
    summary = []
    for key, rows in sorted(grouped.items()):
        entry = {
            "study": key[0],
            "candidate": key[1],
            "threshold_set": key[2],
            "sell_ratio": key[3],
            "take_profit_pct": key[4],
            "reentry_ratio": key[5],
            "sell_fraction": key[6],
            "protected_cash_floor_pct_initial_cash": key[7],
            "cohort_count": len(rows),
            "median_final_equity_aud": _median_or_none(
                [r["final_equity_aud"] for r in rows]
            ),
            "median_total_return_pct": _median_or_none(
                [r["total_return_pct"] for r in rows]
            ),
            "median_delta_total_return_vs_fixed_weekly_pct": _median_or_none(
                [r["delta_total_return_pct"] for r in rows]
            ),
            "median_buy_count": _median_or_none([r["buy_count"] for r in rows]),
            "median_sales_count": _median_or_none([r["sales_count"] for r in rows]),
            "median_round_trips": _median_or_none([r["round_trips"] for r in rows]),
            "median_weeks_holding_fraction": _median_or_none(
                [r["weeks_holding_fraction"] for r in rows]
            ),
            "median_max_drawdown_pct": _median_or_none(
                [r["max_drawdown_pct"] for r in rows]
            ),
            "median_median_realized_sell_return_pct": _median_or_none(
                [r["median_realized_sell_return_pct"] for r in rows
                 if r["median_realized_sell_return_pct"] is not None]
            ),
            "median_median_reentry_weeks_after_sell": _median_or_none(
                [r["median_reentry_weeks_after_sell"] for r in rows
                 if r["median_reentry_weeks_after_sell"] is not None]
            ),
            "benchmark_policy": BENCHMARK_POLICY,
            "median_benchmark_final_equity_aud": _median_or_none(
                [r["benchmark_fixed_weekly"]["final_equity_aud"] for r in rows]
            ),
            "overlapping_cohorts_not_independent": True,
            "research_only": True,
            "trade_executable": False,
        }
        summary.append(entry)
    return summary
