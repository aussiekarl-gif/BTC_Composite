"""Read-only evidence gate for BTC accumulation research inputs.

The private audit master contains retrospective research proxies, NOT live V5.9
decision records. Report date/source coverage without implying tradable signals.
No network calls, private data upload, portfolio mutations or notifications.
"""
from __future__ import annotations

import argparse
import csv
from datetime import date, datetime, timezone
import json
import math
from pathlib import Path

REQUIRED = (
    "date", "risk_score", "risk_score_source", "btc_price_aud",
    "src__blockchain_btc_usd", "src__frankfurter_usd_per_aud",
)


def _number(value: str | None, name: str, *, maximum: float | None = None) -> float | None:
    if value is None or not value.strip():
        return None
    result = float(value)
    if not math.isfinite(result) or result <= 0 and name != "risk_score":
        raise ValueError(f"Invalid {name}")
    if name == "risk_score" and (result < 0 or result > 1):
        raise ValueError("Risk score outside [0, 1]")
    if maximum is not None and result > maximum:
        raise ValueError(f"Invalid {name}")
    return result


def _recent(day: date | None, asof: date, days: int) -> bool:
    return day is not None and 0 <= (asof - day).days <= days


def audit_file(path: Path, *, asof: date, weekly_max_age_days: int = 8,
               price_max_age_days: int = 3) -> dict:
    if not isinstance(asof, date) or weekly_max_age_days < 0 or price_max_age_days < 0:
        raise ValueError("Invalid as-of date or freshness policy")
    latest = {key: None for key in ("risk", "aud_proxy", "btc_usd_reference", "aud_fx_reference")}
    source = None
    total = 0
    risk_rows = 0
    previous = None
    with Path(path).open("r", encoding="utf-8-sig", newline="") as fh:
        reader = csv.DictReader(fh)
        absent = sorted(set(REQUIRED) - set(reader.fieldnames or ()))
        if absent:
            raise ValueError(f"Missing required archive columns: {absent}")
        for line, row in enumerate(reader, 2):
            raw_day = (row["date"] or "")[:10]
            try:
                day = date.fromisoformat(raw_day)
            except (ValueError, TypeError):
                raise ValueError(f"Invalid date at row {line}") from None
            if previous is not None and day <= previous:
                raise ValueError(f"Duplicate or unsorted archive date at row {line}")
            if day > asof:
                raise ValueError(f"Future-dated archive row at row {line}")
            previous = day
            total += 1
            score = _number(row["risk_score"], "risk_score")
            aud = _number(row["btc_price_aud"], "btc_price_aud")
            usd = _number(row["src__blockchain_btc_usd"], "src__blockchain_btc_usd")
            fx = _number(row["src__frankfurter_usd_per_aud"], "src__frankfurter_usd_per_aud")
            label = (row["risk_score_source"] or "").strip()
            if (score is None) != (aud is None) or (score is None) != (not label):
                raise ValueError(f"Incomplete historical risk/price/source row at {line}")
            if score is not None:
                risk_rows += 1
                latest["risk"] = day
                latest["aud_proxy"] = day
                source = label
            if usd is not None:
                latest["btc_usd_reference"] = day
            if fx is not None:
                latest["aud_fx_reference"] = day
    if not total:
        raise ValueError("Empty archive")
    is_fresh = _recent(latest["risk"], asof, weekly_max_age_days)
    usd_fresh = _recent(latest["btc_usd_reference"], asof, price_max_age_days)
    fx_fresh = _recent(latest["aud_fx_reference"], asof, price_max_age_days)
    reasons = []
    if not is_fresh:
        reasons.append("HISTORICAL_RISK_SNAPSHOT_STALE_OR_ABSENT")
    if source != "V5.9 Composite":
        reasons.append("RISK_SERIES_NOT_LIVE_V59_COMPOSITE")
    if not usd_fresh or not fx_fresh:
        reasons.append("MARKET_REFERENCE_STALE_OR_ABSENT")
    reasons.append("HISTORICAL_PROVIDER_VINTAGES_NOT_ATTESTED")
    reasons.append("ETF_EXECUTABLE_PRICE_AND_PORTFOLIO_PARITY_NOT_ATTESTED")
    return {
        "status": "RESEARCH_EVIDENCE_ONLY_NOT_TRADING_APPROVED",
        "asof_utc": asof.isoformat(),
        "archive_rows": total,
        "risk_rows": risk_rows,
        "risk_latest_date": latest["risk"].isoformat() if latest["risk"] else None,
        "risk_latest_source": source,
        "risk_age_days": (asof - latest["risk"]).days if latest["risk"] else None,
        "risk_weekly_fresh": is_fresh,
        "btc_usd_reference_latest_date": latest["btc_usd_reference"].isoformat() if latest["btc_usd_reference"] else None,
        "aud_fx_reference_latest_date": latest["aud_fx_reference"].isoformat() if latest["aud_fx_reference"] else None,
        "market_reference_fresh": usd_fresh and fx_fresh,
        "is_live_v59_reconstruction": False,
        "historical_point_in_time_provenance_verified": False,
        "historical_asx_ibit_executable_fills_verified": False,
        "ready_for_v59_trading_claim": False,
        "ready_to_promote_3x": False,
        "reasons": reasons,
        "note": "Recent public market reference dates do not make an older private Power Law proxy a live V5.9 score.",
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--csv", required=True, type=Path,
                        help="Local private audit-master CSV; never stored in this repository")
    parser.add_argument("--asof", type=date.fromisoformat,
                        default=datetime.now(timezone.utc).date())
    parser.add_argument("--risk-max-age-days", type=int, default=8)
    parser.add_argument("--price-max-age-days", type=int, default=3)
    args = parser.parse_args()
    report = audit_file(args.csv, asof=args.asof,
                        weekly_max_age_days=args.risk_max_age_days,
                        price_max_age_days=args.price_max_age_days)
    print(json.dumps(report, indent=2, sort_keys=True, allow_nan=False))


if __name__ == "__main__":
    main()
