#!/usr/bin/env python3
"""
BTC Composite DCA Monitor
=========================

This script does not place trades. It sends an ntfy notification and logs
the result.

Data sources:
- BTC price history: blockchain.com Charts API (free, keyless).
- MVRV Z-Score, Realized Price, Puell Multiple: bitcoin-data.com API
  (free tier, requires a token - see BITCOIN_DATA_API_TOKEN below).
- AHR999: computed in-script from price history using the published
  formula (5.84*log10(days_since_genesis) - 17.01 fair-value curve,
  combined with a 200-day geometric moving average cost basis). No
  separate API needed for this one.

Composite weighting:
- Power-law residual: 25%
- MVRV Z-Score: 25%
- AHR999: 20%
- Price vs realised price: 20%
- Puell Multiple: 10%

Price Penalty Factor (soft override):
- Price ≤ price_max_dca_usd (45k) → factor = 1.0 (full composite)
- Price ≥ price_min_dca_usd (65k) → factor = 0.0 (zero allocation)
- Between them → linear interpolation from 1.0 to 0.0
- Final composite = original_composite * price_factor

No hard price ceiling and no on/off gate. Every run computes a
composite_value in [0, 1] (1 = cheap, 0 = expensive) and reports a
suggested weekly allocation: weekly_slice_pct = composite_value * 100 / 12
- i.e. the full "if you were all-in today" allocation, spread over 12
weeks, recalculated fresh every run. There's always a number, even if
it's small - never a flat "wait, buy nothing."

This is NOT Benjamin Cowen's proprietary Risk Metric - it's your own
transparent composite built from public data and formulas.

Configuration split:
- Strategy parameters (the residual boundaries, spread window, metric
  staleness limit) live in config.json, committed to the repo - these
  aren't secret, they're your strategy.
- Credentials (BITCOIN_DATA_API_TOKEN, NTFY_TOPIC, NTFY_SERVER) come
  from environment variables / GitHub Actions secrets - never committed.
"""

from __future__ import annotations

import csv
import json
import math
import os
import sys
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import numpy as np
import requests

# Force UTF-8 for standard output to prevent encoding crashes on runners
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

# ================================================================
# File locations
# ================================================================

CONFIG_FILE = Path("config.json")
DATA_DIR = Path("data")
HISTORY_FILE = DATA_DIR / "risk_history.csv"

PRICE_HISTORY_URL = (
    "https://api.blockchain.info/charts/market-price"
    "?timespan=all&format=json&sampled=false"
)

BITCOIN_DATA_API_BASE = "https://api.bitcoin-data.com"
MVRV_ZSCORE_ENDPOINT = "/v1/mvrv-zscore/last"
REALIZED_PRICE_ENDPOINT = "/v1/realized-price/last"
PUELL_MULTIPLE_ENDPOINT = "/v1/puell-multiple/last"

GENESIS_DATE = datetime(2009, 1, 3, tzinfo=timezone.utc)

# Published AHR999 constants (5.84*log10(days) - 17.01 fair-value curve).
AHR999_EXPONENT = 5.84
AHR999_INTERCEPT = -17.01
AHR999_GMA_WINDOW_DAYS = 200

SPREAD_WEEKS = 12  # spread the full allocation across this many weekly slices

WEIGHTS = {
    "powerlaw": 0.25,
    "mvrv_z": 0.25,
    "ahr999": 0.20,
    "price_realised": 0.20,
    "puell": 0.10,
}


# ================================================================
# Configuration
# ================================================================

@dataclass
class Config:
    max_metric_age_hours: int

    price_max_dca_usd: float
    price_min_dca_usd: float

    cheap_residual: float
    neutral_residual: float
    expensive_residual: float

    ntfy_server: str
    ntfy_topic: str
    ntfy_token: str
    bitcoin_data_api_token: str


def load_config() -> Config:
    if not CONFIG_FILE.exists():
        raise RuntimeError(
            "config.json is missing. Copy config.example.json to "
            "config.json and fill in your strategy parameters."
        )

    with CONFIG_FILE.open("r", encoding="utf-8") as file:
        raw = json.load(file)

    # Credentials come from environment variables (GitHub secrets),
    # never from the committed config.json.
    ntfy_topic = os.environ.get("NTFY_TOPIC", str(raw.get("ntfy_topic", "")))
    ntfy_token = os.environ.get("NTFY_TOKEN", str(raw.get("ntfy_token", "")))
    ntfy_server = os.environ.get("NTFY_SERVER") or str(raw.get("ntfy_server", "https://ntfy.sh"))
    bitcoin_data_api_token = os.environ.get("BITCOIN_DATA_API_TOKEN", "")

    if not bitcoin_data_api_token:
        raise RuntimeError(
            "BITCOIN_DATA_API_TOKEN is not set. This is required to fetch "
            "MVRV Z-Score, Realized Price, and Puell Multiple."
        )

    return Config(
        max_metric_age_hours=int(raw["max_metric_age_hours"]),
        price_max_dca_usd=float(raw["price_max_dca_usd"]),
        price_min_dca_usd=float(raw["price_min_dca_usd"]),
        cheap_residual=float(raw["cheap_residual"]),
        neutral_residual=float(raw["neutral_residual"]),
        expensive_residual=float(raw["expensive_residual"]),
        ntfy_server=ntfy_server.rstrip("/"),
        ntfy_topic=ntfy_topic,
        ntfy_token=ntfy_token,
        bitcoin_data_api_token=bitcoin_data_api_token,
    )


# ================================================================
# General functions
# ================================================================

def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def utc_today() -> str:
    return utc_now().strftime("%Y-%m-%d")


def format_usd(value: float) -> str:
    return f"${value:,.0f}"


def clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


def parse_utc_date(value: str) -> datetime:
    """Parse a YYYY-MM-DD date string (as returned by bitcoin-data.com's
    'd' field) into a UTC midnight datetime."""
    return datetime.strptime(value, "%Y-%m-%d").replace(tzinfo=timezone.utc)


# ================================================================
# Bitcoin price and power law
# ================================================================

def fetch_price_history() -> tuple[np.ndarray, np.ndarray]:
    response = requests.get(PRICE_HISTORY_URL, timeout=30)
    response.raise_for_status()

    values = response.json()["values"]

    days = []
    prices = []

    for point in values:
        price = float(point["y"])
        date = datetime.fromtimestamp(point["x"], tz=timezone.utc)
        days_since_genesis = (date - GENESIS_DATE).days

        if days_since_genesis > 0 and price > 0:
            days.append(float(days_since_genesis))
            prices.append(price)

    if len(prices) < 1000:
        raise RuntimeError("Not enough BTC price history returned.")

    return np.array(days), np.array(prices)


def fit_power_law(
    days: np.ndarray,
    prices: np.ndarray,
) -> tuple[float, float, np.ndarray]:
    log_days = np.log10(days)
    log_prices = np.log10(prices)

    exponent, intercept = np.polyfit(log_days, log_prices, 1)
    fitted_logs = intercept + exponent * log_days

    return float(intercept), float(exponent), fitted_logs


# ================================================================
# AHR999 (computed in-script - no separate API needed)
# ================================================================

def compute_ahr999(days: np.ndarray, prices: np.ndarray) -> tuple[float, float, float]:
    """Returns (ahr999, gma_200, fair_value_curve) using the published
    formula: ahr999 = (price / 200-day geometric moving average)
                     * (price / (10^(5.84*log10(days_since_genesis) - 17.01)))
    """
    current_price = float(prices[-1])
    current_days = float(days[-1])

    window = prices[-AHR999_GMA_WINDOW_DAYS:] if len(prices) >= AHR999_GMA_WINDOW_DAYS else prices
    gma_200 = float(np.exp(np.mean(np.log(window))))

    fair_value_curve = float(10 ** (AHR999_EXPONENT * math.log10(current_days) + AHR999_INTERCEPT))

    ahr999 = (current_price / gma_200) * (current_price / fair_value_curve)
    return ahr999, gma_200, fair_value_curve


# ================================================================
# On-chain metrics via bitcoin-data.com (MVRV Z-Score, Realized
# Price, Puell Multiple)
# ================================================================

def _fetch_bitcoin_data_metric(endpoint: str, field: str, token: str) -> tuple[float, str]:
    """Returns (value, date_string) for a bitcoin-data.com /last endpoint."""
    url = f"{BITCOIN_DATA_API_BASE}{endpoint}"
    resp = requests.get(
        url,
        headers={"Authorization": f"Bearer {token}"},
        timeout=30,
    )
    resp.raise_for_status()
    data = resp.json()
    return float(data[field]), str(data["d"])


def fetch_onchain_metrics(config: Config) -> dict[str, Any]:
    """Fetches MVRV Z-Score, Realized Price, and Puell Multiple from
    bitcoin-data.com, and checks each isn't stale beyond
    config.max_metric_age_hours."""
    mvrv_z, mvrv_date = _fetch_bitcoin_data_metric(
        MVRV_ZSCORE_ENDPOINT, "mvrvZscore", config.bitcoin_data_api_token
    )
    realised_price, realised_date = _fetch_bitcoin_data_metric(
        REALIZED_PRICE_ENDPOINT, "realizedPrice", config.bitcoin_data_api_token
    )
    puell_multiple, puell_date = _fetch_bitcoin_data_metric(
        PUELL_MULTIPLE_ENDPOINT, "puellMultiple", config.bitcoin_data_api_token
    )

    oldest_date = min(
        parse_utc_date(mvrv_date),
        parse_utc_date(realised_date),
        parse_utc_date(puell_date),
    )
    age = utc_now() - oldest_date

    if age > timedelta(hours=config.max_metric_age_hours):
        raise RuntimeError(
            "On-chain metrics from bitcoin-data.com are stale. "
            f"Oldest dated value is {age} old; maximum permitted age is "
            f"{config.max_metric_age_hours} hours. "
            f"(mvrv={mvrv_date}, realised={realised_date}, puell={puell_date})"
        )

    if realised_price <= 0:
        raise RuntimeError("realised_price_usd must be greater than zero.")

    return {
        "mvrv_z": mvrv_z,
        "puell_multiple": puell_multiple,
        "realised_price_usd": realised_price,
    }


# ================================================================
# Composite risk calculation
# ================================================================

def indicator_value_score(
    value: float,
    cheap_boundary: float,
    neutral_boundary: float,
    expensive_boundary: float,
) -> float:
    """
    Returns a value score:
    1.0 = cheap / low risk
    0.5 = neutral
    0.0 = expensive / high risk
    """
    if value <= cheap_boundary:
        return 1.0

    if value <= neutral_boundary:
        return 1.0 - 0.5 * (
            (value - cheap_boundary)
            / (neutral_boundary - cheap_boundary)
        )

    if value >= expensive_boundary:
        return 0.0

    return 0.5 * (
        1.0
        - (value - neutral_boundary)
        / (expensive_boundary - neutral_boundary)
    )


def calculate_composite_risk(
    residual: float,
    mvrv_z: float,
    ahr999: float,
    price_realised_ratio: float,
    puell_multiple: float,
    config: Config,
) -> tuple[float, float, dict[str, float]]:
    scores = {
        "powerlaw": indicator_value_score(
            residual,
            config.cheap_residual,
            config.neutral_residual,
            config.expensive_residual,
        ),
        "mvrv_z": indicator_value_score(
            mvrv_z,
            cheap_boundary=0.50,
            neutral_boundary=3.00,
            expensive_boundary=5.00,
        ),
        "ahr999": indicator_value_score(
            ahr999,
            cheap_boundary=0.45,
            neutral_boundary=1.20,
            expensive_boundary=1.80,
        ),
        "price_realised": indicator_value_score(
            price_realised_ratio,
            cheap_boundary=0.90,
            neutral_boundary=1.50,
            expensive_boundary=2.00,
        ),
        "puell": indicator_value_score(
            puell_multiple,
            cheap_boundary=0.50,
            neutral_boundary=2.00,
            expensive_boundary=4.00,
        ),
    }

    composite_value = sum(
        scores[name] * WEIGHTS[name]
        for name in WEIGHTS
    )

    composite_value = clamp(composite_value, 0.0, 1.0)
    composite_risk = 1.0 - composite_value

    return composite_risk, composite_value, scores


# ================================================================
# Logging, notifications
# ================================================================

def append_history(row: dict[str, Any]) -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)

    columns = [
        "date_utc",
        "price_usd",
        "powerlaw_fitted_usd",
        "powerlaw_residual",
        "mvrv_z",
        "ahr999",
        "realised_price_usd",
        "price_realised_ratio",
        "puell_multiple",
        "composite_value",
        "composite_risk",
        "invest_pct_full",
        "weekly_slice_pct",
    ]

    new_file = not HISTORY_FILE.exists()

    with HISTORY_FILE.open("a", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=columns)

        if new_file:
            writer.writeheader()

        writer.writerow(row)


def send_ntfy(
    config: Config,
    title: str,
    message: str,
    priority: str,
    tags: str,
) -> None:
    if not config.ntfy_topic:
        print("\nNTFY_TOPIC is not set. Notification preview:\n")
        print(title)
        print(message)
        return

    url = f"{config.ntfy_server}/{config.ntfy_topic}"

    headers = {
        "Title": title,
        "Priority": priority,
        "Tags": tags,
    }

    if config.ntfy_token:
        headers["Authorization"] = f"Bearer {config.ntfy_token}"

    response = requests.post(
        url,
        data=message.encode("utf-8"),
        headers=headers,
        timeout=30,
    )

    response.raise_for_status()


# ================================================================
# Main
# ================================================================

def main() -> int:
    try:
        config = load_config()

        days, prices = fetch_price_history()
        _, exponent, fitted_logs = fit_power_law(days, prices)

        current_price = float(prices[-1])
        fitted_log = float(fitted_logs[-1])
        fitted_price = float(10 ** fitted_log)

        residual = math.log10(current_price) - fitted_log
        pct_from_trend = ((current_price / fitted_price) - 1.0) * 100

        ahr999, gma_200, ahr999_fair_value = compute_ahr999(days, prices)
        onchain = fetch_onchain_metrics(config)

        mvrv_z = onchain["mvrv_z"]
        puell_multiple = onchain["puell_multiple"]
        realised_price = onchain["realised_price_usd"]

        price_realised_ratio = current_price / realised_price

        composite_risk, composite_value, scores = (
            calculate_composite_risk(
                residual=residual,
                mvrv_z=mvrv_z,
                ahr999=ahr999,
                price_realised_ratio=price_realised_ratio,
                puell_multiple=puell_multiple,
                config=config,
            )
        )

        # ================================================================
        # SOFT PRICE PENALTY OVERRIDE
        # ================================================================
        # Apply a linear penalty factor based purely on USD price.
        # Price <= price_max_dca_usd (45k) -> factor = 1.0 (full composite)
        # Price >= price_min_dca_usd (65k) -> factor = 0.0 (zero allocation)
        # Between them -> linear interpolation from 1.0 to 0.0
        # This ensures the fundamentals still matter, but price acts as
        # a heavy discount that kills buying above $65k.
        if current_price <= config.price_max_dca_usd:
            price_factor = 1.0
        elif current_price >= config.price_min_dca_usd:
            price_factor = 0.0
        else:
            price_range = config.price_min_dca_usd - config.price_max_dca_usd
            price_factor = (config.price_min_dca_usd - current_price) / price_range

        # Multiply the original composite by the price factor.
        # This is the FINAL composite value used for DCA.
        composite_value = clamp(composite_value * price_factor, 0.0, 1.0)
        composite_risk = 1.0 - composite_value
        # ================================================================

        invest_pct_full = round(clamp(composite_value, 0.0, 1.0) * 100, 2)
        weekly_slice_pct = round(invest_pct_full / SPREAD_WEEKS, 4)

        append_history(
            {
                "date_utc": utc_today(),
                "price_usd": f"{current_price:.2f}",
                "powerlaw_fitted_usd": f"{fitted_price:.2f}",
                "powerlaw_residual": f"{residual:.5f}",
                "mvrv_z": f"{mvrv_z:.4f}",
                "ahr999": f"{ahr999:.4f}",
                "realised_price_usd": f"{realised_price:.2f}",
                "price_realised_ratio": f"{price_realised_ratio:.4f}",
                "puell_multiple": f"{puell_multiple:.4f}",
                "composite_value": f"{composite_value:.4f}",
                "composite_risk": f"{composite_risk:.4f}",
                "invest_pct_full": f"{invest_pct_full:.2f}",
                "weekly_slice_pct": f"{weekly_slice_pct:.4f}",
            }
        )

        message = (
            "BTC COMPOSITE DCA MONITOR\n"
            "=========================\n\n"
            f"Date (UTC):             {utc_today()}\n"
            f"BTC price:              {format_usd(current_price)}\n"
            f"Power-law trend:        {format_usd(fitted_price)}\n"
            f"Price vs trend:         {pct_from_trend:+.1f}%\n"
            f"Power-law residual:     {residual:+.4f}\n\n"
            "AUTOMATED METRICS\n"
            f"MVRV Z-Score:           {mvrv_z:.3f}\n"
            f"AHR999:                 {ahr999:.3f}\n"
            f"Realised price:         {format_usd(realised_price)}\n"
            f"Price / realised price: {price_realised_ratio:.3f}x\n"
            f"Puell Multiple:         {puell_multiple:.3f}\n\n"
            "COMPOSITE VALUE SCORES\n"
            f"Power law (25%):        {scores['powerlaw']:.3f}\n"
            f"MVRV Z (25%):           {scores['mvrv_z']:.3f}\n"
            f"AHR999 (20%):           {scores['ahr999']:.3f}\n"
            f"Price / realised (20%): {scores['price_realised']:.3f}\n"
            f"Puell (10%):            {scores['puell']:.3f}\n\n"
            f"Composite value (raw):  {composite_value / price_factor if price_factor > 0 else 0.0:.3f}\n"
            f"Price penalty factor:   {price_factor:.3f}\n"
            f"Final composite value:  {composite_value:.3f}\n"
            f"Composite proxy risk:   {composite_risk:.3f}\n\n"
            f"Full allocation today:  {invest_pct_full}% of your normal DCA amount\n"
            f"This week's slice (/{SPREAD_WEEKS}): {weekly_slice_pct}%\n"
            "Recalculated fresh every run - if conditions improve, "
            "next run's slice rises automatically. No price ceiling, "
            "no on/off gate - there's always a number, even a small one.\n\n"
            "This is your own transparent composite proxy. "
            "It is not Benjamin Cowen's proprietary risk metric. "
            "No trades are executed."
        )

        title = (
            f"BTC DCA - {weekly_slice_pct}% this week "
            f"(risk {composite_risk:.2f})"
        )
        priority = "default"
        tags = "bitcoin,bar_chart"

        print(message)
        send_ntfy(config, title, message, priority, tags)

        return 0

    except Exception as error:
        print(
            "\nBTC Composite DCA monitor failed.\n"
            f"Error: {type(error).__name__}: {error}\n"
            "No DCA figure was generated.\n",
            file=sys.stderr,
        )
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
