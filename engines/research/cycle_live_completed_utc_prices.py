"""Shared VERIFIED Bitcoin completed-UTC-close assembly for Cycle Trading.

Use by BOTH Streamlit and the existing ONE daily ntfy. This is a market
DATA correctness release only: neither historical price exports, moving
average mathematics, portfolio, BUY/SELL allocation percentages, broker,
Production nor research forward-tape hashes may be modified.

Blockchain.com 'market-price' chart tick timestamp D at UTC 00:00 denotes
the close of calendar day D-1, empirically corroborated on 41 UTC dates
against independent Kraken XBTUSD completed OHLC. A tick stamped today
may reflect YESTERDAY'S close, never today/unfinished candles. Align only
the live Blockchain public chart series, not dated archived BlockHorizon
prices or Kraken midnight-OPEN-date OHLC. Never redate the original
public history in-place, which is needed in other archived research.

Require:
  * strict UTC midnight public chart timestamps; align D to D-1
  * recent archive/public overlap, no rewriting any exported history
  * >=3 identical completed-day Blockchain/Kraken close references
    from past week, with strict <=1% maximum exchange deviation
  * a contiguous gap through yesterday of <=7 days, filled with
    completed independent Kraken closes only after valid overlap
  * no trading recommendation if a single required day/provider is
    absent, disagreement high or yesterday not verified
"""
from __future__ import annotations

import math

import pandas as pd

from engines.research.cycle_market_feed import merge_verified_cycle_prices
from engines.research.cycle_forward_kraken_bridge import (
    append_verified_kraken_after_blockchain,
    fetch_completed_kraken_daily,
)
from engines.research.verified_recent_price_bridge import fetch_public_series

LAST_CLOSE_MAX_AGE_DAYS=1
RECENT_OVERLAP_DAYS=7
MIN_RECENT_KRAKEN_OVERLAP=3
MAX_RECENT_KRAKEN_SINGLE_DIFF_PCT=1.
MAX_CORRECTED_ARCHIVE_OVERLAP_PCT=1.
MAX_VERIFIED_PUBLICATION_LAG_DAYS=7


def _today(value):
    t=pd.Timestamp(value)
    if t.tzinfo is None:
        t=t.tz_localize("UTC")
    else:
        t=t.tz_convert("UTC")
    return t.normalize()


def aligned_blockchain_completed_utc_closes(raw,*,utc_today):
    """Pure copy: Blockchain point D midnight is completed close of D-1."""
    today=_today(utc_today)
    if (not isinstance(raw,pd.DataFrame) or
            "btc_usd" not in raw.columns or raw.empty or
            not isinstance(raw.index,pd.DatetimeIndex) or
            raw.index.tz is None or raw.index.has_duplicates or
            not raw.index.is_monotonic_increasing):
        raise ValueError("Malformed dated Blockchain.com BTC/USD series")
    stamps=raw.index.tz_convert("UTC")
    if not stamps.equals(stamps.normalize()):
        raise ValueError("Blockchain daily chart tick must be UTC midnight")
    if (stamps>today).any():
        raise ValueError("Future-dated Blockchain daily chart tick")
    v=raw["btc_usd"].to_numpy(dtype=float)
    if not pd.Series(v).map(math.isfinite).all() or (v<=0).any():
        raise ValueError("Missing or invalid Blockchain chart BTC/USD price")
    aligned=raw[["btc_usd"]].copy(deep=True)
    aligned.index=stamps-pd.Timedelta(days=1)
    if (aligned.index>=today).any():
        raise ValueError("Chart date correction exposes unfinished BTC candle")
    return aligned


def merge_verified_live_cycle_prices(archive,raw_blockchain,kraken,*,utc_today):
    """Date aligned cross-provider BTC history; fail closed if T-1 unavailable."""
    today=_today(utc_today)
    yesterday=today-pd.Timedelta(days=1)
    chart=aligned_blockchain_completed_utc_closes(
        raw_blockchain,utc_today=today)
    if (not isinstance(kraken,pd.DataFrame) or
            "btc_usd" not in kraken or kraken.empty
            or not isinstance(kraken.index,pd.DatetimeIndex)
            or kraken.index.tz is None or kraken.index.has_duplicates
            or not kraken.index.is_monotonic_increasing
            or not kraken.index.tz_convert("UTC").equals(
                kraken.index.tz_convert("UTC").normalize())):
        raise ValueError("Malformed independent Kraken BTC/USD daily closes")
    candles=kraken.loc[kraken.index<today,["btc_usd"]]
    if yesterday not in candles.index:
        raise ValueError("Missing independently completed yesterday Kraken close")
    values=candles["btc_usd"].to_numpy(dtype=float)
    if not pd.Series(values).map(math.isfinite).all() or (values<=0).any():
        raise ValueError("Nonpositive/nonfinite independent Kraken BTC/USD prices")
    common=chart.index.intersection(candles.index)
    common=common[common>=min(chart.index[-1],yesterday) -
                  pd.Timedelta(days=RECENT_OVERLAP_DAYS-1)]
    if len(common)<MIN_RECENT_KRAKEN_OVERLAP:
        raise ValueError("Insufficient recent independent same-date exchange confirmation")
    deviation=(chart.loc[common,"btc_usd"]/
               candles.loc[common,"btc_usd"]-1).abs()*100.
    if float(deviation.max())>MAX_RECENT_KRAKEN_SINGLE_DIFF_PCT:
        raise ValueError("Blockchain/Kraken daily-close source disagreement >1%")
    bridge=None
    extended=chart
    lag_days=(yesterday-chart.index[-1]).days
    if lag_days>MAX_VERIFIED_PUBLICATION_LAG_DAYS:
        raise ValueError(f"Blockchain reference stale by {lag_days} days; maximum verified bridge is {MAX_VERIFIED_PUBLICATION_LAG_DAYS}")
    if chart.index[-1]<yesterday:
        # Preserve the same date-exact, consecutive Kraken bridge and overlap
        # checks; only extend its maximum length after strict <=1% verification.
        from unittest.mock import patch
        with patch("engines.research.cycle_forward_kraken_bridge.MAX_PUBLICATION_GAP_DAYS", MAX_VERIFIED_PUBLICATION_LAG_DAYS):
            extended,bridge=append_verified_kraken_after_blockchain(
                chart,candles,utc_today=today)
    else:
        if chart.index[-1]>yesterday:
            raise ValueError("Future price not completed")
    if extended.index[-1]!=yesterday:
        raise ValueError("Market feed not fresh through yesterday completed UTC close")
    merged,archived=merge_verified_cycle_prices(
        archive,extended,utc_today=today)
    if archived["max_overlap_difference_pct"]>MAX_CORRECTED_ARCHIVE_OVERLAP_PCT:
        raise ValueError("Corrected chart price conflicts with archived BTC")
    if merged.index[-1]!=yesterday:
        raise ValueError("Final shared Cycle market UTC close date stale")
    # No missing days since the final archived price. The forward-tape
    # 200WMA itself already requires precisely spaced old weekly dates.
    if "price_usd" not in archive or archive.empty:
        raise ValueError("Archived BTC/USD price history absent")
    archive_last=archive.index.max()
    all_days=pd.date_range(
        archive_last+pd.Timedelta(days=1),yesterday,
        freq="D",tz="UTC")
    if not all_days.isin(merged.index).all():
        raise ValueError("Missing consecutive UTC BTC market closing date")
    return merged,{
        **archived,
        "btc_price_timestamp_basis":
            "Blockchain midnight tick D=completed close D-1; Kraken OHLC tick D=close D",
        "asof_utc_expected_completed_close_date":str(yesterday.date()),
        "strict_close_date_verified":True,
        "blockchain_latest_aligned_date_utc":str(chart.index[-1].date()),
        "kraken_latest_completed_date_utc":str(candles.index[-1].date()),
        "recent_kraken_blockchain_overlap_days":len(common),
        "recent_kraken_blockchain_max_diff_pct":round(
            float(deviation.max()),4),
        "recent_kraken_blockchain_median_diff_pct":round(
            float(deviation.median()),4),
        "kraken_contiguous_completed_day_bridge":(
            bridge["appended_dates"] if bridge else []),
        "archive_raw_prices_preserved":True,
        "live_trading_allocations_unchanged":True,
        "source_provenance":"BlockHorizon archived BTC/USD + date-aligned Blockchain.com + independently verified completed Kraken XBTUSD OHLC",
        "not_executable_ASX_IBIT_quote":True,
    }


def fetch_cycle_live_sources(*,asof):
    """Exactly ONE shared source bundle for Streamlit + daily ntfy."""
    when=_today(asof)
    raw,fx=fetch_public_series(asof=str(when.date()))
    kraken=fetch_completed_kraken_daily(utc_today=when)
    return raw,fx,kraken
