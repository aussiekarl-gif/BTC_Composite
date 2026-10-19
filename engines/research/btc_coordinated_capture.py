"""Coordinated, independent Kraken/Coinbase prospective sampler.

Separate verified immutable source tapes; one GitHub runner handles both
public HTTP requests closely together. A failure of ONE data provider never
fabricates the other data provider or rewrites either tape. Never trades,
promotes a signal, reads user portfolio, writes Google Sheets, or sends ntfy.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
from pathlib import Path
from typing import Callable

from engines.research.btc_spot_depth_forward import (
    OUTPUT as KRAKEN_OUTPUT, read_verified_tape,
    run_once as run_kraken,
)
from engines.research.coinbase_trade_samples import (
    OUTPUT as COINBASE_OUTPUT, read_tape,
    run_once as run_coinbase,
)

MAX_COMPARISON_SKEW = dt.timedelta(minutes=5)
ARTIFACT = Path("artifacts/btc_microstructure_capture_status.json")


def _stamp(s: str) -> dt.datetime:
    t = dt.datetime.fromisoformat(s)
    if t.tzinfo is None:
        raise ValueError("Market capture missing UTC timezone")
    return t.astimezone(dt.timezone.utc)


def collect(
    *, kraken_path: Path = KRAKEN_OUTPUT,
    coinbase_path: Path = COINBASE_OUTPUT,
    kraken_runner: Callable = run_kraken,
    coinbase_runner: Callable = run_coinbase,
) -> dict:
    """Validate existing hash chains BEFORE IO; separately attempt each feed."""
    read_verified_tape(kraken_path)
    read_tape(coinbase_path)
    errors: list[str] = []
    results: dict[str,str] = {}
    for name,fn,path in (
        ("kraken",kraken_runner,kraken_path),
        ("coinbase",coinbase_runner,coinbase_path),
    ):
        try:
            saved = fn(path=path)
            results[name] = "NEW_SNAPSHOT" if saved else "EXISTING_SLOT"
        except Exception as err:
            # No credentials or personal portfolio info in either public
            # collector. Record terse failure without enabling synthetic data.
            results[name] = "PROVIDER_CAPTURE_FAILED"
            errors.append(f"{name}: {type(err).__name__}")

    # Verify BOTH complete tapes again; if integrity is broken, fail
    # immediately; the GitHub job must NOT commit an invalid capture.
    books = read_verified_tape(kraken_path)
    fills = read_tape(coinbase_path)
    last_book = books[-1] if books else None
    last_fill = fills[-1] if fills else None
    paired = False
    skew_seconds = None
    if last_book and last_fill and last_book["slot_utc"] == last_fill["slot_utc"]:
        skew_seconds = abs((_stamp(last_book["captured_at_utc"])
                           - _stamp(last_fill["captured_at_utc"])).total_seconds())
        paired = skew_seconds <= MAX_COMPARISON_SKEW.total_seconds()
    return {
        "kind":"research_only_public_BTC_microstructure_capture",
        "kraken_status":results["kraken"],
        "coinbase_status":results["coinbase"],
        "kraken_tape_rows":len(books),
        "coinbase_tape_rows":len(fills),
        "latest_same_utc_slot":bool(
            last_book and last_fill and last_book["slot_utc"]==last_fill["slot_utc"]),
        "latest_capture_skew_seconds":skew_seconds,
        "latest_pair_within_5_min":paired,
        "provider_capture_failures":errors,
        "all_providers_ok":not errors,
        "new_trading_signals":0,
        "new_ntfy_messages":0,
        "personal_portfolio_writes":0,
        "scheduled_runner_jobs_per_day":4,
    }


def main():
    p=argparse.ArgumentParser(description="Research-only coordinated Kraken/Coinbase snapshot")
    p.add_argument("--output",type=Path,default=ARTIFACT)
    args=p.parse_args()
    data=collect()
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps(data,indent=2,sort_keys=True)+"\n",encoding="utf-8")
    print(json.dumps(data,sort_keys=True))


if __name__=="__main__":
    main()
