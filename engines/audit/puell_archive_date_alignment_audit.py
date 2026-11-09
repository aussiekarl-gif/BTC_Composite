"""Read-only Puell calendar alignment audit for private BTC master exports.

Comparing a Coin Metrics-derived metric to the same self-calculated master
is NOT an independent provider validation. raw__puell_multiple__puellmultiple
is a separately archived raw export but provider timestamp conventions,
methodology, and original publication dates are not independently verified.

This script does NOT auto-shift, rewrite, or promote any trading input.
"""
from __future__ import annotations
import argparse
import csv
import json
import math
from datetime import date, timedelta
from pathlib import Path

SELF_FIELD = "Puell Multiple"
RAW_FIELD = "raw__puell_multiple__puellmultiple"
CM_ISSUANCE = "cm__IssTotNtv"
CM_PRICE = "cm__PriceUSD"


def _numeric(raw):
    if raw is None or raw == "":
        return None
    value = float(raw)
    if not math.isfinite(value) or value < 0:
        raise ValueError("Nonfinite or negative Puell source observation")
    return value


def load_archive(path: Path) -> dict[date, dict]:
    result = {}
    with Path(path).open("r", encoding="utf-8-sig", newline="") as fh:
        reader = csv.DictReader(fh)
        fields = {"date", SELF_FIELD, RAW_FIELD, CM_ISSUANCE, CM_PRICE}
        if not fields.issubset(reader.fieldnames or []):
            raise ValueError(f"Missing archive fields: {sorted(fields - set(reader.fieldnames or []))}")
        for line, row in enumerate(reader, 2):
            day = date.fromisoformat(row["date"][:10])
            if day in result:
                raise ValueError(f"Duplicate archive date at line {line}")
            result[day] = {
                "self": _numeric(row[SELF_FIELD]),
                "raw": _numeric(row[RAW_FIELD]),
                "issuance_native": _numeric(row[CM_ISSUANCE]),
                "price_usd": _numeric(row[CM_PRICE]),
            }
    if not result:
        raise ValueError("Archive is empty")
    return result


def _metric_pair_stats(pairs: list[tuple[float, float]]) -> dict:
    if not pairs:
        return {"n": 0, "mean_absolute_error": None, "correlation": None}
    n = len(pairs)
    mean_x = sum(x for x, _ in pairs) / n
    mean_y = sum(y for _, y in pairs) / n
    vx = sum((x - mean_x) ** 2 for x, _ in pairs)
    vy = sum((y - mean_y) ** 2 for x, y in pairs)
    covariance = sum((x - mean_x) * (y - mean_y) for x, y in pairs)
    return {
        "n": n,
        "mean_absolute_error": sum(abs(x - y) for x, y in pairs) / n,
        "correlation": covariance / math.sqrt(vx * vy) if vx > 0 and vy > 0 else None,
        "below_1_disagreements": sum((x < 1) != (y < 1) for x, y in pairs),
        "below_075_disagreements": sum((x < .75) != (y < .75) for x, y in pairs),
    }


def _status(raw: float, same: float, following: float,
            tolerance: float = 0.004) -> str:
    """Classification ONLY; never correct date labels in the source."""
    err_same = abs(raw - same)
    err_next = abs(raw - following)
    if err_next < tolerance and err_next < 0.6 * err_same:
        return "matches_following_day"
    if err_same < tolerance and err_same < 0.6 * err_next:
        return "matches_same_day"
    if abs(err_next - err_same) < .005:
        return "ambiguous"
    return "unresolved"


def report(records: dict[date, dict]) -> dict:
    issuance_usd = {
        day: row["issuance_native"] * row["price_usd"]
        for day, row in records.items()
        if row["issuance_native"] is not None and row["price_usd"] is not None
    }
    cm365 = {}
    for day in sorted(issuance_usd):
        dates = [day - timedelta(days=offset) for offset in range(365)]
        if all(d in issuance_usd for d in dates):
            denominator = sum(issuance_usd[d] for d in dates) / 365.
            if denominator > 0:
                cm365[day] = issuance_usd[day] / denominator
    internal_pairs = []
    same_pairs, following_pairs = [], []
    observations, classifications = [], {}
    for day in sorted(records):
        row = records[day]
        computed = cm365.get(day)
        if computed is not None and row["self"] is not None:
            internal_pairs.append((computed, row["self"]))
        if row["raw"] is None or computed is None:
            continue
        same_pairs.append((computed, row["raw"]))
        following = cm365.get(day + timedelta(days=1))
        if following is None:
            continue
        following_pairs.append((following, row["raw"]))
        state = _status(row["raw"], computed, following)
        classifications[state] = classifications.get(state, 0) + 1
        observations.append({"date": day.isoformat(), "class": state})
    # Longest strictly consecutive calendar streak with a single label.
    streaks = []
    current = None
    for obs in observations:
        if (current is not None and current["class"] == obs["class"]
                and (date.fromisoformat(obs["date"])
                     - date.fromisoformat(current["end"])).days == 1):
            current["end"] = obs["date"]
            current["days"] += 1
        else:
            current = {"start": obs["date"], "end": obs["date"],
                       "class": obs["class"], "days": 1}
            streaks.append(current)
    longest = sorted(streaks, key=lambda x: x["days"], reverse=True)[:6]
    return {
        "status": "RESEARCH_ONLY_DO_NOT_PROMOTE_SOURCE_DATE_ALIGNMENT_UNVERIFIED",
        "source_archive_is_private": True,
        "raw_export_provenance_not_independently_verified": True,
        "raw_time_shift_not_applied": True,
        "ready_for_production": False,
        "ready_for_trading": False,
        "master_rows": len(records),
        "calendar_complete_cm_puell_rows": len(cm365),
        "self_derived_vs_cm_reconstruction": _metric_pair_stats(internal_pairs),
        "raw_vs_derived_same_day": _metric_pair_stats(same_pairs),
        "raw_vs_derived_following_day": _metric_pair_stats(following_pairs),
        "alignment_classification_tolerance": 0.004,
        "alignment_classification": classifications,
        "longest_consecutive_alignment_streaks": longest,
        "notes": [
            "Master Puell and recomputed CM issuance are NOT independent series.",
            "Separately archived raw Puell export has changing date correspondence.",
            "Matching a following-day value on a historic raw date may leak future information.",
            "Do not shift dates or replace provider values based on this retrospective fit.",
            "Obtain original daily provider time label, timezone and release timestamp.",
            "No Production CSV, master CSV, Cycle, Streamlit or ntfy files are modified.",
        ],
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--csv", type=Path, required=True)
    parser.add_argument("--out", type=Path)
    args = parser.parse_args()
    result = report(load_archive(args.csv))
    output = json.dumps(result, indent=2, sort_keys=True, allow_nan=False)
    if args.out is not None:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(output + "\n", encoding="utf-8")
    print(output)


if __name__ == "__main__":
    main()
