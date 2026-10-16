"""Read-only ASX:IBIT delayed quote from Yahoo Finance public chart endpoint.

Not guaranteed executable. Never silently substitute US-listed NASDAQ IBIT.
Returns None when currency, market identifier or quote timestamp invalid.
"""
from __future__ import annotations
import datetime as dt
import math
import requests

URL="https://query1.finance.yahoo.com/v8/finance/chart/IBIT.AX"
FALLBACK_URL="https://query2.finance.yahoo.com/v8/finance/chart/IBIT.AX"
MAX_QUOTE_AGE_DAYS=5

def parse_ibit_quote(payload,*,now=None):
    now=now or dt.datetime.now(dt.timezone.utc)
    if now.tzinfo is None: now=now.replace(tzinfo=dt.timezone.utc)
    try:
        item=payload["chart"]["result"][0]
        meta=item["meta"]
        symbol=meta.get("symbol","").upper()
        currency=meta.get("currency","").upper()
    except (ValueError,TypeError,KeyError,IndexError,OverflowError,AttributeError):
        return None
    # Never confuse the AUD ASX ETF with USD NASDAQ:IBIT.
    if symbol not in ("IBIT.AX","IBIT.AU") or currency!="AUD":
        return None
    # Some Yahoo chart responses omit regularMarketPrice/Time but still
    # contain dated daily closes. Accept the most recent valid close as a
    # delayed indicative quote, never as a live executable broker price.
    candidates=[]
    try:
        candidates.append((int(meta["regularMarketTime"]),
                           float(meta["regularMarketPrice"])))
    except (ValueError,TypeError,KeyError,OverflowError):
        pass
    try:
        timestamps=item.get("timestamp") or []
        closes=item["indicators"]["quote"][0]["close"]
        for epoch_raw,close_raw in zip(timestamps,closes):
            if epoch_raw is not None and close_raw is not None:
                candidates.append((int(epoch_raw),float(close_raw)))
    except (ValueError,TypeError,KeyError,IndexError,OverflowError,AttributeError):
        pass
    valid=[]
    for epoch,price in candidates:
        try:
            stamp=dt.datetime.fromtimestamp(epoch,dt.timezone.utc)
        except (ValueError,OverflowError,OSError):
            continue
        days=(now-stamp).total_seconds()/86400
        if math.isfinite(price) and price>0 and -.01<=days<=MAX_QUOTE_AGE_DAYS:
            valid.append((epoch,price,stamp,days))
    if not valid:
        return None
    epoch,price,stamp,days=max(valid,key=lambda row:row[0])
    return {"price_aud":price,"symbol":"ASX:IBIT","provider":"Yahoo Finance delayed quote",
            "timestamp_utc":stamp.isoformat(),"age_hours":round(days*24,1),
            "indicative_only":True}


def format_ibit_units_for_display(decision, *, quote_available):
    """Never label a routine HOLD as missing an ETF quote."""
    units=decision.get("estimated_ibit_units")
    if units is not None:
        return f"{int(units):,}"
    if (not quote_available and
            decision.get("market_signal") in ("BUY WATCH","SELL WATCH")):
        return "Quote unavailable"
    return "No trade"

def fetch_ibit_quote(*,timeout=12,now=None):
    """Try two Yahoo chart hosts; neither claims to be a live broker quote.

    Do not mix up ASX IBIT.AX with US IBIT, or silently use an old quote.
    Both endpoints share one underlying provider, not independent prices.
    """
    errors=[]
    for endpoint in (URL,FALLBACK_URL):
        try:
            response=requests.get(
                endpoint,params={"interval":"1d","range":"5d"},
                headers={"User-Agent":"Mozilla/5.0 (read-only IBIT.AX AUD quote)"},
                timeout=timeout,
            )
            response.raise_for_status()
            quote=parse_ibit_quote(response.json(),now=now)
            if quote is not None:
                return quote
            errors.append("Rejected unavailable/wrong symbol or stale AUD quote")
        except requests.RequestException as exc:
            errors.append(type(exc).__name__)
        except ValueError:
            errors.append("Invalid quote response")
    raise ValueError(
        "ASX:IBIT automatic quote unavailable (two provider endpoints checked). "
        "Use broker price override. Reasons: "+"; ".join(errors)
    )
