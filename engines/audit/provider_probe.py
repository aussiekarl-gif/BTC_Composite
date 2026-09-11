"""Read-only capability probes for optional BTC data providers.

Never logs or displays secret values. Each probe performs at most one lightweight
request and never writes to Production, Research, or the central data repository.
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
    rate_limit_max: str = ""
    rate_limit_used: str = ""

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
    max_limit = r.headers.get("API-KEY-MAX-LIMIT", "")
    used_limit = r.headers.get("API-KEY-USE-LIMIT", "")
    common = dict(http_status=code, rate_limit_max=max_limit, rate_limit_used=used_limit)
    if code == 200:
        return ProbeResult(provider, secret_name, True, "ACCESSIBLE", detail="Probe succeeded", **common)
    if code in (401, 403):
        return ProbeResult(provider, secret_name, True, "AUTH / PLAN BLOCKED", detail="Key exists but endpoint is not accessible", **common)
    if code == 402:
        return ProbeResult(provider, secret_name, True, "PLAN / CREDIT BLOCKED", detail="Provider reports plan or credit restriction", **common)
    if code == 429:
        return ProbeResult(provider, secret_name, True, "RATE LIMITED", detail="No retry performed", **common)
    return ProbeResult(provider, secret_name, True, "HTTP ERROR", detail="Probe returned a non-success status", **common)


def run_provider_probes(st) -> list[dict]:
    """Run conservative one-request probes. Returns display-safe rows only."""
    out: list[ProbeResult] = []

    # CoinGlass: Puell is a useful real entitlement probe and is documented for
    # every current CoinGlass API plan. Rate-limit headers are retained when sent.
    cg, cg_name = _secret(st, "COINGLASS_API_KEY")
    out.append(_classify(
        "CoinGlass — Puell Multiple", cg_name, cg,
        lambda key: requests.get(
            "https://open-api-v4.coinglass.com/api/index/puell-multiple",
            headers={"CG-API-KEY": key, "Accept": "application/json"}, timeout=15,
        ),
    ))

    # CryptoQuant: use the documented discovery endpoint rather than assuming a
    # specific metric path. A successful call tells us the key is valid and gives
    # the provider's currently supported endpoint catalogue for that API service.
    cq, cq_name = _secret(st, "CRYPTOQUANT_API_KEY")
    out.append(_classify(
        "CryptoQuant — endpoint discovery", cq_name, cq,
        lambda key: requests.get(
            "https://api.cryptoquant.com/v1/discovery/endpoints",
            headers={"Authorization": f"Bearer {key}", "Accept": "application/json"},
            params={"format": "json"}, timeout=15,
        ),
    ))

    # CoinGecko secret may be a Demo or Pro key. Try Demo first without spending a
    # second request; if it is a Pro key the result will simply classify as blocked
    # and we can add plan-specific routing after observing the deployed probe.
    gecko, gecko_name = _secret(st, "COINGECKO_API", "COINGECKO_API_KEY")
    out.append(_classify(
        "CoinGecko — Demo ping", gecko_name, gecko,
        lambda key: requests.get(
            "https://api.coingecko.com/api/v3/ping",
            headers={"x-cg-demo-api-key": key, "Accept": "application/json"}, timeout=15,
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
