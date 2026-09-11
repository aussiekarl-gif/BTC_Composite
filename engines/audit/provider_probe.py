"""Read-only capability probes for optional BTC data providers.

Never logs or displays secret values. A probe performs at most one lightweight
request per provider/endpoint and never writes to Production data.
"""
from __future__ import annotations

import os
from dataclasses import dataclass, asdict
from typing import Callable

import requests


@dataclass
class ProbeResult:
    provider: str
    secret_name: str
    configured: bool
    status: str
    http_status: int | None = None
    detail: str = ""

    def row(self):
        return asdict(self)


def _secret(st, *names: str) -> tuple[str, str]:
    for name in names:
        try:
            value = st.secrets.get(name, "")
        except Exception:
            value = ""
        value = value or os.getenv(name, "")
        if value:
            return str(value).strip(), name
    return "", names[0]


def _classify(provider: str, secret_name: str, token: str, call: Callable[[str], requests.Response]) -> ProbeResult:
    if not token:
        return ProbeResult(provider, secret_name, False, "NOT CONFIGURED")
    try:
        r = call(token)
    except requests.RequestException as exc:
        return ProbeResult(provider, secret_name, True, "NETWORK ERROR", detail=type(exc).__name__)

    code = r.status_code
    if code == 200:
        return ProbeResult(provider, secret_name, True, "ACCESSIBLE", code, "Probe succeeded")
    if code in (401, 403):
        return ProbeResult(provider, secret_name, True, "AUTH / PLAN BLOCKED", code, "Key exists but endpoint is not accessible")
    if code == 402:
        return ProbeResult(provider, secret_name, True, "PLAN / CREDIT BLOCKED", code, "Provider reports plan or credit restriction")
    if code == 429:
        return ProbeResult(provider, secret_name, True, "RATE LIMITED", code, "No retry performed")
    return ProbeResult(provider, secret_name, True, "HTTP ERROR", code, "Probe returned a non-success status")


def run_provider_probes(st) -> list[dict]:
    """Run conservative one-request probes. Returns display-safe rows only."""
    out: list[ProbeResult] = []

    cg, cg_name = _secret(st, "COINGLASS_API_KEY")
    out.append(_classify(
        "CoinGlass — Puell Multiple", cg_name, cg,
        lambda key: requests.get(
            "https://open-api-v4.coinglass.com/api/index/puell-multiple",
            headers={"CG-API-KEY": key, "Accept": "application/json"}, timeout=15,
        ),
    ))

    cq, cq_name = _secret(st, "CRYPTOQUANT_API_KEY")
    out.append(_classify(
        "CryptoQuant — BTC OHLCV", cq_name, cq,
        lambda key: requests.get(
            "https://api.cryptoquant.com/v1/btc/market-data/price-ohlcv",
            headers={"Authorization": f"Bearer {key}", "Accept": "application/json"},
            params={"window": "day", "limit": 1}, timeout=15,
        ),
    ))

    gecko, gecko_name = _secret(st, "COINGECKO_API", "COINGECKO_API_KEY")
    out.append(_classify(
        "CoinGecko — BTC market data", gecko_name, gecko,
        lambda key: requests.get(
            "https://api.coingecko.com/api/v3/coins/bitcoin",
            headers={"x-cg-demo-api-key": key, "Accept": "application/json"},
            params={"localization": "false", "tickers": "false", "market_data": "true", "community_data": "false", "developer_data": "false", "sparkline": "false"},
            timeout=15,
        ),
    ))

    # Kotecharts is deliberately presence-only until its authenticated endpoint
    # contract is verified. Do not burn a request against a guessed endpoint.
    kote, kote_name = _secret(st, "KOTECHARTS_API")
    out.append(ProbeResult(
        "Kotecharts", kote_name, bool(kote),
        "CONFIGURED — ENDPOINT NOT PROBED" if kote else "NOT CONFIGURED",
        detail="No request made until authenticated API contract is verified",
    ))

    return [r.row() for r in out]
