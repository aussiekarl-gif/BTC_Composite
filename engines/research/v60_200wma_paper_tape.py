"""V6.0 prospective 200WMA threshold-sensitivity paper tape.

Forward-only observations for the 20/25/30 and 10/15/20 measured ladders.
No personal portfolio, live recommendation, broker order, or ntfy output.
"""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import math
from pathlib import Path
from zoneinfo import ZoneInfo

from engines.research.v60_200wma_policy import (
    THRESHOLD_SETS, allocation_for_discount,
)

GENESIS = "0" * 64
BTC_COLUMNS = (
    "observation_date_utc", "captured_at_utc",
    "signal_input_last_prior_close_date_utc", "btc_usd_observed_close",
    "prior_btc_usd_close", "prior_200wma_usd", "prior_close_div_200wma",
    "fx_observed_prior_aud_per_usd", "fx_prior_date_utc",
    "verified_halving_date", "days_after_halving", "signal",
    "buy_pct_of_remaining_available_cash", "sell_pct_of_current_holdings",
    "trailing_90day_drawdown_prior_pct", "prior_50dma_declining",
    "lagged_30d_annualised_volatility_pct", "market_data_provider",
    "source_crosscheck_max_diff_pct", "model_name", "model_code_sha256",
    "point_in_time_onchain_risk_status", "trade_executable",
    "prior_row_hash", "row_hash",
)
ASX_COLUMNS = (
    "market_session_date_sydney", "captured_at_utc",
    "provider_daily_candle_timestamp_utc", "symbol", "currency",
    "reported_close_aud", "daily_low_aud", "daily_high_aud",
    "daily_volume", "provider", "single_provider_unverified_execution",
    "is_confirmed_broker_fill", "prior_row_hash", "row_hash",
)


def _canonical(row: dict, columns: tuple[str, ...]) -> str:
    obj = {c: str(row[c]) for c in columns if c != "row_hash"}
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def _signature(row: dict, columns: tuple[str, ...]) -> str:
    return hashlib.sha256(_canonical(row, columns).encode("utf-8")).hexdigest()


def _clean_input(row: dict, columns: tuple[str, ...]) -> dict:
    if set(row) != set(columns) - {"prior_row_hash", "row_hash"}:
        raise ValueError("Unexpected immutable V6.0 tape schema")
    return {k: str(row[k]) for k in columns if k not in ("prior_row_hash", "row_hash")}


def _read_rows(content: str, columns: tuple[str, ...], *, date_key: str | None = None) -> list[dict]:
    import csv
    import io
    if not content:
        return []
    reader = csv.DictReader(io.StringIO(content))
    if reader.fieldnames != list(columns):
        raise ValueError("Historical input tape columns changed; refuse migration")
    rows = list(reader)
    previous = GENESIS
    seen = set()
    for row in rows:
        if None in row or any(v is None for v in row.values()):
            raise ValueError("Corrupted immutable tape columns")
        if row["prior_row_hash"] != previous or row["row_hash"] != _signature(row, columns):
            raise ValueError("Modified, reordered or corrupted input tape")
        if date_key:
            key = row[date_key]
            if key in seen:
                raise ValueError("Duplicate immutable tape observation date")
            seen.add(key)
        previous = row["row_hash"]
    return rows


def _dump_rows(rows: list[dict], columns: tuple[str, ...]) -> str:
    import csv
    import io
    stream = io.StringIO(newline="")
    writer = csv.DictWriter(stream, fieldnames=list(columns), lineterminator="\n")
    writer.writeheader()
    writer.writerows(rows)
    return stream.getvalue()

ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "data" / "research_forward_validation"
BTC_TAPE = DATA / "cycle_market_signals.csv"
ASX_TAPE = DATA / "asx_ibit_closes_forward.csv"
SIGNAL_TAPE = DATA / "v60_200wma_paper_signals.csv"
EXECUTION_TAPE = DATA / "v60_200wma_paper_asx_observations.csv"
STATUS_FILE = DATA / "v60_200wma_paper_status.json"
SYDNEY = ZoneInfo("Australia/Sydney")
PAPER_START_AFTER_UTC = dt.datetime.fromisoformat("2026-11-19T09:05:02+00:00")
MODEL_LABEL = "v60_200wma_measured_threshold_sensitivity_paper_v1"
PROTECTED_CASH_VARIANTS = (0.0, 30.0, 50.0)
CUMULATIVE_CAP_VARIANTS = (40.0, 50.0, 60.0)

SIGNAL_COLUMNS = (
    "btc_observation_date_utc", "btc_captured_at_utc",
    "signal_date_utc", "expected_next_asx_session_sydney",
    "btc_usd_sunday_close", "prior_200wma_usd",
    "ratio_to_200wma", "discount_below_200wma_pct",
    "baseline_buy_pct_available_cash",
    "measured_20_25_30_buy_pct_deployable_cash",
    "measured_10_15_20_buy_pct_deployable_cash",
    "protected_cash_floor_variants_pct_initial_cash",
    "cumulative_spend_cap_variants_pct_initial_cash",
    "weekly_hard_cap_pct_original_capital",
    "model_name", "model_code_sha256", "source_btc_row_hash",
    "prior_row_hash", "row_hash",
)
EXECUTION_COLUMNS = (
    "btc_observation_date_utc", "expected_asx_session_date_sydney",
    "observed_asx_session_date_sydney", "captured_at_utc",
    "reported_close_aud", "daily_low_aud", "daily_high_aud",
    "daily_volume", "provider", "indicative_units_per_aud_1000",
    "is_confirmed_broker_fill", "source_btc_signal_row_hash",
    "source_asx_row_hash", "prior_row_hash", "row_hash",
)

# Full-closure days from the reviewed official ASX 2026/2027 calendar.
# Early-close dates remain valid trading sessions.
ASX_FULL_CLOSURES = {
    2026: frozenset({
        "2026-01-01", "2026-01-26", "2026-04-03", "2026-04-06",
        "2026-06-08", "2026-12-25", "2026-12-28",
    }),
    2027: frozenset({
        "2027-01-01", "2027-01-26", "2027-03-26", "2027-03-29",
        "2027-06-14", "2027-12-27", "2027-12-28",
    }),
}
ASX_CALENDAR_SOURCE = (
    "ASX Trade official 2026/2027 calendar; "
    "https://www.asx.com.au/markets/market-resources/trading-hours-calendar/cash-market-trading-hours/trading-calendar"
)


def _utc(value: str) -> dt.datetime:
    stamp = dt.datetime.fromisoformat(value)
    if stamp.tzinfo is None:
        raise ValueError("Capture timestamp must be timezone-aware")
    return stamp.astimezone(dt.timezone.utc)


def _next_asx_session(day: dt.date) -> dt.date:
    candidate = day + dt.timedelta(days=1)
    while True:
        if candidate.year not in ASX_FULL_CLOSURES:
            raise ValueError(
                f"No reviewed ASX calendar for {candidate.year}; fail closed"
            )
        if (candidate.weekday() < 5
                and candidate.isoformat() not in ASX_FULL_CLOSURES[candidate.year]):
            return candidate
        candidate += dt.timedelta(days=1)


def _was_captured_prospectively(row: dict) -> bool:
    try:
        captured = _utc(row["captured_at_utc"])
        observation = dt.date.fromisoformat(row["observation_date_utc"])
    except (KeyError, TypeError, ValueError):
        return False
    return (captured.date() - observation).days == 1


def _code_hash() -> str:
    here = Path(__file__).resolve().parent
    paths = (
        here / "v60_200wma_policy.py",
        here / "v60_200wma_backtest.py",
        here / "v60_200wma_paper_tape.py",
    )
    digest = hashlib.sha256()
    for path in paths:
        digest.update(path.name.encode("utf-8"))
        digest.update(path.read_bytes())
    return digest.hexdigest()


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
            raise ValueError("V6.0 prospective tape backfill forbidden")
    clean["prior_row_hash"] = rows[-1]["row_hash"] if rows else GENESIS
    clean["row_hash"] = _signature(clean, columns)
    rows.append(clean)
    return _dump_rows(rows, columns), True


def build_paper_signal(btc_row: dict, *, model_sha256: str,
                       paper_start_after_utc=PAPER_START_AFTER_UTC) -> dict:
    observation = dt.date.fromisoformat(btc_row["observation_date_utc"])
    signal_date = dt.date.fromisoformat(
        btc_row["signal_input_last_prior_close_date_utc"]
    )
    captured = _utc(btc_row["captured_at_utc"])
    if captured < paper_start_after_utc:
        raise ValueError("Pre-launch observation cannot enter V6.0 paper tape")
    if signal_date.weekday() != 6:
        raise ValueError("Only a completed Sunday BTC close is eligible")
    if not _was_captured_prospectively(btc_row):
        raise ValueError("BTC source row was not captured prospectively")
    if captured.date() <= signal_date:
        raise ValueError("Sunday close must be captured after signal date")
    close = float(btc_row["prior_btc_usd_close"])
    prior_wma = float(btc_row["prior_200wma_usd"])
    crosscheck = float(btc_row["source_crosscheck_max_diff_pct"])
    if not math.isfinite(crosscheck) or crosscheck > 1.0:
        raise ValueError("BTC source cross-check exceeds 1%; refuse paper observation")
    if not btc_row["market_data_provider"] or len(btc_row["row_hash"]) != 64:
        raise ValueError("BTC source provenance or row hash missing")
    ratio = float(btc_row["prior_close_div_200wma"])
    if not all(math.isfinite(x) and x > 0 for x in (close, prior_wma, ratio)):
        raise ValueError("Invalid Sunday close or prior 200WMA")
    if abs(close / prior_wma - ratio) > 0.000001:
        raise ValueError("Frozen BTC/200WMA ratio does not reconcile")
    discount = max(0.0, (1.0 - ratio) * 100.0)
    sydney_capture_date = captured.astimezone(SYDNEY).date()
    expected_asx = _next_asx_session(sydney_capture_date)
    code_sha = str(model_sha256)
    if len(code_sha) != 64 or any(c not in "0123456789abcdef" for c in code_sha):
        raise ValueError("V6.0 model fingerprint must be a SHA256 hex digest")
    return {
        "btc_observation_date_utc": observation.isoformat(),
        "btc_captured_at_utc": captured.isoformat(),
        "signal_date_utc": signal_date.isoformat(),
        "expected_next_asx_session_sydney": expected_asx.isoformat(),
        "btc_usd_sunday_close": f"{close:.6f}",
        "prior_200wma_usd": f"{prior_wma:.6f}",
        "ratio_to_200wma": f"{ratio:.8f}",
        "discount_below_200wma_pct": f"{discount:.6f}",
        "baseline_buy_pct_available_cash": "2.500000",
        "measured_20_25_30_buy_pct_deployable_cash": (
            f"{allocation_for_discount(ratio, candidate='measured', thresholds=THRESHOLD_SETS['20_25_30']):.6f}"
        ),
        "measured_10_15_20_buy_pct_deployable_cash": (
            f"{allocation_for_discount(ratio, candidate='measured', thresholds=THRESHOLD_SETS['10_15_20']):.6f}"
        ),
        "protected_cash_floor_variants_pct_initial_cash": ";".join(
            f"{x:.6f}" for x in PROTECTED_CASH_VARIANTS
        ),
        "cumulative_spend_cap_variants_pct_initial_cash": ";".join(
            f"{x:.6f}" for x in CUMULATIVE_CAP_VARIANTS
        ),
        "weekly_hard_cap_pct_original_capital": "5.000000",
        "model_name": MODEL_LABEL,
        "model_code_sha256": code_sha,
        "source_btc_row_hash": btc_row["row_hash"],
    }


def build_asx_observation(signal_row: dict, asx_row: dict) -> dict:
    expected = dt.date.fromisoformat(signal_row["expected_next_asx_session_sydney"])
    observed = dt.date.fromisoformat(asx_row["market_session_date_sydney"])
    if observed != expected:
        raise ValueError("ASX quote is not the exact expected session; no date shifting")
    captured = _utc(asx_row["captured_at_utc"])
    local = captured.astimezone(SYDNEY)
    if local.date() != observed or local.time() < dt.time(17, 0):
        raise ValueError("ASX close must be captured after 17:00 Sydney on exact session")
    if (asx_row["symbol"] != "ASX:IBIT" or asx_row["currency"] != "AUD"
            or asx_row["is_confirmed_broker_fill"] != "False"
            or asx_row["single_provider_unverified_execution"] != "True"
            or asx_row["provider"] != "Yahoo_Finance_IBIT.AX_daily_candle_indicative"):
        raise ValueError("Refuse non-AUD ASX:IBIT, wrong provider or fabricated broker fill")
    close = float(asx_row["reported_close_aud"])
    low, high = float(asx_row["daily_low_aud"]), float(asx_row["daily_high_aud"])
    volume = int(asx_row["daily_volume"])
    if (not all(math.isfinite(x) and x > 0 for x in (close, low, high))
            or high < low or not low - 0.02 <= close <= high + 0.02 or volume < 0
            or len(asx_row["row_hash"]) != 64):
        raise ValueError("Invalid indicative ASX:IBIT close or source hash")
    return {
        "btc_observation_date_utc": signal_row["btc_observation_date_utc"],
        "expected_asx_session_date_sydney": expected.isoformat(),
        "observed_asx_session_date_sydney": observed.isoformat(),
        "captured_at_utc": captured.isoformat(),
        "reported_close_aud": f"{close:.6f}",
        "daily_low_aud": asx_row["daily_low_aud"],
        "daily_high_aud": asx_row["daily_high_aud"],
        "daily_volume": asx_row["daily_volume"],
        "provider": asx_row["provider"],
        "indicative_units_per_aud_1000": f"{1000.0 / close:.8f}",
        "is_confirmed_broker_fill": "False",
        "source_btc_signal_row_hash": signal_row["row_hash"],
        "source_asx_row_hash": asx_row["row_hash"],
    }


def process_tapes(btc_text: str, asx_text: str, signal_text: str,
                  execution_text: str, *, model_sha256: str,
                  paper_start_after_utc=PAPER_START_AFTER_UTC) -> tuple[str, str, dict]:
    btc_rows = _read_rows(btc_text, BTC_COLUMNS, date_key="observation_date_utc")
    asx_rows = _read_rows(asx_text, ASX_COLUMNS, date_key="market_session_date_sydney")
    signals = _read_rows(signal_text, SIGNAL_COLUMNS, date_key="btc_observation_date_utc")
    executions = _read_rows(execution_text, EXECUTION_COLUMNS, date_key="btc_observation_date_utc")
    existing_dates = {r["btc_observation_date_utc"] for r in signals}
    candidates = [
        row for row in btc_rows
        if row["observation_date_utc"] not in existing_dates
        and _utc(row["captured_at_utc"]) >= paper_start_after_utc
        and dt.date.fromisoformat(row["signal_input_last_prior_close_date_utc"]).weekday() == 6
    ]
    added_signal = False
    if candidates:
        # Only the latest eligible Sunday observation; never reconstruct older weeks.
        latest = max(candidates, key=lambda r: r["observation_date_utc"])
        new = build_paper_signal(
            latest, model_sha256=model_sha256,
            paper_start_after_utc=paper_start_after_utc,
        )
        signal_text, added_signal = _append(
            signal_text, new, SIGNAL_COLUMNS, "btc_observation_date_utc"
        )
    signals = _read_rows(signal_text, SIGNAL_COLUMNS, date_key="btc_observation_date_utc")
    execution_dates = {r["btc_observation_date_utc"] for r in executions}
    added_execution_count = 0
    for signal in signals:
        key = signal["btc_observation_date_utc"]
        if key in execution_dates:
            continue
        expected = signal["expected_next_asx_session_sydney"]
        match = next((r for r in asx_rows if r["market_session_date_sydney"] == expected), None)
        if match is None:
            continue
        record = build_asx_observation(signal, match)
        execution_text, added = _append(
            execution_text, record, EXECUTION_COLUMNS, "btc_observation_date_utc"
        )
        if added:
            execution_dates.add(key)
            added_execution_count += 1
    signals = _read_rows(signal_text, SIGNAL_COLUMNS, date_key="btc_observation_date_utc")
    executions = _read_rows(execution_text, EXECUTION_COLUMNS, date_key="btc_observation_date_utc")
    status = {
        "status": "captured" if added_signal or added_execution_count else "no_new_prospective_observation",
        "paper_start_after_utc": paper_start_after_utc.isoformat(),
        "first_eligible_sunday_close_utc": "2026-11-22",
        "signal_rows": len(signals),
        "asx_observation_rows": len(executions),
        "unmatched_signal_rows": len(signals) - len(executions),
        "latest_signal_date_utc": signals[-1]["signal_date_utc"] if signals else None,
        "latest_linked_asx_session_sydney": executions[-1]["observed_asx_session_date_sydney"] if executions else None,
        "asx_prices_are_indicative_not_broker_fills": True,
        "trade_executable": False,
        "can_claim_trading_edge": False,
        "eligible_for_live_promotion": False,
        "asx_calendar_source": ASX_CALENDAR_SOURCE,
    }
    return signal_text, execution_text, status


def run_once(*, btc_tape=BTC_TAPE, asx_tape=ASX_TAPE,
             signal_tape=SIGNAL_TAPE, execution_tape=EXECUTION_TAPE,
             status_file=STATUS_FILE) -> dict:
    btc_text = Path(btc_tape).read_text() if Path(btc_tape).exists() else ""
    asx_text = Path(asx_tape).read_text() if Path(asx_tape).exists() else ""
    signal_text = Path(signal_tape).read_text() if Path(signal_tape).exists() else ""
    execution_text = Path(execution_tape).read_text() if Path(execution_tape).exists() else ""
    code_sha = _code_hash()
    new_signal, new_execution, status = process_tapes(
        btc_text, asx_text, signal_text, execution_text, model_sha256=code_sha
    )
    Path(signal_tape).parent.mkdir(parents=True, exist_ok=True)
    Path(signal_tape).write_text(new_signal, encoding="utf-8")
    Path(execution_tape).write_text(new_execution, encoding="utf-8")
    Path(status_file).write_text(json.dumps(status, indent=2), encoding="utf-8")
    return status


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--btc-tape", type=Path, default=BTC_TAPE)
    parser.add_argument("--asx-tape", type=Path, default=ASX_TAPE)
    parser.add_argument("--signal-tape", type=Path, default=SIGNAL_TAPE)
    parser.add_argument("--execution-tape", type=Path, default=EXECUTION_TAPE)
    parser.add_argument("--status-file", type=Path, default=STATUS_FILE)
    args = parser.parse_args(argv)
    print(json.dumps(run_once(
        btc_tape=args.btc_tape, asx_tape=args.asx_tape,
        signal_tape=args.signal_tape, execution_tape=args.execution_tape,
        status_file=args.status_file,
    ), sort_keys=True))


if __name__ == "__main__":
    main()
