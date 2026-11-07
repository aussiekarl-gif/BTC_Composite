"""PR-only, read-only HTTP-receipt experiment for a CAUSAL BTC quote.

Three SEPARATE sequential public REST requests:
  1. Kraken depth: hypothesis baseline BEFORE the Coinbase sample.
  2. Coinbase bounded trades: the hypothesis is fully known ONLY here.
  3. A NEW Kraken depth request STARTED after Coinbase's HTTP receipt.

This is NOT the six-hour immutable source collector, the frozen scorecard,
a broker feed, an executable fill or a trade/ntfy signal. It never edits
provider tapes, portfolios, dashboards or model rules. A GitHub Actions
artifact may preserve the standalone diagnostic (not append a historical row).
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
from pathlib import Path
from typing import Any, Callable

from engines.research.btc_spot_depth_forward import (
    fetch_kraken_book, summarize_book,
)
from engines.research.coinbase_trade_samples import (
    fetch_public_trades, summarize as summarize_trades,
)

UTC = dt.timezone.utc
MAX_REQUEST_SECONDS = 120
MAX_PAIR_SECONDS = 300
MAX_ENTRY_SECONDS = 300
REPORT_PATH = Path("artifacts/btc_post_signal_quote_probe_readonly.json")


def _utc(value: dt.datetime) -> dt.datetime:
    if (not isinstance(value, dt.datetime) or value.tzinfo is None
            or value.utcoffset() is None):
        raise ValueError("UTC-aware HTTP receipt clock required")
    return value.astimezone(UTC)


def _slot(t: dt.datetime) -> dt.datetime:
    return t.replace(hour=t.hour // 6 * 6, minute=0, second=0, microsecond=0)


def _request(fetch: Callable, clock: Callable) -> tuple[Any, dt.datetime, dt.datetime]:
    started = _utc(clock())
    payload = fetch()
    received = _utc(clock())
    duration = (received - started).total_seconds()
    if not 0 <= duration <= MAX_REQUEST_SECONDS:
        raise ValueError("HTTP receipt timing invalid; do not score quote")
    return payload, started, received


def collect_probe(
    *, kraken_fetcher: Callable = fetch_kraken_book,
    coinbase_fetcher: Callable = fetch_public_trades,
    clock: Callable = lambda: dt.datetime.now(UTC),
) -> dict[str, Any]:
    """Check actual causal sequencing; no models, trade signals, or tape writes."""
    before_raw, b_start, b_received = _request(kraken_fetcher, clock)
    base = summarize_book(before_raw, captured_at_utc=b_received)

    trades_raw, c_start, c_received = _request(coinbase_fetcher, clock)
    trade = summarize_trades(trades_raw, captured_at_utc=c_received)

    # Do not begin post-signal fetch until the complete two-provider
    # hypothesis is KNOWN. Require a truly new Kraken request and receipt.
    if not b_received < c_received or c_start < b_received:
        raise ValueError("Baseline/coinbase order is not causal")
    post_raw, p_start, p_received = _request(kraken_fetcher, clock)
    if p_start < c_received or p_received <= c_received:
        raise ValueError("Post-signal Kraken quote not causally received")
    post = summarize_book(post_raw, captured_at_utc=p_received)

    all_same_slot = _slot(b_received) == _slot(c_received) == _slot(p_received)
    pair_delay = (c_received - b_received).total_seconds()
    entry_delay = (p_received - c_received).total_seconds()
    timely_pair = 0 < pair_delay <= MAX_PAIR_SECONDS
    timely_entry = 0 < entry_delay <= MAX_ENTRY_SECONDS
    eligible = all_same_slot and timely_pair and timely_entry

    reasons = []
    if not all_same_slot:
        reasons.append("CROSSED_UTC_SIX_HOUR_SLOT")
    if not timely_pair:
        reasons.append("BASELINE_TO_COINBASE_OVER_FIVE_MINUTES")
    if not timely_entry:
        reasons.append("POST_SIGNAL_QUOTE_OVER_FIVE_MINUTES")

    # Microsecond precision is retained for strict causal receipt ordering.
    # Captured quote values are only indicative public REST snapshots.
    result = {
        "kind": "one_off_read_only_causal_post_signal_quote_PROBE",
        "status": ("CAUSAL_REST_QUOTE_OBSERVED_NOT_FILL" if eligible
                   else "EXCLUDED_NO_TIMELY_CAUSAL_QUOTE"),
        "eligible_quote": eligible,
        "exclusion_reasons": reasons,
        "baseline_kraken_request_started_utc": b_start.isoformat(),
        "baseline_kraken_http_receipt_utc": b_received.isoformat(),
        "coinbase_request_started_utc": c_start.isoformat(),
        "hypothesis_fully_known_at_coinbase_http_receipt_utc": c_received.isoformat(),
        "post_kraken_request_started_utc": p_start.isoformat(),
        "post_kraken_http_receipt_utc": p_received.isoformat(),
        "baseline_to_coinbase_seconds": round(pair_delay, 6),
        "known_to_post_quote_seconds": round(entry_delay, 6),
        "same_utc_six_hour_slot": all_same_slot,
        "original_baseline_quote": {
            "bid_usd": base["best_bid_usd"],
            "ask_usd": base["best_ask_usd"],
            "payload_sha256": base["provider_payload_sha256"],
        },
        "coinbase_bounded_sample": {
            "observed_trades": trade["observed_trades"],
            "sample_duration_seconds": trade["sample_duration_seconds"],
            "aggressor_buy_share_pct_sample": trade["aggressor_buy_share_pct_sample"],
            "payload_sha256": trade["provider_payload_sha256"],
            "not_continuous_six_hour_volume": True,
        },
        "separate_post_signal_rest_quote": {
            "bid_usd": post["best_bid_usd"],
            "ask_usd": post["best_ask_usd"],
            "payload_sha256": post["provider_payload_sha256"],
        },
        "not_broker_executable": True,
        "no_independently_observed_exit_or_after_cost_return": True,
        "not_AUD_or_ASX_IBIT_quote": True,
        "model_thresholds_or_weights_changed": False,
        "recommendation": "NONE",
        "ntfy_messages": 0,
        "broker_orders": 0,
        "personal_portfolio_writes": 0,
        "immutable_historical_source_tape_writes": 0,
    }
    return result


def main(argv=None) -> None:
    parser = argparse.ArgumentParser(description="One-off PR-only causal BTC REST quote pilot")
    parser.add_argument("--output", type=Path, default=REPORT_PATH)
    args = parser.parse_args(argv)
    report = collect_probe()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n",
                           encoding="utf-8")
    print(json.dumps({
        "status": report["status"],
        "eligible_quote": report["eligible_quote"],
        "exclusion_reasons": report["exclusion_reasons"],
        "known_to_post_quote_seconds": report["known_to_post_quote_seconds"],
        "ntfy_messages": 0, "broker_orders": 0,
    }, sort_keys=True))


if __name__ == "__main__":
    main()
