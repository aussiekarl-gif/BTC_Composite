"""Research-only Coinbase BTC-USD completed UTC daily close comparator.

Never wired to trading, Streamlit, ntfy, Production or portfolio. Coinbase
Exchange candles use UTC day OPEN timestamps; the current day is incomplete.
"""
from __future__ import annotations

import math
import pandas as pd
import requests

URL="https://api.exchange.coinbase.com/products/BTC-USD/candles"
MAX_DIFF_PCT=1.0
MIN_OVERLAP=3
RECENT_DAYS=7


def _day(value):
    stamp=pd.Timestamp(value)
    return (stamp.tz_localize("UTC") if stamp.tzinfo is None
            else stamp.tz_convert("UTC")).normalize()


def parse_completed_coinbase_daily(payload, *, utc_today):
    """Coinbase arrays: [time, low, high, open, close, volume]."""
    if not isinstance(payload,list) or not payload:
        raise ValueError("Coinbase daily candle response missing")
    today=_day(utc_today)
    dates=[]
    closes=[]
    for row in payload:
        if not isinstance(row,(list,tuple)) or len(row)!=6:
            raise ValueError("Malformed Coinbase daily candle")
        try:
            timestamp=pd.to_datetime(float(row[0]),unit="s",utc=True)
            low,high,opening,closing,volume=map(float,row[1:])
        except (TypeError,ValueError,OverflowError) as exc:
            raise ValueError("Invalid Coinbase daily candle values") from exc
        if timestamp!=timestamp.normalize():
            raise ValueError("Coinbase candle timestamp not UTC midnight")
        if timestamp>=today:
            continue
        if (not all(math.isfinite(x) for x in (low,high,opening,closing,volume))
            or min(low,high,opening,closing)<=0 or volume<=0
            or low>high or not low<=opening<=high or not low<=closing<=high):
            raise ValueError("Invalid completed Coinbase OHLCV")
        dates.append(timestamp)
        closes.append(closing)
    if not dates:
        raise ValueError("No completed Coinbase daily candles")
    index=pd.DatetimeIndex(dates)
    if index.has_duplicates:
        raise ValueError("Duplicate Coinbase daily dates")
    result=pd.DataFrame({"btc_usd":closes},index=index).sort_index()
    return result


def fetch_completed_coinbase_daily(*,utc_today,timeout=20):
    """Public read-only endpoint, bounded response, no credentials."""
    today=_day(utc_today)
    # Coinbase Exchange supports at most 300 candles per request.
    # Fetch enough genuine completed daily closes to cover an older archive cutoff.
    start=today-pd.Timedelta(days=45)
    response=requests.get(
        URL,
        params={"granularity":86400,
                "start":start.isoformat().replace("+00:00","Z"),
                "end":today.isoformat().replace("+00:00","Z")},
        headers={"User-Agent":"BTC-Composite-research-only/1.0"},
        timeout=timeout)
    response.raise_for_status()
    return parse_completed_coinbase_daily(response.json(),utc_today=today)


def compare_coinbase_kraken(coinbase,kraken,*,utc_today):
    """Fail closed unless recent completed UTC dates agree, including yesterday."""
    today=_day(utc_today)
    yesterday=today-pd.Timedelta(days=1)
    for name,frame in (("Coinbase",coinbase),("Kraken",kraken)):
        if (not isinstance(frame,pd.DataFrame) or "btc_usd" not in frame
            or frame.empty or not isinstance(frame.index,pd.DatetimeIndex)
            or frame.index.tz is None or frame.index.has_duplicates):
            raise ValueError(f"Malformed {name} completed BTC/USD closes")
        if (frame.index>=today).any():
            raise ValueError(f"Unfinished {name} daily candle included")
        values=frame["btc_usd"].to_numpy(dtype=float)
        if not all(math.isfinite(x) and x>0 for x in values):
            raise ValueError(f"Invalid {name} price")
        if yesterday not in frame.index:
            raise ValueError(f"Missing yesterday completed {name} close")
    common=coinbase.index.intersection(kraken.index)
    common=common[(common>=today-pd.Timedelta(days=RECENT_DAYS))&(common<today)]
    if len(common)<MIN_OVERLAP:
        raise ValueError("Insufficient recent independent Coinbase/Kraken overlap")
    diff=(coinbase.loc[common,"btc_usd"]/
          kraken.loc[common,"btc_usd"]-1).abs()*100
    maximum=float(diff.max())
    if maximum>MAX_DIFF_PCT:
        raise ValueError("Coinbase/Kraken completed daily closes disagree >1%")
    return {"status":"RESEARCH_ONLY_VERIFIED",
            "asof_utc":str(today.date()),
            "completed_close_utc":str(yesterday.date()),
            "overlap_days":len(common),
            "maximum_difference_pct":round(maximum,4),
            "coinbase_close_usd":float(coinbase.loc[yesterday,"btc_usd"]),
            "kraken_close_usd":float(kraken.loc[yesterday,"btc_usd"]),
            "trading_enabled":False}
