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
    def row(self): return asdict(self)

def _secret(st, *names: str) -> tuple[str, str]:
    for name in names:
        try: value = st.secrets.get(name, "")
        except Exception: value = ""
        value = value or os.getenv(name, "")
        if value: return str(value).strip(), name
    return "", names[0]

def _classify(provider, secret_name, token, call: Callable[[str], requests.Response]):
    if not token: return ProbeResult(provider, secret_name, False, "NOT CONFIGURED")
    try: r = call(token)
    except requests.RequestException as exc: return ProbeResult(provider, secret_name, True, "NETWORK ERROR", detail=type(exc).__name__)
    code=r.status_code; mx=r.headers.get("API-KEY-MAX-LIMIT", ""); used=r.headers.get("API-KEY-USE-LIMIT", "")
    common=dict(http_status=code, rate_limit_max=mx, rate_limit_used=used)
    if code==200: return ProbeResult(provider, secret_name, True, "ACCESSIBLE", detail="Probe succeeded", **common)
    if code in (401,403): return ProbeResult(provider, secret_name, True, "AUTH / PLAN BLOCKED", detail="Key exists but endpoint is not accessible", **common)
    if code==402: return ProbeResult(provider, secret_name, True, "PLAN / CREDIT BLOCKED", detail="Provider reports plan or credit restriction", **common)
    if code==429: return ProbeResult(provider, secret_name, True, "RATE LIMITED", detail="No retry performed", **common)
    return ProbeResult(provider, secret_name, True, "HTTP ERROR", detail="Probe returned a non-success status", **common)

def run_provider_probes(st) -> list[dict]:
    out=[]
    cg,cgn=_secret(st,"COINGLASS_API_KEY")
    out.append(_classify("CoinGlass — Puell Multiple",cgn,cg,lambda key: requests.get("https://open-api-v4.coinglass.com/api/index/puell-multiple",headers={"CG-API-KEY":key,"Accept":"application/json"},timeout=15)))
    cq,cqn=_secret(st,"CRYPTOQUANT_API_KEY")
    out.append(_classify("CryptoQuant — endpoint discovery",cqn,cq,lambda key: requests.get("https://api.cryptoquant.com/v1/discovery/endpoints",headers={"Authorization":f"Bearer {key}","Accept":"application/json"},params={"format":"json"},timeout=15)))
    gecko,gn=_secret(st,"COINGECKO_API","COINGECKO_API_KEY")
    out.append(_classify("CoinGecko — Demo ping",gn,gecko,lambda key: requests.get("https://api.coingecko.com/api/v3/ping",headers={"x-cg-demo-api-key":key,"Accept":"application/json"},timeout=15)))
    kote,kn=_secret(st,"KOTECHARTS_API")
    out.append(ProbeResult("Kotecharts",kn,bool(kote),"CONFIGURED — ENDPOINT NOT PROBED" if kote else "NOT CONFIGURED",detail="No request made until authenticated API contract is verified"))
    return [r.row() for r in out]
