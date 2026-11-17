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
        "pl_cheap": model.DEFAULT_PL_CHEAP,
        "pl_expensive": model.DEFAULT_PL_EXPENSIVE,
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
        weekly_risk, weekly_residual, cheap_threshold=model.DEFAULT_PL_CHEAP
    )
    distribution = model.risk_occurrence_table(weekly_risk)

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
