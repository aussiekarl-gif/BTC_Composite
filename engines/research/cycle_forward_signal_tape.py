"""Immutable prospective BTC Cycle Trading research tape, no private portfolio.

Runs once per UTC day AFTER a public Bitcoin daily close is completed.
Stores the exact live shared market-level BUY WATCH / SELL WATCH / HOLD
plus dated inputs and code fingerprint, NOT an ASX:IBIT trade or personal
portfolio action. Outcomes can only be derived from LATER tape rows that
were saved prospectively. A 2026 provider export is NOT an onchain point-
in-time vintage and must not become a fabricated 2018 forecast.

If a source is unavailable, stale, inconsistent, or halving unverified,
do not write a BUY/HOLD/Sell row. Fail closed and visibly fail CI.
Snapshots are append-only: prior dates/hashes cannot be overwritten.
No ntfy, brokers, Google Sheets, new Production signals or order writes.
"""
from __future__ import annotations

import argparse
import csv
import datetime as dt
import hashlib
import io
import json
import math
from pathlib import Path

import numpy as np
import pandas as pd

from engines.research.cycle_market_feed import merge_verified_cycle_prices
from engines.research.cycle_trading_dashboard_model import build_dashboard_market
from engines.research.cycle_trade_allocation import calculate_allocation_signal
from engines.research.cycle_halving_countdown import (
    fetch_halving_countdown, normalise_halving_epoch_metadata,
)
from engines.research.top_signal_horse_race import read_exported_history
from engines.research.verified_recent_price_bridge import fetch_public_series

ROOT = Path(__file__).resolve().parents[2]
TARGET_DIR = ROOT / "data" / "research_forward_validation"
SIGNAL_TAPE = "cycle_market_signals.csv"
OUTCOME_TAPE = "cycle_signal_outcomes.csv"
HORIZONS = (7, 30, 90)
# A forward-only signal must use YESTERDAY'S completed UTC close.
# A 2/3-day-old BTC mark remains useful market context but may already
# include partly-known price returns, so it must NOT become a prediction.
MAX_OBSERVED_LAG_DAYS = 1
GENESIS = "0" * 64
STRATEGY_LABEL = "shared_cycle_trade_allocation_market_v1_not_historical_wallet"
SIGNAL_COLUMNS = (
    "observation_date_utc", "captured_at_utc",
    "signal_input_last_prior_close_date_utc",
    "btc_usd_observed_close", "prior_btc_usd_close",
    "prior_200wma_usd", "prior_close_div_200wma",
    "fx_observed_prior_aud_per_usd", "fx_prior_date_utc",
    "verified_halving_date", "days_after_halving",
    "signal", "buy_pct_of_remaining_available_cash",
    "sell_pct_of_current_holdings",
    "trailing_90day_drawdown_prior_pct",
    "prior_50dma_declining",
    "lagged_30d_annualised_volatility_pct",
    "market_data_provider", "source_crosscheck_max_diff_pct",
    "model_name", "model_code_sha256",
    "point_in_time_onchain_risk_status",
    "trade_executable", "prior_row_hash", "row_hash",
)
OUTCOME_COLUMNS = (
    "base_observation_date_utc", "horizon_days",
    "future_observation_date_utc", "signal_at_base",
    "base_usd_close", "future_usd_close",
    "btc_price_change_pct",
    "signal_signed_price_change_pct",
    "maximum_observed_downside_pct",
    "maximum_observed_upside_pct",
    "source_base_row_hash", "source_future_row_hash",
    "evaluated_at_utc", "prior_row_hash", "row_hash",
)


def _day(value):
    t = pd.Timestamp(value)
    return (t.tz_localize("UTC") if t.tzinfo is None
            else t.tz_convert("UTC")).normalize()


def _utc_instant(value):
    t = pd.Timestamp(value)
    if t.tzinfo is None:
        raise ValueError("Capture instant must be timezone-aware")
    return t.tz_convert("UTC")


def _canonical(row, columns):
    obj={c:str(row[c]) for c in columns if c!="row_hash"}
    return json.dumps(obj,sort_keys=True,separators=(",",":"),ensure_ascii=True)


def _signature(row, columns):
    return hashlib.sha256(_canonical(row,columns).encode("utf-8")).hexdigest()


def _clean_input(row,columns):
    if set(row) != set(columns)-{"prior_row_hash","row_hash"}:
        raise ValueError("Unexpected immutable tape schema")
    return {k:str(row[k]) for k in columns if k not in
            ("prior_row_hash","row_hash")}


def _read_rows(content,columns,*,date_key=None):
    if not content:
        return []
    reader=csv.DictReader(io.StringIO(content))
    if reader.fieldnames != list(columns):
        raise ValueError("Historical tape columns changed; refuse migration")
    rows=list(reader)
    previous=GENESIS
    seen=set()
    for row in rows:
        if None in row or any(v is None for v in row.values()):
            raise ValueError("Corrupted immutable CSV columns")
        if row["prior_row_hash"]!=previous or row["row_hash"]!=_signature(row,columns):
            raise ValueError("Modified, reordered, or corrupted forward record")
        if date_key:
            key=row[date_key]
            if key in seen:
                raise ValueError("Duplicate frozen forward observation date")
            seen.add(key)
        previous=row["row_hash"]
    return rows


def _dump_rows(rows,columns):
    stream=io.StringIO(newline="")
    writer=csv.DictWriter(stream,fieldnames=list(columns),lineterminator="\n")
    writer.writeheader()
    writer.writerows(rows)
    return stream.getvalue()


def append_snapshot(content,new):
    """Append one observed date; duplicate is a no-op, not a revision.

    First saved version wins, irrespective of later provider revisions,
    code changes, or rerun time. Tamper-evident hash chain validated.
    """
    rows=_read_rows(content,SIGNAL_COLUMNS,date_key="observation_date_utc")
    clean=_clean_input(new,SIGNAL_COLUMNS)
    current=_day(clean["observation_date_utc"])
    if rows:
        previous=_day(rows[-1]["observation_date_utc"])
        if current==previous:
            return content,False
        if current<previous:
            raise ValueError("Historical observation backfill forbidden")
    clean["prior_row_hash"]=rows[-1]["row_hash"] if rows else GENESIS
    clean["row_hash"]=_signature(clean,SIGNAL_COLUMNS)
    rows.append(clean)
    return _dump_rows(rows,SIGNAL_COLUMNS),True


def _prior_annual_volatility(price,date):
    date=_day(date)
    days=pd.date_range(date-pd.Timedelta(days=31),
                       date-pd.Timedelta(days=1),freq="D",tz="UTC")
    if not days.isin(price.index).all():
        raise ValueError("Incomplete trailing prior-price volatility dates")
    raw=price.loc[days].to_numpy(float)
    if not np.isfinite(raw).all() or (raw<=0).any():
        raise ValueError("Invalid prior volatility prices")
    returns=np.diff(np.log(raw))
    return float(np.std(returns,ddof=1)*math.sqrt(365)*100)


def _code_hash():
    here=Path(__file__).resolve().parent
    paths=(
        here/"cycle_trade_allocation.py",
        here/"cycle_trading_dashboard_model.py",
        here/"cycle_market_feed.py",
    )
    digest=hashlib.sha256()
    for path in paths:
        digest.update(path.name.encode())
        digest.update(path.read_bytes())
    return digest.hexdigest()


def build_snapshot(archive,public,fx,*,captured_at_utc,
                   verified_halving_date,code_sha256=None):
    """Only verified, completed UTC daily prices; no future score fields."""
    instant=_utc_instant(captured_at_utc)
    today=instant.normalize()
    if not verified_halving_date:
        raise ValueError("Unverified halving date: refuse prospective signal")
    combined,verified=merge_verified_cycle_prices(
        archive,public,utc_today=today)
    market=build_dashboard_market(
        combined,fx,asof=str(today.date()),
        confirmed_halving_date=verified_halving_date)
    date=_day(market["asof_date"])
    if date>=today or (today-date).days != MAX_OBSERVED_LAG_DAYS:
        raise ValueError(
            "Stale or incomplete BTC UTC daily price: no forward snapshot "
            "without the latest completed prior UTC close")
    if market["usd_aud_prior"] is None or not market["fx_source_date"]:
        raise ValueError("Stale or absent prior AUD/USD FX")
    prior_date=date-pd.Timedelta(days=1)
    if prior_date not in market["price_history"].index:
        raise ValueError("Prior BTC close date absent")
    signal=calculate_allocation_signal(
        market,buy_style="adaptive_recovery")
    vol=_prior_annual_volatility(market["price_history"],date)
    code_hash=code_sha256 if code_sha256 is not None else _code_hash()
    if (not isinstance(code_hash,str)
            or len(code_hash)!=64
            or any(v not in "0123456789abcdef" for v in code_hash)):
        raise ValueError("Model code fingerprint required")
    def number(x,n=6):
        if not math.isfinite(float(x)):
            raise ValueError("Nonfinite signal input")
        return format(float(x),f".{n}f")
    return {
        "observation_date_utc":str(date.date()),
        "captured_at_utc":instant.isoformat(),
        "signal_input_last_prior_close_date_utc":str(prior_date.date()),
        "btc_usd_observed_close":number(market["btc_price_usd"],6),
        "prior_btc_usd_close":number(market["previous_close_usd"],6),
        "prior_200wma_usd":number(market["prior_200wma_usd"],6),
        "prior_close_div_200wma":number(
            market["previous_close_usd"]/market["prior_200wma_usd"],8),
        "fx_observed_prior_aud_per_usd":number(market["usd_aud_prior"],8),
        "fx_prior_date_utc":str(market["fx_source_date"]),
        "verified_halving_date":str(market["halving_date"]),
        "days_after_halving":str(int(market["halving_day"])),
        "signal":str(signal["signal"]),
        "buy_pct_of_remaining_available_cash":number(
            signal["buy_pct_cash"],4),
        "sell_pct_of_current_holdings":number(
            signal["sell_pct_held"],4),
        "trailing_90day_drawdown_prior_pct":number(
            signal["prior_90day_drawdown_pct"],4),
        "prior_50dma_declining":str(bool(signal["prior_sma50_declining"])),
        "lagged_30d_annualised_volatility_pct":number(vol,4),
        "market_data_provider":"archived_BlockHorizon_plus_verified_Blockchain.com",
        "source_crosscheck_max_diff_pct":number(
            verified["max_overlap_difference_pct"],4),
        "model_name":STRATEGY_LABEL,
        "model_code_sha256":code_hash,
        "point_in_time_onchain_risk_status":"NOT_VERIFIED_NOT_INCLUDED",
        "trade_executable":"False",
    }


def _was_captured_prospectively(row):
    """One-day lag exactly; reject previously late research rows for scoring.

    A row stamped 15 October but first written 18 October already observed
    part of its seven-day future, so it cannot be labelled a true forward
    forecast even if its stored value and chain are authentic.
    """
    try:
        timestamp=_utc_instant(row["captured_at_utc"])
        observed=_day(row["observation_date_utc"])
    except (TypeError,ValueError,KeyError):
        return False
    return (timestamp.normalize()-observed).days==1


def append_due_outcomes(existing,signals,*,evaluated_at_utc):
    """Score ONLY truly prospective price observations frozen after each UTC close.

    Future data cannot retroactively revise a signal row. Require ALL daily
    observations in the 7/30/90-day window for drawdown/return scoring.
    Missing dates, originally late captures and current-day records stay
    unscored; never silently interpolate or backfill.
    """
    snapshots=_read_rows(signals,SIGNAL_COLUMNS,
                         date_key="observation_date_utc")
    results=_read_rows(existing,OUTCOME_COLUMNS)
    prior=results[-1]["row_hash"] if results else GENESIS
    present={_day(x["observation_date_utc"]):x for x in snapshots}
    seen={(x["base_observation_date_utc"],int(x["horizon_days"]))
          for x in results}
    timestamp=_utc_instant(evaluated_at_utc).isoformat()
    added=0
    for base in snapshots:
        # Freeze and retain any legitimate older row without rewriting it.
        # A 3-day late 'first capture' is an auditable data point, not a
        # prospectively scored forecast. Its later rows must also be timely.
        if not _was_captured_prospectively(base):
            continue
        start=_day(base["observation_date_utc"])
        for horizon in HORIZONS:
            key=(str(start.date()),horizon)
            if key in seen:
                continue
            days=pd.date_range(start+pd.Timedelta(days=1),
                               start+pd.Timedelta(days=horizon),
                               freq="D",tz="UTC")
            if not days.isin(list(present)).all():
                continue
            if not all(_was_captured_prospectively(present[day])
                       for day in days):
                continue
            future=present[days[-1]]
            px=float(base["btc_usd_observed_close"])
            path=np.array([float(present[d]["btc_usd_observed_close"])
                           for d in days],dtype=float)
            if not np.isfinite(path).all() or np.any(path<=0) or px<=0:
                raise ValueError("Invalid frozen future price path")
            change=100*(float(path[-1])/px-1)
            signal=base["signal"]
            direction={"BUY WATCH":1,"SELL WATCH":-1,"HOLD":0}
            if signal not in direction:
                raise ValueError("Unknown frozen market-level signal")
            record={
                "base_observation_date_utc":key[0],
                "horizon_days":str(horizon),
                "future_observation_date_utc":str(days[-1].date()),
                "signal_at_base":signal,
                "base_usd_close":base["btc_usd_observed_close"],
                "future_usd_close":future["btc_usd_observed_close"],
                "btc_price_change_pct":f"{change:.5f}",
                "signal_signed_price_change_pct":(
                    f"{change*direction[signal]:.5f}" if direction[signal]
                    else ""),
                "maximum_observed_downside_pct":f"{100*(min(px,*path)/px-1):.5f}",
                "maximum_observed_upside_pct":f"{100*(max(px,*path)/px-1):.5f}",
                "source_base_row_hash":base["row_hash"],
                "source_future_row_hash":future["row_hash"],
                "evaluated_at_utc":timestamp,
                "prior_row_hash":prior,
            }
            record["row_hash"]=_signature(record,OUTCOME_COLUMNS)
            results.append(record)
            seen.add(key)
            prior=record["row_hash"]
            added+=1
    if added==0:
        return existing,0
    return _dump_rows(results,OUTCOME_COLUMNS),added


def run_once(*,out_dir=TARGET_DIR, now=None):
    instant=(pd.Timestamp.now(tz="UTC") if now is None
             else _utc_instant(now))
    out=Path(out_dir)
    archive=read_exported_history()
    public,fx=fetch_public_series(asof=str(instant.date()))
    halving=normalise_halving_epoch_metadata(fetch_halving_countdown(now=
        instant.to_pydatetime()))
    verified_date=(halving["last_halving_date"]
                   if halving.get("halving_date_verified") else None)
    new=build_snapshot(
        archive,public,fx,captured_at_utc=instant,
        verified_halving_date=verified_date)
    p_signals=out/SIGNAL_TAPE
    p_outcomes=out/OUTCOME_TAPE
    current=p_signals.read_text() if p_signals.exists() else ""
    updated,added=append_snapshot(current,new)
    prior_results=p_outcomes.read_text() if p_outcomes.exists() else ""
    scored,number=append_due_outcomes(
        prior_results,updated,evaluated_at_utc=instant)
    if added or number:
        out.mkdir(parents=True,exist_ok=True)
    if added:
        p_signals.write_text(updated)
    if number:
        p_outcomes.write_text(scored)
    return {
        "recorded_new_prospective_close":added,
        "observation_date_utc":new["observation_date_utc"],
        "market_signal":new["signal"],
        "buy_pct_cash":new["buy_pct_of_remaining_available_cash"],
        "sell_pct_holdings":new["sell_pct_of_current_holdings"],
        "new_matured_scores":number,
        "no_user_portfolio_or_ntfy_write":True,
    }


def main():
    p=argparse.ArgumentParser()
    p.add_argument("--out-dir",type=Path,default=TARGET_DIR)
    args=p.parse_args()
    print(json.dumps(run_once(out_dir=args.out_dir),sort_keys=True))


if __name__=="__main__":
    main()
