"""Verified server-side persistence for the shared BTC portfolio."""

from __future__ import annotations

import datetime as dt
import json
import os
import sqlite3
from pathlib import Path
from typing import Any

DEFAULT_DB_PATH = "/data/btc_dynamic_dca.sqlite3"

def portfolio_db_path() -> Path:
    return Path(os.getenv("BTC_PORTFOLIO_DB_PATH", DEFAULT_DB_PATH)).expanduser()

def _connect(db_path: Path | None = None) -> sqlite3.Connection:
    path = Path(db_path) if db_path is not None else portfolio_db_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(path), timeout=10)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA busy_timeout=10000")
    conn.execute("""CREATE TABLE IF NOT EXISTS portfolio_state (
        portfolio_key TEXT PRIMARY KEY, payload_json TEXT NOT NULL, updated_at_utc TEXT NOT NULL)""")
    conn.execute("""CREATE TABLE IF NOT EXISTS portfolio_backups (
        id INTEGER PRIMARY KEY AUTOINCREMENT, portfolio_key TEXT NOT NULL,
        payload_json TEXT NOT NULL, saved_at_utc TEXT NOT NULL)""")
    conn.commit()
    return conn

def _normalise(portfolio: Any) -> dict:
    if not isinstance(portfolio, dict):
        raise ValueError("Portfolio must be a dictionary.")
    if not isinstance(portfolio.get("rows", []), list):
        raise ValueError("Portfolio rows must be a list.")
    return json.loads(json.dumps(portfolio, default=str))

def load_portfolio(db_path: Path | None = None) -> tuple[dict, str | None]:
    try:
        with _connect(db_path) as conn:
            row = conn.execute(
                "SELECT payload_json FROM portfolio_state WHERE portfolio_key = ?", ("shared",)
            ).fetchone()
        if row is None:
            return {}, None
        return _normalise(json.loads(row[0])), None
    except Exception as exc:
        return {}, f"{type(exc).__name__}: {exc}"

def save_portfolio(portfolio: dict, db_path: Path | None = None) -> tuple[bool, str | None]:
    try:
        value = _normalise(portfolio)
        payload = json.dumps(value, sort_keys=True, separators=(",", ":"))
        saved_at = dt.datetime.now(dt.timezone.utc).isoformat()
        with _connect(db_path) as conn:
            previous = conn.execute(
                "SELECT payload_json FROM portfolio_state WHERE portfolio_key = ?", ("shared",)
            ).fetchone()
            if previous is not None and previous[0] != payload:
                conn.execute(
                    "INSERT INTO portfolio_backups (portfolio_key, payload_json, saved_at_utc) VALUES (?, ?, ?)",
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
        verified, error = load_portfolio(db_path)
        if error:
            return False, error
        if verified != value:
            return False, "Database verification failed: saved value did not match."
        return True, None
    except Exception as exc:
        return False, f"{type(exc).__name__}: {exc}"
