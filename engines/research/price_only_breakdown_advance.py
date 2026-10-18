"""Research-only, frozen price-only re-timing of 5% of ORIGINAL BTC.

If the existing prior-price 'breakdown' regime occurs on halving days 501
through 524, bring forward 5% ORIGINAL BTC from the day-525 scheduled
tranche to the FIRST such observation. Deduct the same fraction on day525.
NO extra original BTC is sold by day525, and all later original staged
SELL and 200WMA weekly BUY rules are unchanged.

Uses strictly preceding price observations, identical dated AUD FX,
fees, FIFO illustrative SMSF tax and a self-financing chronological wallet.
This does NOT validate trading live ASX:IBIT or real 2026 holdings.
"""
from __future__ import annotations

import argparse
import json
import math
from pathlib import Path

import pandas as pd

from engines.research.cycle_chronological_wallet import (
    previously_completed_200wma_breach, replay_chronological_wallet,
)
from engines.research.day500_aftertax_reinvestment import (
    INITIAL_AUD, PRIMARY, SCORE_DAYS, DELAY_DAYS_AFTER_LAST_SELL,
    fetch_fx_for_cycle, fx_before,
)
from engines.research.shared_cycle_policy import (
    START_DAY, REVIEW_DAY, exit_review_days, staged_exit_decision,
    prior_price_regime, recovery_buy_budget_fraction,
)
from engines.research.smsf_self_financing_replay import AuditSmsfAccount
from engines.research.top_signal_horse_race import read_exported_history

POLICY = "maturity_90pct_holdback20pct"
BUY_STYLE = "adaptive_recovery"
ADVANCE_FRACTION_ORIGINAL = .05
TRIGGER_FIRST_DAY = 501
TRIGGER_LAST_DAY = 524
OFFSET_DAY = 525
CUTOFF = pd.Timestamp("2026-10-05", tz="UTC")
FEE_AUD = 3.
MIN_ORDER_AUD = 100.


def _utc(v):
    date = pd.Timestamp(v)
    return (date.tz_localize("UTC") if date.tzinfo is None
            else date.tz_convert("UTC")).normalize()


def replay_price_breakdown_advance(price, fx, halving, terminal, *,
                                   candidate=False, initial_aud=INITIAL_AUD):
    """Chronological independent account; candidate has exactly one re-timing.

    At the day-525 review, use actual baseline-sold fraction EXCLUDING the
    advanced portion, then subtract precisely that advanced portion from
    the original day-525 order. Future stage fractions see real sold BTC.
    """
    h, end = _utc(halving), _utc(terminal)
    if not isinstance(price, pd.Series) or not isinstance(
            price.index, pd.DatetimeIndex):
        raise ValueError("Expected unique chronological UTC price series")
    if (price.index.tz is None or not price.index.is_unique
            or not price.index.is_monotonic_increasing):
        raise ValueError("Expected unique chronological UTC price series")
    if h not in price.index or end not in price.index or end <= h:
        raise ValueError("Missing or invalid cycle endpoints")
    if end > h + pd.Timedelta(days=SCORE_DAYS):
        raise ValueError("Unobserved future cycle score")
    days = pd.date_range(h, end, freq="D", tz="UTC")
    if not days.isin(price.index).all():
        raise ValueError("Missing daily BTC close")
    if not math.isfinite(float(initial_aud)) or initial_aud <= 103.:
        raise ValueError("Invalid AUD starting balance")
    all_px = price.loc[days].to_numpy(dtype=float)
    if not all(math.isfinite(p) and p > 0 for p in all_px):
        raise ValueError("BTC closes must all be finite and positive")

    account = AuditSmsfAccount(float(initial_aud), fee=FEE_AUD, tax=True)
    if not account.buy(h, float(price.loc[h]) * fx_before(fx, h), 1.):
        raise AssertionError("Initial BTC purchase failed")
    initial_btc = account.btc
    reviews = set(exit_review_days())
    advanced_original = 0.
    advanced_date = None
    total_original_sold = 0.
    day525_sold = None
    first_activation = None
    fixed_rebuy_cash = None
    fills = []
    buy_start = h + pd.Timedelta(
        days=REVIEW_DAY + DELAY_DAYS_AFTER_LAST_SELL)

    for day in days[1:]:
        elapsed = (day - h).days
        usd = float(price.loc[day])
        aud = usd * fx_before(fx, day)
        amount_original = 0.
        scheduled_original = 0.
        if START_DAY <= elapsed <= REVIEW_DAY and elapsed in reviews:
            # Before day525, exclude the early re-timing from BASELINE
            # scheduled original-BTC fractions. Never read future prices.
            baseline_sold = total_original_sold - (
                advanced_original if elapsed <= OFFSET_DAY else 0.)
            baseline_sold = min(1., max(0., baseline_sold / initial_btc))
            decision = staged_exit_decision(
                price.loc[:day], h, day=elapsed,
                sold_original_fraction=baseline_sold, policy=POLICY)
            scheduled_original = float(decision["fraction_original"])
            if elapsed == OFFSET_DAY and advanced_original:
                deduction = advanced_original / initial_btc
                if scheduled_original + 1e-9 < deduction:
                    raise ArithmeticError(
                        "Day525 scheduled BTC cannot fund proposed advance")
                scheduled_original -= deduction
            amount_original = scheduled_original

        if (candidate and advanced_date is None and
                TRIGGER_FIRST_DAY <= elapsed <= TRIGGER_LAST_DAY):
            # prior_price_regime reads exclusively days <= decision T-1.
            regime, _ = prior_price_regime(price.loc[:day], day)
            if regime == "breakdown":
                advanced_date = day
                advanced_original = initial_btc * ADVANCE_FRACTION_ORIGINAL
                amount_original += ADVANCE_FRACTION_ORIGINAL

        if amount_original > 1e-12:
            qty = min(account.btc, initial_btc * amount_original)
            if qty <= 0 or not account.sell(day, aud, qty / account.btc):
                raise ArithmeticError("Planned original-BTC sale did not execute")
            actual_qty = float(account.orders[-1]["btc"])
            total_original_sold += actual_qty
            fills.append({
                "date": str(day.date()), "side": "SELL",
                "original_btc_fraction": actual_qty / initial_btc,
                "advance_on_this_day": bool(advanced_date == day),
                "gross_aud": float(account.orders[-1]["gross_aud"]),
                "tax_escrow_aud": float(account.orders[-1]["tax_aud"]),
            })

        if elapsed == OFFSET_DAY:
            day525_sold = total_original_sold / initial_btc

        if day >= buy_start:
            if first_activation is None and previously_completed_200wma_breach(
                    price, day):
                first_activation = day
                fixed_rebuy_cash = float(account.cash)
            if (first_activation is not None and
                    (day - first_activation).days % 7 == 0):
                step = recovery_buy_budget_fraction(
                    price.loc[:day], day, style=BUY_STYLE)
                gross = min(account.cash, fixed_rebuy_cash *
                            step["fraction_of_initial_buyback_cash"])
                if gross > MIN_ORDER_AUD and account.buy(
                        day, aud, min(1., gross / account.cash)):
                    fills.append({
                        "date": str(day.date()), "side": "BUY",
                        "gross_aud": float(account.orders[-1]["gross_aud"]),
                        "btc": float(account.orders[-1]["btc"]),
                    })
        account.mark(aud)

    last_aud = float(price.loc[end]) * fx_before(fx, end)
    return {
        "candidate": bool(candidate),
        "research_only": True,
        "live_execution_parity_verified": False,
        "halving": str(h.date()),
        "terminal": str(end.date()),
        "completed_day1150": end == h + pd.Timedelta(days=SCORE_DAYS),
        "advanced_sell_date": str(advanced_date.date()) if advanced_date is not None else None,
        "advanced_fraction_original_pct": round(
            100 * advanced_original / initial_btc, 5),
        "fraction_original_sold_by_day525": (
            round(day525_sold, 9) if day525_sold is not None else None),
        "fraction_original_sold_total": round(
            total_original_sold / initial_btc, 9),
        "original_btc": round(initial_btc, 8),
        "first_200wma_rebuy": (
            str(first_activation.date()) if first_activation is not None else None),
        "fixed_original_aftertax_rebuy_cash_aud": (
            round(fixed_rebuy_cash, 2) if fixed_rebuy_cash is not None else None),
        "btc_end": round(account.btc, 8),
        "cash_end_aud": round(account.cash, 2),
        "btc_equivalent_including_cash": round(
            account.btc + account.cash / last_aud, 8),
        "ending_aftertax_liquidation_aud": round(
            account.liquidation_value(end, last_aud), 2),
        "realised_tax_escrow_aud": round(account.total_tax, 2),
        "brokerage_aud": round(account.total_fees, 2),
        "account_drawdown_pct": round(100 * account.drawdown, 2),
        "sell_count": sum(o["side"] == "SELL" for o in account.orders),
        "buy_count": sum(o["side"] == "BUY" for o in account.orders) - 1,
        "executions": fills,
    }


def audit_price_only_advance(history, *, fx_fetcher=fetch_fx_for_cycle):
    """One predeclared hypothesis, same price/FX/tax/cash, no later selection."""
    full = history.loc[:CUTOFF].sort_index()
    if "price_usd" not in full.columns or full.empty:
        raise ValueError("Historical USD closing-price series missing")
    price = full["price_usd"]
    rows = []
    for name, meta in PRIMARY.items():
        h = _utc(meta["halving"])
        terminal = min(h + pd.Timedelta(days=SCORE_DAYS), price.index[-1])
        fx = fx_fetcher(h, terminal)
        ref = replay_chronological_wallet(price, fx, h, terminal)
        baseline = replay_price_breakdown_advance(
            price, fx, h, terminal, candidate=False)
        candidate = replay_price_breakdown_advance(
            price, fx, h, terminal, candidate=True)
        for key, orig_key in (
                ("ending_aftertax_liquidation_aud",
                 "after_hypothetical_liquidation_cgt_aud"),
                ("btc_end", "btc_held"),
                ("cash_end_aud", "cash_remaining_aud"),
                ("sell_count", "sell_count"),
                ("buy_count", "buyback_count")):
            if abs(baseline[key] - ref[orig_key]) > .03:
                raise AssertionError(
                    f"Baseline changed {name} {key}: "
                    f"{baseline[key]} vs {ref[orig_key]}")
        if (baseline["fraction_original_sold_by_day525"] is not None
                and abs(candidate["fraction_original_sold_by_day525"]
                        - baseline["fraction_original_sold_by_day525"]) > 1e-7):
            raise AssertionError("Re-timing sold extra BTC by day525")
        if abs(candidate["fraction_original_sold_total"] -
               baseline["fraction_original_sold_total"]) > 1e-7:
            raise AssertionError("Re-timing altered total original BTC sold")
        if candidate["first_200wma_rebuy"] != baseline["first_200wma_rebuy"]:
            raise AssertionError("Changed frozen prior-200WMA buyback gate")
        orig = baseline["ending_aftertax_liquidation_aud"]
        new = candidate["ending_aftertax_liquidation_aud"]
        rows.append({
            "cycle": name,
            "completed_horizon": baseline["completed_day1150"],
            "first_price_only_breakdown_advance": candidate["advanced_sell_date"],
            "original_aftertax_aud": orig,
            "retimed_aftertax_aud": new,
            "difference_aftertax_aud": round(new - orig, 2),
            "difference_aftertax_pct": round(100 * (new / orig - 1), 3),
            "baseline": baseline,
            "candidate": candidate,
        })
    return {
        "research_only": True,
        "not_approved_for_live_trades": True,
        "onchain_values_used_for_signal": False,
        "btc_price_origin": "archived provider close, vintage not certified",
        "completed_cycles_inspected_before_design": ["2017", "2021"],
        "right_censored": "2025/26 through 2026-10-05",
        "trigger": "first previous-close price-only breakdown on days501..524",
        "fixed_retimed_percent_original_btc": 5.,
        "source_tranche": "day525, exact equal subtraction",
        "later_original_staged_sell_unchanged": True,
        "buyback": "prior 200WMA breach no sooner than day744, same weekly budget",
        "hypothetical_initial_aud": INITIAL_AUD,
        "cycles": rows,
    }


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", type=Path,
                        default=Path("artifacts/price_only_breakdown_advance"))
    args = parser.parse_args(argv)
    result = audit_price_only_advance(read_exported_history())
    args.out.mkdir(parents=True, exist_ok=True)
    (args.out / "summary.json").write_text(
        json.dumps(result, indent=2, default=str))
    import csv
    with (args.out / "summary.csv").open("w", newline="") as stream:
        cols = [
            "cycle", "completed_horizon",
            "first_price_only_breakdown_advance", "original_aftertax_aud",
            "retimed_aftertax_aud", "difference_aftertax_aud",
            "difference_aftertax_pct",
        ]
        writer = csv.DictWriter(stream, fieldnames=cols)
        writer.writeheader()
        for row in result["cycles"]:
            writer.writerow({k: row[k] for k in cols})
    for row in result["cycles"]:
        print(json.dumps({
            "cycle": row["cycle"],
            "complete": row["completed_horizon"],
            "first_breakdown": row["first_price_only_breakdown_advance"],
            "vs_original_aftertax_pct": row["difference_aftertax_pct"],
            "same_original_sold_by_day525": (
                row["baseline"]["fraction_original_sold_by_day525"] ==
                row["candidate"]["fraction_original_sold_by_day525"]),
        }))


if __name__ == "__main__":
    main()
