"""200-week MA bear-entry episode comparison: 17-week DCA versus V5.9.

RESEARCH ONLY. Genuine reconstructed prior-Sunday BTC/USD risk + 200WMA
signals; hypothetical Monday BTC/AUD spot proxy, not ASX:IBIT executions.
An anchor is the FIRST downward weekly crossing, never the hindsight low.
"""
from __future__ import annotations

from datetime import date, timedelta
import math
from statistics import median

from engines.research import v59_causal_timing_horse_race as base

CAP_AUD = 25_500.             # 5% of user's ORIGINAL A$510,000
FRESH_CASH_AUD = 500_000.
EXISTING_TOTAL_AUD = 510_000.
EXISTING_BTC_FRACTION = .41
ANNUAL_CASH_YIELD = .05
HORIZON = 104
STAGGER_WEEKS = 17
CAP_COMPLIANT_WEEKS = 20
SOURCE = "Walk-forward Power Law"
REFERENCE = ("risk_1x", "risk_3x", "risk_3x_risk_le_020",
             "risk_3x_below_200wma")
POLICIES = (
    "17_calendar_unrestricted", "17_calendar_capped",
    "20_calendar_capped", "17_eligible_below_unrestricted",
    "20_eligible_below_capped", "hold_cash",
) + REFERENCE
CASES = (
    ("fresh_AUD500k", FRESH_CASH_AUD, 0.),
    ("41pct_preexisting_AUD510k", EXISTING_TOTAL_AUD, EXISTING_BTC_FRACTION),
)


def historical_crossings(rows: list[dict], threshold: float=1.) -> list[dict]:
    """Crossings of prior-Sunday BTC price down through the prior-Sunday WMA.

    The *previous* observed weekly bar must be contiguous and above the
    threshold. A weak historical risk source is never an assumed cheap signal.
    All qualifying anchor dates are included, even closely spaced recrosses.
    """
    if not 0 < threshold <= 1.2:
        raise ValueError("Invalid threshold")
    seen=[]
    for prev,row in zip(rows,rows[1:]):
        if (row["date"]-prev["date"]).days != 7:
            continue
        if (row.get("risk_score_source") != SOURCE or
                prev.get("risk_score_source") != SOURCE):
            continue
        a=float(prev.get("ratio_to_200wma",math.nan))
        b=float(row.get("ratio_to_200wma",math.nan))
        if math.isfinite(a) and math.isfinite(b) and a>threshold and 0<b<=threshold:
            seen.append({"crossing_monday":row["date"],"sunday_signal":row["signal_date"],
                         "sunday_wma_ratio":b,"previous_ratio":a,
                         "threshold":threshold})
    return seen


def consecutive_weeks_below(rows: list[dict], start_index: int, threshold: float=1.) -> int:
    n=0
    for j in range(start_index,len(rows)):
        if j>start_index and (rows[j]["date"]-rows[j-1]["date"]).days != 7:
            break
        ratio=float(rows[j].get("ratio_to_200wma",math.nan))
        if not math.isfinite(ratio) or not ratio<=threshold:break
        n+=1
    return n


def eligible_cohorts(rows: list[dict]) -> list[dict]:
    """Select one independently rooted crossing per calendar year, 2018–2024.

    This comparison fixes the entry trigger first, instead of selecting the
    best bottom retrospectively. One-year tie break is the EARLIEST crossing.
    Year selection is a descriptive historical sample, not a claim of
    independent market cycles. The 2020 event may not survive Sunday close.
    """
    crossings=historical_crossings(rows)
    indexed={r["date"]:i for i,r in enumerate(rows)}
    first_per_year={}
    for cross in crossings:
        year=cross["crossing_monday"].year
        if year<2018 or year>2024 or year in first_per_year: continue
        i=indexed[cross["crossing_monday"]]
        window=rows[i:i+HORIZON]
        if len(window)!=HORIZON or any(
             (b["date"]-a["date"]).days!=7 for a,b in zip(window,window[1:])):
            continue
        first_per_year[year]={
            "event_year":year,"start":cross["crossing_monday"].isoformat(),
            "initial_sunday_ratio_to_200wma":cross["sunday_wma_ratio"],
            "consecutive_sunday_closes_below_200wma":consecutive_weeks_below(rows,i),
            "rows":window,
        }
    return list(first_per_year.values())


def candidate_spend(*, policy: str, week: int, row: dict,
                    spent: float, starting_cash: float,
                    eligible_weeks_already: int,
                    cash: float, review: date, prev_date: date) -> float:
    if policy not in POLICIES or starting_cash<=0 or spent<0:
        raise ValueError("Invalid candidate")
    ratio=float(row.get("ratio_to_200wma",math.nan))
    if not math.isfinite(ratio) or ratio<=0:
        raise ValueError("Missing prior Sunday moving-average observation")
    if policy in REFERENCE:
        weight=base.policy_multiplier(policy,row)
        weeks_left=max((review-row["date"]).days/7.,1.)
        return max(0.,cash)/weeks_left * weight
    if policy=="hold_cash":
        return 0.
    if policy=="17_calendar_unrestricted":
        return starting_cash/STAGGER_WEEKS if week<17 else 0.
    if policy=="17_calendar_capped":
        return min(starting_cash/STAGGER_WEEKS,CAP_AUD) if week<17 else 0.
    if policy=="20_calendar_capped":
        return starting_cash/CAP_COMPLIANT_WEEKS if week<20 else 0.
    if policy=="17_eligible_below_unrestricted":
        return (starting_cash/STAGGER_WEEKS
                if ratio<=1. and eligible_weeks_already<17 else 0.)
    if policy=="20_eligible_below_capped":
        return (starting_cash/CAP_COMPLIANT_WEEKS
                if ratio<=1. and eligible_weeks_already<20 else 0.)
    raise ValueError("Unrecognised episode policy")


def replay(rows: list[dict], *, policy: str, capital:float,
           starting_btc_fraction:float=0., cash_yield:float=.05) -> dict:
    """Match base.simulate's costs, ETF drag, cash yield, and 104-week mark.

    Adds an *additional* immediately-after-17-week checkpoint. 17-week
    unrestricted tests are expressly noncompliant with A$25.5k weekly cap.
    """
    if len(rows)!=HORIZON or policy not in POLICIES:
        raise ValueError("Require complete 104-week event and declared policy")
    if not 0<=starting_btc_fraction<=1 or not 0<=cash_yield<1 or capital<=0:
        raise ValueError("Invalid cash/holdings")
    starting_cash=capital*(1-starting_btc_fraction)
    cash=starting_cash
    first_price=float(rows[0]["btc_price_aud"])
    btc=capital*starting_btc_fraction/first_price
    bought_btc=0.
    spent=0.
    buy_count=0
    prices=[]
    prev_day=rows[0]["date"]
    eligible_weeks=0
    peak=capital
    max_drawdown=0.
    checkpoint=None
    review=rows[0]["date"]+timedelta(weeks=HORIZON)
    biggest_weekly=0.
    for i,row in enumerate(rows):
        day=row["date"]
        if day!=rows[0]["date"]+timedelta(weeks=i) or (day-row["signal_date"]).days!=1:
            raise ValueError("Missing week, invalid Sunday-to-Monday lag")
        if row.get("risk_score_source")!=SOURCE:
            raise ValueError("Research risk source not attested")
        price=float(row["btc_price_aud"])
        if not math.isfinite(price) or price<=0:
            raise ValueError("Invalid BTC/AUD price")
        days=(day-prev_day).days if i else 0
        cash*=((1+cash_yield)**(days/365.25))
        btc*=(1-base.ANNUAL_ETF_DRAG)**(days/365.25)
        prev_day=day
        gross=candidate_spend(policy=policy,week=i,row=row,spent=spent,
                               starting_cash=starting_cash,eligible_weeks_already=eligible_weeks,
                               cash=cash,review=review,prev_date=prev_day)
        if policy in REFERENCE or policy in ("17_calendar_capped","20_calendar_capped",
                                            "20_eligible_below_capped"):
            gross=min(gross,CAP_AUD)
        # PR #259 risk baselines may reinvest earned cash interest; match
        # its exact behaviour. Fixed-tranche policies deliberately invest
        # only the initial allocated cash budget and leave interest as cash.
        budget_left=(cash if policy in REFERENCE else max(0.,starting_cash-spent))
        gross=max(0.,min(gross,cash,budget_left))
        if gross>base.FIXED_FEE_AUD+.01:
            net=(gross-base.FIXED_FEE_AUD)*(1-base.VARIABLE_BUY_FRICTION)
            cash-=gross
            btc+=net/price
            bought_btc+=net/price
            spent+=gross
            buy_count+=1
            biggest_weekly=max(biggest_weekly,gross)
        if (policy in ("17_eligible_below_unrestricted","20_eligible_below_capped")
                and float(row["ratio_to_200wma"])<=1.):
            eligible_weeks+=1
        peak=max(peak,cash+btc*price)
        max_drawdown=min(max_drawdown,(cash+btc*price)/peak-1.)
        if cash < -1e-5 or btc<0:
            raise AssertionError("No leverage / negative BTC")
        if policy not in ("17_calendar_unrestricted","17_eligible_below_unrestricted"):
            if gross>CAP_AUD+1e-6:
                raise AssertionError("Actual weekly limit violated")
        prices.append(price)
        if i==16:
            checkpoint={
                "btc_held_after_week17":btc,
                "new_btc_bought_before_drag_week17":bought_btc,
                "cash_after_week17_aud":cash,
                "spent_by_week17_aud":spent,
                "equity_after_week17_aud":cash+btc*price,
                "reference_price_after_week17_aud":price,
            }
    assert checkpoint is not None
    return {
        "policy":policy,
        "cash_yield":cash_yield,
        "capital_aud":capital,
        "starting_btc_fraction":starting_btc_fraction,
        "btc_held_after_104w":btc,
        "new_btc_bought_before_drag_104w":bought_btc,
        "cash_after_104w_aud":cash,
        "portfolio_after_104w_aud":cash+btc*prices[-1],
        "btc_equivalent_if_all_cash_converted_at_104w":btc+cash/prices[-1],
        "spent_aud":spent,
        "number_of_buys":buy_count,
        "biggest_weekly_buy_aud":biggest_weekly,
        "median_200wma_17w_ratio":median(float(r["ratio_to_200wma"]) for r in rows[:17]),
        "max_drawdown_pct":max_drawdown*100,
        "original_cap_violated":biggest_weekly>CAP_AUD+1e-5,
        **checkpoint,
    }


def evaluate(rows:list[dict]) -> dict:
    events=eligible_cohorts(rows)
    if not events:
        raise ValueError("No full 104w 200WMA crossing found in real data")
    out=[]
    for case_name,capital,initial_fraction in CASES:
        for event in events:
            variants={}
            for policy in POLICIES:
                variants[policy]=replay(event["rows"],policy=policy,capital=capital,
                                        starting_btc_fraction=initial_fraction)
            compare=variants["risk_3x_risk_le_020"]
            summary={name:{
                "btc_week17":v["btc_held_after_week17"],
                "btc_week104":v["btc_held_after_104w"],
                "new_btc_gross_week17":v["new_btc_bought_before_drag_week17"],
                "cash_week17_aud":v["cash_after_week17_aud"],
                "cash_week104_aud":v["cash_after_104w_aud"],
                "total_value_week104_aud":v["portfolio_after_104w_aud"],
                "value_vs_strict3x_week104_pct":100*(v["portfolio_after_104w_aud"]/
                    compare["portfolio_after_104w_aud"]-1),
                "btc_vs_strict3x_week104_pct":100*(v["btc_held_after_104w"]/
                    compare["btc_held_after_104w"]-1),
                "invested_aud":v["spent_aud"],
                "buys":v["number_of_buys"],
                "peak_weekly_spend_aud":v["biggest_weekly_buy_aud"],
                "violates_AUD25500_cap":v["original_cap_violated"],
                "worst_portfolio_drawdown_pct":v["max_drawdown_pct"],
            } for name,v in variants.items()}
            out.append({
                "case":case_name,"event_year":event["event_year"],
                "first_buy_monday":event["start"],
                "consecutive_sundays_under_wma":event["consecutive_sunday_closes_below_200wma"],
                "entry_signal_ratio":event["initial_sunday_ratio_to_200wma"],
                "start_spot_proxy_aud":event["rows"][0]["btc_price_aud"],
                "week17_spot_proxy_aud":event["rows"][16]["btc_price_aud"],
                "week104_spot_proxy_aud":event["rows"][-1]["btc_price_aud"],
                "policies":summary,
            })
    event_labels=[{"year":x["event_year"],"first_monday":x["start"],
                   "weeks_below_wma":x["consecutive_sunday_closes_below_200wma"]}
                  for x in events]
    all_crossings=[{"first_monday":c["crossing_monday"].isoformat(),
                    "ratio":c["sunday_wma_ratio"]}
                   for c in historical_crossings(rows)]
    return {
        "status":"RESEARCH_ONLY_HINDSIGHT_MARKETS_NOT_EXECUTABLE_ETF",
        "trigger":"First prior-Sunday downward cross below 200 weekly Sunday closes",
        "selected_full_104week_episodes":event_labels,
        "all_observed_prior_sunday_crossings":all_crossings,
        "cases":out,
        "per_week_unrestricted_500k_over_17_aud":FRESH_CASH_AUD/17,
        "user_weekly_cap_aud":CAP_AUD,
        "cap_compliant_min_weeks_to_spend_500k":math.ceil(FRESH_CASH_AUD/CAP_AUD),
        "costs":{"flat_fee_aud":base.FIXED_FEE_AUD,"friction":base.VARIABLE_BUY_FRICTION,
                 "annual_etf_drag":base.ANNUAL_ETF_DRAG,"idle_cash_yield":ANNUAL_CASH_YIELD},
        "notes":[
            "The 17-week duration is a prompt hypothesis, NOT an attested average of complete below-WMA episodes.",
            "No hindsight trough, hindsight price-minimum purchase or retroactive future signal.",
            "17 calendar purchases continue even if BTC exits below-WMA region; 17 eligible only buys while prior Sunday's close remains at/below WMA.",
            "17-week full-cash deployment violates A$25,500 cap for a fresh A$500,000 allocation. Compare 17-week cap and 20-week cap arms.",
            "Existing 41% case is an illustrative 510k account and does not recreate actual Stake fills.",
            "Model baseline uses same 104-week remaining-cash / time-to-review and original 1x, 3x or strict 0.20 multiplier.",
            "Price and AUD/USD FX are historical prior-dated reference proxies; ASX:IBIT did not trade in most episodes.",
            "Cash interest is hypothetical 5% pretax; no guarantee of AAA historical yields, execution quotes or future BTC prices.",
            "Year-level entry events are not independent cycles; model and policy designs retrospective; no policy promotion.",
        ]
    }
