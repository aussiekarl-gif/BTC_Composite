"""One source-validation policy for Streamlit and daily Cycle Trading ntfy.

A public Blockchain.com daily BTC/USD series is appended ONLY to
October-2026 archived provider prices when at least 3 existing dates
overlap and crosscheck. Never use an uncompleted UTC day, overwrite
older provider exports, invent historical data or silently change
price provenance. All prices are observational rather than exchange
bid/ask fills.
"""
from __future__ import annotations

import pandas as pd

MIN_RECENT_OVERLAP=3
MAX_MEDIAN_PRICE_DIFF=.06
MAX_SINGLE_PRICE_DIFF=.15


def merge_verified_cycle_prices(archive,public,*,utc_today):
    if not isinstance(archive,pd.DataFrame) or "price_usd" not in archive:
        raise ValueError("Archive BTC/USD prices missing")
    if not isinstance(public,pd.DataFrame) or "btc_usd" not in public:
        raise ValueError("Public BTC/USD prices missing")
    local=archive["price_usd"].copy().sort_index()
    fresh=public["btc_usd"].copy().sort_index()
    if (not isinstance(local.index,pd.DatetimeIndex) or
            not isinstance(fresh.index,pd.DatetimeIndex) or
            local.empty or fresh.empty or
            local.index.has_duplicates or fresh.index.has_duplicates):
        raise ValueError("Duplicate/missing historical price dates")
    when=pd.Timestamp(utc_today)
    when=when.tz_localize("UTC") if when.tzinfo is None else when.tz_convert("UTC")
    when=when.normalize()
    # Never expose the as-yet unfinished UTC date's daily price.
    fresh=fresh.loc[fresh.index<when]
    if fresh.empty:
        raise ValueError("No completed public BTC/USD closes")
    common=local.index.intersection(fresh.index)
    tail=common[common>=local.index[-1]-pd.Timedelta(days=30)]
    if len(tail)<MIN_RECENT_OVERLAP:
        raise ValueError("Too few recent BTC/USD cross-provider overlap dates")
    deviation=(fresh.loc[tail]/local.loc[tail]-1.).abs()
    if (not deviation.notna().all() or
            float(deviation.median())>MAX_MEDIAN_PRICE_DIFF or
            float(deviation.max())>MAX_SINGLE_PRICE_DIFF):
        raise ValueError("Public BTC/USD conflicts with archived source")
    append=fresh.loc[fresh.index>local.index[-1]]
    merged=pd.concat([local,append]).sort_index()
    if merged.index.has_duplicates or merged.le(0).any() or merged.isna().any():
        raise ValueError("Invalid merged daily BTC/USD prices")
    return merged,{
        "archive_cutoff":str(local.index[-1].date()),
        "overlap_days":len(tail),
        "max_overlap_difference_pct":round(100*float(deviation.max()),2),
        "added_dates":len(append),
        "last_price_date":str(merged.index[-1].date()),
        "price_staleness_days":(when-merged.index[-1]).days,
        "provider_verified":True,
    }
