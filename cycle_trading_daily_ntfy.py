"""One DAILY Cycle Trading ntfy message — informational and non-portfolio.

The runner controls once-per-Brisbane-day with a durable Git commit sent-date
marker. This script only constructs message content or POSTs on explicit send.
Never independently schedules or repeats; no Production DCA comparison.
"""
from __future__ import annotations
import argparse
import datetime as dt
import os
import requests
import pandas as pd
from zoneinfo import ZoneInfo

from engines.research.ibit_quote import fetch_ibit_quote
from engines.research.top_signal_horse_race import read_exported_history
from engines.research.verified_recent_price_bridge import fetch_public_series
from engines.research.cycle_market_feed import merge_verified_cycle_prices
from engines.research.cycle_trading_dashboard_model import build_dashboard_market
from engines.research.cycle_trade_allocation import (
    calculate_allocation_signal,DEFAULT_BUY_STYLE,
)

BRISBANE=ZoneInfo("Australia/Brisbane")

def daily_message(*,now=None,quote=None,market=None):
    now=now or dt.datetime.now(dt.timezone.utc)
    local=now.astimezone(BRISBANE)
    today=local.date().isoformat()
    if quote is None:
        try:quote=fetch_ibit_quote(now=now)
        except Exception:quote=None
    if market is None:
        try:
            history=read_exported_history()["price_usd"]
            remote,fx=fetch_public_series(asof=now.date().isoformat())
            series,verified=merge_verified_cycle_prices(
                pd.DataFrame({"price_usd":history}),remote,
                utc_today=now.date())
            market=build_dashboard_market(series,fx,asof=now.date().isoformat())
            age=(now.date()-pd.Timestamp(market["asof_date"]).date()).days
            if age<0 or age>3 or market["usd_aud_prior"] is None:
                market=None
        except Exception:market=None
    lines=[f"Cycle Trading daily | {today} Brisbane"]
    if quote:
        lines.append(f"ASX:IBIT A${quote['price_aud']:,.2f} (indicative, delayed)")
        lines.append(f"ETF quote {quote['timestamp_utc']} UTC")
    else:
        lines.append("ASX:IBIT quote: unavailable/stale — check broker")
    if market:
        lines.append(f"BTC close US${market['btc_price_usd']:,.0f} ({market['asof_date']})")
        lines.append(f"Prior 200WMA US${market['prior_200wma_usd']:,.0f}")
        try:
            allocation=calculate_allocation_signal(
                market,buy_style=DEFAULT_BUY_STYLE)
        except (TypeError,ValueError,KeyError):
            allocation=None
        if allocation is not None:
            lines.append(f"Cycle signal: {allocation['signal']}")
            lines.append(f"BUY allocation: {allocation['buy_pct_cash']:.2f}% of available AUD cash")
            lines.append(f"SELL allocation: {allocation['sell_pct_held']:.2f}% of current BTC/IBIT holdings")
            lines.append(f"Reason: {allocation['reason']}")
            lines.append("Rule: recovery-confirmation dynamic DCA-in; research-only DCA-out")
        else:
            lines.append("Cycle signal: DATA UNAVAILABLE — no trade recommendation")
            lines.append("BUY allocation: unavailable | SELL allocation: unavailable")
        lines.append(f"Halving day: {market['halving_day']} (2024 day500 passed)")
    else:
        lines.append("Cycle signal: DATA UNAVAILABLE — no trade recommendation")
        lines.append("BUY allocation: unavailable | SELL allocation: unavailable")
    lines.append(
        "Allocation is market-only: no Google Sheets/broker access in ntfy job. "
        "Streamlit shows actual AUD / ETF units after holdings confirmation."
    )
    lines.append("DCA % is per eligible research tranche, NOT a new daily order. Check executed trades.")
    lines.append("Research only; not a broker order. Review SMSF CGT before selling.")
    return today,"\n".join(lines)

def send_ntfy(body,*,topic):
    if not topic:raise ValueError("Missing NTFY_TOPIC")
    if topic.startswith(("https://","http://")):
        url=topic.rstrip("/")
    else:url="https://ntfy.sh/"+topic.strip("/")
    result=requests.post(url,data=body.encode("utf-8"),
        headers={"Title":"BTC Cycle Trading — Daily","Priority":"default",
                 "Tags":"chart_with_upwards_trend","Cache":"no"},
        timeout=20)
    result.raise_for_status()

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--prepare",action="store_true")
    ap.add_argument("--send",action="store_true")
    ap.add_argument("--date-file",default="/tmp/btc_cycle_ntfy_date.txt")
    ap.add_argument("--body-file",default="/tmp/btc_cycle_ntfy_body.txt")
    args=ap.parse_args()
    if args.prepare:
        day,body=daily_message()
        from pathlib import Path
        Path(args.date_file).write_text(day+"\n")
        Path(args.body_file).write_text(body+"\n")
        print(body)
    elif args.send:
        from pathlib import Path
        send_ntfy(Path(args.body_file).read_text(),
                  topic=os.environ.get("NTFY_TOPIC",""))
    else:ap.error("specify --prepare or --send")

if __name__=="__main__":
    main()
