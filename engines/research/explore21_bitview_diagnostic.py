"""Research-only raw-data diagnostic for Explore21 and Bitview public BTC data."""
from __future__ import annotations
import hashlib, json, os, time
from datetime import datetime, timezone
from pathlib import Path
import requests

OUT = Path(os.getenv("OUTPUT_DIR", "artifacts/source-diagnostic"))
TIMEOUT = 45
E21 = {
    "bitcoin-mvrv-ratio": "https://charts.explore21.com/data/bitcoin-mvrv-ratio.csv",
    "bitcoin-puell-multiple": "https://charts.explore21.com/data/bitcoin-puell-multiple.csv",
    "bitcoin-mvrv-z-score": "https://charts.explore21.com/data/bitcoin-mvrv-z-score.csv",
    "bitcoin-realized-price": "https://charts.explore21.com/data/bitcoin-realized-price.csv",
    "bitcoin-percent-supply-in-profit": "https://charts.explore21.com/data/bitcoin-percent-supply-in-profit.csv",
    "bitcoin-hashrate": "https://charts.explore21.com/data/bitcoin-hashrate.csv",
}
BITVIEW = "https://bitview.space/api"
SEARCHES = ["realized price", "hashrate", "mvrv", "supply in profit"]
session = requests.Session()
session.headers.update({"User-Agent": "BTC-Composite-research-diagnostic/1.0"})

def save_bytes(path: Path, content: bytes):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(content)
    return hashlib.sha256(content).hexdigest()

def fetch(url, path, accept=None):
    headers = {"Accept": accept} if accept else {}
    try:
        response = session.get(url, headers=headers, timeout=TIMEOUT)
        meta = {"url": url, "status": response.status_code, "content_type": response.headers.get("Content-Type"),
                "retrieved_at_utc": datetime.now(timezone.utc).isoformat(), "bytes": len(response.content)}
        if response.ok:
            meta["sha256"] = save_bytes(path, response.content)
        else:
            meta["body_excerpt"] = response.text[:800]
        return meta, response
    except Exception as exc:
        return {"url": url, "error": f"{type(exc).__name__}: {exc}", "retrieved_at_utc": datetime.now(timezone.utc).isoformat()}, None

def main():
    OUT.mkdir(parents=True, exist_ok=True)
    report = {"started_utc": datetime.now(timezone.utc).isoformat(), "explore21": {}, "bitview": {"search": {}, "series": {}}}
    # Preserve CSV snapshots as raw provider files; no transformations/merging.
    for metric, url in E21.items():
        meta, response = fetch(url, OUT / "explore21" / f"{metric}.csv", "text/csv")
        if response is not None and response.ok:
            meta["csv_header"] = response.text.splitlines()[0][:1200] if response.text else ""
            meta["row_count_including_header"] = len(response.text.splitlines())
        report["explore21"][metric] = meta
        time.sleep(0.2)
    # Discover rather than assume series IDs; save exact raw responses.
    discovered = set()
    for q in SEARCHES:
        url = f"{BITVIEW}/series/search"
        meta, response = fetch(url + "?q=" + requests.utils.quote(q), OUT / "bitview" / f"search_{q.replace(' ', '_')}.json", "application/json")
        report["bitview"]["search"][q] = meta
        if response is not None and response.ok:
            try:
                ids = response.json()
                if isinstance(ids, list):
                    discovered.update(str(x) for x in ids)
            except ValueError:
                meta["parse_error"] = "response was not JSON"
    # Use priority global metrics rather than alphabetically selecting cohort variants.
    # Keep only IDs that were actually returned by one of the searches.
    priority = ["realized_price", "mvrv", "hashrate", "supply_in_profit", "supply_in_profit_share", "nupl"]
    candidates = [series_id for series_id in priority if series_id in discovered]
    report["bitview"]["selected_candidates"] = candidates
    for series_id in candidates:
        safe = series_id.replace("/", "_")
        info_url = f"{BITVIEW}/series/{requests.utils.quote(series_id, safe='')}"
        info_meta, info_response = fetch(info_url, OUT / "bitview" / "series_info" / f"{safe}.json", "application/json")
        series_record = {"info": info_meta, "data_attempts": [], "metadata_summary": None, "daily_data_summary": None}
        if info_response is not None and info_response.ok:
            try:
                info_json = info_response.json()
                series_record["metadata_summary"] = {
                    "unit": info_json.get("unit"), "type": info_json.get("type"),
                    "indexes": info_json.get("indexes"), "nullable": info_json.get("nullable"),
                    "description": info_json.get("description"),
                }
            except ValueError:
                info_meta["parse_error"] = "series info response was not JSON"
        # API documents the index-specific series endpoint; daily index is the initial candidate.
        data_url = f"{BITVIEW}/series/{requests.utils.quote(series_id, safe='')}/day1"
        data_meta, data_response = fetch(data_url, OUT / "bitview" / "series_data" / f"{safe}_day1.json", "application/json")
        series_record["data_attempts"].append(data_meta)
        if data_response is not None and data_response.ok:
            try:
                payload = data_response.json()
                values = payload.get("data", []) if isinstance(payload, dict) else []
                non_null = [x for x in values if x is not None]
                series_record["daily_data_summary"] = {
                    "index": payload.get("index"), "start": payload.get("start"), "end": payload.get("end"),
                    "total_slots": len(values), "null_count": len(values) - len(non_null),
                    "non_null_count": len(non_null), "min": min(non_null) if non_null else None,
                    "max": max(non_null) if non_null else None,
                    "repeated_adjacent_values": sum(1 for a, b in zip(values, values[1:]) if a is not None and a == b),
                    "version": payload.get("version"),
                }
            except (ValueError, TypeError):
                data_meta["parse_error"] = "daily data response schema could not be summarized"
        if data_response is not None and not data_response.ok:
            fallback_url = data_url + "/data"
            fallback_meta, _ = fetch(fallback_url, OUT / "bitview" / "series_data" / f"{safe}_day1_data.json", "application/json")
            series_record["data_attempts"].append(fallback_meta)
        # Probe date-addressed range semantics for key daily series. These results
        # help verify the mapping between day1 array offsets and calendar dates.
        if series_id in ("mvrv", "realized_price"):
            date_url = data_url + "?start=2020-01-01&end=2020-01-04"
            date_meta, date_response = fetch(date_url, OUT / "bitview" / "date_range" / f"{safe}_2020-01.json", "application/json")
            series_record["date_range_probe"] = date_meta
            if date_response is not None and date_response.ok:
                try:
                    date_payload = date_response.json()
                    series_record["date_range_probe_summary"] = {
                        "payload_keys": list(date_payload.keys()) if isinstance(date_payload, dict) else None,
                        "start": date_payload.get("start") if isinstance(date_payload, dict) else None,
                        "end": date_payload.get("end") if isinstance(date_payload, dict) else None,
                        "index": date_payload.get("index") if isinstance(date_payload, dict) else None,
                        "data": date_payload.get("data") if isinstance(date_payload, dict) else date_payload,
                    }
                except ValueError:
                    date_meta["parse_error"] = "date range response was not JSON"
        report["bitview"]["series"][series_id] = series_record
        time.sleep(0.15)
    report["finished_utc"] = datetime.now(timezone.utc).isoformat()
    (OUT / "diagnostic_report.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"report": str(OUT / "diagnostic_report.json"), "explore21_metrics": len(report["explore21"]),
                      "bitview_searches": len(report["bitview"]["search"]), "bitview_series": len(report["bitview"]["series"]),
                      "finished_utc": report["finished_utc"]}, indent=2))

if __name__ == "__main__":
    main()
