"""Read-only capability and entitlement probes for optional BTC data providers.

Never logs or displays secret values. Capability probe makes at most one lightweight
request per enabled provider. Entitlement probe is explicit and read-only; it samples
selected datasets without writing Production, Research, or the central data repository.
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

def _safe_text(value, limit=160):
    text = str(value or "").replace("\n", " ").replace("\r", " ").strip()
    return text[:limit]

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
    return ProbeResult(provider, secret_name, True, "HTTP ERROR", code, "Probe returned a non-success status", mx, used)

def _classify_coinglass(provider, secret_name, token, call: Callable[[str], requests.Response]):
    if not token: return ProbeResult(provider, secret_name, False, "NOT CONFIGURED")
    try: r = call(token)
    except requests.RequestException as exc: return ProbeResult(provider, secret_name, True, "NETWORK ERROR", detail=type(exc).__name__)
    mx=r.headers.get("API-KEY-MAX-LIMIT", ""); used=r.headers.get("API-KEY-USE-LIMIT", ""); common=dict(http_status=r.status_code, rate_limit_max=mx, rate_limit_used=used)
    if r.status_code == 429: return ProbeResult(provider, secret_name, True, "RATE LIMITED", detail="No retry performed", **common)
    if r.status_code != 200:
        if r.status_code in (401,403): return ProbeResult(provider, secret_name, True, "AUTH / PLAN BLOCKED", detail="HTTP access blocked", **common)
        return ProbeResult(provider, secret_name, True, "HTTP ERROR", detail=f"HTTP {r.status_code}", **common)
    try: payload = r.json()
    except ValueError: return ProbeResult(provider, secret_name, True, "INVALID JSON", detail="HTTP 200 but response was not JSON", **common)
    if isinstance(payload, dict) and "code" in payload:
        api_code=payload.get("code"); msg=_safe_text(payload.get("msg")); success_codes={0,"0",200,"200"}
        if api_code not in success_codes: return ProbeResult(provider, secret_name, True, "API / PLAN BLOCKED", detail=f"CoinGlass code {api_code}: {msg}" if msg else f"CoinGlass code {api_code}", **common)
        if "data" not in payload: return ProbeResult(provider, secret_name, True, "API RESPONSE EMPTY", detail=f"CoinGlass code {api_code}: {msg}" if msg else f"CoinGlass code {api_code}; no data field", **common)
    return ProbeResult(provider, secret_name, True, "ACCESSIBLE", detail="HTTP and CoinGlass application response succeeded", **common)

def run_provider_probes(st) -> list[dict]:
    out=[]
    cg,cgn=_secret(st,"COINGLASS_API_KEY"); out.append(_classify_coinglass("CoinGlass — Puell Multiple",cgn,cg,lambda key: requests.get("https://open-api-v4.coinglass.com/api/index/puell-multiple",headers={"CG-API-KEY":key,"Accept":"application/json"},timeout=15)))
    cq,cqn=_secret(st,"CRYPTOQUANT_API_KEY"); out.append(_classify("CryptoQuant — endpoint discovery",cqn,cq,lambda key: requests.get("https://api.cryptoquant.com/v1/discovery/endpoints",headers={"Authorization":f"Bearer {key}","Accept":"application/json"},params={"format":"json"},timeout=15)))
    gecko,gn=_secret(st,"COINGECKO_API","COINGECKO_API_KEY"); out.append(_classify("CoinGecko — Demo ping",gn,gecko,lambda key: requests.get("https://api.coingecko.com/api/v3/ping",headers={"x-cg-demo-api-key":key,"Accept":"application/json"},timeout=15)))
    kote,kn=_secret(st,"KOTECHARTS_API"); out.append(ProbeResult("Kotecharts",kn,bool(kote),"CONFIGURED — ENDPOINT NOT PROBED" if kote else "NOT CONFIGURED",detail="No request made until authenticated API contract is verified"))
    return [r.row() for r in out]

COINGLASS_DATASETS=[("Puell Multiple","/api/index/puell-multiple"),("Fear & Greed","/api/index/fear-greed-history"),("2Y MA Multiplier","/api/index/2-year-ma-multiplier"),("200W MA","/api/index/200-week-moving-average-heatmap"),("STH SOPR","/api/index/bitcoin-sth-sopr"),("LTH SOPR","/api/index/bitcoin-lth-sopr"),("STH Realized Price","/api/index/bitcoin-sth-realized-price"),("LTH Realized Price","/api/index/bitcoin-lth-realized-price"),("RHODL Ratio","/api/index/bitcoin-rhodl-ratio"),("STH Supply","/api/index/bitcoin-short-term-holder-supply"),("LTH Supply","/api/index/bitcoin-long-term-holder-supply"),("Reserve Risk","/api/index/bitcoin-reserve-risk"),("NUPL","/api/index/bitcoin-net-unrealized-profit-loss")]

def run_coinglass_entitlement_probe(st) -> list[dict]:
    token,secret_name=_secret(st,"COINGLASS_API_KEY"); out=[]
    for label,path in COINGLASS_DATASETS:
        result=_classify_coinglass(f"CoinGlass — {label}",secret_name,token,lambda key,p=path: requests.get("https://open-api-v4.coinglass.com"+p,headers={"CG-API-KEY":key,"Accept":"application/json"},timeout=20)); out.append(result.row())
        if result.status=="RATE LIMITED": break
    return out

def run_cryptoquant_catalogue_probe(st) -> dict:
    token,secret_name=_secret(st,"CRYPTOQUANT_API_KEY")
    if not token: return {"configured":False,"status":"NOT CONFIGURED","secret_name":secret_name,"endpoint_count":0,"btc_endpoint_count":0,"btc_paths":[]}
    try: r=requests.get("https://api.cryptoquant.com/v1/discovery/endpoints",headers={"Authorization":f"Bearer {token}","Accept":"application/json"},params={"format":"json"},timeout=20)
    except requests.RequestException as exc: return {"configured":True,"status":"NETWORK ERROR","secret_name":secret_name,"endpoint_count":0,"btc_endpoint_count":0,"btc_paths":[],"detail":type(exc).__name__}
    if r.status_code!=200: return {"configured":True,"status":f"HTTP {r.status_code}","secret_name":secret_name,"endpoint_count":0,"btc_endpoint_count":0,"btc_paths":[]}
    try: payload=r.json()
    except ValueError: return {"configured":True,"status":"INVALID JSON","secret_name":secret_name,"endpoint_count":0,"btc_endpoint_count":0,"btc_paths":[]}
    data=((payload.get("result") or {}).get("data") or []) if isinstance(payload,dict) else []; paths=[str(x.get("path","")) for x in data if isinstance(x,dict) and x.get("path")]; btc=[p for p in paths if "/btc/" in p]
    return {"configured":True,"status":"ACCESSIBLE","secret_name":secret_name,"endpoint_count":len(paths),"btc_endpoint_count":len(btc),"btc_paths":btc}

def run_cryptoquant_targeted_entitlement_probe(st, paths: list[str]) -> list[dict]:
    """Probe only catalogue-confirmed BTC audit endpoints, one minimal daily observation each."""
    token,secret_name=_secret(st,"CRYPTOQUANT_API_KEY")
    if not token: return [{"path":"","configured":False,"status":"NOT CONFIGURED","http_status":None,"detail":""}]
    relevant=[]
    keywords=("mvrv","sopr","nupl","puell","realized","rhodl","reserve-risk","cdd","dormancy","liveliness","nvt")
    for path in paths or []:
        low=path.lower()
        if any(k in low for k in keywords): relevant.append(path)
    # Bound credit usage: at most 12 catalogue-confirmed endpoints, one tiny request each.
    relevant=relevant[:12]
    out=[]
    for path in relevant:
        try:
            r=requests.get("https://api.cryptoquant.com"+path,headers={"Authorization":f"Bearer {token}","Accept":"application/json"},params={"window":"day","limit":1},timeout=20)
        except requests.RequestException as exc:
            out.append({"path":path,"configured":True,"status":"NETWORK ERROR","http_status":None,"detail":type(exc).__name__}); continue
        if r.status_code==200: status="ACCESSIBLE"; detail="Minimal data request succeeded"
        elif r.status_code==429: status="RATE LIMITED"; detail="Stopped; no retry"
        elif r.status_code in (401,403): status="AUTH / PLAN BLOCKED"; detail="Endpoint unavailable on current entitlement"
        elif r.status_code==402: status="PLAN / CREDIT BLOCKED"; detail="Provider reports plan/credit restriction"
        else: status="HTTP ERROR"; detail=f"HTTP {r.status_code}"
        out.append({"path":path,"configured":True,"status":status,"http_status":r.status_code,"detail":detail})
        if r.status_code==429: break
    if not relevant: out.append({"path":"","configured":True,"status":"NO MATCHING CATALOGUE PATHS","http_status":None,"detail":"No targeted audit endpoints found in discovery catalogue"})
    return out
