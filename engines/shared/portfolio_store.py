"""Persistent storage for the shared BTC portfolio.

Google Sheets is the default backend for Streamlit Cloud. SQLite remains available
for tests and optional local/NAS use.
"""

from __future__ import annotations

import datetime as dt
import json
import os
import sqlite3
from pathlib import Path
from typing import Any

DEFAULT_DB_PATH = "/data/btc_dynamic_dca.sqlite3"
DEFAULT_SHEET_ID = "1YcZBZYIUh886v475RSIrQ-WyKuJVbPyuPPb0_TM62ng"
STATE_WORKSHEET = "portfolio_state"
GOOGLE_SCOPES = (
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive.file",
)


def portfolio_db_path() -> Path:
    return Path(os.getenv("BTC_PORTFOLIO_DB_PATH", DEFAULT_DB_PATH)).expanduser()


def _normalise(portfolio: Any) -> dict:
    if not isinstance(portfolio, dict):
        raise ValueError("Portfolio must be a dictionary.")
    if not isinstance(portfolio.get("rows", []), list):
        raise ValueError("Portfolio rows must be a list.")
    return json.loads(json.dumps(portfolio, default=str))


def _google_settings() -> tuple[str, dict[str, Any]]:
    """Read Google credentials from Streamlit secrets or environment variables."""
    sheet_id = os.getenv("BTC_PORTFOLIO_SHEET_ID", DEFAULT_SHEET_ID)
    raw_credentials = os.getenv("GOOGLE_SERVICE_ACCOUNT_JSON", "").strip()

    if raw_credentials:
        credentials = json.loads(raw_credentials)
    else:
        try:
            import streamlit as st

            sheet_id = str(st.secrets.get("BTC_PORTFOLIO_SHEET_ID", sheet_id))
            secret_json = str(st.secrets.get("GOOGLE_SERVICE_ACCOUNT_JSON", "")).strip()
            credentials = (
                json.loads(secret_json)
                if secret_json
                else dict(st.secrets["google_service_account"])
            )
        except Exception as exc:
            raise RuntimeError(
                "Google Sheets is not configured. Add GOOGLE_SERVICE_ACCOUNT_JSON "
                "to the Streamlit app secrets."
            ) from exc

    if not credentials.get("client_email") or not credentials.get("private_key"):
        raise RuntimeError("Google service-account credentials are incomplete.")
    return sheet_id, credentials


def _google_worksheet():
    import gspread
    from google.oauth2.service_account import Credentials

    sheet_id, info = _google_settings()
    credentials = Credentials.from_service_account_info(info, scopes=GOOGLE_SCOPES)
    spreadsheet = gspread.authorize(credentials).open_by_key(sheet_id)
    try:
        worksheet = spreadsheet.worksheet(STATE_WORKSHEET)
    except gspread.WorksheetNotFound:
        worksheet = spreadsheet.add_worksheet(title=STATE_WORKSHEET, rows=10, cols=3)
        worksheet.update(
            [["portfolio_key", "payload_json", "updated_at_utc"]],
            "A1:C1",
        )
    return worksheet


def _use_sqlite(db_path: Path | None) -> bool:
    """An explicit path is used by tests; env setting supports optional NAS use."""
    return db_path is not None or os.getenv("BTC_PORTFOLIO_BACKEND", "").lower() == "sqlite"


def _connect(db_path: Path | None = None) -> sqlite3.Connection:
    path = Path(db_path) if db_path is not None else portfolio_db_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(path), timeout=10)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA busy_timeout=10000")
    conn.execute(
        """CREATE TABLE IF NOT EXISTS portfolio_state (
        portfolio_key TEXT PRIMARY KEY, payload_json TEXT NOT NULL, updated_at_utc TEXT NOT NULL)"""
    )
    conn.execute(
        """CREATE TABLE IF NOT EXISTS portfolio_backups (
        id INTEGER PRIMARY KEY AUTOINCREMENT, portfolio_key TEXT NOT NULL,
        payload_json TEXT NOT NULL, saved_at_utc TEXT NOT NULL)"""
    )
    conn.commit()
    return conn


def _load_sqlite(db_path: Path | None = None) -> dict:
    with _connect(db_path) as conn:
        row = conn.execute(
            "SELECT payload_json FROM portfolio_state WHERE portfolio_key = ?", ("shared",)
        ).fetchone()
    return {} if row is None else _normalise(json.loads(row[0]))


def _save_sqlite(portfolio: dict, db_path: Path | None = None) -> None:
    value = _normalise(portfolio)
    payload = json.dumps(value, sort_keys=True, separators=(",", ":"))
    saved_at = dt.datetime.now(dt.timezone.utc).isoformat()
    with _connect(db_path) as conn:
        previous = conn.execute(
            "SELECT payload_json FROM portfolio_state WHERE portfolio_key = ?", ("shared",)
        ).fetchone()
        if previous is not None and previous[0] != payload:
            conn.execute(
                "INSERT INTO portfolio_backups (portfolio_key, payload_json, saved_at_utc) "
                "VALUES (?, ?, ?)",
                ("shared", previous[0], saved_at),
            )
        conn.execute(
            """INSERT INTO portfolio_state (portfolio_key, payload_json, updated_at_utc)
            VALUES (?, ?, ?)
            ON CONFLICT(portfolio_key) DO UPDATE SET
                payload_json = excluded.payload_json,
                updated_at_utc = excluded.updated_at_utc""",
            ("shared", payload, saved_at),
        )
        conn.execute(
            """DELETE FROM portfolio_backups
            WHERE portfolio_key = ? AND id NOT IN (
                SELECT id FROM portfolio_backups
                WHERE portfolio_key = ? ORDER BY id DESC LIMIT 20)""",
            ("shared", "shared"),
        )
        conn.commit()


def _load_google() -> dict:
    worksheet = _google_worksheet()
    records = worksheet.get_all_records()
    for record in records:
        if str(record.get("portfolio_key", "")).strip() == "shared":
            payload = str(record.get("payload_json", "")).strip()
            return {} if not payload else _normalise(json.loads(payload))
    return {}


def _save_google(portfolio: dict) -> None:
    value = _normalise(portfolio)
    payload = json.dumps(value, sort_keys=True, separators=(",", ":"))
    saved_at = dt.datetime.now(dt.timezone.utc).isoformat()
    worksheet = _google_worksheet()
    records = worksheet.get_all_records()

    row_number = None
    for index, record in enumerate(records, start=2):
        if str(record.get("portfolio_key", "")).strip() == "shared":
            row_number = index
            break

    values = [["shared", payload, saved_at]]
    if row_number is None:
        worksheet.append_row(values[0], value_input_option="RAW")
    else:
        worksheet.update(values, f"A{row_number}:C{row_number}", value_input_option="RAW")


def load_portfolio(db_path: Path | None = None) -> tuple[dict, str | None]:
    try:
        value = _load_sqlite(db_path) if _use_sqlite(db_path) else _load_google()
        return value, None
    except Exception as exc:
        return {}, f"{type(exc).__name__}: {exc}"


def save_portfolio(portfolio: dict, db_path: Path | None = None) -> tuple[bool, str | None]:
    try:
        value = _normalise(portfolio)
        if _use_sqlite(db_path):
            _save_sqlite(value, db_path)
        else:
            _save_google(value)

        verified, error = load_portfolio(db_path)
        if error:
            return False, error
        if verified != value:
            return False, "Storage verification failed: saved value did not match."
        return True, None
    except Exception as exc:
        return False, f"{type(exc).__name__}: {exc}"
