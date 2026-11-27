"""Aethereal public Bitcoin network daily dataset adapter.

The dataset is free for research and education. Preserve its source attribution,
raw BTC fee units, date convention and missing values; do not infer zero fees.
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

DATASET_URL = "https://dataset.aethereal.top/datasets/bitcoin-network-daily"
CSV_URL = "https://dataset.aethereal.top/files/bitcoin-network-daily.csv"
REQUIRED_COLUMNS = ("fees_btc", "price_usd", "miners_revenue_usd", "transactions")


def fetch_daily_btc_network(*, session=None, timeout=15):
    """Fetch the raw daily network CSV and validate dates/fee units."""
    client = session or requests.Session()
    response = client.get(CSV_URL, timeout=timeout)
    response.raise_for_status()
    frame = pd.read_csv(StringIO(response.text))
    if "date" not in frame.columns:
        raise ValueError("Aethereal Bitcoin Network Daily CSV has no date column")
    missing = set(REQUIRED_COLUMNS) - set(frame.columns)
    if missing:
        raise ValueError(f"Aethereal dataset is missing columns: {sorted(missing)}")
    dates = pd.to_datetime(frame.pop("date"), utc=True, errors="coerce").dt.normalize()
    frame.index = dates
    frame.index.name = "date_utc"
    frame = frame.loc[frame.index.notna()].sort_index()
    if frame.index.has_duplicates:
        raise ValueError("Aethereal dataset contains duplicate UTC daily dates")
    for column in frame.columns:
        frame[column] = pd.to_numeric(frame[column], errors="coerce")
    frame.attrs["provider"] = "Aethereal Data"
    frame.attrs["source_url"] = CSV_URL
    return frame


def save_snapshot(frame, output_csv):
    """Save raw CSV and a provenance/attribution sidecar."""
    if frame.attrs.get("provider") != "Aethereal Data":
        raise ValueError("Frame is missing Aethereal source provenance")
    output = Path(output_csv)
    output.parent.mkdir(parents=True, exist_ok=True)
    frame.to_csv(output, index=True, index_label="date_utc")
    metadata = {
        "provider": "Aethereal Data",
        "dataset": "Bitcoin Network Daily",
        "dataset_url": DATASET_URL,
        "source_csv_url": frame.attrs.get("source_url", CSV_URL),
        "license": "Free for research and education; not a blanket commercial redistribution licence",
        "attribution": f"Aethereal (2026), Bitcoin Network Daily, {DATASET_URL}",
        "retrieved_at_utc": datetime.now(timezone.utc).isoformat(),
        "first_date_utc": str(frame.index.min().date()) if len(frame) else None,
        "last_date_utc": str(frame.index.max().date()) if len(frame) else None,
        "observations": int(len(frame)),
        "columns": list(frame.columns),
        "missing_values_by_column": {
            column: int(frame[column].isna().sum()) for column in frame.columns
        },
        "fee_unit": "BTC per UTC day; block timestamp assigns blocks to UTC day",
        "price_note": "Aethereal price_usd may use a different daily price convention from Coin Metrics; do not multiply fees by this price for cross-provider USD parity without checking.",
        "sha256_csv": hashlib.sha256(output.read_bytes()).hexdigest(),
    }
    sidecar = output.with_suffix(".metadata.json")
    sidecar.write_text(json.dumps(metadata, indent=2) + "\n", encoding="utf-8")
    return sidecar


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output",
        default="data/research/cowen_onchain/bitcoin_network_daily_aethereal.csv",
    )
    args = parser.parse_args()
    frame = fetch_daily_btc_network()
    sidecar = save_snapshot(frame, args.output)
    print(json.dumps({
        "rows": len(frame),
        "first_date": str(frame.index.min().date()),
        "last_date": str(frame.index.max().date()),
        "latest_fees_btc": float(frame["fees_btc"].dropna().iloc[-1]),
        "csv": args.output,
        "metadata": str(sidecar),
    }, indent=2))


if __name__ == "__main__":
    main()
