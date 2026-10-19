"""No-send, no-portfolio diagnostic for Cycle Trading DATA UNAVAILABLE.

Runs each of the REAL public data steps used by one daily ntfy/Streamlit
message, separately, to pinpoint genuine market input failures rather
than confusing independent ASX quotes or other model labels with market
validation. Never posts, reserves a daily notification, changes market
source interpretation, fetches holdings, or places orders.
"""
from __future__ import annotations

import datetime as dt
import json
from pathlib import Path
from typing import Callable, Any

import pandas as pd

from engines.research.top_signal_horse_race import read_exported_history
from engines.research.verified_recent_price_bridge import fetch_public_series
from engines.research.cycle_forward_kraken_bridge import fetch_completed_kraken_daily
from engines.research.cycle_live_completed_utc_prices import merge_verified_live_cycle_prices
from engines.research.cycle_halving_countdown import fetch_halving_countdown
from engines.research.cycle_trading_dashboard_model import build_dashboard_market
from engines.research.cycle_trade_allocation import calculate_allocation_signal,DEFAULT_BUY_STYLE

OUTPUT=Path("artifacts/cycle_daily_market_unavailability_diagnostic.json")


def diagnose(*, now: dt.datetime,
             archive_fetcher: Callable[[],Any]=read_exported_history,
             price_fx_fetcher: Callable=fetch_public_series,
             kraken_fetcher: Callable=fetch_completed_kraken_daily,
             halving_fetcher: Callable=fetch_halving_countdown) -> dict:
    if not isinstance(now,dt.datetime) or now.tzinfo is None or now.utcoffset() is None:
        raise ValueError("Timezone-aware UTC diagnostic instant required")
    utcnow=now.astimezone(dt.timezone.utc)
    today=utcnow.date()
    diag={
        "kind":"READ_ONLY_CYCLE_DAILY_MARKET_AVAILABILITY_DIAGNOSTIC",
        "diagnostic_at_utc":utcnow.isoformat(),
        "required_completed_btc_close_date_utc":str(today-dt.timedelta(days=1)),
        "steps":{},
        "cause":"UNDETERMINED",
        "cycle_watch":"DATA_UNAVAILABLE",
        "trading_recommendation_or_order":False,
        "ntfy_messages_sent":0,
        "notification_reservations_changed":0,
        "portfolio_reads_or_writes":0,
        "market_rules_modified":False,
    }

    def stage(name,func):
        try:
            result=func()
        except Exception as exc:
            # Only public model-data retrieval, no secrets in exception.
            diag["steps"][name]={
                "ok":False,"error_type":type(exc).__name__,
                "error_summary":str(exc)[:260],
            }
            diag["cause"]=name.upper()+"_FAILED"
            return False,None
        diag["steps"][name]={"ok":True}
        return True,result

    ok,history=stage("archived_BTC_history",archive_fetcher)
    if not ok:return diag
    ok,public=stage("Blockchain_BTC_and_prior_AUD_FX",
                     lambda:price_fx_fetcher(asof=str(today)))
    if not ok:return diag
    raw,fx=public
    diag["steps"]["Blockchain_BTC_and_prior_AUD_FX"].update({
        "chart_last_raw_tick_utc":str(raw.index[-1]) if not raw.empty else None,
        "AUD_FX_last_observation_utc":str(fx.index[-1]) if not fx.empty else None,
    })
    ok,kraken=stage("completed_Kraken_BTC_OHLC",
                     lambda:kraken_fetcher(utc_today=utcnow))
    if not ok:return diag
    diag["steps"]["completed_Kraken_BTC_OHLC"]["last_close_date_utc"] = (
        str(kraken.index[-1].date()) if not kraken.empty else None)
    ok,verified=stage("shared_BTC_completed_close_alignment",
                       lambda:merge_verified_live_cycle_prices(
                           history,raw,kraken,utc_today=today))
    if not ok:return diag
    btc_history,verification=verified
    diag["steps"]["shared_BTC_completed_close_alignment"].update({
        "verified_last_close_date_utc":str(btc_history.index[-1].date()),
        "strict_close_date_verified":bool(verification.get("strict_close_date_verified")),
        "overlap_with_Kraken_max_diff_pct":
            verification.get("recent_kraken_blockchain_max_diff_pct"),
    })
    ok,halving=stage("halving_epoch_metadata",
                      lambda:halving_fetcher(now=utcnow))
    if not ok:return diag
    date=halving.get("last_halving_date") if halving.get("halving_date_verified") else None
    if not date or dt.date.fromisoformat(date)>btc_history.index[-1].date():
        diag["cause"]="HALVING_EPOCH_UNVERIFIED"
        diag["steps"]["halving_epoch_metadata"].update({"ok":False,"error_type":"UnverifiedHalvingEpoch"})
        return diag
    ok,market=stage("shared_Cycle_market_math",
                     lambda:build_dashboard_market(
                         btc_history,fx,asof=str(today),
                         confirmed_halving_date=date))
    if not ok:return diag
    recorded=dt.date.fromisoformat(str(market["asof_date"]))
    if (recorded!=today-dt.timedelta(days=1)
        or market["usd_aud_prior"] is None):
        diag["cause"]="LATEST_COMPLETED_CLOSE_OR_PRIOR_FX_INVALID"
        diag["steps"]["shared_Cycle_market_math"].update({
            "ok":False, "market_asof":str(recorded),
            "FX_available":market.get("usd_aud_prior") is not None,
        })
        return diag
    ok,alloc=stage("unchanged_Cycle_allocation",
                   lambda:calculate_allocation_signal(
                       market,buy_style=DEFAULT_BUY_STYLE))
    if not ok:return diag
    diag["cause"]="NONE_INPUTS_VALID"
    diag["cycle_watch"]=alloc["signal"]
    diag["market_date_utc"]=str(market["asof_date"])
    diag["BTC_USD_close"]=float(market["btc_price_usd"])
    diag["prior_200WMA_USD"]=float(market["prior_200wma_usd"])
    diag["buy_pct_cash"]=alloc["buy_pct_cash"]
    diag["sell_pct_held"]=alloc["sell_pct_held"]
    return diag


def main():
    result=diagnose(now=dt.datetime.now(dt.timezone.utc))
    OUTPUT.parent.mkdir(parents=True,exist_ok=True)
    OUTPUT.write_text(json.dumps(result,indent=2,sort_keys=True)+"\n",encoding="utf-8")
    print(json.dumps(result,sort_keys=True))
    # A failure of ANY required source must remain obvious on CI.
    if result["cause"]!="NONE_INPUTS_VALID":
        raise SystemExit("Cycle market unavailable, see staged public source diagnostic")


if __name__=="__main__":
    main()
