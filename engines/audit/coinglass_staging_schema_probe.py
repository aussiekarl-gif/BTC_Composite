"""Safe structural helpers for CoinGlass staging responses.

Research-only. Never returns or logs secret values. Used to locate documented
metric rows even if CoinGlass adds wrapper objects around the data array.
"""
from __future__ import annotations
from typing import Any


def find_metric_records(payload: Any, value_keys: tuple[str, ...]) -> tuple[list[dict], str]:
    best: list[dict] = []
    best_path = ""

    def walk(obj: Any, path: str) -> None:
        nonlocal best, best_path
        if isinstance(obj, list):
            dicts = [x for x in obj if isinstance(x, dict)]
            if dicts:
                hits = [x for x in dicts if any(k in x for k in value_keys)]
                if len(hits) > len(best):
                    best = dicts
                    best_path = path
            for i, child in enumerate(obj[:5]):
                if isinstance(child, (dict, list)):
                    walk(child, f"{path}[{i}]")
        elif isinstance(obj, dict):
            for key, child in obj.items():
                if isinstance(child, (dict, list)):
                    walk(child, f"{path}.{key}" if path else str(key))

    walk(payload, "")
    return best, best_path


def safe_shape_summary(payload: Any) -> str:
    if isinstance(payload, dict):
        keys = sorted(str(k) for k in payload.keys())[:20]
        return "top-level keys: " + ", ".join(keys)
    if isinstance(payload, list):
        return f"top-level list length: {len(payload)}"
    return f"top-level type: {type(payload).__name__}"
