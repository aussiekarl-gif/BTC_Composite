"""Diagnostic fetch for Firsthand Bitcoin public API candidate series.

Preserves raw provider payloads; does not normalise or merge them into project data.
"""
from __future__ import annotations
import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
import requests

BASE = "https://firsthandbitcoin.com/data/api"
SERIES = ("realized", "hashrate", "fees", "difficulty", "mvrv", "btc")

def describe(value):
    if isinstance(value, list):
        return {"type": "list", "length": len(value), "sample": value[:2]}
    if isinstance(value, dict):
        keys = list(value)
        return {"type": "object", "keys": keys[:30],
                "sample": {k: value[k] for k in keys[:3]}}
    return {"type": type(value).__name__, "sample": value}

def fetch_candidate_series(*, session=None, output_dir="artifacts/firsthand"):
    client = session or requests.Session()
    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)
    report = {
        "provider": "Firsthand Bitcoin",
        "catalogue_url": f"{BASE}/series.json",
        "retrieved_at_utc": datetime.now(timezone.utc).isoformat(),
        "license_claim": "Free to use with attribution; link firsthandbitcoin.com/data",
        "series": {},
    }
    urls = {"catalogue": f"{BASE}/series.json", "summary": f"{BASE}/summary.json"}
    urls.update({key: f"{BASE}/series/{key}.json" for key in SERIES})
    for key, url in urls.items():
        response = client.get(url, timeout=30)
        response.raise_for_status()
        payload = response.json()
        if payload is None or payload == {} or payload == []:
            raise ValueError(f"Firsthand endpoint returned an empty payload: {key}")
        (output / f"{key}.json").write_text(
            json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )
        report["series"][key] = {"url": url, **describe(payload)}
    (output / "diagnostic_metadata.json").write_text(
        json.dumps(report, indent=2, default=str) + "\n", encoding="utf-8"
    )
    return report

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", default="artifacts/firsthand")
    args = parser.parse_args()
    print(json.dumps(fetch_candidate_series(output_dir=args.output_dir), indent=2, default=str))

if __name__ == "__main__":
    main()
