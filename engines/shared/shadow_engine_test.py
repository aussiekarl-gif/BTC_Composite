"""Read-only shadow test for running the frozen V5.8.2 risk engine on central candidate inputs."""

from __future__ import annotations

import numpy as np
import pandas as pd
import streamlit as st

from engines.production import production_model as prod
from engines.shared.central_data import CentralDataConfig, load_master


def render_shadow_engine_test(cfg: CentralDataConfig) -> None:
    st.subheader("4. Shadow Production engine test")
    st.caption(
        "This runs the actual V5.8.2 Production risk engine against the SHADOW-ONLY central candidate export. "
        "It does not change Production and is not a final parity proof for MVRV-Z/Fear & Greed."
    )

    shadow_cfg = CentralDataConfig(
        repository=cfg.repository,
        token=cfg.token,
        ref=cfg.ref,
        master_path="shadow/production_input_candidate.csv",
    )
    try:
        shadow = load_master(config=shadow_cfg)
    except Exception as exc:
        st.warning(
            "Shadow candidate export is not available on the central-data main branch yet. "
            f"Once the data PR is merged this section will run automatically. ({type(exc).__name__}: {exc})"
        )
        return

    required = ["btc_usd", "usd_per_aud", "mvrv_z", "fear_greed"]
    missing = [c for c in required if c not in shadow.columns]
    if missing:
        st.error(f"Shadow export is missing required columns: {missing}")
        return

    base = pd.DataFrame(index=shadow.index.copy())
    base["price"] = pd.to_numeric(shadow["btc_usd"], errors="coerce")
    fx = pd.to_numeric(shadow["usd_per_aud"], errors="coerce")
    base = prod.align_fx_to_dates(base, fx)

    external = pd.DataFrame(index=shadow.index.copy())
    external["mvrv_z"] = pd.to_numeric(shadow["mvrv_z"], errors="coerce")
    external["fear_greed"] = pd.to_numeric(shadow["fear_greed"], errors="coerce")
    base = prod.merge_bgeometrics(base, external)

    params = {
        "pl_cheap": prod.DEFAULT_PL_CHEAP,
        "pl_expensive": prod.DEFAULT_PL_EXPENSIVE,
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
        "trend_er_period": prod.DEFAULT_TREND_ER_PERIOD,
        "trend_fast": prod.DEFAULT_TREND_FAST,
        "trend_slow": prod.DEFAULT_TREND_SLOW,
        "trend_range_period": prod.DEFAULT_TREND_RANGE_PERIOD,
        "trend_band_mult": prod.DEFAULT_TREND_BAND_MULT,
    }

    risk = prod.add_risk_indicators(base, "Composite V3.6", params)
    valid = risk.dropna(subset=["risk_score", "price"])
    if valid.empty:
        st.error("The Production risk engine could not produce a valid Risk Score from the shadow export.")
        return

    latest = valid.iloc[-1]
    latest_date = valid.index[-1]
    latest_risk = float(latest["risk_score"])
    latest_mult = float(prod.interpolate(prod.SMART_DCA_POINTS, latest_risk))
    component_count = int(latest.get("risk_components_available", 0))

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Shadow valid risk dates", f"{len(valid):,}")
    c2.metric("Latest shadow Risk Score", f"{latest_risk:.6f}")
    c3.metric("Latest Smart DCA weight", f"{latest_mult:.4f}x")
    c4.metric("Risk components available", f"{component_count}/6")

    mvrv_value = latest.get("mvrv_z", np.nan)
    fg_value = latest.get("fear_greed", np.nan)
    st.caption(
        f"Latest shadow engine date: {latest_date.date()} • BTC/USD {float(latest['price']):,.2f} • "
        f"MVRV-Z {float(mvrv_value):.4f} • Fear & Greed {float(fg_value):.2f}"
    )

    risk_2 = prod.add_risk_indicators(base, "Composite V3.6", params)
    a = pd.to_numeric(risk["risk_score"], errors="coerce")
    b = pd.to_numeric(risk_2["risk_score"], errors="coerce")
    joined = pd.concat([a.rename("a"), b.rename("b")], axis=1).dropna()
    max_repeat_diff = float((joined["a"] - joined["b"]).abs().max()) if len(joined) else np.nan

    if np.isfinite(max_repeat_diff) and max_repeat_diff <= 1e-12:
        st.success("Shadow engine determinism check: PASS — repeated V5.8.2 calculations are exactly identical.")
    else:
        st.error(f"Shadow engine determinism check failed. Max repeated Risk Score difference: {max_repeat_diff}")

    st.info(
        "This proves the central shadow export can drive the frozen V5.8.2 risk engine reproducibly. "
        "It does NOT yet prove fresh live parity for MVRV-Z and Fear & Greed, and Production remains on its existing live data path."
    )
