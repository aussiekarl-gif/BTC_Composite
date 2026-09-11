"""Research-only BTC provider source-priority matrix.

This module documents preferred acquisition order for audit/research datasets.
It does not fetch data, write caches, or alter Production/Research calculations.
"""
from __future__ import annotations

import pandas as pd

# Prefer local/self-calculated/free sources first; then existing cache; keep BGeometrics
# as the remaining specialist source. Live tests showed the configured CoinGlass key is
# blocked for specialist endpoints (application code 401 / Upgrade plan) and the configured
# CryptoQuant entitlement returns HTTP 403 for targeted BTC on-chain/network indicators.
SOURCE_MATRIX = [
    {"metric":"BTC price", "preferred":"Existing benchmark / CoinGecko", "secondary":"Coin Metrics", "fallback":"BGeometrics", "status":"free-first"},
    {"metric":"Fear & Greed", "preferred":"Existing central src__ BGeometrics history", "secondary":"CoinGlass only if future plan access is verified", "fallback":"BGeometrics", "status":"preserve exact Production-source parity"},
    {"metric":"Puell Multiple", "preferred":"Self-calc from Coin Metrics issuance + price", "secondary":"Existing cache", "fallback":"BGeometrics", "status":"free-first; CryptoQuant current entitlement 403 on Puell endpoint"},
    {"metric":"2Y MA Multiplier", "preferred":"Self-calc from benchmark price", "secondary":"Existing cache", "fallback":"BGeometrics", "status":"free-first"},
    {"metric":"200W MA", "preferred":"Self-calc from benchmark price", "secondary":"Existing cache", "fallback":"BGeometrics", "status":"free-first"},
    {"metric":"NUPL", "preferred":"Self-calc from Coin Metrics market/realized cap", "secondary":"Existing cache", "fallback":"BGeometrics", "status":"free-first; CryptoQuant current entitlement 403 on NUPL endpoint"},
    {"metric":"NVT", "preferred":"Self-calc from Coin Metrics inputs", "secondary":"Existing cache", "fallback":"BGeometrics", "status":"free-first; CryptoQuant current entitlement 403 on NVT endpoint"},
    {"metric":"STH SOPR", "preferred":"Existing cache", "secondary":"BGeometrics", "fallback":"Future paid provider entitlement", "status":"CoinGlass blocked; CryptoQuant on-chain current entitlement blocked"},
    {"metric":"LTH SOPR", "preferred":"Existing cache", "secondary":"BGeometrics", "fallback":"Future paid provider entitlement", "status":"CoinGlass blocked; CryptoQuant on-chain current entitlement blocked"},
    {"metric":"STH Realized Price", "preferred":"Existing cache", "secondary":"BGeometrics", "fallback":"Future paid provider entitlement", "status":"CoinGlass blocked; CryptoQuant on-chain current entitlement blocked"},
    {"metric":"LTH Realized Price", "preferred":"Existing cache", "secondary":"BGeometrics", "fallback":"Future paid provider entitlement", "status":"CoinGlass blocked; CryptoQuant on-chain current entitlement blocked"},
    {"metric":"RHODL Ratio", "preferred":"Existing cache", "secondary":"BGeometrics", "fallback":"Future paid provider entitlement", "status":"CoinGlass blocked; do not spend more CryptoQuant on-chain probes on current entitlement"},
    {"metric":"STH Supply", "preferred":"Existing cache", "secondary":"BGeometrics", "fallback":"Future paid provider entitlement", "status":"CoinGlass blocked; CryptoQuant on-chain current entitlement blocked"},
    {"metric":"LTH Supply", "preferred":"Existing cache", "secondary":"BGeometrics", "fallback":"Future paid provider entitlement", "status":"CoinGlass blocked; CryptoQuant on-chain current entitlement blocked"},
    {"metric":"Reserve Risk", "preferred":"Existing cache", "secondary":"BGeometrics", "fallback":"Future paid provider entitlement", "status":"CoinGlass blocked; CryptoQuant on-chain current entitlement blocked"},
    {"metric":"MVRV / MVRV Z", "preferred":"Coin Metrics/self-calc where exact inputs allow", "secondary":"Existing cache", "fallback":"BGeometrics exact Production source", "status":"CryptoQuant MVRV endpoint 403; do not replace Production source without parity"},
    {"metric":"aSOPR / SOPR variants", "preferred":"Existing cache", "secondary":"BGeometrics", "fallback":"Future paid provider entitlement", "status":"specialist; current alternate on-chain plans unavailable"},
    {"metric":"VDD / CDD / Liveliness / Dormancy", "preferred":"Coin Metrics where available", "secondary":"Existing BGeometrics cache", "fallback":"BGeometrics", "status":"CryptoQuant CDD/dormancy endpoints 403 on current entitlement"},
]

CQ_KEYWORDS = (
    "mvrv", "sopr", "nupl", "puell", "realized", "rhodl", "reserve-risk",
    "reserve", "supply", "cdd", "dormancy", "liveliness", "nvt", "profit", "loss",
)


def source_matrix_df() -> pd.DataFrame:
    return pd.DataFrame(SOURCE_MATRIX)


def relevant_cryptoquant_paths(paths: list[str]) -> pd.DataFrame:
    rows=[]
    for path in paths or []:
        low=path.lower()
        hits=[k for k in CQ_KEYWORDS if k in low]
        if hits:
            rows.append({"btc_endpoint_path":path,"matched_topics":", ".join(sorted(set(hits)))})
    return pd.DataFrame(rows)
