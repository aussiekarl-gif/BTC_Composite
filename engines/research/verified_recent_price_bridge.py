"""RESEARCH ONLY: verify and extend weekly BTC/AUD observations beyond master.

Never modify central BTC master, user portfolio, Production or stored risk scores.
Read public Blockchain.com BTC/USD chart and Frankfurter AUD-per-USD FX, align
only to the last available USD/BTC and FX observation ON OR BEFORE each Monday.
Require overlap agreement to historical AUD master, label all sources and dates.

Create an entirely *separate* aud-price-only causal walk-forward Power Law risk
candidate. This is NOT a reconstruction/certification of the original master
risk_score, nor the Production Research WF PL in USD. Pre-2026 prices are used
only to warm indicators. No data after a requested as-of date.
"""
from __future__ import annotations

import argparse
import json
import math
import datetime as dt

import numpy as np
import pandas as pd
import requests

from engines.research.full_cycle_reinvestment import validate_history
from engines.research.real_2026_deployment_audit import evaluate_cohorts, benchmark_account
from engines.research.adaptive_dca_execution import simulate_adaptive
from engines.research.smsf_self_financing_replay import replay

PRICE_ENDPOINT = "https://api.blockchain.info/charts/market-price"
FX_ENDPOINT = "https://api.frankfurter.app/"
MIN_OVERLAP = 4
MAX_MEDIAN_DEVIATION_PCT = 5.0
MAX_SINGLE_DEVIATION_PCT = 12.0
GENESIS = pd.Timestamp("2009-01-03", tz="UTC")
SOURCE_DATE = "2025-12-01"
USER_REPORTED_LOW_USD = 57_717.0
USER_REPORTED_LOW_DATE = "2026-06-30"


def normalise_utc_index(points, *, name, numeric_field):
    result=pd.DataFrame(points)
    if not {"date",numeric_field}.issubset(result.columns):
        raise ValueError(f"{name}: missing required columns")
    result["date"]=pd.to_datetime(result["date"],utc=True,errors="coerce").dt.normalize()
    result[numeric_field]=pd.to_numeric(result[numeric_field],errors="coerce")
    result=result.dropna(subset=["date",numeric_field])
    result=result.loc[np.isfinite(result[numeric_field]) & result[numeric_field].gt(0)]
    if result.empty:
        raise ValueError(f"{name}: no valid dated prices")
    if result["date"].duplicated().any():
        raise ValueError(f"{name}: conflicting duplicate timestamps")
    return result.sort_values("date").set_index("date")[[numeric_field]]


def parse_blockchain_price(payload):
    if not isinstance(payload,dict) or not isinstance(payload.get("values"),list):
        raise ValueError("Invalid Blockchain.com chart response")
    pts=[]
    for p in payload["values"]:
        try:
            date=pd.Timestamp(float(p["x"]),unit="s",tz="UTC")
            price=float(p["y"])
        except (TypeError,ValueError,KeyError,OverflowError):
            continue
        pts.append({"date":date,"btc_usd":price})
    return normalise_utc_index(pts,name="Blockchain.com",numeric_field="btc_usd")


def parse_frankfurter_fx(payload):
    rates=payload.get("rates") if isinstance(payload,dict) else None
    if not isinstance(rates,dict):
        raise ValueError("Invalid Frankfurter API response")
    pts=[]
    for date,v in rates.items():
        try:
            aud_per_usd=float(v["AUD"])
            if aud_per_usd>0 and math.isfinite(aud_per_usd):
                pts.append({"date":date,"aud_per_usd":aud_per_usd})
        except (TypeError,ValueError,KeyError):
            continue
    return normalise_utc_index(pts,name="Frankfurter",numeric_field="aud_per_usd")


def fetch_public_series(*, asof, timeout=30):
    end=pd.Timestamp(asof)
    if end.tzinfo is None: end=end.tz_localize("UTC")
    else: end=end.tz_convert("UTC")
    end=end.normalize()
    now=pd.Timestamp.now(tz="UTC").normalize()
    if end>now:
        raise ValueError("Do not fetch future observations")
    price_response=requests.get(
        PRICE_ENDPOINT,
        params={"timespan":"all","format":"json","sampled":"false"},
        headers={"User-Agent":"BTC-Composite-Research-Audit/1.0"},
        timeout=timeout)
    price_response.raise_for_status()
    price=parse_blockchain_price(price_response.json())
    fx_response=requests.get(
        FX_ENDPOINT+f"{SOURCE_DATE}..{end.strftime('%Y-%m-%d')}",
        params={"from":"USD","to":"AUD"},
        headers={"User-Agent":"BTC-Composite-Research-Audit/1.0"},
        timeout=timeout)
    fx_response.raise_for_status()
    fx=parse_frankfurter_fx(fx_response.json())
    return price,fx


def asof_on_mondays(price, fx, *, start, end, max_price_lag_days=2,
                    max_fx_lag_days=7):
    """Never fill with later price or FX rates; reject stale observations."""
    if price.empty or fx.empty:
        raise ValueError("Cannot bridge missing price or FX")
    start=pd.Timestamp(start);end=pd.Timestamp(end)
    if start.tzinfo is None: start=start.tz_localize("UTC")
    if end.tzinfo is None: end=end.tz_localize("UTC")
    monday=pd.date_range(start.normalize(),end.normalize(),freq="W-MON",tz="UTC")
    if len(monday)<MIN_OVERLAP:
        raise ValueError("Need at least four overlapping Monday observations")
    q=pd.DataFrame({"date":monday})
    p=price.rename_axis("date").reset_index().rename(columns={"date":"price_source_date"})
    x=fx.rename_axis("date").reset_index().rename(columns={"date":"fx_source_date"})
    # Some providers expose Unix-second dates while pandas.date_range is
    # microsecond-resolution in pandas 3. Normalize all merge keys exactly.
    for frame,key in ((q,"date"),(p,"price_source_date"),(x,"fx_source_date")):
        frame[key]=pd.to_datetime(frame[key],utc=True).astype("datetime64[ns, UTC]")
    q=pd.merge_asof(q,p,left_on="date",right_on="price_source_date",direction="backward")
    q=pd.merge_asof(q,x,left_on="date",right_on="fx_source_date",direction="backward")
    q["price_lag_days"]=(q["date"]-q["price_source_date"]).dt.days
    q["fx_lag_days"]=(q["date"]-q["fx_source_date"]).dt.days
    bad=q["btc_usd"].isna()|q["aud_per_usd"].isna()|q["price_lag_days"].gt(max_price_lag_days)|q["fx_lag_days"].gt(max_fx_lag_days)
    if bad.any():
        failures=q.loc[bad,"date"].dt.strftime("%Y-%m-%d").tolist()
        raise ValueError(f"Missing/stale public price or FX for Mondays: {failures[:8]}")
    q["btc_price_aud"]=q["btc_usd"]*q["aud_per_usd"]
    return q.set_index("date")


def append_verified_prices(master, public, *, asof):
    """Make temporary in-memory price history, never insert into central CSV."""
    old=validate_history(master)
    cutoff=old.index[-1]
    asof_ts=pd.Timestamp(asof)
    if asof_ts.tzinfo is None: asof_ts=asof_ts.tz_localize("UTC")
    else: asof_ts=asof_ts.tz_convert("UTC")
    public=public.loc[public.index<=asof_ts].copy()
    intersect=old.index.intersection(public.index)
    if len(intersect)<MIN_OVERLAP:
        raise ValueError("Insufficient public/master overlap; don't splice providers blindly")
    overlap=100*(public.loc[intersect,"btc_price_aud"]/old.loc[intersect,"btc_price_aud"]-1).abs()
    median=float(overlap.median());worst=float(overlap.max())
    if median>MAX_MEDIAN_DEVIATION_PCT or worst>MAX_SINGLE_DEVIATION_PCT:
        raise ValueError(f"Provider overlap mismatch median={median:.2f}%, max={worst:.2f}%")
    additions=public.loc[public.index>cutoff,["btc_price_aud"]]
    if additions.empty:
        raise ValueError("Public provider supplies no verified weeks after existing research master")
    # The historical archived risk score is *NOT* carried forward, filled,
    # or misrepresented as a fresh daily score.
    combined=pd.concat([old[["btc_price_aud"]],
                        additions],axis=0).sort_index()
    if combined.index.has_duplicates or not np.isfinite(combined["btc_price_aud"]).all():
        raise ValueError("Invalid appended price history")
    return combined, {
        "master_last_price_date":str(cutoff),
        "new_public_weeks":len(additions),
        "new_first_week":str(additions.index[0]),
        "new_last_week":str(additions.index[-1]),
        "overlap_count":len(intersect),
        "median_abs_aud_price_deviation_pct":round(median,3),
        "maximum_abs_aud_price_deviation_pct":round(worst,3),
        "public_raw_final_week":str(public.index[-1]),
        "master_risk_score_not_extended":True,
    }


def expanding_aud_powerlaw_risk(weekly_prices, *, min_history_weeks=104,
                                refit_days=91, cheap=-.10, expensive=.20):
    """Strictly prior-data regression. Own candidate (not archived composite)."""
    if cheap>=expensive:
        raise ValueError("Risk scoring boundaries inverted")
    d=weekly_prices.sort_index().copy()
    dates=d.index
    if not isinstance(dates,pd.DatetimeIndex) or dates.has_duplicates:
        raise ValueError("Require unique timestamps")
    if dates.tz is None:
        raise ValueError("Require UTC-aware weekly dates")
    px=pd.to_numeric(d["btc_price_aud"],errors="coerce")
    if px.isna().any() or px.le(0).any():
        raise ValueError("Invalid prices")
    days=np.array([(x-GENESIS).days for x in dates],dtype=float)
    scores=np.full(len(d),np.nan)
    slope=intercept=None
    fitted_at=None
    for i in range(len(d)):
        # Require at least 104 PREVIOUS weekly samples and every fit uses
        # strictly j < i, even if model coefficients remain frozen.
        if i>=min_history_weeks and (fitted_at is None or
                                     (dates[i]-fitted_at).days>=refit_days):
            ok=(days[:i]>0)&np.isfinite(px.to_numpy()[:i])
            if int(ok.sum())>=min_history_weeks:
                slope,intercept=np.polyfit(np.log10(days[:i][ok]),
                                            np.log10(px.to_numpy()[:i][ok]),1)
                fitted_at=dates[i]
        if slope is not None and days[i]>0:
            relative=np.log10(float(px.iloc[i]))-(slope*np.log10(days[i])+intercept)
            scores[i]=min(1.0,max(0.0,(relative-cheap)/(expensive-cheap)))
    out=d.copy()
    out["risk_score"]=scores
    return out


def nearest_historical_fx(fx, purchase_date, *, max_lag_days=7):
    """Return AUD per USD observed on/before the purchase date."""
    when=pd.Timestamp(purchase_date)
    when=when.tz_localize("UTC") if when.tzinfo is None else when.tz_convert("UTC")
    eligible=fx.loc[fx.index<=when]
    if eligible.empty or (when-eligible.index[-1]).days>max_lag_days:
        raise ValueError(f"Historical AUD/USD unavailable at {when}")
    return float(eligible.iloc[-1]["aud_per_usd"])


def weighted_entry_from_synthetic_orders(orders, historical_fx, *,
                                         low_usd=USER_REPORTED_LOW_USD,
                                         starting_capital=500_000.):
    """Cumulative BTC-quantity-weighted BUY cost; never average unit prices.

    Reference bottom is USER-REPORTED, not silently treated as verified by
    Blockchain.com's daily-average chart. Ignore SELL orders only for this
    entry-quality diagnostic; the 2026 cohort has no sales so far.
    """
    buy=[o for o in orders if o["side"]=="BUY"]
    if not buy:
        return {
            "buy_order_count":0,
            "aud_capital_deployed_pct":0.0,
            "average_entry_usd_per_btc":None,
            "error_from_observed_low_pct":None,
            "within_25pct":None,
        }
    usd_spent=0.;aud_spent=0.;acquired=0.
    for o in buy:
        amount=float(o["gross_aud"])
        qty=float(o["btc"])
        if not np.isfinite(amount) or amount<=0 or not np.isfinite(qty) or qty<=0:
            raise ValueError("Cannot calculate BTC-weighted entry from invalid order")
        aud_spent+=amount
        usd_spent+=amount/nearest_historical_fx(historical_fx,o["date"])
        acquired+=qty
    entry=usd_spent/acquired
    error=100*(entry/low_usd-1)
    return {
        "buy_order_count":len(buy),
        "aud_capital_deployed_pct":round(100*aud_spent/starting_capital,3),
        "average_entry_usd_per_btc":round(entry,2),
        "error_from_observed_low_pct":round(error,3),
        "within_25pct":bool(error<=25),
        "benchmark_low_usd":low_usd,
        "benchmark_low_date":USER_REPORTED_LOW_DATE,
    }


GATE_DRAWDOWNS = (.30,.40,.50)


def first_causal_gate_week(history, *, drawdown, start_date="2026-01-01",
                           lookback=52):
    """At execution t inspect ONLY prior week's past-52-week close drawdown."""
    h=validate_history(history)
    start=pd.Timestamp(start_date)
    if h.index.tz is not None:
        start=start.tz_localize(h.index.tz) if start.tzinfo is None else start.tz_convert(h.index.tz)
    prices=h["btc_price_aud"].to_numpy(float)
    for i in range(lookback,len(h)):
        if h.index[i]<start:
            continue
        before=prices[i-lookback:i]
        prev=prices[i-1]
        dd=1-prev/float(np.max(before))
        if dd>=drawdown:
            return h.index[i],dd
    return None,None


def evaluate_causal_drawdown_entry_gates(history, historical_fx, *,
                                         starting_cash=500_000.):
    """Cash starts Jan 2026. Gate activation is *decided* with t-1 only.

    Gate does not secretly start a new account in June; user starts in
    January in CASH, waiting for a causally observable, predeclared signal.
    Dynamic purchase/sale duration remains unrestricted after trigger.
    """
    h=validate_history(history)
    out=[]
    for dd in GATE_DRAWDOWNS:
        gate,observed=first_causal_gate_week(h,drawdown=dd)
        if gate is None:
            out.append({"gate_drawdown_pct":100*dd,"triggered":False,
                        "terminal_cash_only_aud":starting_cash,
                        "average_entry_error_pct":None})
            continue
        simulated=simulate_adaptive(h,deployment_start=gate,
                                    confirm_drawdown=.10,
                                    initial_cash=starting_cash)
        model=replay(h,simulated["trades"],policy="adaptive",tax=True,
                     starting_cash=starting_cash)
        entry=weighted_entry_from_synthetic_orders(model["orders"],historical_fx,
                                                    starting_capital=starting_cash)
        out.append({
            "gate_drawdown_pct":round(dd*100,1),
            "triggered":True,
            "gate_execution_date":str(gate),
            "prior_week_observed_peak_drawdown_pct":round(observed*100,3),
            "filled_orders":model["actual_orders"],
            "buys":model["buy_orders"],
            "sells":model["sell_orders"],
            "btc_held":model["btc"],
            "cash_remaining_aud":model["cash_aud"],
            "ending_marked_equity_aud":model["ending_marked_equity_aud"],
            "hypothetical_after_liquidation_cgt_aud":
                model["hypothetical_final_liquidation_after_cgt_aud"],
            "max_equity_drawdown_pct":model["max_account_drawdown_pct"],
            "entry_vs_reported_low":entry,
        })
    return out


HISTORICAL_TRANSFER_START_YEARS = (2019,2020,2021,2022,2023,2024,2025)


def historical_entry_gate_transfer(history, *,
                                   years=HISTORICAL_TRANSFER_START_YEARS,
                                   capital=500_000.):
    """Fixed cash inception, fixed 52-week horizon on several older eras.

    Scores ACTUAL implementable prior-price-only activation conditions.
    Each cohort is independent hypothetical fresh capital, does not use
    future-optimised starting day, and does not pretend to be a live account.
    Because models have already been examined on 2019–2025, still in-sample.
    """
    h=validate_history(history)
    rows=[]
    for year in years:
        start=f"{year}-01-01"
        end=pd.Timestamp(start,tz="UTC")+pd.Timedelta(weeks=52)
        prefix=h.loc[h.index<end]
        if len(prefix)<104 or prefix.index[-1]<end-pd.Timedelta(weeks=2):
            continue
        matched=benchmark_account(prefix,start,"immediate_buy",initial_cash=capital)
        buy_hold=matched["account_marked_value_aud"]
        policies=[{
            "activation_gate_pct":0,
            "gate_execution_date":matched["first_weekly_execution"],
            "ending_equity_aud":buy_hold,
            "BTC_held":matched["btc_equivalent_held"],
            "filled_orders":matched["actual_orders"],
            "triggered":True,
            "policy":"immediate_buy",
        }]
        for gate in GATE_DRAWDOWNS:
            trigger,_=first_causal_gate_week(prefix,drawdown=gate,
                                              start_date=start)
            if trigger is None:
                policies.append({
                    "policy":f"drawdown_{int(100*gate)}pct_adaptive",
                    "activation_gate_pct":100*gate,
                    "triggered":False,
                    "ending_equity_aud":capital,
                    "BTC_held":0.,
                    "filled_orders":0,
                    "gate_execution_date":None,
                })
                continue
            origin=simulate_adaptive(prefix,confirm_drawdown=.10,
                                      deployment_start=trigger,
                                      initial_cash=capital)
            replayed=replay(prefix,origin["trades"],policy="adaptive",tax=True,
                              starting_cash=capital)
            policies.append({
                "policy":f"drawdown_{int(100*gate)}pct_adaptive",
                "activation_gate_pct":100*gate,
                "triggered":True,
                "gate_execution_date":str(trigger),
                "ending_equity_aud":replayed["ending_marked_equity_aud"],
                "BTC_held":replayed["btc"],
                "filled_orders":replayed["actual_orders"],
            })
        for p in policies:
            p["relative_to_matched_hold_pct"]=round(
                100*(p["ending_equity_aud"]/buy_hold-1),3)
        rows.append({
            "start":start,
            "end":str(prefix.index[-1]),
            "scenarios":policies,
        })
    summaries=[]
    for gate in GATE_DRAWDOWNS:
        candidates=[next(p for p in r["scenarios"]
                         if p["activation_gate_pct"]==100*gate)
                    for r in rows]
        summaries.append({
            "gate_drawdown_pct":100*gate,
            "cohorts":len(candidates),
            "triggered":sum(x["triggered"] for x in candidates),
            "beat_immediate_hold":sum(x["relative_to_matched_hold_pct"]>0
                                      for x in candidates),
            "underperformed_hold":sum(x["relative_to_matched_hold_pct"]<0
                                       for x in candidates),
            "median_relative_to_hold_pct":round(
                float(np.median([x["relative_to_matched_hold_pct"]
                                 for x in candidates])),3)
                if candidates else None,
        })
    return {"fixed_one_year_eras":rows,"summary":summaries,
            "not_out_of_sample":True}


def audit(master, *, asof):
    historical=validate_history(master)
    if historical.index.tz is None:
        raise ValueError("Source master must have UTC-aware weekly index")
    price,fx=fetch_public_series(asof=asof)
    period_start=historical.index[-1]-pd.Timedelta(weeks=10)
    public=asof_on_mondays(price,fx,start=period_start,end=asof)
    combined,quality=append_verified_prices(historical,public,asof=asof)
    candidate=expanding_aud_powerlaw_risk(combined)
    if candidate["risk_score"].isna().any():
        candidate=candidate.dropna(subset=["risk_score"])
    overlap=candidate.index.intersection(historical.index)
    # Compare only overlapping dates; MAE measures divergence but is not
    # permission to replace archived risk_score with our price-only signal.
    diffs=(candidate.loc[overlap,"risk_score"]-
           historical.loc[overlap,"risk_score"]).abs()
    risk_diagnostics={
        "both_risks_overlap_weeks":len(diffs),
        "mean_abs_difference":round(float(diffs.mean()),4),
        "max_abs_difference":round(float(diffs.max()),4),
        "weeks_disagree_by_over_0_20":int(diffs.gt(.20).sum()),
        "signals_are_not_equivalent":True,
    }
    cohorts=evaluate_cohorts(candidate,include_research_orders=True)
    for cohort in cohorts["cohorts"]:
        for outcome in cohort["results"]:
            synthetic_orders=outcome.pop("_research_orders",[])
            outcome["weighted_entry_vs_reported_low"]=weighted_entry_from_synthetic_orders(
                synthetic_orders, fx)
    gated=evaluate_causal_drawdown_entry_gates(candidate,fx)
    historical_transfer=historical_entry_gate_transfer(candidate)
    return {
        "research_only":True,
        "asof_requested":str(pd.Timestamp(asof).date()),
        "price_provider":"Blockchain.com chart market-price BTC/USD",
        "fx_provider":"Frankfurter AUD per USD from USD/AUD official historical series",
        "price_and_fx_alignment":"On/before Monday only; no future filled prices or FX",
        "data_quality":quality,
        "price_only_causal_risk":risk_diagnostics,
        "cohort_replay":cohorts,
        "causal_january_cash_drawdown_gates":gated,
        "historical_one_year_gate_transfer":historical_transfer,
        "warnings":[
            "AUD strict-prior Power Law candidate is NOT the existing proprietary/archived risk_score.",
            "All historical models are in-sample hypotheses; no untouched holdout.",
            "BTC USD 57,717 June 30 is a provisional reported low, not independently verified by weekly Monday closes.",
            "Public weekly BTC/AUD may differ from master since market snapshots/FX methods differ.",
            "No modification to portfolio, Production trading, or source master.",
            "Cash and positions are hypothetical fresh 2026 starts, not user's actual buys.",
            "No claims of complete cycle top/low 25% prediction accuracy.",
            "USD 57,717 low is user-supplied, not independently validated at high-frequency intraday resolution.",
            "Buying error excludes unused cash; deployment percentage is separately disclosed.",
            "The gate thresholds are explored in sample after prior cycle inspection; no prospective validation.",
            "A January cash-held until drawdown strategy is different from pretending June was selected perfectly in advance.",
            "One-year prior-cycle transfer tests are historically inspected and not untouched out-of-sample.",
            "Drawdown gates can stay inactive through a bull market; count missed opportunities.",
        ],
    }


def main():
    p=argparse.ArgumentParser()
    p.add_argument("--asof",default="2026-10-16")
    p.add_argument("--output",default="")
    args=p.parse_args()
    from engines.shared.central_data import load_master
    master=load_master(columns=["btc_price_aud","risk_score"])
    numeric=master[["btc_price_aud","risk_score"]].apply(pd.to_numeric,errors="coerce")
    valid=numeric["btc_price_aud"].gt(0)&numeric["risk_score"].between(0,1)
    result=audit(numeric.loc[valid],asof=args.asof)
    result["source_master_valid_rows"]=int(valid.sum())
    text=json.dumps(result,indent=2,allow_nan=False,
                    default=lambda obj:obj.item() if isinstance(obj,np.generic) else str(obj))
    if args.output:
        from pathlib import Path
        Path(args.output).write_text(text+"\n",encoding="utf-8")
    print(text)


if __name__=="__main__":
    main()
