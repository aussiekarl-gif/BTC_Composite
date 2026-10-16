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
