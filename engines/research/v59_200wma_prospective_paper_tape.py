"""Append-only prospective V5.9 200WMA DCA paper signals and ASX observations.

This tape starts prospectively after 2026-11-19T08:55:02Z. It never
reconstructs signals from earlier rows. A Sunday BTC close must have been
captured on the following UTC day and the point-in-time BTC row must itself
be hash-valid. The existing 200WMA field is consumed as frozen; no current
or future price is used to revise it.

The first expected ASX session is the next weekday after the BTC row's
capture instant in Sydney. To fail closed on public holidays or missing
provider captures, only that exact expected date may be linked. We do not
skip forward to a later quote. Yahoo's close remains indicative, not a
broker fill or executable price. No orders, private portfolio, ntfy or
Production changes.
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
from zoneinfo import ZoneInfo

from engines.research.cycle_forward_signal_tape import (
    GENESIS, _read_rows, _dump_rows, _signature, _clean_input,
    SIGNAL_COLUMNS, _was_captured_prospectively,
)
from engines.research.ibit_asx_forward_close_tape import COLUMNS as IBIT_COLUMNS

ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "data" / "research_forward_validation"
BTC_TAPE = DATA / "cycle_market_signals.csv"
IBIT_TAPE = DATA / "asx_ibit_closes_forward.csv"
SIGNAL_TAPE = DATA / "v59_200wma_paper_signals.csv"
EXECUTION_TAPE = DATA / "v59_200wma_paper_asx_observations.csv"
ARTIFACT = ROOT / "artifacts" / "v59_200wma_paper_status.json"
SYDNEY = ZoneInfo("Australia/Sydney")
PAPER_START_AFTER_UTC = dt.datetime.fromisoformat("2026-11-19T08:55:02+00:00")
MODEL_LABEL = "v59_200wma_distance_A_measured_percent_cash_v1"

SIGNAL_COLUMNS_PAPER = (
    "btc_observation_date_utc", "btc_captured_at_utc",
    "signal_date_utc", "expected_next_asx_weekday_sydney",
    "btc_usd_sunday_close", "prior_200wma_usd",
    "discount_below_200wma_pct", "ratio_to_200wma",
    "current_baseline_buy_pct_available_cash",
    "A_measured_buy_pct_deployable_cash",
    "A_measured_protected_cash_floor_pct_initial_cash",
    "A_measured_30pct_protected_cash_floor_pct_initial_cash",
    "A_measured_30pct_floor_buy_pct_deployable_cash",
    "model_name", "model_code_sha256", "source_btc_row_hash",
    "prior_row_hash", "row_hash",
)
EXECUTION_COLUMNS = (
    "btc_observation_date_utc", "expected_asx_session_date_sydney",
    "observed_asx_session_date_sydney", "captured_at_utc",
    "reported_close_aud", "daily_low_aud", "daily_high_aud",
    "daily_volume", "provider", "is_confirmed_broker_fill",
    "source_btc_signal_row_hash", "source_asx_row_hash",
    "prior_row_hash", "row_hash",
)


def _next_weekday(day: dt.date) -> dt.date:
    candidate = day + dt.timedelta(days=1)
    while candidate.weekday() >= 5:
        candidate += dt.timedelta(days=1)
    return candidate


def _sha_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _load(path: Path) -> str:
    return path.read_text() if path.exists() else ""


def _append(content: str, new: dict, columns: tuple[str, ...],
            date_key: str) -> tuple[str, bool]:
    rows = _read_rows(content, columns, date_key=date_key)
    clean = _clean_input(new, columns)
    key = clean[date_key]
    if rows:
        last = rows[-1][date_key]
        if key == last:
            return content, False
        if key < last:
            raise ValueError("Prospective paper tape backfill forbidden")
    clean["prior_row_hash"] = rows[-1]["row_hash"] if rows else GENESIS
    clean["row_hash"] = _signature(clean, columns)
    rows.append(clean)
    return _dump_rows(rows, columns), True


def build_paper_signal(btc_row: dict, *, model_sha256: str) -> dict:
    """Build only from one new, Sunday-dated, next-day captured BTC snapshot."""
    observation = dt.date.fromisoformat(btc_row["observation_date_utc"])
    signal_date = dt.date.fromisoformat(
        btc_row["signal_input_last_prior_close_date_utc"])
    captured = dt.datetime.fromisoformat(btc_row["captured_at_utc"])
    if captured.tzinfo is None:
        raise ValueError("BTC capture instant must be timezone-aware")
    captured = captured.astimezone(dt.timezone.utc)
    if captured < PAPER_START_AFTER_UTC:
        raise ValueError("Pre-launch BTC observation cannot enter paper tape")
    if signal_date.weekday() != 6:
        raise ValueError("Only a completed Sunday BTC close is a weekly signal")
    if not _was_captured_prospectively(btc_row):
        raise ValueError("BTC input row was not captured prospectively")
    if captured.date() <= signal_date:
        raise ValueError("Sunday close must be captured after its signal date")
    prior_wma = float(btc_row["prior_200wma_usd"])
    close = float(btc_row["prior_btc_usd_close"])
    ratio = float(btc_row["prior_close_div_200wma"])
    if not all(math.isfinite(x) and x > 0 for x in (prior_wma, close, ratio)):
        raise ValueError("Invalid frozen BTC close or prior 200WMA")
    expected_ratio = close / prior_wma
    if abs(expected_ratio - ratio) > 0.000001:
        raise ValueError("Frozen BTC/200WMA ratio does not reconcile")
    discount = max(0.0, (1.0 - ratio) * 100.0)
    if discount + 1e-9 >= 30.0:
        a_pct = 7.5
    elif discount + 1e-9 >= 25.0:
        a_pct = 5.0
    elif discount + 1e-9 >= 20.0:
        a_pct = 3.5
    else:
        a_pct = 2.5
    # The 30% reserve is a research overlay. Buy % is applied only to
    # deployable cash above that reserve, not to total cash.
    expected_asx = _next_weekday(captured.astimezone(SYDNEY).date())
    return {
        "btc_observation_date_utc": observation.isoformat(),
        "btc_captured_at_utc": captured.isoformat(),
        "signal_date_utc": signal_date.isoformat(),
        "expected_next_asx_weekday_sydney": expected_asx.isoformat(),
        "btc_usd_sunday_close": f"{close:.6f}",
        "prior_200wma_usd": f"{prior_wma:.6f}",
        "discount_below_200wma_pct": f"{discount:.6f}",
        "ratio_to_200wma": f"{ratio:.8f}",
        "current_baseline_buy_pct_available_cash": "2.500000",
        "A_measured_buy_pct_deployable_cash": f"{a_pct:.6f}",
        "A_measured_protected_cash_floor_pct_initial_cash": "0.000000",
        "A_measured_30pct_protected_cash_floor_pct_initial_cash": "30.000000",
        "A_measured_30pct_floor_buy_pct_deployable_cash": f"{a_pct:.6f}",
        "model_name": MODEL_LABEL,
        "model_code_sha256": model_sha256,
        "source_btc_row_hash": btc_row["row_hash"],
    }


def build_asx_observation(signal_row: dict, asx_row: dict) -> dict:
    expected = dt.date.fromisoformat(
        signal_row["expected_next_asx_weekday_sydney"])
    observed = dt.date.fromisoformat(asx_row["market_session_date_sydney"])
    if observed != expected:
        raise ValueError("ASX quote is not the exact next expected weekday; no forward shift")
    capture = dt.datetime.fromisoformat(asx_row["captured_at_utc"])
    if capture.tzinfo is None or capture.astimezone(SYDNEY).date() != observed:
        raise ValueError("ASX capture timestamp does not match Sydney session date")
    if capture.astimezone(SYDNEY).time() < dt.time(17, 0):
        raise ValueError("ASX close was not captured after Sydney market close")
    if (asx_row["symbol"] != "ASX:IBIT" or asx_row["currency"] != "AUD"
            or asx_row["is_confirmed_broker_fill"] != "False"):
        raise ValueError("Refuse non-AUD ASX IBIT or fabricated broker fill")
    return {
        "btc_observation_date_utc": signal_row["btc_observation_date_utc"],
        "expected_asx_session_date_sydney": expected.isoformat(),
        "observed_asx_session_date_sydney": observed.isoformat(),
        "captured_at_utc": asx_row["captured_at_utc"],
        "reported_close_aud": asx_row["reported_close_aud"],
        "daily_low_aud": asx_row["daily_low_aud"],
        "daily_high_aud": asx_row["daily_high_aud"],
        "daily_volume": asx_row["daily_volume"],
        "provider": asx_row["provider"],
        "is_confirmed_broker_fill": "False",
        "source_btc_signal_row_hash": signal_row["row_hash"],
        "source_asx_row_hash": asx_row["row_hash"],
    }


def process_tapes(btc_text: str, asx_text: str, signal_text: str,
                  execution_text: str, *, model_sha256: str) -> tuple[str, str, dict]:
    btc_rows = _read_rows(btc_text, SIGNAL_COLUMNS,
                          date_key="observation_date_utc")
    asx_rows = _read_rows(asx_text, IBIT_COLUMNS,
                          date_key="market_session_date_sydney")
    signals = _read_rows(signal_text, SIGNAL_COLUMNS_PAPER,
                         date_key="btc_observation_date_utc")
    executions = _read_rows(execution_text, EXECUTION_COLUMNS,
                            date_key="btc_observation_date_utc")
    signal_dates = {r["btc_observation_date_utc"] for r in signals}
    # Process only the latest frozen BTC Sunday observation. This deliberately
    # avoids walking older Sundays to create a historical-looking paper sample.
    candidates = [r for r in btc_rows
                  if r["observation_date_utc"] not in signal_dates
                  and dt.datetime.fromisoformat(r["captured_at_utc"]).astimezone(
                      dt.timezone.utc) >= PAPER_START_AFTER_UTC
                  and dt.date.fromisoformat(
                      r["signal_input_last_prior_close_date_utc"]).weekday() == 6]
    new_signal = None
    if candidates:
        latest = max(candidates, key=lambda r: r["observation_date_utc"])
        new_signal = build_paper_signal(latest, model_sha256=model_sha256)
        signal_text, added = _append(
            signal_text, new_signal, SIGNAL_COLUMNS_PAPER,
            "btc_observation_date_utc")
        if not added:
            new_signal = None
    signals = _read_rows(signal_text, SIGNAL_COLUMNS_PAPER,
                         date_key="btc_observation_date_utc")
    execution_dates = {r["btc_observation_date_utc"] for r in executions}
    added_execution = False
    # Link only exact next-weekday matches. If the quote is missing because of
    # a holiday or missed capture, leave the signal unmatched forever.
    for signal in signals:
        date_key = signal["btc_observation_date_utc"]
        if date_key in execution_dates:
            continue
        expected = signal["expected_next_asx_weekday_sydney"]
        match = next((r for r in asx_rows
                      if r["market_session_date_sydney"] == expected), None)
        if match is None:
            continue
        record = build_asx_observation(signal, match)
        execution_text, added_execution = _append(
            execution_text, record, EXECUTION_COLUMNS,
            "btc_observation_date_utc")
        if added_execution:
            execution_dates.add(date_key)
    status = {
        "report_type": "prospective_research_paper_tape_integrity_not_edge",
        "paper_start_after_utc": PAPER_START_AFTER_UTC.isoformat(),
        "signal_rows": len(_read_rows(signal_text, SIGNAL_COLUMNS_PAPER,
                                      date_key="btc_observation_date_utc")),
        "asx_observation_rows": len(_read_rows(execution_text, EXECUTION_COLUMNS,
                                               date_key="btc_observation_date_utc")),
        "latest_signal_date_utc": (
            signals[-1]["signal_date_utc"] if signals else None),
        "latest_linked_asx_session_sydney": (
            executions[-1]["observed_asx_session_date_sydney"]
            if executions else None),
        "all_asx_prices_indicative_not_broker_fills": True,
        "can_claim_trading_edge": False,
        "eligible_for_live_promotion": False,
    }
    return signal_text, execution_text, status


def run_once(*, data_dir: Path = DATA, artifact: Path = ARTIFACT) -> dict:
    data_dir = Path(data_dir)
    signal_path = data_dir / SIGNAL_TAPE.name
    execution_path = data_dir / EXECUTION_TAPE.name
    btc_text = _load(data_dir / BTC_TAPE.name)
    asx_text = _load(data_dir / IBIT_TAPE.name)
    signal_text = _load(signal_path)
    execution_text = _load(execution_path)
    code_hash = _sha_file(Path(__file__).resolve())
    signal_text, execution_text, status = process_tapes(
        btc_text, asx_text, signal_text, execution_text,
        model_sha256=code_hash)
    data_dir.mkdir(parents=True, exist_ok=True)
    if signal_text != _load(signal_path):
        signal_path.write_text(signal_text)
    if execution_text != _load(execution_path):
        execution_path.write_text(execution_text)
    artifact = Path(artifact)
    artifact.parent.mkdir(parents=True, exist_ok=True)
    artifact.write_text(json.dumps(status, indent=2, sort_keys=True) + "\n")
    print(json.dumps(status, sort_keys=True))
    return status


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--data-dir", type=Path, default=DATA)
    parser.add_argument("--artifact", type=Path, default=ARTIFACT)
    args = parser.parse_args(argv)
    run_once(data_dir=args.data_dir, artifact=args.artifact)


if __name__ == "__main__":
    main()
