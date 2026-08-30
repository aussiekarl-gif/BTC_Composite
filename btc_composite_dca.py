#!/usr/bin/env python3
"""
BTC Composite DCA Risk Proxy
============================

A notification-only Bitcoin DCA monitor.

This script DOES NOT execute trades.

It calculates a transparent composite risk proxy from:
    - Power-law residual:        25%
    - MVRV Z-Score:              25%
    - AHR999:                    20%
    - Price / realised price:    20%
    - Puell Multiple:            10%

The score is deliberately named "composite proxy risk"; it is NOT
Benjamin Cowen's proprietary Risk Metric.

DCA START condition:
    1. BTC price <= entry_price_usd
    2. composite proxy risk <= risk_start_threshold
    3. Conditions are valid for confirmation_days consecutive checks

Live metric API providers:
    - BTC price: Blockchain.info market-price chart
    - MVRV Z-Score: CryptoQuant API V2
    - AHR999 / Puell: CoinGlass API V4
    - Realised price: configurable API endpoint OR manual metrics JSON

Configuration:
    - Local: config.json (never commit it)
    - GitHub Actions: environment variables/secrets override config.json
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


# ===================================================================
# Defaults
# ===================================================================

DEFAULT_CONFIG_PATH = Path("config.json")
DATA_DIR = Path("data")
HISTORY_CSV = DATA_DIR / "risk_history.csv"
STATE_JSON = DATA_DIR / "state.json"

PRICE_HISTORY_URL = (
    "https://api.blockchain.info/charts/market-price"
    "?timespan=all&format=json&sampled=false"
)

GENESIS_DATE = datetime(2009, 1, 3, tzinfo=timezone.utc)
MIN_HISTORY_POINTS = 1000

REQUEST_HEADERS = {
    "User-Agent": "btc-composite-dca/1.0 GitHub Actions monitor"
}

# Full requested architecture. Total must equal 1.00.
WEIGHTS = {
    "powerlaw": 0.25,
    "mvrv_z": 0.25,
    "ahr999": 0.20,
    "price_realised": 0.20,
    "puell": 0.10,
}


# ===================================================================
# Configuration
# ===================================================================

@dataclass(frozen=True)
class Config:
    entry_price_usd: float
    risk_start_threshold: float
    confirmation_days: int
    max_metric_age_hours: int

    # Power-law mapping.
    # Lower residual = farther below trend = lower risk.
    cheap_residual: float
    neutral_residual: float
    expensive_residual: float

    # API endpoints / credentials
    cryptoquant_base_url: str
    cryptoquant_api_key: str | None
    cryptoquant_mvrv_endpoint: str

    coinglass_base_url: str
    coinglass_api_key: str | None
    coinglass_ahr999_endpoint: str
    coinglass_puell_endpoint: str

    # Realised price:
    # "manual" = data/manual_metrics.json
    # "api" = realised_price_endpoint
    realised_price_source: str
    realised_price_endpoint: str | None
    realised_price_api_key: str | None
    realised_price_api_key_header: str

    # ntfy
    ntfy_server: str
    ntfy_topic: str | None
    ntfy_token: str | None


def read_json_file(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}

    with path.open("r", encoding="utf-8") as file:
        payload = json.load(file)

    if not isinstance(payload, dict):
        raise ValueError(f"{path} must contain one JSON object.")

    return payload


def env_or_config(
    config: dict[str, Any],
    env_name: str,
    config_name: str,
    default: Any = None,
) -> Any:
    """
    GitHub Actions env vars take priority over config.json.
    This lets secrets stay outside the repository.
    """
    value = os.getenv(env_name)

    if value is not None and value != "":
        return value

    return config.get(config_name, default)


def as_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value

    return str(value).lower() in {"1", "true", "yes", "on"}


def load_config() -> Config:
    raw = read_json_file(DEFAULT_CONFIG_PATH)

    return Config(
        entry_price_usd=float(
            env_or_config(raw, "ENTRY_PRICE_USD", "entry_price_usd", 60000)
        ),
        risk_start_threshold=float(
            env_or_config(
                raw,
                "RISK_START_THRESHOLD",
                "risk_start_threshold",
                0.30,
            )
        ),
        confirmation_days=int(
            env_or_config(raw, "CONFIRMATION_DAYS", "confirmation_days", 2)
        ),
        max_metric_age_hours=int(
            env_or_config(
                raw,
                "MAX_METRIC_AGE_HOURS",
                "max_metric_age_hours",
                36,
            )
        ),
        cheap_residual=float(
            env_or_config(raw, "CHEAP_RESIDUAL", "cheap_residual", -0.60)
        ),
        neutral_residual=float(
            env_or_config(raw, "NEUTRAL_RESIDUAL", "neutral_residual", -0.32)
        ),
        expensive_residual=float(
            env_or_config(
                raw,
                "EXPENSIVE_RESIDUAL",
                "expensive_residual",
                0.35,
            )
        ),
        cryptoquant_base_url=str(
            env_or_config(
                raw,
                "CRYPTOQUANT_BASE_URL",
                "cryptoquant_base_url",
                "https://api.cryptoquant.com",
            )
        ).rstrip("/"),
        cryptoquant_api_key=env_or_config(
            raw,
            "CRYPTOQUANT_API_KEY",
            "cryptoquant_api_key",
        ),
        cryptoquant_mvrv_endpoint=str(
            env_or_config(
                raw,
                "CRYPTOQUANT_MVRV_ENDPOINT",
                "cryptoquant_mvrv_endpoint",
                "/v2/community/bitcoin-mvrv-z-score",
            )
        ),
        coinglass_base_url=str(
            env_or_config(
                raw,
                "COINGLASS_BASE_URL",
                "coinglass_base_url",
                "https://open-api-v4.coinglass.com",
            )
        ).rstrip("/"),
        coinglass_api_key=env_or_config(
            raw,
            "COINGLASS_API_KEY",
            "coinglass_api_key",
        ),
        coinglass_ahr999_endpoint=str(
            env_or_config(
                raw,
                "COINGLASS_AHR999_ENDPOINT",
                "coinglass_ahr999_endpoint",
                "/api/indicator/ahr999",
            )
        ),
        coinglass_puell_endpoint=str(
            env_or_config(
                raw,
                "COINGLASS_PUELL_ENDPOINT",
                "coinglass_puell_endpoint",
                "/api/indicator/puell-multiple",
            )
        ),
        realised_price_source=str(
            env_or_config(
                raw,
                "REALISED_PRICE_SOURCE",
                "realised_price_source",
                "manual",
            )
        ).lower(),
        realised_price_endpoint=env_or_config(
            raw,
            "REALISED_PRICE_ENDPOINT",
            "realised_price_endpoint",
        ),
        realised_price_api_key=env_or_config(
            raw,
            "REALISED_PRICE_API_KEY",
            "realised_price_api_key",
        ),
        realised_price_api_key_header=str(
            env_or_config(
                raw,
                "REALISED_PRICE_API_KEY_HEADER",
                "realised_price_api_key_header",
                "Authorization",
            )
        ),
        ntfy_server=str(
            env_or_config(
                raw,
                "NTFY_SERVER",
                "ntfy_server",
                "https://ntfy.sh",
            )
        ).rstrip("/"),
        ntfy_topic=env_or_config(raw, "NTFY_TOPIC", "ntfy_topic"),
        ntfy_token=env_or_config(raw, "NTFY_TOKEN", "ntfy_token"),
    )


def validate_config(config: Config) -> None:
    if config.entry_price_usd <= 0:
        raise ValueError("entry_price_usd must be greater than zero.")

    if not 0.0 <= config.risk_start_threshold <= 1.0:
        raise ValueError("risk_start_threshold must be from 0.0 to 1.0.")

    if config.confirmation_days < 1:
        raise ValueError("confirmation_days must be at least 1.")

    if config.max_metric_age_hours < 1:
        raise ValueError("max_metric_age_hours must be at least 1.")

    if not (
        config.cheap_residual
        < config.neutral_residual
        < config.expensive_residual
    ):
        raise ValueError(
            "Power-law residuals must satisfy "
            "cheap_residual < neutral_residual < expensive_residual."
        )

    if round(sum(WEIGHTS.values()), 10) != 1.0:
        raise ValueError("Composite weights must total exactly 1.0.")

    if config.realised_price_source not in {"manual", "api"}:
        raise ValueError(
            "realised_price_source must be either 'manual' or 'api'."
        )


# ===================================================================
# General helpers
# ===================================================================

def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def utc_today() -> str:
    return utc_now().strftime("%Y-%m-%d")


def format_usd(value: float) -> str:
    return f"${value:,.0f}"


def clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


def ensure_success(response: requests.Response, source: str) -> None:
    try:
        response.raise_for_status()
    except requests.HTTPError as exc:
        body = response.text[:500]
        raise RuntimeError(
            f"{source} returned HTTP {response.status_code}: {body}"
        ) from exc


def latest_numeric_value(payload: Any, candidate_keys: list[str]) -> float:
    """
    Searches a common indicator-API response structure for the most recent
    numeric observation.

    This is intentionally flexible because provider schemas can vary by
    API version and plan. It will fail loudly if no expected field is found.
    """
    if isinstance(payload, dict):
        for key in candidate_keys:
            if key in payload and payload[key] is not None:
                return float(payload[key])

        for key in ("data", "result", "items", "values"):
            if key in payload:
                return latest_numeric_value(payload[key], candidate_keys)

    if isinstance(payload, list):
        if not payload:
            raise ValueError("API response contained an empty list.")

        # Most APIs return chronological data; use last valid item.
        for item in reversed(payload):
            try:
                return latest_numeric_value(item, candidate_keys)
            except (KeyError, TypeError, ValueError):
                continue

    raise ValueError(
        "Could not find a numeric value. "
        f"Expected one of: {candidate_keys}"
    )


# ===================================================================
# BTC price and power-law model
# ===================================================================

def fetch_price_history() -> tuple[np.ndarray, np.ndarray]:
    response = requests.get(
        PRICE_HISTORY_URL,
        headers=REQUEST_HEADERS,
        timeout=30,
    )
    ensure_success(response, "Blockchain.info market-price API")

    values = response.json().get("values", [])

    days: list[float] = []
    prices: list[float] = []

    for point in values:
        timestamp = point.get("x")
        value = point.get("y")

        if timestamp is None or value is None:
            continue

        price = float(value)
        day = (
            datetime.fromtimestamp(timestamp, tz=timezone.utc)
            - GENESIS_DATE
        ).days

        if day > 0 and price > 0:
            days.append(float(day))
            prices.append(price)

    if len(prices) < MIN_HISTORY_POINTS:
        raise RuntimeError(
            f"Only {len(prices)} usable price observations received; "
            f"expected at least {MIN_HISTORY_POINTS}."
        )

    return np.array(days, dtype=float), np.array(prices, dtype=float)


def fit_power_law(
    days: np.ndarray,
    prices: np.ndarray,
) -> tuple[float, float, np.ndarray]:
    """
    Fits:
        log10(price) = intercept + exponent * log10(days since genesis)
    """
    log_days = np.log10(days)
    log_prices = np.log10(prices)

    exponent, intercept = np.polyfit(log_days, log_prices, 1)
    fitted_logs = intercept + exponent * log_days

    return float(intercept), float(exponent), fitted_logs


# ===================================================================
# External metric fetchers
# ===================================================================

def fetch_mvrv_zscore(config: Config) -> float:
    """
    Fetch current MVRV Z-Score from CryptoQuant.

    If CryptoQuant changes its JSON schema, update only candidate_keys
    or this function after examining the response body.
    """
    if not config.cryptoquant_api_key:
        raise RuntimeError("CRYPTOQUANT_API_KEY is missing.")

    url = (
        f"{config.cryptoquant_base_url}"
        f"{config.cryptoquant_mvrv_endpoint}"
    )

    response = requests.get(
        url,
        headers={
            "Authorization": f"Bearer {config.cryptoquant_api_key}",
            "User-Agent": REQUEST_HEADERS["User-Agent"],
        },
        timeout=30,
    )
    ensure_success(response, "CryptoQuant MVRV Z-Score API")

    payload = response.json()

    return latest_numeric_value(
        payload,
        candidate_keys=[
            "mvrv_z_score",
            "mvrv_z",
            "mvrvZScore",
            "value",
            "close",
        ],
    )


def coinglass_get(
    config: Config,
    endpoint: str,
    source_name: str,
) -> Any:
    if not config.coinglass_api_key:
        raise RuntimeError("COINGLASS_API_KEY is missing.")

    url = f"{config.coinglass_base_url}{endpoint}"

    response = requests.get(
        url,
        headers={
            "CG-API-KEY": config.coinglass_api_key,
            "User-Agent": REQUEST_HEADERS["User-Agent"],
        },
        timeout=30,
    )
    ensure_success(response, source_name)

    payload = response.json()

    # CoinGlass commonly returns code "0" on a successful request.
    if isinstance(payload, dict):
        code = payload.get("code")

        if code not in (None, 0, "0"):
            raise RuntimeError(
                f"{source_name} API error: {json.dumps(payload)[:500]}"
            )

    return payload


def fetch_ahr999(config: Config) -> float:
    """
    Fetch current AHR999 from CoinGlass.

    Confirm the exact endpoint included in your CoinGlass plan. If its
    published API path differs, change only config.json:
      coinglass_ahr999_endpoint
    """
    payload = coinglass_get(
        config,
        config.coinglass_ahr999_endpoint,
        "CoinGlass AHR999 API",
    )

    return latest_numeric_value(
        payload,
        candidate_keys=[
            "ahr999",
            "ahr_999",
            "ahr999Index",
            "value",
            "close",
        ],
    )


def fetch_puell_multiple(config: Config) -> float:
    """
    Fetch current Puell Multiple from CoinGlass.

    Confirm the exact endpoint in your CoinGlass dashboard/API plan and
    override coinglass_puell_endpoint in config.json where needed.
    """
    payload = coinglass_get(
        config,
        config.coinglass_puell_endpoint,
        "CoinGlass Puell Multiple API",
    )

    return latest_numeric_value(
        payload,
        candidate_keys=[
            "puell_multiple",
            "puellMultiple",
            "puell",
            "value",
            "close",
        ],
    )


def parse_utc_datetime(value: str) -> datetime:
    text = value.replace("Z", "+00:00")
    result = datetime.fromisoformat(text)

    if result.tzinfo is None:
        return result.replace(tzinfo=timezone.utc)

    return result.astimezone(timezone.utc)


def fetch_realised_price_manual(config: Config) -> float:
    """
    Loads a manually updated realised price from:
        data/manual_metrics.json

    Expected example:
    {
      "as_of_utc": "2026-08-30T00:00:00Z",
      "realised_price_usd": 58200.00
    }
    """
    path = DATA_DIR / "manual_metrics.json"

    if not path.exists():
        raise RuntimeError(
            f"Manual realised-price file not found: {path}. "
            "Either create it or configure realised_price_source='api'."
        )

    data = read_json_file(path)

    if "as_of_utc" not in data or "realised_price_usd" not in data:
        raise ValueError(
            f"{path} requires as_of_utc and realised_price_usd."
        )

    as_of = parse_utc_datetime(str(data["as_of_utc"]))
    age = utc_now() - as_of

    if age > timedelta(hours=config.max_metric_age_hours):
        raise RuntimeError(
            f"Manual realised-price data is stale ({age}). "
            f"Maximum permitted age is {config.max_metric_age_hours} hours."
        )

    value = float(data["realised_price_usd"])

    if value <= 0:
        raise ValueError("manual realised_price_usd must be > 0.")

    return value


def fetch_realised_price_api(config: Config) -> float:
    """
    Generic realised-price API fetcher.

    You must configure:
      realised_price_endpoint
      realised_price_api_key (if required)
      realised_price_api_key_header

    This generic function expects one of these likely fields:
      realised_price_usd, realized_price_usd, realised_price,
      realized_price, value, close

    If your chosen provider uses another response schema, customise this
    function rather than weakening missing-data protections.
    """
    if not config.realised_price_endpoint:
        raise RuntimeError(
            "realised_price_endpoint is required when source is 'api'."
        )

    headers = {"User-Agent": REQUEST_HEADERS["User-Agent"]}

    if config.realised_price_api_key:
        headers[config.realised_price_api_key_header] = (
            config.realised_price_api_key
        )

    response = requests.get(
        config.realised_price_endpoint,
        headers=headers,
        timeout=30,
    )
    ensure_success(response, "Realised price API")

    payload = response.json()

    value = latest_numeric_value(
        payload,
        candidate_keys=[
            "realised_price_usd",
            "realized_price_usd",
            "realised_price",
            "realized_price",
            "value",
            "close",
        ],
    )

    if value <= 0:
        raise ValueError("API returned a non-positive realised price.")

    return value


def fetch_realised_price(config: Config) -> float:
    if config.realised_price_source == "manual":
        return fetch_realised_price_manual(config)

    return fetch_realised_price_api(config)


# ===================================================================
# Composite score functions
# ===================================================================

def indicator_value_score(
    value: float,
    cheap_boundary: float,
    neutral_boundary: float,
    expensive_boundary: float,
) -> float:
    """
    Converts raw metric reading to a 0–1 valuation score:

        1.00 = cheap / favourable for long-term DCA
        0.50 = neutral
        0.00 = expensive / unfavourable for new DCA

    Assumes that a LOWER raw metric reading indicates cheaper conditions.
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


def powerlaw_value_score(residual: float, config: Config) -> float:
    return indicator_value_score(
        residual,
        config.cheap_residual,
        config.neutral_residual,
        config.expensive_residual,
    )


def mvrv_value_score(mvrv_z: float) -> float:
    return indicator_value_score(
        mvrv_z,
        cheap_boundary=0.50,
        neutral_boundary=3.00,
        expensive_boundary=5.00,
    )


def ahr999_value_score(ahr999: float) -> float:
    return indicator_value_score(
        ahr999,
        cheap_boundary=0.45,
        neutral_boundary=1.20,
        expensive_boundary=1.80,
    )


def price_realised_value_score(price_realised_ratio: float) -> float:
    return indicator_value_score(
        price_realised_ratio,
        cheap_boundary=0.90,
        neutral_boundary=1.50,
        expensive_boundary=2.00,
    )


def puell_value_score(puell_multiple: float) -> float:
    return indicator_value_score(
        puell_multiple,
        cheap_boundary=0.50,
        neutral_boundary=2.00,
        expensive_boundary=4.00,
    )


def calculate_composite_risk(
    residual: float,
    mvrv_z: float,
    ahr999: float,
    price_realised_ratio: float,
    puell_multiple: float,
    config: Config,
) -> tuple[float, float, dict[str, float]]:
    """
    Returns:
        composite_risk  (0 = low risk / cheap, 1 = high risk / expensive)
        composite_value (inverse of risk)
        component value scores
    """
    scores = {
        "powerlaw": powerlaw_value_score(residual, config),
        "mvrv_z": mvrv_value_score(mvrv_z),
        "ahr999": ahr999_value_score(ahr999),
        "price_realised": price_realised_value_score(
            price_realised_ratio
        ),
        "puell": puell_value_score(puell_multiple),
    }

    composite_value = sum(
        scores[name] * WEIGHTS[name]
        for name in WEIGHTS
    )

    composite_value = clamp(composite_value, 0.0, 1.0)
    composite_risk = 1.0 - composite_value

    return (
        round(composite_risk, 4),
        round(composite_value, 4),
        {name: round(value, 4) for name, value in scores.items()},
    )


# ===================================================================
# Persistence and notifications
# ===================================================================

def load_state() -> dict[str, Any]:
    if not STATE_JSON.exists():
        return {
            "consecutive_qualified_days": 0,
            "last_status": "UNKNOWN",
            "last_date_utc": None,
        }

    try:
        return read_json_file(STATE_JSON)
    except (OSError, ValueError, json.JSONDecodeError):
        return {
            "consecutive_qualified_days": 0,
            "last_status": "UNKNOWN",
            "last_date_utc": None,
        }


def save_state(state: dict[str, Any]) -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)

    with STATE_JSON.open("w", encoding="utf-8") as file:
        json.dump(state, file, indent=2, sort_keys=True)
        file.write("\n")


def append_history(row: dict[str, Any]) -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)

    columns = [
        "date_utc",
        "price_usd",
        "powerlaw_fitted_usd",
        "powerlaw_exponent",
        "powerlaw_residual_log10",
        "pct_from_powerlaw_trend",
        "mvrv_z",
        "ahr999",
        "realised_price_usd",
        "price_realised_ratio",
        "puell_multiple",
        "powerlaw_value_score",
        "mvrv_value_score",
        "ahr999_value_score",
        "price_realised_value_score",
        "puell_value_score",
        "composite_value",
        "composite_risk",
        "entry_price_usd",
        "risk_start_threshold",
        "price_gate_passed",
        "risk_gate_passed",
        "consecutive_qualified_days",
        "confirmation_days",
        "signal",
    ]

    file_exists = HISTORY_CSV.exists()

    with HISTORY_CSV.open("a", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=columns)

        if not file_exists:
            writer.writeheader()

        writer.writerow(
            {column: row.get(column, "") for column in columns}
        )


def send_ntfy(
    config: Config,
    title: str,
    message: str,
    priority: str,
    tags: str,
) -> None:
    """
    If NTFY_TOPIC is absent, prints the notification instead.
    """
    if not config.ntfy_topic:
        print("\nNTFY_TOPIC not set. Notification preview:\n")
        print(title)
        print(message)
        return

    url = f"{config.ntfy_server}/{config.ntfy_topic}"

    headers = {
        "Title": title.encode("ascii", errors="replace").decode("ascii"),
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
    ensure_success(response, "ntfy")


# ===================================================================
# Main execution
# ===================================================================

def main() -> int:
    try:
        config = load_config()
        validate_config(config)

        # BTC current price and power-law position.
        days, prices = fetch_price_history()
        _, exponent, fitted_logs = fit_power_law(days, prices)

        current_price = float(prices[-1])
        fitted_log = float(fitted_logs[-1])
        fitted_price = float(10 ** fitted_log)

        residual = math.log10(current_price) - fitted_log
        pct_from_trend = ((current_price / fitted_price) - 1.0) * 100

        # Live / current on-chain indicator values.
        mvrv_z = fetch_mvrv_zscore(config)
        ahr999 = fetch_ahr999(config)
        puell_multiple = fetch_puell_multiple(config)
        realised_price = fetch_realised_price(config)

        price_realised_ratio = current_price / realised_price

        composite_risk, composite_value, component_scores = (
            calculate_composite_risk(
                residual=residual,
                mvrv_z=mvrv_z,
                ahr999=ahr999,
                price_realised_ratio=price_realised_ratio,
                puell_multiple=puell_multiple,
                config=config,
            )
        )

        price_gate_passed = current_price <= config.entry_price_usd
        risk_gate_passed = (
            composite_risk <= config.risk_start_threshold
        )
        qualified_today = price_gate_passed and risk_gate_passed

        state = load_state()
        previous_status = str(state.get("last_status", "UNKNOWN"))

        if qualified_today:
            consecutive_days = (
                int(state.get("consecutive_qualified_days", 0)) + 1
            )
        else:
            consecutive_days = 0

        confirmed = (
            qualified_today
            and consecutive_days >= config.confirmation_days
        )

        if confirmed:
            signal = "START_DCA"
        elif qualified_today:
            signal = "PENDING_CONFIRMATION"
        elif price_gate_passed:
            signal = "PRICE_OK_RISK_TOO_HIGH"
        elif risk_gate_passed:
            signal = "RISK_OK_PRICE_TOO_HIGH"
        else:
            signal = "WAIT"

        save_state(
            {
                "consecutive_qualified_days": consecutive_days,
                "last_status": signal,
                "last_date_utc": utc_today(),
            }
        )

        append_history(
            {
                "date_utc": utc_today(),
                "price_usd": f"{current_price:.2f}",
                "powerlaw_fitted_usd": f"{fitted_price:.2f}",
                "powerlaw_exponent": f"{exponent:.6f}",
                "powerlaw_residual_log10": f"{residual:.6f}",
                "pct_from_powerlaw_trend": f"{pct_from_trend:.2f}",
                "mvrv_z": f"{mvrv_z:.5f}",
                "ahr999": f"{ahr999:.5f}",
                "realised_price_usd": f"{realised_price:.2f}",
                "price_realised_ratio": f"{price_realised_ratio:.5f}",
                "puell_multiple": f"{puell_multiple:.5f}",
                "powerlaw_value_score": (
                    f"{component_scores['powerlaw']:.4f}"
                ),
                "mvrv_value_score": (
                    f"{component_scores['mvrv_z']:.4f}"
                ),
                "ahr999_value_score": (
                    f"{component_scores['ahr999']:.4f}"
                ),
                "price_realised_value_score": (
                    f"{component_scores['price_realised']:.4f}"
                ),
                "puell_value_score": (
                    f"{component_scores['puell']:.4f}"
                ),
                "composite_value": f"{composite_value:.4f}",
                "composite_risk": f"{composite_risk:.4f}",
                "entry_price_usd": f"{config.entry_price_usd:.2f}",
                "risk_start_threshold": (
                    f"{config.risk_start_threshold:.2f}"
                ),
                "price_gate_passed": price_gate_passed,
                "risk_gate_passed": risk_gate_passed,
                "consecutive_qualified_days": consecutive_days,
                "confirmation_days": config.confirmation_days,
                "signal": signal,
            }
        )

        message = (
            "BTC COMPOSITE DCA RISK PROXY\n"
            "--------------------------------\n"
            f"Date (UTC):              {utc_today()}\n"
            f"BTC price:               {format_usd(current_price)}\n"
            f"Power-law trend:         {format_usd(fitted_price)}\n"
            f"Price vs trend:          {pct_from_trend:+.1f}%\n"
            f"Power-law residual:      {residual:+.4f}\n\n"
            "LIVE INPUTS\n"
            f"MVRV Z-Score:            {mvrv_z:.3f}\n"
            f"AHR999:                  {ahr999:.3f}\n"
            f"Realised price:          {format_usd(realised_price)}\n"
            f"Price / realised:        {price_realised_ratio:.3f}x\n"
            f"Puell Multiple:          {puell_multiple:.3f}\n\n"
            "WEIGHTED VALUE SCORES\n"
            f"Power law (25%):         {component_scores['powerlaw']:.3f}\n"
            f"MVRV Z (25%):            {component_scores['mvrv_z']:.3f}\n"
            f"AHR999 (20%):            {component_scores['ahr999']:.3f}\n"
            f"Price/realised (20%):    "
            f"{component_scores['price_realised']:.3f}\n"
            f"Puell (10%):             {component_scores['puell']:.3f}\n\n"
            f"Composite value:         {composite_value:.3f} / 1.000\n"
            f"Composite proxy risk:    {composite_risk:.3f} / 1.000\n\n"
            "YOUR START CONDITIONS\n"
            f"Price <= {format_usd(config.entry_price_usd)}: "
            f"{'PASS' if price_gate_passed else 'WAIT'}\n"
            f"Risk <= {config.risk_start_threshold:.2f}: "
            f"{'PASS' if risk_gate_passed else 'WAIT'}\n"
            f"Confirmation:            "
            f"{consecutive_days}/{config.confirmation_days} days\n\n"
            f"STATUS: {signal}\n\n"
            "This is a transparent composite proxy, not Benjamin Cowen's "
            "proprietary risk metric. No trades are executed."
        )

        if signal == "START_DCA":
            title = (
                f"BTC DCA START — Risk {composite_risk:.3f}, "
                f"BTC {format_usd(current_price)}"
            )
            priority = "high"
            tags = "bitcoin,moneybag,white_check_mark"

        elif signal == "PENDING_CONFIRMATION":
            title = (
                "BTC DCA conditions met — "
                f"Day {consecutive_days}/{config.confirmation_days}"
            )
            priority = "default"
            tags = "bitcoin,hourglass_flowing_sand"

        elif signal != previous_status:
            title = f"BTC DCA status changed — {signal}"
            priority = "default"
            tags = "bitcoin,bar_chart"

        else:
            title = (
                f"BTC DCA monitor — Risk {composite_risk:.3f} "
                f"({signal})"
            )
            priority = "low"
            tags = "bitcoin,bar_chart"

        print(message)
        send_ntfy(config, title, message, priority, tags)

        return 0

    except Exception as exc:
        error_message = (
            "BTC Composite DCA monitor failed.\n\n"
            f"Error: {type(exc).__name__}: {exc}\n\n"
            "No DCA signal was generated. Check API keys, endpoint paths, "
            "provider plan access, and manual data freshness."
        )

        print(error_message, file=sys.stderr)

        # Best-effort error notification. Do not hide original error.
        try:
            config = load_config()
            send_ntfy(
                config,
                "BTC DCA monitor ERROR",
                error_message,
                priority="high",
                tags="bitcoin,warning",
            )
        except Exception:
            pass

        return 1


if __name__ == "__main__":
    raise SystemExit(main())
