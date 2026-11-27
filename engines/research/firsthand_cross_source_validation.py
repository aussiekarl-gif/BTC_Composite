"""Compare Firsthand Bitcoin daily series with Coin Metrics Community observations.

Research-only diagnostic. It does not write project model inputs or alter signals.
"""
from __future__ import annotations

import argparse
import csv
import io
import json
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
import requests

FIRSTHAND_CATALOGUE = "https://firsthandbitcoin.com/data/api/series.json"
COINMETRICS_URL = "https://community-api.coinmetrics.io/v4/timeseries/asset-metrics"
EXPLORE21_PRICE_CSV = "https://charts.explore21.com/data/bitcoin-price.csv"
METRICS = ("PriceUSD", "FeeTotNtv", "CapMVRVCur")


def fetch_firsthand(session=requests, keys=("btc", "fees", "realized", "mvrv", "ma200w")):
    response = session.get(FIRSTHAND_CATALOGUE, timeout=30)
    response.raise_for_status()
    catalogue = response.json()
    entries = {item["key"]: item for item in catalogue["series"]}
    frames = {}
    for key in keys:
        if key not in entries:
            raise ValueError(f"Firsthand catalogue missing required series: {key}")
        payload_response = session.get(entries[key]["json"], timeout=30)
        payload_response.raise_for_status()
        payload = payload_response.json()
        if not isinstance(payload.get("data"), list):
            raise ValueError(f"Firsthand {key} payload has no data list")
        frame = pd.DataFrame(payload["data"], columns=["date", key])
        frame["date"] = pd.to_datetime(frame["date"], utc=True, errors="raise").dt.normalize()
        frame[key] = pd.to_numeric(frame[key], errors="coerce")
        if frame["date"].duplicated().any() or not frame["date"].is_monotonic_increasing:
            raise ValueError(f"Firsthand {key} dates are duplicate or non-monotonic")
        frames[key] = frame.set_index("date")[key]
    return pd.concat(frames.values(), axis=1).sort_index()


def fetch_coinmetrics(session=requests, start_date="2013-01-01"):
    params = {
        "assets": "btc", "metrics": ",".join(METRICS), "frequency": "1d",
        "start_time": start_date, "paging_from": "start", "page_size": 10000,
        "format": "json",
    }
    response = session.get(COINMETRICS_URL, params=params, timeout=60)
    response.raise_for_status()
    payload = response.json()
    rows = list(payload.get("data", []))
    next_url = payload.get("next_page_url")
    while next_url:
        if not next_url.startswith("https://community-api.coinmetrics.io/"):
            raise ValueError("Unexpected Coin Metrics pagination URL")
        response = session.get(next_url, timeout=60)
        response.raise_for_status()
        payload = response.json()
        rows.extend(payload.get("data", []))
        next_url = payload.get("next_page_url")
    frame = pd.DataFrame(rows)
    if frame.empty or "time" not in frame:
        raise ValueError("Coin Metrics returned no dated observations")
    frame["date"] = pd.to_datetime(frame.pop("time"), utc=True).dt.normalize()
    frame = frame.drop(columns=["asset"], errors="ignore").set_index("date").sort_index()
    if frame.index.duplicated().any():
        raise ValueError("Coin Metrics returned duplicate dates")
    for metric in METRICS:
        if metric in frame:
            frame[metric] = pd.to_numeric(frame[metric], errors="coerce")
    return frame



def fetch_explore21_price(session=requests):
    """Fetch Explore21's independent Bitstamp UTC daily OHLC price history."""
    response = session.get(EXPLORE21_PRICE_CSV, timeout=45,
                           headers={"User-Agent": "BTC-Composite-research/1.0",
                                    "Accept": "text/csv"})
    response.raise_for_status()
    if len(response.content) > 10_000_000:
        raise ValueError("Unexpectedly large Explore21 price CSV")
    reader = csv.DictReader(io.StringIO(response.text))
    required = {"date", "btc_open_usd", "btc_high_usd", "btc_low_usd", "btc_close_usd"}
    if not reader.fieldnames or not required.issubset(reader.fieldnames):
        raise ValueError("Explore21 price CSV schema changed")
    frame = pd.DataFrame(list(reader))
    frame["date"] = pd.to_datetime(frame["date"], utc=True, errors="raise").dt.normalize()
    for col in required - {"date"}:
        frame[col] = pd.to_numeric(frame[col], errors="coerce")
    frame = frame.set_index("date").sort_index()
    if frame.index.duplicated().any():
        raise ValueError("Explore21 price dates are duplicated")
    return frame



def compare_series(left, right, *, min_observations=30):
    pair = pd.concat([left.rename("firsthand"), right.rename("coinmetrics")], axis=1).dropna()
    pair = pair[(pair["firsthand"] > 0) & (pair["coinmetrics"] > 0)]
    if len(pair) < min_observations:
        return {"observations": int(len(pair)), "status": "INSUFFICIENT_OVERLAP"}
    ape = ((pair["firsthand"] / pair["coinmetrics"]) - 1).abs() * 100
    recent = pair.loc[pair.index >= pair.index.max() - pd.Timedelta(days=90)]
    recent_ape = ((recent["firsthand"] / recent["coinmetrics"]) - 1).abs() * 100
    worst = ape.nlargest(10)
    return {
        "status": "COMPARISON_ONLY",
        "observations": int(len(pair)),
        "first_date": pair.index.min().date().isoformat(),
        "last_date": pair.index.max().date().isoformat(),
        "mean_ape_pct": float(ape.mean()),
        "median_ape_pct": float(ape.median()),
        "p95_ape_pct": float(ape.quantile(0.95)),
        "max_ape_pct": float(ape.max()),
        "recent_90d_observations": int(len(recent)),
        "recent_90d_mean_ape_pct": float(recent_ape.mean()) if len(recent) else None,
        "worst_dates": [
            {"date": idx.date().isoformat(), "ape_pct": float(value),
             "firsthand": float(pair.loc[idx, "firsthand"]),
             "coinmetrics": float(pair.loc[idx, "coinmetrics"])}
            for idx, value in worst.items()
        ],
    }




def compare_date_lags(left, right, *, start_date="2017-01-01", max_lag_days=2):
    """Test whether UTC date-label shifts explain apparent price disagreement.

    Positive lag means compare left[D] with right[D+lag]. This is diagnostic
    only; it must not be used to silently shift or repair a provider series.
    """
    rows = []
    for lag in range(-max_lag_days, max_lag_days + 1):
        aligned = pd.concat({
            "left": left,
            "right": right.shift(-lag),
        }, axis=1).dropna()
        aligned = aligned.loc[aligned.index >= pd.Timestamp(start_date, tz="UTC")]
        aligned = aligned[(aligned["left"] > 0) & (aligned["right"] > 0)]
        if aligned.empty:
            rows.append({"right_date_offset_days": lag, "observations": 0})
            continue
        ape = ((aligned["left"] / aligned["right"]) - 1.0).abs() * 100.0
        worst = ape.nlargest(5)
        rows.append({
            "right_date_offset_days": lag,
            "observations": int(len(aligned)),
            "mean_ape_pct": float(ape.mean()),
            "median_ape_pct": float(ape.median()),
            "p95_ape_pct": float(ape.quantile(0.95)),
            "max_ape_pct": float(ape.max()),
            "worst_dates": [
                {"left_date": d.date().isoformat(),
                 "right_date": (d + pd.Timedelta(days=lag)).date().isoformat(),
                 "ape_pct": float(v),
                 "left_price": float(aligned.loc[d, "left"]),
                 "right_price": float(aligned.loc[d, "right"])}
                for d, v in worst.items()
            ],
        })
    return {
        "status": "DIAGNOSTIC_ONLY_NO_AUTOMATIC_REALIGNMENT",
        "start_date": start_date,
        "offset_definition": "positive offset compares left[D] with right[D+offset]",
        "results": rows,
        "best_mean_ape_offset_days": min(
            (r for r in rows if r.get("observations", 0)),
            key=lambda r: r["mean_ape_pct"],
        )["right_date_offset_days"],
    }


def compare_200wma_distance(firsthand, coinmetrics, *, start_date="2017-01-01"):
    """Compare discount tiers using the exact V6.0 prior-200-Sunday-close signal."""
    from engines.research.v60_200wma_policy import weekly_prior_200wma_signals

    fh = weekly_prior_200wma_signals(firsthand["btc"]).set_index("signal_date")
    cm = weekly_prior_200wma_signals(coinmetrics["PriceUSD"]).set_index("signal_date")
    pair = pd.concat({
        "firsthand_distance_pct": fh["discount_below_200wma_pct"],
        "coinmetrics_distance_pct": cm["discount_below_200wma_pct"],
    }, axis=1).dropna()
    pair = pair.loc[pair.index >= pd.Timestamp(start_date, tz="UTC")]
    if pair.empty:
        return {"status": "INSUFFICIENT_OVERLAP", "observations": 0}
    delta = (pair["firsthand_distance_pct"] - pair["coinmetrics_distance_pct"]).abs()
    tiers = {}
    for threshold in (0, 5, 10, 15, 20, 25, 30):
        a = pair["firsthand_distance_pct"] >= threshold
        b = pair["coinmetrics_distance_pct"] >= threshold
        flips = pair.index[a != b]
        tiers[str(threshold)] = {
            "firsthand_signal_weeks": int(a.sum()),
            "coinmetrics_signal_weeks": int(b.sum()),
            "disagreement_weeks": int(len(flips)),
            "disagreement_pct": float(len(flips) / len(pair) * 100.0),
            "first_10_disagreement_dates": [d.date().isoformat() for d in flips[:10]],
        }
    return {
        "status": "RESEARCH_ONLY_EXACT_V60_WEEKLY_THRESHOLD_SENSITIVITY",
        "signal_definition": "Completed Sunday close / mean of previous 200 completed Sunday closes; signal Sunday excluded",
        "first_signal_date": pair.index.min().date().isoformat(),
        "last_signal_date": pair.index.max().date().isoformat(),
        "observations": int(len(pair)),
        "absolute_discount_difference_percentage_points": {
            "mean": float(delta.mean()), "median": float(delta.median()),
            "p95": float(delta.quantile(0.95)), "max": float(delta.max()),
        },
        "thresholds": tiers,
        "note": "Exact weekly V6.0 signal classifications only; no simulated execution or portfolio outcome.",
    }


def build_report(firsthand, coinmetrics, explore21_price):
    comparisons = {
        "btc_price_usd_vs_coinmetrics": compare_series(firsthand["btc"], coinmetrics["PriceUSD"]),
        "btc_price_date_lag_vs_coinmetrics": compare_date_lags(firsthand["btc"], coinmetrics["PriceUSD"]),
        "btc_price_date_lag_vs_explore21_bitstamp": compare_date_lags(firsthand["btc"], explore21_price["btc_close_usd"]),
        "btc_price_usd_vs_explore21_bitstamp_close": compare_series(firsthand["btc"], explore21_price["btc_close_usd"]),
        "coinmetrics_priceusd_vs_explore21_bitstamp_close": compare_series(coinmetrics["PriceUSD"], explore21_price["btc_close_usd"]),
        "200wma_vs_coinmetrics_1400_calendar_day_sma": compare_series(
            firsthand["ma200w"],
            coinmetrics["PriceUSD"].rolling(1400, min_periods=1400).mean(),
        ),
        "200wma_distance_threshold_sensitivity": compare_200wma_distance(firsthand, coinmetrics),
        "daily_fees_btc": compare_series(firsthand["fees"], coinmetrics["FeeTotNtv"]),
        "mvrv": compare_series(firsthand["mvrv"], coinmetrics["CapMVRVCur"]),
    }
    # Realised price derived algebraically from Coin Metrics price / MVRV.
    if {"PriceUSD", "CapMVRVCur"}.issubset(coinmetrics.columns):
        cm_realized = coinmetrics["PriceUSD"] / coinmetrics["CapMVRVCur"]
        comparisons["realized_price_usd_vs_cm_price_over_mvrv"] = compare_series(
            firsthand["realized"], cm_realized
        )
    coverage = {}
    for name, series in {**{f"firsthand_{k}": v for k, v in firsthand.items()},
                         **{f"coinmetrics_{k}": coinmetrics[k] for k in coinmetrics.columns}}.items():
        coverage[name] = {
            "first_date": series.dropna().index.min().date().isoformat() if series.notna().any() else None,
            "last_date": series.dropna().index.max().date().isoformat() if series.notna().any() else None,
            "rows": int(series.notna().sum()),
            "missing_dates_within_span": int((pd.date_range(series.dropna().index.min(),
                series.dropna().index.max(), freq="D", tz="UTC").difference(series.dropna().index)).size)
                if series.notna().any() else None,
        }
    return {
        "provider": "Firsthand Bitcoin vs Coin Metrics Community",
        "retrieved_at_utc": datetime.now(timezone.utc).isoformat(),
        "purpose": "research-only cross-source comparison; not a data-source approval",
        "comparison_method": "same UTC calendar date; three-way BTC price comparison includes Explore21 Bitstamp UTC close",
        "price_source_notes": {"coinmetrics": "PriceUSD is Coin Metrics reference rate at end of UTC day", "explore21": "Explore21 states daily BTC/USD candles are Bitstamp last trade of UTC day", "firsthand": "Firsthand provider daily price venue and timestamp convention still to be confirmed"},
        "realized_price_note": "Coin Metrics reference is PriceUSD / CapMVRVCur, not a directly published realised-price metric; this assumes matching supply basis.",
        "coverage": coverage,
        "comparisons": comparisons,
        "decision": "NOT_APPROVED_FOR_MODEL_INPUTS",
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", default="artifacts/firsthand/cross_source_comparison.json")
    args = parser.parse_args()
    firsthand = fetch_firsthand()
    coinmetrics = fetch_coinmetrics(start_date=str(firsthand.index.min().date()))
    explore21_price = fetch_explore21_price()
    report = build_report(firsthand, coinmetrics, explore21_price)
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
