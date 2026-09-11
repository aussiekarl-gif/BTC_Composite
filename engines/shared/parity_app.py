#!/usr/bin/env python3
"""Read-only parity lab for the shared BTC data layer."""
from __future__ import annotations
import os
import datetime as dt
import numpy as np
import pandas as pd
import streamlit as st
from engines.shared.central_data import CentralDataConfig, CentralDataError, load_master
from engines.shared.shadow_engine_test import render_shadow_engine_test
from engines.production import production_model as prod
from engines.research import research_model as research

def _secret_or_env(name: str, default: str = "") -> str:
    try:
        value = st.secrets.get(name, "")
        if value: return str(value).strip()
    except Exception: pass
    return str(os.getenv(name, default) or default).strip()

def _central_config() -> CentralDataConfig:
    return CentralDataConfig(repository=_secret_or_env("BTC_CENTRAL_DATA_REPO", _secret_or_env("AUDIT_GITHUB_REPO", "aussiekarl-gif/btc-audit-data")), token=_secret_or_env("BTC_CENTRAL_DATA_TOKEN", _secret_or_env("AUDIT_GITHUB_TOKEN", "")), ref=_secret_or_env("BTC_CENTRAL_DATA_REF", _secret_or_env("AUDIT_GITHUB_BRANCH", "main")) or "main", master_path=_secret_or_env("BTC_CENTRAL_DATA_MASTER", _secret_or_env("AUDIT_GITHUB_PATH", "btc_audit_backup.csv")) or "btc_audit_backup.csv")

@st.cache_data(ttl=900, show_spinner=False)
def _load_central_cached(repo, token, ref, path): return load_master(config=CentralDataConfig(repository=repo,token=token,ref=ref,master_path=path))

def _daily(series):
    x=pd.to_numeric(series,errors="coerce").dropna().copy()
    if not isinstance(x.index,pd.DatetimeIndex): return pd.Series(dtype=float)
    x.index=pd.to_datetime(x.index,utc=True,errors="coerce").normalize(); x=x[~x.index.isna()]
    return x.groupby(level=0).last().sort_index()

def _comparison_row(label,current,central,current_source,central_source):
    joined=pd.concat([_daily(current).rename("current"),_daily(central).rename("central")],axis=1,join="inner").dropna()
    if joined.empty: return {"Input":label,"Current source":current_source,"Central candidate":central_source,"Overlap days":0,"Status":"NO OVERLAP"}
    denom=joined.current.replace(0,np.nan).abs(); pct=((joined.central-joined.current).abs()/denom*100).replace([np.inf,-np.inf],np.nan).dropna(); corr=joined.current.corr(joined.central)
    return {"Input":label,"Current source":current_source,"Central candidate":central_source,"Overlap days":len(joined),"Median abs diff %":float(pct.median()) if len(pct) else np.nan,"95th pct abs diff %":float(pct.quantile(.95)) if len(pct) else np.nan,"Max abs diff %":float(pct.max()) if len(pct) else np.nan,"Correlation":float(corr) if np.isfinite(corr) else np.nan,"Status":"MEASURED"}

def _exact_model_row(label,a,b):
    joined=pd.concat([_daily(a).rename("production"),_daily(b).rename("research")],axis=1,join="inner").dropna()
    if joined.empty:return {"Input":label,"Overlap days":0,"Max abs difference":np.nan,"Exact?":"NO OVERLAP"}
    diff=(joined.production-joined.research).abs(); return {"Input":label,"Overlap days":len(joined),"Max abs difference":float(diff.max()),"Exact?":"YES" if (diff<=1e-12).all() else "NO"}

st.title("Central BTC Data Parity Lab")
st.caption("Read-only safety stage. This compares the new central research database with the inputs currently fetched by V5.8.2 Production and V5.9 Research. Nothing on this page changes either model or writes to btc-audit-data.")
with st.expander("Safety boundary",expanded=False):
    st.markdown("- The central master remains research data.\n- This page performs comparisons only.\n- Production stays on its existing data path until a separately reviewed migration.\n- BGeometrics is fetched only once per parity run.")
lookback=st.selectbox("Comparison window",[365,730,1460],index=1,format_func=lambda x:f"Last {x} days"); end_date=dt.date.today(); start_date=end_date-dt.timedelta(days=int(lookback))
if not st.button("RUN READ-ONLY PARITY CHECK",type="primary",key="run_central_parity"): st.info("Run the parity check when you want to compare the central master against the current live data paths."); st.stop()
cfg=_central_config()
try:
    with st.spinner("Reading central BTC master..."): central=_load_central_cached(cfg.repository,cfg.token,cfg.ref,cfg.master_path)
except CentralDataError as exc: st.error(f"Central data could not be read: {exc}"); st.stop()
st.success(f"Central master loaded: {len(central):,} unique dates • {len(central.columns):,} columns • {central.index.min().date()} → {central.index.max().date()}")
with st.spinner("Fetching current comparison inputs..."):
    prod_price=prod.fetch_btc_history(start_date,end_date); research_price=research.fetch_btc_history(start_date,end_date); prod_fx=prod.fetch_aud_usd_rates(start_date,end_date); token=prod.get_bgeometrics_token(); bg_live_error=""
    try: prod_bg=prod.fetch_bgeometrics_bundle(start_date,end_date,token)
    except Exception as exc: prod_bg=pd.DataFrame(); bg_live_error=f"{type(exc).__name__}: {exc}"
st.subheader("1. Production vs Research current price-path parity"); model_rows=[]
if not prod_price.empty and not research_price.empty and "price" in prod_price and "price" in research_price: model_rows.append(_exact_model_row("BTC/USD price",prod_price.price,research_price.price))
if model_rows: st.dataframe(pd.DataFrame(model_rows),use_container_width=True,hide_index=True); st.caption("External BGeometrics inputs are not fetched twice here.")
else: st.warning("No overlapping Production/Research price inputs were available for comparison.")
st.subheader("2. Central master vs current Production inputs"); rows=[]; window=central.loc[(central.index.date>=start_date)&(central.index.date<=end_date)]
def add_or_gap(label,current_series,central_col,current_source,role="Production-critical"):
    central_obs=int(pd.to_numeric(window[central_col],errors="coerce").notna().sum()) if central_col in window.columns else 0; central_present=central_obs>0
    try: current_present=current_series is not None and len(_daily(current_series))>0
    except Exception: current_present=False
    if central_present and current_present:
        row=_comparison_row(label,current_series,window[central_col],current_source,central_col); row["Role"]=role; row["Central observations"]=central_obs
        if row.get("Status")=="NO OVERLAP": row["Status"]="CENTRAL PRESENT — NO DATE OVERLAP"
    elif central_present: row={"Input":label,"Role":role,"Current source":current_source,"Central candidate":central_col,"Central observations":central_obs,"Overlap days":0,"Status":"CENTRAL PRESENT — LIVE COMPARISON UNAVAILABLE"}
    else: row={"Input":label,"Role":role,"Current source":current_source,"Central candidate":central_col,"Central observations":0,"Overlap days":0,"Status":"SOURCE-PRESERVING CENTRAL GAP"}
    rows.append(row)
add_or_gap("BTC/USD daily price",prod_price.price if not prod_price.empty and "price" in prod_price else None,"src__blockchain_btc_usd","Blockchain.com market-price")
add_or_gap("MVRV Z-Score",prod_bg.mvrv_z if "mvrv_z" in prod_bg else None,"src__bgeometrics_mvrv_z","BGeometrics mvrv-zscore")
add_or_gap("Fear & Greed",prod_bg.fear_greed if "fear_greed" in prod_bg else None,"src__bgeometrics_fear_greed","BGeometrics fear-greed")
add_or_gap("AUD/USD FX",prod_fx,"src__frankfurter_usd_per_aud","Frankfurter business-day FX")
add_or_gap("Regime Score",prod_bg.regime_score if "regime_score" in prod_bg else None,"src__bgeometrics_regime_score","BGeometrics regime-score",role="Optional context — not used in Risk Score/DCA sizing")
st.caption("Migration readiness is based only on exact source-preserving `src__` columns.")
parity=pd.DataFrame(rows)
for col in ["Median abs diff %","95th pct abs diff %","Max abs diff %","Correlation"]:
    if col not in parity: parity[col]=np.nan
if "Central observations" not in parity: parity["Central observations"]=0
st.dataframe(parity[["Input","Role","Current source","Central candidate","Central observations","Overlap days","Median abs diff %","95th pct abs diff %","Max abs diff %","Correlation","Status"]].style.format({"Median abs diff %":"{:.4f}","95th pct abs diff %":"{:.4f}","Max abs diff %":"{:.4f}","Correlation":"{:.6f}"},na_rep="—"),use_container_width=True,hide_index=True)
if bg_live_error: st.caption("Live BGeometrics comparison was unavailable on this run: "+bg_live_error)
st.subheader("3. Migration readiness"); critical=parity[parity.Role.eq("Production-critical")]; measured=int((critical.Status=="MEASURED").sum()); present_unvalidated=int(critical.Status.str.startswith("CENTRAL PRESENT",na=False).sum()); gaps=int(critical.Status.str.contains("GAP",regex=True,na=False).sum()); optional_gaps=int((~parity.Role.eq("Production-critical") & parity.Status.str.contains("GAP",regex=True,na=False)).sum())
st.metric("Production-critical inputs with measured central parity",measured); st.metric("Production-critical inputs present but awaiting live validation",present_unvalidated); st.metric("True Production-critical central-source gaps",gaps)
if optional_gaps: st.caption(f"Optional/context-only source gaps: {optional_gaps}. These do not block Production input centralization.")
if gaps: st.warning("Centralization is not ready for Production yet. Some Production-critical exact-source inputs are genuinely missing.")
elif present_unvalidated: st.info("All listed source-preserving inputs exist centrally, but some still need a successful live parity comparison. Production remains unchanged until those validations are complete.")
else: st.info("All listed inputs have measurable central candidates. Production remains unchanged pending separately reviewed migration.")
render_shadow_engine_test(cfg,live_price=prod_price,live_fx=prod_fx,live_bg=prod_bg)
st.caption("No files were written and no Production/Research data source was changed by this parity check.")