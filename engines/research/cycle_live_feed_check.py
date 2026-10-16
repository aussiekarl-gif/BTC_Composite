"""Read-only public price health check: no broker, portfolio or notification access.

GitHub CI may run this as a nonblocking availability probe. Market data
must pass the SAME full prior-day cross-provider verification as Streamlit.
"""
from __future__ import annotations
import datetime as dt
import json

from engines.research.top_signal_horse_race import read_exported_history
from engines.research.verified_recent_price_bridge import fetch_public_series
from engines.research.cycle_market_feed import merge_verified_cycle_prices
from engines.research.cycle_trading_dashboard_model import build_dashboard_market
from engines.research.ibit_quote import fetch_ibit_quote


def probe_public_feeds(*,now=None):
    now=now or dt.datetime.now(dt.timezone.utc)
    today=now.date()
    result={
        "checked_at_utc":now.isoformat(),
        "data_only":True,
        "trades_placed":0,
        "ntfy_messages_sent":0,
        "market_ok":False,
        "ibit_quote_ok":False,
    }
    try:
        archive=read_exported_history()
        remote,fx=fetch_public_series(asof=today.isoformat(),timeout=20)
        combined,verification=merge_verified_cycle_prices(
            archive,remote,utc_today=today)
        market=build_dashboard_market(combined,fx,asof=today.isoformat())
        days=(today-dt.date.fromisoformat(market["asof_date"])).days
        result.update({
            "market_ok":days<=3 and market["usd_aud_prior"] is not None,
            "data_age_days":days,
            "market_asof":market["asof_date"],
            "crosschecked_overlaps":verification["overlap_days"],
            "fx_date":market["fx_source_date"],
            "market_issue":(
                None if days<=3 and market["usd_aud_prior"] is not None
                else "Stale market or missing historical FX"
            ),
        })
    except Exception as exc:
        result["market_issue"]=f"{type(exc).__name__}: {str(exc)[:240]}"
    try:
        quote=fetch_ibit_quote(now=now,timeout=10)
        result.update({
            "ibit_quote_ok":True,
            "ibit_quote_asof_utc":quote["timestamp_utc"],
            "ibit_quote_age_hours":quote["age_hours"],
            "source":quote["provider"],
        })
    except Exception as exc:
        result["ibit_quote_issue"]=f"{type(exc).__name__}: {str(exc)[:240]}"
    return result


if __name__=="__main__":
    d=probe_public_feeds()
    print(json.dumps(d,indent=2))
    if not d["market_ok"] or not d["ibit_quote_ok"]:
        raise SystemExit(1)
