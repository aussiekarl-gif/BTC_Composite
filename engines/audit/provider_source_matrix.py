"""Research-only BTC provider source-priority matrix.

This module documents preferred acquisition order for audit/research datasets.
It does not fetch data, write caches, or alter Production/Research calculations.
"""
from __future__ import annotations

import pandas as pd

# Prefer local/self-calculated/free sources first; then verified alternate providers;
# keep BGeometrics as specialist/fallback rather than the default bulk source.
SOURCE_MATRIX = [
    {"metric":"BTC price", "preferred":"Existing benchmark / CoinGecko", "secondary":"Coin Metrics", "fallback":"BGeometrics", "status":"free-first"},
    {"metric":"Fear & Greed", "preferred":"CoinGlass", "secondary":"Existing central src__ BGeometrics history", "fallback":"BGeometrics", "status":"CoinGlass entitlement verified"},
    {"metric":"Puell Multiple", "preferred":"Self-calc from Coin Metrics issuance + price", "secondary":"CoinGlass", "fallback":"BGeometrics", "status":"free-first; CoinGlass verified"},
    {"metric":"2Y MA Multiplier", "preferred":"Self-calc from benchmark price", "secondary":"CoinGlass", "fallback":"BGeometrics", "status":"free-first; CoinGlass verified"},
    {"metric":"200W MA", "preferred":"Self-calc from benchmark price", "secondary":"CoinGlass", "fallback":"BGeometrics", "status":"free-first; CoinGlass verified"},
    {"metric":"NUPL", "preferred":"Self-calc from Coin Metrics market/realized cap", "secondary":"CoinGlass", "fallback":"CryptoQuant / BGeometrics", "status":"free-first; CoinGlass verified"},
    {"metric":"STH SOPR", "preferred":"CoinGlass", "secondary":"CryptoQuant if entitlement permits", "fallback":"BGeometrics", "status":"CoinGlass entitlement verified"},
    {"metric":"LTH SOPR", "preferred":"CoinGlass", "secondary":"CryptoQuant if entitlement permits", "fallback":"BGeometrics", "status":"CoinGlass entitlement verified"},
    {"metric":"STH Realized Price", "preferred":"CoinGlass", "secondary":"CryptoQuant if entitlement permits", "fallback":"BGeometrics", "status":"CoinGlass entitlement verified"},
    {"metric":"LTH Realized Price", "preferred":"CoinGlass", "secondary":"CryptoQuant if entitlement permits", "fallback":"BGeometrics", "status":"CoinGlass entitlement verified"},
    {"metric":"RHODL Ratio", "preferred":"CoinGlass", "secondary":"CryptoQuant if catalogue/plan supports", "fallback":"BGeometrics", "status":"CoinGlass entitlement verified"},
    {"metric":"STH Supply", "preferred":"CoinGlass", "secondary":"CryptoQuant if entitlement permits", "fallback":"BGeometrics", "status":"CoinGlass entitlement verified"},
    {"metric":"LTH Supply", "preferred":"CoinGlass", "secondary":"CryptoQuant if entitlement permits", "fallback":"BGeometrics", "status":"CoinGlass entitlement verified"},
    {"metric":"Reserve Risk", "preferred":"CoinGlass", "secondary":"CryptoQuant if entitlement permits", "fallback":"BGeometrics", "status":"CoinGlass entitlement verified"},
    {"metric":"MVRV / MVRV Z", "preferred":"Coin Metrics/self-calc where exact inputs allow", "secondary":"CryptoQuant if entitlement permits", "fallback":"BGeometrics exact Production source", "status":"do not replace Production source without parity"},
    {"metric":"aSOPR / SOPR variants", "preferred":"CryptoQuant if entitlement permits", "secondary":"CoinGlass where equivalent exists", "fallback":"BGeometrics", "status":"specialist"},
    {"metric":"VDD / CDD / Liveliness / Dormancy", "preferred":"Coin Metrics or CryptoQuant where available", "secondary":"BGeometrics cached history", "fallback":"BGeometrics", "status":"specialist"},
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
