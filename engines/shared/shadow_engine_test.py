"""Read-only shadow tests for the frozen V5.8.2 risk engine."""
from __future__ import annotations

import numpy as np
import pandas as pd
import streamlit as st

from engines.production import production_model as prod
from engines.shared.central_data import CentralDataConfig, load_master


def _params():
    return {
        "pl_cheap": prod.DEFAULT_PL_CHEAP, "pl_expensive": prod.DEFAULT_PL_EXPENSIVE,
        "valuation_strength": prod.DEFAULT_VALUATION_STRENGTH,
        "min_valuation_mult": prod.DEFAULT_MIN_VALUATION_MULT,
        "max_valuation_mult": min(prod.DEFAULT_MAX_VALUATION_MULT, 2.0),
        "min_risk_components": prod.DEFAULT_MIN_RISK_COMPONENTS,
        "price_position_window": prod.DEFAULT_PRICE_POSITION_WINDOW,
        "risk_calibration_min_periods": prod.DEFAULT_RISK_CALIBRATION_MIN_PERIODS,
        "risk_calibration_window": prod.DEFAULT_RISK_CALIBRATION_WINDOW,
        "risk_calibration_blend": prod.DEFAULT_RISK_CALIBRATION_BLEND,
        "absolute_risk_weight": prod.DEFAULT_ABSOLUTE_RISK_WEIGHT,
        "relative_risk_weight": prod.DEFAULT_RELATIVE_RISK_WEIGHT,
        "trend_er_period": prod.DEFAULT_TREND_ER_PERIOD, "trend_fast": prod.DEFAULT_TREND_FAST,
        "trend_slow": prod.DEFAULT_TREND_SLOW, "trend_range_period": prod.DEFAULT_TREND_RANGE_PERIOD,
        "trend_band_mult": prod.DEFAULT_TREND_BAND_MULT,
    }


def _engine(price: pd.DataFrame, fx, external: pd.DataFrame) -> pd.DataFrame:
    base = price[["price"]].copy()
    base = prod.align_fx_to_dates(base, fx)
    base = prod.merge_bgeometrics(base, external)
    return prod.add_risk_indicators(base, "Composite V3.6", _params())


def render_shadow_engine_test(cfg: CentralDataConfig, live_price=None, live_fx=None, live_bg=None) -> None:
    st.subheader("4. Shadow Production engine test")
    st.caption("Runs the actual frozen V5.8.2 Production risk engine against the SHADOW-ONLY central candidate export. Production is unchanged.")
    shadow_cfg = CentralDataConfig(repository=cfg.repository, token=cfg.token, ref=cfg.ref, master_path="shadow/production_input_candidate.csv")
    try:
        shadow = load_master(config=shadow_cfg)
    except Exception as exc:
        st.warning(f"Shadow candidate export is unavailable. ({type(exc).__name__}: {exc})")
        return
    required = ["btc_usd", "usd_per_aud", "mvrv_z", "fear_greed"]
    missing = [c for c in required if c not in shadow.columns]
    if missing:
        st.error(f"Shadow export is missing required columns: {missing}")
        return

    price = pd.DataFrame({"price": pd.to_numeric(shadow["btc_usd"], errors="coerce")}, index=shadow.index)
    fx = pd.to_numeric(shadow["usd_per_aud"], errors="coerce")
    external = pd.DataFrame(index=shadow.index)
    external["mvrv_z"] = pd.to_numeric(shadow["mvrv_z"], errors="coerce")
    external["fear_greed"] = pd.to_numeric(shadow["fear_greed"], errors="coerce")
    risk = _engine(price, fx, external)
    valid = risk.dropna(subset=["risk_score", "price"])
    if valid.empty:
        st.error("The Production risk engine could not produce a valid Risk Score from the shadow export.")
        return
    latest = valid.iloc[-1]; latest_date = valid.index[-1]
    latest_risk = float(latest["risk_score"]); latest_mult = float(prod.interpolate(prod.SMART_DCA_POINTS, latest_risk))
    c1,c2,c3,c4 = st.columns(4)
    c1.metric("Shadow valid risk dates", f"{len(valid):,}"); c2.metric("Latest shadow Risk Score", f"{latest_risk:.6f}")
    c3.metric("Latest Smart DCA weight", f"{latest_mult:.4f}x"); c4.metric("Risk components available", f"{int(latest.get('risk_components_available',0))}/6")
    st.caption(f"Latest shadow engine date: {latest_date.date()} • BTC/USD {float(latest['price']):,.2f} • MVRV-Z {float(latest.get('mvrv_z',np.nan)):.4f} • Fear & Greed {float(latest.get('fear_greed',np.nan)):.2f}")

    risk2 = _engine(price, fx, external)
    repeat = pd.concat([risk["risk_score"].rename("a"), risk2["risk_score"].rename("b")], axis=1).dropna()
    repeat_diff = float((repeat.a-repeat.b).abs().max()) if len(repeat) else np.nan
    if np.isfinite(repeat_diff) and repeat_diff <= 1e-12:
        st.success("Shadow engine determinism check: PASS — repeated V5.8.2 calculations are exactly identical.")
    else:
        st.error(f"Shadow engine determinism check failed. Max repeated Risk Score difference: {repeat_diff}")

    st.subheader("5. Live Production vs central shadow output parity")
    st.caption("Uses the live inputs already fetched by this parity run; it makes no additional BGeometrics request. The same frozen V5.8.2 engine is run on both paths.")
    if live_price is None or getattr(live_price,"empty",True) or live_bg is None or getattr(live_bg,"empty",True):
        st.info("Live output parity unavailable on this run because a complete live Production input bundle was not returned. No central data is treated as missing.")
        return
    try:
        live_risk = _engine(live_price, live_fx, live_bg)
    except Exception as exc:
        st.warning(f"Live Production engine comparison could not run: {type(exc).__name__}: {exc}")
        return

    component_cols = ["power_law_score","mvrv_score","price_position_score","mayer_score","fear_greed_score","rsi_score"]
    compare_cols = ["risk_score"] + component_cols
    rows=[]
    for col in compare_cols:
        if col not in live_risk.columns or col not in risk.columns: continue
        pair=pd.concat([pd.to_numeric(live_risk[col],errors="coerce").rename("live"),pd.to_numeric(risk[col],errors="coerce").rename("central")],axis=1,join="inner").dropna()
        diff=(pair.live-pair.central).abs() if len(pair) else pd.Series(dtype=float)
        rows.append({"Output":col,"Overlap dates":len(pair),"Max abs difference":float(diff.max()) if len(diff) else np.nan,"Exact?":"YES" if len(diff) and bool((diff<=1e-12).all()) else ("NO" if len(diff) else "NO OVERLAP")})
    out=pd.DataFrame(rows)
    st.dataframe(out, use_container_width=True, hide_index=True)
    risk_row=next((r for r in rows if r["Output"]=="risk_score"),None)
    if risk_row and risk_row["Exact?"]=="YES":
        st.success("LIVE vs CENTRAL SHADOW: PASS — V5.8.2 Risk Score is exactly identical across all overlapping dates.")
    elif risk_row and risk_row["Overlap dates"]:
        st.warning(f"LIVE vs CENTRAL SHADOW: DIFFERENCE DETECTED — Risk Score max absolute difference {risk_row['Max abs difference']:.12g}. Component rows above show where it originates.")
    else:
        st.info("No overlapping live/shadow Risk Score dates were available on this run.")

    # Latest common valid date gives a human-readable DCA sizing check.
    common=pd.concat([live_risk["risk_score"].rename("live"),risk["risk_score"].rename("central")],axis=1,join="inner").dropna()
    if len(common):
        d=common.index[-1]; lr=float(common.iloc[-1].live); cr=float(common.iloc[-1].central)
        lm=float(prod.interpolate(prod.SMART_DCA_POINTS,lr)); cm=float(prod.interpolate(prod.SMART_DCA_POINTS,cr))
        st.caption(f"Latest common date {d.date()} • Live Risk {lr:.6f} / {lm:.4f}x • Central Risk {cr:.6f} / {cm:.4f}x")

    st.info("This remains a read-only shadow test. It does not switch Production or write central data.")