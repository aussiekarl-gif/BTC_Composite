#!/usr/bin/env python3
"""Low-volume, metadata-only discovery of Bitview daily Bitcoin network series."""
import json
import urllib.error
import urllib.parse
import urllib.request

BASE = "https://bitview.space"
ATTRIBUTION = "Bitview (bitview.space), data license CC BY 4.0"


def get_json(path, timeout=45):
    req = urllib.request.Request(
        BASE + path,
        headers={"User-Agent": "BTC_Composite-research/1.0", "Accept": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=timeout) as response:
        return json.loads(response.read().decode("utf-8"))


def main():
    health = get_json("/health")
    counts = get_json("/api/series/count")
    indexes = get_json("/api/series/indexes")
    queries = ("transactions", "transaction fees", "miner revenue", "hashrate")
    discovery = {}
    chosen = []
    for q in queries:
        results = get_json("/api/series/search?q=" + urllib.parse.quote(q) + "&limit=8")
        names = results if isinstance(results, list) else results.get("series", results.get("results", []))
        normalized = [str(x.get("name") if isinstance(x, dict) else x) for x in names]
        discovery[q] = normalized
        for name in normalized[:2]:
            if name and name not in chosen:
                chosen.append(name)
    metadata = {}
    for name in chosen:
        path = "/api/series/" + urllib.parse.quote(name, safe="")
        metadata[name] = get_json(path)
    report = {
        "attribution": ATTRIBUTION,
        "service_health": health,
        "series_counts": counts,
        "available_indexes": indexes,
        "search_results": discovery,
        "candidate_metadata": metadata,
        "note": "Discovery only. No historical series values were downloaded or retained.",
    }
    print(json.dumps(report, indent=2, sort_keys=True))
    # Guardrails: fail if search or metadata endpoints are unavailable/empty.
    if not discovery or not chosen or not metadata:
        raise SystemExit("Bitview series discovery returned no usable candidates")

if __name__ == "__main__":
    main()
