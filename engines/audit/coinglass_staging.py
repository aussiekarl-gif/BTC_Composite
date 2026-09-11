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


COINGLASS_BASE = "https://open-api-v4.coinglass.com"
STAGING_PATH = "staging/coinglass_specialist.csv"


@dataclass(frozen=True)
class Spec:
    label: str
    path: str
    value_key: str
    column: str


SPECS = [
    Spec("STH SOPR", "/api/index/bitcoin-sth-sopr", "sth_sopr", "cg__sth_sopr"),
    Spec("LTH SOPR", "/api/index/bitcoin-lth-sopr", "lth_sopr", "cg__lth_sopr"),
    Spec("STH Realized Price", "/api/index/bitcoin-sth-realized-price", "sth_realized_price", "cg__sth_realized_price"),
    Spec("LTH Realized Price", "/api/index/bitcoin-lth-realized-price", "lth_realized_price", "cg__lth_realized_price"),
    Spec("RHODL Ratio", "/api/index/bitcoin-rhodl-ratio", "rhodl_ratio", "cg__rhodl_ratio"),
    Spec("STH Supply", "/api/index/bitcoin-short-term-holder-supply", "short_term_holder_supply", "cg__sth_supply"),
    Spec("LTH Supply", "/api/index/bitcoin-long-term-holder-supply", "long_term_holder_supply", "cg__lth_supply"),
    Spec("Reserve Risk", "/api/index/bitcoin-reserve-risk", "reserve_risk_index", "cg__reserve_risk"),
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


def _fetch_spec(spec: Spec, token: str) -> tuple[pd.DataFrame, dict]:
    r = requests.get(
        COINGLASS_BASE + spec.path,
        headers={"CG-API-KEY": token, "Accept": "application/json"},
        timeout=30,
    )
    status = {
        "dataset": spec.label,
        "http_status": r.status_code,
        "rows": 0,
        "status": "",
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
    data = payload.get("data", []) if isinstance(payload, dict) else []
    if not isinstance(data, list):
        status["status"] = "UNEXPECTED DATA SHAPE"
        return pd.DataFrame(), status
    rows = []
    for item in data:
        if not isinstance(item, dict):
            continue
        ts = item.get("timestamp")
        value = item.get(spec.value_key)
        if ts is None or value is None:
            continue
        rows.append((ts, value))
    if not rows:
        status["status"] = f"FIELD NOT FOUND: {spec.value_key}"
        return pd.DataFrame(), status
    df = pd.DataFrame(rows, columns=["timestamp", spec.column])
    df["date"] = pd.to_datetime(df["timestamp"], unit="ms", utc=True, errors="coerce").dt.date
    df[spec.column] = pd.to_numeric(df[spec.column], errors="coerce")
    df = df.dropna(subset=["date", spec.column]).drop(columns=["timestamp"])
    df = df.drop_duplicates(subset=["date"], keep="last").set_index("date").sort_index()
    status["rows"] = len(df)
    status["status"] = "PARSED"
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
    """Persist to staging/coinglass_specialist.csv only; never the authoritative master."""
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
        try:
            sha = meta.json().get("sha")
        except ValueError:
            sha = None
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
    if sha:
        payload["sha"] = sha
    put = requests.put(url, headers=headers, json=payload, timeout=45)
    if put.status_code not in (200, 201):
        return f"NOT SAVED — upload HTTP {put.status_code}"

    verify = requests.get(url, headers=headers, params={"ref": "main"}, timeout=25)
    if verify.status_code != 200:
        return f"SAVED but verification HTTP {verify.status_code}"
    return f"SAVED + VERIFIED — {len(frame):,} dates, {len(frame.columns)} provider columns → {STAGING_PATH}"
