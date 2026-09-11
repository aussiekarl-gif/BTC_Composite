import os
import time
import io
import json
import base64
import hashlib
import datetime as dt
from pathlib import Path
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd
import requests
import streamlit as st

BASE = "https://bitcoin-data.com/v1"
HEADERS = {"User-Agent": "Mozilla/5.0", "Accept": "application/json"}
COINMETRICS_BASE = "https://community-api.coinmetrics.io/v4"
COINMETRICS_ASSET = "btc"

# Names below are deliberately protected from BGeometrics acquisition.
# They are either calculated from the frozen benchmark price or from free Coin Metrics inputs.
FREE_FIRST_CANDIDATES = {
    "Puell Multiple", "Mayer Multiple (200D)", "2Y MA Multiple", "200W MA Multiple",
    "MVRV", "NUPL", "NVT", "NVT Signal", "ThermoCap Multiple", "Investor Price",
    "MVRV Z-Score (positive control)",
}

# Research candidates only. Nothing here changes Production or V5.9 Research.
CANDIDATES = {
    # Existing positive control. Reuse local cache; never spend BGeometrics quota just to refresh it.
    "MVRV Z-Score (positive control)": ("LOCAL CACHE", []),

    # Free/self-calculated candidates. These are NEVER requested from BGeometrics.
    "Puell Multiple": ("FREE / Coin Metrics -> calculated locally", []),
    "Mayer Multiple (200D)": ("SELF / benchmark price", []),
    "2Y MA Multiple": ("SELF / benchmark price", []),
    "200W MA Multiple": ("SELF / benchmark price", []),
    "MVRV": ("FREE / Coin Metrics inputs -> calculated locally", []),
    "NUPL": ("FREE / Coin Metrics inputs -> calculated locally", []),
    "NVT": ("FREE / Coin Metrics inputs -> calculated locally", []),
    "NVT Signal": ("FREE / Coin Metrics inputs -> calculated locally", []),
    "ThermoCap Multiple": ("FREE / Coin Metrics inputs -> calculated locally", []),
    "Investor Price": ("FREE / Coin Metrics inputs -> calculated locally", []),

    # Metrics that still require a specialist on-chain history source.
    "VDD Multiple": ("vdd-multiple", ["vddMultiple", "vdd_multiple", "value"]),
    "STH MVRV": ("sth-mvrv", ["sthMvrv", "sth_mvrv", "mvrv", "value"]),
    "LTH MVRV": ("lth-mvrv", ["lthMvrv", "lth_mvrv", "mvrv", "value"]),
    "aSOPR": ("asopr", ["asopr", "aSOPR", "value"]),
    "% Supply / UTXOs in Profit": ("profit-loss", ["profitLoss", "profit_loss", "profit", "value", "percent", "pct"]),
}

# One-time master-history acquisition plan. These are DATA candidates, not strategy inputs.
# Priority 1 fills the current audit gaps; priorities 2-3 preserve useful adjacent on-chain
# families so future research does not need to re-download history. CSV support below is
# based on the BGeometrics API schema already saved with this project.
MASTER_DATASETS = [
    # Priority 1 — current audit gaps
    {"label":"VDD Multiple", "endpoint":"vdd-multiple", "priority":1, "category":"Coin-day activity", "csv":True, "aliases":["vddMultiple","vdd_multiple","value"]},
    {"label":"VDD", "endpoint":"vdd", "priority":1, "category":"Coin-day activity", "csv":True, "aliases":["vdd","value"]},
    {"label":"STH MVRV", "endpoint":"sth-mvrv", "priority":1, "category":"Holder valuation", "csv":False, "aliases":["sthMvrv","sth_mvrv","mvrv","value"]},
    {"label":"LTH MVRV", "endpoint":"lth-mvrv", "priority":1, "category":"Holder valuation", "csv":False, "aliases":["lthMvrv","lth_mvrv","mvrv","value"]},
    {"label":"aSOPR", "endpoint":"asopr", "priority":1, "category":"Spent-profit behaviour", "csv":False, "aliases":["asopr","aSOPR","value"]},
    {"label":"UTXOs in Profit %", "endpoint":"utxos-in-profit-pct", "priority":1, "category":"Profitability", "csv":False, "aliases":["utxosInProfitPct","utxos_in_profit_pct","percent","pct","value"]},
    {"label":"Supply in Profit %", "endpoint":"supply-in-profit-pct", "priority":1, "category":"Profitability", "csv":True, "aliases":["supplyInProfitPct","supply_in_profit_pct","percent","pct","value"]},

    # Priority 2 — close relatives / strong research controls
    {"label":"STH MVRV Z-Score", "endpoint":"sth-mvrv-zscore", "priority":2, "category":"Holder valuation", "csv":False, "aliases":["sthMvrvZscore","zscore","value"]},
    {"label":"LTH MVRV Z-Score", "endpoint":"lth-mvrv-zscore", "priority":2, "category":"Holder valuation", "csv":False, "aliases":["lthMvrvZscore","zscore","value"]},
    {"label":"SOPR", "endpoint":"sopr", "priority":2, "category":"Spent-profit behaviour", "csv":False, "aliases":["sopr","value"]},
    {"label":"STH SOPR", "endpoint":"sth-sopr", "priority":2, "category":"Spent-profit behaviour", "csv":False, "aliases":["sthSopr","sopr_sth","sopr","value"]},
    {"label":"LTH SOPR", "endpoint":"lth-sopr", "priority":2, "category":"Spent-profit behaviour", "csv":False, "aliases":["lthSopr","sopr_lth","sopr","value"]},
    {"label":"STH Realized Price", "endpoint":"sth-realized-price", "priority":2, "category":"Cost basis", "csv":False, "aliases":["sthRealizedPrice","realized_price","price","value"]},
    {"label":"LTH Realized Price", "endpoint":"lth-realized-price", "priority":2, "category":"Cost basis", "csv":False, "aliases":["lthRealizedPrice","realized_price","price","value"]},
    {"label":"CVDD", "endpoint":"cvdd", "priority":2, "category":"Long-cycle floor", "csv":True, "aliases":["cvdd","price","value"]},
    {"label":"CDD", "endpoint":"cdd", "priority":2, "category":"Coin-day activity", "csv":True, "aliases":["cdd","value"]},
    {"label":"Supply Adjusted CDD", "endpoint":"supply-adjusted-cdd", "priority":2, "category":"Coin-day activity", "csv":True, "aliases":["supplyAdjustedCdd","cdd","value"]},
    {"label":"Liveliness", "endpoint":"liveliness", "priority":2, "category":"Coin-day activity", "csv":True, "aliases":["liveliness","value"]},
    {"label":"Average Dormancy", "endpoint":"average-dormancy", "priority":2, "category":"Coin-day activity", "csv":True, "aliases":["averageDormancy","dormancy","value"]},
    {"label":"RHODL Ratio", "endpoint":"rhodl-ratio", "priority":2, "category":"Holder age valuation", "csv":False, "aliases":["rhodlRatio","rhodl_ratio","value"]},
    {"label":"NVT Z-Score", "endpoint":"nvt-zscore", "priority":2, "category":"Network valuation", "csv":False, "aliases":["nvtZscore","zscore","value"]},

    # Priority 3 — preserve broader context while quota permits
    {"label":"Realized Profit/Loss Ratio", "endpoint":"realized-profit-loss-ratio", "priority":3, "category":"Profitability", "csv":False, "aliases":["realizedProfitLossRatio","ratio","value"]},
    {"label":"Percent STH in Profit", "endpoint":"percent-sth-in-profit", "priority":3, "category":"Profitability", "csv":False, "aliases":["percentSthInProfit","percent","pct","value"]},
    {"label":"Percent LTH in Profit", "endpoint":"percent-lth-in-profit", "priority":3, "category":"Profitability", "csv":False, "aliases":["percentLthInProfit","percent","pct","value"]},
    {"label":"STH Supply in Profit", "endpoint":"supply-profit-sth", "priority":3, "category":"Profitability", "csv":False, "aliases":["supplyProfitSth","value"]},
    {"label":"LTH Supply in Profit", "endpoint":"supply-profit-lth", "priority":3, "category":"Profitability", "csv":False, "aliases":["supplyProfitLth","value"]},
    {"label":"STH Supply in Loss", "endpoint":"supply-loss-sth", "priority":3, "category":"Profitability", "csv":False, "aliases":["supplyLossSth","value"]},
    {"label":"LTH Supply in Loss", "endpoint":"supply-loss-lth", "priority":3, "category":"Profitability", "csv":False, "aliases":["supplyLossLth","value"]},
    {"label":"Long-Term Holder Supply", "endpoint":"long-term-hodler-supply-btc", "priority":3, "category":"Holder supply", "csv":False, "aliases":["longTermHodlerSupplyBtc","supply","value"]},
    {"label":"Short-Term Holder Supply", "endpoint":"short-term-hodler-supply-btc", "priority":3, "category":"Holder supply", "csv":False, "aliases":["shortTermHodlerSupplyBtc","supply","value"]},
    {"label":"Illiquid Supply", "endpoint":"illiquid-supply", "priority":3, "category":"Liquidity", "csv":False, "aliases":["illiquidSupply","supply","value"]},
    {"label":"Highly Liquid Supply", "endpoint":"highly-liquid-supply", "priority":3, "category":"Liquidity", "csv":True, "aliases":["highlyLiquidSupply","supply","value"]},
    {"label":"1 Year HODL", "endpoint":"hodl-one-year", "priority":3, "category":"Holder age", "csv":False, "aliases":["hodlOneYear","percent","value"]},
    {"label":"2 Year HODL", "endpoint":"hodl-two-year", "priority":3, "category":"Holder age", "csv":False, "aliases":["hodlTwoYear","percent","value"]},
    {"label":"Miner Reserve", "endpoint":"miner-reserve", "priority":3, "category":"Miner", "csv":False, "aliases":["minerReserve","reserve","value"]},
    {"label":"Miner Sell Pressure", "endpoint":"miner-sell-pressure", "priority":3, "category":"Miner", "csv":False, "aliases":["minerSellPressure","value"]},
    {"label":"Miner Position Index", "endpoint":"miner-position-index", "priority":3, "category":"Miner", "csv":False, "aliases":["minerPositionIndex","mpi","value"]},
    {"label":"Active MVRV", "endpoint":"active-mvrv", "priority":3, "category":"Cointime", "csv":False, "aliases":["activeMvrv","mvrv","value"]},
    {"label":"Vaulted MVRV", "endpoint":"vaulted-mvrv", "priority":3, "category":"Cointime", "csv":False, "aliases":["vaultedMvrv","mvrv","value"]},
    {"label":"Profitable Days", "endpoint":"profitable-days", "priority":3, "category":"Cycle context", "csv":False, "aliases":["profitableDays365d","profitable_days_365d","value"]},
]

MASTER_START_DATE = dt.date(2010, 7, 18)
BRISBANE_TZ = ZoneInfo("Australia/Brisbane")

# Cache lives beside this script when bundled into engines/audit/cache.
# Streamlit Cloud/local runtimes may not preserve writes across redeploys, so the
# page also provides a downloadable consolidated cache that can be committed/uploaded.
SCRIPT_DIR = Path(__file__).resolve().parent if "__file__" in globals() else Path.cwd()
CACHE_DIR = SCRIPT_DIR / "cache"
CACHE_DIR.mkdir(parents=True, exist_ok=True)
BUNDLED_CACHE = CACHE_DIR / "public_model_cache.csv"
MASTER_CACHE = CACHE_DIR / "btc_onchain_master_cache.csv"
FROZEN_BENCHMARK = CACHE_DIR / "btc_v5_9_r2_frozen.csv"
AUDIT_MEMORY = CACHE_DIR / "btc_audit_memory.csv"


def get_token():
    try:
        t = st.secrets.get("BGEOMETRICS_TOKEN", "")
        if t:
            return str(t).strip()
    except Exception:
        pass
    return os.getenv("BGEOMETRICS_TOKEN", "").strip()


def _secret_or_env(*names, default=""):
    for name in names:
        try:
            value = st.secrets.get(name, "")
            if value:
                return str(value).strip()
        except Exception:
            pass
        value = os.getenv(name, "")
        if value:
            return str(value).strip()
    return default


def audit_storage_config():
    """Durable GitHub storage for Streamlit Cloud.

    IMPORTANT: use a separate private data repo, not the repo that deploys this app,
    otherwise every autosave commit can trigger a Streamlit redeploy.
    """
    token = _secret_or_env("AUDIT_GITHUB_TOKEN", "GITHUB_TOKEN", "GH_TOKEN")
    repo = _secret_or_env("AUDIT_GITHUB_REPO")
    branch = _secret_or_env("AUDIT_GITHUB_BRANCH", default="main") or "main"
    path = _secret_or_env("AUDIT_GITHUB_PATH", default="btc_audit_backup.csv") or "btc_audit_backup.csv"
    return {"token": token, "repo": repo, "branch": branch, "path": path}


def _github_headers(token):
    return {
        "Accept": "application/vnd.github+json",
        "Authorization": f"Bearer {token}",
        "X-GitHub-Api-Version": "2022-11-28",
        "User-Agent": "btc-public-model-audit",
    }


def _github_read_backup():
    """Read the durable backup from GitHub, including files >1 MB.

    GitHub's Contents API deliberately omits the inline `content` field for files
    larger than 1 MB.  The old implementation interpreted that as an empty file.
    We now fetch the raw representation explicitly, so a multi-megabyte audit CSV
    restores correctly after Streamlit sleeps/restarts.

    Returns (raw_bytes, sha, status).
    """
    cfg = audit_storage_config()
    if not cfg["token"] or not cfg["repo"]:
        return b"", None, "NOT CONFIGURED"

    url = f"https://api.github.com/repos/{cfg['repo']}/contents/{cfg['path']}"
    headers = _github_headers(cfg["token"])
    try:
        meta = requests.get(url, headers=headers, params={"ref": cfg["branch"]}, timeout=25)
        if meta.status_code == 404:
            return b"", None, "CONNECTED — no remote backup yet"
        meta.raise_for_status()
        obj = meta.json()
        sha = obj.get("sha")

        # Small files are normally embedded as base64 in the metadata response.
        content = obj.get("content")
        if content:
            raw = base64.b64decode(content.encode())
            return raw, sha, f"CONNECTED — remote backup found ({len(raw):,} bytes)"

        # Files >1 MB are not embedded by the Contents API. Request raw bytes.
        raw_headers = headers.copy()
        raw_headers["Accept"] = "application/vnd.github.raw"
        rr = requests.get(url, headers=raw_headers, params={"ref": cfg["branch"]}, timeout=45)
        rr.raise_for_status()
        raw = rr.content

        # Defensive fallback: some GitHub/proxy combinations may still return JSON.
        ctype = (rr.headers.get("content-type") or "").lower()
        if "json" in ctype:
            try:
                robj = rr.json()
                if robj.get("content"):
                    raw = base64.b64decode(robj["content"].encode())
                elif obj.get("download_url"):
                    dr = requests.get(obj["download_url"], headers=headers, timeout=45)
                    dr.raise_for_status()
                    raw = dr.content
            except Exception:
                pass

        if not raw:
            return b"", sha, "CONNECTED — remote backup is genuinely empty"
        return raw, sha, f"CONNECTED — remote backup found ({len(raw):,} bytes)"
    except Exception as e:
        return b"", None, f"ERROR — {type(e).__name__}: {e}"


def load_remote_audit_memory():
    """Load the single durable backup CSV from GitHub. Returns (frame, status)."""
    raw, _sha, status = _github_read_backup()
    if not raw:
        return pd.DataFrame(), status
    try:
        frame = read_cache_csv(io.BytesIO(raw))
        if frame is None or frame.empty:
            return pd.DataFrame(), "CONNECTED — remote CSV read but contained no usable rows"
        return frame, f"CONNECTED — restored {len(frame):,} remote rows"
    except Exception as e:
        return pd.DataFrame(), f"ERROR — remote CSV parse failed: {type(e).__name__}: {e}"


def save_remote_audit_memory(memory):
    """Persist the entire audit memory as ONE CSV in GitHub, only when changed.

    Handles backups larger than 1 MB and returns explicit HTTP details on failure.
    """
    cfg = audit_storage_config()
    if memory is None or memory.empty:
        return "SKIPPED — memory empty"
    if not cfg["token"] or not cfg["repo"]:
        return "NOT CONFIGURED"

    tmp = memory.copy()
    tmp.index.name = "date"
    raw = tmp.reset_index().to_csv(index=False).encode("utf-8")
    url = f"https://api.github.com/repos/{cfg['repo']}/contents/{cfg['path']}"
    headers = _github_headers(cfg["token"])
    try:
        old_raw, sha, read_status = _github_read_backup()
        if read_status.startswith("ERROR"):
            return "SAVE FAILED — " + read_status

        if old_raw and hashlib.sha256(old_raw).digest() == hashlib.sha256(raw).digest():
            return f"CURRENT — {len(memory):,} rows already stored in GitHub"

        payload = {
            "message": "Update BTC audit persistent backup",
            "content": base64.b64encode(raw).decode("ascii"),
            "branch": cfg["branch"],
        }
        if sha:
            payload["sha"] = sha

        r = requests.put(url, headers=headers, json=payload, timeout=60)
        if r.status_code not in (200, 201):
            detail = r.text[:500].replace("\n", " ")
            return f"SAVE FAILED — GitHub HTTP {r.status_code}: {detail}"

        # Verify immediately. This catches permissions/path/branch problems now,
        # rather than after the user leaves the website.
        verify_raw, _verify_sha, verify_status = _github_read_backup()
        if not verify_raw:
            return f"SAVE UNVERIFIED — write returned HTTP {r.status_code}; {verify_status}"
        try:
            verify = read_cache_csv(io.BytesIO(verify_raw))
            vrows = len(verify)
            vcols = set(map(str, verify.columns))
            lcols = set(map(str, memory.columns))
        except Exception:
            vrows = -1
            vcols = set()
            lcols = set(map(str, memory.columns))
        if vrows != len(memory) or vcols != lcols:
            missing_cols = sorted(lcols - vcols)[:8]
            return (f"SAVE UNVERIFIED — local {len(memory):,} dates/{len(lcols):,} columns; "
                    f"remote {vrows if vrows >= 0 else 'unreadable'} dates/{len(vcols):,} columns; "
                    f"missing remotely: {missing_cols if missing_cols else 'none'}")
        return f"SAVED + VERIFIED — {len(memory):,} unique dates / {len(lcols):,} columns in durable GitHub master"
    except Exception as e:
        return f"SAVE FAILED — {type(e).__name__}: {e}"



def download_button_no_state_change(label, data, file_name, mime, **kwargs):
    """Render a download that does not intentionally mutate audit state.

    Newer Streamlit versions support on_click='ignore', which avoids a rerun.
    Older versions fall back to the standard download button; any rerun remains safe
    because GitHub is the transactional source of truth.
    """
    try:
        import inspect
        if "on_click" in inspect.signature(st.download_button).parameters:
            kwargs.setdefault("on_click", "ignore")
    except Exception:
        pass
    return st.download_button(label, data, file_name, mime, **kwargs)

def _pick(frame, aliases):
    if frame is None or frame.empty:
        return None
    lower = {str(c).lower(): c for c in frame.columns}
    for a in aliases:
        if a.lower() in lower:
            return lower[a.lower()]
    for a in aliases:
        for c in frame.columns:
            if a.lower() in str(c).lower():
                return c
    for c in frame.columns:
        if str(c).lower() in {"d", "date", "day", "thedate", "unixts"}:
            continue
        s = pd.to_numeric(frame[c], errors="coerce")
        if s.notna().sum() >= max(3, int(0.5 * len(frame))):
            return c
    return None


def _normalise_date_index(df):
    if df is None or df.empty:
        return pd.DataFrame()
    out = df.copy()
    if "date" in out.columns:
        d = pd.to_datetime(out["date"], utc=True, errors="coerce")
        out = out.drop(columns=["date"])
    else:
        d = pd.to_datetime(out.index, utc=True, errors="coerce")
    out.index = d
    out.index.name = "date"
    out = out[~out.index.isna()].sort_index()
    return out.loc[~out.index.duplicated(keep="last")]


def read_cache_csv(file_or_path):
    try:
        df = pd.read_csv(file_or_path)
    except Exception:
        return pd.DataFrame()
    if "date" not in df.columns:
        return pd.DataFrame()
    return _normalise_date_index(df)


def combine_caches(*frames):
    frames = [f for f in frames if f is not None and not f.empty]
    if not frames:
        return pd.DataFrame()
    out = pd.concat(frames, axis=0, sort=False)
    # Multiple cache files can cover different columns/dates. Collapse duplicates by
    # taking the last non-null observation per column for each date.
    out = out.groupby(out.index).last().sort_index()
    out.index.name = "date"
    return out


def save_runtime_cache(cache):
    if cache is None or cache.empty:
        return
    try:
        CACHE_DIR.mkdir(parents=True, exist_ok=True)
        tmp = cache.copy()
        tmp.index.name = "date"
        tmp.reset_index().to_csv(BUNDLED_CACHE, index=False)
    except Exception:
        # Runtime may be read-only. Download button still works.
        pass


def save_runtime_master_cache(cache):
    """Best-effort persistence of the reusable master on-chain cache."""
    if cache is None or cache.empty:
        return
    try:
        CACHE_DIR.mkdir(parents=True, exist_ok=True)
        tmp = cache.copy()
        tmp.index.name = "date"
        tmp.reset_index().to_csv(MASTER_CACHE, index=False)
    except Exception:
        # Streamlit Cloud may be ephemeral/read-only. The download button remains authoritative.
        pass


def master_dataset_count(frame):
    """Count BGeometrics catalogue datasets actually represented in a wide master frame."""
    if frame is None or frame.empty:
        return 0
    return sum(dataset_cached(frame, d) for d in MASTER_DATASETS)


def master_schema_text(frame):
    """Human-readable master shape. Rows are UNIQUE DATES, not total observations."""
    if frame is None or frame.empty:
        return "0 dates • 0 columns • 0 cached datasets"
    return f"{len(frame):,} unique dates • {len(frame.columns):,} columns • {master_dataset_count(frame)} cached datasets"


def save_audit_memory(*frames):
    """Transactional single-master persistence.

    GitHub is the durable source of truth. Before EVERY write we re-read the latest
    remote master and merge it with the caller's frames. This prevents a stale
    Streamlit session/rerun from overwriting newer columns that were already saved.
    The local CSV is only a speed cache.
    """
    latest_remote, remote_status = load_remote_audit_memory()
    memory = combine_caches(latest_remote, *frames)
    if memory.empty:
        return memory
    try:
        CACHE_DIR.mkdir(parents=True, exist_ok=True)
        tmp = memory.copy()
        tmp.index.name = "date"
        tmp.reset_index().to_csv(AUDIT_MEMORY, index=False)
    except Exception:
        pass
    status = save_remote_audit_memory(memory)
    st.session_state["audit_remote_save_status"] = status
    st.session_state["audit_master_schema"] = master_schema_text(memory)
    return memory


def audit_backup_frame(cache, base, existing_memory=None):
    return combine_caches(existing_memory, cache, base)


def dataset_cached(cache, ds):
    """True when this endpoint already has any locally cached observations.

    Deliberately conservative for quota protection: once an endpoint has been acquired,
    it is skipped by default even if BGeometrics only exposed a partial historical window.
    Existing datasets are refreshed only when the user explicitly opts in.
    """
    if cache is None or cache.empty:
        return False
    prefix = f"raw__{ds['endpoint'].replace('-', '_')}__"
    cols = [c for c in cache.columns if str(c).startswith(prefix)]
    if ds["label"] in cache.columns:
        cols.append(ds["label"])
    for c in cols:
        if pd.to_numeric(cache[c], errors="coerce").notna().any():
            return True
    return False


@st.cache_data(ttl=900, show_spinner=False)
def fetch_endpoint(endpoint, start_date, end_date, token):
    params = {
        "startday": pd.Timestamp(start_date).strftime("%Y-%m-%d"),
        "endday": pd.Timestamp(end_date).strftime("%Y-%m-%d"),
        "size": 10000,
    }
    h = HEADERS.copy()
    if token:
        h["Authorization"] = f"Bearer {token}"
        params["token"] = token

    r = requests.get(f"{BASE}/{endpoint}", params=params, headers=h, timeout=45)
    rate = parse_rate_headers(r.headers)

    if r.status_code == 429:
        raise RateLimitError(rate)
    if r.status_code in (401, 403):
        raise RuntimeError(f"BGeometrics authentication failed (HTTP {r.status_code}).")

    r.raise_for_status()
    payload = r.json()
    if isinstance(payload, dict):
        for k in ("data", "results", "items", "values", "_embedded"):
            v = payload.get(k)
            if isinstance(v, list):
                payload = v
                break
            if isinstance(v, dict):
                lists = [x for x in v.values() if isinstance(x, list)]
                if lists:
                    payload = lists[0]
                    break
    if isinstance(payload, dict):
        payload = [payload]

    rows = []
    if isinstance(payload, list):
        for item in payload:
            if not isinstance(item, dict):
                continue
            d = item.get("d") or item.get("date") or item.get("day") or item.get("theDate") or item.get("unixts")
            if d is None:
                continue
            z = dict(item)
            if str(d).isdigit() and len(str(d)) >= 10:
                z["date"] = pd.to_datetime(int(d), unit="s", utc=True, errors="coerce")
            else:
                z["date"] = pd.to_datetime(d, utc=True, errors="coerce")
            rows.append(z)
    if not rows:
        return pd.DataFrame(), rate
    return _normalise_date_index(pd.DataFrame(rows)), rate


def parse_rate_headers(headers):
    """Parse common quota headers without assuming BGeometrics uses one exact scheme."""
    def first(*names):
        for name in names:
            v = headers.get(name)
            if v not in (None, ""):
                return v
        return None

    limit = first("X-RateLimit-Limit", "RateLimit-Limit")
    remaining = first("X-RateLimit-Remaining", "RateLimit-Remaining")
    reset_raw = first("X-RateLimit-Reset", "RateLimit-Reset")
    retry_after = first("Retry-After")
    reset_local = None
    seconds_left = None

    # Retry-After may be seconds or an HTTP date. Prefer it on 429 when present.
    if retry_after:
        try:
            seconds_left = max(0, int(float(retry_after)))
            reset_local = dt.datetime.now(BRISBANE_TZ) + dt.timedelta(seconds=seconds_left)
        except Exception:
            try:
                from email.utils import parsedate_to_datetime
                x = parsedate_to_datetime(str(retry_after))
                if x.tzinfo is None:
                    x = x.replace(tzinfo=dt.timezone.utc)
                reset_local = x.astimezone(BRISBANE_TZ)
                seconds_left = max(0, int((reset_local - dt.datetime.now(BRISBANE_TZ)).total_seconds()))
            except Exception:
                pass

    if reset_local is None and reset_raw:
        try:
            rv = float(reset_raw)
            # Most APIs use Unix epoch seconds. Small values are sometimes seconds-to-reset.
            if rv > 10_000_000:
                reset_local = dt.datetime.fromtimestamp(rv, tz=dt.timezone.utc).astimezone(BRISBANE_TZ)
            else:
                reset_local = dt.datetime.now(BRISBANE_TZ) + dt.timedelta(seconds=max(0, rv))
            seconds_left = max(0, int((reset_local - dt.datetime.now(BRISBANE_TZ)).total_seconds()))
        except Exception:
            pass
    return {"limit": limit, "remaining": remaining, "reset_raw": reset_raw, "retry_after": retry_after,
            "reset_local": reset_local, "seconds_left": seconds_left}


def rate_text(rate):
    if not rate:
        return "Rate-limit headers not returned."
    bits = []
    if rate.get("remaining") is not None and rate.get("limit") is not None:
        bits.append(f"{rate['remaining']} of {rate['limit']} requests remaining")
    elif rate.get("remaining") is not None:
        bits.append(f"{rate['remaining']} requests remaining")
    if rate.get("reset_local") is not None:
        r = rate["reset_local"]
        bits.append(f"reset {r.strftime('%-I:%M:%S %p')} Brisbane time on {r.strftime('%d %b %Y')}")
        sec = rate.get("seconds_left")
        if sec is not None:
            h, rem = divmod(sec, 3600)
            m, ss = divmod(rem, 60)
            bits.append(f"about {h}h {m}m {ss}s remaining")
    return " · ".join(bits) if bits else "Reset time not supplied by BGeometrics."


class RateLimitError(RuntimeError):
    def __init__(self, rate):
        self.rate = rate or {}
        super().__init__("BGeometrics rate limit reached (HTTP 429). " + rate_text(self.rate))


def _extract_date_column(df):
    if df is None or df.empty:
        return pd.DataFrame()
    z = df.copy()
    for c in z.columns:
        if str(c).lower() in {"date", "d", "day", "thedate", "unixts", "timestamp"}:
            vals = z[c]
            if str(c).lower() in {"unixts", "timestamp"}:
                parsed = pd.to_datetime(pd.to_numeric(vals, errors="coerce"), unit="s", utc=True, errors="coerce")
            else:
                parsed = pd.to_datetime(vals, utc=True, errors="coerce")
            if parsed.notna().sum() >= max(1, int(0.5 * len(z))):
                z["date"] = parsed
                return _normalise_date_index(z)
    return pd.DataFrame()


def fetch_master_dataset(ds, start_date, end_date, token):
    endpoint = ds["endpoint"]
    h = HEADERS.copy()
    params = {}
    if token:
        h["Authorization"] = f"Bearer {token}"
        params["token"] = token

    if ds.get("csv"):
        r = requests.get(f"{BASE}/{endpoint}/csv", params=params, headers=h, timeout=90)
        rate = parse_rate_headers(r.headers)
        if r.status_code == 429:
            raise RateLimitError(rate)
        if r.status_code in (401, 403):
            raise RuntimeError(f"Authentication failed (HTTP {r.status_code})")
        r.raise_for_status()
        try:
            frame = pd.read_csv(io.StringIO(r.text))
            frame = _extract_date_column(frame)
        except Exception as exc:
            raise RuntimeError(f"Could not parse CSV export: {exc}")
    else:
        frame, rate = fetch_endpoint(endpoint, start_date, end_date, token)

    if frame is None or frame.empty:
        return pd.DataFrame(), rate

    # Keep every numeric field from the endpoint so the one-time download is reusable.
    raw = pd.DataFrame(index=frame.index)
    for c in frame.columns:
        if str(c).lower() in {"date", "d", "day", "thedate", "unixts", "timestamp"}:
            continue
        num = pd.to_numeric(frame[c], errors="coerce")
        if num.notna().sum() >= max(3, int(0.20 * len(frame))):
            clean = ''.join(ch.lower() if ch.isalnum() else '_' for ch in str(c)).strip('_')
            raw[f"raw__{endpoint.replace('-', '_')}__{clean}"] = num

    # Also create a simple named primary series where possible.
    primary = _pick(frame, ds.get("aliases", []))
    if primary is not None:
        raw[ds["label"]] = pd.to_numeric(frame[primary], errors="coerce")

    raw = raw.loc[(raw.index.date >= start_date) & (raw.index.date <= end_date)]
    return raw, rate


@st.cache_data(ttl=6 * 3600, show_spinner=False)
def fetch_coinmetrics_metric(metric, start_date, end_date):
    """Fetch one free/community Coin Metrics daily metric with pagination.

    Failure is non-fatal: the caller can continue with whatever free metrics are available.
    No BGeometrics token or request is used here.
    """
    params = {
        "assets": COINMETRICS_ASSET,
        "metrics": metric,
        "frequency": "1d",
        "page_size": 10000,
        "paging_from": "start",
        "start_time": pd.Timestamp(start_date).strftime("%Y-%m-%d"),
        "end_time": pd.Timestamp(end_date).strftime("%Y-%m-%d"),
    }
    url = f"{COINMETRICS_BASE}/timeseries/asset-metrics"
    rows = []
    while url:
        r = requests.get(url, params=params if "?" not in url else None, headers=HEADERS, timeout=60)
        r.raise_for_status()
        payload = r.json()
        rows.extend(payload.get("data", []))
        url = payload.get("next_page_url")
        params = None
    if not rows:
        return pd.Series(dtype=float)
    z = pd.DataFrame(rows)
    if "time" not in z.columns or metric not in z.columns:
        return pd.Series(dtype=float)
    z["date"] = pd.to_datetime(z["time"], utc=True, errors="coerce").dt.normalize()
    z[metric] = pd.to_numeric(z[metric], errors="coerce")
    z = z.dropna(subset=["date", metric]).drop_duplicates("date").sort_values("date")
    return z.set_index("date")[metric]


def _cm_get(metric, start_date, end_date, status_rows):
    try:
        x = fetch_coinmetrics_metric(metric, start_date, end_date)
        if x is None or x.empty:
            status_rows.append({"Free input": metric, "Status": "Unavailable / no rows"})
            return pd.Series(dtype=float)
        status_rows.append({"Free input": metric, "Status": f"OK — {len(x):,} daily rows"})
        return x
    except Exception as exc:
        status_rows.append({"Free input": metric, "Status": f"Unavailable: {str(exc)[:120]}"})
        return pd.Series(dtype=float)


def build_free_indicator_cache(start_date, end_date):
    """Build every indicator we can safely derive without BGeometrics.

    The function intentionally degrades gracefully. If a Community metric is unavailable,
    only dependent indicators are omitted; the audit still runs.
    """
    status_rows = []
    cm = {}
    # Free-first research archive: collect a broad set of Coin Metrics Community BTC
    # series. Unavailable metrics are skipped independently. Raw series are retained
    # with a cm__ prefix so future research can use them without another download.
    cm_metrics = (
        "PriceUSD", "RevNtv", "FeeTotNtv", "SplyCur",
        "CapMrktCurUSD", "CapRealUSD", "TxTfrValAdjUSD", "RevAllTimeUSD",
        "HashRate", "AdrActCnt", "TxCnt", "FeeTotUSD", "FeeMeanUSD",
        "IssContNtv", "IssTotNtv", "TxTfrCnt", "TxTfrValAdjNtv",
        "TxTfrValUSD", "TxTfrValNtv", "SplyAct1d", "SplyAct30d",
        "SplyAct90d", "SplyAct1yr", "NVTAdj", "NVTAdj90",
    )
    for metric in cm_metrics:
        cm[metric] = _cm_get(metric, start_date, end_date, status_rows)

    idx = pd.DatetimeIndex([])
    for x in cm.values():
        if x is not None and not x.empty:
            idx = idx.union(x.index)
    if len(idx) == 0:
        return pd.DataFrame(), status_rows

    raw = pd.DataFrame(index=idx.sort_values())
    for k, x in cm.items():
        if x is not None and not x.empty:
            raw[k] = x.reindex(raw.index)

    # Preserve every free raw input we successfully acquired. Prefixing prevents
    # collisions with derived/audit columns and records provenance in the one CSV.
    out = pd.DataFrame(index=raw.index)
    for c in raw.columns:
        out[f"cm__{c}"] = pd.to_numeric(raw[c], errors="coerce")

    # Puell Multiple: actual native issuance * price, divided by its trailing 365-day mean.
    issuance = pd.Series(np.nan, index=raw.index, dtype=float)
    issuance_source = None
    # Coin Metrics defines RevNtv as miner revenue = newly issued BTC + transaction fees.
    # Therefore RevNtv - FeeTotNtv isolates actual daily native issuance.
    if {"RevNtv", "FeeTotNtv"}.issubset(raw.columns):
        x = (pd.to_numeric(raw["RevNtv"], errors="coerce") - pd.to_numeric(raw["FeeTotNtv"], errors="coerce")).clip(lower=0)
        if x.notna().sum() >= 365:
            issuance = x
            issuance_source = "RevNtv - FeeTotNtv"
    if issuance_source is None and "SplyCur" in raw:
        x = pd.to_numeric(raw["SplyCur"], errors="coerce").diff().clip(lower=0)
        if x.notna().sum() >= 365:
            issuance = x
            issuance_source = "SplyCur.diff() proxy"

    if issuance_source is not None and "PriceUSD" in raw:
        issuance_usd = issuance * pd.to_numeric(raw["PriceUSD"], errors="coerce")
        out["Puell Multiple"] = issuance_usd / issuance_usd.rolling(365, min_periods=365).mean()
        status_rows.append({"Free input": "Puell Multiple", "Status": f"CALCULATED locally from {issuance_source} + PriceUSD"})
    else:
        status_rows.append({"Free input": "Puell Multiple", "Status": "Could not calculate — issuance/price inputs unavailable"})

    market = pd.to_numeric(raw.get("CapMrktCurUSD"), errors="coerce") if "CapMrktCurUSD" in raw else None
    realized = pd.to_numeric(raw.get("CapRealUSD"), errors="coerce") if "CapRealUSD" in raw else None
    transfer = pd.to_numeric(raw.get("TxTfrValAdjUSD"), errors="coerce") if "TxTfrValAdjUSD" in raw else None
    thermo = pd.to_numeric(raw.get("RevAllTimeUSD"), errors="coerce") if "RevAllTimeUSD" in raw else None
    supply = pd.to_numeric(raw.get("SplyCur"), errors="coerce") if "SplyCur" in raw else None

    if market is not None and realized is not None:
        out["MVRV"] = market / realized.replace(0, np.nan)
        out["NUPL"] = (market - realized) / market.replace(0, np.nan)
        status_rows.append({"Free input": "MVRV + NUPL", "Status": "CALCULATED locally from market cap + realized cap"})

    if market is not None and transfer is not None:
        out["NVT"] = market / transfer.replace(0, np.nan)
        transfer_90 = transfer.rolling(90, min_periods=75).mean()
        out["NVT Signal"] = market / transfer_90.replace(0, np.nan)
        status_rows.append({"Free input": "NVT + NVT Signal", "Status": "CALCULATED locally from market cap + adjusted transfer value"})

    if market is not None and thermo is not None:
        out["ThermoCap Multiple"] = market / thermo.replace(0, np.nan)
        status_rows.append({"Free input": "ThermoCap Multiple", "Status": "CALCULATED locally from market cap / cumulative miner revenue"})

    if realized is not None and thermo is not None and supply is not None:
        investor_cap = realized - thermo
        investor_price = investor_cap / supply.replace(0, np.nan)
        out["Investor Cap"] = investor_cap
        out["Investor Price"] = investor_price
        status_rows.append({"Free input": "Investor Cap + Investor Price", "Status": "CALCULATED locally from realized cap, thermo cap and supply"})

    out = out.replace([np.inf, -np.inf], np.nan)
    out.index.name = "date"
    return out, status_rows



@st.cache_data(ttl=6 * 3600, show_spinner=False)
def fetch_blockchain_source_history(start_date, end_date):
    """Capture the exact Blockchain.com BTC/USD source used by Production."""
    start_ts = pd.Timestamp(start_date, tz="UTC") if pd.Timestamp(start_date).tzinfo is None else pd.Timestamp(start_date).tz_convert("UTC")
    end_ts = pd.Timestamp(end_date, tz="UTC") if pd.Timestamp(end_date).tzinfo is None else pd.Timestamp(end_date).tz_convert("UTC")
    r = requests.get(
        "https://api.blockchain.info/charts/market-price",
        params={"timespan": "all", "format": "json", "sampled": "false"},
        headers={"User-Agent": "BTC-DCA-Simulator/3.4"},
        timeout=30,
    )
    r.raise_for_status()
    rows = []
    for point in r.json().get("values", []):
        try:
            ts = pd.to_datetime(float(point["x"]), unit="s", utc=True).normalize()
            value = float(point["y"])
            if value > 0 and start_ts.normalize() <= ts <= end_ts.normalize():
                rows.append((ts, value))
        except Exception:
            continue
    if not rows:
        return pd.DataFrame()
    out = pd.DataFrame(rows, columns=["date", "src__blockchain_btc_usd"]).drop_duplicates("date", keep="last").set_index("date").sort_index()
    return out


@st.cache_data(ttl=24 * 3600, show_spinner=False)
def fetch_frankfurter_source_history(start_date, end_date):
    """Capture the exact Frankfurter USD/AUD source used by Production."""
    url = f"https://api.frankfurter.app/{pd.Timestamp(start_date).strftime('%Y-%m-%d')}..{pd.Timestamp(end_date).strftime('%Y-%m-%d')}?from=USD&to=AUD"
    r = requests.get(url, headers={"User-Agent": "BTC-DCA-Simulator/3.4"}, timeout=30)
    r.raise_for_status()
    rows = []
    for day, vals in r.json().get("rates", {}).items():
        aud_per_usd = float(vals.get("AUD", 0) or 0)
        if aud_per_usd > 0:
            rows.append((pd.to_datetime(day, utc=True), 1.0 / aud_per_usd))
    if not rows:
        return pd.DataFrame()
    return pd.DataFrame(rows, columns=["date", "src__frankfurter_usd_per_aud"]).drop_duplicates("date", keep="last").set_index("date").sort_index()


def fetch_bgeometrics_production_sources(start_date, end_date, token):
    """Capture Production BGeometrics sources without letting one forbidden endpoint abort all others.

    BGeometrics can return HTTP 403 for an individual endpoint that is not included in the
    current account tier. That is not proof that the token itself is invalid. Each endpoint
    is therefore attempted independently, using the same fetch_endpoint() authentication
    path as the existing audit collector. Rate limits still stop the run immediately.
    """
    out = pd.DataFrame()
    statuses = []
    specs = [
        # Migration-critical inputs first so an optional endpoint cannot block them.
        ("mvrv-zscore", {"src__bgeometrics_mvrv_z": ["mvrvZScore", "mvrv_zscore", "zscore", "mvrvZ"]}),
        ("fear-greed", {"src__bgeometrics_fear_greed": ["fearGreed", "fearAndGreed", "fear_greed", "value", "score"]}),
        ("regime-score", {
            "src__bgeometrics_regime_score": ["regimeScore"],
            "src__bgeometrics_regime_delta_30d": ["regimeDelta30d"],
            "src__bgeometrics_regime_active_weight": ["activeWeight"],
            "src__bgeometrics_regime": ["regime"],
        }),
        # Optional parity/archive field. Production does not use this as its main BTC price feed.
        ("btc-price", {"src__bgeometrics_btc_price": ["price", "btcPrice", "btc_price", "value", "close"]}),
    ]

    for endpoint, mapping in specs:
        try:
            frame, rate = fetch_endpoint(endpoint, start_date, end_date, token)
        except RateLimitError:
            raise
        except Exception as exc:
            statuses.append({"Endpoint": endpoint, "Status": f"Unavailable — {exc}"})
            continue

        if frame is None or frame.empty:
            statuses.append({"Endpoint": endpoint, "Status": "No rows returned"})
            continue

        captured = 0
        for dest, aliases in mapping.items():
            col = _pick(frame, aliases)
            if col is None:
                continue
            series = frame[col].rename(dest)
            if dest != "src__bgeometrics_regime":
                series = pd.to_numeric(series, errors="coerce")
            out = out.join(series, how="outer") if not out.empty else series.to_frame()
            captured += int(series.notna().sum())

        statuses.append({
            "Endpoint": endpoint,
            "Status": f"Captured {captured:,} values" if captured else "Endpoint returned rows but expected fields were not found",
        })

    return (out.sort_index() if not out.empty else pd.DataFrame()), statuses

def puell_threshold_research(merged, total_capital=500000.0):
    """Causal Monday accumulation comparison for Puell thresholds in AUD.

    Same weekly AUD allowance enters each strategy. Threshold strategies hold unused
    allowance in cash and deploy ALL accumulated cash on an eligible Monday. Puell is
    attached using the last completed daily observation before Monday elsewhere.
    """
    required = {"btc_price_aud", "Puell Multiple"}
    if not required.issubset(merged.columns):
        return pd.DataFrame()
    z = merged[["btc_price_aud", "Puell Multiple"]].copy()
    z["btc_price_aud"] = pd.to_numeric(z["btc_price_aud"], errors="coerce")
    z["Puell Multiple"] = pd.to_numeric(z["Puell Multiple"], errors="coerce")
    z = z.dropna()
    if len(z) < 52:
        return pd.DataFrame()
    n = len(z)
    weekly = float(total_capital) / n
    rows = []

    plain_btc = float((weekly / z["btc_price_aud"]).sum())
    rows.append({"Strategy":"Plain Monday DCA", "BTC":plain_btc, "Deployed":total_capital, "Cash left":0.0, "Buy weeks":n})

    for threshold in (0.50, 0.40, 0.30):
        cash = btc = deployed = 0.0
        buys = 0
        for _, r in z.iterrows():
            cash += weekly
            if float(r["Puell Multiple"]) <= threshold and cash > 0:
                btc += cash / float(r["btc_price_aud"])
                deployed += cash
                cash = 0.0
                buys += 1
        rows.append({"Strategy":f"Puell <= {threshold:.2f}", "BTC":btc, "Deployed":deployed, "Cash left":cash, "Buy weeks":buys})

    out = pd.DataFrame(rows)
    out["BTC vs plain %"] = (out["BTC"] / plain_btc - 1.0) * 100.0
    out["Avg buy price AUD"] = out["Deployed"] / out["BTC"].replace(0, np.nan)
    out["Deployed %"] = out["Deployed"] / float(total_capital) * 100.0
    return out


BOTTOM_ACCELERATOR_RULES = {
    "MVRV Z": ("MVRV Z-Score (positive control)", (0.50, 0.00, -0.25)),
    "Puell": ("Puell Multiple", (0.60, 0.50, 0.40)),
    "2Y MA": ("2Y MA Multiple", (0.80, 0.65, 0.55)),
    "200W MA": ("200W MA Multiple", (1.10, 0.95, 0.85)),
    "LTH MVRV": ("LTH MVRV", (1.40, 1.10, 0.90)),
    "Investor Price": ("Investor Price", (1.40, 1.20, 1.00)),
}


def _bottom_severity(value, thresholds):
    if not np.isfinite(value):
        return 0
    moderate, deep, extreme = thresholds
    if value < extreme:
        return 3
    if value < deep:
        return 2
    if value < moderate:
        return 1
    return 0


def _severity_boost(level):
    return {0: 1.00, 1: 1.25, 2: 1.50, 3: 2.00}.get(int(level), 1.00)


def _causal_remaining_capital_dca(frame, boost, total_capital=500000.0):
    """Sequential live-style allocator using only information available at each Monday.

    Each week starts from remaining capital / weeks remaining, then applies the frozen
    R2 DCA multiplier and the research accelerator. The known horizon is allowed; future
    indicator values/prices are never used. Final week deploys any remaining balance so
    every strategy is compared on equal total capital.
    """
    z = frame.copy()
    z["btc_price_aud"] = pd.to_numeric(z.get("btc_price_aud"), errors="coerce")
    z["dca_multiplier"] = pd.to_numeric(z.get("dca_multiplier", 1.0), errors="coerce").fillna(1.0)
    z = z[z["btc_price_aud"].gt(0)].copy()
    if z.empty:
        return None
    boost = pd.Series(boost, index=frame.index).reindex(z.index).fillna(1.0).astype(float)

    remaining = float(total_capital)
    btc = deployed = 0.0
    buy_weeks = 0
    n = len(z)
    for i, (idx, r) in enumerate(z.iterrows()):
        if remaining <= 1e-9:
            break
        weeks_left = n - i
        if weeks_left == 1:
            amount = remaining
        else:
            base = remaining / weeks_left
            amount = min(remaining, base * max(0.0, float(r["dca_multiplier"])) * max(0.0, float(boost.loc[idx])))
        if amount > 0:
            btc += amount / float(r["btc_price_aud"])
            deployed += amount
            remaining -= amount
            buy_weeks += 1
    return {
        "BTC": btc,
        "Deployed": deployed,
        "Cash left": remaining,
        "Buy weeks": buy_weeks,
        "Avg buy price AUD": deployed / btc if btc > 0 else np.nan,
    }


def bottom_accelerator_research(merged, total_capital=500000.0):
    """Test fixed, pre-declared bear-zone accelerators on top of frozen R2 Monday sizing."""
    if "btc_price_aud" not in merged.columns or "dca_multiplier" not in merged.columns:
        return pd.DataFrame(), pd.DataFrame()

    work = merged.copy()
    severity_cols = {}
    for label, (col, thresholds) in BOTTOM_ACCELERATOR_RULES.items():
        if col not in work.columns:
            continue
        x = pd.to_numeric(work[col], errors="coerce")
        sev = x.map(lambda v: _bottom_severity(v, thresholds) if np.isfinite(v) else 0)
        severity_cols[label] = sev

    base_boost = pd.Series(1.0, index=work.index)
    baseline = _causal_remaining_capital_dca(work, base_boost, total_capital)
    if baseline is None:
        return pd.DataFrame(), pd.DataFrame()

    rows = [{"Strategy": "Frozen R2 baseline", **baseline}]
    for label, sev in severity_cols.items():
        boost = sev.map(_severity_boost)
        result = _causal_remaining_capital_dca(work, boost, total_capital)
        if result is not None:
            rows.append({"Strategy": f"R2 + {label} accelerator", **result})

    # Consensus uses only the four longer-history inputs. Missing inputs do not vote.
    core = [x for x in ("MVRV Z", "Puell", "2Y MA", "200W MA") if x in severity_cols]
    consensus_boost = pd.Series(1.0, index=work.index, dtype=float)
    if len(core) >= 2:
        for idx in work.index:
            vals = []
            for label in core:
                source_col = BOTTOM_ACCELERATOR_RULES[label][0]
                if source_col in work.columns and pd.notna(work.at[idx, source_col]):
                    vals.append(float(severity_cols[label].loc[idx]))
            if len(vals) >= 2:
                avg = float(np.mean(vals))
                consensus_boost.loc[idx] = 2.00 if avg >= 2.0 else 1.50 if avg >= 1.5 else 1.25 if avg >= 1.0 else 1.00
        result = _causal_remaining_capital_dca(work, consensus_boost, total_capital)
        if result is not None:
            rows.append({"Strategy": "R2 + 4-factor consensus", **result})

    summary = pd.DataFrame(rows)
    base_btc = float(summary.loc[summary["Strategy"].eq("Frozen R2 baseline"), "BTC"].iloc[0])
    summary["BTC vs R2 %"] = (summary["BTC"] / base_btc - 1.0) * 100.0

    era_rows = []
    if "era" in work.columns:
        for era in ("2016–2019", "2020–2022", "2023–present"):
            part = work[work["era"].eq(era)].copy()
            if len(part) < 20:
                continue
            base_e = _causal_remaining_capital_dca(part, pd.Series(1.0, index=part.index), total_capital)
            if base_e is None:
                continue
            for label, sev in severity_cols.items():
                boost = sev.reindex(part.index).fillna(0).map(_severity_boost)
                rr = _causal_remaining_capital_dca(part, boost, total_capital)
                if rr is not None:
                    era_rows.append({"Era": era, "Strategy": label, "BTC vs R2 %": (rr["BTC"] / base_e["BTC"] - 1.0) * 100.0})
            if len(core) >= 2:
                rr = _causal_remaining_capital_dca(part, consensus_boost.reindex(part.index).fillna(1.0), total_capital)
                if rr is not None:
                    era_rows.append({"Era": era, "Strategy": "4-factor consensus", "BTC vs R2 %": (rr["BTC"] / base_e["BTC"] - 1.0) * 100.0})

    return summary, pd.DataFrame(era_rows)

def expanding_percentile(s, min_periods=52):
    x = pd.to_numeric(s, errors="coerce")
    vals = x.to_numpy(dtype=float)
    out = np.full(len(vals), np.nan)
    seen = []
    for i, v in enumerate(vals):
        if np.isfinite(v):
            seen.append(v)
        if len(seen) >= min_periods and np.isfinite(v):
            a = np.asarray(seen, dtype=float)
            out[i] = (np.sum(a < v) + 0.5 * np.sum(a == v)) / len(a)
    return pd.Series(out, index=s.index)


def spearman(a, b):
    z = pd.concat([pd.to_numeric(a, errors="coerce"), pd.to_numeric(b, errors="coerce")], axis=1).dropna()
    if len(z) < 20:
        return np.nan
    return z.iloc[:, 0].rank().corr(z.iloc[:, 1].rank())


def residualize_candidate(candidate, base):
    z = pd.concat([candidate, base], axis=1).dropna()
    out = pd.Series(np.nan, index=candidate.index, dtype=float)
    if len(z) < 30:
        return out
    y = z.iloc[:, 0].to_numpy(float)
    x = z.iloc[:, 1].to_numpy(float)
    X = np.column_stack([np.ones(len(x)), x])
    beta = np.linalg.lstsq(X, y, rcond=None)[0]
    out.loc[z.index] = y - X @ beta
    return out


def era_name(dt):
    y = pd.Timestamp(dt).year
    if y <= 2019:
        return "2016–2019"
    if y <= 2022:
        return "2020–2022"
    return "2023–present"


def prepare_frozen(uploaded):
    df = uploaded.copy() if isinstance(uploaded, pd.DataFrame) else pd.read_csv(uploaded)
    if isinstance(df.index, pd.DatetimeIndex) and "date" not in df.columns:
        df = df.reset_index()
    if "date" not in df.columns:
        raise ValueError("CSV must contain date column")
    df["date"] = pd.to_datetime(df["date"], utc=True, errors="coerce")
    df = df.dropna(subset=["date"]).set_index("date").sort_index()
    if "price_usd" not in df.columns:
        raise ValueError("CSV must contain price_usd")
    if "risk_score" not in df.columns:
        raise ValueError("CSV must contain risk_score")

    df["price_usd"] = pd.to_numeric(df["price_usd"], errors="coerce")
    df["risk_score"] = pd.to_numeric(df["risk_score"], errors="coerce")

    # Completely local, zero-API indicators from price history.
    # Use time-based rolling windows so they remain correct even if the frozen export has occasional missing dates.
    df["Mayer Multiple (200D)"] = df["price_usd"] / df["price_usd"].rolling("200D", min_periods=180).mean()
    df["2Y MA Multiple"] = df["price_usd"] / df["price_usd"].rolling("730D", min_periods=650).mean()

    m = df[df.index.weekday == 0].copy()
    if m.empty:
        m = df.resample("W-MON").first()
    m["200W MA Multiple"] = m["price_usd"] / m["price_usd"].rolling(200, min_periods=180).mean()

    for w in (4, 12, 26, 52):
        m[f"fwd_{w}w"] = m["price_usd"].shift(-w) / m["price_usd"] - 1
    m["era"] = [era_name(i) for i in m.index]
    return m


def attach_metric_asof(audit_index, daily_series, prior_completed_day=False):
    """Attach latest known daily value to each audit Monday.

    When prior_completed_day=True, the lookup cutoff is one second before the Monday
    timestamp, preventing a same-day/incomplete daily observation from entering a
    Monday decision. This is used for Puell accumulation research.
    """
    daily = pd.to_numeric(daily_series, errors="coerce").dropna().sort_index()
    if daily.empty:
        return pd.Series(np.nan, index=audit_index, dtype=float)
    audit_dates = pd.DatetimeIndex(audit_index)
    cutoffs = audit_dates - pd.Timedelta(seconds=1) if prior_completed_day else audit_dates
    left = pd.DataFrame({"audit_date": audit_dates, "lookup_date": cutoffs}).sort_values("lookup_date")
    right = daily.rename("value").reset_index().rename(columns={daily.index.name or "index": "metric_date"})
    right["metric_date"] = pd.to_datetime(right["metric_date"], utc=True, errors="coerce")
    right = right.dropna(subset=["metric_date"]).sort_values("metric_date")
    joined = pd.merge_asof(left, right, left_on="lookup_date", right_on="metric_date", direction="backward")
    joined = joined.sort_values("audit_date")
    return pd.Series(pd.to_numeric(joined["value"], errors="coerce").to_numpy(), index=audit_index)


def cache_span(cache, column):
    if cache.empty or column not in cache.columns:
        return None, None, 0
    s = pd.to_numeric(cache[column], errors="coerce").dropna()
    if s.empty:
        return None, None, 0
    return s.index.min(), s.index.max(), int(s.notna().sum())


def missing_ranges(cache, column, start, end):
    """Return up to two broad missing ranges (before/after cache coverage).

    We intentionally avoid filling interior one-day holes because Monday as-of matching
    tolerates sparse daily series and avoiding unnecessary API calls is the priority.
    """
    s0, s1, n = cache_span(cache, column)
    start = pd.Timestamp(start, tz="UTC") if pd.Timestamp(start).tzinfo is None else pd.Timestamp(start).tz_convert("UTC")
    end = pd.Timestamp(end, tz="UTC") if pd.Timestamp(end).tzinfo is None else pd.Timestamp(end).tz_convert("UTC")
    if n == 0:
        return [(start, end)]
    ranges = []
    if s0 > start:
        ranges.append((start, s0 - pd.Timedelta(days=1)))
    if s1 < end:
        ranges.append((s1 + pd.Timedelta(days=1), end))
    return [(a, b) for a, b in ranges if a <= b]


st.title("BTC Public Model Audit — Guided Mode V5.4")
st.caption(
    "Research only. This page is designed to be used in order: 1 → 2 → 3 → 4. "
    "Free/self-calculated indicators are built first; BGeometrics is used only for metrics we cannot reproduce safely. "
    "All supplied/acquired data is consolidated into one audit memory file; with GitHub storage configured it survives Streamlit restarts automatically."
)

st.info(
    "**Normal use:** ① check benchmark → ② confirm cache → ③ build free indicators → "
    "④ collect all still-missing specialist BTC history until quota stops → ⑤ run the audit."
)

with st.expander("What this page does / safety rules", expanded=False):
    st.markdown(
        """
- **Free first:** Puell, MVRV, NUPL, NVT, NVT Signal, ThermoCap Multiple and Investor Price are calculated locally from free Coin Metrics inputs.
- **Zero-API price indicators:** Mayer Multiple, 2Y MA Multiple and 200W MA Multiple come directly from the frozen price history.
- **Never asks BGeometrics for a metric on the free/self-calculated list.**
- **Never re-downloads a cached BGeometrics endpoint by default.**
- **Stops immediately on HTTP 429** and keeps what was already downloaded.
- **Uses the available BGeometrics quota until the provider reports exhaustion; every successful dataset is persisted immediately.
- **Does not change V5.9 Research or V5.8.2 Production.**
- The **Refresh already-cached datasets** option is hidden under Advanced settings and is OFF by default.
        """
    )

# -----------------------------------------------------------------------------
# STEP 1 — Frozen benchmark
# -----------------------------------------------------------------------------
st.header("① Benchmark")
st.caption("Use the frozen V5.9 R2 benchmark. The bundled file is used automatically when present.")

benchmark_upload = st.file_uploader(
    "Optional replacement benchmark (normally leave empty)",
    type=["csv"],
    key="frozen",
    help="Only upload a different btc_v5_9_r2_frozen.csv if we deliberately want to replace the bundled benchmark.",
)

local_memory = read_cache_csv(AUDIT_MEMORY) if AUDIT_MEMORY.exists() else pd.DataFrame()
remote_memory, remote_load_status = load_remote_audit_memory()
# GitHub is authoritative. Local runtime data is only an additional recovery/speed source.
# The transactional saver re-reads GitHub again before any write, so a stale session
# cannot overwrite newer remotely-saved columns.
memory = combine_caches(remote_memory, local_memory)

storage_cfg = audit_storage_config()
if storage_cfg["token"] and storage_cfg["repo"]:
    if remote_load_status.startswith("ERROR"):
        st.error("Persistent audit storage: " + remote_load_status)
    else:
        st.success("Persistent audit storage: " + remote_load_status)
else:
    st.warning(
        "Persistent audit storage is NOT configured. Streamlit Cloud deletes local runtime files when the app sleeps/restarts. "
        "Add AUDIT_GITHUB_TOKEN and AUDIT_GITHUB_REPO to Streamlit Secrets to make the single backup automatic and permanent."
    )

if benchmark_upload is not None:
    benchmark_source = benchmark_upload
elif FROZEN_BENCHMARK.exists():
    benchmark_source = FROZEN_BENCHMARK
elif (not memory.empty) and {"price_usd", "risk_score"}.issubset(memory.columns):
    benchmark_source = memory
else:
    benchmark_source = None

if benchmark_source is None:
    st.warning("Benchmark missing. Upload btc_v5_9_r2_frozen.csv once. The audit will remember it automatically after that.")
    st.stop()

try:
    base = prepare_frozen(benchmark_source)
    if benchmark_upload is not None:
        try:
            uploaded_raw = pd.read_csv(benchmark_upload)
            uploaded_raw.to_csv(FROZEN_BENCHMARK, index=False)
        except Exception:
            pass
        memory = save_audit_memory(memory, base)
except Exception as e:
    st.error(f"Benchmark could not be read: {e}")
    st.stop()

start = base.index.min().date()
end = base.index.max().date()
st.success(f"Benchmark ready: {start} → {end} • {len(base):,} Monday observations")

# -----------------------------------------------------------------------------
# STEP 2 — Cache status
# -----------------------------------------------------------------------------
st.header("② Existing data cache")
st.caption("The bundled cache is loaded first. Free/self-calculated data is added before any BGeometrics request is considered.")

bundled = read_cache_csv(BUNDLED_CACHE) if BUNDLED_CACHE.exists() else pd.DataFrame()
bundled_master = read_cache_csv(MASTER_CACHE) if MASTER_CACHE.exists() else pd.DataFrame()

with st.expander("Optional one-file recovery — normally leave empty", expanded=False):
    backup_restore = st.file_uploader(
        "Restore btc_audit_backup.csv",
        type=["csv"], key="audit_backup_restore",
        help="Only needed after a redeploy/move if the runtime memory file is gone. One file restores benchmark + cached audit history.",
    )

restored = read_cache_csv(backup_restore) if backup_restore is not None else pd.DataFrame()
cache = combine_caches(memory, bundled, bundled_master, restored)
if backup_restore is not None and not restored.empty:
    # A deliberate restore is a real state change, so persist it transactionally.
    memory = save_audit_memory(memory, restored, base)
else:
    # Ordinary Streamlit reruns must be read-only. Previously this called
    # save_audit_memory() on every rerun, which repeatedly downloaded the ~3 MB
    # GitHub master several times even when nothing had changed. That made the
    # page appear to blink/hang while the backend was doing redundant network I/O.
    memory = combine_caches(memory, cache, base)

cached_count = sum(dataset_cached(cache, d) for d in MASTER_DATASETS)
missing_count = len(MASTER_DATASETS) - cached_count
m1, m2, m3 = st.columns(3)
m1.metric("Datasets cached", cached_count)
m2.metric("Still missing", missing_count)
m3.metric("Unique dates in master", 0 if cache.empty else f"{len(cache):,}")
st.caption("Master storage is a WIDE time-series table: row count is unique dates, not the sum of all dataset observations. Adding a new indicator usually adds columns, so 5,900 dates can remain 5,900 while cached datasets increase.")

if cache.empty:
    st.warning("No cache is loaded yet. The next download would start from zero.")
else:
    st.success("Cache loaded. Cached endpoints will be skipped automatically.")

plan_rows = []
for d in MASTER_DATASETS:
    prefix = f"raw__{d['endpoint'].replace('-', '_')}__"
    endpoint_cols = [c for c in cache.columns if str(c).startswith(prefix)] if not cache.empty else []
    if (not cache.empty) and d["label"] in cache.columns:
        endpoint_cols.append(d["label"])
    union_index = pd.DatetimeIndex([])
    for c in dict.fromkeys(endpoint_cols):
        z = pd.to_numeric(cache[c], errors="coerce").dropna()
        union_index = union_index.union(z.index)
    plan_rows.append({
        "#": len(plan_rows) + 1,
        "Priority": d["priority"],
        "Dataset": d["label"],
        "Cached?": "YES — SKIP" if len(union_index) else "NO — DOWNLOAD",
        "Rows": len(union_index),
        "First": "—" if len(union_index) == 0 else union_index.min().date().isoformat(),
        "Last": "—" if len(union_index) == 0 else union_index.max().date().isoformat(),
    })
plan_df = pd.DataFrame(plan_rows)

with st.expander("Show numbered dataset list", expanded=False):
    st.dataframe(plan_df, use_container_width=True, hide_index=True)

backup_now = audit_backup_frame(cache, base, memory)
if st.session_state.get("audit_remote_save_status"):
    st.caption("Last persistent save: " + st.session_state["audit_remote_save_status"])
    if st.session_state.get("audit_master_schema"):
        st.caption("Current durable master: " + st.session_state["audit_master_schema"])

if not backup_now.empty:
    download_button_no_state_change(
        "DOWNLOAD SINGLE AUDIT BACKUP (NO STATE CHANGE)",
        backup_now.reset_index().to_csv(index=False).encode(),
        "btc_audit_backup.csv",
        "text/csv",
        key="single_audit_backup",
        help="One portable CSV containing the remembered benchmark plus all cached free/specialist audit history.",
    )

# -----------------------------------------------------------------------------
# STEP 3 — Build free/self-calculated indicators first
# -----------------------------------------------------------------------------
st.header("③ Build free / self-calculated indicators")
st.caption(
    "This step uses the frozen benchmark plus the free Coin Metrics Community API. "
    "It uses ZERO BGeometrics requests and is always attempted before specialist downloads."
)

price_local = ["Mayer Multiple (200D)", "2Y MA Multiple", "200W MA Multiple"]
st.success("Already calculated from benchmark price: " + ", ".join(price_local))

free_start = max(MASTER_START_DATE, dt.date(2010, 7, 18))
free_end = dt.date.today()
if st.button("BUILD / REFRESH FREE INDICATORS", type="primary", key="build_free_indicators"):
    with st.spinner("Building free indicators from Coin Metrics Community data..."):
        free_frame, free_status = build_free_indicator_cache(free_start, free_end)
    if free_status:
        st.dataframe(pd.DataFrame(free_status), use_container_width=True, hide_index=True)
    source_status = []
    try:
        blockchain_source = fetch_blockchain_source_history(free_start, free_end)
        if not blockchain_source.empty:
            free_frame = combine_caches(free_frame, blockchain_source)
            source_status.append({"Production source": "Blockchain.com BTC/USD", "Status": f"Captured {len(blockchain_source):,} rows"})
    except Exception as exc:
        source_status.append({"Production source": "Blockchain.com BTC/USD", "Status": f"Unavailable: {str(exc)[:120]}"})
    try:
        fx_source = fetch_frankfurter_source_history(free_start, free_end)
        if not fx_source.empty:
            free_frame = combine_caches(free_frame, fx_source)
            source_status.append({"Production source": "Frankfurter USD/AUD", "Status": f"Captured {len(fx_source):,} rows"})
    except Exception as exc:
        source_status.append({"Production source": "Frankfurter USD/AUD", "Status": f"Unavailable: {str(exc)[:120]}"})
    if source_status:
        st.dataframe(pd.DataFrame(source_status), use_container_width=True, hide_index=True)
    if free_frame is not None and not free_frame.empty:
        cache = combine_caches(cache, free_frame)
        save_runtime_master_cache(cache)
        save_runtime_cache(cache)
        memory = save_audit_memory(memory, cache, base)
        st.success(f"Free/source-preserving cache updated: {len(free_frame):,} daily rows. No BGeometrics quota used. Audit memory saved automatically.")
    else:
        st.warning("No free/source-preserving rows were available. Price-only indicators still work and BGeometrics was not contacted.")

# Recalculate specialist-cache counts after the free step.
cached_count = sum(dataset_cached(cache, d) for d in MASTER_DATASETS)
missing_count = len(MASTER_DATASETS) - cached_count

st.subheader("④A Preserve exact Production-source inputs")
st.caption(
    "Source-preserving archive for parity only. Blockchain.com and Frankfurter are captured in the free step above. "
    "This button captures the exact BGeometrics endpoints used by Production (btc-price, MVRV-Z, Fear & Greed, Regime Score) into dedicated src__ columns. "
    "It does not change Production and uses up to four BGeometrics requests."
)
source_token = get_token()
if st.button(
    "CAPTURE BGEOMETRICS PRODUCTION SOURCES (USES UP TO 4 REQUESTS)",
    disabled=not bool(source_token),
    key="capture_production_sources",
):
    try:
        with st.spinner("Capturing exact Production-source BGeometrics history..."):
            source_frame, source_rows = fetch_bgeometrics_production_sources(MASTER_START_DATE, dt.date.today(), source_token)
        if source_rows:
            st.dataframe(pd.DataFrame(source_rows), use_container_width=True, hide_index=True)
        if source_frame is not None and not source_frame.empty:
            cache = combine_caches(cache, source_frame)
            save_runtime_master_cache(cache)
            save_runtime_cache(cache)
            memory = save_audit_memory(memory, cache, base)
            st.success("Exact Production-source BGeometrics history saved to the durable central master in src__ columns.")
        else:
            st.warning("No source-preserving BGeometrics rows were returned.")
    except RateLimitError as exc:
        st.warning("BGeometrics quota reached before source capture completed. " + rate_text(exc.rate))
    except Exception as exc:
        st.error(f"Production-source capture failed: {exc}")

# -----------------------------------------------------------------------------
# STEP 4 — Acquire only specialist history still missing
# -----------------------------------------------------------------------------
st.header("④ BTC research collector — acquire all missing BGeometrics history")
st.caption("Free/self-calculated metrics are protected from BGeometrics requests. The collector uses the available quota only for specialist BTC datasets not already stored, saves each success immediately, and resumes where it stopped next time.")

token = get_token()
if token:
    st.success("BGeometrics token detected.")
else:
    st.warning("No BGeometrics token detected. Downloading is disabled, but the local-cache audit still works.")

if missing_count == 0:
    st.success("All planned datasets are already cached. No BGeometrics download is needed.")
else:
    next_missing = [d for d in sorted(MASTER_DATASETS, key=lambda x: (x["priority"], x["label"])) if not dataset_cached(cache, d)]
    preview = ", ".join(d["label"] for d in next_missing[:5])
    if len(next_missing) > 5:
        preview += ", …"
    st.info(f"Next eligible datasets: **{preview}**")

with st.expander("Advanced download settings — normally do not change", expanded=False):
    master_start = st.date_input("Master-history start date", value=MASTER_START_DATE, key="master_start")
    master_end = st.date_input("Master-history end date", value=dt.date.today(), key="master_end")
    refresh_existing = st.checkbox(
        "Refresh already-cached datasets (USES QUOTA)",
        value=False,
        key="refresh_existing_master",
        help="Leave OFF. This bypasses the quota guard for deliberate refresh/retry work only.",
    )

st.caption(
    f"Quota guard active: **{cached_count} cached endpoints will not be requested again**. "
    f"Only {missing_count} missing endpoints are eligible."
)

if st.button(
    "COLLECT ALL MISSING DATA UNTIL QUOTA STOPS",
    type="primary",
    disabled=(not bool(token)) or (missing_count == 0),
    key="master_download",
):
    master_rows = []
    master_rate = None
    master_limited = False
    requests_made = 0
    for ds in sorted(MASTER_DATASETS, key=lambda x: (x["priority"], x["label"])):
        already = dataset_cached(cache, ds)
        if already and not refresh_existing:
            continue
        try:
            frame, master_rate = fetch_master_dataset(ds, master_start, master_end, token)
            requests_made += 1
            if frame.empty:
                status = "No usable rows returned"
            else:
                cache = combine_caches(cache, frame)
                a, b = frame.index.min().date(), frame.index.max().date()
                status = f"Saved {len(frame):,} rows ({a} → {b})"
            save_runtime_master_cache(cache)
            save_runtime_cache(cache)
            memory = save_audit_memory(memory, cache, base)
            # Rebuild working cache from the exact transactional master returned by the saver.
            cache = combine_caches(memory, cache)
            durable = st.session_state.get("audit_remote_save_status", "save status unavailable")
            status = status + " | " + master_schema_text(memory) + " | " + durable
            master_rows.append({"Dataset": ds["label"], "Status": status})

            time.sleep(1.2)
        except RateLimitError as exc:
            master_rate = exc.rate
            master_limited = True
            master_rows.append({"Dataset": ds["label"], "Status": "HTTP 429 — stopped immediately"})
            break
        except Exception as exc:
            master_rows.append({"Dataset": ds["label"], "Status": f"Error: {str(exc)[:180]}"})

    st.write(f"**API requests used this batch: {requests_made}**")
    if master_rows:
        st.dataframe(pd.DataFrame(master_rows), use_container_width=True, hide_index=True)
    if master_rate:
        st.info("BGeometrics quota: " + rate_text(master_rate))
    if master_limited:
        st.warning("Quota reached. Everything downloaded before the 429 is already saved permanently. If BGeometrics supplied a reset time it is shown above in Brisbane time; otherwise the provider did not expose one. Run this same collector later and all cached datasets will be skipped automatically.")


# -----------------------------------------------------------------------------
# STEP 5 — Audit
# -----------------------------------------------------------------------------
st.header("⑤ Run the research audit")
st.caption(
    "This uses the data currently available. It may be run even when some datasets are still missing. "
    "A partial result is not treated as a final strategy decision."
)

use_api = False  # Important: Step 4 is cache-only. Step 3 is the only place allowed to spend quota.

if not st.button("RUN AUDIT USING CACHED DATA", type="primary", key="run_audit"):
    st.stop()

merged = base.copy()
fetch_status = []
rate_limited = False
last_rate_info = None

for name, (endpoint, aliases) in CANDIDATES.items():
    # Price-derived candidates are already in the frozen benchmark.
    if name in merged.columns and pd.to_numeric(merged[name], errors="coerce").notna().any():
        obs = int(pd.to_numeric(merged[name], errors="coerce").notna().sum())
        status = "Self-calculated from frozen benchmark — no API call"
        fetch_status.append((name, endpoint, obs, status))
        continue

    local_series = pd.Series(dtype=float)
    if not cache.empty and name in cache.columns:
        local_series = pd.to_numeric(cache[name], errors="coerce").dropna().sort_index()

    if not local_series.empty:
        merged[name] = attach_metric_asof(merged.index, local_series, prior_completed_day=(name == "Puell Multiple"))
        obs = int(merged[name].notna().sum())
        status = "Free/local cache — no BGeometrics call" if name in FREE_FIRST_CANDIDATES else "BGeometrics cache only — no API call"
    else:
        obs = 0
        if name in FREE_FIRST_CANDIDATES:
            status = "Free/self source not built or unavailable — BGeometrics BLOCKED"
        else:
            status = "Not in specialist cache yet"
    fetch_status.append((name, endpoint, obs, status))

if "Investor Price" in merged.columns:
    merged["Investor Price"] = merged["price_usd"] / pd.to_numeric(merged["Investor Price"], errors="coerce")

st.header("⑥ Audit data coverage")
status_df = pd.DataFrame(fetch_status, columns=["Candidate", "Endpoint", "Monday observations", "Status"])
st.dataframe(status_df, use_container_width=True, hide_index=True)
if rate_limited:
    st.warning(
        "BGeometrics reached its rate limit, so further API requests were stopped. "
        "The audit continues below using all locally cached observations already available."
    )
if last_rate_info:
    st.info("BGeometrics quota: " + rate_text(last_rate_info))

st.subheader("Puell accumulation threshold research")
st.caption(
    "Causal equal-contribution test: weekly capital accumulates in cash and is deployed only when Puell is at/below the threshold. "
    "No future qualifying dates are used to size a purchase. Research only; this does not change Production."
)
puell_bt = puell_threshold_research(merged, total_capital=500000.0)
if puell_bt.empty:
    st.info("Puell threshold test will appear once the free Puell series has enough history.")
else:
    st.dataframe(
        puell_bt.style.format({
            "BTC":"{:.6f}", "Deployed":"${:,.0f}", "Cash left":"${:,.0f}",
            "BTC vs plain %":"{:+.2f}%", "Avg buy price AUD":"${:,.0f}", "Deployed %":"{:.1f}%"
        }),
        use_container_width=True, hide_index=True,
    )

st.subheader("Bottom-zone accelerator research — on top of frozen R2")
st.caption(
    "Fixed pre-declared thresholds; moderate/deep/extreme zones add 1.25x/1.50x/2.00x to the frozen R2 Monday sizing. "
    "Allocator is sequential: remaining capital / weeks remaining × current R2 multiplier × current accelerator. "
    "No future indicator values are used and every strategy is compared on the same AUD 500,000 capital."
)
accel_summary, accel_eras = bottom_accelerator_research(merged, total_capital=500000.0)
if accel_summary.empty:
    st.info("Accelerator test requires btc_price_aud and dca_multiplier in the frozen benchmark.")
else:
    st.dataframe(
        accel_summary.style.format({
            "BTC":"{:.6f}", "Deployed":"${:,.0f}", "Cash left":"${:,.0f}",
            "Avg buy price AUD":"${:,.0f}", "BTC vs R2 %":"{:+.2f}%"
        }),
        use_container_width=True, hide_index=True,
    )
    if not accel_eras.empty:
        st.caption("Era robustness — BTC accumulation edge versus frozen R2 within each era")
        pivot_accel = accel_eras.pivot(index="Strategy", columns="Era", values="BTC vs R2 %").reset_index()
        st.dataframe(
            pivot_accel.style.format({c:"{:+.2f}%" for c in pivot_accel.columns if c != "Strategy"}),
            use_container_width=True, hide_index=True,
        )

horizons = (4, 12, 26, 52)
rows = []
era_rows = []
for name in CANDIDATES:
    if name not in merged.columns:
        continue
    raw = pd.to_numeric(merged[name], errors="coerce")
    if raw.notna().sum() < 52:
        continue
    risk = expanding_percentile(raw, min_periods=52)
    base_r = pd.to_numeric(merged["risk_score"], errors="coerce")
    resid = residualize_candidate(risk, base_r)
    redundancy = spearman(risk, base_r)
    row = {"Candidate": name, "Coverage": int(raw.notna().sum()), "Redundancy vs R2": redundancy}
    stable_eras = 0
    for h in horizons:
        row[f"{h}w candidate"] = spearman(risk, merged[f"fwd_{h}w"])
        row[f"{h}w residual"] = spearman(resid, merged[f"fwd_{h}w"])
    for era in ("2016–2019", "2020–2022", "2023–present"):
        mask = merged["era"].eq(era)
        v = spearman(risk[mask], merged.loc[mask, "fwd_26w"])
        era_rows.append({"Candidate": name, "Era": era, "26w Spearman": v})
        if np.isfinite(v) and v < 0:
            stable_eras += 1
    row["Negative 26w eras"] = stable_eras
    c26, c52 = row["26w candidate"], row["52w candidate"]
    r26, r52 = row["26w residual"], row["52w residual"]
    passes = (
        np.isfinite(c26) and c26 < 0
        and np.isfinite(c52) and c52 < 0
        and ((np.isfinite(r26) and r26 < 0) or (np.isfinite(r52) and r52 < 0))
        and stable_eras >= 2
    )
    row["Screen"] = "PASS TO NEXT TEST" if passes else "NO PROMOTION"
    rows.append(row)

res = pd.DataFrame(rows)
if not res.empty:
    res["Residual avg 26/52"] = res[["26w residual", "52w residual"]].mean(axis=1)
    res = res.sort_values(["Screen", "Residual avg 26/52"], ascending=[True, True])

st.header("⑦ Screening results")
st.caption(
    "For a risk/valuation metric, more negative future-return Spearman is better. "
    "Residual tests whether the candidate adds information beyond frozen R2."
)
show_cols = [
    "Candidate", "Coverage", "Redundancy vs R2", "4w candidate", "12w candidate",
    "26w candidate", "52w candidate", "26w residual", "52w residual",
    "Negative 26w eras", "Screen",
]
if res.empty:
    st.warning(
        "The local cache does not yet contain enough history for a full screening result. "
        "Run the free indicator builder first; only the remaining specialist metrics depend on the BGeometrics cache."
    )
else:
    existing = [c for c in show_cols if c in res.columns]
    fmt = {c: "{:+.3f}" for c in existing if c not in {"Candidate", "Coverage", "Negative 26w eras", "Screen"}}
    st.dataframe(res[existing].style.format(fmt), use_container_width=True, hide_index=True)

st.header("⑧ Era stability — 26 week horizon")
era_df = pd.DataFrame(era_rows)
if not era_df.empty:
    pivot = era_df.pivot(index="Candidate", columns="Era", values="26w Spearman").reset_index()
    st.dataframe(
        pivot.style.format({c: "{:+.3f}" for c in pivot.columns if c != "Candidate"}),
        use_container_width=True,
        hide_index=True,
    )

st.header("⑨ Research verdict")
sufficient = 0 if res.empty else int(res["Coverage"].ge(52).sum())
total_candidates = len(CANDIDATES)
if sufficient < total_candidates:
    st.info(f"Audit incomplete — {sufficient} of {total_candidates} candidates have sufficient history. No strategy conclusion yet.")
if res.empty:
    st.info("No candidate is promoted. We simply need more cached history before judging them.")
else:
    passed = res[res["Screen"].eq("PASS TO NEXT TEST")]
    if passed.empty and sufficient >= total_candidates:
        st.success("No public candidate cleared the conservative information screen. Keep V5.9 simple.")
    elif passed.empty:
        st.caption("No tested candidate has cleared the screen so far, but the audit is not complete.")
    else:
        st.warning("These candidates earned only a NEXT TEST, not production inclusion:")
        st.dataframe(
            passed[["Candidate", "Redundancy vs R2", "26w candidate", "52w candidate", "26w residual", "52w residual", "Negative 26w eras"]],
            use_container_width=True,
            hide_index=True,
        )
        st.info("Next stage is causal equal-capital DCA testing. Nothing is promoted automatically.")

out = merged.copy()
out.index.name = "date"
download_button_no_state_change(
    "DOWNLOAD MERGED AUDIT DATA (NO STATE CHANGE)",
    out.reset_index().to_csv(index=False).encode(),
    "btc_public_model_audit_merged.csv",
    "text/csv",
)
download_button_no_state_change(
    "DOWNLOAD AUDIT SUMMARY (NO STATE CHANGE)",
    res.to_csv(index=False).encode(),
    "btc_public_model_audit_summary.csv",
    "text/csv",
)

st.caption(
    "Persistence note: GitHub btc_audit_backup.csv is the single durable source of truth. Every write first re-reads and merges the latest remote master, then saves and verifies BOTH dates and columns. Downloads do not intentionally change state. The local cache is only a speed/recovery copy."
)
