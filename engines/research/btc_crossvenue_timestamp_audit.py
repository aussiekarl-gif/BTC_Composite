"""Research-only cross-venue timestamp audit; never produces a trading signal.

Kraken book is a resting order snapshot; Coinbase trades are a bounded
short sample. They are NOT two independent voting models or executable
arbitrage prices, even when their collection timestamps align.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import math
from pathlib import Path

from engines.research.btc_spot_depth_forward import (
    OUTPUT as KRAKEN_FILE, read_verified_tape as read_kraken,
)
from engines.research.coinbase_trade_samples import (
    OUTPUT as COINBASE_FILE, read_tape as read_coinbase,
)

MAX_SKEW = dt.timedelta(minutes=5)
MAX_DATA_AGE = dt.timedelta(hours=12)
OUTLIER_PCT = 2.0


def _utc(value: dt.datetime) -> dt.datetime:
    if not isinstance(value, dt.datetime) or value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("Timezone-aware as-of required")
    return value.astimezone(dt.timezone.utc)


def _parse(value: str) -> dt.datetime:
    return _utc(dt.datetime.fromisoformat(value))


def compare(*, kraken_path: Path = KRAKEN_FILE, coinbase_path: Path = COINBASE_FILE,
            as_of_utc: dt.datetime) -> dict[str, object]:
    """Verify immutable source tapes, then return diagnostics, never an action."""
    now = _utc(as_of_utc)
    books = read_kraken(kraken_path)
    fills = read_coinbase(coinbase_path)
    result: dict[str,object] = {
        "status": "NOT_COMPARABLE", "research_only": True,
        "is_trade_signal": False, "executable_order_aud": 0.0,
        "kraken_depth_is_executed_volume": False,
        "coinbase_sample_is_complete_interval": False,
        "consensus_agent_votes": 0,
    }
    if not books or not fills:
        return {**result,"reason":"One or both real forward data tapes not yet captured"}
    by_slot_books = {x["slot_utc"]:x for x in books}
    by_slot_fills = {x["slot_utc"]:x for x in fills}
    common = sorted(set(by_slot_books)&set(by_slot_fills))
    if not common:
        return {**result,"reason":"No identical UTC sampling slot"}
    slot=common[-1]
    book,fill=by_slot_books[slot],by_slot_fills[slot]
    bt,ft=_parse(book["captured_at_utc"]),_parse(fill["captured_at_utc"])
    result.update({
        "slot_utc":slot, "kraken_captured_at_utc":bt.isoformat(),
        "coinbase_captured_at_utc":ft.isoformat(),
        "capture_skew_seconds":round(abs((bt-ft).total_seconds()),3),
        "coinbase_sample_duration_seconds":fill["sample_duration_seconds"],
        "coinbase_observed_trades":int(fill["observed_trades"]),
    })
    if bt>now or ft>now:
        return {**result,"reason":"Future captured evidence cannot be scored"}
    if max(now-bt,now-ft)>MAX_DATA_AGE:
        return {**result,"reason":"Data older than 12 hours at review time"}
    if abs(bt-ft)>MAX_SKEW:
        return {**result,"reason":"Captures over five minutes apart; no cross-venue price comparison"}
    if book["complete_25bps_band"] != "True":
        return {**result,"reason":"Kraken 25bp book depth incomplete"}
    try:
        mid=float(book["mid_usd"])
        vwap=float(fill["sample_vwap_usd"])
        depthshare=float(book["bid_depth_share_pct_25bps"])
        buyshare=float(fill["aggressor_buy_share_pct_sample"])
    except (TypeError,ValueError,OverflowError):
        return {**result,"reason":"Malformed numeric observations"}
    if (not all(math.isfinite(x) for x in (mid,vwap,depthshare,buyshare))
        or mid<=0 or vwap<=0 or not 0<=depthshare<=100
        or not 0<=buyshare<=100):
        return {**result,"reason":"Unusable values"}
    difference_pct=100*(vwap/mid-1)
    result.update({
        "kraken_mid_usd":round(mid,6),
        "coinbase_sample_vwap_usd":round(vwap,6),
        "coinbase_vwap_vs_kraken_mid_pct":round(difference_pct,4),
        "kraken_resting_bid_depth_share_pct":round(depthshare,4),
        "coinbase_buyer_initiated_sample_share_pct":round(buyshare,4),
    })
    if abs(difference_pct)>OUTLIER_PCT:
        return {**result, "status":"PRICE_DIVERGENCE_REVIEW",
                "reason":"Large differences: providers are NOT executable arbitrage quotes"}
    return {**result,"status":"NEAR_TIME_RESEARCH_OBSERVATION",
            "reason":"Comparable capture times, incompatible measurement windows: no trading advice"}


def main():
    p=argparse.ArgumentParser(description="Read-only Bitcoin source-comparison audit")
    p.add_argument("--now", help="ISO UTC as-of instant, defaults to current UTC")
    args=p.parse_args()
    now=dt.datetime.fromisoformat(args.now) if args.now else dt.datetime.now(dt.timezone.utc)
    print(json.dumps(compare(as_of_utc=now),indent=2,sort_keys=True))


if __name__=="__main__":
    main()
