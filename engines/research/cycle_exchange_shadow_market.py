"""Research-only shadow Cycle market built from independently checked exchange closes.

Never replaces the Streamlit/ntfy feed, never trades, never alters archive.
"""
from __future__ import annotations
import datetime as dt
import json
import sys
import pandas as pd
from engines.research.top_signal_horse_race import read_exported_history
from engines.research.cycle_coinbase_daily_reference import fetch_completed_coinbase_daily, compare_coinbase_kraken
from engines.research.cycle_forward_kraken_bridge import fetch_completed_kraken_daily
from engines.research.cycle_trading_dashboard_model import build_dashboard_market
from engines.research.cycle_trade_allocation import calculate_allocation_signal, DEFAULT_BUY_STYLE


def shadow_market(archive, coinbase, kraken, *, utc_today):
    verification=compare_coinbase_kraken(coinbase,kraken,utc_today=utc_today)
    if archive.empty or "price_usd" not in archive:
        raise ValueError("Missing archived BTC/USD prices")
    last=archive.index.max()
    if last.tzinfo is None:
        last=last.tz_localize("UTC")
    else:
        last=last.tz_convert("UTC")
    last=last.normalize()
    common=archive.index.intersection(coinbase.index).intersection(kraken.index)
    if len(common)<3:
        raise ValueError("Insufficient independent archive/exchange overlap")
    # Archive may use a different daily reference convention; fail rather
    # than silently redate or overwrite any original observations.
    archive_px=archive.loc[common,"price_usd"].astype(float)
    for name,frame in (("Coinbase",coinbase),("Kraken",kraken)):
        diff=(frame.loc[common,"btc_usd"]/archive_px-1).abs()
        if diff.max()>0.01:
            raise ValueError(f"Archive and {name} completed closes disagree >1%")
    yesterday=pd.Timestamp(utc_today).tz_localize("UTC")-pd.Timedelta(days=1)
    required=pd.date_range(last+pd.Timedelta(days=1),yesterday,freq="D",tz="UTC")
    if len(required)==0 or not required.isin(coinbase.index).all() or not required.isin(kraken.index).all():
        raise ValueError("Missing consecutive independently verified exchange closes")
    # Verify every appended day, not just recent seven-day acceptance.
    difference=(coinbase.loc[required,"btc_usd"]/kraken.loc[required,"btc_usd"]-1).abs()
    if difference.max()>0.01:
        raise ValueError("Exchange disagreement on historical bridge >1%")
    merged=pd.concat([archive["price_usd"],kraken.loc[required,"btc_usd"].rename("price_usd")])
    if merged.index.has_duplicates:
        raise ValueError("Duplicate BTC dates")
    market=build_dashboard_market(merged,None,asof=utc_today,confirmed_halving_date="2024-04-20")
    signal=calculate_allocation_signal(market,buy_style=DEFAULT_BUY_STYLE)
    return {"research_only":True,"trading_enabled":False,
            "archive_last_utc":str(last.date()),"completed_close_utc":verification["completed_close_utc"],
            "appended_days":len(required),"max_bridge_exchange_difference_pct":round(float(difference.max())*100,4),
            "btc_close_usd":market["btc_price_usd"],"prior_200wma_usd":market["prior_200wma_usd"],
            "signal":signal["signal"],"buy_pct_cash":signal["buy_pct_cash"],
            "sell_pct_held":signal["sell_pct_held"]}


def main():
    today=dt.datetime.now(dt.timezone.utc).date().isoformat()
    try:
        result=shadow_market(read_exported_history(),
                             fetch_completed_coinbase_daily(utc_today=today),
                             fetch_completed_kraken_daily(utc_today=today),utc_today=today)
    except Exception as exc:
        print(json.dumps({"research_only":True,"trading_enabled":False,"status":"UNVERIFIED",
                          "error_type":type(exc).__name__,"error":str(exc)[:300]},sort_keys=True))
        return 1
    print(json.dumps(result,sort_keys=True))
    return 0


if __name__=="__main__":
    sys.exit(main())
