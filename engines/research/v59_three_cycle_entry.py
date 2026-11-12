"""Three full BTC halving bear cycles: causal 200WMA + phase versus 20-week DCA.

Research only. Allows the 2014/15 period to participate via *price and FX only*
without fabricating V5.9 R2 risk scores, which are comparable only in 2018/22.
Runs a shared calendar for each cycle from halving day 600 through 1300,
not a separately selected 104-week horizon per candidate entry. All trade
decisions use previous fully CLOSED Sunday BTC prices; Monday is a spot/FX
execution reference, never a historical ASX:IBIT fill.
"""
from __future__ import annotations

from datetime import date, timedelta
import math
from statistics import median

import pandas as pd

from engines.research import v59_causal_timing_horse_race as prior
from engines.research.v59_four_year_bottoms import CYCLES

HALVINGS = (
    (date(2012,11,28), "2014_15", date(2015,1,14)),
    (date(2016,7,9), "2018", date(2018,12,15)),
    (date(2020,5,11), "2022", date(2022,11,9)),
    (date(2024,4,20), "2026", None),
)
CAPITAL = 500_000.
WEEKLY_CAP = 25_500.
CASH_YIELD = .05
FIRST_PHASE_DAY = 600        # Existing model's publicly known 600..1200 age zone.
END_PHASE_DAY = 1300         # Fixed common future measurement for every arm.
NEAR_WMA_LIMIT = 1.05       # Explicitly exploratory after earlier cycle research.
ETF_DRAG = prior.ANNUAL_ETF_DRAG
SPREAD = prior.VARIABLE_BUY_FRICTION
FEE = prior.FIXED_FEE_AUD
POLICIES = (
    "wma_near_20week", "wma_age800_20week", "wma_near_25week",
    "wma_near_stage20drop", "wma_near_stage35drop",
    "wma_near_only_when_near", "halving_day800_20week",
    "hold_cash", "v59_risk3x", "v59_strict020",
)
PRICE_ONLY_POLICIES = POLICIES[:-2]


def next_monday(day:date) -> date:
    return day+timedelta(days=(7-day.weekday())%7)


def build_price_only_rows(btc:pd.DataFrame, fx:pd.Series) -> list[dict]:
    """Build strict Sunday signal / Monday price from full price history.

    Require 200 real consecutive Sunday BTC prices; no resample Sat proxy
    in missing-Sunday weeks, no retroactive Monday FX, no invented score.
    """
    if "price" not in btc.columns or btc.empty or fx is None or fx.empty:
        raise ValueError("Require public BTC USD price AND dated AUD FX")
    p=btc["price"].copy()
    p.index=pd.to_datetime(p.index,utc=True).normalize()
    p=pd.to_numeric(p,errors="coerce")
    if p.index.has_duplicates or not p.index.is_monotonic_increasing:
        raise ValueError("BTC calendar contains repeated/unsorted daily closes")
    if not p.dropna().gt(0).all():
        raise ValueError("BTC prices must be positive")
    fx=fx.copy()
    fx.index=pd.to_datetime(fx.index,utc=True).normalize()
    fx=pd.to_numeric(fx,errors="coerce").sort_index().dropna()
    if fx.index.has_duplicates or not fx.gt(0).all():
        raise ValueError("Dated AUD FX invalid")
    sunday=p.loc[p.index.weekday==6]
    weekly=sunday.resample("W-SUN").last()
    if weekly.empty or weekly.index[0].weekday()!=6:
        raise ValueError("No Sunday BTC closes")
    ma=weekly.rolling(200,min_periods=200).mean()
    high=p.rolling(365,min_periods=365).max()
    rows=[]
    for monday in p.index[p.index.weekday==0]:
        sig_day=monday-pd.Timedelta(days=1)
        if sig_day not in sunday.index or sig_day not in ma.index:
            continue
        wma=float(ma.loc[sig_day])
        close=float(p.loc[sig_day])
        fill=float(p.loc[monday])
        if not (math.isfinite(wma) and wma>0 and math.isfinite(close)
                and close>0 and math.isfinite(fill) and fill>0):
            continue
        pos=fx.index.searchsorted(sig_day,side="right")-1
        if pos<0:continue
        fixing=fx.index[pos]
        usd_per_aud=float(fx.iloc[pos])
        if not (0<usd_per_aud and 0<=(monday-fixing).days<=5):
            continue
        historic_halvings=[v[0] for v in HALVINGS if v[0]<=sig_day.date()]
        last=historic_halvings[-1] if historic_halvings else None
        old_high=float(high.loc[sig_day]) if sig_day in high.index else float("nan")
        rows.append({
            "date":monday.date(),"signal_date":sig_day.date(),
            "spot_sunday_usd":close,"btc_price_aud":fill/usd_per_aud,
            "price_usd":fill,"usd_per_aud":usd_per_aud,
            "fx_date":fixing.date(),"wma_usd":wma,
            "ratio_to_200wma":close/wma,
            "drawdown_from_trailing_365_high":(close/old_high-1
                if math.isfinite(old_high) and old_high>0 else None),
            "halving_age_days":(sig_day.date()-last).days if last else None,
            "past_halving_date":last.isoformat() if last else None,
            "risk_score":None,"risk_score_source":"UNAVAILABLE_PRICE_ONLY",
        })
    return rows


def cycle_periods(rows:list[dict]) -> list[dict]:
    indexed={r["date"]:i for i,r in enumerate(rows)}
    out=[]
    for halving,cycle,bottom in HALVINGS:
        requested_first=next_monday(halving+timedelta(days=FIRST_PHASE_DAY))
        terminal=next_monday(halving+timedelta(days=END_PHASE_DAY))
        # In 2015 the first **fully supported** 200-week Sunday average can
        # occur after day 600, because the public BTC archive starts in 2011.
        # Left-truncate every policy on that same first observable Monday;
        # never invent earlier WMA values or call it a full day-600 comparison.
        first=next((r["date"] for r in rows
                    if requested_first<=r["date"]<=terminal),requested_first)
        warmup_truncated=first>requested_first
        if bottom is None:
            out.append({
                "cycle":cycle,"halving":halving.isoformat(),
                "status":"UNCONFIRMED_AND_RIGHT_CENSORED",
                "expost_low":None,"not_simulated":True,
                "first_phase_monday":first.isoformat(),
                "requested_phase_monday":requested_first.isoformat(),
                "wma_warmup_left_truncated":warmup_truncated,
                "common_terminal_monday":terminal.isoformat(),
            })
            continue
        if first not in indexed or terminal not in indexed:
            out.append({"cycle":cycle,"halving":halving.isoformat(),
                "status":"MISSING_COMPLETE_PRICE_FX_WINDOW",
                "expost_low":bottom.isoformat(),"not_simulated":True,
                "first_phase_monday":first.isoformat(),
                "common_terminal_monday":terminal.isoformat()})
            continue
        block=rows[indexed[first]:indexed[terminal]+1]
        complete=(all(r["date"]==first+timedelta(weeks=i)
                for i,r in enumerate(block)) and
                block[-1]["date"]==terminal)
        if not complete:
            out.append({"cycle":cycle,"halving":halving.isoformat(),
                "status":"INCOMPLETE_OBSERVED_WEEKLY_COHORT",
                "expost_low":bottom.isoformat(),"not_simulated":True,
                "first_phase_monday":first.isoformat(),
                "common_terminal_monday":terminal.isoformat()})
            continue
        out.append({"cycle":cycle,"halving":halving.isoformat(),
            "status":"COMPLETE_PRICE_FX_ONLY" if cycle=="2014_15"
                      else "COMPLETE_PRICE_FX_R2_COMPARABLE",
            "expost_low":bottom.isoformat(),"not_simulated":False,
            "first_phase_monday":first.isoformat(),
            "requested_phase_monday":requested_first.isoformat(),
            "wma_warmup_left_truncated":warmup_truncated,
            "common_terminal_monday":terminal.isoformat(),
            "rows":block})
    return out


def first_entry(rows:list[dict], policy:str) -> dict | None:
    """Ex ante fixed halving clock plus Sunday MA threshold, no bottom oracle."""
    if policy=="hold_cash":return None
    if policy.startswith("v59_"):return rows[0]
    if policy=="halving_day800_20week":
        return next((r for r in rows if r["halving_age_days"]>=800),None)
    age_floor=800 if policy=="wma_age800_20week" else FIRST_PHASE_DAY
    return next((r for r in rows if r["halving_age_days"]>=age_floor
               and r["ratio_to_200wma"]<=NEAR_WMA_LIMIT),None)


def _multiplier(risk:float, strict:bool) -> float:
    # Only reconstructed V5.9 R2, never proxied by an invented 2015 score.
    if not math.isfinite(risk) or not 0<=risk<=1:
        raise ValueError("Invalid real V5.9 risk")
    from engines.research.v59_dynamic_risk_policy import risk_buy_multiplier
    m=risk_buy_multiplier(risk)
    return m if not strict or risk<=.2 else 0.


def replay(rows:list[dict], *, policy:str, capital:float=CAPITAL,
           initial_btc_fraction:float=0., cash_yield:float=CASH_YIELD,
           risk_lookup:dict | None=None) -> dict:
    """Matched common-calendar self-financing simulation. No sales, taxes or leverage."""
    if policy not in POLICIES or not rows:
        raise ValueError("Unknown policy or empty price period")
    if not 0<=initial_btc_fraction<=1 or not 0<=cash_yield<1:
        raise ValueError("Invalid financial inputs")
    beginning=rows[0]["date"]
    terminal=rows[-1]["date"]
    for i,r in enumerate(rows):
        if r["date"]!=beginning+timedelta(weeks=i) or (r["date"]-r["signal_date"]).days!=1:
            raise ValueError("Missing weekly price or causal Sunday signal")
    if policy.startswith("v59_"):
        if risk_lookup is None or any(
            r["date"] not in risk_lookup or
            risk_lookup[r["date"]].get("risk_score_source")!="Walk-forward Power Law"
            for r in rows):
            return {"policy":policy,"status":"UNAVAILABLE_NO_VERIFIED_R2_HISTORY",
                "not_compared_in_2015":True}
    anchor=first_entry(rows,policy)
    initial_cash=capital*(1-initial_btc_fraction)
    available_budget=initial_cash
    cash=initial_cash
    btc=capital*initial_btc_fraction/float(rows[0]["btc_price_aud"])
    paid=0.;net_bought=0.;interest=0.;orders=0
    peak=capital;dd=0.
    first_fill=None
    prev=beginning
    cohort_rows_after_entry=0
    for i,r in enumerate(rows):
        today=r["date"]
        elapsed=(today-prev).days if i else 0
        gained=cash*((1+cash_yield)**(elapsed/365.25)-1)
        cash+=gained
        interest+=gained
        btc*=(1-ETF_DRAG)**(elapsed/365.25)
        prev=today
        gross=0.
        if anchor is not None and today>=anchor["date"]:
            age=(today-anchor["date"]).days//7
            ratio=float(r["ratio_to_200wma"])
            if policy=="wma_near_20week" or policy=="wma_age800_20week" or policy=="halving_day800_20week":
                if age<20:gross=initial_cash/20.
            elif policy=="wma_near_25week":
                if age<25:gross=initial_cash/25.
            elif policy in ("wma_near_stage20drop","wma_near_stage35drop"):
                # The *prior Sunday close* of the current candidate Monday
                # must be 20/35% below the FIRST signal's Sunday close.
                drop=.20 if policy=="wma_near_stage20drop" else .35
                triggered=r["spot_sunday_usd"]<=anchor["spot_sunday_usd"]*(1-drop)
                # Early cautious rate or accelerate after an observed extra fall,
                # eventually invest residual principal over next ~24-32 weeks.
                gross=initial_cash*(.051 if triggered else (.025 if age<8 else .05))
            elif policy=="wma_near_only_when_near":
                if ratio<=NEAR_WMA_LIMIT:gross=initial_cash/20.
            elif policy.startswith("v59_"):
                risk_row=risk_lookup[today]
                risk=float(risk_row["risk_score"])
                mult=_multiplier(risk,strict=policy=="v59_strict020")
                weeks_remaining=max((terminal-today).days/7,1)
                gross=cash/weeks_remaining*mult
            else:
                raise ValueError("Unhandled policy")
            # All policies, including optional V5.9 R2, use fixed weekly cap.
            gross=min(max(gross,0.),WEEKLY_CAP,cash)
            # Price-only strategies expend at most ORIGINAL CASH allocated,
            # while the reference V5.9 may reinvest earned interest.
            if not policy.startswith("v59_"):
                gross=min(gross,max(0.,available_budget-paid))
        price=float(r["btc_price_aud"])
        if gross>FEE+.01:
            cash-=gross
            bought=(gross-FEE)*(1-SPREAD)/price
            btc+=bought
            net_bought+=bought
            paid+=gross
            orders+=1
            if first_fill is None:first_fill=today.isoformat()
        equity=cash+btc*price
        peak=max(equity,peak)
        dd=min(dd,equity/peak-1)
        if cash < -1e-5 or btc < -1e-5 or gross>WEEKLY_CAP+1e-5:
            raise AssertionError("Cash/weekly cap/negative balance violation")
        if anchor is not None and today>=anchor["date"]:
            cohort_rows_after_entry+=1
    last=float(rows[-1]["btc_price_aud"])
    return {
        "policy":policy,"status":"RESEARCH_ONLY",
        "initial_btc_fraction":initial_btc_fraction,
        "first_signal_date":anchor["signal_date"].isoformat() if anchor else None,
        "first_buy_monday":first_fill,
        "asof_terminal":terminal.isoformat(),
        "btc_units_at_terminal":btc,
        "additional_btc_units_before_drag":net_bought,
        "cash_aud_at_terminal":cash,
        "portfolio_aud_at_terminal":cash+btc*last,
        "terminal_btc_equivalent_including_cash":btc+cash/last,
        "total_purchases_aud":paid,
        "cash_interest_aud":interest,
        "buy_count":orders,
        "worst_drawdown_pct":100*dd,
        "not_a_historical_ASX_IBIT_fill":True,
    }


def synthetic_false_bottom_stress() -> list[dict]:
    """Artificial fixed-valuation context; no historical signal refitting."""
    out=[]
    generic_start=next_monday(date(2020,5,11)+timedelta(days=800))
    for decline in (.20,.35,.50):
        for recover in (False,True):
            seq=[]
            for i in range(104):
                # Prior-Sunday USD close observed before next Monday proxy.
                # Deterministic 12-week fall, 12-week recovery or stay-low.
                if i<=12:
                    price=100000*(1-decline*i/12)
                elif recover and i<=24:
                    price=100000*(1-decline+decline*(i-12)/12)
                else:
                    price=100000 if recover else 100000*(1-decline)
                day=generic_start+timedelta(weeks=i)
                seq.append({
                    "date":day,"signal_date":day-timedelta(days=1),
                    "spot_sunday_usd":price,
                    "btc_price_aud":price/.70,
                    "ratio_to_200wma":price/100000,
                    "halving_age_days":800+i*7,
                })
            for initial_fraction, capital in ((0.,500000.),(.41,510000.)):
                for policy in ("wma_near_20week","wma_near_25week",
                               "wma_near_stage20drop","wma_near_stage35drop",
                               "wma_near_only_when_near"):
                    rec=replay(seq,policy=policy,capital=capital,
                               initial_btc_fraction=initial_fraction)
                    out.append({
                        "scenario":f"fall_{int(decline*100)}pct_then_"+("recover" if recover else "stay_low"),
                        "risk_is_recomputed":False,
                        "wma_held_fixed_at_initial_price":True,
                        "policy":policy,
                        "initial_btc_fraction":initial_fraction,
                        "btc_units_at_terminal":rec["btc_units_at_terminal"],
                        "total_portfolio_aud":rec["portfolio_aud_at_terminal"],
                        "uninvested_cash_aud":rec["cash_aud_at_terminal"],
                        "max_drawdown_pct":rec["worst_drawdown_pct"],
                    })
    return out


def evaluate(price_rows:list[dict], risk_rows:list[dict]) -> dict:
    seasons=cycle_periods(price_rows)
    risk_map={x["date"]:x for x in risk_rows}
    output=[]
    for season in seasons:
        context={k:v for k,v in season.items() if k!="rows"}
        if season["not_simulated"]:
            output.append(context)
            continue
        sample=season["rows"]
        observations=[r for r in sample if r["halving_age_days"]>=FIRST_PHASE_DAY
                      and r["ratio_to_200wma"]<=NEAR_WMA_LIMIT]
        x={**context,
           "first_near_signal_sunday":observations[0]["signal_date"].isoformat()
               if observations else None,
           "first_near_signal_halving_age_days":observations[0]["halving_age_days"]
               if observations else None,
           "near_wma_observed_weeks":len(observations),
           "first_200wma_ratio":sample[0]["ratio_to_200wma"],
           "three_scenario_replays":{},
        }
        for case,capital,fraction in (
            ("fresh_AUD500k",500000.,0.),
            ("existing_41pct_AUD510k",510000.,.41)):
            x["three_scenario_replays"][case]={
                name:replay(sample,policy=name,capital=capital,
                            initial_btc_fraction=fraction,risk_lookup=risk_map)
                for name in POLICIES
            }
        output.append(x)
    return {
        "status":"RESEARCH_ONLY_NO_LIVE_PROMOTION",
        "raw_price_data_pre_2017_used":True,
        "historical_reconstructed_v59_r2_not_fabricated_for_2015":True,
        "shared_horizon":"First Monday on/after halving+600 through first Monday on/after halving+1300",
        "causal_near_200wma_threshold":NEAR_WMA_LIMIT,
        "age_800_sensitivity_is_posthoc":True,
        "true_cycle_bottom_date_only_used_for_expost_labelling":True,
        "cash_return_illustrative":CASH_YIELD,
        "weekly_cap_aud":WEEKLY_CAP,
        "same_horizon_across_each_cycle_candidates":True,
        "schedules":output,
        "synthetic_fixed_valuation_stress":synthetic_false_bottom_stress(),
        "limitations":[
            "Only three complete major cycles if 2015 price/FX lookback supports 200 real Sunday observations. 2026 right-censored.",
            "2015 has no V5.9 research risk baseline; code refuses to synthesize one.",
            "Day-600/800 phase and WMA +5% gates were chosen after observing historical cycles; leave-one-cycle-out testing cannot reverse selection bias.",
            "Early BTC/USD and FX data quality, 2015 trading liquidity, institutional/IBIT availability and spreads differ dramatically from 2026.",
            "Synthetic 20/35/50% declines keep WMA fixed; not a real recalculated indicator path or forecast.",
            "Annual 5% pretax AUD cash yield and spread/fixed ETF drag are illustrative rather than true historical AAA cashflows.",
            "ASX:IBIT did not exist in historical cycles; prices are hypothetical BTC/USD spot divided by previous public AUD/USD fixing.",
            "No production trading, portfolio write, automation action, streamlit or ntfy changed.",
        ],
    }
