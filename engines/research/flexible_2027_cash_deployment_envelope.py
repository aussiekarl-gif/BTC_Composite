"""Conditional cash deployment envelope — paper RESEARCH, not a BTC forecast.

The user confirmed 20 Oct 2026 that 30 Nov 2026 is NOT a deployment
deadline. Cash may remain unspent through 2027 if market signals are poor.

This calculator is intentionally PRICE-FREE: it illustrates what fraction
of initial notional cash would be committed by various fixed percentages
of REMAINING cash after N actual eligible, executed 7-day-spaced BUYs.
It cannot select BUY dates, predict value, evaluate 200WMA, make trades,
estimate tax, or assume a missed opportunity is always a market bottom.

The existing 20-week fixed DCA forward account is a CONTROL, not the
user's real deployment instruction. Unchanged live Cycle 2.5% rule.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import math
from decimal import Decimal, ROUND_HALF_UP, getcontext
from pathlib import Path

getcontext().prec = 32

RESEARCH_ENROLMENT_DATE = dt.date(2026, 10, 20)
CHECKPOINTS = (
    dt.date(2026, 11, 30),
    dt.date(2027, 3, 31),
    dt.date(2027, 6, 30),
    dt.date(2027, 12, 31),
)
# Ratios are deterministic COUNTERFACTUAL exposure, not probabilities.
CONDITIONAL_ELIGIBILITY_FRACTIONS = (
    Decimal("0"),
    Decimal("0.25"),
    Decimal("0.50"),
    Decimal("1"),
)
PAPER_BUY_PCTS_OF_REMAINING_CASH = (
    Decimal("2.5"),  # current real weekly conditional Cycle market percentage
    Decimal("3.0"),  # candidate only
    Decimal("3.5"),  # candidate only
    Decimal("5.0"),  # candidate only
)
NOMINAL_STARTING_CASH_AUD = Decimal("500000")
MIN_COOLDOWN_DAYS = 7
OUTPUT = Path("artifacts/research_flexible_btc_deployment_2027.json")


def maximum_possible_seven_day_orders(*, start: dt.date, thru: dt.date) -> int:
    """Upper bound only. BTC/FX signals and actual ASX sessions are NOT known."""
    if (not isinstance(start, dt.date) or isinstance(start, dt.datetime)
        or not isinstance(thru, dt.date) or isinstance(thru, dt.datetime)):
        raise ValueError("Plain calendar dates required")
    if thru < start:
        raise ValueError("Checkpoint precedes research enrolment")
    return 1 + (thru - start).days // MIN_COOLDOWN_DAYS


def remaining_cash_after_conditional_buys(
    starting_cash_aud: Decimal, buy_pct_remaining_cash: Decimal, eligible_fills: int,
) -> Decimal:
    """No terminal forced sweep: zero eligible trades => ALL cash retained."""
    if not isinstance(starting_cash_aud, Decimal) or not starting_cash_aud.is_finite() or starting_cash_aud <= 0:
        raise ValueError("Positive finite decimal notional cash required")
    if (not isinstance(buy_pct_remaining_cash, Decimal)
        or not buy_pct_remaining_cash.is_finite()
        or not Decimal("0") <= buy_pct_remaining_cash <= Decimal("100")):
        raise ValueError("Valid conditional percent 0..100 required")
    if isinstance(eligible_fills, bool) or not isinstance(eligible_fills, int) or eligible_fills < 0:
        raise ValueError("Nonnegative integer count of actual eligible paper fills required")
    return starting_cash_aud * (
        Decimal("1")-buy_pct_remaining_cash/Decimal("100")
    ) ** eligible_fills


def _aud(v: Decimal) -> str:
    return str(v.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))


def build_envelope(
    *, hypothetical_cash_aud: Decimal = NOMINAL_STARTING_CASH_AUD,
    start: dt.date = RESEARCH_ENROLMENT_DATE,
    checkpoints: tuple[dt.date, ...] = CHECKPOINTS,
) -> dict:
    if (not isinstance(hypothetical_cash_aud, Decimal)
        or not hypothetical_cash_aud.is_finite() or hypothetical_cash_aud <= 0):
        raise ValueError("Hypothetical notional cash must be positive finite Decimal")
    if not checkpoints:
        raise ValueError("At least one future research checkpoint required")
    if tuple(sorted(checkpoints)) != tuple(checkpoints) or len(set(checkpoints)) != len(checkpoints):
        raise ValueError("Checkpoints must be distinct and ordered")
    items = []
    for due in checkpoints:
        available = maximum_possible_seven_day_orders(start=start, thru=due)
        for f in CONDITIONAL_ELIGIBILITY_FRACTIONS:
            eligible = int(math.floor(Decimal(available) * f))
            for pct in PAPER_BUY_PCTS_OF_REMAINING_CASH:
                cash = remaining_cash_after_conditional_buys(
                    hypothetical_cash_aud, pct, eligible,
                )
                items.append({
                    "checkpoint_calendar_date_not_deployment_deadline": due.isoformat(),
                    "maximum_7day_spaced_opportunities_IF_signals_every_week": available,
                    "hypothetical_fraction_of_weeks_with_eligible_filled_buy": str(f),
                    "hypothetical_eligible_executed_buy_opportunities": eligible,
                    "candidate_pct_of_remaining_cash_on_eligible_buy_only": str(pct),
                    "starting_reference_cash_aud": _aud(hypothetical_cash_aud),
                    "cash_remaining_aud_before_prices_costs_tax": _aud(cash),
                    "cash_deployed_aud_before_prices_costs_tax": _aud(hypothetical_cash_aud-cash),
                    "percent_original_cash_deployed": str(
                        ((hypothetical_cash_aud-cash)*100/hypothetical_cash_aud)
                        .quantize(Decimal("0.0001"),rounding=ROUND_HALF_UP)),
                    "model_investment_return_calculated": False,
                    "buy_signal_dates_observed": False,
                    "is_user_portfolio": False,
                })
    return {
        "kind": "BTC_FLEXIBLE_2027_CONDITIONAL_CASH_ONLY_ENVELOPE_NOT_PERFORMANCE",
        "objective_recorded_2026_10_20": "NOVEMBER_2026_IS_NOT_A_FORCED_DEPLOYMENT_DEADLINE",
        "uninvested_AUD_may_remain_in_2027": True,
        "forced_buy_at_any_checkpoint": False,
        "live_2_5_percent_weekly_buy_unchanged": True,
        "20_week_fixed_DCA_remains_an_independent_benchmark": True,
        "all_candidate_percentages_research_only": True,
        "cash_start_is_illustrative_not_verified_actual_portfolio": True,
        "starting_capital_aud_reference_only": _aud(hypothetical_cash_aud),
        "no_performance_or_alpha_inferred_from_cash_deployment_speed": True,
        "no_assumed_price_or_spread_or_taxes_or_etf_whole_units": True,
        "no_negative_cash_or_mandatory_deployment": True,
        "no_live_trading_or_broker_operations": True,
        "no_portfolio_reads_or_writes": True,
        "no_notifications": True,
        "observations": items,
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description="Illustrative cash-only conditional deployment envelope")
    parser.add_argument("--output", type=Path, default=OUTPUT)
    args = parser.parse_args(argv)
    result = build_envelope()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result,indent=2,sort_keys=True)+"\n",encoding="utf-8")
    print(json.dumps({
        "research_goal":result["objective_recorded_2026_10_20"],
        "hypothetical_notional_cash_AUD":result["starting_capital_aud_reference_only"],
        "no_forced_investment": not result["forced_buy_at_any_checkpoint"],
        "candidate_policies": len(PAPER_BUY_PCTS_OF_REMAINING_CASH),
        "counterfactual_rows":len(result["observations"]),
        "investable_alpha_proven": False,
    },sort_keys=True))


if __name__ == "__main__":
    main()
