"""Rebuild the V5.9 Power Law floor audit from the same public BTC history as DCA Today.

Research-only. No portfolio, order, notification, or live sizing writes.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

from engines.research import research_model as model


def main() -> None:
    now = datetime.now(timezone.utc)
    btc = model.fetch_btc_history(model.RESEARCH_PL_HISTORY_START.to_pydatetime(), now)
    if btc is None or btc.empty:
        raise RuntimeError("Blockchain.com BTC history unavailable; refusing to publish an empty audit")

    frame = model.merge_bgeometrics(btc.copy(), pd.DataFrame())
    params = {
        "risk_model": "Research WF Power Law",
        "legacy_linear_pl_cheap": model.DEFAULT_PL_CHEAP,
        "pl_expensive": model.DEFAULT_PL_EXPENSIVE,
        "active_risk_mapping": "Tail-stretched Research",
        "active_zero_risk_residual_threshold": model.RESEARCH_TAIL_RISK_KNOTS[0][0],
        "research_pl_min_weeks": model.RESEARCH_PL_MIN_WEEKS,
        "research_pl_refit_days": model.RESEARCH_PL_REFIT_DAYS,
    }
    scored = model.add_risk_indicators(frame, "Research WF Power Law", params)

    # Match DCA Today: exclude the still-open UTC date and use completed W-MON buckets.
    closed_cutoff = pd.Timestamp(now.date(), tz="UTC")
    index_utc = pd.to_datetime(scored.index, utc=True)
    closed = scored.loc[index_utc < closed_cutoff].copy()
    valid_risk = closed.dropna(subset=["risk_score", "price"])
    if valid_risk.empty:
        raise RuntimeError("No completed daily V5.9 risk observations")
    as_of = valid_risk.index[-1]
    weekly_risk = model.completed_weekly_last(valid_risk["risk_score"], as_of=as_of)
    weekly_residual = model.completed_weekly_last(
        closed["power_law_residual"].dropna(), as_of=as_of
    )
    audit = model.power_law_floor_diagnostics(
        weekly_risk, weekly_residual
    )
    distribution = model.risk_occurrence_table(weekly_risk)
    weekly_price = model.completed_weekly_last(valid_risk["price"], as_of=as_of)
    weekly_fair = model.completed_weekly_last(valid_risk["fair_value"], as_of=as_of)
    weekly_frame = pd.concat(
        [
            weekly_residual.rename("residual"),
            weekly_price.rename("price_usd"),
            weekly_fair.rename("fair_value_usd"),
        ],
        axis=1,
    ).dropna(subset=["residual"])

    def cycle_for(ts: pd.Timestamp) -> str:
        if ts < pd.Timestamp("2016-07-09", tz="UTC"):
            return "Pre-2016 halving (partial history)"
        if ts < pd.Timestamp("2020-05-11", tz="UTC"):
            return "2016–2020 cycle"
        if ts < pd.Timestamp("2024-04-20", tz="UTC"):
            return "2020–2024 cycle"
        return "2024–current cycle"

    def threshold_episodes(cutoff: float) -> list[dict]:
        hit_dates = weekly_frame.index[weekly_frame["residual"] <= cutoff]
        groups: list[list[pd.Timestamp]] = []
        current: list[pd.Timestamp] = []
        for ts in hit_dates:
            if current and (ts - current[-1]).days > 7:
                groups.append(current)
                current = []
            current.append(ts)
        if current:
            groups.append(current)

        episodes = []
        for dates in groups:
            segment = weekly_frame.loc[dates]
            minimum_date = segment["residual"].idxmin()
            minimum = segment.loc[minimum_date]
            fair = float(minimum["fair_value_usd"])
            price = float(minimum["price_usd"])
            episodes.append({
                "cycle": cycle_for(dates[0]),
                "start_week_utc": dates[0].isoformat(),
                "end_week_utc": dates[-1].isoformat(),
                "weeks": len(dates),
                "minimum_residual": float(minimum["residual"]),
                "minimum_week_utc": minimum_date.isoformat(),
                "btc_price_at_minimum_usd": price,
                "power_law_fair_value_at_minimum_usd": fair,
                "price_as_pct_of_fair_value_at_minimum": (
                    100.0 * price / fair if fair > 0 else None
                ),
            })
        return episodes

    episode_cutoffs = (-0.20, -0.25, -0.30, -0.35, -0.40)
    episodes = {
        f"{cutoff:.2f}": threshold_episodes(cutoff)
        for cutoff in episode_cutoffs
    }

    # Re-map the exact same causal residual series under candidate cheap floors.
    # This is a legacy linear-floor sensitivity study only. Active Research
    # risk uses the tail-stretched mapping and its separate zero-risk boundary.
    candidate_cheap_floors = tuple(round(-0.20 - 0.01 * i, 2) for i in range(21))
    candidate_sweep = []
    for cheap in candidate_cheap_floors:
        candidate_score = (
            (weekly_frame["residual"] - cheap)
            / (model.DEFAULT_PL_EXPENSIVE - cheap)
        ).clip(0.0, 1.0)
        candidate_distribution = model.risk_occurrence_table(candidate_score)
        def candidate_count(label: str) -> int:
            return int(candidate_distribution.loc[
                candidate_distribution["Risk range"] == label, "Weeks"
            ].sum())
        by_cycle = {}
        for cycle in (
            "Pre-2016 halving (partial history)",
            "2016–2020 cycle",
            "2020–2024 cycle",
            "2024–current cycle",
        ):
            cycle_mask = pd.Series(
                [cycle_for(ts) == cycle for ts in weekly_frame.index],
                index=weekly_frame.index,
            )
            cycle_score = candidate_score.loc[cycle_mask]
            cycle_dist = model.risk_occurrence_table(cycle_score)
            by_cycle[cycle] = int(cycle_dist.loc[
                cycle_dist["Risk range"] == "0.00–0.01", "Weeks"
            ].sum())
        candidate_sweep.append({
            "candidate_pl_cheap": cheap,
            "zero_score_weeks": int(candidate_score.eq(0.0).sum()),
            "lowest_bucket_weeks": candidate_count("0.00–0.01"),
            "lowest_bucket_percent": (
                100.0 * candidate_count("0.00–0.01") / len(candidate_score)
                if len(candidate_score) else 0.0
            ),
            "second_bucket_weeks": candidate_count("0.01–0.02"),
            "second_bucket_percent": (
                100.0 * candidate_count("0.01–0.02") / len(candidate_score)
                if len(candidate_score) else 0.0
            ),
            "by_cycle_lowest_bucket_weeks": by_cycle,
        })

    bottom_anchors = [
        {"label": "2015 bear-market low", "date": "2015-01-14", "type": "cycle bottom"},
        {"label": "2018 bear-market low", "date": "2018-12-15", "type": "cycle bottom"},
        {"label": "2020 COVID crash low", "date": "2020-03-13", "type": "external shock"},
        {"label": "2022 bear-market low", "date": "2022-11-21", "type": "cycle bottom"},
        {"label": "2026 user-supplied cycle low", "date": "2026-06-30", "type": "user-supplied anchor"},
    ]
    bottom_capture = []
    for anchor in bottom_anchors:
        target = pd.Timestamp(anchor["date"], tz="UTC")
        nearest = min(weekly_frame.index, key=lambda ts: abs(ts - target))
        row = weekly_frame.loc[nearest]
        fair = float(row["fair_value_usd"])
        price = float(row["price_usd"])
        bottom_capture.append({
            **anchor,
            "nearest_completed_week_utc": nearest.isoformat(),
            "distance_days": int(abs((nearest - target).days)),
            "residual": float(row["residual"]),
            "btc_price_usd": price,
            "power_law_fair_value_usd": fair,
            "price_as_pct_of_fair_value": 100.0 * price / fair if fair > 0 else None,
            "captured_by_cutoff": {
                f"{cutoff:.2f}": bool(row["residual"] <= cutoff)
                for cutoff in candidate_cheap_floors
            },
        })

    def bucket(label: str) -> dict:
        row = distribution.loc[distribution["Risk range"] == label]
        return {
            "weeks": int(row["Weeks"].sum()),
            "percent": float(row["Percent"].sum()),
        }

    result = {
        "status": "RESEARCH_ONLY_FULL_PUBLIC_HISTORY_REPLAY",
        "generated_at_utc": now.isoformat(),
        "last_closed_daily_observation_utc": pd.Timestamp(as_of).isoformat(),
        "last_completed_weekly_observation_utc": pd.Timestamp(weekly_risk.index[-1]).isoformat(),
        "source": "Blockchain.com public BTC/USD daily market-price history",
        "model": "V5.9 Research WF Power Law",
        "history_start": str(model.RESEARCH_PL_HISTORY_START),
        "pl_cheap": model.DEFAULT_PL_CHEAP,
        "pl_expensive": model.DEFAULT_PL_EXPENSIVE,
        "weekly_observations": int(len(weekly_risk)),
        "risk_distribution": distribution.to_dict(orient="records"),
        "power_law_floor_by_cycle": audit.to_dict(orient="records"),
        "threshold_episodes": episodes,
        "candidate_cheap_floor_sweep": candidate_sweep,
        "historical_bottom_capture": bottom_capture,
        "threshold_episode_summary": {
            f"{cutoff:.2f}": {
                "episodes": len(episodes[f"{cutoff:.2f}"]),
                "weeks": sum(item["weeks"] for item in episodes[f"{cutoff:.2f}"]),
                "by_cycle": {
                    cycle: sum(1 for item in episodes[f"{cutoff:.2f}"] if item["cycle"] == cycle)
                    for cycle in (
                        "Pre-2016 halving (partial history)",
                        "2016–2020 cycle",
                        "2020–2024 cycle",
                        "2024–current cycle",
                    )
                },
            }
            for cutoff in episode_cutoffs
        },
        "zero_bucket": bucket("0.00–0.01"),
        "second_lowest_bucket": bucket("0.01–0.02"),
        "safety": {
            "changes_live_model": False,
            "changes_dca_sizing": False,
            "changes_production": False,
            "portfolio_or_order_writes": False,
            "notifications_sent": False,
        },
    }
    output = Path("artifacts/v59_power_law_floor_full_history.json")
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, indent=2, default=str) + "\n", encoding="utf-8")
    print(json.dumps(result, indent=2, default=str))


if __name__ == "__main__":
    main()
