"""Read-only ASX:IBIT delayed quote from Yahoo Finance public chart endpoint.

Not guaranteed executable. Never silently substitute US-listed NASDAQ IBIT.
Returns None when currency, market identifier or quote timestamp invalid.
"""
from __future__ import annotations
import datetime as dt
import math
import requests

URL="https://query1.finance.yahoo.com/v8/finance/chart/IBIT.AX"
MAX_QUOTE_AGE_DAYS=5

def parse_ibit_quote(payload,*,now=None):
    now=now or dt.datetime.now(dt.timezone.utc)
    if now.tzinfo is None: now=now.replace(tzinfo=dt.timezone.utc)
    try:
        item=payload["chart"]["result"][0]
        meta=item["meta"]
        symbol=meta.get("symbol","").upper()
        currency=meta.get("currency","").upper()
        price=float(meta.get("regularMarketPrice"))
        epoch=int(meta.get("regularMarketTime"))
        stamp=dt.datetime.fromtimestamp(epoch,dt.timezone.utc)
    except (ValueError,TypeError,KeyError,IndexError,OverflowError):
        return None
    if symbol not in ("IBIT.AX","IBIT.AU") or currency!="AUD":
        return None
    if not math.isfinite(price) or price<=0: return None
    days=(now-stamp).total_seconds()/86400
    if days<-.01 or days>MAX_QUOTE_AGE_DAYS:
        return None
    return {"price_aud":price,"symbol":"ASX:IBIT","provider":"Yahoo Finance delayed quote",
            "timestamp_utc":stamp.isoformat(),"age_hours":round(days*24,1),
            "indicative_only":True}

def fetch_ibit_quote(*,timeout=12,now=None):
    response=requests.get(URL,params={"interval":"1d","range":"5d"},
        headers={"User-Agent":"Mozilla/5.0 (BTC-Composite read-only Research)"},
        timeout=timeout)
    response.raise_for_status()
    quote=parse_ibit_quote(response.json(),now=now)
    if quote is None:
        raise ValueError("No valid recent AUD quote for ASX:IBIT; broker entry required")
    return quote
