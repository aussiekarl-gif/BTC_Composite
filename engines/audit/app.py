import os
import time
import io
import json
import datetime as dt
from pathlib import Path
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd
import requests
import streamlit as st

BASE = "https://bitcoin-data.com/v1"
HEADERS = {"User-Agent": "Mozilla/5.0", "Accept": "application/json"}

# Research candidates only. Nothing here changes Production or V5.9 Research.
CANDIDATES = {
    "MVRV Z-Score (positive control)": ("mvrv-zscore", ["mvrvZScore", "mvrv_zscore", "zscore", "mvrvZ", "value"]),
    "Puell Multiple": ("puell-multiple", ["puellMultiple", "puell_multiple", "puell", "value"]),
    "VDD Multiple": ("vdd-multiple", ["vddMultiple", "vdd_multiple", "value"]),
    "STH MVRV": ("sth-mvrv", ["sthMvrv", "sth_mvrv", "mvrv", "value"]),
    "LTH MVRV": ("lth-mvrv", ["lthMvrv", "lth_mvrv", "mvrv", "value"]),
    "aSOPR": ("asopr", ["asopr", "aSOPR", "value"]),
    "% Supply / UTXOs in Profit": ("profit-loss", ["profitLoss", "profit_loss", "profit", "value", "percent", "pct"]),
    "NVT Signal": ("nvts", ["nvts", "nvtSignal", "nvt_signal", "value"]),
    "Investor Price": ("investor-price", ["investorPrice", "investor_price", "price", "value"]),
}

# One-time master-history acquisition plan. These are DATA candidates, not strategy inputs.
# Priority 1 fills the current audit gaps; priorities 2-3 preserve useful adjacent on-chain
# families so future research does not need to re-download history. CSV support below is
# based on the BGeometrics API schema already saved with this project.
MASTER_DATASETS = [
    # Priority 1 — current audit gaps
    {"label":"Puell Multiple", "endpoint":"puell-multiple", "priority":1, "category":"Miner valuation", "csv":False, "aliases":["puellMultiple","puell_multiple","puell","value"]},
    {"label":"VDD Multiple", "endpoint":"vdd-multiple", "priority":1, "category":"Coin-day activity", "csv":True, "aliases":["vddMultiple","vdd_multiple","value"]},
    {"label":"VDD", "endpoint":"vdd", "priority":1, "category":"Coin-day activity", "csv":True, "aliases":["vdd","value"]},
    {"label":"STH MVRV", "endpoint":"sth-mvrv", "priority":1, "category":"Holder valuation", "csv":False, "aliases":["sthMvrv","sth_mvrv","mvrv","value"]},
    {"label":"LTH MVRV", "endpoint":"lth-mvrv", "priority":1, "category":"Holder valuation", "csv":False, "aliases":["lthMvrv","lth_mvrv","mvrv","value"]},
    {"label":"aSOPR", "endpoint":"asopr", "priority":1, "category":"Spent-profit behaviour", "csv":False, "aliases":["asopr","aSOPR","value"]},
    {"label":"UTXOs in Profit %", "endpoint":"utxos-in-profit-pct", "priority":1, "category":"Profitability", "csv":False, "aliases":["utxosInProfitPct","utxos_in_profit_pct","percent","pct","value"]},
    {"label":"Supply in Profit %", "endpoint":"supply-in-profit-pct", "priority":1, "category":"Profitability", "csv":True, "aliases":["supplyInProfitPct","supply_in_profit_pct","percent","pct","value"]},
    {"label":"NVT Signal", "endpoint":"nvt-signal", "priority":1, "category":"Network valuation", "csv":False, "aliases":["nvtSignal","nvt_signal","nvts","value"]},
    {"label":"Investor Price", "endpoint":"investor-price", "priority":1, "category":"Cost-basis valuation", "csv":False, "aliases":["investorPrice","investor_price","price","value"]},

    # Priority 2 — close relatives / strong research controls
    {"label":"MVRV", "endpoint":"mvrv", "priority":2, "category":"Valuation", "csv":False, "aliases":["mvrv","value"]},
    {"label":"STH MVRV Z-Score", "endpoint":"sth-mvrv-zscore", "priority":2, "category":"Holder valuation", "csv":False, "aliases":["sthMvrvZscore","zscore","value"]},
    {"label":"LTH MVRV Z-Score", "endpoint":"lth-mvrv-zscore", "priority":2, "category":"Holder valuation", "csv":False, "aliases":["lthMvrvZscore","zscore","value"]},
    {"label":"SOPR", "endpoint":"sopr", "priority":2, "category":"Spent-profit behaviour", "csv":False, "aliases":["sopr","value"]},
    {"label":"STH SOPR", "endpoint":"sth-sopr", "priority":2, "category":"Spent-profit behaviour", "csv":False, "aliases":["sthSopr","sopr_sth","sopr","value"]},
    {"label":"LTH SOPR", "endpoint":"lth-sopr", "priority":2, "category":"Spent-profit behaviour", "csv":False, "aliases":["lthSopr","sopr_lth","sopr","value"]},
    {"label":"Realized Price", "endpoint":"realized-price", "priority":2, "category":"Cost basis", "csv":False, "aliases":["realizedPrice","realized_price","price","value"]},
    {"label":"STH Realized Price", "endpoint":"sth-realized-price", "priority":2, "category":"Cost basis", "csv":False, "aliases":["sthRealizedPrice","realized_price","price","value"]},
    {"label":"LTH Realized Price", "endpoint":"lth-realized-price", "priority":2, "category":"Cost basis", "csv":False, "aliases":["lthRealizedPrice","realized_price","price","value"]},
    {"label":"CVDD", "endpoint":"cvdd", "priority":2, "category":"Long-cycle floor", "csv":True, "aliases":["cvdd","price","value"]},
    {"label":"CDD", "endpoint":"cdd", "priority":2, "category":"Coin-day activity", "csv":True, "aliases":["cdd","value"]},
    {"label":"Supply Adjusted CDD", "endpoint":"supply-adjusted-cdd", "priority":2, "category":"Coin-day activity", "csv":True, "aliases":["supplyAdjustedCdd","cdd","value"]},
    {"label":"Liveliness", "endpoint":"liveliness", "priority":2, "category":"Coin-day activity", "csv":True, "aliases":["liveliness","value"]},
    {"label":"Average Dormancy", "endpoint":"average-dormancy", "priority":2, "category":"Coin-day activity", "csv":True, "aliases":["averageDormancy","dormancy","value"]},
    {"label":"RHODL Ratio", "endpoint":"rhodl-ratio", "priority":2, "category":"Holder age valuation", "csv":False, "aliases":["rhodlRatio","rhodl_ratio","value"]},
    {"label":"NVT", "endpoint":"nvt", "priority":2, "category":"Network valuation", "csv":False, "aliases":["nvt","value"]},
    {"label":"NVT Z-Score", "endpoint":"nvt-zscore", "priority":2, "category":"Network valuation", "csv":False, "aliases":["nvtZscore","zscore","value"]},

    # Priority 3 — preserve broader context while quota permits
    {"label":"Investor Cap", "endpoint":"investor-cap", "priority":3, "category":"Cost-basis valuation", "csv":False, "aliases":["investorCap","investor_cap","value"]},
    {"label":"Realized Cap", "endpoint":"realized-cap", "priority":3, "category":"Cost basis", "csv":True, "aliases":["realizedCap","realized_cap","value"]},
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


def get_token():
    try:
        t = st.secrets.get("BGEOMETRICS_TOKEN", "")
        if t:
            return str(t).strip()
    except Exception:
        pass
    return os.getenv("BGEOMETRICS_TOKEN", "").strip()


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
    limit = headers.get("X-RateLimit-Limit")
    remaining = headers.get("X-RateLimit-Remaining")
    reset_raw = headers.get("X-RateLimit-Reset")
    reset_local = None
    seconds_left = None
    if reset_raw:
        try:
            ts = int(float(reset_raw))
            reset_local = dt.datetime.fromtimestamp(ts, tz=dt.timezone.utc).astimezone(BRISBANE_TZ)
            seconds_left = max(0, int((reset_local - dt.datetime.now(BRISBANE_TZ)).total_seconds()))
        except Exception:
            pass
    return {"limit": limit, "remaining": remaining, "reset_raw": reset_raw, "reset_local": reset_local, "seconds_left": seconds_left}


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
    return " · ".join(bits) if bits else "Rate-limit headers not returned."


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
    df = pd.read_csv(uploaded)
    if "date" not in df.columns:
        raise ValueError("CSV must contain date column")
    df["date"] = pd.to_datetime(df["date"], utc=True, errors="coerce")
    df = df.dropna(subset=["date"]).set_index("date").sort_index()
    if "price_usd" not in df.columns:
        raise ValueError("CSV must contain price_usd")
    if "risk_score" not in df.columns:
        raise ValueError("CSV must contain risk_score")
    m = df[df.index.weekday == 0].copy()
    if m.empty:
        m = df.resample("W-MON").first()
    m["price_usd"] = pd.to_numeric(m["price_usd"], errors="coerce")
    m["risk_score"] = pd.to_numeric(m["risk_score"], errors="coerce")
    for w in (4, 12, 26, 52):
        m[f"fwd_{w}w"] = m["price_usd"].shift(-w) / m["price_usd"] - 1
    m["era"] = [era_name(i) for i in m.index]
    return m


def attach_metric_asof(audit_index, daily_series):
    daily = pd.to_numeric(daily_series, errors="coerce").dropna().sort_index()
    if daily.empty:
        return pd.Series(np.nan, index=audit_index, dtype=float)
    left = pd.DataFrame({"audit_date": pd.DatetimeIndex(audit_index)}).sort_values("audit_date")
    right = daily.rename("value").reset_index().rename(columns={daily.index.name or "index": "metric_date"})
    right["metric_date"] = pd.to_datetime(right["metric_date"], utc=True, errors="coerce")
    right = right.dropna(subset=["metric_date"]).sort_values("metric_date")
    joined = pd.merge_asof(left, right, left_on="audit_date", right_on="metric_date", direction="backward")
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


st.title("BTC Broad Public Model Audit — Cache First")
st.caption(
    "Research only. Existing local data is used first; BGeometrics is contacted only for genuinely missing history. "
    "Nothing is promoted automatically into V5.9 or Production."
)

with st.expander("Why cache-first", expanded=True):
    st.markdown(
        """
- **No repeat downloads:** historical observations already stored locally are reused.
- **Incremental updates only:** when the API is available, only history before/after the stored range is requested.
- **Rate-limit safe:** if BGeometrics returns HTTP 429, the audit continues with whatever is already cached.
- **Portable cache:** download the consolidated cache and keep it with the website so future runs do not start from zero.
"""
    )

st.subheader("1. Frozen V5.9 benchmark")
uploaded = st.file_uploader("Upload btc_v5_9_r2_frozen.csv", type=["csv"], key="frozen")
if uploaded is None:
    st.info("Upload the frozen V5.9 R2 CSV to begin.")
    st.stop()

try:
    base = prepare_frozen(uploaded)
except Exception as e:
    st.error(str(e))
    st.stop()

start = base.index.min().date()
end = base.index.max().date()
st.write(f"Frozen sample: **{start} → {end}**, {len(base):,} Monday observations")

st.subheader("2. Local historical cache")
bundled = read_cache_csv(BUNDLED_CACHE) if BUNDLED_CACHE.exists() else pd.DataFrame()
extra_cache_file = st.file_uploader(
    "Optional: upload a previously downloaded public_model_cache.csv",
    type=["csv"],
    key="cache",
    help="Useful after a Streamlit redeploy or when moving the app to another machine.",
)
extra = read_cache_csv(extra_cache_file) if extra_cache_file is not None else pd.DataFrame()
cache = combine_caches(bundled, extra)

if cache.empty:
    st.warning("No local public-model cache found yet. The audit can still run, but missing metrics require BGeometrics.")
else:
    coverage_rows = []
    for name in CANDIDATES:
        a, b, n = cache_span(cache, name)
        coverage_rows.append({
            "Candidate": name,
            "Cached rows": n,
            "First cached": "—" if a is None else a.date().isoformat(),
            "Last cached": "—" if b is None else b.date().isoformat(),
        })
    st.dataframe(pd.DataFrame(coverage_rows), use_container_width=True, hide_index=True)

# Download is available even before an API run.
if not cache.empty:
    cache_bytes = cache.reset_index().to_csv(index=False).encode()
    st.download_button("Download current consolidated cache", cache_bytes, "public_model_cache.csv", "text/csv")

token = get_token()
if token:
    st.success("BGeometrics token detected. It will only be used for missing history.")
else:
    st.info("No BGeometrics token detected. You can still run a local-cache-only audit.")

use_api = st.checkbox("Fetch missing history from BGeometrics when quota is available", value=True, disabled=not bool(token))

st.subheader("2A. One-time master on-chain history acquisition")
st.caption(
    "Prepared for the next quota window. Each dataset is downloaded once, cached locally, and skipped on later runs. "
    "Priority 1 fills the current audit; priorities 2–3 preserve adjacent raw history for future research. "
    "Downloading a series does NOT add it to V5.9."
)
plan_df = pd.DataFrame([{
    "Priority": d["priority"], "Dataset": d["label"], "Category": d["category"],
    "Endpoint": d["endpoint"], "CSV export": "Yes" if d.get("csv") else "No / JSON"
} for d in MASTER_DATASETS]).sort_values(["Priority", "Category", "Dataset"])
st.dataframe(plan_df, use_container_width=True, hide_index=True)

master_start = st.date_input("Master-history start date", value=MASTER_START_DATE, key="master_start")
master_end = st.date_input("Master-history end date", value=dt.date.today(), key="master_end")
st.info(
    "Quota-safe behaviour: datasets are processed in priority order; already-cached datasets are skipped; "
    "the first HTTP 429 stops all further requests. The exact X-RateLimit-Reset header is converted to Brisbane time."
)

if st.button("Download next master-cache batch", disabled=not bool(token), key="master_download"):
    master_rows = []
    master_rate = None
    master_limited = False
    for ds in sorted(MASTER_DATASETS, key=lambda x: (x["priority"], x["label"])):
        prefix = f"raw__{ds['endpoint'].replace('-', '_')}__"
        already = (not cache.empty) and (
            any(str(c).startswith(prefix) for c in cache.columns) or ds["label"] in cache.columns
        )
        if already:
            master_rows.append({"Dataset": ds["label"], "Priority": ds["priority"], "Status": "Already cached — skipped"})
            continue
        try:
            frame, master_rate = fetch_master_dataset(ds, master_start, master_end, token)
            if frame.empty:
                status = "No usable rows returned"
            else:
                cache = combine_caches(cache, frame)
                a, b = frame.index.min().date(), frame.index.max().date()
                status = f"Saved {len(frame):,} rows ({a} → {b})"
            master_rows.append({"Dataset": ds["label"], "Priority": ds["priority"], "Status": status})
            save_runtime_cache(cache)
            # Be conservative when the service tells us the window is nearly empty.
            try:
                if master_rate and master_rate.get("remaining") is not None and int(master_rate["remaining"]) <= 1:
                    master_rows.append({"Dataset": "—", "Priority": "—", "Status": "Stopped with one request left as safety buffer"})
                    break
            except Exception:
                pass
            time.sleep(0.5)
        except RateLimitError as exc:
            master_rate = exc.rate
            master_limited = True
            master_rows.append({"Dataset": ds["label"], "Priority": ds["priority"], "Status": str(exc)})
            break
        except Exception as exc:
            master_rows.append({"Dataset": ds["label"], "Priority": ds["priority"], "Status": f"Error: {str(exc)[:180]}"})

    if master_rows:
        st.dataframe(pd.DataFrame(master_rows), use_container_width=True, hide_index=True)
    if master_rate:
        st.info("BGeometrics quota: " + rate_text(master_rate))
    if master_limited:
        st.warning("Quota exhausted. No more requests were sent. Run the same button after the displayed reset; cached datasets will be skipped automatically.")
    if not cache.empty:
        st.download_button(
            "Download master on-chain cache",
            cache.reset_index().to_csv(index=False).encode(),
            "btc_onchain_master_cache.csv",
            "text/csv",
            key="master_cache_download",
        )
        meta_rows=[]
        for ds in MASTER_DATASETS:
            cols=[c for c in cache.columns if str(c).startswith(f"raw__{ds['endpoint'].replace('-', '_')}__")]
            if ds["label"] in cache.columns:
                cols.append(ds["label"])
            if cols:
                sub=cache[cols].dropna(how="all")
                if not sub.empty:
                    meta_rows.append({"Dataset":ds["label"],"Endpoint":ds["endpoint"],"Priority":ds["priority"],"Columns saved":len(set(cols)),"Rows":len(sub),"First":sub.index.min().date().isoformat(),"Last":sub.index.max().date().isoformat()})
        if meta_rows:
            st.download_button(
                "Download master-cache inventory",
                pd.DataFrame(meta_rows).to_csv(index=False).encode(),
                "btc_onchain_master_cache_inventory.csv",
                "text/csv",
                key="master_inventory_download",
            )

st.divider()
if not st.button("Run cache-first public-model audit", type="primary"):
    st.stop()

merged = base.copy()
fetch_status = []
rate_limited = False
last_rate_info = None

for i, (name, (endpoint, aliases)) in enumerate(CANDIDATES.items(), start=1):
    # Start with whatever we already have.
    local_series = pd.Series(dtype=float)
    if not cache.empty and name in cache.columns:
        local_series = pd.to_numeric(cache[name], errors="coerce").dropna().sort_index()

    ranges = missing_ranges(cache, name, start, end)
    fetched_parts = []
    status_bits = []

    if ranges and use_api and token and not rate_limited:
        for a, b in ranges:
            try:
                f, rate_info = fetch_endpoint(endpoint, a.date(), b.date(), token)
                last_rate_info = rate_info
                c = _pick(f, aliases)
                if c is None:
                    status_bits.append(f"No numeric field for {a.date()}→{b.date()}")
                    continue
                s = pd.to_numeric(f[c], errors="coerce").dropna().rename(name)
                fetched_parts.append(s)
                status_bits.append(f"Fetched {len(s):,} rows {a.date()}→{b.date()}")
                time.sleep(0.35)
            except RateLimitError as e:
                last_rate_info = e.rate
                status_bits.append(str(e)[:220])
                rate_limited = True
                break
            except Exception as e:
                status_bits.append(str(e)[:220])

    # Merge local + freshly fetched series. Fresh data wins on duplicate dates.
    pieces = [s for s in [local_series] + fetched_parts if s is not None and not s.empty]
    if pieces:
        combined = pd.concat(pieces).groupby(level=0).last().sort_index()
        combined.name = name
        cache = combine_caches(cache, combined.to_frame())
        merged[name] = attach_metric_asof(merged.index, combined)
        obs = int(merged[name].notna().sum())
    else:
        obs = 0

    if obs and not status_bits:
        status = "Cache only"
    elif obs and status_bits:
        status = "Cache + " + "; ".join(status_bits)
    elif status_bits:
        status = "; ".join(status_bits)
    else:
        status = "No cached data"

    fetch_status.append((name, endpoint, obs, status))

# Persist any new observations for this runtime, and always make them downloadable.
save_runtime_cache(cache)

if "Investor Price" in merged.columns:
    merged["Investor Price"] = merged["price_usd"] / pd.to_numeric(merged["Investor Price"], errors="coerce")

st.subheader("3. Data coverage used in this run")
status_df = pd.DataFrame(fetch_status, columns=["Candidate", "Endpoint", "Monday observations", "Status"])
st.dataframe(status_df, use_container_width=True, hide_index=True)
if rate_limited:
    st.warning(
        "BGeometrics reached its rate limit, so further API requests were stopped. "
        "The audit continues below using all locally cached observations already available."
    )
if last_rate_info:
    st.info("BGeometrics quota: " + rate_text(last_rate_info))

if not cache.empty:
    cache_bytes = cache.reset_index().to_csv(index=False).encode()
    st.download_button(
        "Download updated consolidated cache",
        cache_bytes,
        "public_model_cache.csv",
        "text/csv",
        key="updated_cache",
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

st.subheader("4. Main screening results")
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
        "This is expected while the BGeometrics quota is exhausted; the cache will fill incrementally on future runs."
    )
else:
    existing = [c for c in show_cols if c in res.columns]
    fmt = {c: "{:+.3f}" for c in existing if c not in {"Candidate", "Coverage", "Negative 26w eras", "Screen"}}
    st.dataframe(res[existing].style.format(fmt), use_container_width=True, hide_index=True)

st.subheader("5. Era stability — 26 week horizon")
era_df = pd.DataFrame(era_rows)
if not era_df.empty:
    pivot = era_df.pivot(index="Candidate", columns="Era", values="26w Spearman").reset_index()
    st.dataframe(
        pivot.style.format({c: "{:+.3f}" for c in pivot.columns if c != "Candidate"}),
        use_container_width=True,
        hide_index=True,
    )

st.subheader("6. Research verdict")
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
st.download_button(
    "Download merged audit dataset",
    out.reset_index().to_csv(index=False).encode(),
    "btc_public_model_audit_merged.csv",
    "text/csv",
)
st.download_button(
    "Download audit summary",
    res.to_csv(index=False).encode(),
    "btc_public_model_audit_summary.csv",
    "text/csv",
)

st.caption(
    "Cache note: runtime file writes can be lost on a Streamlit Cloud redeploy. "
    "Keep the downloaded public_model_cache.csv with the website (engines/audit/cache/) so the next deploy starts with the accumulated history."
)
