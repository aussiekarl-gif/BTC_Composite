"""Run the calendar-enrolled adaptive-recovery cohort replay and save artifact CSVs."""
from __future__ import annotations

from datetime import date
import hashlib
import json
from pathlib import Path

from engines.research.v60_historical_report import load_btc_daily,fetch_usd_per_aud
from engines.research.prospective_adaptive_recovery_replay import run_all_cohorts,summary_table

ROOT=Path(__file__).resolve().parents[2]
OUTPUT=ROOT/"research_artifacts"/"prospective_adaptive_recovery_replay"


def main():
    btc,btc_sha,btc_end=load_btc_daily()
    fx_start=date(2016,1,1)
    fx,fx_sha=fetch_usd_per_aud(fx_start,btc.index[-1].date())
    cohorts=run_all_cohorts(btc,fx)
    summary=summary_table(cohorts)
    OUTPUT.mkdir(parents=True,exist_ok=True)
    cohort_path=OUTPUT/"prospective_adaptive_recovery_cohorts.csv"
    summary_path=OUTPUT/"prospective_adaptive_recovery_summary.csv"
    metadata_path=OUTPUT/"prospective_adaptive_recovery_metadata.json"
    cohorts.to_csv(cohort_path,index=False)
    summary.to_csv(summary_path,index=False)
    meta={
        "research_only":True,
        "trade_executable":False,
        "btc_source_file":"data/mvrv_z_score_2026-10-06T21-46-14.csv",
        "btc_source_sha256":btc_sha,
        "btc_last_observation":btc_end,
        "btc_source_caveat":"Archived October-2026 export, not point-in-time historical data vintages",
        "fx_source":"Frankfurter historical USD/AUD inverted to USD per AUD",
        "fx_payload_sha256":fx_sha,
        "entry_dates":"First Monday of each calendar quarter, 2017 through 2025, full 104-week cohorts only",
        "cohort_weeks":104,
        "validation_split":"train enrolment before 2022-01-01; holdout enrolment on/after 2022-01-01",
        "cohorts_overlap":True,
        "cash_budget_aud":292383.0,
        "capital_reference_aud":510000.0,
        "cash_yield_annual":0.05,
        "weekly_cap_pct_original_capital":5.0,
        "weekly_cap_aud":25500.0,
        "buy_friction_pct":0.3,
        "fixed_fee_aud":3.0,
        "policy_definitions":{
            "fixed_weekly":"Budget/104 scheduled purchases every 7 days after enrolment",
            "remaining_cash_2_5pct_below_200wma":"2.5% of remaining cash weekly only when prior BTC/USD close is below its strictly prior 200WMA",
            "adaptive_recovery":"Existing shared adaptive_recovery sizing helper; trigger strictly below prior 200WMA; weekly budget fractions 2.5%, 15%, 4.5%, or 1% of original fresh cash; 5% capital weekly hard cap",
        },
        "execution_proxy":"Daily BTC/USD close divided by latest available USD-per-AUD FX quote; not ASX:IBIT execution",
        "timing_error":"VWAP premium to cohort's full 104-week BTC/AUD daily-close low; retrospective scoring only",
        "limitations":[
            "Quarterly cohorts overlap; observations are descriptive and not independent.",
            "Archived BTC export may have retrospective revisions; no point-in-time BTC source vintages.",
            "Cash yield is a deterministic annual effective rate on remaining cash; no tax or SMSF phase modelling.",
            "0.3% purchase friction and A$3 fee are scenario assumptions, not measured historical IBIT spreads or broker fills.",
            "The adaptive policy may trigger late or never; cash remaining and trigger delay are reported.",
            "Not an ASX:IBIT ETF backtest, not live parity and not a recommendation.",
        ],
    }
    metadata_path.write_text(json.dumps(meta,indent=2,sort_keys=True)+"\n")
    print("Prospective adaptive recovery research artifact generated")
    print(f"BTC export SHA256: {btc_sha}")
    print(f"FX payload SHA256: {fx_sha}")
    print(f"Completed cohorts: {len(cohorts)//3}")
    print(summary.to_string(index=False))


if __name__=="__main__":
    main()
