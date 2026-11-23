"""Explore21 public BTC daily metric CSV acquisition (CC BY 4.0).

The source catalogue currently lists Puell Multiple, MVRV and MVRV Z-Score.
This is a raw-data adapter only: no normalisation, backfilling or trade signals.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime, timezone
from io import StringIO
from pathlib import Path

import pandas as pd
import requests

CSV_BASE = "https://charts.explore21.com/data"
METRIC_CATALOG = {
    "bitcoin-puell-multiple": {
        "chart_url": "https://charts.explore21.com/bitcoin-puell-multiple",
        "method_version": 1,
        "expected_columns": ("puell_multiple", "issuance_btc", "issuance_usd",
                             "issuance_usd_365d_avg", "btc_close_usd"),
    },
    "bitcoin-mvrv-ratio": {
        "chart_url": "https://charts.explore21.com/bitcoin-mvrv-ratio",
        "method_version": 2,
        "expected_columns": ("mvrv_ratio", "btc_close_usd"),
    },
    "bitcoin-mvrv-z-score": {
        "chart_url": "https://charts.explore21.com/bitcoin-mvrv-z-score",
        "method_version": 1,
        "expected_columns": ("mvrv_z_score", "btc_close_usd"),
    },
}


def fetch_metric(metric_id, *, session=None, timeout=60):
    """Fetch one whitelisted daily CSV and preserve its original columns/blank cells."""
    if metric_id not in METRIC_CATALOG:
        raise ValueError(f"Unsupported Explore21 metric id: {metric_id}")
    client = session or requests.Session()
    url = f"{CSV_BASE}/{metric_id}.csv"
    response = client.get(url, timeout=timeout)
    response.raise_for_status()
    frame = pd.read_csv(StringIO(response.text))
    if "date" not in frame.columns:
        raise ValueError(f"{metric_id}: CSV has no date column")
    dates = pd.to_datetime(frame.pop("date"), utc=True, errors="coerce").dt.normalize()
    frame.index = dates
    frame.index.name = "date_utc"
    frame = frame.loc[frame.index.notna()].sort_index()
    if frame.index.has_duplicates:
        raise ValueError(f"{metric_id}: duplicate UTC dates")
    if not set(METRIC_CATALOG[metric_id]["expected_columns"]).issubset(frame.columns):
        raise ValueError(f"{metric_id}: expected source columns are missing")
    for column in frame.columns:
        frame[column] = pd.to_numeric(frame[column], errors="coerce")
    frame.attrs["metric_id"] = metric_id
    frame.attrs["source_url"] = url
    return frame


def save_metric(frame, output_csv):
    """Save raw source data with method, licence, retrieval and integrity metadata."""
    metric_id = frame.attrs.get("metric_id")
    if metric_id not in METRIC_CATALOG:
        raise ValueError("Frame is missing a recognised Explore21 metric_id")
    output = Path(output_csv)
    output.parent.mkdir(parents=True, exist_ok=True)
    frame.to_csv(output, index=True, index_label="date_utc")
    metadata = {
        "provider": "Explore21",
        "metric_id": metric_id,
        "chart_url": METRIC_CATALOG[metric_id]["chart_url"],
        "source_csv_url": frame.attrs.get("source_url"),
        "method_version": METRIC_CATALOG[metric_id]["method_version"],
        "license": "CC BY 4.0",
        "attribution": f"Explore21 Charts, {METRIC_CATALOG[metric_id]['chart_url']}, accessed {datetime.now(timezone.utc).date().isoformat()}",
        "retrieved_at_utc": datetime.now(timezone.utc).isoformat(),
        "first_date_utc": str(frame.index.min().date()) if len(frame) else None,
        "last_date_utc": str(frame.index.max().date()) if len(frame) else None,
        "observations": int(len(frame)),
        "columns": list(frame.columns),
        "missing_values_by_column": {
            column: int(frame[column].isna().sum()) for column in frame.columns
        },
        "sha256_csv": hashlib.sha256(output.read_bytes()).hexdigest(),
        "historical_vintage_note": (
            "Explore21's published point-in-time vintages begin 2026-11-18; "
            "earlier historical rows are not verified historical vintages."
        ),
    }
    sidecar = output.with_suffix(".metadata.json")
    sidecar.write_text(json.dumps(metadata, indent=2) + "\n", encoding="utf-8")
    return sidecar


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", default="data/research/explore21")
    args = parser.parse_args()
    output_dir = Path(args.output_dir)
    for metric_id in METRIC_CATALOG:
        frame = fetch_metric(metric_id)
        path = output_dir / f"{metric_id}.csv"
        sidecar = save_metric(frame, path)
        print(json.dumps({
            "metric_id": metric_id,
            "rows": len(frame),
            "first_date": str(frame.index.min().date()),
            "last_date": str(frame.index.max().date()),
            "csv": str(path),
            "metadata": str(sidecar),
        }))


if __name__ == "__main__":
    main()
