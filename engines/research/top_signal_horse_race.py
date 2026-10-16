"""Top-signal horse race, research only. Never trades or writes portfolio/master.

Assess well-known and independent *causal on the saved observations*
BTC/USD indicators on dated exported BlockHorizon research CSVs.

Historical CSVs were exported in October 2026: their time-series values
are NOT independently verified as published real-time in prior years.
There may be retrospective data revision, and parameter selection itself
could be hindsight. Prefix-invariance in this script ONLY prevents
lookahead in calculations, not on-chain historical vintage bias.

All alert events are detected from PREVIOUS completed daily observations,
with earliest model trade at next calendar day's observed BTC/USD close.
No fitting to known cycle peaks; peaks used only to score results later.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd

DATA=Path(__file__).resolve().parents[2]/"data"
FILE_MVRV="mvrv_z_score_2026-10-06T21-46-14.csv"
FILE_NUPL="nupl_net_unrealized_profit_loss__2026-10-06T08-54-39.csv"
FILE_SOPR="sopr_spent_output_profit_ratio__2026-10-07T21-21-13.csv"

# All named threshold families are predeclared (not optimised on this run).
PEAK_WINDOWS={
    "2013":("2013-11-01","2014-02-01"),
    "2017":("2017-09-01","2018-02-01"),
    "2021":("2021-01-01","2022-02-01"),
    "2025":("2025-01-01","2026-01-01"),
}
# Calendar features here are context only, *not* top predictions.
HALVINGS=pd.to_datetime(["2012-11-28","2016-07-09","2020-05-11",
                          "2024-04-20"],utc=True)
MIN_SEPARATION_DAYS=90


def parse_chart_csv(path, column):
    frame=pd.read_csv(path)
    if not {"timestamp",column,"Price"}.issubset(frame.columns):
        raise ValueError(f"Bad research indicator CSV: {path.name}")
    frame["timestamp"]=pd.to_datetime(
        pd.to_numeric(frame["timestamp"],errors="coerce"),unit="ms",
        utc=True,errors="coerce").dt.normalize()
    for c in (column,"Price"):
        frame[c]=pd.to_numeric(frame[c],errors="coerce")
    frame=frame.dropna(subset=["timestamp",column,"Price"])
    frame=frame.loc[(frame[column].notna())&frame["Price"].gt(0)]
    if frame["timestamp"].duplicated().any():
        raise ValueError(f"Duplicate indicator observations: {path}")
    if frame.empty:
        raise ValueError(f"No data in {path}")
    return (frame.set_index("timestamp")[[column,"Price"]]
            .sort_index())


def read_exported_history(root=DATA):
    m=parse_chart_csv(root/FILE_MVRV,"MVRV Z-Score")
    n=parse_chart_csv(root/FILE_NUPL,"Net Unrealized Profit/Loss (NUPL)")
    s=parse_chart_csv(root/FILE_SOPR,"Spent Output Profit Ratio (SOPR)")
    a=m.rename(columns={"Price":"price_mvrv","MVRV Z-Score":"mvrv_z"})
    b=n.rename(columns={"Price":"price_nupl",
                        "Net Unrealized Profit/Loss (NUPL)":"nupl"})
    c=s.rename(columns={"Price":"price_sopr",
                        "Spent Output Profit Ratio (SOPR)":"sopr"})
    frame=a.join(b,how="inner").join(c,how="inner")
    if frame.empty: raise ValueError("No paired dated indicators")
    spread=(frame[["price_mvrv","price_nupl","price_sopr"]].max(axis=1)
            /frame[["price_mvrv","price_nupl","price_sopr"]].min(axis=1)-1)
    if spread.max()>.01:
        raise ValueError(f"Price inconsistency among exports: {spread.max():.2%}")
    frame=frame.rename(columns={"price_mvrv":"price_usd"})
    return frame[["price_usd","mvrv_z","nupl","sopr"]]


def _prior_rolling(values, n, *, min_n=None, func="mean"):
    s=pd.Series(values,dtype=float)
    r=s.shift(1).rolling(n,min_periods=n if min_n is None else min_n)
    if func=="mean": return r.mean()
    if func=="max":return r.max()
    if func=="min":return r.min()
    raise ValueError("Unknown rolling operation")


def build_daily_signals(data):
    """At date t, signals use values only through t-1.

    Daily historical observations are presumed end-of-day closes, so order
    executes on date t. A current-day onchain observation cannot itself
    fire an executable same-day sell.
    """
    df=data.copy().sort_index()
    req={"price_usd","mvrv_z","nupl","sopr"}
    if not req.issubset(df.columns):
        raise ValueError("Required price/onchain fields absent")
    if df.index.has_duplicates or not isinstance(df.index,pd.DatetimeIndex):
        raise ValueError("Need unique dated daily observations")
    for key in req:
        if not np.isfinite(df[key].to_numpy(dtype=float)).all():
            raise ValueError(f"Invalid/missing observations: {key}")
    if df["price_usd"].le(0).any():
        raise ValueError("Nonpositive BTC prices")

    px=df["price_usd"]
    prior=px.shift(1)
    slow200=_prior_rolling(px,200)
    slow350=_prior_rolling(px,350)
    fast111=_prior_rolling(px,111)
    ma50=_prior_rolling(px,50)
    ma50_old=ma50.shift(14)
    high365=_prior_rolling(px,365)
    high90=_prior_rolling(px,90)
    low365=_prior_rolling(px,365,func="min")
    # Prefix percentiles: distribution observed strictly *before* this date
    # (each observation's percentile excludes its own value).
    risk_m=df["mvrv_z"].shift(1)
    risk_n=df["nupl"].shift(1)
    risk_s=df["sopr"].shift(1)
    percentile_m=np.full(len(df),np.nan)
    percentile_n=np.full(len(df),np.nan)
    for i in range(730,len(df)):
        start=max(0,i-1095)
        hist_m=df["mvrv_z"].iloc[start:i].to_numpy(dtype=float)
        hist_n=df["nupl"].iloc[start:i].to_numpy(dtype=float)
        if len(hist_m)>=730:
            percentile_m[i]=float(np.mean(hist_m<=float(risk_m.iloc[i])))
            percentile_n[i]=float(np.mean(hist_n<=float(risk_n.iloc[i])))

    days_from_halving=[]
    for t in df.index:
        preceding=HALVINGS[HALVINGS<t]
        days_from_halving.append((t-preceding[-1]).days if len(preceding) else -1)
    result=pd.DataFrame(index=df.index)
    result["price_usd"]=px
    result["mvrv_z_prior"]=risk_m
    result["nupl_prior"]=risk_n
    result["sopr_prior"]=risk_s
    result["ma50_prior"]=ma50
    result["ma200_prior"]=slow200
    result["ma350_prior"]=slow350
    result["pi_ratio_prior"]=fast111/(2*slow350)
    result["ma50_declining"]=ma50.lt(ma50_old)
    result["drawdown90_prior"]=(1-prior/high90).clip(lower=0)
    result["drawdown365_prior"]=(1-prior/high365).clip(lower=0)
    result["near_annual_high_prior"]=prior.ge(high365*.97)
    result["upswing_prior"]=prior.div(low365).ge(1.5)
    result["halving_age_days"]=days_from_halving

    # A: Strict historical, fixed classic euphoria trigger.
    result["classic_euphoria"]=risk_m.ge(7.)|risk_n.ge(.75)
    # Pi: *event* a rare 111-day vs 2*350-day cross, computed using
    # prior-day averages, not current-day indicator values.
    pi=result["pi_ratio_prior"]
    result["pi_top_cross"]=pi.ge(1.) & pi.shift(1).lt(1.)
    # B: Premature/silent thresholds addressed with prior-only
    # 3-year historical percentile. Percentiles can be misleading in
    # secular regime shifts and do not guarantee top detection.
    result["relative_euphoria"]=(percentile_m>=.95)&(percentile_n>=.90)
    # C: Price-only context + top failure: previously strong rally,
    # then 10% retracement below 90-day observed high + below 50day MA.
    result["trend_reversal"]=(
        result["upswing_prior"] &
        result["drawdown90_prior"].ge(.10) &
        prior.lt(ma50) & result["ma50_declining"]
    )
    # D: Halving maturity context independent of onchain extremes.
    # Warning near 52-week highs in 350-800 day post-halving window,
    # sell confirmation from 12% drawdown or 50DMA trend break.
    result["cycle_maturity_warning"]=(
        result["halving_age_days"].between(350,800) &
        result["near_annual_high_prior"]
    )
    # The latest *past* 120-day warning is used for confirmation.
    recent_warn=result["cycle_maturity_warning"].shift(1).rolling(
        120,min_periods=1).max().fillna(0).astype(bool)
    result["maturity_confirmed_reversal"]=(
        recent_warn & result["drawdown365_prior"].ge(.12) &
        prior.lt(ma50)
    )
    # E: price-only regime drawdown, no halving and no MVRV needed,
    # active if 20% below observed 90-day high AND a falling 50DMA.
    result["late_trend_break"]=(
        result["drawdown90_prior"].ge(.20) &
        prior.lt(ma50) &
        result["ma50_declining"]
    )
    return result


SIGNALS=(
    "classic_euphoria","pi_top_cross","relative_euphoria",
    "trend_reversal","cycle_maturity_warning",
    "maturity_confirmed_reversal","late_trend_break",
)


def distinct_events(series, *, separation_days=MIN_SEPARATION_DAYS):
    # Multiple consecutive "true" days form only one alert event.
    events=[]
    last=None
    for day,active in series.fillna(False).items():
        if not bool(active):continue
        if last is None or (day-last).days>=separation_days:
            events.append(day)
            last=day
    return events


def evaluate_alerts(frame, signals, *, peak_windows=PEAK_WINDOWS):
    if not frame.index.equals(signals.index):
        raise ValueError("Misaligned prices/signals")
    output={}
    for family in SIGNALS:
        events=distinct_events(signals[family])
        matched=[]
        for label,(s,e) in peak_windows.items():
            sub=frame.loc[s:e,"price_usd"]
            if sub.empty:continue
            peak_date=sub.idxmax()
            peak_price=float(sub.max())
            # A signal is considered near enough to help iff within
            # 140 days BEFORE and 56 days AFTER the eventual peak.
            left=peak_date-pd.Timedelta(days=140)
            right=peak_date+pd.Timedelta(days=56)
            near=[d for d in events if left<=d<=right]
            # The best warning is the nearest event; selection here
            # is scoring hindsight only, not trade execution.
            if near:
                chosen=min(near,key=lambda d:abs((d-peak_date).days))
                chosen_price=float(frame.loc[chosen,"price_usd"])
            else:chosen=chosen_price=None
            matched.append({
                "cycle":label,
                "peak_date_in_scoring_window":str(peak_date.date()),
                "peak_close_usd":round(peak_price,2),
                "alert_date":str(chosen.date()) if chosen is not None else None,
                "days_from_peak":(chosen-peak_date).days if chosen is not None else None,
                "alert_execution_close_usd":round(chosen_price,2) if chosen is not None else None,
                "sell_error_vs_peak_close_pct":(
                    round(max(0.,100*(1-chosen_price/peak_price)),3)
                    if chosen is not None else None),
                "not_found_in_plus_minus_window":chosen is None,
            })
        event_details=[]
        for event in events:
            if event < pd.Timestamp("2013-01-01",tz="UTC"):continue
            px=float(frame.loc[event,"price_usd"])
            future=frame.loc[(frame.index>event) &
                             (frame.index<=event+pd.Timedelta(days=365)),
                             "price_usd"]
            # Post-event 365-day full outcome must be observed, otherwise
            # label as *censored*, not a success or failure.
            complete=frame.index[-1]>=event+pd.Timedelta(days=365)
            drawdown=(100*(1-float(future.min())/px)
                      if complete and not future.empty else None)
            event_details.append({
                "date":str(event.date()),
                "price_usd":round(px,2),
                "complete_365day_future":complete,
                "subsequent_max_decline_pct":round(drawdown,3) if drawdown is not None else None,
                "followed_by_30pct_decline":(
                    bool(drawdown>=30) if drawdown is not None else None),
            })
        eligible=[r for r in event_details if r["complete_365day_future"]]
        output[family]={
            "evaluated_macro_peaks":len(matched),
            "peaks_with_nearby_alert":sum(not x["not_found_in_plus_minus_window"] for x in matched),
            "distinct_events_since_2013":len(event_details),
            "fully_followed_events":len(eligible),
            "events_followed_by_30pct_decline":sum(x["followed_by_30pct_decline"] for x in eligible),
            "censored_recent_events":sum(not x["complete_365day_future"] for x in event_details),
            "scored_peaks":matched,
            "alert_events":event_details,
        }
    return output


def audit():
    source=read_exported_history()
    data=source.loc[:pd.Timestamp("2026-10-07",tz="UTC")]
    signals=build_daily_signals(data)
    scores=evaluate_alerts(data,signals)
    return {
        "research_only":True,
        "price_data_start":str(data.index[0]),
        "price_data_end":str(data.index[-1]),
        "source_file_names":[FILE_MVRV,FILE_NUPL,FILE_SOPR],
        "source_export_date":"2026-10-06/07",
        "signal_period":"Each decision uses metrics/prices recorded strictly before execution date",
        "macro_window_scoring":"Peaks selected ex post within 2013, 2017, 2021, 2025 fixed named windows. Nearby alerts must lie 140 days BEFORE or 56 days AFTER observed peak.",
        "decline_followup":"30% decline within 365 days of alert close, censored if full 365-day future unavailable",
        "family_results":scores,
        "warnings":[
            "A fixed threshold that worked before 2021 can silently fail at recent peaks.",
            "The 2021 cycle had distinct April and November highs; alerts months before November can be too early.",
            "Historical onchain CSV exports were created in October 2026; publication vintages and revisions unverified.",
            "Known cycle windows and scores are evaluation hindsight, not inputs to signal detector.",
            "Multiple repeated alerts, signal lag, slippage, false sells and taxes matter; no live trades simulated.",
            "No indicator or combination can guarantee it detects every future BTC peak.",
            "No changes to Production, portfolio, validated master, or Research defaults.",
        ],
    }


def main():
    p=argparse.ArgumentParser()
    p.add_argument("--output",default="")
    args=p.parse_args()
    result=audit()
    text=json.dumps(result,indent=2,allow_nan=False)
    if args.output:
        Path(args.output).write_text(text+"\n",encoding="utf-8")
    print(text)


if __name__=="__main__":
    main()
