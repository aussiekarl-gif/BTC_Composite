"""Open Bitcoin Metrics daily CDD dataset adapter (CC BY 4.0)."""
from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime, timezone
from io import StringIO
from pathlib import Path

import pandas as pd
import requests

DATASET_URL = "https://github.com/diegorllanos/open-bitcoin-metrics"
CSV_URL = (
    "https://raw.githubusercontent.com/diegorllanos/open-bitcoin-metrics/main/"
    "metrics/obm_cdd_btcxdays_daily/obm_cdd_btcxdays_daily.csv"
)
SERIES_ID = "obm_cdd_btcxdays_daily"


def fetch_daily_cdd(*, session=None, timeout=60):
    """Fetch and validate the published full-history daily BTC-days CDD series."""
    client = session or requests.Session()
    response = client.get(CSV_URL, timeout=timeout)
    response.raise_for_status()
    frame = pd.read_csv(StringIO(response.text))
    required = {"date", "series_id", "value", "unit", "frequency", "release_version"}
    missing = required - set(frame.columns)
    if missing:
        raise ValueError(f"Open Bitcoin Metrics CDD CSV missing columns: {sorted(missing)}")
    frame = frame.loc[frame["series_id"].eq(SERIES_ID)].copy()
    if frame.empty:
        raise ValueError("Open Bitcoin Metrics CSV contains no daily CDD series rows")
    if not frame["unit"].eq("BTC-days").all():
        raise ValueError("Open Bitcoin Metrics CDD unit is not consistently BTC-days")
    if not frame["frequency"].eq("daily").all():
        raise ValueError("Open Bitcoin Metrics CDD frequency is not consistently daily")
    dates = pd.to_datetime(frame.pop("date"), utc=True, errors="coerce").dt.normalize()
    values = pd.to_numeric(frame.pop("value"), errors="coerce")
    frame.index = dates
    frame.index.name = "date_utc"
    frame["cdd_btc_days"] = values.to_numpy(dtype=float)
    frame = frame.loc[frame.index.notna()].sort_index()
    if frame.index.has_duplicates:
        raise ValueError("Open Bitcoin Metrics CDD contains duplicate UTC dates")
    if frame["cdd_btc_days"].isna().any():
        raise ValueError("Open Bitcoin Metrics CDD contains missing values")
    if (frame["cdd_btc_days"] < 0).any():
        raise ValueError("Open Bitcoin Metrics CDD contains negative values")
    if len(frame) > 1:
        gaps = frame.index.to_series().diff().dropna()
        if not gaps.eq(pd.Timedelta(days=1)).all():
            raise ValueError("Open Bitcoin Metrics CDD history has missing calendar dates")
    frame.attrs["provider"] = "Open Bitcoin Metrics"
    frame.attrs["dataset_url"] = DATASET_URL
    frame.attrs["source_url"] = CSV_URL
    frame.attrs["series_id"] = SERIES_ID
    frame.attrs["release_version"] = str(frame["release_version"].iloc[-1])
    return frame[["cdd_btc_days"]]


def save_snapshot(frame, output_csv):
    """Write CDD CSV with CC BY 4.0 attribution and integrity sidecar."""
    if frame.attrs.get("provider") != "Open Bitcoin Metrics":
        raise ValueError("Frame is missing Open Bitcoin Metrics source provenance")
    output = Path(output_csv)
    output.parent.mkdir(parents=True, exist_ok=True)
    frame.to_csv(output, index=True, index_label="date_utc")
    metadata = {
        "provider": "Open Bitcoin Metrics",
        "dataset_url": frame.attrs.get("dataset_url", DATASET_URL),
        "source_csv_url": frame.attrs.get("source_url", CSV_URL),
        "series_id": SERIES_ID,
        "release_version": frame.attrs.get("release_version"),
        "unit": "BTC-days",
        "frequency": "daily UTC",
        "license": "CC BY 4.0",
        "attribution": "Llanos, D. R., Open Bitcoin Metrics, metric obm_cdd_btcxdays_daily, https://arxiv.org/abs/2607.03124",
        "retrieved_at_utc": datetime.now(timezone.utc).isoformat(),
        "first_date_utc": str(frame.index.min().date()),
        "last_date_utc": str(frame.index.max().date()),
        "observations": int(len(frame)),
        "missing_values": int(frame["cdd_btc_days"].isna().sum()),
        "sha256_csv": hashlib.sha256(output.read_bytes()).hexdigest(),
        "method_note": "Spent-output value in BTC multiplied by age in days, summed over outputs spent on each UTC calendar day. The source's zero values are valid zero-flow observations.",
    }
    sidecar = output.with_suffix(".metadata.json")
    sidecar.write_text(json.dumps(metadata, indent=2) + "\n", encoding="utf-8")
    return sidecar


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output",
        default="data/research/cowen_onchain/obm_cdd_btcxdays_daily.csv",
    )
    args = parser.parse_args()
    frame = fetch_daily_cdd()
    sidecar = save_snapshot(frame, args.output)
    print(json.dumps({
        "rows": len(frame),
        "first_date": str(frame.index.min().date()),
        "last_date": str(frame.index.max().date()),
        "latest_cdd_btc_days": float(frame["cdd_btc_days"].iloc[-1]),
        "release_version": frame.attrs["release_version"],
        "csv": args.output,
        "metadata": str(sidecar),
    }, indent=2))


if __name__ == "__main__":
    main()
