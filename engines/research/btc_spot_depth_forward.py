"""Research-only prospective Kraken XBT/USD spot order book.
No trades, portfolio writes, ntfy, model imports, or historical backfill.
The capture instant is client HTTP response receipt, NOT a Kraken venue timestamp.
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
from typing import Any, Callable

SOURCE = "Kraken_Spot_REST_Depth_XBTUSD"
ENDPOINT = "https://api.kraken.com/0/public/Depth"
PAIR = "XBTUSD"
MARKET_KEYS = frozenset(("XXBTZUSD", "XBTUSD"))
REQUEST_COUNT = 500
BAND_FRACTION = 0.0025
SLOT_HOURS = 6
MAX_TOP_TIER_AGE_SECONDS = 15 * 60
OUTPUT = (Path(__file__).resolve().parents[2] / "data" /
          "research_forward_validation" / "kraken_spot_depth_forward.csv")
GENESIS = "0" * 64
COLUMNS = (
    "slot_utc", "captured_at_utc", "provider", "market", "quote_currency",
    "observation_clock", "requested_depth_levels", "bids_count", "asks_count",
    "best_bid_usd", "best_ask_usd", "mid_usd", "spread_bps",
    "bids_btc_25bps", "asks_btc_25bps", "bids_usd_25bps", "asks_usd_25bps",
    "bid_depth_share_pct_25bps", "complete_25bps_band", "research_signal",
    "provider_payload_sha256", "previous_row_hash", "row_hash",
)


def _utc(value: dt.datetime) -> dt.datetime:
    if not isinstance(value, dt.datetime) or value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("A timezone-aware capture instant is required")
    return value.astimezone(dt.timezone.utc)


def _finite_positive(value: Any, field: str) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError, OverflowError) as err:
        raise ValueError(f"Invalid {field}") from err
    if not math.isfinite(number) or number <= 0:
        raise ValueError(f"Non-positive/nonfinite {field}")
    return number


def _parse_levels(raw: Any, *, side: str, now: dt.datetime) -> list[tuple[float, float, float]]:
    if not isinstance(raw, list) or len(raw) < 2 or len(raw) > REQUEST_COUNT:
        raise ValueError(f"Malformed {side} book length")
    parsed: list[tuple[float, float, float]] = []
    previous: float | None = None
    for level in raw:
        if not isinstance(level, (list, tuple)) or len(level) < 3:
            raise ValueError(f"Malformed {side} order-book tier")
        price = _finite_positive(level[0], f"{side} price")
        amount = _finite_positive(level[1], f"{side} volume")
        timestamp = _finite_positive(level[2], f"{side} update timestamp")
        # Deep resting orders can be old; old TOP quotes are a stale-book risk.
        if timestamp > now.timestamp() + 60:
            raise ValueError(f"Future {side} level timestamp")
        if previous is not None and ((side == "bid" and price >= previous)
                                     or (side == "ask" and price <= previous)):
            raise ValueError(f"Unsorted/duplicate {side} price levels")
        previous = price
        parsed.append((price, amount, timestamp))
    return parsed


def summarize_book(payload: dict[str, Any], *, captured_at_utc: dt.datetime) -> dict[str, str]:
    """Compute depth only for a fully covered 25bp band; never emit a trade."""
    now = _utc(captured_at_utc)
    if not isinstance(payload, dict) or payload.get("error") != []:
        raise ValueError("Kraken API error or malformed envelope")
    data = payload.get("result")
    if not isinstance(data, dict) or len(data) != 1:
        raise ValueError("One unambiguous spot market is required")
    key = next(iter(data))
    if key not in MARKET_KEYS or not isinstance(data[key], dict):
        raise ValueError("Refuse non-XBT/USD Kraken market")
    book = data[key]
    bids = _parse_levels(book.get("bids"), side="bid", now=now)
    asks = _parse_levels(book.get("asks"), side="ask", now=now)
    if (now.timestamp() - bids[0][2] > MAX_TOP_TIER_AGE_SECONDS
        or now.timestamp() - asks[0][2] > MAX_TOP_TIER_AGE_SECONDS):
        raise ValueError("Stale Kraken top-of-book quotes")
    best_bid, best_ask = bids[0][0], asks[0][0]
    if best_ask <= best_bid:
        raise ValueError("Crossed or locked order book")
    mid = (best_bid + best_ask) / 2
    spread_bps = (best_ask - best_bid) / mid * 10000
    if not 0 < spread_bps < 250:
        raise ValueError("Implausibly wide market or invalid BTC book")
    low, high = mid*(1-BAND_FRACTION), mid*(1+BAND_FRACTION)
    complete = bids[-1][0] <= low and asks[-1][0] >= high
    in_bids = [(p, v) for p, v, _ in bids if p >= low]
    in_asks = [(p, v) for p, v, _ in asks if p <= high]
    bid_btc, ask_btc = sum(v for _,v in in_bids), sum(v for _,v in in_asks)
    bid_usd = sum(p*v for p,v in in_bids)
    ask_usd = sum(p*v for p,v in in_asks)
    if not (bid_usd > 0 and ask_usd > 0):
        raise ValueError("No two-sided depth within band")
    raw_hash = hashlib.sha256(json.dumps(payload, sort_keys=True,
                       separators=(",", ":"), allow_nan=False).encode("utf-8")).hexdigest()
    captured = now.isoformat(timespec="seconds")
    slot = now.replace(hour=(now.hour//SLOT_HOURS)*SLOT_HOURS,
                       minute=0, second=0, microsecond=0)
    return {
        "slot_utc": slot.isoformat(), "captured_at_utc": captured,
        "provider": SOURCE, "market": "XBT/USD", "quote_currency": "USD",
        "observation_clock": "HTTP_response_receipt_not_exchange_timestamp",
        "requested_depth_levels": str(REQUEST_COUNT),
        "bids_count": str(len(bids)), "asks_count": str(len(asks)),
        "best_bid_usd": f"{best_bid:.6f}", "best_ask_usd": f"{best_ask:.6f}",
        "mid_usd": f"{mid:.6f}", "spread_bps": f"{spread_bps:.6f}",
        "bids_btc_25bps": f"{bid_btc:.8f}", "asks_btc_25bps": f"{ask_btc:.8f}",
        "bids_usd_25bps": f"{bid_usd:.2f}", "asks_usd_25bps": f"{ask_usd:.2f}",
        "bid_depth_share_pct_25bps": (f"{100*bid_usd/(bid_usd+ask_usd):.6f}"
                                      if complete else ""),
        "complete_25bps_band": str(complete),
        "research_signal": "OBSERVATION_ONLY_NO_TRADE",
        "provider_payload_sha256": raw_hash,
    }


def _signature(row: dict[str, str]) -> str:
    canonical = {key: row[key] for key in COLUMNS if key != "row_hash"}
    return hashlib.sha256(json.dumps(canonical, sort_keys=True,
                                    separators=(",", ":"),
                                    ensure_ascii=True).encode("utf-8")).hexdigest()


def read_verified_tape(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open("r", newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        if tuple(reader.fieldnames or ()) != COLUMNS:
            raise ValueError("Historical tape has a different schema")
        rows = list(reader)
    if not rows:
        raise ValueError("Existing empty/tampered tape must not be reset")
    prev_hash = GENESIS
    previous_slot: dt.datetime | None = None
    for row in rows:
        if set(row) != set(COLUMNS):
            raise ValueError("Malformed historical tape row")
        if row["previous_row_hash"] != prev_hash or row["row_hash"] != _signature(row):
            raise ValueError("Immutable spot-depth tape hash-chain violation")
        try:
            slot = _utc(dt.datetime.fromisoformat(row["slot_utc"]))
            capture = _utc(dt.datetime.fromisoformat(row["captured_at_utc"]))
        except (TypeError, ValueError) as err:
            raise ValueError("Invalid historical tape timestamps") from err
        if (slot.hour % SLOT_HOURS != 0 or slot.minute != 0 or slot.second != 0
            or not slot <= capture < slot+dt.timedelta(hours=SLOT_HOURS)
            or (previous_slot is not None and slot <= previous_slot)
            or row["provider"] != SOURCE or row["market"] != "XBT/USD"
            or row["research_signal"] != "OBSERVATION_ONLY_NO_TRADE"):
            raise ValueError("Tape chronology/market invariants failed")
        if row["complete_25bps_band"] not in ("True", "False") or (
            row["complete_25bps_band"] == "False" and row["bid_depth_share_pct_25bps"]
        ):
            raise ValueError("Partial book has fabricated depth share")
        prev_hash, previous_slot = row["row_hash"], slot
    return rows


def append_snapshot(path: Path, observation: dict[str, str]) -> bool:
    """Only a strictly newer capture slot is appended; no backfill."""
    if set(observation) != set(COLUMNS)-{"previous_row_hash", "row_hash"}:
        raise ValueError("Unexpected snapshot observation fields")
    existing = read_verified_tape(path)
    if existing:
        last = _utc(dt.datetime.fromisoformat(existing[-1]["slot_utc"]))
        current = _utc(dt.datetime.fromisoformat(observation["slot_utc"]))
        if current == last:
            return False
        if current < last:
            raise ValueError("Historical snapshot/backfill forbidden")
    row = {**observation,
           "previous_row_hash": existing[-1]["row_hash"] if existing else GENESIS}
    row["row_hash"] = _signature(row)
    new_rows = existing+[row]
    buffer = io.StringIO(newline="")
    writer = csv.DictWriter(buffer, fieldnames=COLUMNS, lineterminator="\n")
    writer.writeheader()
    writer.writerows(new_rows)
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", newline="",
                                     dir=path.parent, prefix=".depth-", delete=False) as f:
        temp_name = f.name
        f.write(buffer.getvalue())
    try:
        os.replace(temp_name, path)
    finally:
        if os.path.exists(temp_name):
            os.unlink(temp_name)
    if read_verified_tape(path) != new_rows:
        raise AssertionError("Post-write hash verification failed")
    return True


def fetch_kraken_book(*, timeout: int = 12) -> dict[str, Any]:
    """Public read-only REST endpoint, no credentials or order routing."""
    import requests
    response = requests.get(
        ENDPOINT, params={"pair": PAIR, "count": REQUEST_COUNT},
        headers={"User-Agent": "BTC-Composite-paper-only-spot-depth/1.0"},
        timeout=timeout)
    response.raise_for_status()
    return response.json()


def run_once(*, path: Path = OUTPUT,
             fetcher: Callable[[], dict[str, Any]] = fetch_kraken_book,
             clock: Callable[[], dt.datetime] = lambda: dt.datetime.now(dt.timezone.utc)
             ) -> bool:
    now = _utc(clock())
    existing = read_verified_tape(path)
    slot = now.replace(hour=now.hour//SLOT_HOURS*SLOT_HOURS,
                       minute=0, second=0, microsecond=0)
    if existing and existing[-1]["slot_utc"] == slot.isoformat():
        return False
    payload = fetcher()
    receipt = _utc(clock())
    if receipt < now or receipt-now > dt.timedelta(minutes=2):
        raise ValueError("Public source response timing inconsistent")
    if receipt.replace(hour=receipt.hour//SLOT_HOURS*SLOT_HOURS,
                       minute=0, second=0, microsecond=0) != slot:
        raise ValueError("Crossed capture slot; retry next slot")
    return append_snapshot(path, summarize_book(payload, captured_at_utc=receipt))


def main() -> None:
    parser = argparse.ArgumentParser(description="Paper-only prospective Kraken BTC depth")
    parser.add_argument("--self-check-only", action="store_true")
    parser.add_argument("--probe-only", action="store_true",
                        help="Fetch/parse a real public book without any persistence")
    args = parser.parse_args()
    if args.self_check_only and args.probe_only:
        parser.error("--probe-only and --self-check-only are mutually exclusive")
    read_verified_tape(OUTPUT)
    if args.probe_only:
        raw = fetch_kraken_book()
        row = summarize_book(raw, captured_at_utc=dt.datetime.now(dt.timezone.utc))
        print(json.dumps({
            "status": "PROBE_SUCCESS_NO_WRITES_NO_TRADES",
            "provider": row["provider"], "captured_at_utc": row["captured_at_utc"],
            "spread_bps": row["spread_bps"],
            "full_25bps_coverage": row["complete_25bps_band"],
        }, sort_keys=True))
    elif args.self_check_only:
        print("Existing depth tape verified; no network or write")
    else:
        appended = run_once()
        print("New paper-only spot-depth observation appended" if appended
              else "Current six-hour slot already captured; no change")


if __name__ == "__main__":
    main()
