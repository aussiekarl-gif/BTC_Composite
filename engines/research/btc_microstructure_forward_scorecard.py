"""Pre-registered BTC microstructure forward scorecard; read-only and paper-only.

This is NOT a new signal for the Streamlit / ntfy / execution portfolio.
Sources are immutable Coinbase bounded trade samples and Kraken REST depth,
which have different measurement windows and must never count as independent
agent votes. Score ONLY later, genuinely observed Kraken quote snapshots.
"""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import math
from pathlib import Path
from typing import Any

from engines.research.btc_spot_depth_forward import OUTPUT as DEPTH_PATH, read_verified_tape
from engines.research.coinbase_trade_samples import OUTPUT as TRADES_PATH, read_tape

UTC = dt.timezone.utc
# Freeze BEFORE eligible 2026-10-19 07:xx UTC sampling slot. Never apply to
# earlier Oct 18 observations after inspecting their subsequent returns.
FROZEN_AFTER = dt.datetime(2026, 10, 19, 2, 0, tzinfo=UTC)
POLICY_NAME = "microstructure_joint_extremes_60_40_paper_v1"
HORIZONS_HOURS = (6, 24, 168)
MAX_CAPTURE_SKEW = dt.timedelta(minutes=5)
MAX_HORIZON_LAG = dt.timedelta(minutes=90)
MAX_COINBASE_SAMPLE_SECONDS = 300.0
THRESHOLD_HIGH = 60.0
THRESHOLD_LOW = 40.0
MIN_DISTINCT_DAYS = 30
MIN_PAIRED_SAMPLES = 60


def _time(raw: str) -> dt.datetime:
    try:
        x = dt.datetime.fromisoformat(raw)
    except (TypeError, ValueError) as err:
        raise ValueError("Invalid source timestamp") from err
    if x.tzinfo is None or x.utcoffset() is None:
        raise ValueError("Unzoned source timestamp")
    return x.astimezone(UTC)


def _finite(raw: Any) -> float:
    try:
        x = float(raw)
    except (TypeError, ValueError, OverflowError) as err:
        raise ValueError("Invalid numeric source field") from err
    if not math.isfinite(x):
        raise ValueError("Nonfinite numeric source field")
    return x


def policy_sha256() -> str:
    frozen = {
        "name": POLICY_NAME, "freeze_utc": FROZEN_AFTER.isoformat(),
        "horizons_hours": list(HORIZONS_HOURS),
        "max_skew_seconds": MAX_CAPTURE_SKEW.total_seconds(),
        "max_lag_seconds": MAX_HORIZON_LAG.total_seconds(),
        "maximum_coinbase_window_seconds": MAX_COINBASE_SAMPLE_SECONDS,
        "high_threshold": THRESHOLD_HIGH,
        "low_threshold": THRESHOLD_LOW,
    }
    return hashlib.sha256(json.dumps(frozen, sort_keys=True,
                                     separators=(",", ":")).encode("utf-8")).hexdigest()


def build_report(depth: list[dict[str, str]],
                 trades: list[dict[str, str]], *,
                 as_of_utc: dt.datetime) -> dict[str, Any]:
    """Inputs must be validated by the immutable tape readers before calling.

    Never interpolate a missing future quote, use a last-known price as an
    outcome, infer a future date's market close, or backfill new trade samples.
    """
    if not isinstance(as_of_utc, dt.datetime) or as_of_utc.tzinfo is None or as_of_utc.utcoffset() is None:
        raise ValueError("Timezone-aware as-of required")
    now = as_of_utc.astimezone(UTC)
    for row in depth + trades:
        if _time(row["captured_at_utc"]) > now:
            raise ValueError("Future tape observation relative to audit instant")
    book_map = {r["slot_utc"]: r for r in depth}
    trade_map = {r["slot_utc"]: r for r in trades}
    if len(book_map) != len(depth) or len(trade_map) != len(trades):
        raise ValueError("Duplicate source slots")

    sorted_books = sorted(depth, key=lambda r: _time(r["captured_at_utc"]))
    base_rows: list[dict[str, Any]] = []
    excluded: dict[str, int] = {}
    def reject(reason: str):
        excluded[reason] = excluded.get(reason, 0) + 1

    for slot in sorted(set(book_map) | set(trade_map)):
        book, fill = book_map.get(slot), trade_map.get(slot)
        if book is None or fill is None:
            reject("missing_second_venue")
            continue
        bt, ft = _time(book["captured_at_utc"]), _time(fill["captured_at_utc"])
        known = max(bt, ft)
        if known < FROZEN_AFTER:
            reject("predates_frozen_policy")
            continue
        if abs(bt - ft) > MAX_CAPTURE_SKEW:
            reject("capture_skew_over_5min")
            continue
        if (book["complete_25bps_band"] != "True"
            or fill["sample_only_not_continuous"] != "True"):
            reject("unusable_source_coverage")
            continue
        window = _finite(fill["sample_duration_seconds"])
        last_age = _finite(fill["last_trade_age_seconds"])
        if (not 0 < window <= MAX_COINBASE_SAMPLE_SECONDS
            or last_age < 0 or last_age > 120
            or int(fill["observed_trades"]) < 20):
            reject("trade_sample_unusable")
            continue
        bidshare = _finite(book["bid_depth_share_pct_25bps"])
        buyshare = _finite(fill["aggressor_buy_share_pct_sample"])
        mid = _finite(book["mid_usd"])
        if not (0 <= bidshare <= 100 and 0 <= buyshare <= 100 and mid > 0):
            reject("unusable_numeric_input")
            continue

        # A hypothesis, NOT two independent votes. Both measure correlated spot
        # market microstructure. Neutral cases retained to avoid selection bias.
        if bidshare >= THRESHOLD_HIGH and buyshare >= THRESHOLD_HIGH:
            hypothesis = "PAPER_BULL"
        elif bidshare <= THRESHOLD_LOW and buyshare <= THRESHOLD_LOW:
            hypothesis = "PAPER_BEAR"
        else:
            hypothesis = "PAPER_NEUTRAL"
        source = {
            "slot_utc": slot,
            "known_at_utc": known.isoformat(),
            "kraken_price_observed_at_utc": bt.isoformat(),
            "kraken_source_hash": book["row_hash"],
            "coinbase_source_hash": fill["row_hash"],
            "baseline_kraken_mid_usd": round(mid, 6),
            "kraken_bid_depth_share_pct": round(bidshare, 6),
            "coinbase_aggressor_buy_share_sample_pct": round(buyshare, 6),
            "coinbase_sample_seconds": round(window, 3),
            "hypothesis": hypothesis,
            "horizons": {},
        }
        for hours in HORIZONS_HOURS:
            target = known + dt.timedelta(hours=hours)
            # Do not select earlier observations and pretend the horizon has
            # matured. Use earliest later actual price <= 90 minutes late.
            candidates = [b for b in sorted_books
                          if target <= _time(b["captured_at_utc"]) <= target + MAX_HORIZON_LAG]
            if not candidates:
                source["horizons"][str(hours)] = {
                    "status": "NO_EXACT_FUTURE_OBSERVATION",
                }
                continue
            future = candidates[0]
            future_time = _time(future["captured_at_utc"])
            future_mid = _finite(future["mid_usd"])
            if future_mid <= 0:
                raise ValueError("Bad future BTC midpoint")
            move = 100*(future_mid/mid-1)
            directional = (move if hypothesis == "PAPER_BULL" else
                           -move if hypothesis == "PAPER_BEAR" else None)
            source["horizons"][str(hours)] = {
                "status": "OBSERVED_PRICE_RETURN_NOT_EXECUTABLE",
                "future_kraken_source_hash": future["row_hash"],
                "observed_at_utc": future_time.isoformat(),
                "actual_elapsed_hours": round((future_time-known).total_seconds()/3600, 4),
                "btc_mid_return_pct": round(move, 6),
                "hypothesis_signed_move_pct": (round(directional, 6)
                                               if directional is not None else None),
            }
        base_rows.append(source)

    summary: dict[str, Any] = {}
    for hours in HORIZONS_HOURS:
        observed = [(p, p["horizons"][str(hours)]) for p in base_rows
                    if p["horizons"][str(hours)]["status"] == "OBSERVED_PRICE_RETURN_NOT_EXECUTABLE"]
        active = [(p, r) for p, r in observed if p["hypothesis"] != "PAPER_NEUTRAL"]
        distinct_days = len({p["known_at_utc"][:10] for p, _ in active})
        # Return values are observational BTC/USD Kraken mid changes, NOT
        # USD/AUD or IBIT fill results. Small n makes optimization misleading.
        summary[str(hours)] = {
            "matured_paired_observations": len(observed),
            "matured_non_neutral_hypotheses": len(active),
            "distinct_utc_days_with_non_neutral_hypotheses": distinct_days,
            "mean_signed_btc_mid_move_pct_exploratory": (
                round(sum(float(r["hypothesis_signed_move_pct"]) for _,r in active)
                      / len(active), 6) if active else None),
            "unconditional_matched_mean_btc_mid_return_pct": (
                round(sum(float(r["btc_mid_return_pct"]) for _,r in observed)
                      / len(observed), 6) if observed else None),
            "minimum_evidence_gate_met": (
                len(active) >= MIN_PAIRED_SAMPLES and distinct_days >= MIN_DISTINCT_DAYS),
            "valid_after_fee_trade_outperformance": False,
        }
    return {
        "policy_name": POLICY_NAME,
        "policy_sha256": policy_sha256(),
        "hypothesis_policy_frozen_after_utc": FROZEN_AFTER.isoformat(),
        "reported_at_utc": now.isoformat(),
        "label": "read_only_exploratory_forward_BTC_midpoint_scorecard_not_a_trading_strategy",
        "depth_observations_in_source": len(depth),
        "trade_sample_observations_in_source": len(trades),
        "strict_timestamp_paired_observations": len(base_rows),
        "pair_exclusion_reasons": dict(sorted(excluded.items())),
        "rules": {
            "freeze_high_pct": THRESHOLD_HIGH,
            "freeze_low_pct": THRESHOLD_LOW,
            "independently_verified_agent_votes": 0,
            "data_is_full_6h_trade_flow": False,
            "executable_IBIT_AUD_quote": False,
            "max_capture_skew_minutes": MAX_CAPTURE_SKEW.total_seconds()/60,
        },
        "horizon_summary": summary,
        "observations": base_rows,
        "approved_for_live_trading": False,
        "buy_or_sell_recommendation": "NONE",
        "new_ntfy_messages": 0,
        "portfolio_writes": 0,
    }


def main(argv=None):
    p = argparse.ArgumentParser(description="Read-only BTC forward microstructure scorecard")
    p.add_argument("--output", type=Path, default=Path("artifacts/btc_microstructure_forward_scorecard.json"))
    args = p.parse_args(argv)
    book = read_verified_tape(DEPTH_PATH)
    fills = read_tape(TRADES_PATH)
    result = build_report(book, fills, as_of_utc=dt.datetime.now(UTC))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, sort_keys=True, indent=2)+"\n", encoding="utf-8")
    print(json.dumps({k: v for k, v in result.items() if k != "observations"}, sort_keys=True))


if __name__ == "__main__":
    main()
