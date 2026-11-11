"""Prospective read-only V5.9 risk observation from the SAME Research model.

Does not access personal Google Sheets, publish ntfy, place orders, or edit a
historical master. A completed UTC daily row is required; unavailable or neutral
fallback signals are not treated as cheap valuation. GitHub Actions artifacts
are prospective evidence, NOT proof of historical provider publication vintages.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
import math
from pathlib import Path
import pandas as pd

from engines.research import research_model as model
from engines.research.v59_dynamic_risk_policy import risk_buy_multiplier

SIGNAL_SOURCE = "Walk-forward Power Law"
PRICE_PROVIDER = "Blockchain.com market-price daily UTC"
FX_PROVIDER = "Frankfurter USD/AUD business-day"


def live_risk_params():
    """The risk-affecting settings used by V5.9 DCA Today, not proxy archive labels."""
    return {
        "risk_model": "Research WF Power Law",
        "pl_cheap": model.DEFAULT_PL_CHEAP,
        "pl_expensive": model.DEFAULT_PL_EXPENSIVE,
        "research_pl_min_weeks": model.RESEARCH_PL_MIN_WEEKS,
        "research_pl_refit_days": model.RESEARCH_PL_REFIT_DAYS,
        "risk_calibration_min_periods": model.DEFAULT_RISK_CALIBRATION_MIN_PERIODS,
        "risk_calibration_window": model.DEFAULT_RISK_CALIBRATION_WINDOW,
        "risk_calibration_blend": model.DEFAULT_RISK_CALIBRATION_BLEND,
        "absolute_risk_weight": model.DEFAULT_ABSOLUTE_RISK_WEIGHT,
        "relative_risk_weight": model.DEFAULT_RELATIVE_RISK_WEIGHT,
        "min_risk_components": model.DEFAULT_MIN_RISK_COMPONENTS,
        "price_position_window": model.DEFAULT_PRICE_POSITION_WINDOW,
    }


def snapshot_from_scored(scored: pd.DataFrame, *, now_utc: datetime, params: dict, fx_latest_date=None) -> dict:
    if now_utc.tzinfo is None:
        raise ValueError("now_utc must include timezone")
    now_utc = now_utc.astimezone(timezone.utc)
    cutoff = pd.Timestamp(now_utc.date(), tz="UTC")
    if not isinstance(scored.index, pd.DatetimeIndex):
        raise ValueError("Expected UTC timestamped historical price rows")
    valid = scored.copy()
    valid.index = pd.to_datetime(valid.index, utc=True)
    valid = valid.loc[valid.index < cutoff].sort_index()
    # Do not skip a newest missing-score row and quietly promote an old signal.
    if valid.empty:
        raise ValueError("No closed BTC daily price records")
    latest = valid.iloc[-1]
    stamp = valid.index[-1]
    day = stamp.date()
    age = (now_utc.date()-day).days
    score = float(latest.get("risk_score", float("nan")))
    source = str(latest.get("risk_score_source", ""))
    spot_usd = float(latest.get("price", float("nan")))
    fx = float(latest.get("usd_per_aud", float("nan")))
    risk_valid = bool(math.isfinite(score) and 0 <= score <= 1)
    spot_valid = bool(math.isfinite(spot_usd) and spot_usd > 0)
    fx_valid = bool(math.isfinite(fx) and fx > 0)
    fx_day = pd.to_datetime(fx_latest_date, utc=True).date() if fx_latest_date is not None else None
    fx_age = (now_utc.date()-fx_day).days if fx_day is not None else None
    # Snapshot is usable as an exact dated R2 research input only if actual
    # Power-Law fit supplied the score; do not accept Neutral fallback.
    source_ok = source == SIGNAL_SOURCE
    age_ok = 0 <= age <= 3
    fx_age_ok = fx_age is not None and 0 <= fx_age <= 5
    risk_ready = source_ok and age_ok and risk_valid and spot_valid
    market_ready = risk_ready and fx_valid and fx_age_ok
    preview_multiplier = risk_buy_multiplier(score) if risk_ready else None
    fingerprint = hashlib.sha256(
        (json.dumps(params, sort_keys=True)+"|"+str(stamp)+"|"+
         str(spot_usd)+"|"+str(score)+"|"+source).encode("utf-8")
    ).hexdigest()
    return {
        "status": ("RESEARCH_SIGNAL_SNAPSHOT_READY" if market_ready else "BLOCKED_SOURCE_OR_FRESHNESS"),
        "captured_at_utc": now_utc.isoformat(),
        "closed_risk_observation_utc": stamp.isoformat(),
        "closed_risk_age_days": age,
        "risk_model": params["risk_model"],
        "risk_score_source": source,
        "r2_sizing_risk": score if risk_valid else None,
        "continuous_valuation_risk": (
            float(latest["continuous_valuation_risk"])
            if "continuous_valuation_risk" in latest and
            pd.notna(latest["continuous_valuation_risk"]) else None
        ),
        "btc_usd_closed_price": spot_usd if spot_valid else None,
        "usd_per_aud": fx if fx_valid and fx_age_ok else None,
        "fx_observation_date_utc": fx_day.isoformat() if fx_day else None,
        "fx_age_days": fx_age,
        "risk_provider": PRICE_PROVIDER,
        "fx_provider": FX_PROVIDER,
        "model_params": params,
        "fingerprint": fingerprint,
        "research_aggressive_risk_band_multiplier": preview_multiplier,
        "risk_signal_ready": risk_ready,
        "risk_and_fx_fresh": market_ready,
        "provider_historical_vintages_attested": False,
        "personal_portfolio_loaded": False,
        "broker_free_cash_verified": False,
        "asx_ibit_executable_quote_verified": False,
        "ntfy_streamlit_parity_verified": False,
        "ready_for_live_aggressive_orders": False,
        "no_automatic_buy_sell_or_notifications": True,
        "issues": [
            reason for failed, reason in (
                (not source_ok, "R2_SCORE_NOT_ACTUAL_WALK_FORWARD_FIT"),
                (not age_ok, "RISK_DAILY_CLOSE_STALE_OR_FUTURE"),
                (not risk_valid, "RISK_SCORE_MISSING_OR_INVALID"),
                (not spot_valid, "BTC_USD_PRICE_MISSING_OR_INVALID"),
                (not fx_valid or not fx_age_ok, "AUD_FX_SOURCE_MISSING_OR_STALE"),
                (True, "REAL_PORTFOLIO_AND_BROKER_CASH_NOT_ATTESTED"),
                (True, "LIVE_STREAMLIT_NTFY_PARITY_NOT_ATTESTED"),
            ) if failed
        ],
    }


def capture(now_utc: datetime | None = None) -> dict:
    now = now_utc or datetime.now(timezone.utc)
    params = live_risk_params()
    start = model.RESEARCH_PL_HISTORY_START.to_pydatetime()
    btc = model.fetch_btc_history(start, now)
    if btc.empty:
        raise RuntimeError("Blockchain.com history unavailable; no trading inference")
    fx = model.fetch_aud_usd_rates(start, now)
    fx_latest = fx.index.max() if fx is not None and len(fx) else None
    frame = model.align_fx_to_dates(btc, fx)
    frame = model.merge_bgeometrics(frame, pd.DataFrame())
    scored = model.add_risk_indicators(frame, params["risk_model"], params)
    return snapshot_from_scored(scored, now_utc=now, params=params, fx_latest_date=fx_latest)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, default=Path("artifacts/research_v59_live_signal_snapshot.json"))
    args = parser.parse_args()
    try:
        result = capture()
    except Exception as exc:
        # Publish the failure but never a fabricated risk or cash suggestion.
        result = {
            "status": "BLOCKED_SOURCE_CAPTURE_FAILED",
            "captured_at_utc": datetime.now(timezone.utc).isoformat(),
            "error_type": type(exc).__name__,
            "ready_for_live_aggressive_orders": False,
            "no_automatic_buy_sell_or_notifications": True,
        }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(result, indent=2, allow_nan=False, sort_keys=True)+"\n")
    print(json.dumps(result, indent=2, allow_nan=False, sort_keys=True))
    # A failed capture must be visible in Actions, not look like a green audit.
    return 0 if result.get("status") == "RESEARCH_SIGNAL_SNAPSHOT_READY" else 2


if __name__ == "__main__":
    raise SystemExit(main())
