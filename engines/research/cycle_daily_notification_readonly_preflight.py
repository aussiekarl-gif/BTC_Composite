"""One-time read-only full daily ntfy render vs shared Cycle BTC sources.

Never import/call send_ntfy, never post to ntfy, never read personal
portfolio or run Streamlit, never touch GitHub delivery reservation.
The TODAY message renderer may fetch normal public IBIT/halving quotes,
but any BUY/SELL recommendation must match strict yesterday completed
BTC/Kraken/Blockchain shared market and original unchanged allocation.

Run as a GitHub Actions PR preflight BEFORE next scheduled daily message.
CI failure means a REAL operational discrepancy, not a license to send
an extra test notification.
"""
from __future__ import annotations

import datetime as dt
import json

from cycle_trading_daily_ntfy import daily_message
from engines.research.cycle_trade_allocation import (
    DEFAULT_BUY_STYLE,calculate_allocation_signal,
)
from engines.research.cycle_live_completed_utc_prices import (
    fetch_cycle_live_sources,merge_verified_live_cycle_prices,
)
from engines.research.cycle_trading_dashboard_model import build_dashboard_market
from engines.research.top_signal_horse_race import read_exported_history

VERIFIED_2026_HALVING_DATE="2024-04-20"


def main():
    now=dt.datetime.now(dt.timezone.utc)
    today=now.date()
    if today.year!=2026:
        raise ValueError("This Oct 2026 frozen-halving preflight must be refreshed")
    source=read_exported_history()
    raw,fx,kraken=fetch_cycle_live_sources(asof=str(today))
    price,meta=merge_verified_live_cycle_prices(
        source,raw,kraken,utc_today=today)
    market=build_dashboard_market(
        price,fx,asof=str(today),
        confirmed_halving_date=VERIFIED_2026_HALVING_DATE)
    expected=calculate_allocation_signal(
        market,buy_style=DEFAULT_BUY_STYLE)
    # IMPORTANT: do NOT inject a market into the daily function.
    # Its own real fetch/halving validation must reproduce the same
    # independently calculated shared source signal.
    date,body=daily_message(
        now=now,quote=False,market=None,
        reference_snapshot_fetcher=None)
    checks=[
        f"Cycle signal: {expected['signal']}",
        f"BUY allocation: {expected['buy_pct_cash']:.2f}%",
        f"SELL allocation: {expected['sell_pct_held']:.2f}%",
        f"BTC close US${market['btc_price_usd']:,.0f} ({market['asof_date']})",
        f"Prior 200WMA US${market['prior_200wma_usd']:,.0f}",
        f"{today-dt.timedelta(days=1)}",
    ]
    missing=[row for row in checks if row not in body]
    if missing:
        raise AssertionError(
            "Daily ntfy independently fetched different/missing market "
            "input than Streamlit/shared market: "+repr(missing))
    if "Cycle signal: DATA UNAVAILABLE" in body:
        raise AssertionError("Daily notification is not able to produce valid BTC close")
    if "not a broker order" not in body:
        raise AssertionError("Missing trading research-only disclaimer")
    if "ASX:IBIT" not in body:
        raise AssertionError("Missing ASX quote status")
    result={
        "preflight_only_no_send":True,
        "local_message_date":date,
        "signal":expected["signal"],
        "buy_pct_remaining_cash":expected["buy_pct_cash"],
        "sell_pct_remaining_BTC":expected["sell_pct_held"],
        "verified_completed_utc_day":str(market["asof_date"]),
        "BTC_USD_close":round(float(market["btc_price_usd"]),2),
        "prior_200week_MA":round(float(market["prior_200wma_usd"]),2),
        "Kraken_recent_overlap_max_abs_percent":
            meta["recent_kraken_blockchain_max_diff_pct"],
        "all_message_market_lines_match_shared_model":True,
        "ntfy_posts_made":0,
        "delivery_reservation_changes":0,
        "real_trade_orders":0,
    }
    print("CYCLE_DAILY_RENDER_PREFLIGHT "+json.dumps(result,sort_keys=True))
    print("=== READ-ONLY INDICATIVE DAILY MESSAGE (NOT SENT) ===")
    print(body)


if __name__=="__main__":
    main()
