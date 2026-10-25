"""Unified BTC research readiness (read-only, never a strategy or trade).

Combines verified Cycle/ASX source tapes with separately verified immutable
Kraken/Coinbase tapes and the frozen prospective scorecard. Designed for
existing GitHub forward signal workflow: no extra schedule, provider calls,
model tuning, portfolio or notification writes.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
from pathlib import Path
from zoneinfo import ZoneInfo

from engines.research.forward_market_readiness import inspect_forward_tapes
from engines.research.cycle_forward_signal_tape import (
    TARGET_DIR, SIGNAL_TAPE, OUTCOME_TAPE,
)
from engines.research.btc_spot_depth_forward import (
    OUTPUT as KRAKEN_TAPE, read_verified_tape,
)
from engines.research.coinbase_trade_samples import (
    OUTPUT as COINBASE_TAPE, read_tape,
)
from engines.research.btc_microstructure_forward_scorecard import (
    build_report as micro_forward_report,
)

SYDNEY = ZoneInfo("Australia/Sydney")
MAX_PUBLIC_SAMPLE_AGE_HOURS = 9
FRESH_DAILY_BTC_MAX_AGE_DAYS = 2
OUTPUT = Path("artifacts/btc_unified_research_readiness.json")


def _instant(value):
    x = dt.datetime.fromisoformat(value)
    if x.tzinfo is None or x.utcoffset() is None:
        raise ValueError("Unzoned original market observation")
    return x.astimezone(dt.timezone.utc)


def _freshness(now, rows):
    if not rows:
        return {"count": 0, "latest_captured_at_utc": None,
                "age_hours": None, "recent": False}
    last = _instant(rows[-1]["captured_at_utc"])
    age = (now - last).total_seconds()/3600
    if age < 0:
        raise ValueError("Future dated market capture")
    return {
        "count": len(rows),
        "latest_captured_at_utc": last.isoformat(),
        "age_hours": round(age, 3),
        "recent": age <= MAX_PUBLIC_SAMPLE_AGE_HOURS,
    }


def build_control_room(
    btc_text: str, asx_text: str, outcome_text: str,
    kraken_verified: list[dict[str,str]],
    coinbase_verified: list[dict[str,str]], *,
    as_of_utc: dt.datetime,
) -> dict:
    """Call only with source rows already verified by official tape readers.

    No model inputs or signal parameters are modified here. 'Not ready' is
    the only possible live-trading promotion status even with 1000 samples.
    """
    if (not isinstance(as_of_utc, dt.datetime)
        or as_of_utc.tzinfo is None or as_of_utc.utcoffset() is None):
        raise ValueError("Timezone-aware report instant required")
    now = as_of_utc.astimezone(dt.timezone.utc)
    cycle = inspect_forward_tapes(btc_text, asx_text, outcome_text, now=now)
    micro = micro_forward_report(
        kraken_verified, coinbase_verified, as_of_utc=now,
    )
    kraken_health = _freshness(now, kraken_verified)
    coinbase_health = _freshness(now, coinbase_verified)
    flags = []
    # The all-history peak is an immutable provenance issue. It must NOT
    # be relabeled as current source failure merely because it stays in
    # the hash-chained tape forever. Newest saved rows remain separate.
    last_five_peak = cycle["last_five_saved_BTC_source_crosscheck_max_dispersion_pct"]
    is_recent_window_good = (
        last_five_peak is not None
        and cycle["last_five_saved_BTC_sources_all_prospective"]
        and len(cycle["last_five_saved_BTC_source_dates_utc"]) == 5
        and last_five_peak < 5.0
    )
    if cycle["public_provider_dispersion_requires_review"]:
        historical_detail = (
            "The archived BTC source crosscheck exceeds 5%. Independent research traced the worst historical 6.29% mismatch to Blockchain.com midnight chart dates referring to the PRECEDING UTC close (audit 2026-10-18). This is not a current spot-price error; live parser date-alignment release remains unapproved."
        )
        if is_recent_window_good:
            historical_detail += (
                " The latest five prospectively saved BTC source diagnostics"
                f" have a maximum {last_five_peak:.4f}% disagreement,"
                " below the 5% historical review threshold."
                " This narrower sample does not certify an executable"
                " live price, but does separate the legacy audit issue"
                " from recent saved evidence."
            )
        flags.append({
            "severity": "REVIEW",
            "code": "BTC_SOURCE_MAX_DISPERSION_GE_5PCT",
            "detail": historical_detail,
        })
    btc_age = cycle["BTC_close_age_calendar_days"]
    if btc_age is None or btc_age < 0 or btc_age > FRESH_DAILY_BTC_MAX_AGE_DAYS:
        flags.append({
            "severity": "REVIEW",
            "code": "BTC_DAILY_FORWARD_CLOSE_MISSING_OR_STALE",
            "detail": "Genuine recent UTC Bitcoin forward price evidence missing; this is not a live BUY/SELL signal.",
        })
    for name, health in (("KRAKEN", kraken_health), ("COINBASE", coinbase_health)):
        if not health["recent"]:
            flags.append({
                "severity": "REVIEW", "code": name+"_PUBLIC_FEED_NOT_RECENT",
                "detail": "No valid source-stamped public observation within the last nine hours. Check the scheduled GitHub Actions collector.",
            })

    # No ASX close is expected on Sat/Sun and before Sydney 17:00.
    sydney_now = now.astimezone(SYDNEY)
    asx_expected = (sydney_now.weekday() < 5
                    and sydney_now.time() >= dt.time(17))
    if asx_expected and cycle["latest_ASX_IBIT_Sydney_date"] != sydney_now.date().isoformat():
        flags.append({
            "severity": "REVIEW",
            "code": "ASX_IBIT_SAME_DAY_REFERENCE_CLOSE_UNAVAILABLE",
            "detail": "After local Sydney 17:00, there is no same-date archived indicative ASX:IBIT AUD close; holidays and Yahoo delays are possible. Do not fabricate a broker-executable quote.",
        })

    current_pairs = micro["strict_timestamp_paired_observations"]
    scored = micro["horizon_summary"]
    scoreboard = {
        "Cycle Trading live-policy control": {
            "research_role": "ACTIVE_MARKET_WATCH_NOT_PROVEN_PRIMARY_STRATEGY",
            "forward_source_rows": cycle["total_frozen_BTC_market_snapshots"],
            "genuine_prospective_daily_rows": cycle["genuine_following_day_UTC_BTC_snapshots"],
            "verified_horizon_outcomes": cycle["recorded_forward_7_30_90d_outcomes"],
            "exact_executable_ASX_replay_proven": False,
            "after_cost_control_performance_verified": False,
        },
        "Production V5.8.2": {
            "research_role": "FROZEN_ACTIVE_REFERENCE",
            "risk_parameters_changed": False,
            "point_in_time_2017_2021_indicator_vintage_verified": False,
            "cash_funded_identical_forward_execution_proven": False,
            "after_cost_outperformance_verified": False,
        },
        "Research V5.9": {
            "research_role": "FROZEN_RESEARCH_REFERENCE",
            "risk_parameters_changed": False,
            "identical_historical_inputs_verified": False,
            "after_cost_outperformance_verified": False,
        },
        "BTC Microstructure v1": {
            "research_role": "PROSPECTIVE_OBSERVATIONAL_HYPOTHESIS_ONLY",
            "verified_kraken_book_rows": kraken_health["count"],
            "verified_coinbase_bounded_trade_samples": coinbase_health["count"],
            "strict_capture_time_paired_rows": current_pairs,
            "active_6h_price_outcomes": scored["6"]["matured_non_neutral_hypotheses"],
            "active_24h_price_outcomes": scored["24"]["matured_non_neutral_hypotheses"],
            "active_168h_price_outcomes": scored["168"]["matured_non_neutral_hypotheses"],
            "policy_sha256": micro["policy_sha256"],
            "after_cost_outperformance_verified": False,
        },
        "Buy-and-hold / fixed DCA benchmark": {
            "research_role": "REQUIRED_CONTROL_NOT_YET_HISTORICALLY_MATCHED_FOR_ASX_IBIT",
            "real_asx_broker_execution_verified": False,
            "after_cost_comparable_performance_verified": False,
        },
    }
    blockers = [
        "Live Cycle Trading remaining-position SELL and cash-gated 2.5% BUY are NOT numerically equivalent to earlier original-position historical backtests.",
        "Genuine historical ASX:IBIT bid/ask quotes, Australian market-session/holiday confirmation, and realistic broker fills are not available for a matched execution comparison.",
        "Production V5.8.2 / Research V5.9 point-in-time historical indicator vintage and live-funded execution need independent verification.",
        "Free public Kraken resting liquidity and Coinbase bounded trade samples cannot represent six-hour complete trade flow or independent agent votes.",
        "Insufficient point-in-time matured market outcomes for any investable alpha claim.",
        "SMSF fund phase, parcel-specific capital gains, FX and fee/slippage scenarios must be verified before personal after-tax comparison.",
    ]
    if flags:
        blockers.append("One or more source health/reconciliation flags remain open, including the historical Blockchain.com daily timestamp semantics where applicable.")

    return {
        "kind": "BTC_RESEARCH_DATA_HEALTH_AND_RELEASE_READINESS_NOT_INVESTMENT_ADVICE",
        "reported_at_utc": now.isoformat(),
        "model_leader_declared": False,
        "comparative_return_winner": None,
        "research_priorities": [
            "Use the confirmed Blockchain.com previous-day-close date-alignment audit to prepare and verify a versioned live-source correctness release candidate, requiring explicit approval before any Streamlit/ntfy signal-input change; never overwrite prior research records.",
            "Accumulate verified prospective ASX:IBIT quotes and BTC Cycle snapshots; investigate feed failures only when a completed eligible date was missed.",
            "Keep cash/inventory/execution parity pilot matched to the existing Streamlit decision function; no synthetic historical ASX fills.",
            "Measure frozen microstructure hypotheses only on later actual timestamps; retain neutral and missing outcomes.",
            "After enough eligible observations, compare exact-live-policy Cycle Trading, frozen Production, Research, fixed DCA and buy/hold after costs.",
        ],
        "source_health": {
            "cycle_forward": cycle,
            "btc_crosscheck_provenance": {
                "all_saved_dates_peak_pct": cycle["max_historical_BTC_source_crosscheck_dispersion_pct"],
                "latest_saved_dated_close_pct": cycle["latest_saved_BTC_source_crosscheck_dispersion_pct"],
                "latest_five_dated_closes_peak_pct": last_five_peak,
                "latest_five_dated_source_days_utc": cycle["last_five_saved_BTC_source_dates_utc"],
                "latest_five_all_prospective": cycle["last_five_saved_BTC_sources_all_prospective"],
                "latest_five_below_historical_review_threshold": is_recent_window_good,
                "all_time_historical_audit_still_open": cycle["public_provider_dispersion_requires_review"],
                "does_not_verify_live_broker_or_spot_execution": True,
            },
            "kraken": kraken_health,
            "coinbase": coinbase_health,
            "microstructure_exclusions": micro["pair_exclusion_reasons"],
            "matured_microstructure_horizons": scored,
            "asx_close_expected_from_calendar_clock": asx_expected,
            "asx_date_today_sydney": sydney_now.date().isoformat(),
        },
        "model_scoreboard": scoreboard,
        "review_flags": flags,
        "unresolved_promotion_blockers": blockers,
        "comparison_is_economically_fair": False,
        "approved_for_live_investment_use": False,
        "live_buy_sell_action": "UNCHANGED_BY_THIS_REPORT",
        "recommended_trade_aud": 0,
        "new_notifications": 0,
        "portfolio_writes": 0,
        "production_parameters_changed": False,
        "research_parameters_changed": False,
        "existing_cycle_rules_changed": False,
    }


def _read(path):
    return Path(path).read_text(encoding="utf-8") if Path(path).exists() else ""


def main(argv=None):
    parser = argparse.ArgumentParser(description="Read-only BTC unified research readiness")
    parser.add_argument("--data-dir", type=Path, default=TARGET_DIR)
    parser.add_argument("--output", type=Path, default=OUTPUT)
    args = parser.parse_args(argv)
    if not args.data_dir.is_dir():
        raise ValueError("Forward data directory unavailable")
    result = build_control_room(
        _read(args.data_dir / SIGNAL_TAPE),
        _read(args.data_dir / "asx_ibit_closes_forward.csv"),
        _read(args.data_dir / OUTCOME_TAPE),
        read_verified_tape(KRAKEN_TAPE),
        read_tape(COINBASE_TAPE),
        as_of_utc=dt.datetime.now(dt.timezone.utc),
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({
        "kind": result["kind"],
        "models": list(result["model_scoreboard"]),
        "market_source_flags": [x["code"] for x in result["review_flags"]],
        "crosscheck_all_dates_max_pct": result["source_health"]["btc_crosscheck_provenance"]["all_saved_dates_peak_pct"],
        "crosscheck_latest_five_dated_rows_max_pct": result["source_health"]["btc_crosscheck_provenance"]["latest_five_dated_closes_peak_pct"],
        "strict_microstructure_pairs": result["model_scoreboard"]["BTC Microstructure v1"]["strict_capture_time_paired_rows"],
        "live_policy_changes": False,
    }, sort_keys=True))


if __name__ == "__main__":
    main()
