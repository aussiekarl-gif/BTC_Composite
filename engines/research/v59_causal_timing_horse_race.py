"""Research-only BTC/AUD entry timing horse race, using true computed V5.9 WF risk.

Historical public spot BTC/USD and AUD/USD FX, NOT historical executable ASX:IBIT.
No private portfolio data, automated orders, ntfy or Production changes.

All signals are taken on the previous Sunday BTC UTC close and hypothetical
purchases occur at the following Monday UTC BTC/AUD spot close reference.
No current/future bar can select the amount; price of execution is used ONLY
for settlement and mark-to-market. This is an approximation, not a valid
ASX open/ask or fill timestamp. Provider vintages are not independently
attested, and retrospective model design can still be overfit.
"""
from __future__ import annotations

import argparse
from datetime import date, datetime, timedelta, timezone
import json
import math
from pathlib import Path

import numpy as np
import pandas as pd
from engines.research import research_model as model
from engines.research.v59_dynamic_risk_policy import risk_buy_multiplier
from engines.research.v59_live_signal_snapshot import live_risk_params

CAPITAL_AUD = 510_000.
WEEKS = 104
FIXED_FEE_AUD = 3.
VARIABLE_BUY_FRICTION = .003    # illustrative 0.30% spread / slippage
ANNUAL_ETF_DRAG = .0025         # illustrative 0.25%, NOT verified ASX ETF fee
MAX_WEEKLY_FRACTION = .05
POLICIES = (
    "plain_1x", "risk_1x", "risk_2x", "risk_3x",
    "risk_3x_below_200wma", "risk_3x_10pct_below_200wma",
    "risk_3x_drawdown_25pct", "risk_3x_drawdown_40pct",
    "risk_3x_risk_le_020", "risk_3x_price_above_50dma",
    "risk_3x_50dma_rising", "risk_3x_below_200wma_or_40pct_drawdown",
)
# Report separately; no selection or independent-validated claim for partial.
CASH_YIELDS = (0., .05)
RESERVE_FRACTIONS = (0., .10)
FIRST_COHORT = date(2017, 1, 1)
LAST_COHORT = date(2024, 7, 1)
TRAIN_STARTS_THROUGH = date(2020, 1, 1)
HOLDOUT_STARTS_FROM = date(2022, 1, 1)


def policy_multiplier(policy: str, signal: dict) -> float:
    if policy not in POLICIES:
        raise ValueError("Unknown predeclared policy")
    risk = float(signal["risk_score"])
    if not math.isfinite(risk) or not 0 <= risk <= 1:
        raise ValueError("Risk is not a valid bounded R2 WF value")
    if signal.get("risk_score_source") != "Walk-forward Power Law":
        raise ValueError("Neutral or unknown risk source is not a trade signal")
    if policy == "plain_1x":
        return 1.
    mult = float(risk_buy_multiplier(risk))
    if policy == "risk_1x":
        return min(mult, 1.)
    if policy == "risk_2x":
        return min(mult, 2.)
    if policy == "risk_3x":
        return mult
    if policy == "risk_3x_risk_le_020":
        return mult if risk <= .20 else 0.
    ratio = float(signal.get("ratio_to_200wma", float("nan")))
    dd = float(signal.get("drawdown_365", float("nan")))
    sma50_ratio = float(signal.get("ratio_to_50dma", float("nan")))
    rising = signal.get("sma50_rising")
    if policy == "risk_3x_below_200wma":
        passed = math.isfinite(ratio) and ratio <= 1.0
    elif policy == "risk_3x_10pct_below_200wma":
        passed = math.isfinite(ratio) and ratio <= .90
    elif policy == "risk_3x_drawdown_25pct":
        passed = math.isfinite(dd) and dd <= -.25
    elif policy == "risk_3x_drawdown_40pct":
        passed = math.isfinite(dd) and dd <= -.40
    elif policy == "risk_3x_price_above_50dma":
        passed = math.isfinite(sma50_ratio) and sma50_ratio > 1.
    elif policy == "risk_3x_50dma_rising":
        passed = rising is True
    elif policy == "risk_3x_below_200wma_or_40pct_drawdown":
        passed = ((math.isfinite(ratio) and ratio <= 1.) or
                  (math.isfinite(dd) and dd <= -.40))
    else:
        raise ValueError("Unhandled policy")
    return mult if passed else 0.


def build_weekly_rows(scored: pd.DataFrame, fx: pd.Series) -> list[dict]:
    """Use Sunday signal, Monday execution, explicitly dated prior FX, no fallback."""
    if scored.empty or fx is None or fx.empty:
        raise ValueError("Missing market history or AUD/USD rates")
    data = scored.copy()
    data.index = pd.to_datetime(data.index, utc=True).floor("D")
    if data.index.has_duplicates or not data.index.is_monotonic_increasing:
        raise ValueError("Market days must be unique, ordered UTC dates")
    fx = fx.copy().sort_index()
    fx.index = pd.to_datetime(fx.index, utc=True).floor("D")
    if fx.index.has_duplicates:
        raise ValueError("FX has repeated dates")
    fx = pd.to_numeric(fx, errors="coerce").dropna()
    if fx.empty or not fx.gt(0).all():
        raise ValueError("No verified positive FX")
    weekly_ma = (pd.to_numeric(data["price"], errors="coerce")
                 .resample("W-SUN").last().rolling(200, min_periods=200).mean())
    sma50 = data["price"].rolling(50, min_periods=50).mean()
    sma50_old = sma50.shift(28)
    drawdown = data["price"] / data["price"].rolling(365, min_periods=365).max() - 1.
    rows = []
    for ts in data.index:
        if ts.weekday() != 0 or ts.date() < FIRST_COHORT:
            continue
        sunday = ts - pd.Timedelta(days=1)
        if sunday not in data.index:
            continue
        sig = data.loc[sunday]
        if str(sig.get("risk_score_source")) != "Walk-forward Power Law":
            continue
        risk, price_usd, spot_usd = (
            float(sig.get("risk_score", float("nan"))),
            float(data.at[ts, "price"]), float(sig["price"])
        )
        if not (math.isfinite(risk) and 0 <= risk <= 1 and
                math.isfinite(price_usd) and price_usd > 0 and
                math.isfinite(spot_usd) and spot_usd > 0):
            continue
        # Monday's official FX fix is not necessarily published by ASX open.
        # Use strictly PREVIOUS Sunday's latest available fix (usually Friday).
        fx_pos = fx.index.searchsorted(sunday, side="right") - 1
        if fx_pos < 0:
            continue
        fx_day, usd_per_aud = fx.index[fx_pos], float(fx.iloc[fx_pos])
        # Business-day rates can be delayed a weekend; never allow
        # unknown or >5-day-old rates or any future price.
        if not (0 <= (ts - fx_day).days <= 5 and math.isfinite(usd_per_aud)
                and usd_per_aud > 0):
            continue
        wma = float(weekly_ma.loc[sunday]) if sunday in weekly_ma.index else float("nan")
        ma = float(sma50.loc[sunday])
        ma_old = float(sma50_old.loc[sunday])
        rows.append({
            "date": ts.date(), "signal_date": sunday.date(),
            "btc_price_aud": price_usd / usd_per_aud,
            "price_usd": price_usd,
            "usd_per_aud": usd_per_aud, "fx_date": fx_day.date(),
            "risk_score": risk, "risk_score_source": str(sig["risk_score_source"]),
            "ratio_to_200wma": (spot_usd / wma if math.isfinite(wma) and wma > 0 else float("nan")),
            "drawdown_365": float(drawdown.loc[sunday]),
            "ratio_to_50dma": (spot_usd / ma if math.isfinite(ma) and ma > 0 else float("nan")),
            "sma50_rising": (bool(ma > ma_old) if math.isfinite(ma_old) and math.isfinite(ma) else None),
        })
    if len(rows) < 100:
        raise ValueError("Insufficient complete lagged weekly BTC/FX/R2 history")
    return rows


def simulate(rows: list[dict], *, policy: str, cash_yield: float,
             reserve_fraction: float, capital: float=CAPITAL_AUD,
             review_date: date | None=None, max_fraction: float=MAX_WEEKLY_FRACTION,
             buy_friction: float=VARIABLE_BUY_FRICTION,
             fixed_fee: float=FIXED_FEE_AUD, etf_drag: float=ANNUAL_ETF_DRAG,
             initial_btc_fraction: float=0.) -> dict:
    """Self-financing 104-week matched cohort with interest on uninvested cash."""
    if not rows or policy not in POLICIES:
        raise ValueError("No rows or invalid policy")
    if not all(math.isfinite(x) for x in
               (cash_yield, reserve_fraction, capital, max_fraction, buy_friction, fixed_fee, etf_drag, initial_btc_fraction)):
        raise ValueError("Financial input nonfinite")
    if not (0 <= cash_yield < 1 and 0 <= reserve_fraction <= 1 and capital > 0
            and 0 < max_fraction <= 1 and 0 <= buy_friction < 1
            and 0 <= fixed_fee < capital and 0 <= etf_drag < 1
            and 0 <= initial_btc_fraction <= 1):
        raise ValueError("Invalid financial input")
    review = review_date or rows[0]["date"] + timedelta(weeks=WEEKS)
    first_price=float(rows[0]["btc_price_aud"])
    if not math.isfinite(first_price) or first_price <= 0:
        raise ValueError("Invalid initial BTC/AUD mark for existing holdings")
    # Already-owned BTC is valued at cohort entry, not bought again.
    cash = capital * (1.-initial_btc_fraction)
    btc = capital * initial_btc_fraction / first_price
    invested, paid_cost, interest, nbuy = 0., 0., 0., 0
    initial_day = rows[0]["date"]
    prev_day = initial_day
    reserve = reserve_fraction * capital
    peak, worst_dd = capital, 0.
    first_date = None
    spent_first_26w = 0.
    for i, row in enumerate(rows):
        day = row["date"]
        if not isinstance(day, date) or (i > 0 and day <= prev_day):
            raise ValueError("Unsorted or duplicate execution dates")
        if (day - row["signal_date"]).days != 1:
            raise ValueError("Missing strictly previous daily signal")
        passed_days = (day - prev_day).days if i > 0 else 0
        if i > 0 and passed_days != 7:
            raise ValueError("Weekly cohort has a missing execution date")
        price = float(row["btc_price_aud"])
        if not math.isfinite(price) or price <= 0:
            raise ValueError("Invalid execution price")
        # Interest compounded on cash only; an illustrative AAA-like return.
        earned = cash * ((1. + cash_yield) ** (passed_days / 365.25) - 1.)
        cash += earned
        interest += earned
        btc *= (1. - etf_drag) ** (passed_days / 365.25)
        prev_day = day
        available = max(0., cash-reserve)
        weeks_left = max((review - day).days / 7., 1.)
        # Review date stops BUYs; it never forces expenditure or liquidation.
        weight = policy_multiplier(policy, row) if day <= review else 0.
        spend = min(available, max(0., available / weeks_left * weight),
                    capital * max_fraction)
        if spend > fixed_fee + .01:
            net = (spend - fixed_fee) * (1. - buy_friction)
            cash -= spend
            btc += net / price
            invested += spend
            paid_cost += spend-net
            nbuy += 1
            if first_date is None:
                first_date = day
            if (day-initial_day).days < 26*7:
                spent_first_26w += spend
        equity = cash + btc*price
        peak = max(peak, equity)
        worst_dd = min(worst_dd, equity/peak-1.)
        if cash < reserve-1e-5 or btc < 0:
            raise AssertionError("Cash reserve, leverage or negative BTC violation")
    terminal = float(rows[-1]["btc_price_aud"])
    equity = cash + btc*terminal
    return {
        "btc_units": btc, "cash_aud": cash, "equity_aud": equity,
        "terminal_btc_equivalent": btc+cash/terminal,
        "drawdown_pct":100*worst_dd, "btc_50pct_shock_equity_aud":cash+btc*terminal*.5,
        "net_invested_aud": invested, "interest_earned_aud": interest,
        "initial_btc_fraction":initial_btc_fraction,
        "total_cost_aud":paid_cost, "buy_count":nbuy,
        "first_buy_date":first_date.isoformat() if first_date else None,
        "deployed_fraction_of_initial":invested/capital,
        "spent_first_26weeks_pct_initial":spent_first_26w/capital,
        "average_aud_spend_per_btc":invested / btc if btc > 0 else None,
    }


def cohort_windows(rows: list[dict]) -> list[dict]:
    """Full 104-week Jan/Jul 2017–2024 cohorts. No right-censored winners."""
    start_days = [date(y, m, 1) for y in range(2017,2025) for m in (1,7)]
    windows = []
    for anchor in start_days:
        if anchor > LAST_COHORT:
            continue
        cohort = [r for r in rows if anchor <= r["date"] < anchor+timedelta(weeks=WEEKS)]
        if len(cohort) != WEEKS or any(
                (b["date"]-a["date"]).days != 7
                for a,b in zip(cohort,cohort[1:])):
            continue
        split = ("TRAIN" if anchor <= TRAIN_STARTS_THROUGH else
                 "HISTORICAL_HOLDOUT" if anchor >= HOLDOUT_STARTS_FROM else "BRIDGE_EXCLUDED")
        windows.append({
            "anchor":anchor.isoformat(), "start":cohort[0]["date"].isoformat(),
            "end":cohort[-1]["date"].isoformat(),"split":split,"rows":cohort,
            "review_date":anchor+timedelta(weeks=WEEKS)
        })
    if not windows:
        raise ValueError("No fully supported 104-week cohorts")
    return windows


def horizon_sensitivity(windows, *, capital=CAPITAL_AUD):
    """Common 104-week measurement; buying paused after review at 39..130w.

    130-week review is incomplete by the 104-week measurement date;
    unspent interest-earning cash must always be reported.
    """
    relevant=("plain_1x","risk_1x","risk_2x","risk_3x","risk_3x_risk_le_020")
    records=[]
    for w in windows:
        anchor=date.fromisoformat(w["anchor"])
        for cash_yield in CASH_YIELDS:
            for reserve in RESERVE_FRACTIONS:
                for horizon in (39,52,60,78,104,130):
                    for policy in relevant:
                        result=simulate(w["rows"],policy=policy,cash_yield=cash_yield,
                                        reserve_fraction=reserve,capital=capital,
                                        review_date=anchor+timedelta(weeks=horizon))
                        records.append({"anchor":w["anchor"],"split":w["split"],
                                        "policy":policy,"cash_yield":cash_yield,
                                        "reserve_fraction":reserve,"horizon":horizon,
                                        **result})
    baseline={(r["anchor"],r["cash_yield"],r["reserve_fraction"]):r
              for r in records if r["policy"]=="risk_1x" and r["horizon"]==104}
    for rec in records:
        b=baseline[(rec["anchor"],rec["cash_yield"],rec["reserve_fraction"])]
        rec["equity_uplift_pct"]=100*(rec["equity_aud"]/b["equity_aud"]-1)
        rec["drawdown_change_pp"]=rec["drawdown_pct"]-b["drawdown_pct"]
    summary=[]
    for split in ("TRAIN","HISTORICAL_HOLDOUT"):
        for cash_yield in CASH_YIELDS:
            for reserve in RESERVE_FRACTIONS:
                for horizon in (39,52,60,78,104,130):
                    for policy in relevant:
                        selected=[r for r in records if r["split"]==split
                                  and r["cash_yield"]==cash_yield
                                  and r["reserve_fraction"]==reserve
                                  and r["horizon"]==horizon and r["policy"]==policy]
                        if not selected:continue
                        summary.append({"split":split,"cash_yield":cash_yield,
                            "reserve_fraction":reserve,"review_after_weeks":horizon,
                            "policy":policy,"cohorts":len(selected),
                            "median_equity_uplift_pct":float(np.median([x["equity_uplift_pct"] for x in selected])),
                            "worst_equity_uplift_pct":min(x["equity_uplift_pct"] for x in selected),
                            "median_deployed_fraction":float(np.median([x["deployed_fraction_of_initial"] for x in selected])),
                            "median_drawdown_change_pp":float(np.median([x["drawdown_change_pp"] for x in selected])),
                        })
    return summary


def existing_btc_exposure_sensitivity(windows, *, capital=CAPITAL_AUD):
    """Same preexisting ~41% BTC position across policies; time only cash buys."""
    exposure=.41
    reports=[]
    for w in windows:
        for cash_yield in CASH_YIELDS:
            for reserve in RESERVE_FRACTIONS:
                for policy in POLICIES:
                    rec=simulate(w["rows"],policy=policy,cash_yield=cash_yield,
                         reserve_fraction=reserve,capital=capital,
                         review_date=w["review_date"],initial_btc_fraction=exposure)
                    reports.append({"anchor":w["anchor"],"split":w["split"],
                       "cash_yield":cash_yield,"reserve_fraction":reserve,
                       "policy":policy,**rec})
    control={(r["anchor"],r["cash_yield"],r["reserve_fraction"]):r
             for r in reports if r["policy"]=="risk_1x"}
    for r in reports:
        b=control[(r["anchor"],r["cash_yield"],r["reserve_fraction"])]
        r["equity_gain_pct"]=100*(r["equity_aud"]/b["equity_aud"]-1)
        r["drawdown_gap_pp"]=r["drawdown_pct"]-b["drawdown_pct"]
    out=[]
    for split in ("TRAIN","HISTORICAL_HOLDOUT"):
        for cash_yield in CASH_YIELDS:
            for reserve in RESERVE_FRACTIONS:
                for policy in POLICIES:
                    selected=[r for r in reports if r["split"]==split
                              and r["cash_yield"]==cash_yield
                              and r["reserve_fraction"]==reserve
                              and r["policy"]==policy]
                    if not selected:continue
                    out.append({"split":split,"policy":policy,
                       "cash_yield":cash_yield,"reserve_fraction":reserve,
                       "initial_btc_fraction":exposure,"cohorts":len(selected),
                       "median_equity_uplift_pct":float(np.median([r["equity_gain_pct"] for r in selected])),
                       "worst_equity_uplift_pct":min(r["equity_gain_pct"] for r in selected),
                       "equity_win_fraction":sum(r["equity_gain_pct"]>0 for r in selected)/len(selected),
                       "median_new_cash_deployed_frac_initial":float(np.median(
                           [r["deployed_fraction_of_initial"] for r in selected])),
                       "median_drawdown_change_pp":float(np.median(
                           [r["drawdown_gap_pp"] for r in selected])),
                    })
    return out


def evaluate(rows: list[dict], *, capital: float=CAPITAL_AUD) -> dict:
    windows = cohort_windows(rows)
    trials = []
    for w in windows:
        for annual_yield in CASH_YIELDS:
            for reserve in RESERVE_FRACTIONS:
                for policy in POLICIES:
                    res = simulate(w["rows"], policy=policy, cash_yield=annual_yield,
                                   reserve_fraction=reserve, capital=capital,
                                   review_date=w["review_date"])
                    trials.append({**{k:w[k] for k in ("anchor","start","end","split")},
                                   "cash_yield":annual_yield,"reserve_fraction":reserve,
                                   "policy":policy, **res})
    lookup = {(v["anchor"],v["cash_yield"],v["reserve_fraction"],v["policy"]):v
              for v in trials}
    for row in trials:
        control = lookup[(row["anchor"],row["cash_yield"],row["reserve_fraction"],"risk_1x")]
        row["equity_uplift_vs_risk1x_pct"] = 100*(row["equity_aud"]/control["equity_aud"]-1)
        row["btc_eq_uplift_vs_risk1x_pct"] = 100*(row["terminal_btc_equivalent"]/control["terminal_btc_equivalent"]-1)
        row["drawdown_change_vs_risk1x_pp"] = row["drawdown_pct"]-control["drawdown_pct"]
    summary=[]
    for annual_yield in CASH_YIELDS:
        for reserve in RESERVE_FRACTIONS:
            for split in ("TRAIN","HISTORICAL_HOLDOUT"):
                for policy in POLICIES:
                    rec=[r for r in trials if r["cash_yield"]==annual_yield and
                         r["reserve_fraction"]==reserve and r["split"]==split and r["policy"]==policy]
                    if not rec: continue
                    summary.append({
                        "split":split,"cash_yield":annual_yield,"reserve_fraction":reserve,
                        "policy":policy,"cohorts":len(rec),
                        "median_equity_uplift_pct":float(np.median([r["equity_uplift_vs_risk1x_pct"] for r in rec])),
                        "worst_equity_uplift_pct":min(r["equity_uplift_vs_risk1x_pct"] for r in rec),
                        "median_btc_equiv_uplift_pct":float(np.median([r["btc_eq_uplift_vs_risk1x_pct"] for r in rec])),
                        "equity_win_fraction":sum(r["equity_uplift_vs_risk1x_pct"]>0 for r in rec)/len(rec),
                        "median_deployed_frac":float(np.median([r["deployed_fraction_of_initial"] for r in rec])),
                        "median_drawdown_change_pp":float(np.median([r["drawdown_change_vs_risk1x_pp"] for r in rec])),
                        "median_early_26w_spend_pct_initial":float(np.median([r["spent_first_26weeks_pct_initial"] for r in rec]))*100,
                    })
    # Predeclared simple TRAIN-only criterion, then test on later historical
    # cohort dates. Historical holdout is not truly independent of 2026 design.
    considered=[s for s in summary if s["split"]=="TRAIN"
                 and s["cash_yield"]==.05 and s["reserve_fraction"]==0.
                 and s["median_deployed_frac"]>=.50]
    selected=max(considered,key=lambda x:(x["median_btc_equiv_uplift_pct"],
                                             x["worst_equity_uplift_pct"],
                                             x["policy"])) if considered else None
    test=next((s for s in summary if selected and s["split"]=="HISTORICAL_HOLDOUT"
               and s["cash_yield"]==.05 and s["reserve_fraction"]==0.
               and s["policy"]==selected["policy"]),None)
    return {
        "status":"RESEARCH_ONLY_RETROSPECTIVE_NOT_POINT_IN_TIME_PROVIDER_VINTAGE_VERIFIED",
        "no_promotion_or_trade_authorisation":True,
        "starting_capital_aud":capital,
        "lookback_context": "2012+ continuously computed V5.9 research WF Power Law",
        "source_risk":"Walk-forward Power Law calculated afresh from public price history",
        "signal_timing":"Previous Sunday UTC price/risk/200WMA/365d drawdown/50DMA; hypothetical next Monday BTC/AUD spot price",
        "execution_instrument":"Historical BTC/AUD spot proxy ONLY; no historical ASX:IBIT fills",
        "assumptions":{"cash_yields_annual_before_tax":CASH_YIELDS,
                       "protected_reserve_fractions":RESERVE_FRACTIONS,
                       "entry_cost_fraction":VARIABLE_BUY_FRICTION,
                       "flat_fee_per_buy_aud":FIXED_FEE_AUD,
                       "hypothetical_etf_drag_annual":ANNUAL_ETF_DRAG,
                       "max_weekly_fraction_of_starting_capital":MAX_WEEKLY_FRACTION,
                       "cohort_weeks":WEEKS},
        "data_last_execution_date":rows[-1]["date"].isoformat(),
        "number_matched_weekly_rows":len(rows),
        "completed_cohorts":len(windows),
        "train_selected_by_predeclared_score":selected,
        "historical_holdout_outcome_for_train_selection":test,
        "caveats":[
            "Historical public prices and FX can have revisions; provider publication vintages not attested.",
            "Chosen policies were designed after examining BTC history; historical holdout is not truly untouched.",
            "Two-year overlapping Jan/Jul cohorts share price paths and do not add independent halving cycles.",
            "Profitably timing bottoms and detecting confirmed later troughs are not assumed; no hindsight lows used in decisions.",
            "No executable ASX ETF fills, spreads, taxes, AAA distributions reinvestment mechanics or cash account access.",
            "5% cash return and ETF drag are explicit illustrative assumptions, NOT guaranteed historical rates.",
            "Observed BTC positions are virtual 2017+ cohorts, NOT user's real Nov 2026 BTC/AAA holdings.",
            "No claim of optimal timing until forward, provider-vintage and true out-of-sample validation.",
        ],
        "summary":summary,"trials":trials,
        "review_horizon_sensitivity":horizon_sensitivity(windows,capital=capital),
        "existing_btc_exposure_sensitivity":existing_btc_exposure_sensitivity(windows,capital=capital),
    }


def fetch_and_evaluate() -> dict:
    now=datetime.now(timezone.utc)
    start=model.RESEARCH_PL_HISTORY_START.to_pydatetime()
    btc=model.fetch_btc_history(start,now)
    fx=model.fetch_aud_usd_rates(start,now)
    if btc is None or btc.empty or fx is None or fx.empty:
        raise RuntimeError("BTC or real historical FX unavailable; refusing synthetic FX fallback")
    # Mirror live DCA Today: install the expected optional-factor columns
    # as unavailable (NaN); Research WF Power Law uses its own causal fit.
    priced=model.merge_bgeometrics(btc,pd.DataFrame())
    scored=model.add_risk_indicators(priced,"Research WF Power Law",live_risk_params())
    rows=build_weekly_rows(scored,fx)
    result=evaluate(rows)
    result["provider_input_btc_first_last"]=[str(btc.index.min()),str(btc.index.max())]
    result["provider_input_fx_first_last"]=[str(fx.index.min()),str(fx.index.max())]
    return result


def main():
    p=argparse.ArgumentParser()
    p.add_argument("--out",type=Path,default=Path("artifacts/v59_buy_timing_horse_race.json"))
    args=p.parse_args()
    try:
        report=fetch_and_evaluate()
    except Exception as exc:
        report={"status":"RESEARCH_RUN_BLOCKED","error_type":type(exc).__name__,
                "error":str(exc),"no_promotion_or_trade_authorisation":True}
    args.out.parent.mkdir(parents=True,exist_ok=True)
    args.out.write_text(json.dumps(report,indent=2,default=str,allow_nan=False)+"\n")
    if report.get("status")=="RESEARCH_RUN_BLOCKED":
        print(json.dumps(report))
        return 2
    print(json.dumps({
        "status":report["status"],
        "completed_cohorts":report["completed_cohorts"],
        "weekly_rows":report["number_matched_weekly_rows"],
        "btc_input":report["provider_input_btc_first_last"],
        "fx_input":report["provider_input_fx_first_last"],
        "train_selected":report["train_selected_by_predeclared_score"],
        "holdout_result":report["historical_holdout_outcome_for_train_selection"],
    },default=str))
    for row in report["summary"]:
        if row["cash_yield"]==.05 and row["reserve_fraction"]==0.:
            print("TIMING_RESULT",json.dumps(row,sort_keys=True))
        elif row["policy"] in ("risk_1x","risk_2x","risk_3x","risk_3x_risk_le_020"):
            print("CASH_RESERVE_SENSITIVITY",json.dumps(row,sort_keys=True))
    for row in report["review_horizon_sensitivity"]:
        if (row["split"]=="HISTORICAL_HOLDOUT" and row["cash_yield"]==.05
                and row["reserve_fraction"]==0.):
            print("HORIZON_RESULT",json.dumps(row,sort_keys=True))
    for row in report["existing_btc_exposure_sensitivity"]:
        if (row["split"]=="HISTORICAL_HOLDOUT" and row["cash_yield"]==.05
                and row["reserve_fraction"]==0.):
            print("EXISTING_BTC_RESULT",json.dumps(row,sort_keys=True))
    return 0


if __name__=="__main__":
    raise SystemExit(main())
