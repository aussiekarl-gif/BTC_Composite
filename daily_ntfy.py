#!/usr/bin/env python3
"""
Temporary dual-model ntfy comparison for BTC Dynamic DCA.

Compares, side-by-side:
- V5.8.2 Production (engines/production/app.py)
- V5.9 Research (engines/research/app.py)

Privacy / behavior:
- No portfolio balance, holdings, capital amount, or recommended AUD amount is sent.
- The notification shows each model's Risk Score and DCA multiplier only.
- Risk calculations use the latest fully closed UTC day; BTC prices are live.
- The existing GitHub Actions workflow can remain unchanged: it still runs
  `python daily_ntfy.py`.
"""

from __future__ import annotations

import ast
import datetime as dt
import os
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parent
PROD_APP = ROOT / "engines" / "production" / "app.py"
RESEARCH_APP = ROOT / "engines" / "research" / "app.py"
BRISBANE = ZoneInfo("Australia/Brisbane")


def load_app_engine(app_file: Path):
    if not app_file.exists():
        raise RuntimeError(f"Engine file not found: {app_file}")

    source = app_file.read_text(encoding="utf-8")
    tree = ast.parse(source, filename=str(app_file))
    safe_nodes = []

    for node in tree.body:
        if (
            isinstance(node, ast.Expr)
            and isinstance(node.value, ast.Call)
            and isinstance(node.value.func, ast.Attribute)
            and isinstance(node.value.func.value, ast.Name)
            and node.value.func.value.id == "st"
            and node.value.func.attr == "set_page_config"
        ):
            break
        safe_nodes.append(node)

    module = ast.Module(body=safe_nodes, type_ignores=[])
    ast.fix_missing_locations(module)
    ns = {"__file__": str(app_file), "__name__": f"btc_engine_{app_file.parent.name}"}
    exec(compile(module, str(app_file), "exec"), ns)
    return ns


def fixed_engine_params(e, model: str, start_date: dt.date, end_date: dt.datetime):
    params = {
        "risk_model": model,
        "frequency": "Weekly",
        "day_of_week": end_date.weekday(),
        "fund_cheap": e["DEFAULT_FUND_CHEAP"],
        "fund_expensive": e["DEFAULT_FUND_EXPENSIVE"],
        "pl_cheap": e["DEFAULT_PL_CHEAP"],
        "pl_expensive": e["DEFAULT_PL_EXPENSIVE"],
        "total_capital_aud": 500000.0,  # compatibility only; never sent
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


def calculate_model_summary(app_file: Path, model: str):
    e = load_app_engine(app_file)
    np, pd = e["np"], e["pd"]
    now_utc = dt.datetime.now(dt.timezone.utc)

    closed_cutoff_utc = dt.datetime.combine(now_utc.date(), dt.time.min, tzinfo=dt.timezone.utc)
    closed_end_utc = closed_cutoff_utc - dt.timedelta(microseconds=1)

    if model == "Research WF Power Law":
        # R2/R3 research engine defines its calibration history start explicitly.
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


def send_ntfy(prod, research, btc_aud, btc_usd):
    topic = os.getenv("NTFY_TOPIC", "").strip()
    if not topic:
        raise RuntimeError("GitHub secret NTFY_TOPIC is missing or empty.")

    url = topic.rstrip("/") if topic.startswith(("http://", "https://")) else "https://ntfy.sh/" + topic.strip("/")

    import requests

    now_local = dt.datetime.now(dt.timezone.utc).astimezone(BRISBANE)
    weekday = now_local.weekday() < 5
    market_line = (
        "ASX:IBIT: weekday trading day (check ASX holiday status)"
        if weekday
        else "ASX:IBIT: market closed (weekend)"
    )

    rel = research["multiplier"] / prod["multiplier"] if prod["multiplier"] > 0 else float("nan")
    rel_text = f"{(rel - 1) * 100:+.0f}% vs Production multiplier" if rel == rel else "n/a"

    lines = [
        "TEMPORARY DUAL-MODEL COMPARISON",
        "",
        f"V5.8.2 Production: Risk {prod['risk']:.3f} ({prod['label']}) | DCA {prod['multiplier']:.2f}x",
        f"V5.9 Research:    Risk {research['risk']:.3f} ({research['label']}) | DCA {research['multiplier']:.2f}x",
        f"Research sizing difference: {rel_text}",
        "",
        f"Risk data through: Prod {prod['risk_data_date']} | Research {research['risk_data_date']}",
        f"BTC Price AUD: A${btc_aud:,.0f} (live)",
        f"BTC Price USD: US${btc_usd:,.0f} (live)",
        market_line,
        "",
        "Research is comparison-only; V5.8.2 remains the production control.",
    ]

    any_alert = prod["alert"] or research["alert"]
    if any_alert:
        lines.insert(1, "Risk-drop condition detected in at least one model")

    response = requests.post(
        url,
        data="\n".join(lines).encode("utf-8"),
        headers={
            "Title": f"BTC DCA Compare - {now_local.strftime('%d/%m/%y')}",
            "Priority": "high" if any_alert else "default",
            "Tags": "bitcoin,warning" if any_alert else "bitcoin,chart_with_upwards_trend",
            "Cache": "no",
        },
        timeout=20,
    )
    response.raise_for_status()


def main():
    prod, prod_engine, prod_latest = calculate_model_summary(PROD_APP, "Composite V3.6")
    research, research_engine, research_latest = calculate_model_summary(RESEARCH_APP, "Research WF Power Law")
    btc_aud, btc_usd = fetch_live_prices(prod_engine, prod_latest)

    print(
        f"Production: risk={prod['risk']:.3f}, mult={prod['multiplier']:.3f}; "
        f"Research: risk={research['risk']:.3f}, mult={research['multiplier']:.3f}; "
        f"BTC AUD={btc_aud:.0f}, USD={btc_usd:.0f}"
    )
    send_ntfy(prod, research, btc_aud, btc_usd)
    print("Dual-model ntfy notification sent.")


if __name__ == "__main__":
    main()
