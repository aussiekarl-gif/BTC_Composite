"""Daily first-captured realized-price reference from Explore21/BGeometrics.

Explore21's realized price and BTC close are captured from the same dated CSV
row. BGeometrics remains a provenance fallback, but without its own matched
BTC close it cannot produce a forward-eligible spot/realized ratio. No trades.
"""
from __future__ import annotations

from datetime import date,datetime,timezone
import hashlib
import json
import math
import csv
import io

import requests

SOURCE="BGeometrics Bitcoin Data API, realized-price"
SOURCE_URL="https://bitcoin-data.com/v1/realized-price/last"
EXPLORE21_SOURCE="Explore21 Bitcoin Core on-chain realized price CSV (CC BY 4.0)"
EXPLORE21_URL="https://charts.explore21.com/data/bitcoin-realized-price.csv"
EXPLORE21_CHART="https://charts.explore21.com/bitcoin-realized-price"
MAX_PROVIDER_AGE_DAYS=3
FIELDS=("realizedPrice","realized_price","realized-price","realizedPriceUsd",
        "realized_price_usd","realizedprice","realized_price_btc","value")
DATE_FIELDS=("d","date","day","timestamp_date")
UTC_FIELDS=("unixTs","timestamp","unix_ts")
USER_AGENT="BTC-Composite-v59-realized-research/1.0"


def normalized_reference(raw, *, captured_at_utc:datetime,
                         closed_signal_date:date) -> dict:
    """Preserve provider observation date AND first-local-fetch timestamp."""
    if captured_at_utc.tzinfo is None:
        raise ValueError("Timezone-aware capture required")
    if not isinstance(closed_signal_date,date):
        raise ValueError("Closed signal date required")
    ts=captured_at_utc.astimezone(timezone.utc)
    response_hash=hashlib.sha256(json.dumps(raw,sort_keys=True,default=str).encode()).hexdigest()
    base={
        "status":"UNAVAILABLE","provider":SOURCE,"url":SOURCE_URL,
        "captured_at_utc":ts.isoformat(),"provider_observation_date":None,
        "realized_price_usd":None,"price_to_realized_ratio":None,
        "usable_for_forward":False,"provider_delayed":None,
        "raw_response_sha256":response_hash,
        "not_asx_ibit_or_cowen_prediction":True,
    }
    if isinstance(raw,list):
        if len(raw)!=1: return {**base,"failure":"AMBIGUOUS_API_LIST"}
        raw=raw[0]
    if not isinstance(raw,dict):
        return {**base,"failure":"UNRECOGNIZED_API_RESPONSE"}
    payload=raw.get("data",raw)
    if isinstance(payload,list):
        if len(payload)!=1:return {**base,"failure":"AMBIGUOUS_API_PAYLOAD"}
        payload=payload[0]
    if not isinstance(payload,dict):
        return {**base,"failure":"UNRECOGNIZED_API_PAYLOAD"}
    value=next((payload[k] for k in FIELDS if k in payload),None)
    day=next((payload[k] for k in DATE_FIELDS if k in payload),None)
    if day is None:
        stamp=next((payload[k] for k in UTC_FIELDS if k in payload),None)
        if stamp is not None:
            try:
                seconds=float(stamp)
                if seconds>1e12:seconds/=1000
                day=datetime.fromtimestamp(seconds,tz=timezone.utc).date()
            except (TypeError,ValueError,OverflowError):
                pass
    try:
        provider_date=day if isinstance(day,date) else date.fromisoformat(str(day)[:10])
        price=float(value)
    except (TypeError,ValueError,OverflowError):
        return {**base,"failure":"MISSING_REALIZED_DATE_OR_VALUE"}
    delayed=bool(raw.get("delayed",False) or payload.get("delayed",False))
    age=(closed_signal_date-provider_date).days
    result={**base,"provider_observation_date":provider_date.isoformat(),
            "provider_delayed":delayed,"provider_age_days_at_signal":age,
            "realized_price_usd":price if math.isfinite(price) and price>0 else None}
    if not (math.isfinite(price) and 1<price<1_000_000):
        return {**result,"failure":"INVALID_VALUE"}
    if not 0<=age<=MAX_PROVIDER_AGE_DAYS or delayed:
        return {**result,"status":"STALE_OR_DELAYED","failure":"NOT_CURRENT_FOR_SIGNAL"}
    return {**result,"status":"VALID_DATED_RESEARCH_REFERENCE",
            "usable_for_forward":True}


def _public_explore21(*,closed_signal_date:date,now:datetime) -> dict:
    """Only daily data that the independent provider has published when fetched."""
    response=requests.get(EXPLORE21_URL,timeout=12,
                          headers={"User-Agent":USER_AGENT,"Accept":"text/csv"})
    response.raise_for_status()
    if len(response.content)>5_000_000:
        raise ValueError("Unexpectedly large realized CSV")
    reader=csv.DictReader(io.StringIO(response.text))
    required=("date","realized_price_usd","btc_close_usd")
    if reader.fieldnames is None or any(k not in reader.fieldnames for k in required):
        raise ValueError("Explore21 CSV missing explicit realized USD/date fields")
    last=None
    prev=None
    count=0
    for row in reader:
        current=date.fromisoformat(row["date"].strip())
        if prev is not None and current<=prev:
            raise ValueError("Explore21 CSV non-monotonic or duplicate dates")
        prev=current
        last=row
        count+=1
    if last is None or count<365:
        raise ValueError("Explore21 returned empty/short market history")
    rp=float(last["realized_price_usd"])
    price=float(last["btc_close_usd"])
    if not (math.isfinite(rp) and math.isfinite(price) and
            1<rp<1_000_000 and price>0):
        raise ValueError("Explore21 latest values are nonfinite or invalid")
    reading=normalized_reference(
        {"d":last["date"],"realizedPrice":rp},
        captured_at_utc=now,closed_signal_date=closed_signal_date)
    reading.update({
        "provider":EXPLORE21_SOURCE,"url":EXPLORE21_URL,
        "source_chart":EXPLORE21_CHART,
        "provider_csv_rows":count,
        "raw_response_sha256":hashlib.sha256(response.content).hexdigest(),
        "provider_btc_close_usd":price,
    })
    return reading


def _delayed_bgeometrics(*,closed_signal_date:date,now:datetime) -> dict:
    """Fallback retained for provenance; recent days may be subscriber-delayed."""
    import os
    headers={"User-Agent":USER_AGENT,"Accept":"application/json"}
    token=os.environ.get("BGEOMETRICS_API_TOKEN","").strip()
    if token:
        headers["Authorization"]="Bearer "+token
    response=requests.get(SOURCE_URL,timeout=10,headers=headers)
    response.raise_for_status()
    return normalized_reference(response.json(),captured_at_utc=now,
                                closed_signal_date=closed_signal_date)


def capture_reference(*, closed_signal_date:date,
                      captured_at_utc:datetime|None=None) -> dict:
    """Try fresh independent node CSV, then optional API; never assume freshness."""
    now=captured_at_utc or datetime.now(timezone.utc)
    primary=None
    try:
        primary=_public_explore21(closed_signal_date=closed_signal_date,now=now)
        if primary.get("usable_for_forward"):
            return primary
    except Exception as e:
        primary={"status":"UNAVAILABLE","provider":EXPLORE21_SOURCE,
                 "url":EXPLORE21_URL,"failure":"SOURCE_OR_SCHEMA_FETCH_FAILED",
                 "error_type":type(e).__name__,
                 "usable_for_forward":False}
    try:
        secondary=_delayed_bgeometrics(closed_signal_date=closed_signal_date,now=now)
        if secondary.get("usable_for_forward"):
            secondary["primary_provider_status"]=primary.get("status")
            return secondary
        secondary["primary_provider_status"]=primary.get("status")
        secondary["primary_provider_failure"]=primary.get("failure")
        return secondary
    except Exception as e:
        return {
            "status":"UNAVAILABLE","provider":EXPLORE21_SOURCE,
            "url":EXPLORE21_URL,
            "captured_at_utc":now.astimezone(timezone.utc).isoformat(),
            "provider_observation_date":None,"realized_price_usd":None,
            "usable_for_forward":False,"price_to_realized_ratio":None,
            "failure":"BOTH_PROVIDERS_UNAVAILABLE",
            "primary_provider_status":primary.get("status"),
            "primary_provider_failure":primary.get("failure"),
            "secondary_error_type":type(e).__name__,
            "not_asx_ibit_or_cowen_prediction":True,
        }


def paired_to_spot(reference:dict|None,spot_usd:float,signal_date:date) -> dict:
    """Use the provider's own same-day BTC close for a realized-price ratio.

    spot_usd is the separate Blockchain.com daily-average market-price proxy
    used by the V5.9 tape. It is retained as a diagnostic, never silently
    mixed with Explore21's daily-close realized-price observation.
    """
    if not reference:
        return {"status":"UNAVAILABLE","usable_for_forward":False,
                "price_to_realized_ratio":None,"realized_price_usd":None,
                "ratio_method_version":None}
    result=dict(reference)
    result.update({
        "price_to_realized_ratio":None,
        "ratio_method_version":None,
        "ratio_spot_price_source":None,
        "ratio_spot_price_basis":None,
        "blockchain_market_price_usd":None,
        "blockchain_market_price_basis":(
            "Blockchain.com market-price chart daily average across major exchanges; not OHLC close"),
        "blockchain_market_price_to_realized_ratio":None,
        "blockchain_vs_provider_close_gap_pct":None,
    })
    if not result.get("usable_for_forward"):
        return result
    try:
        date_obs=date.fromisoformat(result["provider_observation_date"])
        val=float(result["realized_price_usd"])
        provider_close=float(result["provider_btc_close_usd"])
        age=(signal_date-date_obs).days
        if age!=0:
            result.update(status="STALE_DATE_MISMATCH",usable_for_forward=False,
                          failure="PROVIDER_DATE_MUST_MATCH_SIGNAL_DATE")
            return result
        if not (math.isfinite(val) and math.isfinite(provider_close)
                and val>0 and provider_close>0):
            raise ValueError("Invalid provider close or realized price")
        try:
            market_average=float(spot_usd)
            if math.isfinite(market_average) and market_average>0:
                result["blockchain_market_price_usd"]=market_average
                result["blockchain_market_price_to_realized_ratio"]=market_average/val
                result["blockchain_vs_provider_close_gap_pct"]=(
                    100*(market_average/provider_close-1))
        except (TypeError,ValueError,OverflowError):
            market_average=None
        result.update({
            "price_to_realized_ratio":provider_close/val,
            "ratio_method_version":"explore21_same_day_close_v2",
            "ratio_spot_price_source":result.get("provider"),
            "ratio_spot_price_basis":"Provider BTC daily UTC close from the same CSV row/date as realized price",
            "usable_for_forward":True,
            "status":"VALID_DATED_RESEARCH_REFERENCE",
        })
    except KeyError:
        result.update(status="UNMATCHED_PRICE_BASIS",usable_for_forward=False,
                      failure="PROVIDER_BTC_CLOSE_REQUIRED_FOR_RATIO")
    except (TypeError,ValueError,OverflowError):
        result.update(status="INVALID_DATED_PAIR",usable_for_forward=False,
                      price_to_realized_ratio=None)
    return result
