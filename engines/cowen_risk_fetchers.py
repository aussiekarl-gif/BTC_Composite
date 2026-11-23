"""
Free live data fetchers — using the user's tokens, all opportunistic/free.

Primary source — BGeometrics (bitcoin-data.com):
  * "Free plan: No registration needed — just call the API directly."
  * Endpoints used here (all GET https://bitcoin-data.com/v1/<endpoint>):
      - market-cap, mvrv, mvrv-zscore, puell-multiple, terminal-price,
        thermo-cap, profit-loss (fraction in [0,1]), realized-cap-hodl-waves
        (per-band realized cap for the RHODL approximation).
  * Limit: 10 requests / hour (hourly counter on your IP).
  * Token: BGEOMETRICS_TOKEN / BITCOIN_DATA_API_TOKEN — sent as
    Authorization: Bearer (the free plan is anonymous-capable; a token may
    unlock Advanced/full history — your call).

Token sources (env vars — see README for why GitHub secrets are NOT
readable via the GitHub API; export them or paste them into the environment):
  * CryptoQuant v1 — CRYPTOQUANT_API_KEY: fills MVRV, Realized Price
    (realized_price_usd), Fees (transaction_fees_usd), MinerCap
    (miner_cap_usd → mCTC), Supply (supply_current).  Market-indicator data
    there requires Professional+ — used opportunistically, silent fallback.
  * CryptoQuant community — CQ_API_KEY (free-account token): MVRV Z-Score.
  * Coinglass Pro — COINGLASS_API_KEY (CG-API-KEY header): Bitcoin RHODL Ratio
    (/api/index/bitcoin-rhodl-ratio); opportunistic Terminal Price candidates.
  * CoinGecko — COINGECKO_API (anonymous, or x-cg-pro-api-key for the Pro
    tier): spot market cap.
  * MANUAL_REALISED_PRICE_USD: constant realized price in USD; the app derives
    Realized Cap = price × circulating supply → MVRV (needs supply_current or
    a CSV `circulating_supply` column).

Streamlit caches the live bundle (st.cache_data, TTL=1800s) so the BGeometrics
10-requests-per-hour limit is respected across app reruns.
"""

from __future__ import annotations

import concurrent.futures
import os
from typing import Optional

import numpy as np
import pandas as pd
import requests
import streamlit as st

BASE = "https://bitcoin-data.com/v1"

def _env(var: str) -> Optional[str]:
    """Return the value of an env var, or a Streamlit secret (from
    `.streamlit/secrets.toml`) when the env var is not set."""
    v = os.environ.get(var)
    if v:
        return v
    try:
        return st.secrets.get(var) or None
    except Exception:
        return None

# Canonical columns produced by fetch_live_df() — consumed by app.derive_series().
# endpoint: canonical column emitted.
BG_SERIES = {
    "mvrv": "mvrv",
    "mvrv-zscore": "mvrv_zscore",
    "puell-multiple": "puell_multiple",
    "terminal-price": "terminal_price",
    "thermo-cap": "thermo_cap",
    "profit-loss": "profit_loss",
    "market-cap": "market_cap",
}

# Candidate field names accepted when parsing BGeometrics responses
# (the API uses e.g. mvrvZscore / marketCap; different endpoints name
# values slightly differently).
BG_CANDIDATES = {
    "mvrv": ["mvrv"],
    "mvrv-zscore": ["mvrvZscore", "mvrv_zscore", "mvrvZScore", "mvrv_z", "zscore"],
    "puell-multiple": ["puellMultiple", "puell_multiple", "puell"],
    "terminal-price": ["terminalPrice", "terminal_price", "terminalprice"],
    "thermo-cap": ["thermoCap", "thermocap", "thermo_cap"],
    "profit-loss": ["profitLoss", "profit_loss"],
    "market-cap": ["marketCap", "market_cap"],
}

BTC_GENESIS = pd.Timestamp("2009-01-03")

# RHODL approximation: (RealizedValue(1-week band) / RealizedValue(1y–2y band))
# × market age in days.  "1-week band" is proxied by the band that starts at
# 1 week (age_1w_1m); the "1y–2y band" is age_1y_2y.
RHODL_RECENT_BAND = "age_1w_1m"
RHODL_MATURE_BAND = "age_1y_2y"

# CryptoQuant community enrichment: canonical column -> path under
# /v2/community/ when CQ_API_KEY is set.  Fills only what BGeometrics lacks.
CQ_COMMUNITY_FILL = {
    "mvrv_zscore": "bitcoin-mvrv-z-score",
}

# CryptoQuant v1 fills (opportunistic, CRYPTOQUANT_API_KEY):
# canonical column -> (v1 path, [candidate field names]) — field names from the
# CryptoQuant API catalog (docs.cryptoquant.com/catalog/catalog.json).
CQ_V1_URL = "https://api.cryptoquant.com/v1"

CQ_V1_FILLS = {
    "mvrv": ("btc/market-indicator/mvrv", ["mvrv"]),
    "realized_price_usd": ("btc/market-indicator/realized-price", ["realized_price", "realised_price"]),
    "transaction_fees_usd": (
        "btc/network-data/fees",
        ["fees_transaction_mean_usd", "fees_transaction_median_usd",
         "fees_block_mean_usd", "fees_total_usd"],
    ),
    "miner_cap_usd": ("btc/miner-flows/reserve", ["reserve_usd", "reserve"]),
    "supply_current": ("btc/network-data/supply", ["supply_total", "supply_new"]),
}

# Coinglass Pro fills (opportunistic, COINGLASS_API_KEY):
# canonical column -> list of (full path, [candidate field names]).
# rhodl_ratio path verified in the Coinglass endpoint overview; the Terminal
# Price path on the Pro indicator page is opportunistic (several candidates).
COINGLASS_BASE = "https://open-api-v4.coinglass.com"

COINGLASS_FILLS = {
    "rhodl_ratio": [
        (f"{COINGLASS_BASE}/api/index/bitcoin-rhodl-ratio", ["rhodl_ratio", "rhodl", "rhodlRatio"]),
    ],
    "terminal_price": [
        (f"{COINGLASS_BASE}/api/index/bitcoin-terminal-price", ["terminal_price", "terminalPrice"]),
        (f"{COINGLASS_BASE}/api/index/bitcoin-terminal-price-model", ["terminal_price", "terminalPrice"]),
        (f"{COINGLASS_BASE}/api/pro/terminal-price", ["terminal_price", "terminalPrice"]),
        (f"{COINGLASS_BASE}/api/index/bitcoin-terminal-price-estimate", ["terminal_price", "terminalPrice"]),
    ],
}


# ---------------------------------------------------------------------------
# JSON / record parsing
# ---------------------------------------------------------------------------

def _get_json(url: str, timeout: int = 20, headers: dict | None = None):
    try:
        r = requests.get(url, timeout=timeout, headers=headers)
        if r.status_code != 200:
            if headers and r.status_code in (401, 403):
                # token rejected → retry anonymously (free plan)
                r = requests.get(url, timeout=timeout)
                if r.status_code != 200:
                    return None
            else:
                return None  # includes 429 (rate-limited)
        return r.json()
    except Exception:
        return None


def _parse_records_df(payload) -> Optional[pd.DataFrame]:
    """Parse BGeometrics responses of the form [{d, <value fields>}, ...]
    into a DataFrame indexed by date."""
    if isinstance(payload, dict):
        payload = payload.get("data") or payload.get("result") or payload.get("body")
    if not isinstance(payload, list):
        return None
    records = [r for r in payload
               if isinstance(r, dict) and any(k in r for k in ("d", "date", "timestamp", "unixTs"))]
    if not records:
        return None
    df = pd.DataFrame(records)
    date_col = next((c for c in ("d", "date", "timestamp") if c in df.columns), None)
    if date_col is None:
        return None
    df = df.rename(columns={date_col: "date"})
    df["date"] = pd.to_datetime(df["date"], errors="coerce")
    df = df.dropna(subset=["date"]).sort_values("date")
    if df.empty:
        return None
    return df.set_index("date")


def _series_from_records(payload, candidates: list[str]) -> Optional[pd.Series]:
    df = _parse_records_df(payload)
    if df is None:
        return None
    col = next((c for c in candidates if c in df.columns), None)
    if col is None:
        numeric = [c for c in df.columns if pd.api.types.is_numeric_dtype(df[c])]
        col = numeric[0] if numeric else None
    if col is None:
        return None
    s = pd.to_numeric(df[col], errors="coerce").dropna()
    s.name = "value"
    return s


def _fetch_bgeometrics_series(endpoint: str, candidates: list[str]) -> Optional[pd.Series]:
    return _series_from_records(
        _get_json(f"{BASE}/{endpoint}", headers=_bgeometrics_headers()),
        candidates,
    )


def fetch_bgeometrics_hodl_waves() -> Optional[pd.DataFrame]:
    """Realized cap by HODL bands -> for the RHODL approximation."""
    return _parse_records_df(
        _get_json(f"{BASE}/realized-cap-hodl-waves", headers=_bgeometrics_headers())
    )


def _bgeometrics_headers() -> dict:
    """Send BGEOMETRICS_TOKEN / BITCOIN_DATA_API_TOKEN as a Bearer token if set."""
    for var in ("BGEOMETRICS_TOKEN", "BITCOIN_DATA_API_TOKEN"):
        token = _env(var)
        if token:
            return {"Authorization": f"Bearer {token}"}
    return {}


def _rhodl_from_hodl(hodl: pd.DataFrame) -> Optional[pd.Series]:
    if RHODL_RECENT_BAND not in hodl.columns or RHODL_MATURE_BAND not in hodl.columns:
        return None
    recent = pd.to_numeric(hodl[RHODL_RECENT_BAND], errors="coerce")
    mature = pd.to_numeric(hodl[RHODL_MATURE_BAND], errors="coerce")
    age_days = (hodl.index - BTC_GENESIS).days.astype(float)
    rhodl = pd.Series(
        np.where(mature > 0, (recent * age_days) / mature, np.nan),
        index=hodl.index,
    )
    return rhodl.dropna()


# ---------------------------------------------------------------------------
# CryptoQuant (v1 + community) — opportunistic fills (user's tokens)
# ---------------------------------------------------------------------------

def _cq_v1_get(path: str):
    key = _env("CRYPTOQUANT_API_KEY")
    if not key:
        return None
    payload = _get_json(f"{CQ_V1_URL}/{path}", headers={"Authorization": f"Bearer {key}"})
    if payload is None:
        payload = _get_json(f"{CQ_V1_URL}/{path}?api_key={key}")
    return payload


def _cq_v1_fills(out: dict) -> None:
    for col, (path, cands) in CQ_V1_FILLS.items():
        if col in out:
            continue
        s = _extract_series(_cq_v1_get(path), cands)
        if s is not None and not s.empty:
            out[col] = s


def fetch_cryptoquant_series(path: str) -> Optional[pd.Series]:
    """Fetch a CryptoQuant community endpoint (requires CQ_API_KEY env var)
    and extract the first date/value series found in the response."""
    key = _env("CQ_API_KEY")
    if not key:
        return None
    payload = _get_json(f"https://api.cryptoquant.com/v2/community/{path}",
                        headers={"Authorization": f"Bearer {key}"})
    if payload is None:
        return None

    def extract(obj, depth=0):
        if depth > 6:
            return None
        if isinstance(obj, dict):
            date_keys = ("date", "datetime", "day", "d")
            has_date = any(k in obj for k in date_keys)
            if has_date and any(isinstance(v, (int, float)) and not isinstance(v, bool)
                                for k, v in obj.items() if k not in date_keys):
                return obj
            for v in obj.values():
                r = extract(v, depth + 1)
                if r is not None:
                    return r
        elif isinstance(obj, list) and obj and isinstance(obj[0], dict):
            date_keys = ("date", "datetime", "day", "d")
            if any(any(k in r for k in date_keys) for r in obj[:50]):
                recs = [r for r in obj if isinstance(r, dict)]
                dates, vals = [], []
                for r in recs:
                    d = next((r[k] for k in date_keys if k in r), None)
                    v = next((v for k, v in r.items()
                              if k not in date_keys and isinstance(v, (int, float))
                              and not isinstance(v, bool)), None)
                    if d is not None and v is not None:
                        dates.append(d)
                        vals.append(v)
                if dates:
                    df = pd.DataFrame({"v": vals}, index=pd.to_datetime(pd.Series(dates), errors="coerce"))
                    df = df.loc[~df.index.duplicated(keep="first")].sort_index()
                    return df["v"]
            for v in obj[:50]:
                r = extract(v, depth + 1)
                if r is not None:
                    return r
        return None

    s = extract(payload)
    if isinstance(s, pd.Series):
        return s.astype(float)
    if isinstance(s, pd.DataFrame) and "v" in s.columns:
        return s["v"].astype(float)
    return None


# ---------------------------------------------------------------------------
# Coinglass Pro (opportunistic fills, COINGLASS_API_KEY)
# ---------------------------------------------------------------------------

def _coinglass_fills(out: dict) -> None:
    key = _env("COINGLASS_API_KEY")
    headers = {"CG-API-KEY": key} if key else None
    for col, targets in COINGLASS_FILLS.items():
        if col in out:
            continue
        for url, cands in targets:
            s = _extract_series(_get_json(url, headers=headers), cands)
            if s is not None and not s.empty:
                out[col] = s
                break


# ---------------------------------------------------------------------------
# Generic extractors (tolerant of API envelope shapes)
# ---------------------------------------------------------------------------

DATE_KEYS = ("d", "date", "datetime", "day", "timestamp", "unixTs", "date_time", "ts")
NON_VALUE_KEYS = set(DATE_KEYS) | {"blockheight", "id", "symbol", "metric", "name", "exchange"}


def _dt_series(vals) -> pd.DatetimeIndex:
    s = pd.Series(vals)
    if (s.size > 0 and s.notna().all() and pd.api.types.is_numeric_dtype(s)
            and s.iloc[0] > 1_000_000_000):
        return pd.DatetimeIndex(pd.to_datetime(s, unit="s"))
    return pd.DatetimeIndex(pd.to_datetime(s, errors="coerce"))


def _first_numeric(rec: dict, candidates: list[str]) -> Optional[float]:
    for c in candidates:
        v = rec.get(c)
        if isinstance(v, (int, float)) and not isinstance(v, bool):
            return float(v)
    for k, v in rec.items():
        if k in NON_VALUE_KEYS:
            continue
        if isinstance(v, (int, float)) and not isinstance(v, bool):
            return float(v)
    return None


def _extract_series(payload, candidates: list[str]) -> Optional[pd.Series]:
    """Tolerant extractor: finds the first date/value series in a JSON payload
    (list of records, or dict envelopes like {"data": [...]})."""
    if payload is None:
        return None
    if isinstance(payload, dict):
        for k in ("data", "result", "body", "metrics", "series", "values", "records", "response"):
            if k in payload:
                s = _extract_series(payload[k], candidates)
                if s is not None:
                    return s
        return None
    if isinstance(payload, list):
        recs = [r for r in payload if isinstance(r, dict)]
        dates, vals = [], []
        for r in recs:
            d = next((r[k] for k in DATE_KEYS if r.get(k) is not None), None)
            if d is None:
                continue
            v = _first_numeric(r, candidates)
            if v is not None:
                dates.append(d)
                vals.append(v)
        if dates:
            s = pd.Series(vals, index=_dt_series(dates))
            return s.dropna().sort_index()
    return None


# ---------------------------------------------------------------------------
# CoinGecko (anonymous or pro key) — spot market cap
# ---------------------------------------------------------------------------

def fetch_coingecko_market_cap() -> Optional[float]:
    """Current spot market cap of Bitcoin (single value) from CoinGecko."""
    key = _env("COINGECKO_API")
    headers = {"x-cg-pro-api-key": key} if key else None
    payload = _get_json(
        "https://api.coingecko.com/api/v3/coins/bitcoin?localization=false&tickers=false&market_data=true",
        headers=headers,
    )
    if not isinstance(payload, dict):
        return None
    try:
        return float(payload["market_data"]["market_cap"]["usd"])
    except (KeyError, TypeError, ValueError):
        return None


def _manual_realised_price() -> Optional[float]:
    """MANUAL_REALISED_PRICE_USD (or US spelling) — constant realized price in USD."""
    raw = _env("MANUAL_REALISED_PRICE_USD") or _env("MANUAL_REALIZED_PRICE_USD")
    if not raw:
        return None
    try:
        return float(raw)
    except (TypeError, ValueError):
        return None


# ---------------------------------------------------------------------------
# Live bundle (cached)
# ---------------------------------------------------------------------------

@st.cache_data(ttl=1800, show_spinner=False)
def fetch_live_df() -> Optional[pd.DataFrame]:
    """Fetch the canonical live DataFrame. Returns None when nothing
    could be fetched (e.g. hourly rate limit hit)."""
    out: dict[str, pd.Series] = {}
    endpoints = dict(BG_SERIES)

    with concurrent.futures.ThreadPoolExecutor(max_workers=9) as ex:
        futs = {
            ep: ex.submit(_fetch_bgeometrics_series, ep, BG_CANDIDATES[ep])
            for ep in endpoints
        }
        futs["realized-cap-hodl-waves"] = ex.submit(fetch_bgeometrics_hodl_waves)
        for ep, fut in futs.items():
            try:
                s = fut.result()
            except Exception:
                s = None
            if ep == "realized-cap-hodl-waves":
                if s is not None:
                    rhodl = _rhodl_from_hodl(s)
                    if rhodl is not None and not rhodl.empty:
                        out["rhodl_ratio"] = rhodl
                continue
            col = endpoints[ep]
            if s is not None and not s.empty:
                out[col] = s

    # Optional CryptoQuant community enrichment (needs CQ_API_KEY).
    for col, cq_path in CQ_COMMUNITY_FILL.items():
        if col not in out:
            s = fetch_cryptoquant_series(cq_path)
            if s is not None and not s.empty:
                out[col] = s

    df = pd.DataFrame(out)

    # CryptoQuant v1 fills (needs CRYPTOQUANT_API_KEY) — silent fallback if missing.
    _cq_v1_fills(out)
    df = pd.DataFrame(out)

    # Coinglass Pro fills (needs COINGLASS_API_KEY) — silent fallback if missing.
    _coinglass_fills(out)
    df = pd.DataFrame(out)

    # CoinGecko spot market cap — fallback when BGeometrics market-cap is
    # missing/empty.
    if "market_cap" not in df.columns or df["market_cap"].isna().all():
        cg = fetch_coingecko_market_cap()
        if cg is not None:
            df["market_cap"] = cg

    # MANUAL_REALISED_PRICE_USD → realized_price_usd column (used for MVRV).
    rp = _manual_realised_price()
    if rp is not None and not df.empty:
        df["realized_price_usd"] = rp

    df = df.dropna(how="all", axis=1)
    if df.empty:
        return None
    return df
