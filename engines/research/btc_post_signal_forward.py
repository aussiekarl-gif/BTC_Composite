"""Prospective research-only POST-SIGNAL Kraken quote tape and forward horizons.

NOT an executable BTC/ASX:IBIT order, broker quote, or strategy.
Only call on a runner AFTER it has saved BOTH genuine new baseline Kraken
and Coinbase records in this run. Never backfill missing history. The new
Kraken public REST call is independently initiated AFTER both receipts.
Existing historical source tapes are never altered by this module.
"""
from __future__ import annotations

import argparse
import csv
import datetime as dt
import hashlib
import io
import json
import math
import os
from pathlib import Path
import tempfile
from typing import Callable

from engines.research.btc_spot_depth_forward import (
    OUTPUT as BASE_PATH, fetch_kraken_book, read_verified_tape as read_kraken,
    summarize_book,
)
from engines.research.coinbase_trade_samples import (
    OUTPUT as TRADES_PATH, read_tape as read_coinbase,
)
from engines.research.btc_microstructure_forward_scorecard import (
    build_report as frozen_scorecard,
)

UTC = dt.timezone.utc
MAX_WAIT = 300
MAX_HTTP = 120
MAX_HORIZON_LAG = dt.timedelta(minutes=90)
HORIZONS_H = (6, 24, 168)
FEE_BPS = (5, 10, 25)  # hypothetical BTC spot fees PER SIDE, not broker rates
GENESIS = "0" * 64
OUTPUT = (Path(__file__).resolve().parents[2] / "data" /
          "research_forward_validation" / "kraken_post_signal_quotes_forward.csv")
REPORT = Path("artifacts/btc_post_signal_forward_scorecard.json")
CAPTURE_STATUS = Path("artifacts/btc_microstructure_capture_status.json")

FIELDS = (
    "slot_utc", "baseline_kraken_receipt_utc", "coinbase_receipt_utc",
    "post_kraken_request_started_utc", "post_kraken_receipt_utc",
    "baseline_kraken_row_hash", "coinbase_row_hash",
    "frozen_policy_sha256", "frozen_hypothesis",
    "best_bid_usd", "best_ask_usd", "provider_payload_sha256",
    "previous_row_hash", "row_hash",
)


def utc(value):
    if not isinstance(value, dt.datetime) or value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("Timezone-aware timestamp required")
    return value.astimezone(UTC)


def instant(raw):
    return utc(dt.datetime.fromisoformat(raw))


def slot(t):
    t = utc(t)
    return t.replace(hour=(t.hour // 6) * 6, minute=0, second=0, microsecond=0)


def positive(raw):
    n = float(raw)
    if not math.isfinite(n) or n <= 0:
        raise ValueError("Non-positive/nonfinite quote")
    return n


def signature(row):
    data = {key: row[key] for key in FIELDS if key != "row_hash"}
    return hashlib.sha256(json.dumps(data, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def read_tape(path: Path = OUTPUT):
    if not path.exists():
        return []
    with path.open(encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        if tuple(reader.fieldnames or ()) != FIELDS:
            raise ValueError("Post-signal research tape schema mismatch")
        rows = list(reader)
    if not rows:
        raise ValueError("Existing empty post-signal tape cannot be reset")
    prior = GENESIS
    last_slot = None
    for row in rows:
        if (set(row) != set(FIELDS) or row["previous_row_hash"] != prior
                or signature(row) != row["row_hash"]):
            raise ValueError("Post-signal tape SHA-chain violation")
        first = instant(row["baseline_kraken_receipt_utc"])
        known = instant(row["coinbase_receipt_utc"])
        began = instant(row["post_kraken_request_started_utc"])
        received = instant(row["post_kraken_receipt_utc"])
        this_slot = instant(row["slot_utc"])
        if (this_slot != slot(first) or this_slot != slot(known)
                or this_slot != slot(received)
                or (last_slot is not None and this_slot <= last_slot)
                or not first < known <= began < received
                or (known-first).total_seconds() > MAX_WAIT
                or (received-known).total_seconds() > MAX_WAIT
                or (received-began).total_seconds() > MAX_HTTP
                or row["frozen_hypothesis"] not in
                   ("PAPER_BULL", "PAPER_BEAR", "PAPER_NEUTRAL")
                or any(len(row[x]) != 64 for x in (
                    "baseline_kraken_row_hash", "coinbase_row_hash",
                    "frozen_policy_sha256", "provider_payload_sha256"))
                or positive(row["best_ask_usd"]) <= positive(row["best_bid_usd"])):
            raise ValueError("Invalid causal quote tape chronology, market or provenance")
        prior, last_slot = row["row_hash"], this_slot
    return rows


def append(path: Path, observation: dict):
    if set(observation) != set(FIELDS) - {"previous_row_hash", "row_hash"}:
        raise ValueError("Unexpected post-signal quote fields")
    rows = read_tape(path)
    if rows and instant(observation["slot_utc"]) <= instant(rows[-1]["slot_utc"]):
        raise ValueError("Duplicate or backdated post-signal tape; no rewrite")
    new = {**observation, "previous_row_hash": rows[-1]["row_hash"] if rows else GENESIS}
    new["row_hash"] = signature(new)
    # Validate the full prospective chain BEFORE atomically replacing the file.
    buffer = io.StringIO(newline="")
    writer = csv.DictWriter(buffer, fieldnames=FIELDS, lineterminator="\n")
    writer.writeheader()
    writer.writerows(rows + [new])
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile("w", dir=path.parent, encoding="utf-8",
                                     newline="", delete=False) as handle:
        tmp = handle.name
        handle.write(buffer.getvalue())
    try:
        if read_tape(Path(tmp)) != rows + [new]:
            raise AssertionError("Prospective chain validation failed")
        os.replace(tmp, path)
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)
    return new


def collect(*, depth_path=BASE_PATH, coinbase_path=TRADES_PATH,
            output=OUTPUT, status: dict, fetcher: Callable = fetch_kraken_book,
            clock: Callable = lambda: dt.datetime.now(UTC)):
    """ONLY two newly saved original receipts from the same runner qualify."""
    read_tape(output)  # abort on prior tampering BEFORE live HTTP
    if (status.get("kraken_status") != "NEW_SNAPSHOT"
            or status.get("coinbase_status") != "NEW_SNAPSHOT"):
        return {"status": "SKIP_NO_TWO_NEW_ORIGINAL_SOURCE_RECEIPTS", "appended": False}
    depth = read_kraken(depth_path)
    trades = read_coinbase(coinbase_path)
    if not depth or not trades or depth[-1]["slot_utc"] != trades[-1]["slot_utc"]:
        return {"status": "SKIP_UNPAIRED_ORIGINAL_SOURCES", "appended": False}
    book, trade = depth[-1], trades[-1]
    b_time, c_time = instant(book["captured_at_utc"]), instant(trade["captured_at_utc"])
    start = utc(clock())
    if (not b_time < c_time <= start
            or slot(b_time) != slot(c_time) or slot(c_time) != slot(start)
            or (c_time-b_time).total_seconds() > MAX_WAIT
            or (start-c_time).total_seconds() > MAX_WAIT):
        return {"status": "SKIP_STALE_ORIGINAL_PAIR", "appended": False}
    frozen = frozen_scorecard(depth, trades, as_of_utc=start)
    matched = [x for x in frozen["observations"]
               if x["slot_utc"] == book["slot_utc"]
               and x["kraken_source_hash"] == book["row_hash"]
               and x["coinbase_source_hash"] == trade["row_hash"]]
    if len(matched) != 1:
        return {"status": "SKIP_FROZEN_POLICY_PAIR_INELIGIBLE", "appended": False}
    original = matched[0]
    payload = fetcher()   # genuinely new HTTP call initiated AFTER Coinbase receipt
    receipt = utc(clock())
    if (not start < receipt or (receipt-start).total_seconds() > MAX_HTTP
            or receipt <= c_time or (receipt-c_time).total_seconds() > MAX_WAIT
            or slot(receipt) != slot(c_time)):
        return {"status": "SKIP_LATE_OR_AMBIGUOUS_NEW_REST_RECEIPT", "appended": False}
    quote = summarize_book(payload, captured_at_utc=receipt)
    observation = {
        "slot_utc": book["slot_utc"],
        "baseline_kraken_receipt_utc": book["captured_at_utc"],
        "coinbase_receipt_utc": trade["captured_at_utc"],
        "post_kraken_request_started_utc": start.isoformat(timespec="microseconds"),
        "post_kraken_receipt_utc": receipt.isoformat(timespec="microseconds"),
        "baseline_kraken_row_hash": book["row_hash"],
        "coinbase_row_hash": trade["row_hash"],
        "frozen_policy_sha256": frozen["policy_sha256"],
        "frozen_hypothesis": original["hypothesis"],
        "best_bid_usd": quote["best_bid_usd"],
        "best_ask_usd": quote["best_ask_usd"],
        "provider_payload_sha256": quote["provider_payload_sha256"],
    }
    saved = append(output, observation)
    return {
        "status": "APPENDED_CAUSAL_REST_SNAPSHOT_NOT_EXECUTABLE",
        "appended": True, "slot_utc": saved["slot_utc"],
        "frozen_hypothesis": saved["frozen_hypothesis"],
        "new_row_hash": saved["row_hash"],
        "broker_orders": 0, "ntfy_messages": 0, "portfolio_writes": 0,
        "original_source_tape_writes": 0,
    }


def score(rows, *, as_of: dt.datetime):
    now = utc(as_of)
    # As-of filtering ensures no future observation can affect earlier reports.
    visible = [x for x in rows if instant(x["post_kraken_receipt_utc"]) <= now]
    observations = []
    for row in visible:
        known = instant(row["coinbase_receipt_utc"])
        entry = instant(row["post_kraken_receipt_utc"])
        outcomes = {}
        for horizon in HORIZONS_H:
            target = known + dt.timedelta(hours=horizon)
            key = str(horizon)
            if now < target:
                outcomes[key] = {"status": "NOT_YET_MATURED"}
                continue
            later = [r for r in visible
                     if target <= instant(r["post_kraken_receipt_utc"])
                     <= target + MAX_HORIZON_LAG
                     and instant(r["post_kraken_receipt_utc"]) > entry]
            if not later:
                outcomes[key] = {"status": "NO_TIMELY_LATER_OBSERVED_QUOTE"}
                continue
            exit_quote = later[0]
            details = {"status": "OBSERVED_REST_QUOTES_NOT_EXECUTABLE",
                       "later_quote_hash": exit_quote["row_hash"],
                       "later_quote_receipt_utc": exit_quote["post_kraken_receipt_utc"],
                       "hypothetical_spot_long_return_pct_by_fee_bps": None}
            if row["frozen_hypothesis"] == "PAPER_BULL":
                ask = positive(row["best_ask_usd"])
                bid = positive(exit_quote["best_bid_usd"])
                details["hypothetical_spot_long_return_pct_by_fee_bps"] = {
                    str(fee): round(100 * (
                        bid * (1-fee/10000) / (ask * (1+fee/10000)) - 1
                    ), 6) for fee in FEE_BPS
                }
            outcomes[key] = details
        observations.append({
            "slot_utc": row["slot_utc"],
            "frozen_hypothesis": row["frozen_hypothesis"],
            "entry_rest_quote_hash": row["row_hash"],
            "horizons": outcomes,
        })
    active = [r for r in visible if r["frozen_hypothesis"] != "PAPER_NEUTRAL"]
    distinct_days = len({instant(r["coinbase_receipt_utc"]).date() for r in active})
    return {
        "kind": "paper_only_forward_post_signal_quote_outcomes_v1",
        "as_of_utc": now.isoformat(),
        "prospective_causal_quote_rows": len(visible),
        "frozen_non_neutral_hypotheses": len(active),
        "distinct_days_with_active_hypotheses": distinct_days,
        "minimum_60_non_neutral_across_30_days": len(active) >= 60 and distinct_days >= 30,
        "market_trade_recommendation": "NONE",
        "after_cost_ASX_IBIT_AUD_outperformance_validated": False,
        "broker_orders": 0, "ntfy_messages": 0,
        "observations": observations,
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description="Post-signal research tape, no trading")
    parser.add_argument("--self-check-only", action="store_true")
    parser.add_argument("--score-only", action="store_true")
    parser.add_argument("--output", type=Path, default=REPORT)
    args = parser.parse_args(argv)
    prior = read_tape()
    if args.self_check_only:
        print(json.dumps({"validated_paper_quote_rows": len(prior),
                          "no_source_writes": True}))
        return
    if args.score_only:
        report = score(prior, as_of=dt.datetime.now(UTC))
    else:
        status = json.loads(CAPTURE_STATUS.read_text(encoding="utf-8"))
        result = collect(status=status)
        report = {"new_quote_attempt": result, "forward_score":
                  score(read_tape(), as_of=dt.datetime.now(UTC))}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, sort_keys=True)+"\n",
                           encoding="utf-8")
    print(json.dumps({key: val for key, val in report.items()
                      if key != "observations"}, sort_keys=True))


if __name__ == "__main__":
    main()
