"""Persist independent V5.8.2 / V5.9 DCA Today dates across Streamlit restarts.

Target dates have their OWN keys in the existing Google Sheets portfolio_state
worksheet (or same SQLite table in local/tests). They NEVER write or merge
the 'shared' key containing BTC/ASX:IBIT purchase and sale transactions.
No default dates are stored unless the user selects one or an existing
browser date is migrated. The read-write contract mirrors portfolio_store
and returns explicit errors so a failed save is not falsely reported as
persistent. This module does NOT alter DCA allocation or market signals.
"""
from __future__ import annotations

import datetime as dt
import json
import sqlite3
from pathlib import Path

from engines.shared import portfolio_store as _store

_VALID_MODELS = {
    "production": "setting:production_dca_today_target_date",
    "research": "setting:research_strategy_review_target_date",
}


def _key(model: str) -> str:
    if model not in _VALID_MODELS:
        raise ValueError("Unknown DCA model settings key")
    return _VALID_MODELS[model]


def _parse_record(payload: str) -> str | None:
    if not payload:
        return None
    obj = json.loads(payload)
    if not isinstance(obj, dict) or not isinstance(obj.get("target_date"), str):
        raise ValueError("Invalid saved DCA target date record")
    text = obj["target_date"]
    parsed = dt.date.fromisoformat(text)
    if text != parsed.isoformat():
        raise ValueError("DCA saved target date must be YYYY-MM-DD")
    return text


def load_dca_target_date(
    model: str, db_path: Path | None = None
) -> tuple[str | None, str | None]:
    """Load date from distinct settings row, never from trading portfolio."""
    try:
        key = _key(model)
        if _store._use_sqlite(db_path):
            with _store._connect(db_path) as conn:
                row = conn.execute(
                    "SELECT payload_json FROM portfolio_state "
                    "WHERE portfolio_key = ?", (key,)
                ).fetchone()
            payload = None if row is None else row[0]
        else:
            records = _store._google_worksheet().get_all_records()
            record = next(
                (r for r in records if str(r.get("portfolio_key", "")).strip()==key),
                None
            )
            payload = str(record.get("payload_json", "")).strip() if record else None
        return _parse_record(payload), None
    except Exception as exc:
        return None, f"{type(exc).__name__}: {exc}"


def save_dca_target_date(
    model: str, target_date: dt.date | str, db_path: Path | None = None
) -> tuple[bool, str | None]:
    """Save ONLY a DCA preference; preserve all real portfolio transactions."""
    try:
        key = _key(model)
        if isinstance(target_date, dt.datetime):
            raise ValueError("Expected an unambiguous date, not a datetime")
        date = (dt.date.fromisoformat(target_date)
                if isinstance(target_date, str) else target_date)
        if not isinstance(date, dt.date):
            raise ValueError("Invalid DCA target date")
        text = date.isoformat()
        data = json.dumps({"target_date":text},sort_keys=True,separators=(",",":"))
        now = dt.datetime.now(dt.timezone.utc).isoformat()
        if _store._use_sqlite(db_path):
            with _store._connect(db_path) as conn:
                conn.execute(
                    "INSERT INTO portfolio_state "
                    "(portfolio_key,payload_json,updated_at_utc) "
                    "VALUES (?,?,?) ON CONFLICT(portfolio_key) "
                    "DO UPDATE SET payload_json=excluded.payload_json, "
                    "updated_at_utc=excluded.updated_at_utc",
                    (key,data,now))
                conn.commit()
        else:
            worksheet = _store._google_worksheet()
            records = worksheet.get_all_records()
            index = next(
                (i for i,r in enumerate(records,start=2)
                 if str(r.get("portfolio_key","")).strip()==key),
                None
            )
            if index is None:
                worksheet.append_row([key,data,now],value_input_option="RAW")
            else:
                worksheet.update(
                    [[key,data,now]],f"A{index}:C{index}",
                    value_input_option="RAW")
        reread,error=load_dca_target_date(model,db_path)
        if error:
            return False,error
        if reread!=text:
            return False,"Saved date verification failed."
        return True,None
    except Exception as exc:
        return False,f"{type(exc).__name__}: {exc}"


def choose_target_date(
    *,server_date: str | None,browser_date: str | None,
    default_date: dt.date,min_date: dt.date
) -> tuple[dt.date, bool]:
    """Prefer durable date, else migrate browser; never silently jump +3y.

    Return (display_date, existing_user_choice): the caller should NOT
    persist a brand-new, generated default until changed by the user.
    If a previously selected date is past the minimum, retain intent
    by clamping to the minimum rather than jumping back three years.
    """
    if min_date>default_date:
        raise ValueError("Invalid DCA fallback date range")
    for text in (server_date,browser_date):
        if not text:
            continue
        try:
            date=dt.date.fromisoformat(text)
        except (TypeError,ValueError):
            continue
        return max(date,min_date),True
    return default_date,False
