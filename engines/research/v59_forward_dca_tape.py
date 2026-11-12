"""Append-only, research-only *prospective* V5.9 / 200WMA daily evidence.

Capture runs after UTC daily close, records as-published model inputs, refuses
revisions and missing/fallback signals, and grades only subsequently captured
market closes. Paper entries are only scored after a NEXT Monday observation.
No live trades, portfolio or notification writes.
"""
from __future__ import annotations
import argparse
from datetime import date, datetime, timedelta, timezone
import json
import math
from pathlib import Path
from typing import Any

from engines.research.v59_dynamic_risk_policy import risk_buy_multiplier
from engines.research.v59_live_signal_snapshot import capture

CAPITAL = 510_000.
INITIAL_BTC_FRACTION = .41
CASH_YIELD = .05
ETF_DRAG = .0025
FRICTION = .003
FIXED_FEE = 3.
WEEKLY_CAP = .05*CAPITAL
ILLUSTRATIVE_REVIEW = date(2027,12,31)
HORIZONS=(7,28,84)
REQUIRED_SNAPSHOT_STATUS="RESEARCH_SIGNAL_SNAPSHOT_READY"
GATES=("risk_1x","risk_3x","risk_3x_risk_le_020","below_200wma","below_to_plus10")
DATA_VERSION=1


def to_observation(s:dict, code_sha:str="") -> dict:
    """Never replace actual observed risk with recomputed history."""
    if s.get("status") != REQUIRED_SNAPSHOT_STATUS or not s.get("risk_and_fx_fresh"):
        raise ValueError("Invalid or stale prospective snapshot; no paper trade")
    observed=datetime.fromisoformat(s["captured_at_utc"].replace("Z","+00:00"))
    signal=datetime.fromisoformat(s["closed_risk_observation_utc"].replace("Z","+00:00"))
    if observed.tzinfo is None or signal.tzinfo is None:
        raise ValueError("Must have timezone-aware snapshot timestamps")
    observed=observed.astimezone(timezone.utc)
    signal=signal.astimezone(timezone.utc)
    if signal >= observed or signal.date()>=observed.date():
        raise ValueError("Only closed daily market observations allowed")
    if s.get("risk_score_source")!="Walk-forward Power Law":
        raise ValueError("Cannot publish neutral risk fallback")
    risk=float(s["r2_sizing_risk"])
    price=float(s["btc_usd_closed_price"])
    fx=float(s["usd_per_aud"])
    wma=float(s["btc_usd_200wma_last_completed_sunday"])
    ratio=float(s["daily_closed_btc_usd_to_last_completed_200wma_ratio"])
    week=date.fromisoformat(s["btc_usd_200wma_week_ending_utc"])
    fx_date=date.fromisoformat(s["fx_observation_date_utc"])
    if not (0<=risk<=1 and all(math.isfinite(x) and x>0
            for x in (price,fx,wma,ratio))):
        raise ValueError("Incomplete or nonsensical market/risk input")
    if not (week<=signal.date() and week.weekday()==6 and
            (signal.date()-week).days<=6 and
            fx_date<=signal.date() and (signal.date()-fx_date).days<=5):
        raise ValueError("200WMA week and FX fixing must precede observation")
    if abs(price/wma-ratio) > 1e-6:
        raise ValueError("Inconsistent WMA ratio")
    if not s.get("fingerprint"):
        raise ValueError("Expected stable model-input fingerprint")
    return {
        "schema":DATA_VERSION,"signal_date":signal.date().isoformat(),
        "captured_at_utc":observed.isoformat(),
        "btc_usd":price,"usd_per_aud":fx,"fx_fix_date":fx_date.isoformat(),
        "btc_usd_200wma":wma,
        "btc_usd_to_200wma":ratio,"wma_week_ending":week.isoformat(),
        "risk":risk,"model_fingerprint":str(s["fingerprint"]),
        "risk_model":s["risk_model"],"risk_source":s["risk_score_source"],
        "price_source":s["risk_provider"],"fx_source":s["fx_provider"],
        "code_commit_sha":code_sha or "UNKNOWN_NOT_ATTESTED",
        "asx_ibit_trade_executable":False,"actual_broker_holdings_verified":False,
        "paper_only":True
    }


def read_tape(path:Path) -> list[dict]:
    if not path.exists():
        return []
    rows=[]
    for line in path.read_text().splitlines():
        if line.strip():
            rows.append(json.loads(line))
    validate_tape(rows)
    return rows


def validate_tape(rows:list[dict]) -> None:
    previous=None
    for r in rows:
        if r.get("schema")!=DATA_VERSION or not r.get("paper_only"):
            raise ValueError("Corrupt/untrusted forward tape version")
        d=date.fromisoformat(r["signal_date"])
        ts=datetime.fromisoformat(r["captured_at_utc"])
        if ts.tzinfo is None or ts.date()<=d:
            raise ValueError("Backdated or unzoned forward capture")
        if previous is not None and d<=previous:
            raise ValueError("Tape must be strictly append-only increasing days")
        if r.get("risk_source")!="Walk-forward Power Law" or r.get("asx_ibit_trade_executable") is not False:
            raise ValueError("Unattested prospective tape row")
        previous=d


def add_observation(rows:list[dict],new:dict) -> tuple[list[dict],bool]:
    validate_tape(rows)
    validate_tape([new])
    if rows:
        old_date=date.fromisoformat(rows[-1]["signal_date"])
        new_date=date.fromisoformat(new["signal_date"])
        if new_date==old_date:
            # Keep the FIRST as-published row, never secretly replace it with
            # a revised feed value or refitted model within the same UTC day.
            return rows,False
        if new_date<old_date:
            raise ValueError("New data is older than immutable tape; no backfill")
        if new_date>old_date+timedelta(days=1):
            # Real gaps are allowed but *never* filled with retrospective prices.
            pass
    return rows+[new],True


def multipliers(row:dict) -> dict:
    risk=float(row["risk"])
    ratio=float(row["btc_usd_to_200wma"])
    if not (math.isfinite(risk) and 0<=risk<=1 and
            math.isfinite(ratio) and ratio>0):
        raise ValueError("Invalid point-in-time policy input")
    aggressive=risk_buy_multiplier(risk)
    return {
        "risk_1x":min(1.,aggressive),
        "risk_3x":aggressive,
        "risk_3x_risk_le_020":aggressive if risk<=.20 else 0.,
        "below_200wma":aggressive if ratio<=1. else 0.,
        "below_to_plus10":aggressive if ratio<=1.10 else 0.,
    }


def matured_returns(rows:list[dict]) -> dict:
    """Only PREVIOUSLY saved future day references; no history refetch."""
    lookup={date.fromisoformat(x["signal_date"]):x for x in rows}
    result={}
    for horizon in HORIZONS:
        scores={name:[] for name in GATES}
        reference_count=0
        for r in rows:
            d=date.fromisoformat(r["signal_date"])
            future=lookup.get(d+timedelta(days=horizon))
            if future is None:continue
            # Use independently captured future AUD FX. This is a reference
            # BTC/AUD return, not an ASX ETF or broker execution return.
            original=float(r["btc_usd"])/float(r["usd_per_aud"])
            after=float(future["btc_usd"])/float(future["usd_per_aud"])
            cash_pct=100*((1+CASH_YIELD)**(horizon/365.25)-1)
            excess=100*(after/original-1)-cash_pct
            reference_count+=1
            for name,weight in multipliers(r).items():
                if weight>0:scores[name].append(excess)
        result[str(horizon)+"d"]={
            "observed_exact_horizon_pairs":reference_count,
            "btc_aud_excess_over_5pct_cash_on_signals_pct":{
                name:{"count":len(z),"mean_pct":sum(z)/len(z) if z else None}
                for name,z in scores.items()
            }
        }
    return result


def paper_portfolios(rows:list[dict]) -> dict:
    """Forward-only *Sunday signal then Monday proxy fill*, no actual orders.

    Missing a captured Sunday/Monday => no assumed fill. First matched
    Monday marks existing ~41% holdings, not a reconstructed Stake entry.
    """
    by_day={date.fromisoformat(r["signal_date"]):r for r in rows}
    pairs=[]
    for d in sorted(by_day):
        if d.weekday()!=0:continue
        sunday=by_day.get(d-timedelta(days=1))
        if sunday is None:continue
        monday=by_day[d]
        if sunday["wma_week_ending"]!=sunday["signal_date"]:continue
        price=float(monday["btc_usd"])/float(sunday["usd_per_aud"])
        if math.isfinite(price) and price>0:pairs.append((d,price,sunday))
    if not pairs:
        return {"matched_prospective_monday_fills":0,"status":"WAITING_FOR_FULL_SUNDAY_MONDAY_PAIR",
                "broker_fills_verified":False}
    first_price=pairs[0][1]
    output={}
    for name in GATES:
        cash=CAPITAL*(1-INITIAL_BTC_FRACTION)
        btc=CAPITAL*INITIAL_BTC_FRACTION/first_price
        spent=0.;interest=0.; buys=0
        prev=pairs[0][0];peak=CAPITAL;worst=0.
        for i,(day,price,sun) in enumerate(pairs):
            days=(day-prev).days if i else 0
            if days<0:raise ValueError("Nonchronological paper pair")
            earned=cash*((1+CASH_YIELD)**(days/365.25)-1)
            cash+=earned;interest+=earned
            btc*=(1-ETF_DRAG)**(days/365.25)
            prev=day
            weight=multipliers(sun)[name] if day<=ILLUSTRATIVE_REVIEW else 0.
            remaining=max((ILLUSTRATIVE_REVIEW-day).days/7.,1.)
            proposed=min(cash,cash/remaining*weight,WEEKLY_CAP)
            if proposed>FIXED_FEE+.01:
                cash-=proposed
                btc+=(proposed-FIXED_FEE)*(1-FRICTION)/price
                spent+=proposed;buys+=1
            equity=cash+btc*price
            peak=max(peak,equity)
            worst=min(worst,equity/peak-1)
            if cash < -1e-6 or proposed>WEEKLY_CAP+1e-6:
                raise AssertionError("No leverage and cap must hold")
        output[name]={
            "portfolio_aud":cash+btc*pairs[-1][1],
            "additional_purchase_aud":spent,
            "remaining_cash_aud":cash,
            "paper_btc_reference_units":btc,"paper_buy_count":buys,
            "max_drawdown_pct":100*worst,"cash_interest_aud":interest,
        }
    baseline=output["risk_3x_risk_le_020"]["portfolio_aud"]
    for x in output.values():x["value_gap_vs_strict020_pct"]=100*(x["portfolio_aud"]/baseline-1)
    return {
        "matched_prospective_monday_fills":len(pairs),
        "first_paper_monday":pairs[0][0].isoformat(),
        "last_paper_monday":pairs[-1][0].isoformat(),
        "status":"PROSPECTIVE_PAPER_ONLY_NOT_BROKER_EXECUTABLE",
        "illustrative_review_date_not_hard_user_deadline":ILLUSTRATIVE_REVIEW.isoformat(),
        "broker_fills_verified":False,"strategies":output,
        "note":"Uses immutable prior-Sunday signals and next captured Monday BTC/USD proxy with Sunday prior FX. Existing holdings virtualised at first paired Monday. No historical backfill.",
    }


def scorecard(rows:list[dict], new_record_added:bool) -> dict:
    validate_tape(rows)
    days=[date.fromisoformat(x["signal_date"]) for x in rows]
    missed=sum((b-a).days-1 for a,b in zip(days,days[1:]))
    return {
        "status":"RESEARCH_ONLY_FORWARD_DATA",
        "observations":len(rows),
        "first_actual_capture":rows[0]["captured_at_utc"] if rows else None,
        "last_signal_day":rows[-1]["signal_date"] if rows else None,
        "new_day_appended":new_record_added,
        "uncaptured_calendar_days_between_first_last":missed,
        "matured_paper_BTC_AUD_returns":matured_returns(rows),
        "prospective_shadow":paper_portfolios(rows),
        "not_asx_ibit_execution_or_personal_portfolio":True,
        "no_live_recommendations_orders_notifications":True,
    }


def main() -> int:
    p=argparse.ArgumentParser()
    p.add_argument("--old",type=Path,required=True)
    p.add_argument("--new",type=Path,required=True)
    p.add_argument("--scorecard",type=Path,required=True)
    p.add_argument("--snapshot",type=Path,required=True)
    p.add_argument("--code-sha",default="UNKNOWN_NOT_ATTESTED")
    args=p.parse_args()
    old=read_tape(args.old)
    s=capture()
    args.snapshot.parent.mkdir(parents=True,exist_ok=True)
    args.snapshot.write_text(json.dumps(s,sort_keys=True,indent=2,allow_nan=False)+"\n")
    new=to_observation(s,args.code_sha)
    tape,added=add_observation(old,new)
    summary=scorecard(tape,added)
    args.new.parent.mkdir(parents=True,exist_ok=True)
    args.scorecard.parent.mkdir(parents=True,exist_ok=True)
    args.new.write_text("".join(json.dumps(x,sort_keys=True,allow_nan=False)+"\n" for x in tape))
    args.scorecard.write_text(json.dumps(summary,indent=2,sort_keys=True,allow_nan=False)+"\n")
    print("V59_FORWARD_CAPTURE "+json.dumps({
        "new_day_appended":added,"observations":len(tape),
        "last_signal_day":summary["last_signal_day"],
        "matched_prospective_mondays":summary["prospective_shadow"]["matched_prospective_monday_fills"],
        "status":summary["status"],"live_trade_authorised":False
    },sort_keys=True))
    return 0


if __name__=="__main__":
    raise SystemExit(main())
