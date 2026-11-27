"""Generate the calendar-enrolled hybrid DCA + adaptive reserve research artifact."""
from __future__ import annotations

from datetime import date
import json
import sys
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT))

from engines.research.v60_historical_report import load_btc_daily,fetch_usd_per_aud
from engines.research.hybrid_calendar_adaptive_dca import run_all_hybrid_cohorts,hybrid_summary_table

OUTPUT=ROOT/"research_artifacts"/"hybrid_calendar_adaptive_dca"


def main():
    btc,btc_sha,btc_end=load_btc_daily()
    fx,fx_sha=fetch_usd_per_aud(date(2016,1,1),btc.index[-1].date())
    hybrids=run_all_hybrid_cohorts(btc,fx)
    summary=hybrid_summary_table(hybrids)
    OUTPUT.mkdir(parents=True,exist_ok=True)
    hybrids.to_csv(OUTPUT/"hybrid_calendar_adaptive_cohorts.csv",index=False)
    summary.to_csv(OUTPUT/"hybrid_calendar_adaptive_summary.csv",index=False)
    metadata={
        "research_only":True,"trade_executable":False,
        "btc_source_file":"data/mvrv_z_score_2026-10-06T21-46-14.csv",
        "btc_source_sha256":btc_sha,"btc_last_observation":btc_end,
        "fx_source":"Frankfurter historical USD/AUD inverted to USD per AUD",
        "fx_payload_sha256":fx_sha,
        "cohort_entry_dates":"First Monday of each calendar quarter; full 104-week cohorts only",
        "cohort_count":int(hybrids.enrolment_date.nunique()),
        "cohorts_overlap":True,
        "base_allocation_variants_pct":[25,50,75,80,90,95,100],
        "base_leg":"Fixed weekly purchases of its original sub-budget divided by 104",
        "adaptive_leg":"Existing prospective adaptive_recovery helper on remaining original sub-budget",
        "weekly_cap_aud":25500.0,
        "capital_reference_aud":510000.0,
        "cash_budget_aud":292383.0,
        "cash_yield_annual_effective":0.05,
        "buy_friction_pct":0.3,"fixed_fee_aud":3.0,
        "shared_cap_rule":"All base/adaptive purchases within each enrolment-anchored 7-day bucket share one 5%-capital cap",
        "execution_proxy":"BTC/USD daily close converted using latest available USD-per-AUD FX; not ASX:IBIT fills",
        "limitations":["Quarterly cohorts overlap and are not independent","Archived BTC price export is not a point-in-time data vintage","Cash interest is a deterministic assumption; no SMSF tax phase modelling","Fees/friction are scenario assumptions, not historical IBIT execution costs","Adaptive signal may trigger late or never","Research-only; no live orders, signals, dashboard or portfolio edits"],
    }
    (OUTPUT/"hybrid_calendar_adaptive_metadata.json").write_text(json.dumps(metadata,indent=2,sort_keys=True)+"\n")
    print("Hybrid calendar DCA + adaptive reserve replay completed")
    print(f"BTC source SHA256: {btc_sha}")
    print(f"FX payload SHA256: {fx_sha}")
    print(f"Cohorts: {hybrids.enrolment_date.nunique()} × {hybrids.base_allocation_pct.nunique()} variants")
    print(summary.to_string(index=False))


if __name__=="__main__":
    main()
