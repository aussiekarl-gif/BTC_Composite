"""Fetch Firsthand's documented public JSON endpoints without assuming slugs.

Raw payloads are retained for inspection. Nothing is normalised or integrated.
"""
from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urljoin

import requests

BASE = "https://firsthandbitcoin.com"
API = f"{BASE}/data/api"
KEYWORDS = ("bitcoin price", "network hashrate", "hashrate", "difficulty",
            "fees", "realised price", "realized price", "mvrv", "200-week",
            "200 week", "transactions per day", "miner revenue")


def describe(value):
    if isinstance(value, list):
        return {"type": "list", "length": len(value), "sample": value[:2]}
    if isinstance(value, dict):
        keys = list(value)
        return {"type": "object", "keys": keys[:40],
                "sample": {k: value[k] for k in keys[:4]}}
    return {"type": type(value).__name__, "sample": value}


def discover_json_links(value, path="$"):
    """Walk the published catalogue and collect its explicit JSON links."""
    found = []
    if isinstance(value, dict):
        label = " ".join(str(value.get(k, "")) for k in
                         ("name", "title", "label", "description", "unit"))
        for key, item in value.items():
            if isinstance(item, str) and key.lower() in {
                "json", "json_url", "jsonurl", "url_json"
            }:
                found.append((label or path, urljoin(BASE, item)))
            elif isinstance(item, (dict, list)):
                found.extend(discover_json_links(item, f"{path}.{key}"))
    elif isinstance(value, list):
        for index, item in enumerate(value):
            found.extend(discover_json_links(item, f"{path}[{index}]"))
    return found


def fetch_candidate_series(*, session=None, output_dir="artifacts/firsthand"):
    client = session or requests.Session()
    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)
    report = {
        "provider": "Firsthand Bitcoin",
        "catalogue_url": f"{API}/series.json",
        "retrieved_at_utc": datetime.now(timezone.utc).isoformat(),
        "license_claim": "Free to reuse with attribution/link to firsthandbitcoin.com/data",
        "series": {},
    }

    catalogue_response = client.get(f"{API}/series.json", timeout=30)
    catalogue_response.raise_for_status()
    catalogue = catalogue_response.json()
    if not catalogue:
        raise ValueError("Firsthand series catalogue is empty")
    (output / "catalogue.json").write_text(
        json.dumps(catalogue, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    report["catalogue"] = describe(catalogue)

    summary_response = client.get(f"{API}/summary.json", timeout=30)
    summary_response.raise_for_status()
    summary = summary_response.json()
    if not summary:
        raise ValueError("Firsthand summary endpoint is empty")
    (output / "summary.json").write_text(
        json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    report["summary"] = describe(summary)

    links = discover_json_links(catalogue)
    selected = [(label, url) for label, url in links
                if any(word in label.lower() for word in KEYWORDS)]
    # Keep every discovered candidate distinct; avoid silently guessing endpoint slugs.
    if not selected:
        raise ValueError("No candidate JSON links discovered in published series catalogue")
    seen = set()
    for index, (label, url) in enumerate(selected, start=1):
        if url in seen:
            continue
        seen.add(url)
        response = client.get(url, timeout=30)
        response.raise_for_status()
        payload = response.json()
        if payload is None or payload == {} or payload == []:
            raise ValueError(f"Firsthand endpoint returned empty payload: {url}")
        filename = f"candidate_{index:02d}.json"
        (output / filename).write_text(
            json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )
        report["series"][filename] = {
            "label": label, "url": url, **describe(payload)
        }

    (output / "diagnostic_metadata.json").write_text(
        json.dumps(report, indent=2, default=str) + "\n", encoding="utf-8"
    )
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", default="artifacts/firsthand")
    args = parser.parse_args()
    print(json.dumps(fetch_candidate_series(output_dir=args.output_dir),
                     indent=2, default=str))


if __name__ == "__main__":
    main()
