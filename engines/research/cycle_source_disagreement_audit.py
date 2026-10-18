"""Research-only attribution of the ~6.29% BTC daily-price provider mismatch.

The current Cycle market feed preserves October-2026 BlockHorizon archived
BTC/USD prices, and only appends Blockchain.com prices after the archive
cutoff. Its "crosscheck_max_diff_pct" is the MAX ABSOLUTE deviation over
~30 overlapping days, NOT the newest price difference and NOT Kraken's
latest-close accuracy. The research Kraken bridge also has its own recent
overlap check. We must not collapse three distinct checks into one number.

This report freezes date-exact archive vs Blockchain.com vs Kraken spot
daily data, looks for the actual offending dates, and tests whether any
last-prior-close below-200WMA classification would flip if the daily
reference source were different. It does NOT replace any historical
prices, trading recommendation, alert, personal portfolio, or live
crosscheck thresholds. No broker/ASX quote is inferred.
"""
from __future__ import annotations

import argparse
import json
import math
from pathlib import Path

import pandas as pd
import requests

from engines.research.top_signal_horse_race import read_exported_history
from engines.research.verified_recent_price_bridge import fetch_public_series
from engines.research.cycle_forward_kraken_bridge import (
    fetch_completed_kraken_daily,
)
from engines.research.fresh_cash_200wma_matched_backtest import (
    _historical_wma,
)

MAX_LOOKBACK_DAYS=30
CROSSCHECK_REVIEW_LEVEL_PCT=5.
CLOSE_THRESHOLD_REVIEW_MARGIN_PCT=5.


def _day(v):
    x=pd.Timestamp(v)
    return (x.tz_localize("UTC") if x.tzinfo is None
            else x.tz_convert("UTC")).normalize()


def _prices(frame,col,name):
    if (not isinstance(frame,pd.DataFrame) or col not in frame
            or frame.empty or not isinstance(frame.index,pd.DatetimeIndex)
            or frame.index.tz is None or frame.index.has_duplicates
            or not frame.index.is_monotonic_increasing):
        raise ValueError(f"Invalid {name} dated BTC price series")
    series=frame[col].astype(float)
    if not series.index.equals(series.index.normalize()):
        raise ValueError(f"Non-UTC-midnight {name} dates")
    if not series.map(math.isfinite).all() or series.le(0).any():
        raise ValueError(f"Nonpositive/invalid {name} BTC prices")
    return series


def _pair(a,b,*,start,end,name_a,name_b):
    left=a.loc[(a.index>=start)&(a.index<=end)]
    right=b.loc[(b.index>=start)&(b.index<=end)]
    days=left.index.intersection(right.index)
    if not len(days):
        return {"pair":f"{name_a}_versus_{name_b}","overlap_days":0,
                "available":False}
    signed=100*(right.loc[days]/left.loc[days]-1)
    absolute=signed.abs()
    worst=absolute.idxmax()
    return {
        "pair":f"{name_a}_versus_{name_b}",
        "available":True,
        "overlap_days":len(days),
        "first_overlap_date":str(days[0].date()),
        "last_overlap_date":str(days[-1].date()),
        "maximum_absolute_pct":round(float(absolute.max()),5),
        "maximum_deviation_date_utc":str(worst.date()),
        "median_absolute_pct":round(float(absolute.median()),5),
        "median_signed_pct":round(float(signed.median()),5),
        "dates_exceeding_5pct":[str(d.date()) for d in days
                                 if absolute.loc[d]>CROSSCHECK_REVIEW_LEVEL_PCT],
        "latest_pair_deviation_pct":round(float(signed.iloc[-1]),5),
        "latest_pair_absolute_pct":round(float(absolute.iloc[-1]),5),
        "maximum_date_first_price_usd":round(float(a.loc[worst]),4),
        "maximum_date_second_price_usd":round(float(b.loc[worst]),4),
    }


def source_overlap_audit(archive,blockchain,*,kraken=None,
                         asof="2026-10-18"):
    today=_day(asof)
    a=_prices(archive,"price_usd","archived_BlockHorizon")
    b=_prices(blockchain,"btc_usd","Blockchain.com")
    a=a.loc[a.index<today]
    b=b.loc[b.index<today]
    if not len(a) or not len(b):
        raise ValueError("No prior completed BTC prices")
    cutoff=a.index[-1]
    start=cutoff-pd.Timedelta(days=MAX_LOOKBACK_DAYS)
    pair_ab=_pair(a,b,start=start,end=cutoff,
                  name_a="archive",name_b="Blockchain")
    if not pair_ab["available"] or pair_ab["overlap_days"]<3:
        raise ValueError("Not enough DATE-MATCHED archived/public BTC overlap")
    k=None
    pairs=[pair_ab]
    if kraken is not None:
        k=_prices(kraken,"btc_usd","Kraken_XBTUSD")
        k=k.loc[k.index<today]
        if len(k):
            pairs.append(_pair(a,k,start=start,end=cutoff,
                               name_a="archive",name_b="Kraken"))
            pairs.append(_pair(b,k,start=start,end=cutoff,
                               name_a="Blockchain",name_b="Kraken"))
    common=a.index.intersection(b.index)
    common=common[(common>=start)&(common<=cutoff)]
    samples=[]
    critical=[]
    for d in common:
        archive_px=float(a.loc[d])
        public_px=float(b.loc[d])
        kraken_px=(float(k.loc[d]) if k is not None and d in k.index
                   else None)
        # Compare how individual close references straddle the gate
        # against ONE fixed, archived-history, exact-prior 200WMA.
        # This is a local sensitivity only: NOT a complete alternate
        # 200-week price history or actual changed BUY recommendation.
        gate=None
        try:
            _,wma=_historical_wma(a,d+pd.Timedelta(days=1))
            if math.isfinite(float(wma)) and wma>0:
                status={
                    "archive":archive_px<float(wma),
                    "Blockchain":public_px<float(wma),
                }
                if kraken_px is not None:
                    status["Kraken"]=kraken_px<float(wma)
                flip=len(set(status.values()))>1
                nearest=min(abs(v/float(wma)-1)
                            for v in (archive_px,public_px)
                            + ((kraken_px,) if kraken_px is not None else ()))
                gate={
                    "archived_reference_prior_200wma_usd":
                        round(float(wma),3),
                    "source_below_wma":status,
                    "potential_different_single_day_gate":flip,
                    "at_least_one_source_within_5pct_200wma":
                        nearest<=CLOSE_THRESHOLD_REVIEW_MARGIN_PCT/100.,
                }
                if flip:
                    critical.append(str(d.date()))
        except (ValueError,KeyError,IndexError):
            pass
        item={
            "date_utc":str(d.date()),
            "archive_BTC_USD":round(archive_px,3),
            "blockchain_BTC_USD":round(public_px,3),
            "archive_vs_blockchain_signed_pct":round(
                100*(public_px/archive_px-1),5),
            "archive_vs_blockchain_absolute_pct":round(
                100*abs(public_px/archive_px-1),5),
            "kraken_BTC_USD":round(kraken_px,3)
                if kraken_px is not None else None,
            "archive_vs_kraken_absolute_pct":round(
                100*abs(kraken_px/archive_px-1),5)
                if kraken_px is not None else None,
            "blockchain_vs_kraken_absolute_pct":round(
                100*abs(kraken_px/public_px-1),5)
                if kraken_px is not None else None,
            "strict_prior_200wma_sensitivity":gate,
        }
        samples.append(item)
    worst=pair_ab["maximum_deviation_date_utc"]
    offending=next(x for x in samples if x["date_utc"]==worst)
    third_source_assessment="UNAVAILABLE_NO_THIRD_SOURCE"
    if offending["kraken_BTC_USD"] is not None:
        ar=float(offending["archive_vs_kraken_absolute_pct"])
        br=float(offending["blockchain_vs_kraken_absolute_pct"])
        if ar<=1 and br>5:
            third_source_assessment="KRAKEN_CLOSER_TO_ARCHIVE_ON_WORST_DAY"
        elif br<=1 and ar>5:
            third_source_assessment="KRAKEN_CLOSER_TO_BLOCKCHAIN_ON_WORST_DAY"
        elif ar<=1 and br<=1:
            third_source_assessment="ALL_SOURCES_AGREE_NEARLY_ON_WORST_DAY"
        else:
            third_source_assessment="AMBIGUOUS_PROVIDER_CLOSE_DEFINITIONS"
    return {
        "research_only":True,
        "prices_overwritten":False,
        "live_cycle_model_or_ntfy_modified":False,
        "calculation":"ABS(blockchain BTC/USD daily point / BlockHorizon historical Price on EXACT UTC date -1), max over 30 calendar day archived cutoff overlap",
        "archive_latest_date":str(cutoff.date()),
        "blockchain_latest_completed_date":str(b.index[-1].date()),
        "kraken_latest_completed_date":(
            str(k.index[-1].date()) if k is not None and len(k) else None),
        "source_pairs":pairs,
        "historical_6p29_crosscheck_is_NOT_last_BTC_spot_error":True,
        "worst_blockchain_archive_overlap_day":offending,
        "third_source_assessment_on_worst_date":third_source_assessment,
        "potential_200wma_crossing_disagreement_dates":critical,
        "local_gate_sensitivity_uses_archived_200wma_for_all_prices":True,
        "source_observations":samples,
        "manual_data_provenance_review_required":(
            pair_ab["maximum_absolute_pct"]>=CROSSCHECK_REVIEW_LEVEL_PCT),
        "eligible_to_change_live_source_or_signal":False,
    }


def main(argv=None):
    parser=argparse.ArgumentParser()
    parser.add_argument("--out",type=Path,default=Path(
        "artifacts/cycle_source_overlap_oct2026.json"))
    args=parser.parse_args(argv)
    import datetime as dt
    today=dt.datetime.now(dt.timezone.utc)
    archive=read_exported_history()
    price,fx=fetch_public_series(asof=today.date().isoformat())
    # Only source prices matter here; FX deliberately not fabricated.
    kraken=None
    kraken_error=None
    try:
        kraken=fetch_completed_kraken_daily(utc_today=today)
    except (requests.RequestException,ValueError) as exc:
        kraken_error=f"{type(exc).__name__}: {exc}"
    outcome=source_overlap_audit(
        archive,price,kraken=kraken,asof=today)
    outcome["Kraken_3rd_source_fetch_status"]=(
        "OK" if kraken is not None else "UNAVAILABLE")
    outcome["Kraken_fetch_error"]=kraken_error
    args.out.parent.mkdir(parents=True,exist_ok=True)
    args.out.write_text(json.dumps(outcome,indent=2,sort_keys=True)+"\n")
    for pair in outcome["source_pairs"]:
        print(json.dumps(pair,sort_keys=True))
    print("WORST_DAY "+
          json.dumps(outcome["worst_blockchain_archive_overlap_day"],
                     sort_keys=True))
    print("SOURCE_INTERPRETATION "+
          json.dumps({
            "third_source_assessment":outcome[
                "third_source_assessment_on_worst_date"],
            "potential_200wma_crossing_disagreement_dates":outcome[
                "potential_200wma_crossing_disagreement_dates"],
            "not_last_BTC_price_error":True,
            "manual_data_provenance_review_required":outcome[
                "manual_data_provenance_review_required"],
          },sort_keys=True))
    print("RESEARCH ONLY. No live Cycle BUY/SELL, FX, ntfy or portfolio changes.")


if __name__=="__main__":
    main()
