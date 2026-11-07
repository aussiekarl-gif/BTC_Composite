"""Read-only Coin Metrics Puell source acceptance: never writes market tapes or signals."""
from __future__ import annotations

import datetime as dt
import json
import urllib.error
from pathlib import Path
import urllib.parse
import urllib.request

BASE = "https://community-api.coinmetrics.io/v4/timeseries/asset-metrics"
METRICS = ("IssTotUSD", "IssTotNtv", "PriceUSD", "RevNtv", "FeeTotNtv", "RevUSD", "IssContUSD")


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
                                         "error_type": type(exc).__name__,
                                         "http_status": exc.code if isinstance(exc, urllib.error.HTTPError) else None}
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
    # Recompute exact rolling calendar-year Puell ratios on actual provider rows.
    # Do not call the RevUSD/IssContUSD variants equivalent to IssTotUSD.
    for name in ("IssTotUSD", "RevUSD", "IssContUSD"):
        values = series[name]
        if not values:
            continue
        ordered_days = [dt.date.fromisoformat(d) for d in sorted(values)]
        daily = {dt.date.fromisoformat(d): v for d, v in values.items()}
        latest = ordered_days[-1]
        window = [latest - dt.timedelta(days=i) for i in range(364, -1, -1)]
        if all(d in daily for d in window):
            average = sum(daily[d] for d in window) / 365
            result.setdefault("puell_variants", {})[name] = {
                "date": latest.isoformat(),
                "value": daily[latest] / average if average > 0 else None,
                "complete_365_calendar_days": True,
                "note": "Derived from source observations; not independent published Puell series"}
        else:
            result.setdefault("puell_variants", {})[name] = {
                "date": latest.isoformat(), "complete_365_calendar_days": False}
    result["primary_source_healthy"] = (
        result["metrics"]["IssTotUSD"]["status"] == "OK"
        and result["metrics"]["IssTotNtv"]["status"] == "OK"
        and result["metrics"]["PriceUSD"]["status"] == "OK"
        and result["comparison"].get("paired_days", 0) >= 365
        and result["comparison"].get("max_relative_difference", 1) < 1e-8
        and result.get("puell_variants", {}).get("IssTotUSD", {}).get("complete_365_calendar_days") is True)
    result["ready_for_merge"] = False
    result["independent_matching_puell_series_verified"] = False
    return result


if __name__ == "__main__":
    destination = Path("artifacts/research_puell_live_source_audit.json")
    destination.parent.mkdir(parents=True, exist_ok=True)
    data = report()
    destination.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(data, sort_keys=True))
    if not data["primary_source_healthy"]:
        raise SystemExit("Coin Metrics primary Puell source audit FAILED; report artifact retained")
