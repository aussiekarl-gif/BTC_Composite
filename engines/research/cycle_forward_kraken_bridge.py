"""Research-only fresh BTC/USD close bridge for the prospective signal tape.

Kraken public spot XBTUSD candles serve ONLY when Blockchain.com's dated
market-price observations do not include yesterday. Every Kraken candle
has a UTC-midnight opening timestamp; a candle dated *today* is still
running, even if the API includes it, and is NEVER used.

Before stitching, compare >=3 recent already-published dates against
Blockchain.com. Append Kraken closes only to the end and only for a
CONTIGUOUS short gap (<=3 days) through yesterday; never overwrite an
existing archived/provider close. Do not wire this into Streamlit, ntfy,
Production, V5.9, cash allocations, user holdings or broker orders.
"""
from __future__ import annotations

import math

import pandas as pd
import requests

KRAKEN_URL="https://api.kraken.com/0/public/OHLC"
PAIR="XBTUSD"
DAILY_MINUTES=1440
MIN_OVERLAP=3
RECENT_OVERLAP_DAYS=7
MAX_SINGLE_PRICE_DEVIATION=.08
MAX_MEDIAN_PRICE_DEVIATION=.05
MAX_PUBLICATION_GAP_DAYS=3


def _utc_day(value):
    p=pd.Timestamp(value)
    return (p.tz_localize("UTC") if p.tzinfo is None
            else p.tz_convert("UTC")).normalize()


def parse_kraken_completed_daily(payload, *, utc_today):
    """Parse Kraken OHLC and EXCLUDE the uncommitted current-day candle."""
    if not isinstance(payload,dict):
        raise ValueError("Kraken OHLC is not a JSON object")
    errors=payload.get("error")
    results=payload.get("result")
    if errors or not isinstance(errors,list) or not isinstance(results,dict):
        raise ValueError("Kraken returned an API error or missing result")
    products=[v for k,v in results.items() if k!="last"]
    if len(products)!=1 or not isinstance(products[0],list):
        raise ValueError("Kraken response must contain one spot USD market")
    today=_utc_day(utc_today)
    dates=[]
    prices=[]
    for candle in products[0]:
        if not isinstance(candle,list) or len(candle)<8:
            raise ValueError("Malformed Kraken daily OHLC candle")
        raw=float(candle[0])
        timestamp=pd.to_datetime(raw,unit="s",utc=True)
        if timestamp!=timestamp.normalize():
            raise ValueError("Unexpected non-UTC-midnight OHLC candle")
        if timestamp>=today:
            continue
        close=float(candle[4])
        trades=float(candle[7])
        if (not math.isfinite(close) or close<=0
                or not math.isfinite(trades) or trades<=0):
            raise ValueError("Kraken historical price/trades invalid")
        dates.append(timestamp)
        prices.append(close)
    if not dates:
        raise ValueError("No completed Kraken spot daily candles")
    index=pd.DatetimeIndex(dates)
    if index.has_duplicates or not index.is_monotonic_increasing:
        raise ValueError("Duplicate or out-of-order Kraken daily candles")
    return pd.DataFrame({"btc_usd":prices},index=index)


def fetch_completed_kraken_daily(*,utc_today,timeout=20):
    """Kraken public REST, no authentication or user portfolio inputs."""
    response=requests.get(
        KRAKEN_URL,params={"pair":PAIR,"interval":DAILY_MINUTES},
        headers={"User-Agent":"BTC-Composite-forward-audit/1.0"},timeout=timeout)
    response.raise_for_status()
    return parse_kraken_completed_daily(
        response.json(),utc_today=utc_today)


def append_verified_kraken_after_blockchain(blockchain,kraken,*,utc_today):
    """Date-exact short bridge only, recent public-source overlap required.

    Old blockchain prices remain unchanged even when Kraken close differs.
    A large difference is an error, not an opportunity to reprice old bars.
    """
    today=_utc_day(utc_today)
    yesterday=today-pd.Timedelta(days=1)
    if (not isinstance(blockchain,pd.DataFrame)
            or not isinstance(kraken,pd.DataFrame)
            or "btc_usd" not in blockchain or "btc_usd" not in kraken):
        raise ValueError("Two independently dated BTC/USD dataframes required")
    for name,frame in (("Blockchain",blockchain),("Kraken",kraken)):
        if (not isinstance(frame.index,pd.DatetimeIndex)
                or frame.index.tz is None
                or frame.index.has_duplicates
                or not frame.index.is_monotonic_increasing
                or frame.empty):
            raise ValueError(f"{name} price dates missing, unordered or duplicated")
        values=frame["btc_usd"].to_numpy(dtype=float)
        if not pd.Series(values).map(math.isfinite).all() or (values<=0).any():
            raise ValueError(f"{name} invalid BTC/USD prices")
    known=blockchain.loc[blockchain.index<today,["btc_usd"]]
    candles=kraken.loc[kraken.index<today,["btc_usd"]]
    if known.empty or candles.empty:
        raise ValueError("No independently observed BTC sources")
    if known.index[-1]>=yesterday:
        raise ValueError("No delayed Blockchain.com gap to bridge")
    lag=(yesterday-known.index[-1]).days
    if not 1<=lag<=MAX_PUBLICATION_GAP_DAYS:
        raise ValueError("Delayed public reference exceeds short safe Kraken bridge")
    common=known.index.intersection(candles.index)
    common=common[common>=known.index[-1]-pd.Timedelta(days=RECENT_OVERLAP_DAYS-1)]
    if len(common)<MIN_OVERLAP:
        raise ValueError("Too few recent Kraken/Blockchain BTC overlap days")
    difference=(candles.loc[common,"btc_usd"]/
                known.loc[common,"btc_usd"]-1).abs()
    if (float(difference.median())>MAX_MEDIAN_PRICE_DEVIATION
            or float(difference.max())>MAX_SINGLE_PRICE_DEVIATION):
        raise ValueError("Kraken daily close conflicts with Blockchain.com market price")
    additions=candles.loc[candles.index>known.index[-1]]
    expected=pd.date_range(
        known.index[-1]+pd.Timedelta(days=1),yesterday,
        freq="D",tz="UTC")
    if not additions.index.equals(expected):
        raise ValueError("Kraken does not have each consecutive newly completed close")
    combined=pd.concat([known,additions])
    if combined.index.has_duplicates:
        raise ValueError("Provider bridge duplicated BTC reference dates")
    if not combined.loc[known.index,"btc_usd"].equals(known["btc_usd"]):
        raise AssertionError("Research feed attempted to overwrite Blockchain history")
    return combined,{
        "provider":"Kraken XBTUSD completed UTC daily candle after Blockchain.com",
        "appended_dates":[str(x.date()) for x in additions.index],
        "existing_market_closes_preserved":True,
        "kraken_blockchain_overlap_days":len(common),
        "kraken_blockchain_max_diff_pct":round(float(difference.max())*100,4),
        "kraken_blockchain_median_diff_pct":round(float(difference.median())*100,4),
        "only_prior_completed_utc_candles":True,
        "reference_was_lagged_days":lag,
    }
