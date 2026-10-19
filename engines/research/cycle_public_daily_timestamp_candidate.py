"""Strict RESEARCH-ONLY Blockchain.com daily timestamp correction candidate.

Chart point at UTC midnight D represents the just-completed BTC close
ending at D, i.e. completed close date D-1. Empirically supported by
Oct 2026 archived BlockHorizon and completed Kraken OHLC comparisons.

Never modify shared live parser, saved forward data, ntfy, Streamlit, model
parameters, personal holdings, broker, or research master.
"""
from __future__ import annotations

import datetime as dt
import math
from typing import Any

import pandas as pd

from engines.research.cycle_market_feed import merge_verified_cycle_prices
from engines.research.cycle_forward_kraken_bridge import append_verified_kraken_after_blockchain

# Conservative independent audits, stricter than existing generic merge gate.
ARCHIVE_OVERLAP_DAYS = 3
KRAKEN_OVERLAP_DAYS = 3
REVIEW_ARCHIVE_MAX_DIFF = .02  # 2%, stop instead of hiding disagreement
REVIEW_KRAKEN_MAX_DIFF = .01   # 1%
PRICE_HISTORY_NOT_A_BROKER_EXECUTION = True


def _utc_day(value: Any) -> pd.Timestamp:
    x = pd.Timestamp(value)
    return (x.tz_localize("UTC") if x.tzinfo is None
            else x.tz_convert("UTC")).normalize()


def strict_previous_utc_close(payload: dict[str, Any], *, captured_at_utc: dt.datetime
                              ) -> pd.DataFrame:
    """Raw epoch UTC-MIDNIGHT point D becomes completed trading-close date D-1.

    Reject nonmidnight/future/missing/nonfinite point; never guess whether a
    new provider payload switched timestamp semantics.
    """
    if (not isinstance(captured_at_utc, dt.datetime)
        or captured_at_utc.tzinfo is None
        or captured_at_utc.utcoffset() is None):
        raise ValueError("Timezone-aware HTTP response receipt required")
    observed = captured_at_utc.astimezone(dt.timezone.utc)
    if not isinstance(payload, dict) or not isinstance(payload.get("values"),list):
        raise ValueError("Blockchain.com chart values array required")
    values=payload["values"]
    if not values:
        raise ValueError("No public chart points")
    rows=[]
    for point in values:
        if not isinstance(point,dict) or "x" not in point or "y" not in point:
            raise ValueError("Malformed Blockchain chart point")
        raw=point["x"]
        if isinstance(raw,bool) or not isinstance(raw,(int,float)) or not math.isfinite(raw):
            raise ValueError("Invalid chart epoch")
        if int(raw) != raw:
            raise ValueError("Fractional chart epoch")
        try:
            stamp=dt.datetime.fromtimestamp(int(raw),dt.timezone.utc)
        except (OverflowError,ValueError,OSError) as err:
            raise ValueError("Unrepresentable chart epoch") from err
        if stamp.time()!=dt.time(0,0):
            raise ValueError("Non-midnight chart timestamp; label semantics unverified")
        if stamp>observed:
            raise ValueError("Provider chart observation not captured yet")
        px=point["y"]
        try:
            price=float(px)
        except (TypeError,ValueError,OverflowError) as err:
            raise ValueError("Invalid BTC USD chart price") from err
        if not math.isfinite(price) or price<=0:
            raise ValueError("Invalid BTC USD chart price")
        # At midnight D a fully elapsed D-1 close is available; NEVER
        # interpret point as the close of the still ongoing UTC day D.
        close_date=(stamp-dt.timedelta(days=1))
        if close_date.date()>=observed.date():
            raise ValueError("Future/unfinished UTC daily close")
        rows.append((close_date,price))
    if any(a[0]>=b[0] for a,b in zip(rows,rows[1:])):
        raise ValueError("Out of order or duplicated daily close timestamps")
    return pd.DataFrame({"btc_usd":[p for _,p in rows]},
                        index=pd.DatetimeIndex([t for t,_ in rows],tz="UTC"))


def build_corrected_source_candidate(archive: pd.DataFrame,
                                     raw_blockchain: dict[str, Any],
                                     completed_kraken: pd.DataFrame, *,
                                     captured_at_utc: dt.datetime):
    """A parallel candidate, NEVER a live input or buy/sell recommendation.

    An independently verified Kraken contiguous short bridge is mandatory.
    The preserved archive remains immutable. No live market model import.
    """
    today=_utc_day(captured_at_utc)
    aligned=strict_previous_utc_close(raw_blockchain,captured_at_utc=captured_at_utc)
    if (not isinstance(archive,pd.DataFrame) or "price_usd" not in archive
        or archive.empty or not isinstance(archive.index,pd.DatetimeIndex)
        or archive.index.tz is None or archive.index.has_duplicates):
        raise ValueError("Dated independent historic BTC/USD archive required")
    if (not isinstance(completed_kraken,pd.DataFrame)
        or "btc_usd" not in completed_kraken or completed_kraken.empty
        or not isinstance(completed_kraken.index,pd.DatetimeIndex)
        or completed_kraken.index.tz is None or completed_kraken.index.has_duplicates):
        raise ValueError("Independent completed Kraken price series required")
    if not archive.index.is_monotonic_increasing or not completed_kraken.index.is_monotonic_increasing:
        raise ValueError("Sources must be date sorted")
    if archive.index[-1]>=today or completed_kraken.index[-1]>=today:
        raise ValueError("Future or unfinished BTC reference in source")
    if aligned.index[-1]>=today:
        raise ValueError("Newly labelled UTC close incomplete")
    # Use exact date-matched PRIMARY historic references, rather than
    # comparing raw midnight D with archive completed close D.
    cutoff=archive.index[-1]
    common=archive.index.intersection(aligned.index)
    common=common[common>=cutoff-pd.Timedelta(days=30)]
    if len(common)<ARCHIVE_OVERLAP_DAYS:
        raise ValueError("Not enough aligned archive chart overlap")
    historic=archive.loc[common,"price_usd"].astype(float)
    public=aligned.loc[common,"btc_usd"].astype(float)
    if (not (historic.gt(0)&public.gt(0)).all()
        or not (historic.map(math.isfinite)&public.map(math.isfinite)).all()):
        raise ValueError("Invalid historical close values")
    spread=(public/historic-1).abs()
    if float(spread.max())>REVIEW_ARCHIVE_MAX_DIFF:
        raise ValueError("Corrected timestamp candidate does not match original historic archive")
    # Independent 3-day-overlap Kraken verification BEFORE trusting any
    # bridge, and stricter 1% source disagreement threshold.
    common_k=aligned.index.intersection(completed_kraken.index)
    common_k=common_k[common_k>=aligned.index[-1]-pd.Timedelta(days=6)]
    if len(common_k)<KRAKEN_OVERLAP_DAYS:
        raise ValueError("No recent independent Kraken overlap")
    diff=(aligned.loc[common_k,"btc_usd"]/
          completed_kraken.loc[common_k,"btc_usd"]-1).abs()
    if not diff.map(math.isfinite).all() or float(diff.max())>REVIEW_KRAKEN_MAX_DIFF:
        raise ValueError("Aligned public BTC close conflicts with completed Kraken exchange data")
    with_kraken, bridge=append_verified_kraken_after_blockchain(
        aligned, completed_kraken, utc_today=today)
    combined, meta=merge_verified_cycle_prices(
        archive,with_kraken,utc_today=today)
    if combined.index[-1]!=today-pd.Timedelta(days=1):
        raise ValueError("Source cannot provide most recent completed UTC close")
    if not combined.loc[archive.index,"price_usd"].equals(
        archive["price_usd"].sort_index()):
        raise AssertionError("Correction attempted to revise historical archive prices")
    return {
        "source":"Blockchain.com market-price chart midnight D relabelled as D-1, independent Kraken verified",
        "corrected_latest_public_close_utc":str(aligned.index[-1].date()),
        "latest_verified_full_close_utc":str(combined.index[-1].date()),
        "max_archive_overlap_difference_pct":round(float(spread.max())*100,5),
        "max_recent_kraken_overlap_difference_pct":round(float(diff.max())*100,5),
        "archive_overlap_days":len(common),
        "kraken_recent_overlap_days":len(common_k),
        "kraken_bridge_appended_dates":bridge["appended_dates"],
        "original_archive_prices_preserved":True,
        "point_in_time_daily_close_only":True,
        "available_for_live_trading":False,
        "live_parser_modified":False,
        "portfolio_or_ntfy_modified":False,
        "research_only_no_investment_instruction":True,
        "candidate_history":combined,
    }
