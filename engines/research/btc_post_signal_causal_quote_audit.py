"""Independent, read-only CAUSAL quote-coverage audit of existing BTC tapes.

This is a measurement of what a trader COULD HAVE KNOWN after BOTH public
REST responses, NOT a tradable quote, fill, signal or ASX:IBIT strategy.
No historical reconstruction, interpolated prices, new orders or ntfy.
"""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import math
from pathlib import Path
from typing import Any

from engines.research.btc_microstructure_forward_scorecard import (
    build_report as build_original_scorecard,
)
from engines.research.btc_spot_depth_forward import (
    OUTPUT as DEPTH_PATH, read_verified_tape,
)
from engines.research.coinbase_trade_samples import (
    OUTPUT as TRADES_PATH, read_tape,
)

UTC = dt.timezone.utc
NAME = "btc_post_signal_causal_quote_coverage_paper_v1"
MAX_ENTRY_LAG = dt.timedelta(minutes=5)
MAX_EXIT_LAG = dt.timedelta(minutes=90)
HORIZONS_HOURS = (6, 24, 168)
# These are explicitly hypothetical, NOT verified ASX:IBIT or broker fees.
HYPOTHETICAL_SPOT_FEE_BPS_PER_SIDE = (5, 10, 25)


def _time(raw: str) -> dt.datetime:
    try:
        value = dt.datetime.fromisoformat(raw)
    except (TypeError, ValueError) as exc:
        raise ValueError("Malformed UTC timestamp") from exc
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("Timezone-aware timestamp required")
    return value.astimezone(UTC)


def _price(row: dict[str, str], field: str) -> float:
    try:
        x = float(row[field])
    except (KeyError, TypeError, ValueError, OverflowError) as exc:
        raise ValueError(f"Invalid {field}") from exc
    if not math.isfinite(x) or x <= 0:
        raise ValueError(f"Non-positive or non-finite {field}")
    return x


def _hash() -> str:
    parameters = {
        "name": NAME,
        "entry_max_lag_seconds": MAX_ENTRY_LAG.total_seconds(),
        "exit_max_lag_seconds": MAX_EXIT_LAG.total_seconds(),
        "horizons": HORIZONS_HOURS,
        "hypothetical_spot_fee_bps_per_side": HYPOTHETICAL_SPOT_FEE_BPS_PER_SIDE,
        "no_ibit_execution": True,
        "post_signal_quote_required": True,
    }
    return hashlib.sha256(json.dumps(parameters, sort_keys=True).encode()).hexdigest()


def build_audit(
    depth: list[dict[str, str]],
    trades: list[dict[str, str]],
    *,
    as_of_utc: dt.datetime,
) -> dict[str, Any]:
    """Call with SHA-chain-validated Kraken/Coinbase tape readers in production.

    Source timestamp is client HTTP receipt, NOT venue order-book timestamp.
    Quotes may disappear before orders arrive; even the after-cost scenario
    is not executable evidence. Existing frozen hypotheses are never refit.
    """
    if (not isinstance(as_of_utc, dt.datetime) or as_of_utc.tzinfo is None
            or as_of_utc.utcoffset() is None):
        raise ValueError("Timezone-aware as-of required")
    now = as_of_utc.astimezone(UTC)
    original = build_original_scorecard(depth, trades, as_of_utc=now)
    books = sorted(depth, key=lambda b: _time(b["captured_at_utc"]))
    observations = []
    for hypothesis in original["observations"]:
        known = _time(hypothesis["known_at_utc"])
        # Crucially, the Kraken snapshot used to BUILD the hypothesis cannot
        # also serve as the post-signal entry, even when timestamps tie to
        # the nearest second. An actual later independent REST receipt is
        # required. This is the known causal-pricing flaw in exploratory mids.
        next_books = [b for b in books if known < _time(b["captured_at_utc"])]
        next_book = next_books[0] if next_books else None
        eligible_entry = (
            next_book is not None
            and _time(next_book["captured_at_utc"]) <= known + MAX_ENTRY_LAG
        )
        row: dict[str, Any] = {
            "source_slot_utc": hypothesis["slot_utc"],
            "hypothesis": hypothesis["hypothesis"],
            "known_at_utc": known.isoformat(),
            "original_kraken_source_hash": hypothesis["kraken_source_hash"],
            "original_coinbase_source_hash": hypothesis["coinbase_source_hash"],
            "original_midpoint_cannot_be_entry": True,
            "post_signal_quote_observed": bool(eligible_entry),
            "entry_status": (
                "CAUSAL_POST_SIGNAL_REST_QUOTE_NOT_FILL" if eligible_entry
                else "NO_POST_SIGNAL_QUOTE_WITHIN_5_MINUTES"
            ),
            "first_later_quote_delay_seconds": (
                round((_time(next_book["captured_at_utc"])-known).total_seconds(), 3)
                if next_book is not None else None
            ),
            "horizons": {},
        }
        if eligible_entry:
            entry_at = _time(next_book["captured_at_utc"])
            ask = _price(next_book, "best_ask_usd")
            bid = _price(next_book, "best_bid_usd")
            if ask < bid:
                raise ValueError("Crossed Kraken quote")
            row["entry_quote_at_utc"] = entry_at.isoformat()
            row["entry_kraken_source_hash"] = next_book["row_hash"]
            row["entry_bid_usd"] = round(bid, 6)
            row["entry_ask_usd"] = round(ask, 6)
        else:
            entry_at = None
            ask = None
        for hours in HORIZONS_HOURS:
            if not eligible_entry:
                row["horizons"][str(hours)] = {"status": "NO_CAUSAL_ENTRY_QUOTE"}
                continue
            # Horizon measured from the time the full hypothesis was known.
            # Exit must be a genuinely later observation, not stale data.
            target = known + dt.timedelta(hours=hours)
            exits = [b for b in books if (
                _time(b["captured_at_utc"]) >= target
                and _time(b["captured_at_utc"]) > entry_at
                and _time(b["captured_at_utc"]) <= target + MAX_EXIT_LAG
            )]
            if not exits:
                row["horizons"][str(hours)] = {"status": "NO_CAUSAL_EXIT_QUOTE"}
                continue
            exit_book = exits[0]
            exit_at = _time(exit_book["captured_at_utc"])
            exit_bid = _price(exit_book, "best_bid_usd")
            exit_ask = _price(exit_book, "best_ask_usd")
            if exit_bid > exit_ask:
                raise ValueError("Crossed Kraken exit quote")
            base = {
                "status": "CAUSAL_QUOTES_NOT_EXECUTABLE",
                "exit_quote_at_utc": exit_at.isoformat(),
                "exit_kraken_source_hash": exit_book["row_hash"],
                "exit_bid_usd": round(exit_bid, 6),
                "actual_elapsed_from_known_hours": round(
                    (exit_at-known).total_seconds()/3600, 4
                ),
                "spot_long_after_hypothetical_fees_pct": None,
                "no_IBIT_AUD_execution_evidence": True,
            }
            if hypothesis["hypothesis"] == "PAPER_BULL":
                # Long-only spot scenario: pay Kraken ASK, receive Kraken BID.
                # No market impact, slippage, FX, tax, ASX spread or IBIT fees.
                base["spot_long_after_hypothetical_fees_pct"] = {
                    str(bps): round(100 * (
                        exit_bid * (1-bps/10000) /
                        (ask * (1+bps/10000)) - 1
                    ), 6)
                    for bps in HYPOTHETICAL_SPOT_FEE_BPS_PER_SIDE
                }
            elif hypothesis["hypothesis"] == "PAPER_BEAR":
                base["reason_no_long_IBIT_return"] = "BEAR_NOT_A_LONG_ONLY_IBIT_ENTRY"
            else:
                base["reason_no_long_IBIT_return"] = "NEUTRAL_NO_TRADE"
            row["horizons"][str(hours)] = base
        observations.append(row)

    eligible = [o for o in observations if o["post_signal_quote_observed"]]
    bull = [o for o in eligible if o["hypothesis"] == "PAPER_BULL"]
    mature = {str(h): sum(
        1 for o in bull
        if o["horizons"][str(h)]["status"] == "CAUSAL_QUOTES_NOT_EXECUTABLE"
    ) for h in HORIZONS_HOURS}
    return {
        "name": NAME,
        "audit_policy_sha256": _hash(),
        "as_of_utc": now.isoformat(),
        "original_frozen_policy_sha256": original["policy_sha256"],
        "strict_paired_hypotheses": len(observations),
        "post_signal_quotes_within_5_minutes": len(eligible),
        "missing_timely_post_signal_quotes": len(observations)-len(eligible),
        "bull_hypotheses_with_timely_entry_quote": len(bull),
        "hypothetical_spot_long_matured_by_hours": mature,
        "cost_scenario_bps_per_side_not_broker_verified":
            list(HYPOTHETICAL_SPOT_FEE_BPS_PER_SIDE),
        "all_quotes_are_HTTP_receipt_snapshots_not_executable_fills": True,
        "ASX_IBIT_AUD_quotes_available_for_this_audit": False,
        "after_cost_ASX_IBIT_outperformance_validated": False,
        "after_cost_BTC_trade_outperformance_validated": False,
        "trade_recommendation": "NONE",
        "portfolio_writes": 0,
        "ntfy_messages": 0,
        "broker_orders": 0,
        "observations": observations,
    }


def main(argv=None) -> None:
    parser = argparse.ArgumentParser(description="Read-only post-signal BTC quote coverage")
    parser.add_argument("--output", type=Path,
                        default=Path("artifacts/btc_post_signal_causal_quote_audit.json"))
    args = parser.parse_args(argv)
    depth = read_verified_tape(DEPTH_PATH)
    trades = read_tape(TRADES_PATH)
    report = build_audit(depth, trades, as_of_utc=dt.datetime.now(UTC))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, sort_keys=True)+"\n", encoding="utf-8")
    print(json.dumps({k: v for k, v in report.items() if k != "observations"}, sort_keys=True))


if __name__ == "__main__":
    main()
