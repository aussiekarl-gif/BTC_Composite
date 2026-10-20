"""Read-only acceptance report for the FIRST genuine Oct-2026 ASX:IBIT session.

This reads original immutable BTC Cycle forward evidence and the ASX
single-provider AUD daily-close tape, then calls the frozen three-policy
matched-capital paper ledger WITHOUT refitting/altering any strategy.
All first-session paper positions must reconcile to existing marked
account values. Real broker fills, tax, alpha and actual notification
delivery are NOT demonstrated by this output.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
from pathlib import Path

from engines.research.cycle_forward_signal_tape import (
    TARGET_DIR, SIGNAL_TAPE, SIGNAL_COLUMNS, _read_rows,
)
from engines.research.ibit_asx_forward_close_tape import OUTPUT as ASX_TAPE
from engines.research.forward_ibit_matched_benchmark import (
    EPOCH, INITIAL_AUD, BROKERAGE_AUD, SPREAD_BPS, SYDNEY, grade, _instant,
)

OUTPUT=Path("artifacts/forward_ibit_first_actual_session.json")


def first_actual_session(cycle_csv:str,asx_csv:str,*,as_of_utc:dt.datetime)->dict:
    graded=grade(cycle_csv,asx_csv,as_of_utc=as_of_utc)
    if not graded["matched_sessions"]:
        return {
            "kind":"FIRST_ASX_IBIT_FORWARD_PAPER_SESSION_NO_ELIGIBLE_SESSION_YET",
            "enrolment_sydney":EPOCH.isoformat(),
            "eligible_first_session_found":False,
            "three_way_performance_winner":None,
            "real_orders":0,"portfolio_writes":0,"ntfy_sent":0,
        }
    session=graded["matched_sessions"][0]
    day=dt.date.fromisoformat(session["session_date_sydney"])
    if day<EPOCH:raise AssertionError("Pre-enrolment ASX session was fabricated")
    ref=float(session["ASX_indicative_close_aud"])
    if ref<=0:raise AssertionError("Not a valid positive observed AUD daily close")
    open_at=dt.datetime.combine(day,dt.time(10),SYDNEY).astimezone(dt.timezone.utc)
    cycle_row=None
    if session["signal_source_hash"] is not None:
        evidence=_read_rows(cycle_csv,SIGNAL_COLUMNS,date_key="observation_date_utc")
        matching=[r for r in evidence if r["row_hash"]==session["signal_source_hash"]]
        if len(matching)!=1:raise ValueError("Frozen Cycle preopen evidence not uniquely found")
        cycle_row=matching[0]
        if _instant(cycle_row["captured_at_utc"])>=open_at:
            raise AssertionError("After-ASX-open market WATCH used in first session")
        if cycle_row["signal"] not in ("HOLD","BUY WATCH","SELL WATCH"):
            raise ValueError("Unsupported Cycle first-session WATCH")
        if cycle_row["observation_date_utc"]!=session["signal_from_preopen_public_data"]:
            raise AssertionError("Preopen source date not conserved")
    else:
        if session["signal_from_preopen_public_data"] is not None:
            raise AssertionError("Missing source hash falsely used for market decision")

    policy_rows={}
    for name,policy in graded["policies"].items():
        fills=[o for o in policy["paper_orders"] if o["session_date_sydney"]==day.isoformat()]
        if len(fills)>1:
            raise AssertionError("More than one paper fill on first ASX session")
        if fills:
            fill=fills[0]
            units=int(fill["whole_IBIT_units"])*(1 if fill["side"]=="BUY" else -1)
            if units<0:raise AssertionError("No owned ETF shares before first ASX session")
            cash=round(float(fill["cash_after_aud"]),2)
            if fill["NOT_ACTUALLY_EXECUTED"] is not True:
                raise ValueError("First ASX paper fill misrepresented as real order")
            if fill["source_capture_utc"] is not None and _instant(fill["source_capture_utc"])>=open_at:
                raise AssertionError("Forward BUY or SELL used after-open source")
        else:
            units=0
            cash=INITIAL_AUD
        marked=round(cash+units*ref,2)
        ledger_mark=session["matched_before_tax_aud_marks"][name]
        if abs(marked-ledger_mark)>.011:
            raise AssertionError("First-session account does not reconcile to frozen matched ledger")
        pct=round(100*units*ref/marked,4)
        policy_rows[name]={
            "original_hypothetical_AUD":INITIAL_AUD,
            "actual_paper_fills_on_first_session":len(fills),
            "research_only_whole_ASX_IBIT_units":units,
            "paper_AUD_cash_remaining":cash,
            "single_provider_indicative_mark_at_close_AUD":marked,
            "ETF_account_exposure_at_first_session_pct":pct,
            "first_session_assumed_broker_fees_AUD":len(fills)*BROKERAGE_AUD,
            "first_session_assumed_one_sided_spread_bps":SPREAD_BPS,
            "NOT_ACTUALLY_TRADED":True,
        }
    if set(policy_rows)!={"Cycle_live_market_watch",
                          "fixed_weekly_20wk_AUD_DCA","initial_buy_and_hold"}:
        raise AssertionError("Preregistered three-policy cohort changed")
    return {
        "kind":"FIRST_GENUINE_ASX_IBIT_AUD_FORWARD_SESSION_READ_ONLY_PAPER_RECONCILIATION",
        "enrolment_sydney":EPOCH.isoformat(),
        "eligible_first_session_found":True,
        "first_session_sydney":day.isoformat(),
        "ASX_close_single_provider_indicative_AUD":ref,
        "ASX_source_sha256_chain_row_hash":session["ASX_source_hash"],
        "ASX_open_sydney_10am_utc":open_at.isoformat(),
        "first_Cycle_action":session["Cycle_shadow_action"],
        "Cycle_market_signal_available_pre_ASX_open":cycle_row is not None,
        "Cycle_source_market_watch_if_valid":cycle_row["signal"] if cycle_row else None,
        "Cycle_source_observed_completed_close_utc":(
            cycle_row["observation_date_utc"] if cycle_row else None),
        "Cycle_source_actual_capture_utc":(
            cycle_row["captured_at_utc"] if cycle_row else None),
        "Cycle_source_sha256_row_hash":cycle_row["row_hash"] if cycle_row else None,
        "separate_mid_session_signal_not_required_for_preopen_benchmark":True,
        "ETF_daily_close_not_an_executable_order_at_10am":True,
        "fees_and_spread_are_assumptions_not_proven_broker_execution":True,
        "cash_account_comparison_not_yet_aftertax_or_risk_adjusted":True,
        "minimum_30_completed_sessions_for_exploratory_review":30,
        "first_session_can_prove_strategy_winner":False,
        "three_way_performance_winner":None,
        "policies":policy_rows,
        "real_orders":0,"portfolio_writes":0,"ntfy_sent":0,
    }


def main(argv=None):
    p=argparse.ArgumentParser(description="Reconcile first prospective matched ASX session (paper only)")
    p.add_argument("--data-dir",type=Path,default=TARGET_DIR)
    p.add_argument("--output",type=Path,default=OUTPUT)
    args=p.parse_args(argv)
    prices=args.data_dir/SIGNAL_TAPE
    asx=args.data_dir/ASX_TAPE.name
    result=first_actual_session(
        prices.read_text(encoding="utf-8") if prices.exists() else "",
        asx.read_text(encoding="utf-8") if asx.exists() else "",
        as_of_utc=dt.datetime.now(dt.timezone.utc),
    )
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps(result,sort_keys=True,indent=2)+"\n",encoding="utf-8")
    print(json.dumps(result,sort_keys=True))


if __name__=="__main__":
    main()
