#!/usr/bin/env python3
"""
Temporary dual-model ntfy comparison for BTC Dynamic DCA.

Compares, side-by-side:
- V5.8.2 Production (engines/production/production_model.py)
- V5.9 Research (engines/research/research_model.py)

Privacy / behavior:
- No portfolio balance, holdings, capital amount, or recommended AUD amount is sent.
- The notification shows each model's Risk Score and DCA multiplier only.
- Risk calculations use the latest fully closed UTC day; BTC prices are live.
"""

from __future__ import annotations

import datetime as dt
import os
from zoneinfo import ZoneInfo

from engines.production import production_model as PROD_MODEL
from engines.research import research_model as RESEARCH_MODEL

BRISBANE = ZoneInfo("Australia/Brisbane")


def load_model_engine(engine_module):
    """Expose the imported calculation module using the notifier's existing dict API."""
    return vars(engine_module)


def fixed_engine_params(e, model: str, start_date: dt.date, end_date: dt.datetime):
    params = {
        "risk_model": model,
        "frequency": "Weekly",
        "day_of_week": end_date.weekday(),
        "fund_cheap": e["DEFAULT_FUND_CHEAP"],
        "fund_expensive": e["DEFAULT_FUND_EXPENSIVE"],
        "pl_cheap": e["DEFAULT_PL_CHEAP"],
        "pl_expensive": e["DEFAULT_PL_EXPENSIVE"],
        "total_capital_aud": 500000.0,
        "base_dca_pct": 0.01,
        "pressure_strength": 0.0,
        "max_period_pct": 0.05,
        "min_cash_reserve_pct": e["DEFAULT_MIN_CASH_RESERVE_PCT"],
        "sell_threshold": 0.0,
        "max_sell_pct_period": min(e["DEFAULT_MAX_SELL_PCT_PERIOD"], 0.20),
        "fee_pct": e["DEFAULT_FEE_PCT"],
        "regime_overlay": 0.0,
        "valuation_strength": e["DEFAULT_VALUATION_STRENGTH"],
        "min_valuation_mult": e["DEFAULT_MIN_VALUATION_MULT"],
        "max_valuation_mult": min(e["DEFAULT_MAX_VALUATION_MULT"], 2.0),
        "pressure_cap": 1.0,
        "max_btc_weight": 1.0,
        "min_days_between_sales": e["DEFAULT_MIN_DAYS_BETWEEN_SALES"],
        "buy_threshold": e["DEFAULT_BUY_THRESHOLD"],
        "sell_risk_threshold": e["DEFAULT_SELL_RISK_THRESHOLD"],
        "min_trade_aud": e["DEFAULT_MIN_TRADE_AUD"],
        "min_risk_components": e["DEFAULT_MIN_RISK_COMPONENTS"],
        "price_position_window": e["DEFAULT_PRICE_POSITION_WINDOW"],
        "risk_calibration_min_periods": e["DEFAULT_RISK_CALIBRATION_MIN_PERIODS"],
        "risk_calibration_window": e["DEFAULT_RISK_CALIBRATION_WINDOW"],
        "risk_calibration_blend": e["DEFAULT_RISK_CALIBRATION_BLEND"],
        "absolute_risk_weight": e["DEFAULT_ABSOLUTE_RISK_WEIGHT"],
        "relative_risk_weight": e["DEFAULT_RELATIVE_RISK_WEIGHT"],
        "require_weak_trend_for_sell": False,
        "trend_er_period": e["DEFAULT_TREND_ER_PERIOD"],
        "trend_fast": e["DEFAULT_TREND_FAST"],
        "trend_slow": e["DEFAULT_TREND_SLOW"],
        "trend_range_period": e["DEFAULT_TREND_RANGE_PERIOD"],
        "trend_band_mult": e["DEFAULT_TREND_BAND_MULT"],
        "trend_buy_bull": e["DEFAULT_TREND_BUY_BULL"],
        "trend_buy_neutral": e["DEFAULT_TREND_BUY_NEUTRAL"],
        "trend_buy_bear": e["DEFAULT_TREND_BUY_BEAR"],
        "trend_sell_bull": e["DEFAULT_TREND_SELL_BULL"],
        "trend_sell_neutral": e["DEFAULT_TREND_SELL_NEUTRAL"],
        "trend_sell_bear": e["DEFAULT_TREND_SELL_BEAR"],
        "start_date": dt.datetime.combine(start_date, dt.time.min, tzinfo=dt.timezone.utc),
        "end_date": end_date,
    }

    if model == "Research WF Power Law":
        params["research_pl_min_weeks"] = e["RESEARCH_PL_MIN_WEEKS"]
        params["research_pl_refit_days"] = e["RESEARCH_PL_REFIT_DAYS"]

    return params


def risk_label(risk: float) -> str:
    if risk <= 0.20:
        return "VERY LOW"
    if risk <= 0.40:
        return "LOW"
    if risk <= 0.60:
        return "NEUTRAL"
    if risk <= 0.80:
        return "HIGH"
    return "VERY HIGH"


def calculate_model_summary(engine_module, model: str):
    e = load_model_engine(engine_module)
    np, pd = e["np"], e["pd"]
    now_utc = dt.datetime.now(dt.timezone.utc)

    closed_cutoff_utc = dt.datetime.combine(now_utc.date(), dt.time.min, tzinfo=dt.timezone.utc)
    closed_end_utc = closed_cutoff_utc - dt.timedelta(microseconds=1)

    if model == "Research WF Power Law":
        hist_start = e.get("RESEARCH_PL_HISTORY_START", pd.Timestamp("2012-01-01", tz="UTC"))
        lookback_start = pd.Timestamp(hist_start).to_pydatetime()
    else:
        lookback_start = closed_end_utc - dt.timedelta(days=365 * 11)

    params = fixed_engine_params(e, model, lookback_start.date(), closed_end_utc)

    df = e["fetch_btc_history"](lookback_start, closed_end_utc)
    if df is None or df.empty:
        raise RuntimeError(f"No BTC history returned for {model}.")

    fx = e["fetch_aud_usd_rates"](lookback_start, closed_end_utc)
    token = e["get_bgeometrics_token"]()
    bg = e["fetch_bgeometrics_bundle"](
        lookback_start - dt.timedelta(days=300), closed_end_utc, token
    )

    df = e["align_fx_to_dates"](df, fx)
    df = e["merge_bgeometrics"](df, bg)
    risk_df = e["add_risk_indicators"](df, model, params)
    valid = risk_df.dropna(subset=["risk_score", "price"]).copy()

    if isinstance(valid.index, pd.DatetimeIndex):
        idx = valid.index
        if idx.tz is None:
            cutoff = pd.Timestamp(closed_cutoff_utc.replace(tzinfo=None))
        else:
            cutoff = pd.Timestamp(closed_cutoff_utc).tz_convert(idx.tz)
        valid = valid.loc[idx < cutoff]
    elif "date" in valid.columns:
        dates = pd.to_datetime(valid["date"], utc=True, errors="coerce")
        valid = valid.loc[dates < pd.Timestamp(closed_cutoff_utc)]

    if valid.empty:
        raise RuntimeError(f"Risk Score unavailable for {model}.")

    latest = valid.iloc[-1]
    current_risk = float(latest["risk_score"])
    multiplier = float(e["interpolate"](e["SMART_DCA_POINTS"], current_risk))

    if isinstance(valid.index, pd.DatetimeIndex):
        latest_ts = pd.Timestamp(valid.index[-1])
    elif "date" in valid.columns:
        latest_ts = pd.Timestamp(valid.iloc[-1]["date"])
    else:
        latest_ts = pd.Timestamp(closed_end_utc.date())
    if latest_ts.tzinfo is not None:
        latest_ts = latest_ts.tz_convert("UTC").tz_localize(None)

    risk_obs = valid["risk_score"].dropna().astype(float)
    previous_risk = float(risk_obs.iloc[-2]) if len(risk_obs) >= 2 else np.nan
    risk_drop = previous_risk - current_risk if np.isfinite(previous_risk) else np.nan
    crossed_below_020 = bool(
        np.isfinite(previous_risk) and previous_risk >= 0.20 and current_risk < 0.20
    )
    drop_alert = bool(np.isfinite(risk_drop) and risk_drop >= 0.03)

    return {
        "risk": current_risk,
        "label": risk_label(current_risk),
        "multiplier": multiplier,
        "risk_data_date": latest_ts.date().strftime("%d/%m/%y"),
        "risk_drop": risk_drop,
        "alert": crossed_below_020 or drop_alert,
    }, e, latest


def fetch_live_prices(e, latest):
    np = e["np"]
    try:
        r = e["requests"].get(
            "https://api.coingecko.com/api/v3/simple/price",
            params={"ids": "bitcoin", "vs_currencies": "aud,usd"},
            headers=e["REQUEST_HEADERS"],
            timeout=20,
        )
        r.raise_for_status()
        data = r.json().get("bitcoin", {})
        aud = float(data.get("aud", np.nan))
        usd = float(data.get("usd", np.nan))
    except Exception:
        aud, usd = np.nan, np.nan

    if not np.isfinite(aud) or aud <= 0:
        try:
            aud = float(e["fetch_live_btc_aud"]())
        except Exception:
            aud = np.nan
    if not np.isfinite(usd) or usd <= 0:
        usd = float(latest["price"])
    if (not np.isfinite(aud) or aud <= 0) and "usd_per_aud" in latest.index:
        fx = float(latest["usd_per_aud"])
        if np.isfinite(fx) and fx > 0:
            aud = float(latest["price"]) / fx
    return aud, usd


# The calculation helpers above are retained for historical validation imports.
# This former notification program is retired: never publish to ntfy.
def main():
    print(
        "Retired: dual-model ntfy notifications are disabled. "
        "Only the scheduled Cycle Trading daily summary may send ntfy."
    )


if __name__ == "__main__":
    main()
