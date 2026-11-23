"""Free-first Coin Metrics Community API acquisition for V6.0 research.

Community data is for non-commercial use under Coin Metrics' published
Creative Commons terms. This module never changes Production or emits trades.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse

import pandas as pd
import requests

BASE_URL = "https://community-api.coinmetrics.io/v4"
DEFAULT_METRICS = (
    "CapMVRVCur",
    "CapMVRVZ",
    "FeeTotUSD",
    "IssTotUSD",
    "PuellMulTot",
    "PriceUSD",
    "SplyCur",
    "RevAllTimeUSD",
    "SplyMiner0HopAllNtv",
    "SplyMiner1HopAllNtv",
)
ALLOWED_HOST = "community-api.coinmetrics.io"


def _get_json(session, url, *, params=None, timeout=60):
    response = session.get(url, params=params, timeout=timeout)
    response.raise_for_status()
    payload = response.json()
    if not isinstance(payload, dict) or not isinstance(payload.get("data"), list):
        raise ValueError("Coin Metrics response did not contain a data array")
    return payload


def fetch_daily_btc_metrics(
    *,
    start_time="2009-01-03",
    end_time=None,
    metrics=DEFAULT_METRICS,
    session=None,
    page_size=10000,
):
    """Fetch BTC daily asset metrics from the no-key Community API.

    Pagination follows Coin Metrics' next_page_url unmodified. Null values stay
    null. The returned frame is indexed by unique UTC dates and includes only
    the requested metric columns that the endpoint actually returned.
    """
    if not metrics:
        raise ValueError("At least one metric is required")
    if not 1 <= int(page_size) <= 10000:
        raise ValueError("page_size must be between 1 and 10000")
    client = session or requests.Session()
    params = {
        "assets": "btc",
        "metrics": ",".join(metrics),
        "frequency": "1d",
        "start_time": start_time,
        "paging_from": "start",
        "page_size": int(page_size),
        "format": "json",
    }
    if end_time:
        params["end_time"] = end_time

    payload = _get_json(
        client, f"{BASE_URL}/timeseries/asset-metrics", params=params
    )
    rows = list(payload["data"])
    next_url = payload.get("next_page_url")
    while next_url:
        parsed = urlparse(next_url)
        if parsed.scheme != "https" or parsed.hostname != ALLOWED_HOST:
            raise ValueError("Unexpected Coin Metrics pagination host")
        payload = _get_json(client, next_url)
        rows.extend(payload["data"])
        next_url = payload.get("next_page_url")

    if not rows:
        raise ValueError("Coin Metrics returned no observations")

    frame = pd.DataFrame.from_records(rows)
    if "time" not in frame:
        raise ValueError("Coin Metrics response has no time field")
    dates = pd.to_datetime(frame.pop("time"), utc=True, errors="coerce").dt.normalize()
    frame = frame.drop(columns=["asset"], errors="ignore")
    frame.index = dates
    frame.index.name = "date_utc"
    frame = frame.loc[frame.index.notna()].sort_index()
    if frame.index.has_duplicates:
        raise ValueError("Coin Metrics returned duplicate BTC daily dates")

    available = [metric for metric in metrics if metric in frame.columns]
    if not available:
        raise ValueError(
            "None of the requested metrics were returned. Check Community API entitlements and metric IDs."
        )
    frame = frame[available].apply(pd.to_numeric, errors="coerce")
    return frame


def save_snapshot(frame, output_csv, *, requested_metrics=DEFAULT_METRICS):
    """Write the raw CSV plus an attribution/provenance JSON sidecar."""
    output = Path(output_csv)
    output.parent.mkdir(parents=True, exist_ok=True)
    frame.to_csv(output, index=True, index_label="date_utc")
    digest = hashlib.sha256(output.read_bytes()).hexdigest()
    metadata = {
        "provider": "Coin Metrics Community API",
        "endpoint": f"{BASE_URL}/timeseries/asset-metrics",
        "asset": "btc",
        "frequency": "1d",
        "requested_metrics": list(requested_metrics),
        "returned_metrics": list(frame.columns),
        "first_date_utc": str(frame.index.min().date()) if len(frame) else None,
        "last_date_utc": str(frame.index.max().date()) if len(frame) else None,
        "observations": int(len(frame)),
        "retrieved_at_utc": datetime.now(timezone.utc).isoformat(),
        "license": "Coin Metrics Community Data — CC BY-NC 4.0; non-commercial use only; attribution required",
        "sha256_csv": digest,
        "missing_values_by_metric": {
            column: int(frame[column].isna().sum()) for column in frame.columns
        },
        "unavailable_metrics": frame.attrs.get("unavailable_metrics", {}),
    }
    sidecar = output.with_suffix(".metadata.json")
    sidecar.write_text(json.dumps(metadata, indent=2) + "\n", encoding="utf-8")
    return sidecar


def fetch_daily_btc_metrics_resilient(
    *,
    start_time="2009-01-03",
    end_time=None,
    metrics=DEFAULT_METRICS,
    session=None,
    page_size=10000,
):
    """Try one efficient batch, then isolate metrics omitted/restricted by Community access.

    If the batch is rejected or omits one or more requested metric columns,
    only the missing metrics are requested separately. Unavailable IDs are
    recorded in DataFrame.attrs; no missing series is silently zero-filled.
    """
    client = session or requests.Session()
    unavailable = {}
    frames = []
    try:
        batch = fetch_daily_btc_metrics(
            start_time=start_time, end_time=end_time, metrics=metrics,
            session=client, page_size=page_size,
        )
        frames.append(batch)
        missing = [metric for metric in metrics if metric not in batch.columns]
    except requests.HTTPError:
        missing = list(metrics)

    for metric in missing:
        try:
            one = fetch_daily_btc_metrics(
                start_time=start_time, end_time=end_time, metrics=(metric,),
                session=client, page_size=page_size,
            )
            frames.append(one)
        except (requests.HTTPError, ValueError) as exc:
            response = getattr(exc, "response", None)
            unavailable[metric] = getattr(response, "status_code", None) or str(exc)

    if not frames:
        raise RuntimeError(
            "No requested metric was available from the Coin Metrics Community API; "
            f"unavailable={unavailable}"
        )
    result = pd.concat(frames, axis=1, join="outer").sort_index()
    result = result.loc[:, ~result.columns.duplicated()]
    result.attrs["unavailable_metrics"] = unavailable
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--start-date", default="2009-01-03")
    parser.add_argument("--end-date", default=None)
    parser.add_argument(
        "--output",
        default="data/research/coinmetrics_btc_daily_community.csv",
    )
    args = parser.parse_args()
    frame = fetch_daily_btc_metrics_resilient(
        start_time=args.start_date, end_time=args.end_date
    )
    sidecar = save_snapshot(frame, args.output)
    print(
        json.dumps(
            {
                "rows": len(frame),
                "columns": list(frame.columns),
                "first_date": str(frame.index.min().date()),
                "last_date": str(frame.index.max().date()),
                "csv": args.output,
                "metadata": str(sidecar),
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
