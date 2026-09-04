#!/usr/bin/env python3
"""
Daily ntfy summary + Risk Drop Alert for BTC Dynamic DCA V5.8.2 Clean R2.

Important:
- No recommended DCA amount or portfolio/capital information is sent.
- The Risk Score / Opportunity Rarity / Better Entry Evidence calculations
  are loaded directly from app.py so the notification uses the same engine.
- Risk alerts are informational only and do not change Smart DCA sizing.
- Risk/alert calculations use only the latest fully closed UTC day; BTC prices remain live.
- ASX:IBIT availability is labelled by Monday-Friday trading-day status.
- The better-entry horizon is fixed at 156 weeks (3 years), matching the
  default DCA Today horizon.
"""

from __future__ import annotations

import ast
import datetime as dt
import os
from pathlib import Path
from zoneinfo import ZoneInfo

APP_FILE = Path(__file__).with_name("app.py")
BRISBANE = ZoneInfo("Australia/Brisbane")


def load_app_engine():
    """Load only imports/constants/functions above Streamlit UI startup."""
    source = APP_FILE.read_text(encoding="utf-8")
    tree = ast.parse(source, filename=str(APP_FILE))

    safe_nodes = []
    for node in tree.body:
        # app.py starts UI at st.set_page_config(...). Everything above it is
        # the shared calculation/data engine.
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
    ns = {"__file__": str(APP_FILE), "__name__": "btc_dca_engine"}
    exec(compile(module, str(APP_FILE), "exec"), ns)
    return ns


def fixed_engine_params(e):
    """V5.8.2 fixed calibrated settings used by DCA Today.

    The end_date is overridden in calculate_summary() with the last fully closed
    UTC day for deterministic ntfy risk calculations.
    """
    today = dt.datetime.now(dt.timezone.utc).date()
    start_date = today - dt.timedelta(days=365 * 11)
    return {
        "risk_model": "Composite V3.6",
        "frequency": "Weekly",
        "day_of_week": today.weekday(),
        "fund_cheap": e["DEFAULT_FUND_CHEAP"],
        "fund_expensive": e["DEFAULT_FUND_EXPENSIVE"],
        "pl_cheap": e["DEFAULT_PL_CHEAP"],
        "pl_expensive": e["DEFAULT_PL_EXPENSIVE"],
        "total_capital_aud": 500000.0,  # compatibility only; not sent or used for risk
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
        "end_date": dt.datetime.combine(today, dt.time.max, tzinfo=dt.timezone.utc),
    }


def fetch_live_prices(requests, np, headers):
    url = "https://api.coingecko.com/api/v3/simple/price"
    r = requests.get(
        url,
        params={"ids": "bitcoin", "vs_currencies": "aud,usd"},
        headers=headers,
        timeout=20,
    )
    r.raise_for_status()
    data = r.json().get("bitcoin", {})
    aud = float(data.get("aud", np.nan))
    usd = float(data.get("usd", np.nan))
    return aud, usd


def risk_label(risk):
    if risk <= 0.20:
        return "VERY LOW"
    if risk <= 0.40:
        return "LOW"
    if risk <= 0.60:
        return "NEUTRAL"
    if risk <= 0.80:
        return "HIGH"
    return "VERY HIGH"


def calculate_summary():
    e = load_app_engine()
    np, pd = e["np"], e["pd"]
    now_utc = dt.datetime.now(dt.timezone.utc)

    # IMPORTANT: Risk is calculated only from fully closed UTC calendar days.
    # This makes the valuation reading deterministic during the current day, even
    # when BTC or external API values are still moving/updating intraday.
    closed_cutoff_utc = dt.datetime.combine(
        now_utc.date(), dt.time.min, tzinfo=dt.timezone.utc
    )
    closed_end_utc = closed_cutoff_utc - dt.timedelta(microseconds=1)
    lookback_start = closed_end_utc - dt.timedelta(days=365 * 11)
    params = fixed_engine_params(e)
    params["end_date"] = closed_end_utc

    df = e["fetch_btc_history"](lookback_start, closed_end_utc)
    if df is None or df.empty:
        raise RuntimeError("No BTC history returned.")

    fx = e["fetch_aud_usd_rates"](lookback_start, closed_end_utc)
    token = e["get_bgeometrics_token"]()
    bg = e["fetch_bgeometrics_bundle"](
        lookback_start - dt.timedelta(days=300), closed_end_utc, token
    )

    df = e["align_fx_to_dates"](df, fx)
    df = e["merge_bgeometrics"](df, bg)
    risk_df = e["add_risk_indicators"](df, "Composite V3.6", params)
    valid = risk_df.dropna(subset=["risk_score", "price"]).copy()

    # Defence in depth: even if an upstream source unexpectedly returns today's
    # partial observation, exclude it from the Risk Score and alert calculations.
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
        raise RuntimeError("Risk Score could not be calculated from a fully closed UTC day.")

    latest = valid.iloc[-1]
    current_risk = float(latest["risk_score"])

    if isinstance(valid.index, pd.DatetimeIndex):
        latest_ts = pd.Timestamp(valid.index[-1])
    elif "date" in valid.columns:
        latest_ts = pd.Timestamp(valid.iloc[-1]["date"])
    else:
        latest_ts = pd.Timestamp(closed_end_utc.date())
    if latest_ts.tzinfo is not None:
        latest_ts = latest_ts.tz_convert("UTC").tz_localize(None)
    risk_data_date = latest_ts.date()

    # Alert comparisons use adjacent fully closed historical observations.
    # No portfolio/capital information is involved.
    risk_obs = valid["risk_score"].dropna().astype(float)
    previous_risk = float(risk_obs.iloc[-2]) if len(risk_obs) >= 2 else np.nan
    risk_drop = (previous_risk - current_risk) if np.isfinite(previous_risk) else np.nan
    crossed_below_020 = bool(
        np.isfinite(previous_risk) and previous_risk >= 0.20 and current_risk < 0.20
    )

    cutoff_90d = pd.Timestamp(valid.index[-1]) - pd.Timedelta(days=90) if isinstance(valid.index, pd.DatetimeIndex) else None
    if cutoff_90d is not None:
        prior_90 = risk_obs[(risk_obs.index >= cutoff_90d) & (risk_obs.index < risk_obs.index[-1])]
    else:
        prior_90 = risk_obs.iloc[-91:-1]
    prior_90d_low = float(prior_90.min()) if len(prior_90) else np.nan
    new_90d_low = bool(np.isfinite(prior_90d_low) and current_risk < prior_90d_low)
    drop_alert = bool(np.isfinite(risk_drop) and risk_drop >= 0.03)
    alert_reasons = []
    if crossed_below_020:
        alert_reasons.append("Risk crossed below 0.20")
    if drop_alert:
        alert_reasons.append(f"Risk fell {risk_drop:.3f} since previous closed reading")
    if new_90d_low:
        alert_reasons.append("New 90-day Risk low")

    if isinstance(valid.index, pd.DatetimeIndex):
        weekly = valid["risk_score"].resample("W-MON").last().dropna()
    elif "date" in valid.columns:
        weekly = valid.set_index("date")["risk_score"].resample("W-MON").last().dropna()
    else:
        weekly = valid["risk_score"].dropna()

    rarity = e["opportunity_rarity_from_history"](weekly, current_risk)
    better = e["lower_risk_opportunity_stats"](weekly, current_risk, 156.0)

    live_aud, live_usd = fetch_live_prices(
        e["requests"], np, e["REQUEST_HEADERS"]
    )
    # Fallback AUD to the app's own live helper / historical quote.
    if not np.isfinite(live_aud) or live_aud <= 0:
        live_aud = e["fetch_live_btc_aud"]()
    if not np.isfinite(live_aud) or live_aud <= 0:
        usd_per_aud = float(latest["usd_per_aud"])
        live_aud = float(latest["price"]) / usd_per_aud
    if not np.isfinite(live_usd) or live_usd <= 0:
        live_usd = float(latest["price"])

    cycles_used = int(better.get("cycles_used", 0) or 0)
    cycle_successes = int(better.get("cycle_successes", 0) or 0)
    better_entry_text = (
        f"{cycle_successes} of {cycles_used} cycles" if cycles_used >= 1 else "n/a"
    )

    local_now = now_utc.astimezone(BRISBANE)
    # User can execute via ASX:IBIT Monday-Friday. This intentionally treats
    # weekdays as trading days; exceptional ASX public holidays are labelled
    # separately in the message caveat rather than guessed.
    ibit_weekday = local_now.weekday() < 5
    return {
        "date": local_now.strftime("%d/%m/%y"),
        "risk_data_date": risk_data_date.strftime("%d/%m/%y"),
        "risk": current_risk,
        "risk_label": risk_label(current_risk),
        "btc_aud": live_aud,
        "btc_usd": live_usd,
        "rarity": rarity["rarity_label"],
        "better_entry": better_entry_text,
        "previous_risk": previous_risk,
        "risk_drop": risk_drop,
        "alert_reasons": alert_reasons,
        "risk_alert": bool(alert_reasons),
        "ibit_weekday": ibit_weekday,
    }


def send_ntfy(summary):
    topic = os.getenv("NTFY_TOPIC", "").strip()
    if not topic:
        raise RuntimeError("GitHub secret NTFY_TOPIC is missing or empty.")

    if topic.startswith("http://") or topic.startswith("https://"):
        url = topic.rstrip("/")
    else:
        url = "https://ntfy.sh/" + topic.strip("/")

    import requests

    ibit_status = (
        "ASX:IBIT - weekday trading day (check ASX holiday status)"
        if summary["ibit_weekday"]
        else "ASX:IBIT - market closed (weekend); reassess next trading day"
    )

    lines = [
        f"BTC Risk: {summary['risk']:.3f} - {summary['risk_label']}",
        f"Risk data through: {summary['risk_data_date']} (closed UTC day)",
        f"BTC Price AUD: A${summary['btc_aud']:,.0f} (live)",
        f"BTC Price USD: US${summary['btc_usd']:,.0f} (live)",
        f"Opportunity Rarity: {summary['rarity']}",
        f"Better Entry Evidence: {summary['better_entry']}",
        ibit_status,
    ]

    if summary["risk_alert"]:
        lines.insert(0, "RISK DROP ALERT")
        lines.append("Trigger: " + "; ".join(summary["alert_reasons"]))
        if not summary["ibit_weekday"]:
            lines.append("Weekend signal only - IBIT cannot be bought until ASX trading resumes.")
        title = f"BTC BUY OPPORTUNITY - {summary['date']}"
        priority = "high"
        tags = "bitcoin,warning"
    else:
        title = f"BTC Daily DCA - {summary['date']}"
        priority = "default"
        tags = "bitcoin,chart_with_upwards_trend"

    message = "\n".join(lines)

    # Deliberately contains NO recommended DCA amount, capital, holdings,
    # portfolio value, or transaction information.
    response = requests.post(
        url,
        data=message.encode("utf-8"),
        headers={
            "Title": title,
            "Priority": priority,
            "Tags": tags,
            "Cache": "no",
        },
        timeout=20,
    )
    response.raise_for_status()


def main():
    summary = calculate_summary()
    print(
        f"Risk={summary['risk']:.3f} {summary['risk_label']} "
        f"(closed through {summary['risk_data_date']}); "
        f"AUD={summary['btc_aud']:.0f}; USD={summary['btc_usd']:.0f}; "
        f"Rarity={summary['rarity']}; BetterEntry={summary['better_entry']}; "
        f"Alert={summary['risk_alert']}; IBITWeekday={summary['ibit_weekday']}"
    )
    send_ntfy(summary)
    print("ntfy notification sent.")


if __name__ == "__main__":
    main()
