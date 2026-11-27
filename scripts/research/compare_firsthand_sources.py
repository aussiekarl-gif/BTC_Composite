#!/usr/bin/env python3
"""Research-only matched-date comparison of Firsthand Bitcoin and existing source snapshots."""
import csv
import json
import math
import statistics
from datetime import date, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
FH = ROOT / "capture" / "series"
DATA = ROOT / "data" / "research" / "cowen_onchain"
CM = DATA / "coinmetrics_btc_daily_community.csv"
AE = DATA / "bitcoin_network_daily_aethereal.csv"
OUT = ROOT / "capture" / "matched_source_comparison.json"


def read_csv(path):
    with path.open(encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def to_day(value):
    return str(value)[:10] if value else None


def series(path, date_col, value_col):
    result = {}
    for row in read_csv(path):
        day = to_day(row.get(date_col))
        if not day:
            continue
        try:
            val = float(row.get(value_col, ""))
        except (ValueError, TypeError):
            continue
        if math.isfinite(val):
            result[day] = val
    return result


def rolling_mean7(values):
    out = {}
    days = sorted(values)
    for i, day in enumerate(days):
        window = days[max(0, i - 6):i + 1]
        if len(window) != 7:
            continue
        try:
            consecutive = all(
                date.fromisoformat(window[j + 1]) - date.fromisoformat(window[j]) == timedelta(days=1)
                for j in range(6)
            )
        except ValueError:
            consecutive = False
        if consecutive:
            out[day] = statistics.mean(values[d] for d in window)
    return out


def block_reward(day):
    if day >= "2024-04-20":
        return 3.125
    if day >= "2020-05-11":
        return 6.25
    if day >= "2016-07-09":
        return 12.5
    if day >= "2012-11-28":
        return 25.0
    return 50.0


def compare(label, candidate, reference, reference_name, pct_floor=1e-9):
    common = sorted(candidate.keys() & reference.keys())
    pairs = [(candidate[d], reference[d], d) for d in common]
    if not pairs:
        return {"label": label, "reference": reference_name, "n": 0}
    x, y = [p[0] for p in pairs], [p[1] for p in pairs]
    mean_x, mean_y = statistics.mean(x), statistics.mean(y)
    sx, sy = statistics.pstdev(x), statistics.pstdev(y)
    corr = None if sx == 0 or sy == 0 else sum((a-mean_x)*(b-mean_y) for a,b in zip(x,y))/(len(x)*sx*sy)
    nonzero = [(a,b,d) for a,b,d in pairs if abs(b) > pct_floor]
    ape = [abs(a-b)/abs(b)*100 for a,b,d in nonzero]
    ratios = [a/b for a,b,d in nonzero]
    top = sorted(((abs(a-b)/abs(b)*100, d, a, b) for a,b,d in nonzero), reverse=True)[:5]
    return {
        "label": label, "reference": reference_name, "n": len(pairs),
        "first_date": common[0], "last_date": common[-1],
        "correlation": corr,
        "mean_absolute_pct_error_nonzero_reference": statistics.mean(ape) if ape else None,
        "median_absolute_pct_error_nonzero_reference": statistics.median(ape) if ape else None,
        "median_candidate_reference_ratio_nonzero_reference": statistics.median(ratios) if ratios else None,
        "mean_absolute_error": statistics.mean(abs(a-b) for a,b,d in pairs),
        "mean_bias_candidate_minus_reference": statistics.mean(a-b for a,b,d in pairs),
        "zero_reference_excluded_for_pct": len(pairs)-len(nonzero),
        "worst_pct_error_dates": [{"date": d, "ape_pct": err, "candidate": a, "reference": b} for err,d,a,b in top],
    }


def main():
    firsthand = {
        "price_usd": series(FH / "btc.csv", "day", "btc"),
        "fees_btc": series(FH / "fees.csv", "day", "fees"),
        "fees7_btc": series(FH / "fees7.csv", "day", "fees7"),
        "miner_revenue_usd": series(FH / "revenue.csv", "day", "revenue"),
        "tx7": series(FH / "tx7.csv", "day", "tx7"),
        "revenue_subsidy_usd": series(FH / "revSubsidy.csv", "day", "revSubsidy"),
        "revenue_fees_usd": series(FH / "revFees.csv", "day", "revFees"),
        "blocks_day": series(FH / "blocksDay.csv", "day", "blocksDay"),
    }
    coinmetrics = {
        "price_usd": series(CM, "date_utc", "PriceUSD"),
        "fees_btc": series(CM, "date_utc", "FeeTotNtv"),
    }
    cm_total_revenue = {}
    for row in read_csv(CM):
        day = to_day(row.get("date_utc"))
        try:
            total = float(row["IssTotUSD"]) + float(row["FeeTotNtv"]) * float(row["PriceUSD"])
            if day and math.isfinite(total):
                cm_total_revenue[day] = total
        except (ValueError, TypeError, KeyError):
            continue
    aethereal = {
        "price_usd": series(AE, "date_utc", "price_usd"),
        "fees_btc": series(AE, "date_utc", "fees_btc"),
        "miner_revenue_usd": series(AE, "date_utc", "miners_revenue_usd"),
        "transactions": series(AE, "date_utc", "transactions"),
    }
    fh_fee_usd_expected_from_raw = {
        d: firsthand["fees_btc"][d] * firsthand["price_usd"][d]
        for d in firsthand["fees_btc"].keys() & firsthand["price_usd"].keys()
    }
    fh_fee_usd_expected_from_7d = {
        d: firsthand["fees7_btc"][d] * firsthand["price_usd"][d]
        for d in firsthand["fees7_btc"].keys() & firsthand["price_usd"].keys()
    }
    revenue_component_sum = {
        d: firsthand["revenue_subsidy_usd"][d] + firsthand["revenue_fees_usd"][d]
        for d in firsthand["revenue_subsidy_usd"].keys() & firsthand["revenue_fees_usd"].keys()
    }
    subsidy_expected_from_blocks = {
        d: firsthand["blocks_day"][d] * block_reward(d) * firsthand["price_usd"][d]
        for d in firsthand["blocks_day"].keys() & firsthand["price_usd"].keys()
    }
    comparisons = [
        compare("Firsthand BTC price vs Coin Metrics PriceUSD", firsthand["price_usd"], coinmetrics["price_usd"], "Coin Metrics Community"),
        compare("Firsthand BTC price vs Aethereal price_usd", firsthand["price_usd"], aethereal["price_usd"], "Aethereal snapshot"),
        compare("Firsthand fees BTC vs Coin Metrics FeeTotNtv", firsthand["fees_btc"], coinmetrics["fees_btc"], "Coin Metrics Community"),
        compare("Firsthand fees BTC vs Aethereal fees_btc", firsthand["fees_btc"], aethereal["fees_btc"], "Aethereal snapshot"),
        compare("Firsthand fees7 vs trailing 7-day mean of Firsthand daily fees", firsthand["fees7_btc"], rolling_mean7(firsthand["fees_btc"]), "Firsthand daily-fee series"),
        compare("Firsthand miner revenue vs Aethereal miners_revenue_usd", firsthand["miner_revenue_usd"], aethereal["miner_revenue_usd"], "Aethereal snapshot"),
        compare("Firsthand miner revenue vs Coin Metrics derived total revenue", firsthand["miner_revenue_usd"], cm_total_revenue, "Coin Metrics derived estimate"),
        compare("Firsthand miner revenue vs its subsidy + fees components", firsthand["miner_revenue_usd"], revenue_component_sum, "Firsthand component sum"),
        compare("Firsthand USD fees vs raw BTC fees x price", firsthand["revenue_fees_usd"], fh_fee_usd_expected_from_raw, "Firsthand raw-fee conversion"),
        compare("Firsthand USD fees vs fees7 x price", firsthand["revenue_fees_usd"], fh_fee_usd_expected_from_7d, "Firsthand 7-day fee conversion"),
        compare("Firsthand subsidy USD vs blocksDay x halving reward x price", firsthand["revenue_subsidy_usd"], subsidy_expected_from_blocks, "Firsthand block-count calculation"),
        compare("Firsthand tx7 vs Aethereal transactions (raw)", firsthand["tx7"], aethereal["transactions"], "Aethereal snapshot"),
        compare("Firsthand tx7 vs Aethereal transactions (trailing 7-day mean)", firsthand["tx7"], rolling_mean7(aethereal["transactions"]), "Aethereal trailing 7-day mean"),
    ]
    source_coverage = {
        name: {"n": len(values), "first_date": min(values) if values else None, "last_date": max(values) if values else None}
        for name, values in {
            **firsthand,
            "Coin Metrics PriceUSD": coinmetrics["price_usd"],
            "Coin Metrics FeeTotNtv": coinmetrics["fees_btc"],
            "Coin Metrics derived total revenue": cm_total_revenue,
            **{f"Aethereal {k}": v for k, v in aethereal.items()},
        }.items()
    }
    block_counts = list(firsthand["blocks_day"].values())
    block_stats = {
        "n": len(block_counts),
        "mean": statistics.mean(block_counts) if block_counts else None,
        "median": statistics.median(block_counts) if block_counts else None,
        "min": min(block_counts) if block_counts else None,
        "max": max(block_counts) if block_counts else None,
        "counts_of_common_values": {str(k): block_counts.count(k) for k in sorted(set(block_counts))[:25]},
        "fraction_100_to_180_blocks": sum(100 <= n <= 180 for n in block_counts) / len(block_counts) if block_counts else None,
    }
    period_comparisons = []
    periods = (("2013-01-01", "2016-12-31"), ("2017-01-01", "2020-12-31"), ("2021-01-01", "2023-12-31"), ("2024-01-01", "2026-12-31"))
    period_pairs = (
        ("Firsthand miner revenue vs Aethereal", firsthand["miner_revenue_usd"], aethereal["miner_revenue_usd"], "Aethereal snapshot"),
        ("Firsthand miner revenue vs Coin Metrics derived", firsthand["miner_revenue_usd"], cm_total_revenue, "Coin Metrics derived estimate"),
        ("Firsthand fees vs Coin Metrics", firsthand["fees_btc"], coinmetrics["fees_btc"], "Coin Metrics Community"),
    )
    for label, candidate, reference, reference_name in period_pairs:
        for start, end in periods:
            c_period = {d:v for d,v in candidate.items() if start <= d <= end}
            r_period = {d:v for d,v in reference.items() if start <= d <= end}
            period_comparisons.append(compare(f"{label} ({start[:4]}-{end[:4]})", c_period, r_period, reference_name))
    report = {
        "purpose": "Research-only matched-date source comparison; no strategy/data-source changes.",
        "generated_utc_date": date.today().isoformat(),
        "coverage": source_coverage,
        "blocks_day_summary": block_stats,
        "comparisons": comparisons,
        "period_comparisons": period_comparisons,
        "interpretation_notes": [
            "MAPE and median APE exclude reference values equal to zero; exclusions are counted.",
            "Daily date matching uses the first 10 characters of the date field.",
            "Correlation and percentage errors are descriptive, not proof of identical definitions or source quality.",
            "The tx7-vs-rolling-mean comparison is diagnostic; no metric semantics are assumed.",
            "Coin Metrics derived total miner revenue is IssTotUSD plus native fees multiplied by daily PriceUSD; it is a derived cross-check, not a published total-revenue field.",
            "Firsthand revenue-component, block-subsidy, and fee-conversion checks are arithmetic consistency tests, not independent-source validation.",
            "The 7-day rolling checks require seven consecutive calendar dates.",
        ],
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(report, indent=2), encoding="utf-8")
    for c in comparisons + period_comparisons:
        print(json.dumps(c, sort_keys=True))
    print("Blocks/day summary:", json.dumps(block_stats, sort_keys=True))
    print("Report written:", OUT)
    for c in comparisons:
        if c["n"] < 1000:
            raise SystemExit(f"Insufficient overlap for comparison {c['label']}: {c['n']} days")

if __name__ == "__main__":
    main()
