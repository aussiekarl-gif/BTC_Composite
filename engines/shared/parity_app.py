#!/usr/bin/env python3
"""Read-only parity lab for the shared BTC data layer.

This page compares the central research master with the data paths currently used
by Production/Research. It does not write data and cannot switch either model to
central inputs.
"""

from __future__ import annotations

import os
import datetime as dt

import numpy as np
import pandas as pd
import streamlit as st

from engines.shared.central_data import CentralDataConfig, CentralDataError, load_master
from engines.production import production_model as prod
from engines.research import research_model as research


def _secret_or_env(name: str, default: str = "") -> str:
    try:
        value = st.secrets.get(name, "")
        if value:
            return str(value).strip()
    except Exception:
        pass
    return str(os.getenv(name, default) or default).strip()


def _central_config() -> CentralDataConfig:
    return CentralDataConfig(
        repository=_secret_or_env("BTC_CENTRAL_DATA_REPO", _secret_or_env("AUDIT_GITHUB_REPO", "aussiekarl-gif/btc-audit-data")),
        token=_secret_or_env("BTC_CENTRAL_DATA_TOKEN", _secret_or_env("AUDIT_GITHUB_TOKEN", "")),
        ref=_secret_or_env("BTC_CENTRAL_DATA_REF", _secret_or_env("AUDIT_GITHUB_BRANCH", "main")) or "main",
        master_path=_secret_or_env("BTC_CENTRAL_DATA_MASTER", _secret_or_env("AUDIT_GITHUB_PATH", "btc_audit_backup.csv")) or "btc_audit_backup.csv",
    )


@st.cache_data(ttl=900, show_spinner=False)
def _load_central_cached(repo: str, token: str, ref: str, path: str) -> pd.DataFrame:
    cfg = CentralDataConfig(repository=repo, token=token, ref=ref, master_path=path)
    return load_master(config=cfg)


def _daily(series: pd.Series) -> pd.Series:
    x = pd.to_numeric(series, errors="coerce").dropna().copy()
    if not isinstance(x.index, pd.DatetimeIndex):
        return pd.Series(dtype=float)
    idx = pd.to_datetime(x.index, utc=True, errors="coerce").normalize()
    x.index = idx
    x = x[~x.index.isna()]
    return x.groupby(level=0).last().sort_index()


def _comparison_row(label: str, current: pd.Series, central: pd.Series, current_source: str, central_source: str) -> dict:
    a = _daily(current).rename("current")
    b = _daily(central).rename("central")
    joined = pd.concat([a, b], axis=1, join="inner").dropna()
    if joined.empty:
        return {
            "Input": label,
            "Current source": current_source,
            "Central candidate": central_source,
            "Overlap days": 0,
            "Median abs diff %": np.nan,
            "95th pct abs diff %": np.nan,
            "Max abs diff %": np.nan,
            "Correlation": np.nan,
            "Status": "NO OVERLAP",
        }
    denom = joined["current"].replace(0, np.nan).abs()
    pct = ((joined["central"] - joined["current"]).abs() / denom * 100.0).replace([np.inf, -np.inf], np.nan).dropna()
    corr = joined["current"].corr(joined["central"])
    return {
        "Input": label,
        "Current source": current_source,
        "Central candidate": central_source,
        "Overlap days": int(len(joined)),
        "Median abs diff %": float(pct.median()) if len(pct) else np.nan,
        "95th pct abs diff %": float(pct.quantile(0.95)) if len(pct) else np.nan,
        "Max abs diff %": float(pct.max()) if len(pct) else np.nan,
        "Correlation": float(corr) if np.isfinite(corr) else np.nan,
        "Status": "MEASURED",
    }


def _exact_model_row(label: str, a: pd.Series, b: pd.Series) -> dict:
    aa = _daily(a).rename("production")
    bb = _daily(b).rename("research")
    joined = pd.concat([aa, bb], axis=1, join="inner").dropna()
    if joined.empty:
        return {"Input": label, "Overlap days": 0, "Max abs difference": np.nan, "Exact?": "NO OVERLAP"}
    diff = (joined["production"] - joined["research"]).abs()
    return {
        "Input": label,
        "Overlap days": int(len(joined)),
        "Max abs difference": float(diff.max()),
        "Exact?": "YES" if bool((diff <= 1e-12).all()) else "NO",
    }


st.title("Central BTC Data Parity Lab")
st.caption(
    "Read-only safety stage. This compares the new central research database with the inputs currently fetched by "
    "V5.8.2 Production and V5.9 Research. Nothing on this page changes either model or writes to btc-audit-data."
)

with st.expander("Safety boundary", expanded=False):
    st.markdown(
        """
- `btc-audit-data/btc_audit_backup.csv` remains a **research master**, not a Production input.
- This page performs comparisons only.
- Missing central equivalents are reported as gaps rather than silently substituted.
- A future `validated/production_input.csv` will only be created after we are satisfied with coverage and parity.
- Production stays on its existing data path until a separate explicitly reviewed change.
- BGeometrics is fetched only **once** per parity run to protect the limited quota.
        """
    )

lookback = st.selectbox("Comparison window", [365, 730, 1460], index=1, format_func=lambda x: f"Last {x} days")
end_date = dt.date.today()
start_date = end_date - dt.timedelta(days=int(lookback))

if not st.button("RUN READ-ONLY PARITY CHECK", type="primary", key="run_central_parity"):
    st.info("Run the parity check when you want to compare the central master against the current live data paths.")
    st.stop()

cfg = _central_config()
try:
    with st.spinner("Reading central BTC master..."):
        central = _load_central_cached(cfg.repository, cfg.token, cfg.ref, cfg.master_path)
except CentralDataError as exc:
    st.error(f"Central data could not be read: {exc}")
    st.stop()

st.success(
    f"Central master loaded: {len(central):,} unique dates • {len(central.columns):,} columns • "
    f"{central.index.min().date()} → {central.index.max().date()}"
)

with st.spinner("Fetching current comparison inputs..."):
    prod_price = prod.fetch_btc_history(start_date, end_date)
    research_price = research.fetch_btc_history(start_date, end_date)
    prod_fx = prod.fetch_aud_usd_rates(start_date, end_date)
    token = prod.get_bgeometrics_token()
    # One BGeometrics bundle only. Research and Production are not allowed to double-spend quota here.
    prod_bg = prod.fetch_bgeometrics_bundle(start_date, end_date, token)

st.subheader("1. Production vs Research current price-path parity")
model_rows = []
if not prod_price.empty and not research_price.empty and "price" in prod_price and "price" in research_price:
    model_rows.append(_exact_model_row("BTC/USD price", prod_price["price"], research_price["price"]))
if model_rows:
    st.dataframe(pd.DataFrame(model_rows), use_container_width=True, hide_index=True)
    st.caption("External BGeometrics inputs are not fetched twice here; the limited quota is reserved for the central-vs-current comparison below.")
else:
    st.warning("No overlapping Production/Research price inputs were available for comparison.")

st.subheader("2. Central master vs current Production inputs")
rows = []
window = central.loc[(central.index.date >= start_date) & (central.index.date <= end_date)]

def add_or_gap(label, current_series, central_col, current_source):
    if central_col in window.columns and current_series is not None and len(current_series):
        rows.append(_comparison_row(label, current_series, window[central_col], current_source, central_col))
    else:
        rows.append({
            "Input": label, "Current source": current_source, "Central candidate": central_col,
            "Overlap days": 0, "Status": "SOURCE-PRESERVING CENTRAL GAP"
        })

add_or_gap(
    "BTC/USD daily price",
    prod_price["price"] if (not prod_price.empty and "price" in prod_price.columns) else None,
    "src__blockchain_btc_usd",
    "Blockchain.com market-price",
)
add_or_gap(
    "MVRV Z-Score",
    prod_bg["mvrv_z"] if "mvrv_z" in prod_bg.columns else None,
    "src__bgeometrics_mvrv_z",
    "BGeometrics mvrv-zscore",
)
add_or_gap(
    "Fear & Greed",
    prod_bg["fear_greed"] if "fear_greed" in prod_bg.columns else None,
    "src__bgeometrics_fear_greed",
    "BGeometrics fear-greed",
)
add_or_gap(
    "AUD/USD FX",
    prod_fx if prod_fx is not None else None,
    "src__frankfurter_usd_per_aud",
    "Frankfurter business-day FX",
)
add_or_gap(
    "Regime Score",
    prod_bg["regime_score"] if "regime_score" in prod_bg.columns else None,
    "src__bgeometrics_regime_score",
    "BGeometrics regime-score",
)

st.caption(
    "Migration readiness is based only on exact source-preserving `src__` columns. "
    "Coin Metrics remains useful research data but is not treated as a substitute for the Production Blockchain.com feed."
)

parity = pd.DataFrame(rows)
for col in ["Median abs diff %", "95th pct abs diff %", "Max abs diff %", "Correlation"]:
    if col not in parity.columns:
        parity[col] = np.nan
st.dataframe(
    parity[["Input","Current source","Central candidate","Overlap days","Median abs diff %","95th pct abs diff %","Max abs diff %","Correlation","Status"]]
        .style.format({"Median abs diff %":"{:.4f}","95th pct abs diff %":"{:.4f}","Max abs diff %":"{:.4f}","Correlation":"{:.6f}"}, na_rep="—"),
    use_container_width=True,
    hide_index=True,
)

st.subheader("3. Migration readiness")
measured = int((parity["Status"] == "MEASURED").sum())
gaps = int(parity["Status"].str.contains("GAP", regex=True, na=False).sum())
st.metric("Inputs with measured central parity", measured)
st.metric("Inputs still requiring a central equivalent / validation", gaps)

if gaps:
    st.warning(
        "Centralization is not ready for Production yet. That is the expected safe result at this stage: "
        "we first measure what matches, identify missing inputs, and only then build a small validated Production export."
    )
else:
    st.info(
        "All listed inputs have measurable central candidates. This still does not switch Production; the next step would be "
        "a separately reviewed validated export with explicit tolerances and reproducibility checks."
    )

st.caption("No files were written and no Production/Research data source was changed by this parity check.")
