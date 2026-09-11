"""CoinGlass specialist-history staging collector.

Research-only. Fetches selected specialist BTC datasets already entitlement-verified,
normalizes them to daily date-indexed columns, and can persist them to a NON-authoritative
staging CSV in btc-audit-data. It never changes Production or the authoritative audit master.
"""
from __future__ import annotations

import base64
import os
from dataclasses import dataclass

import pandas as pd
import requests

from engines.audit.coinglass_staging_schema_probe import find_metric_records, safe_shape_summary

COINGLASS_BASE = "https://open-api-v4.coinglass.com"
STAGING_PATH = "staging/coinglass_specialist.csv"

@dataclass(frozen=True)
class Spec:
    label: str
    path: str
    value_keys: tuple[str, ...]
    column: str

SPECS = [
    Spec("STH SOPR", "/api/index/bitcoin-sth-sopr", ("sth_sopr", "sthSopr", "sopr"), "cg__sth_sopr"),
    Spec("LTH SOPR", "/api/index/bitcoin-lth-sopr", ("lth_sopr", "lthSopr", "sopr"), "cg__lth_sopr"),
    Spec("STH Realized Price", "/api/index/bitcoin-sth-realized-price", ("sth_realized_price", "sthRealizedPrice", "realized_price"), "cg__sth_realized_price"),
    Spec("LTH Realized Price", "/api/index/bitcoin-lth-realized-price", ("lth_realized_price", "lthRealizedPrice", "realized_price"), "cg__lth_realized_price"),
    Spec("RHODL Ratio", "/api/index/bitcoin-rhodl-ratio", ("rhodl_ratio", "rhodlRatio"), "cg__rhodl_ratio"),
    Spec("STH Supply", "/api/index/bitcoin-short-term-holder-supply", ("short_term_holder_supply", "shortTermHolderSupply", "sth_supply"), "cg__sth_supply"),
    Spec("LTH Supply", "/api/index/bitcoin-long-term-holder-supply", ("long_term_holder_supply", "longTermHolderSupply", "lth_supply"), "cg__lth_supply"),
    Spec("Reserve Risk", "/api/index/bitcoin-reserve-risk", ("reserve_risk_index", "reserveRiskIndex", "reserve_risk"), "cg__reserve_risk"),
]

def _secret(st, *names: str) -> str:
    for name in names:
        try:
            value = st.secrets.get(name, "")
        except Exception:
            value = ""
        value = value or os.getenv(name, "")
        if value:
            return str(value).strip()
    return ""

def _safe_text(value, limit=180):
    return str(value or "").replace("\n", " ").replace("\r", " ").strip()[:limit]

def _coerce_date_series(values: pd.Series) -> pd.Series:
    numeric = pd.to_numeric(values, errors="coerce")
    finite = numeric.dropna()
    if not finite.empty:
        median = float(finite.abs().median())
        unit = "ms" if median > 1e11 else "s"
        return pd.to_datetime(numeric, unit=unit, utc=True, errors="coerce").dt.date
    return pd.to_datetime(values, utc=True, errors="coerce").dt.date

def _fetch_spec(spec: Spec, token: str) -> tuple[pd.DataFrame, dict]:
    r = requests.get(
        COINGLASS_BASE + spec.path,
        headers={"CG-API-KEY": token, "Accept": "application/json"},
        timeout=30,
    )
    status = {
        "dataset": spec.label,
        "http_status": r.status_code,
        "api_code": "",
        "api_message": "",
        "rows": 0,
        "status": "",
        "response_path": "",
        "rate_limit_max": r.headers.get("API-KEY-MAX-LIMIT", ""),
        "rate_limit_used": r.headers.get("API-KEY-USE-LIMIT", ""),
    }
    if r.status_code == 429:
        status["status"] = "RATE LIMITED — STOPPED"
        return pd.DataFrame(), status
    if r.status_code != 200:
        status["status"] = f"HTTP {r.status_code}"
        return pd.DataFrame(), status
    try:
        payload = r.json()
    except ValueError:
        status["status"] = "INVALID JSON"
        return pd.DataFrame(), status

    if isinstance(payload, dict) and "code" in payload:
        status["api_code"] = payload.get("code")
        status["api_message"] = _safe_text(payload.get("msg"))
        if payload.get("code") not in {0, "0", 200, "200"}:
            status["status"] = f"COINGLASS API BLOCKED — code {payload.get('code')}"
            return pd.DataFrame(), status
        if "data" not in payload:
            status["status"] = "COINGLASS RESPONSE HAS NO DATA FIELD"
            return pd.DataFrame(), status

    records, response_path = find_metric_records(payload, spec.value_keys)
    status["response_path"] = response_path or "not located"
    if not records:
        status["status"] = "METRIC RECORDS NOT FOUND — " + safe_shape_summary(payload)
        return pd.DataFrame(), status

    rows = []
    used_key = ""
    for item in records:
        if not isinstance(item, dict):
            continue
        ts = item.get("timestamp")
        if ts is None:
            ts = item.get("time")
        if ts is None:
            ts = item.get("date")
        value = None
        for key in spec.value_keys:
            if item.get(key) is not None:
                value = item.get(key)
                used_key = key
                break
        if ts is None or value is None:
            continue
        rows.append((ts, value))

    if not rows:
        status["status"] = "TIMESTAMP/VALUE ROWS NOT FOUND"
        return pd.DataFrame(), status

    df = pd.DataFrame(rows, columns=["timestamp", spec.column])
    df["date"] = _coerce_date_series(df["timestamp"])
    df[spec.column] = pd.to_numeric(df[spec.column], errors="coerce")
    df = df.dropna(subset=["date", spec.column]).drop(columns=["timestamp"])
    df = df.drop_duplicates(subset=["date"], keep="last").set_index("date").sort_index()
    status["rows"] = len(df)
    status["status"] = f"PARSED ({used_key})"
    return df, status

def collect_specialist_history(st) -> tuple[pd.DataFrame, list[dict]]:
    token = _secret(st, "COINGLASS_API_KEY")
    if not token:
        return pd.DataFrame(), [{"dataset": "CoinGlass", "status": "NOT CONFIGURED", "http_status": None, "rows": 0}]
    merged = pd.DataFrame()
    statuses = []
    for spec in SPECS:
        try:
            frame, status = _fetch_spec(spec, token)
        except requests.RequestException as exc:
            statuses.append({"dataset": spec.label, "status": f"NETWORK ERROR: {type(exc).__name__}", "http_status": None, "rows": 0})
            continue
        statuses.append(status)
        if status.get("status", "").startswith("RATE LIMITED"):
            break
        if frame.empty:
            continue
        merged = frame if merged.empty else merged.join(frame, how="outer")
    if not merged.empty:
        merged.index.name = "date"
        merged = merged.sort_index()
    return merged, statuses

def _github_headers(token: str) -> dict:
    return {
        "Accept": "application/vnd.github+json",
        "Authorization": f"Bearer {token}",
        "X-GitHub-Api-Version": "2022-11-28",
        "User-Agent": "btc-coinglass-staging",
    }

def save_staging_csv(st, frame: pd.DataFrame) -> str:
    if frame is None or frame.empty:
        return "NOT SAVED — no parsed rows"
    token = _secret(st, "AUDIT_GITHUB_TOKEN", "GITHUB_TOKEN", "GH_TOKEN")
    repo = _secret(st, "AUDIT_GITHUB_REPO")
    if not token or not repo:
        return "NOT SAVED — audit GitHub storage not configured"
    url = f"https://api.github.com/repos/{repo}/contents/{STAGING_PATH}"
    headers = _github_headers(token)
    meta = requests.get(url, headers=headers, params={"ref": "main"}, timeout=25)
    sha = None
    if meta.status_code == 200:
        try: sha = meta.json().get("sha")
        except ValueError: sha = None
    elif meta.status_code != 404:
        return f"NOT SAVED — metadata HTTP {meta.status_code}"

    out = frame.copy().reset_index()
    out["date"] = pd.to_datetime(out["date"], errors="coerce").dt.strftime("%Y-%m-%d")
    raw = out.to_csv(index=False).encode("utf-8")
    payload = {
        "message": "Update CoinGlass specialist staging history",
        "content": base64.b64encode(raw).decode("ascii"),
        "branch": "main",
    }
    if sha: payload["sha"] = sha
    put = requests.put(url, headers=headers, json=payload, timeout=45)
    if put.status_code not in (200, 201):
        return f"NOT SAVED — upload HTTP {put.status_code}"
    verify = requests.get(url, headers=headers, params={"ref": "main"}, timeout=25)
    if verify.status_code != 200:
        return f"SAVED but verification HTTP {verify.status_code}"
    return f"SAVED + VERIFIED — {len(frame):,} dates, {len(frame.columns)} provider columns → {STAGING_PATH}"
