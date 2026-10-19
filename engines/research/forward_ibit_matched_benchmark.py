"""Frozen, matched, prospective AUD/ASX:IBIT paper benchmark (NEVER an order).

Uses only TWO existing SHA256-chained forward tapes:
  1. actual prior-captured Cycle BTC market WATCH and risk fractions;
  2. separately later-captured, single-Yahoo-provider indicative IBIT.AX AUD CLOSE.
It uses no historical 2017/21 non-existent IBIT quotes, no FX proxy, no
portfolio, ntfy, tax assumption, synthetic missing prices or live broker data.

Trading at a later SAME-DAY CLOSE is an explicitly UNEXECUTABLE closing-price
proxy, not a confirmed fill or guaranteed available pre-close order price.
Frozen hypothetical policies are Cycle (exact current market percentages but
paper funded), cash-start buy/hold, and 20-week fixed cash DCA.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import math
from pathlib import Path
from zoneinfo import ZoneInfo

from engines.research.cycle_forward_signal_tape import (
    TARGET_DIR, SIGNAL_TAPE, SIGNAL_COLUMNS, _read_rows, _was_captured_prospectively,
    STRATEGY_LABEL,
)
from engines.research.ibit_asx_forward_close_tape import (
    COLUMNS as IBIT_COLUMNS, OUTPUT as IBIT_TAPE, PROVIDER as IBIT_PROVIDER,
)

SYDNEY=ZoneInfo("Australia/Sydney")
EPOCH=dt.date(2026,10,20)  # declared before this first comparable session
INITIAL_AUD=100000.00
BROKERAGE_AUD=3.00
SPREAD_BPS=25.0  # explicit research sensitivity, NOT observed broker spread
WEEKLY_DCA_WEEKS=20
STALE_MARKET_MAX_DAYS=3
MIN_SESSIONS_FOR_REVIEW=30
# Locked to the actual original prospective Cycle model code fingerprint
# in the 17/18-Oct saved market tape, BEFORE 20-Oct ASX comparison starts.
# A later Cycle model improvement must be evaluated as a NEW named cohort,
# not silently stitched into this 2026-10-20 forward experiment.
FROZEN_CYCLE_MODEL_CODE_SHA256="0143723687ff676300734a4bcc9887cdc095c74b70b958852d9448412b7f08a7"
OUTPUT=Path("artifacts/forward_ibit_matched_benchmark.json")


def _instant(value):
    t=dt.datetime.fromisoformat(value)
    if t.tzinfo is None or t.utcoffset() is None:
        raise ValueError("Market evidence has no timezone")
    return t.astimezone(dt.timezone.utc)


def _number(value,*,positive=False):
    try: f=float(value)
    except (TypeError,ValueError,OverflowError) as err:
        raise ValueError("Non-numeric historical evidence") from err
    if not math.isfinite(f) or (positive and f<=0):
        raise ValueError("Non-finite or invalid market price")
    return f


def _account():
    return {"cash":INITIAL_AUD,"units":0,"fees":0.0,
            "last_trade":None,"orders":[],"peak":INITIAL_AUD,
            "max_drawdown_pct":0.0}


def _trade(acc,*,name,date,reference_aud,side,budget_aud=None,pct=None,
           source_capture_utc=None):
    if side not in ("BUY","SELL"):
        raise ValueError("Only explicit paper BUY/SELL")
    px=reference_aud*(1+SPREAD_BPS/10000.0 if side=="BUY"
                      else 1-SPREAD_BPS/10000.0)
    if not math.isfinite(px) or px<=0:
        raise ValueError("Nonpositive sensitivity price")
    if side=="BUY":
        if pct is not None:
            budget_aud=acc["cash"]*pct/100.0
        if budget_aud is None:
            raise ValueError("Unfunded paper BUY")
        spend=min(acc["cash"],float(budget_aud))
        units=max(0,int(math.floor((spend-BROKERAGE_AUD)/px+1e-10)))
        if units<1:return False
        gross=round(units*px,2)+BROKERAGE_AUD
        if gross>acc["cash"]+0.0001:
            raise AssertionError("Overspent AUD cash in shadow paper account")
        acc["cash"]=round(acc["cash"]-gross,2)
    else:
        if pct is None:raise ValueError("Explicit partial SELL pct required")
        units=int(math.floor(acc["units"]*pct/100.0+1e-9))
        if units<=0:return False
        gross=round(units*px,2)-BROKERAGE_AUD
        if gross<=0:return False
        acc["cash"]=round(acc["cash"]+gross,2)
    acc["units"]+=units if side=="BUY" else -units
    if acc["units"]<0 or acc["cash"] < -0.001:
        raise AssertionError("Negative inventory or AUD account")
    acc["fees"]+=BROKERAGE_AUD
    acc["last_trade"]=date
    acc["orders"].append({
        "session_date_sydney":date.isoformat(),
        "paper_policy":name, "side":side,"whole_IBIT_units":units,
        "assumed_one_side_spread_bps":SPREAD_BPS,
        "hypothetical_reference_close_aud":round(reference_aud,6),
        "assumed_paper_execution_price_aud":round(px,6),
        "cash_after_aud":round(acc["cash"],2),
        "signal_capture_utc":source_capture_utc,
        "NOT_ACTUALLY_EXECUTED":True,
    })
    return True


def _mark(acc,close):
    wealth=acc["cash"]+acc["units"]*close
    acc["peak"]=max(acc["peak"],wealth)
    if acc["peak"]>0:
        acc["max_drawdown_pct"]=max(
            acc["max_drawdown_pct"],100*(acc["peak"]-wealth)/acc["peak"])
    return wealth


def grade(cycle_csv:str,ibit_csv:str,*,as_of_utc:dt.datetime):
    if not isinstance(as_of_utc,dt.datetime) or as_of_utc.tzinfo is None:
        raise ValueError("Timezone-aware research as-of required")
    now=as_of_utc.astimezone(dt.timezone.utc)
    # THESE official readers fail closed if earlier saved source row is
    # modified, reordered, or has a broken SHA256 chain.
    signals=_read_rows(cycle_csv,SIGNAL_COLUMNS,date_key="observation_date_utc")
    closes=_read_rows(ibit_csv,IBIT_COLUMNS,date_key="market_session_date_sydney")
    eligible=[]
    prospective_seen=[]
    rejected={}
    def skip(reason):
        rejected[reason]=rejected.get(reason,0)+1
    previous_signal_date=None
    for row in signals:
        day=dt.date.fromisoformat(row["observation_date_utc"])
        captured=_instant(row["captured_at_utc"])
        if captured>now:raise ValueError("Future source signal capture")
        if previous_signal_date is not None and day<=previous_signal_date:
            raise ValueError("Unordered BTC forward signal")
        previous_signal_date=day
        if day<EPOCH-dt.timedelta(days=3):
            skip("predates_paper_benchmark_enrolment")
            continue
        if not _was_captured_prospectively(row):
            skip("not_genuinely_prospective_signal")
            continue
        if (row["model_name"]!=STRATEGY_LABEL
            or row["trade_executable"]!="False"
            or row["point_in_time_onchain_risk_status"]!="NOT_VERIFIED_NOT_INCLUDED"):
            raise ValueError("BTC market signal scheme or execution claim changed")
        # Keep the REAL latest pre-open prospectively observed source row,
        # even if it fails a version/quality gate, so the replay does not
        # fall back to an older favourable accepted BUY/SELL instruction.
        prospective_seen.append({**row,"_captured":captured,"_date":day})
        if row["model_code_sha256"]!=FROZEN_CYCLE_MODEL_CODE_SHA256:
            skip("frozen_cycle_model_code_sha256_changed")
            continue
        if _number(row["source_crosscheck_max_diff_pct"])>1.:
            skip("provider_crosscheck_over_one_pct")
            continue
        if row["signal"] not in ("BUY WATCH","SELL WATCH","HOLD"):
            raise ValueError("Unknown frozen Cycle Trading market WATCH")
        buy=_number(row["buy_pct_of_remaining_available_cash"])
        sell=_number(row["sell_pct_of_current_holdings"])
        if not 0<=buy<=100 or not 0<=sell<=100:
            raise ValueError("Malformed Cycle percentage")
        if (row["signal"]=="BUY WATCH" and (buy<=0 or sell!=0)
            or row["signal"]=="SELL WATCH" and (sell<=0 or buy!=0)
            or row["signal"]=="HOLD" and (buy!=0 or sell!=0)):
            raise ValueError("Market WATCH and percentages disagree")
        eligible.append({**row,"_captured":captured,"_date":day})

    observations=[]
    previous_session=None
    for c in closes:
        day=dt.date.fromisoformat(c["market_session_date_sydney"])
        captured=_instant(c["captured_at_utc"])
        if captured>now:raise ValueError("Future ASX close capture")
        if previous_session is not None and day<=previous_session:
            raise ValueError("ASX source session chronology invalid")
        previous_session=day
        if day<EPOCH:continue
        if day.weekday()>=5:
            raise ValueError("Weekend ASX session cannot be invented")
        local=captured.astimezone(SYDNEY)
        if local.date()!=day or local.time()<dt.time(17):
            raise ValueError("Not a completed same-day ASX close capture")
        if (c["provider"]!=IBIT_PROVIDER or c["symbol"]!="ASX:IBIT"
            or c["currency"]!="AUD" or c["is_confirmed_broker_fill"]!="False"
            or c["single_provider_unverified_execution"]!="True"):
            raise ValueError("Wrong ASX instrument or fabricated broker fill")
        close=_number(c["reported_close_aud"],positive=True)
        low=_number(c["daily_low_aud"],positive=True)
        high=_number(c["daily_high_aud"],positive=True)
        if low>high or close < low-.02 or close>high+.02:
            raise ValueError("Inconsistent ASX session OHLC")
        observations.append({"date":day,"close":close,"source_hash":c["row_hash"],
                             "captured_at":captured})
    accounts={name:_account() for name in ("Cycle_live_market_watch",
             "fixed_weekly_20wk_AUD_DCA","initial_buy_and_hold")}
    first_week=EPOCH.isocalendar()
    first_week_monday=EPOCH-dt.timedelta(days=EPOCH.weekday())
    dca_weeks=set()
    used_signals=[]
    journal=[]
    source_failed_sessions=0
    exposure_observed={name:[] for name in accounts}
    for session in observations:
        day=session["date"]
        ref=session["close"]
        # Only signals KNOWN BEFORE 10:00 Sydney on execution date.
        # Quotes are completed Yahoo daily candles observed after 17:00,
        # not a fill price that was known when hypothetical decision was made.
        open_utc=dt.datetime.combine(day,dt.time(10),SYDNEY).astimezone(dt.timezone.utc)
        known=[s for s in prospective_seen if (s["_captured"]<open_utc
              and 0<=(day-s["_date"]).days<=STALE_MARKET_MAX_DAYS)]
        most_recent=max(known,key=lambda s:(s["_captured"],s["_date"])) if known else None
        allowed={s["row_hash"] for s in eligible}
        live=most_recent if most_recent and most_recent["row_hash"] in allowed else None
        if live:used_signals.append(live["row_hash"])
        cyc=accounts["Cycle_live_market_watch"]
        action="NO_FRESH_PREOPEN_SIGNAL"
        if most_recent and not live:
            # Important: never trade on an older eligible signal after
            # a newer known bad-source or changed-code record exists.
            action="LATEST_PREOPEN_SIGNAL_FAILED_QUALITY_OR_VERSION_GATE"
            source_failed_sessions+=1
        if live and (cyc["last_trade"] is None
                     or (day-cyc["last_trade"]).days>=7):
            if live["signal"]=="BUY WATCH":
                if _trade(cyc,name="Cycle_live_market_watch",date=day,
                          reference_aud=ref,side="BUY",
                          pct=_number(live["buy_pct_of_remaining_available_cash"]),
                          source_capture_utc=live["captured_at_utc"]):
                    action="PAPER_BUY"
                else:action="NOT_ENOUGH_AUD_FOR_WHOLE_UNIT"
            elif live["signal"]=="SELL WATCH":
                if _trade(cyc,name="Cycle_live_market_watch",date=day,
                          reference_aud=ref,side="SELL",
                          pct=_number(live["sell_pct_of_current_holdings"]),
                          source_capture_utc=live["captured_at_utc"]):
                    action="PAPER_SELL"
                else:action="NOT_ENOUGH_OWNED_UNITS_TO_SELL"
            else:action="HOLD"
        elif live:action="HOLD_7DAY_COOLDOWN"

        bh=accounts["initial_buy_and_hold"]
        if not bh["orders"]:
            _trade(bh,name="initial_buy_and_hold",date=day,
                   reference_aud=ref,side="BUY",budget_aud=INITIAL_AUD)
        fixed=accounts["fixed_weekly_20wk_AUD_DCA"]
        monday=day-dt.timedelta(days=day.weekday())
        week=(monday-first_week_monday).days//7
        if 0<=week<WEEKLY_DCA_WEEKS and week not in dca_weeks:
            # First actual observed weekday in week: no catch-up for gaps,
            # 5% original budget for exactly 20 predeclared calendar weeks.
            _trade(fixed,name="fixed_weekly_20wk_AUD_DCA",date=day,
                   reference_aud=ref,side="BUY",
                   budget_aud=INITIAL_AUD/WEEKLY_DCA_WEEKS)
            dca_weeks.add(week)
        marks={name:round(_mark(acc,ref),2) for name,acc in accounts.items()}
        exposure={}
        for name,acc in accounts.items():
            mark_value=acc["cash"]+acc["units"]*ref
            if mark_value<=0:
                raise AssertionError("Paper account wealth must be positive")
            invested_pct=100.0*(acc["units"]*ref)/mark_value
            if not 0<=invested_pct<=100.001:
                raise AssertionError("Impossible ETF capital exposure")
            exposure[name]=round(invested_pct,4)
            exposure_observed[name].append(invested_pct)
        journal.append({
            "session_date_sydney":day.isoformat(),
            "ASX_indicative_close_aud":round(ref,6),
            "ASX_source_hash":session["source_hash"],
            "signal_from_preopen_public_data":live["observation_date_utc"] if live else None,
            "signal_source_hash":live["row_hash"] if live else None,
            "Cycle_shadow_action":action,
            "matched_before_tax_aud_marks":marks,
            "matched_session_ETF_exposure_pct":exposure,
        })
    reports={}
    for name,acc in accounts.items():
        last=observations[-1]["close"] if observations else None
        reports[name]={
            "initial_cash_aud":INITIAL_AUD,
            "final_indicative_before_tax_mark_aud":
                round(_mark(acc,last),2) if last is not None else None,
            "cash_aud":round(acc["cash"],2),
            "IBIT_whole_units":acc["units"],
            "fee_paid_aud":round(acc["fees"],2),
            "assumed_spread_bps_one_side":SPREAD_BPS,
            "max_observed_drawdown_pct":
                round(acc["max_drawdown_pct"],4) if observations else None,
            "paper_orders_count":len(acc["orders"]),
            "mean_observed_session_ETF_exposure_pct":(
                round(sum(exposure_observed[name])/len(exposure_observed[name]),4)
                if exposure_observed[name] else None),
            "last_observed_session_ETF_exposure_pct":(
                round(exposure_observed[name][-1],4)
                if exposure_observed[name] else None),
            "observed_session_exposure_count":len(exposure_observed[name]),
            "paper_orders":acc["orders"],
        }
    enough=len(observations)>=MIN_SESSIONS_FOR_REVIEW
    return {
        "kind":"FROZEN_FORWARD_ASX_INDICATIVE_PAPER_ONLY_NOT_EXECUTABLE",
        "as_of_utc":now.isoformat(),
        "fixed_enrolment_date_sydney":EPOCH.isoformat(),
        "initial_equal_capital_aud":INITIAL_AUD,
        "explicit_one_side_spread_assumption_bps":SPREAD_BPS,
        "brokerage_assumption_per_fill_aud":BROKERAGE_AUD,
        "fund_fee_already_reflected_in_observed_ETF_price_no_extra_charge":True,
        "smsf_tax_unverified_NOT_calculated":True,
        "policy_uses_only_pre_ASX_open_prospective_Cycle_signals":True,
        "ASX_close_proxy_NOT_available_as_guaranteed_preclose_execution":True,
        "market_source_single_provider_yahoo_not_broker_quote":True,
        "frozen_cycle_model_code_sha256":FROZEN_CYCLE_MODEL_CODE_SHA256,
        "cycle_prior_dated_signals_available":len(eligible),
        "matched_sessions_latest_known_source_failed_eligibility":source_failed_sessions,
        "reported_ETF_exposure_is_not_risk_adjusted_outperformance":True,
        "cycle_excluded_signals":dict(sorted(rejected.items())),
        "verified_indicative_ASX_sessions":len(observations),
        "minimum_sessions_for_exploratory_review":MIN_SESSIONS_FOR_REVIEW,
        "sufficient_for_preliminary_exploratory_review":enough,
        "eligible_Cycle_signal_source_hashes_used":sorted(set(used_signals)),
        "policies":reports,
        "matched_sessions":journal,
        "comparative_live_strategy_winner":None,
        "after_cost_and_tax_outperformance_proven":False,
        "approved_for_model_change":False,
        "real_orders_placed":0,"portfolio_writes":0,"new_ntfy_messages":0,
    }


def main(argv=None):
    p=argparse.ArgumentParser(description="Paper-only forward ASX IBIT AUD equal-budget experiment")
    p.add_argument("--data-dir",type=Path,default=TARGET_DIR)
    p.add_argument("--output",type=Path,default=OUTPUT)
    args=p.parse_args(argv)
    cycles=(args.data_dir/SIGNAL_TAPE)
    asx=(args.data_dir/IBIT_TAPE.name)
    result=grade(cycles.read_text() if cycles.exists() else "",
                 asx.read_text() if asx.exists() else "",
                 as_of_utc=dt.datetime.now(dt.timezone.utc))
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps(result,sort_keys=True,indent=2)+"\n",encoding="utf-8")
    print(json.dumps({key:result[key] for key in (
        "fixed_enrolment_date_sydney","cycle_prior_dated_signals_available",
        "verified_indicative_ASX_sessions",
        "sufficient_for_preliminary_exploratory_review",
        "comparative_live_strategy_winner",
        "after_cost_and_tax_outperformance_proven"
    )},sort_keys=True))


if __name__=="__main__":
    main()
