"""One DAILY Cycle Trading ntfy message — informational and non-portfolio.

The runner controls once-per-Brisbane-day with a durable Git commit sent-date
marker. This script only constructs message content or POSTs on explicit send.
Never independently schedules or repeats; Production/Research labels are
read-only major-risk comparisons, not matched DCA percentages.
"""
from __future__ import annotations
import argparse
import datetime as dt
import os
import requests
import pandas as pd
from zoneinfo import ZoneInfo

from engines.research.ibit_quote import fetch_ibit_quote
from engines.research.cycle_halving_countdown import fetch_halving_countdown
from engines.research.top_signal_horse_race import read_exported_history
from engines.research.verified_recent_price_bridge import fetch_public_series
from engines.research.cycle_market_feed import merge_verified_cycle_prices
from engines.research.cycle_trading_dashboard_model import build_dashboard_market
from engines.research.shared_cycle_policy import cycle_exit_stage_status
from engines.research.cycle_model_redflags import (
    evaluate_major_red_flags,fetch_reference_model_risks,
    model_agreement_statuses,daily_reference_labels,MODELS,
)
from engines.research.cycle_trade_allocation import (
    calculate_allocation_signal,DEFAULT_BUY_STYLE,
)

BRISBANE=ZoneInfo("Australia/Brisbane")

def daily_message(*,now=None,quote=None,market=None,
                  reference_snapshot_fetcher=None):
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
            halving=fetch_halving_countdown(now=now)
            confirmed=(halving.get("last_halving_date") if halving.get("halving_date_verified") else None)
            if not confirmed or dt.date.fromisoformat(confirmed)>series.index[-1].date():
                raise ValueError("Halving epoch unverified or newer than last BTC close")
            market=build_dashboard_market(series,fx,asof=now.date().isoformat(),
                                          confirmed_halving_date=confirmed)
            age=(now.date()-pd.Timestamp(market["asof_date"]).date()).days
            if age<0 or age>3 or market["usd_aud_prior"] is None:
                market=None
        except Exception:market=None
    lines=[f"Cycle Trading daily | {today} Brisbane"]
    baselines={}
    allocation=None
    agreement={name:"no data" for name in MODELS}
    if quote:
        lines.append(f"ASX:IBIT A${quote['price_aud']:,.2f} (indicative, delayed)")
        lines.append(f"ETF quote dated {quote['timestamp_utc'][:10]} UTC")
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
            # No added notifications, ordinary disagreements or 'all clear'
            # text. Check V5.8.2 and V5.9 only for actionable market
            # percentages, and warn solely when extreme conflict is verified.
            if reference_snapshot_fetcher is not None:
                try:
                    baselines=reference_snapshot_fetcher()
                    agreement=daily_reference_labels(
                        buy_pct_cash=allocation["buy_pct_cash"],
                        sell_pct_held=allocation["sell_pct_held"],
                        snapshots=baselines,market_asof=market["asof_date"],
                        today=now.date(),
                        confirmed_halving_date=market["halving_date"],
                    )
                    crosscheck=evaluate_major_red_flags(
                        buy_pct_cash=allocation["buy_pct_cash"],
                        sell_pct_held=allocation["sell_pct_held"],
                        snapshots=baselines,market_asof=market["asof_date"],
                        today=now.date(),
                        confirmed_halving_date=market["halving_date"],
                    )
                    for warning in crosscheck["warnings"]:
                        lines.append("⚠ "+warning)
                except Exception:
                    # Unknown != passing comparison. The main Cycle
                    # notification still sends; no duplicate warning.
                    pass
        else:
            lines.append("Cycle signal: DATA UNAVAILABLE — no trade recommendation")
            lines.append("BUY allocation: unavailable | SELL allocation: unavailable")
        lines.append(f"Halving day: {market['halving_day']} (since {market['halving_date']})")
        full_status=cycle_exit_stage_status(
            market["halving_date"],market["asof_date"])
        if full_status["exit_window_expired"]:
            # Already enforced by the Cycle model; no repeated daily banner.
            pass
        elif full_status["next_exit_review_date"]:
            lines.append(
                f"Historical original-BTC EXIT research review: "
                f"{full_status['next_exit_review_date']} "
                "(not a confirmed portfolio sale)"
            )
    else:
        lines.append("Cycle signal: DATA UNAVAILABLE — no trade recommendation")
        lines.append("BUY allocation: unavailable | SELL allocation: unavailable")
    lines.append(f"Production: {agreement[MODELS[0]]}")
    lines.append(f"Research: {agreement[MODELS[1]]}")
    lines.append("Market-only % per eligible tranche; no Google Sheets/broker access; not a broker order.")
    lines.append("Research only: verify broker holdings, quote and SMSF tax before trading.")
    return today,"\n".join(lines)

def send_ntfy(body,*,topic):
    if not topic:raise ValueError("Missing NTFY_TOPIC")
    if topic.startswith(("https://","http://")):
        url=topic.rstrip("/")
    else:url="https://ntfy.sh/"+topic.strip("/")
    result=requests.post(url,data=body.encode("utf-8"),
        headers={"Title":"BTC Cycle Trading - Daily","Priority":"default",
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
        day,body=daily_message(reference_snapshot_fetcher=fetch_reference_model_risks)
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
