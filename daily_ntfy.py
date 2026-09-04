#!/usr/bin/env python3
"""
Daily ntfy summary for BTC Dynamic DCA V5.8.2.

Important:
- No recommended DCA amount or portfolio/capital information is sent.
- The Risk Score / Opportunity Rarity / Chance of Better Entry calculations
  are loaded directly from app.py so the notification uses the same engine.
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
    """V5.8.2 fixed calibrated settings used by DCA Today."""
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
        "composite_weights": {
            "mvrv": 0.25,
            "power_law": 0.25,
            "mayer": 0.15,
            "fear_greed": 0.10,
            "rsi": 0.05,
        },
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
    lookback_start = now_utc - dt.timedelta(days=365 * 11)
    params = fixed_engine_params(e)

    df = e["fetch_btc_history"](lookback_start, now_utc)
    if df is None or df.empty:
        raise RuntimeError("No BTC history returned.")

    fx = e["fetch_aud_usd_rates"](lookback_start, now_utc)
    token = e["get_bgeometrics_token"]()
    bg = e["fetch_bgeometrics_bundle"](
        lookback_start - dt.timedelta(days=300), now_utc, token
    )

    df = e["align_fx_to_dates"](df, fx)
    df = e["merge_bgeometrics"](df, bg)
    risk_df = e["add_risk_indicators"](df, "Composite V3.6", params)
    valid = risk_df.dropna(subset=["risk_score", "price"])
    if valid.empty:
        raise RuntimeError("Risk Score could not be calculated.")

    latest = valid.iloc[-1]
    current_risk = float(latest["risk_score"])

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

    chance = better.get("chance_materially_lower", np.nan)
    chance_text = f"{100.0 * float(chance):.0f}%" if np.isfinite(chance) else "n/a"

    local_now = now_utc.astimezone(BRISBANE)
    return {
        "date": local_now.strftime("%d/%m/%y"),
        "risk": current_risk,
        "risk_label": risk_label(current_risk),
        "btc_aud": live_aud,
        "btc_usd": live_usd,
        "rarity": rarity["rarity_label"],
        "better_entry": chance_text,
    }


def send_ntfy(summary):
    topic = os.getenv("NTFY_TOPIC", "").strip()
    if not topic:
        raise RuntimeError("GitHub secret NTFY_TOPIC is missing or empty.")

    # Accept either a topic name or a full ntfy topic URL in the secret.
    if topic.startswith("http://") or topic.startswith("https://"):
        url = topic.rstrip("/")
    else:
        url = "https://ntfy.sh/" + topic.strip("/")

    import requests

    message = (
        f"BTC Risk: {summary['risk']:.3f} — {summary['risk_label']}\n"
        f"BTC Price AUD: A${summary['btc_aud']:,.0f}\n"
        f"BTC Price USD: US${summary['btc_usd']:,.0f}\n"
        f"Opportunity Rarity: {summary['rarity']}\n"
        f"Chance of Better Entry: {summary['better_entry']}"
    )

    # Deliberately contains NO recommended DCA amount, capital, holdings,
    # portfolio value, or transaction information.
    response = requests.post(
        url,
        data=message.encode("utf-8"),
        headers={
            "Title": f"BTC Daily DCA — {summary['date']}",
            "Priority": "default",
            "Tags": "bitcoin,chart_with_upwards_trend",
            "Cache": "no",
        },
        timeout=20,
    )
    response.raise_for_status()


def main():
    summary = calculate_summary()
    print(
        f"Risk={summary['risk']:.3f} {summary['risk_label']}; "
        f"AUD={summary['btc_aud']:.0f}; USD={summary['btc_usd']:.0f}; "
        f"Rarity={summary['rarity']}; BetterEntry={summary['better_entry']}"
    )
    send_ntfy(summary)
    print("ntfy notification sent.")


if __name__ == "__main__":
    main()
