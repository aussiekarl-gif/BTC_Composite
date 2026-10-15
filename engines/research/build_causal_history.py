"""Build a reproducible BTC/AUD weekly research series using causal Power Law risk.

Uses historical Blockchain.com BTC/USD closes and Frankfurter AUD FX.
Research-only: do not treat FX fallback values as validated historical data.
"""
import argparse
import datetime as dt
import json
import numpy as np
import pandas as pd
import requests



def build_dataset(start="2015-01-01", end=None):
    if end is None:
        end = dt.date.today().isoformat()
    raw = requests.get(
        "https://api.blockchain.info/charts/market-price",
        params={"timespan": "all", "format": "json", "sampled": "false"},
        timeout=45,
    )
    raw.raise_for_status()
    payload = raw.json()
    btc = pd.DataFrame(
        [(pd.to_datetime(p["x"], unit="s", utc=True), float(p["y"]))
         for p in payload.get("values", []) if float(p["y"]) > 0],
        columns=["date", "price"],
    ).set_index("date").sort_index()
    btc = btc.loc[~btc.index.duplicated(keep="last")]
    # Include pre-start history so the expanding risk regression is warmed up.
    btc = btc.loc[(btc.index >= pd.Timestamp(start, tz="UTC") - pd.Timedelta(days=730)) &
                  (btc.index <= pd.Timestamp(end, tz="UTC"))]
    if btc.empty:
        raise ValueError("No BTC historical observations")
    fx_start = (pd.Timestamp(start) - pd.Timedelta(days=730)).date().isoformat()
    # Long-range Frankfurter requests can time out (HTTP 522). Fetch annual
    # windows independently; never substitute synthetic FX values.
    fx_parts = []
    session = requests.Session()
    for year in range(pd.Timestamp(fx_start).year, pd.Timestamp(end).year + 1):
        chunk_start = max(pd.Timestamp(fx_start), pd.Timestamp(f"{year}-01-01"))
        chunk_end = min(pd.Timestamp(end), pd.Timestamp(f"{year}-12-31"))
        if chunk_start > chunk_end:
            continue
        fx_url = (f"https://api.frankfurter.app/"
                  f"{chunk_start.date().isoformat()}..{chunk_end.date().isoformat()}"
                  "?from=USD&to=AUD")
        # Primary Frankfurter host occasionally stalls. Retry briefly and
        # switch to the documented v1 host before failing closed.
        rates = None
        errors = []
        for host in ("https://api.frankfurter.dev/v1/",
                     "https://api.frankfurter.app/"):
            try:
                url = fx_url.replace("https://api.frankfurter.app/", host)
                response = session.get(url, timeout=(8, 18))
                response.raise_for_status()
                rates = response.json().get("rates", {})
                if rates:
                    break
            except requests.RequestException as exc:
                errors.append(str(exc))
        if not rates:
            raise ValueError(f"USD/AUD provider unavailable for {year}: {errors}")
        if not rates:
            raise ValueError(f"Missing USD/AUD FX history for {year}")
        fx_parts.append(pd.Series(
            {pd.Timestamp(day, tz="UTC"): float(value["AUD"])
             for day, value in rates.items()}, dtype=float))
    fx = pd.concat(fx_parts).sort_index()
    fx = fx.loc[~fx.index.duplicated(keep="last")]
    if fx.empty or not np.isfinite(fx).all() or not (fx > 0).all():
        raise ValueError("No validated USD-to-AUD FX history")
    if fx.index.min() > btc.index.min() + pd.Timedelta(days=7):
        raise ValueError("FX history does not cover BTC start")
    btc["aud_per_usd"] = fx.reindex(btc.index.union(fx.index)).sort_index().ffill().reindex(btc.index)
    if btc["aud_per_usd"].isna().any():
        raise ValueError("Missing early FX observations; refusing to invent exchange rates")
    btc = btc.dropna(subset=["aud_per_usd"])
    btc["btc_price_aud"] = btc["price"] * btc["aud_per_usd"]
    # Refit expanding log-price versus log-days every 91 days, with 52 weekly
    # observations minimum. Each regression uses strictly earlier weeks.
    genesis = pd.Timestamp("2009-01-03", tz="UTC")
    weekly = btc.resample("W-MON").last().dropna()
    scores = []
    last_fit = None
    slope = intercept = None
    for ts, row in weekly.iterrows():
        if last_fit is None or (ts - last_fit).days >= 91:
            history = weekly.loc[weekly.index < ts, "price"]
            days = np.array((history.index - genesis).days, dtype=float)
            values = history.to_numpy(dtype=float)
            valid = (days > 0) & (values > 0) & np.isfinite(values)
            if valid.sum() >= 52:
                slope, intercept = np.polyfit(np.log10(days[valid]), np.log10(values[valid]), 1)
                last_fit = ts
        if slope is None:
            scores.append(np.nan)
        else:
            days_now = (ts - genesis).days
            fair_log = slope * np.log10(days_now) + intercept
            scores.append(float(np.clip((np.log10(row["price"]) - fair_log + .10) / .30, 0, 1)))
    weekly["risk_score"] = scores
    weekly = weekly.dropna(subset=["risk_score"])
    if len(weekly) < 100:
        raise ValueError("Insufficient scored weekly observations")
    result = weekly.loc[weekly.index >= pd.Timestamp(start, tz="UTC"),
                        ["btc_price_aud", "risk_score"]].copy()
    result.index.name = "date"
    return result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--start", default="2015-01-01")
    parser.add_argument("--end", default=dt.date.today().isoformat())
    parser.add_argument("--out", default="research_outputs/causal_btc_aud_weekly.csv")
    args = parser.parse_args()
    result = build_dataset(args.start, args.end)
    from pathlib import Path
    target = Path(args.out)
    target.parent.mkdir(parents=True, exist_ok=True)
    result.to_csv(target)
    print(json.dumps({"rows": len(result), "first": str(result.index.min()),
                      "last": str(result.index.max()), "csv": str(target)}))


if __name__ == "__main__":
    main()
