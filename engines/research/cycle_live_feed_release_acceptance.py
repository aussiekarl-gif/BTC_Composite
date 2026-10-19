"""Release acceptance and code-only rollback REHEARSAL for live BTC Cycle feed.

No BTC trading, private holdings, automated orders, ntfy POST, daily
reservation updates, provider archive changes, or GitHub rollback commits.
The currently-live UTC midnight D -> completed-close D-1 source correction
is preserved throughout. Streamlit market WATCH parity is NOT a claim about
account-specific whole-IBIT-unit BUY/SELL orders.
"""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
from pathlib import Path
from unittest.mock import patch

import pandas as pd

from cycle_trading_daily_ntfy import daily_message
from engines.research.top_signal_horse_race import read_exported_history
from engines.research.cycle_live_completed_utc_prices import (
    fetch_cycle_live_sources, aligned_blockchain_completed_utc_closes,
    merge_verified_live_cycle_prices,
)
from engines.research.cycle_halving_countdown import fetch_halving_countdown
from engines.research.cycle_trading_dashboard_model import build_dashboard_market
from engines.research.cycle_trade_allocation import (
    calculate_allocation_signal, DEFAULT_BUY_STYLE,
)
from engines.research.ibit_quote import fetch_ibit_quote

OUTPUT=Path("artifacts/cycle_live_feed_acceptance_rollback.json")
LIVE_GAP_POLICY=7
LEGACY_GAP_POLICY=3


def _hash_frame(frame: pd.DataFrame) -> str:
    if not isinstance(frame,pd.DataFrame) or not isinstance(frame.index,pd.DatetimeIndex):
        raise ValueError("Dated provider frame required")
    values=[(pd.Timestamp(i).isoformat(),[str(x) for x in record])
            for i,record in frame.iterrows()]
    return hashlib.sha256(json.dumps(values,sort_keys=True,separators=(",",":")
                                   ).encode("utf-8")).hexdigest()


def _source_wiring() -> dict:
    """Read the actual deployed source paths. Not a Streamlit browser E2E."""
    app=(Path(__file__).resolve().parent/"cycle_trading_app.py").read_text(encoding="utf-8")
    notify=(Path(__file__).resolve().parents[2]/"cycle_trading_daily_ntfy.py").read_text(encoding="utf-8")
    app_required=(
        "fetch_cycle_live_sources", "merge_verified_live_cycle_prices",
        "build_dashboard_market", "make_current_decision(",
        "feed_verified=", "verification.get(\"strict_close_date_verified\")",
    )
    notify_required=(
        "fetch_cycle_live_sources", "merge_verified_live_cycle_prices",
        "build_dashboard_market", "calculate_allocation_signal(",
        "strict_close_date_verified",
    )
    if not all(x in app for x in app_required):
        raise AssertionError("Streamlit shared source or feed-verified gate wiring changed")
    if not all(x in notify for x in notify_required):
        raise AssertionError("Daily notification shared source/market wiring changed")
    return {
        "Streamlit_and_ntfy_use_same_shared_BTC_market_module":True,
        "both_use_same_200WMA_market_builder":True,
        "Streamlit_has_verified_feed_and_portfolio_gates":True,
        "market_default_style_parity_tested":True,
        "account_specific_whole_IBIT_order_parity_asserted":False,
        "Streamlit_browser_UI_end_to_end_tested":False,
    }


def accept(archive,raw,fx,kraken,halving,*,now:dt.datetime,quote:dict|None):
    if not isinstance(now,dt.datetime) or now.tzinfo is None or now.utcoffset() is None:
        raise ValueError("Timezone-aware evaluation instant required")
    now=now.astimezone(dt.timezone.utc)
    today=now.date()
    if not isinstance(halving,dict) or not halving.get("halving_date_verified"):
        raise ValueError("Halving epoch unverified: no market recommendation")
    confirmed=halving.get("last_halving_date")
    if not confirmed or dt.date.fromisoformat(confirmed)>today-dt.timedelta(days=1):
        raise ValueError("Halving anchor newer than completed BTC close")
    originals={key:_hash_frame(value) for key,value in (
        ("archive",archive),("blockchain",raw),("dated_fx",fx),("kraken",kraken))}
    corrected=aligned_blockchain_completed_utc_closes(raw,utc_today=today)
    yesterday=pd.Timestamp(today-dt.timedelta(days=1),tz="UTC")
    if corrected.index[-1]>=pd.Timestamp(today,tz="UTC"):
        raise AssertionError("Blockchain D-1 correction exposed today's unfinished bar")
    prices,source=merge_verified_live_cycle_prices(
        archive,raw,kraken,utc_today=today)
    if not source.get("strict_close_date_verified") or prices.index[-1]!=yesterday:
        raise AssertionError("BTC feed not verified through exact previous UTC close")
    if not source.get("archive_raw_prices_preserved"):
        raise AssertionError("Archived BTC evidence not preserved")
    market=build_dashboard_market(
        prices,fx,asof=today.isoformat(),confirmed_halving_date=confirmed)
    if (pd.Timestamp(market["asof_date"]).date()!=yesterday.date()
        or market.get("usd_aud_prior") is None
        or not market.get("fx_source_date")):
        raise ValueError("Streamlit/ntfy both require completed BTC and dated FX")
    allocation=calculate_allocation_signal(market,buy_style=DEFAULT_BUY_STYLE)
    _,body=daily_message(now=now,market=market,quote=quote,
                          reference_snapshot_fetcher=None)
    checks=(
        f"Cycle signal: {allocation['signal']}",
        f"BUY allocation: {allocation['buy_pct_cash']:.2f}%",
        f"SELL allocation: {allocation['sell_pct_held']:.2f}%",
        f"BTC close US" + "$" + f"{market['btc_price_usd']:,.0f} ({market['asof_date']})",
        f"Prior 200WMA US" + "$" + f"{market['prior_200wma_usd']:,.0f}",
        "not a broker order",
    )
    missing=[line for line in checks if line not in body]
    if missing or "DATA UNAVAILABLE" in body:
        raise AssertionError("Market and ntfy parity failure: "+repr(missing))

    from engines.research import cycle_live_completed_utc_prices as live
    with patch.object(live,"MAX_LIVE_KRAKEN_GAP_DAYS",LEGACY_GAP_POLICY):
        try:
            legacy_prices,legacy_source=merge_verified_live_cycle_prices(
                archive,raw,kraken,utc_today=today)
        except ValueError as exc:
            legacy_status="FAIL_CLOSED"
            legacy_reason=type(exc).__name__+": "+str(exc)[:180]
        else:
            if not legacy_source.get("strict_close_date_verified"):
                raise AssertionError("Legacy bridge returned unverified data")
            legacy_status="VERIFIED_AVAILABLE"
            legacy_reason=None
            if not legacy_prices.equals(prices):
                raise AssertionError("Rollback alters existing completed BTC prices")
    gap=(yesterday-corrected.index[-1]).days
    if gap>LEGACY_GAP_POLICY and legacy_status!="FAIL_CLOSED":
        raise AssertionError("Legacy 3-day gap incorrectly accepted longer source delay")
    if gap<=LEGACY_GAP_POLICY and legacy_status!="VERIFIED_AVAILABLE":
        raise AssertionError("Legacy gap unexpectedly rejected unchanged valid source")
    if live.MAX_LIVE_KRAKEN_GAP_DAYS!=LIVE_GAP_POLICY:
        raise AssertionError("In-memory rollback rehearsal leaked into live code")

    # A missing INTERIOR required Kraken candle must never be interpolated.
    missing_day_status="NOT_APPLICABLE_NO_GAP"
    if gap>=2:
        missing=corrected.index[-1]+pd.Timedelta(days=1)
        broken=kraken.drop(index=missing)
        try:
            merge_verified_live_cycle_prices(archive,raw,broken,utc_today=today)
        except ValueError:
            missing_day_status="REJECTED_MISSING_REAL_KRAKEN_CLOSE"
        else:
            raise AssertionError("Missing Kraken completed day was not rejected")
    if originals!={key:_hash_frame(value) for key,value in (
        ("archive",archive),("blockchain",raw),("dated_fx",fx),("kraken",kraken))}:
        raise AssertionError("Provider inputs were modified in release acceptance")

    return {
        "status":"PASS_READ_ONLY_MARKET_SOURCE_RELEASE_ACCEPTANCE",
        "checked_at_utc":now.isoformat(),
        "completed_UTC_BTC_close_date":market["asof_date"],
        "BTC_close_USD":round(float(market["btc_price_usd"]),2),
        "prior_200WMA_USD":round(float(market["prior_200wma_usd"]),2),
        "default_style_market_watch":allocation["signal"],
        "market_buy_pct_remaining_cash":allocation["buy_pct_cash"],
        "market_sell_pct_remaining_holdings":allocation["sell_pct_held"],
        "ntfy_message_matches_shared_Streamlit_market_calculation":True,
        "Blockchain_last_aligned_daily_close":str(corrected.index[-1].date()),
        "Kraken_latest_completed_close":str(kraken.index[-1].date()),
        "verified_Kraken_Blockchain_recent_overlap_days":
            source["recent_kraken_blockchain_overlap_days"],
        "recent_overlap_max_diff_pct":source["recent_kraken_blockchain_max_diff_pct"],
        "actual_verified_Kraken_bridge_dates":source["kraken_contiguous_completed_day_bridge"],
        "live_gap_limit_days":LIVE_GAP_POLICY,
        "rollback_rehearsal_limit_days":LEGACY_GAP_POLICY,
        "rollback_rehearsal_status":legacy_status,
        "rollback_rehearsal_reason":legacy_reason,
        "rollback_retains_correct_Blockchain_D_minus_1_label":True,
        "rollback_changes_no_live_code_or_archived_data":True,
        "missing_Kraken_day_test":missing_day_status,
        "source_sha256_fingerprints":originals,
        "code_wiring":_source_wiring(),
        "portfolio_writes":0,
        "broker_orders":0,
        "notifications_sent":0,
        "delivery_reservations_changed":0,
        "strategy_rules_changed":False,
        "new_strategy_approved":False,
    }


def main(argv=None):
    p=argparse.ArgumentParser(description="BTC live source parity/rollback dry run, no ntfy")
    p.add_argument("--output",type=Path,default=OUTPUT)
    args=p.parse_args(argv)
    now=dt.datetime.now(dt.timezone.utc)
    archive=read_exported_history()
    raw,fx,kraken=fetch_cycle_live_sources(asof=now.date().isoformat())
    halving=fetch_halving_countdown(now=now)
    try:
        quote=fetch_ibit_quote(now=now)
    except Exception:
        # Missing ETF quote is independent from the BTC market WATCH.
        quote=None
    result=accept(archive,raw,fx,kraken,halving,now=now,quote=quote)
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps(result,indent=2,sort_keys=True)+"\n",encoding="utf-8")
    print("CYCLE_LIVE_RELEASE_ACCEPTANCE "+json.dumps(result,sort_keys=True))


if __name__=="__main__":
    main()
