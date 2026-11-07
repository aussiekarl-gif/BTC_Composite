"""Read-only Coin Metrics Puell source acceptance: never writes market tapes or signals."""
from __future__ import annotations

import datetime as dt
import json
from pathlib import Path
import urllib.parse
import urllib.request

BASE = "https://community-api.coinmetrics.io/v4/timeseries/asset-metrics"
METRICS = ("IssTotUSD", "IssTotNtv", "PriceUSD", "RevNtv", "FeeTotNtv")


def fetch(metric: str, start: str, end: str) -> dict[str, float]:
    params = urllib.parse.urlencode({"assets": "btc", "metrics": metric, "frequency": "1d",
                                     "start_time": start, "end_time": end, "page_size": 10000})
    values = {}
    url = BASE + "?" + params
    while url:
        with urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": "BTC-Puell-research-audit/1.0"}), timeout=35) as response:
            payload = json.load(response)
        for row in payload.get("data", []):
            try:
                day = dt.datetime.fromisoformat(row["time"].replace("Z", "+00:00")).date().isoformat()
                values[day] = float(row[metric])
            except (KeyError, TypeError, ValueError):
                continue
        url = payload.get("next_page_url")
    return values


def report() -> dict:
    today = dt.datetime.now(dt.timezone.utc).date()
    start = (today - dt.timedelta(days=440)).isoformat()
    end = (today - dt.timedelta(days=2)).isoformat()
    result = {"audit": "read_only_coinmetrics_puell_source", "start": start, "end": end,
              "not_live_trading_validation": True, "metrics": {}, "comparison": {}}
    series = {}
    for metric in METRICS:
        try:
            series[metric] = fetch(metric, start, end)
            result["metrics"][metric] = {"rows": len(series[metric]), "status": "OK" if series[metric] else "NO_DATA"}
        except Exception as exc:
            series[metric] = {}
            result["metrics"][metric] = {"rows": 0, "status": "FETCH_FAILED",
                                         "error_type": type(exc).__name__}
    direct = series["IssTotUSD"]
    native = series["IssTotNtv"]
    price = series["PriceUSD"]
    common = sorted(set(direct) & set(native) & set(price))
    if common:
        relative_errors = [abs(direct[d] - native[d] * price[d]) / max(abs(direct[d]), 1e-12)
                           for d in common]
        result["comparison"] = {"paired_days": len(common), "max_relative_difference": max(relative_errors),
                                "mean_relative_difference": sum(relative_errors) / len(relative_errors),
                                "definition": "IssTotUSD versus IssTotNtv * PriceUSD; NOT an independent Puell variant"}
    result["ready_for_merge"] = False
    result["independent_matching_puell_series_verified"] = False
    return result


if __name__ == "__main__":
    destination = Path("artifacts/research_puell_live_source_audit.json")
    destination.parent.mkdir(parents=True, exist_ok=True)
    data = report()
    destination.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(data, sort_keys=True))
