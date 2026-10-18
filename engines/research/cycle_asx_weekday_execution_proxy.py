"""Research-only ASX weekday execution *proxy*, never invented IBIT history.

ASX:IBIT actually listed 2025-11-14. Earlier 2017/2021 are BTC/AUD
counterfactuals, NOT actual ASX quotes or true historical IBIT performance.
The official ASX calendar, exchange session quotes, broker bid/ask spreads,
tracking error and true portfolio tax lots are unavailable. Treat weekday
only as an optimistic calendar proxy (public holidays may still be open
in the model) and treat BTC T day-close as a NEXT-CLOSE execution proxy
after deciding exclusively with T-1 prices.

Sensitivity:
  (a) legacy every-calendar-day price proxy (0 slippage/no ETF costs),
  (b) weekday-only BTC/AUD closes, A$3 per order, 0 spread or ETF costs,
  (c) weekday-only plus assumed 10/25/50 bps ONE SIDE price impact
      and illustrative 0.39% per-year BTC NAV erosion.
  All are cash-only BUY cases starting at same date, no invented BTC sale.
  Independent original shared market allocation is checked every date.
No Production, live Cycle Trading, ntfy, portfolio, or broker edits.
"""
from __future__ import annotations
import argparse
import csv
import json
import math
from pathlib import Path

import numpy as np
import pandas as pd

from engines.research.cycle_trade_allocation import calculate_allocation_signal
from engines.research.day500_aftertax_reinvestment import (
    PRIMARY, SCORE_DAYS, fetch_fx_for_cycle, fx_before,
)
from engines.research.fresh_cash_200wma_matched_backtest import (
    BUDGET_AUD,FEE_AUD,MIN_ORDER_AUD,START_DAYS,_historical_wma,
)
from engines.research.smsf_self_financing_replay import AuditSmsfAccount
from engines.research.staged_dca_delayed_bottom_stress import delayed_bottom_path
from engines.research.top_signal_horse_race import read_exported_history
from engines.research.live_weekly_buy_parity import replay_exact_live_market_buy

FRACTIONS=(.025,.03,.035)
MODELS=(
    ("calendar_optimistic",False,0,0.),
    ("weekday_zero_cost",True,0,0.),
    ("weekday_10bps_fee039",True,10,.0039),
    ("weekday_25bps_fee039",True,25,.0039),
    ("weekday_50bps_fee039",True,50,.0039),
)
TRADE_COOLDOWN_DAYS=7
BTC_CUTOFF=pd.Timestamp("2026-10-05",tz="UTC")
SHOCK_PREFIX=(("2017",750,960),("2021",650,900))
SHOCK_DROPS=(.50,.70)
SHOCK_TERMINALS=(.55,1.05)


def utc_date(value):
    dt=pd.Timestamp(value)
    return (dt.tz_localize("UTC") if dt.tzinfo is None
            else dt.tz_convert("UTC")).normalize()


def replay_proxy(price,fx,*,start,terminal,fractions=FRACTIONS,
                 weekday_only=True,one_side_cost_bps=0,
                 annual_nav_fee=0.,budget_aud=BUDGET_AUD,
                 carry_weekend=False,carry_max_days=3,
                 rebound_cap_over_200wma=.03):
    start,end=utc_date(start),utc_date(terminal)
    if (not isinstance(price,pd.Series)
            or not isinstance(price.index,pd.DatetimeIndex)
            or price.index.tz is None
            or not price.index.is_monotonic_increasing
            or price.index.has_duplicates
            or start not in price.index or end not in price.index
            or start>=end):
        raise ValueError("Ordered UTC BTC closes and endpoints required")
    required=pd.date_range(start-pd.Timedelta(days=1394),end,
                           freq="D",tz="UTC")
    if not required.isin(price.index).all():
        raise ValueError("Missing exact 200WMA price warmup/day")
    values=price.loc[required].to_numpy(float)
    if (not np.isfinite(values).all() or (values<=0).any()
            or type(weekday_only) is not bool
            or type(carry_weekend) is not bool
            or (carry_weekend and not weekday_only)
            or type(carry_max_days) is not int
            or not 1<=carry_max_days<=3
            or not math.isfinite(float(rebound_cap_over_200wma))
            or not 0<=rebound_cap_over_200wma<=.10
            or not math.isfinite(float(one_side_cost_bps))
            or not 0<=one_side_cost_bps<=200
            or not math.isfinite(float(annual_nav_fee))
            or not 0<=annual_nav_fee<=.05
            or not math.isfinite(float(budget_aud)) or budget_aud<=100
            or len(set(fractions))!=len(fractions)
            or not all(isinstance(x,(int,float)) and 0<x<=1
                       for x in fractions)):
        raise ValueError("Invalid BTC close, execution assumptions or cash")
    wallets={f:AuditSmsfAccount(float(budget_aud),fee=FEE_AUD,tax=True)
             for f in fractions}
    orders={f:[] for f in fractions}
    last_filled={f:None for f in fractions}
    market_watch=0
    watch_on_weekend=0
    watch_on_weekday=0
    weekend_signal_pending=None
    total_weekend_carried_fills=0
    for date in pd.date_range(start+pd.Timedelta(days=1),end,
                              freq="D",tz="UTC"):
        prior,wma=_historical_wma(price,date)
        eligible=bool(prior<wma)
        market={
            "price_history":price.loc[:date],
            "previous_close_usd":prior,
            "prior_200wma_usd":wma,
            "previous_close_below_200wma":eligible,
            "halving_day":9999,
        }
        signal=calculate_allocation_signal(
            market,buy_style="adaptive_recovery")
        if eligible:
            if signal["signal"]!="BUY WATCH" or signal["buy_pct_cash"]!=2.5:
                raise AssertionError("Original market BUY signal parity drift")
            market_watch+=1
            if date.weekday()<5:watch_on_weekday+=1
            else:watch_on_weekend+=1
        elif signal["signal"]=="BUY WATCH":
            raise AssertionError("New trade without original WMA gate")
        # Candidate weekend carry is a SEPARATE rule from the live WMA
        # trading policy. On Saturday/Sunday a valid LIVE market WATCH
        # cannot be filled as an ASX order. Record its timestamp only.
        # The next business WEEKDAY may use it at most once, without
        # backdating the fill or overriding a 7-day executed-trade cooldown.
        if carry_weekend and date.weekday()>=5 and eligible:
            weekend_signal_pending=date
        carry_eligible=(
            carry_weekend and weekday_only and date.weekday()<5
            and not eligible and weekend_signal_pending is not None
            and 0<(date-weekend_signal_pending).days<=carry_max_days
            and prior<=wma*(1+rebound_cap_over_200wma)
        )
        nav_factor=(1-annual_nav_fee)**((date-start).days/365.)
        # Model's BTC-equivalent NAV, with hypothetical drag only on ETF
        # sensitivity, never on BTC signal. Not an actual IBIT valuation.
        aud_mid=float(price.loc[date])*fx_before(fx,date)*nav_factor
        for fraction,account in wallets.items():
            due=(last_filled[fraction] is None or
                 (date-last_filled[fraction]).days>=TRADE_COOLDOWN_DAYS)
            allowed=not weekday_only or date.weekday()<5
            if (eligible or carry_eligible) and due and allowed:
                gross=account.cash*fraction
                if gross>MIN_ORDER_AUD and gross>2*FEE_AUD:
                    adjusted_aud=aud_mid*(1+one_side_cost_bps/10000.)
                    if account.buy(date,adjusted_aud,
                                   min(1.,gross/account.cash)):
                        order=account.orders[-1]
                        orders[fraction].append({
                            "date":str(date.date()),
                            "entry_reason":(
                                "last_weekend_prior_200wma_watch_carried"
                                if carry_eligible else "strict_live_below_200wma"),
                            "weekend_signal_origin_date":(
                                str(weekend_signal_pending.date())
                                if carry_eligible else None),
                            "gross_aud":round(float(order["gross_aud"]),2),
                            "btc_equivalent":round(float(order["btc"]),10),
                            "prior_usd_close":round(prior,3),
                            "prior_weekly_200wma":round(wma,3),
                            "weekday":date.strftime("%a"),
                            "one_side_cost_bps":one_side_cost_bps,
                            "nav_annual_fee_assumption_pct":round(
                                annual_nav_fee*100,3),
                        })
                        last_filled[fraction]=date
                        if carry_eligible:
                            total_weekend_carried_fills+=1
            account.mark(aud_mid)
        # A pending weekend WATCH is never reissued after its FIRST
        # weekday review, regardless of cash dust, cooldown, price
        # overshoot, or whether an executable fill was possible.
        if weekday_only and date.weekday()<5:
            weekend_signal_pending=None
    terminal_mid=float(price.loc[end])*fx_before(fx,end)*(
        (1-annual_nav_fee)**((end-start).days/365.))
    result={}
    for fraction,wallet in wallets.items():
        fills=orders[fraction]
        for a,b in zip(fills,fills[1:]):
            if (utc_date(b["date"])-utc_date(a["date"])).days<7:
                raise AssertionError("A second BUY violates 7d cooldown")
        if weekday_only and any(utc_date(x["date"]).weekday()>=5
                                for x in fills):
            raise AssertionError("Weekend purchase in ASX weekday proxy")
        outcome=wallet.liquidation_value(
            end,terminal_mid*(1-one_side_cost_bps/10000.))
        result[str(fraction)]={
            "fraction_of_remaining_cash_pct":round(100*fraction,3),
            "hypothetical_aud_aftertax_liquidation":round(outcome,2),
            "btc_equivalent":round(wallet.btc,8),
            "remaining_cash_aud":round(wallet.cash,2),
            "remaining_cash_pct":round(100*wallet.cash/budget_aud,3),
            "purchases":len(fills),
            "max_drawdown_pct":round(100*wallet.drawdown,3),
            "total_brokerage_aud":round(wallet.total_fees,2),
            "orders":fills,
        }
    return {
        "start_date":str(start.date()),
        "terminal_date":str(end.date()),
        "market_buy_watch_dates":market_watch,
        "buy_watch_weekend_dates":watch_on_weekend,
        "buy_watch_weekday_dates":watch_on_weekday,
        "weekday_only":weekday_only,
        "candidate_weekend_carry":carry_weekend,
        "candidate_carry_max_days":carry_max_days if carry_weekend else None,
        "candidate_max_rebound_over_wma_pct":(
            round(100*rebound_cap_over_200wma,3) if carry_weekend else None),
        "number_of_extra_carried_account_fills":total_weekend_carried_fills,
        "one_side_cost_bps":one_side_cost_bps,
        "assumed_annual_etf_nav_drag_pct":round(annual_nav_fee*100,3),
        "no_verified_asx_ibit_prices_before_listing":True,
        "real_asx_ibit_listing_date":"2025-11-14",
        "reference_fill_is_usd_btc_close_not_ibit":True,
        "account":result,
    }


def compare_modes(price,fx,*,start,terminal,cycle,startday,shock=None):
    outputs=[]
    for label,weekday,bps,nav in MODELS:
        replay=replay_proxy(
            price,fx,start=start,terminal=terminal,
            weekday_only=weekday,one_side_cost_bps=bps,
            annual_nav_fee=nav)
        base=replay["account"][str(FRACTIONS[0])]
        for p in FRACTIONS[1:]:
            alt=replay["account"][str(p)]
            outputs.append({
                "cycle":cycle,
                "cash_start_day":int(startday),
                "synthetic":shock is not None,
                "shock_decline_pct":shock[0] if shock else None,
                "terminal_pct_prior_shock":shock[1] if shock else None,
                "mode":label,
                "one_side_cost_bps":bps,
                "nav_annual_fee_pct":round(nav*100,3),
                "candidate_buy_fraction_pct":round(p*100,3),
                "market_buy_watch_dates":replay["market_buy_watch_dates"],
                "market_weekend_watch_dates":replay["buy_watch_weekend_dates"],
                "baseline_btc":base["btc_equivalent"],
                "candidate_btc":alt["btc_equivalent"],
                "baseline_cash_aud":base["remaining_cash_aud"],
                "candidate_cash_aud":alt["remaining_cash_aud"],
                "baseline_buy_count":base["purchases"],
                "candidate_buy_count":alt["purchases"],
                "baseline_aftertax_aud":base[
                    "hypothetical_aud_aftertax_liquidation"],
                "candidate_aftertax_aud":alt[
                    "hypothetical_aud_aftertax_liquidation"],
                "candidate_relative_aftertax_pct":round(
                    100*(alt["hypothetical_aud_aftertax_liquidation"]/
                         base["hypothetical_aud_aftertax_liquidation"]-1),3),
                "candidate_orders":alt["orders"],
            })
        if label=="calendar_optimistic":
            old=replay_exact_live_market_buy(price,fx,start=start,
                terminal=terminal,fractions=FRACTIONS)
            for p in FRACTIONS:
                matched=replay["account"][str(p)]
                expected=old["wallets"][str(p)]
                for x,y in (("btc_equivalent","btc_held"),
                            ("remaining_cash_aud","cash_left_aud"),
                            ("purchases","fills"),
                            ("hypothetical_aud_aftertax_liquidation",
                             "aftertax_aud")):
                    if matched[x]!=expected[y]:
                        raise AssertionError(
                            f"Pure original weekly DCA parity {p}, {x}: "
                            f"{matched[x]} != {expected[y]}")
    return outputs


def audit(history,*,fx_fetcher=fetch_fx_for_cycle):
    price=history["price_usd"].dropna().sort_index().loc[:BTC_CUTOFF]
    historical=[]
    stress=[]
    for cycle,meta in PRIMARY.items():
        halving=utc_date(meta["halving"])
        terminal=min(halving+pd.Timedelta(days=SCORE_DAYS),price.index[-1])
        fx=fx_fetcher(halving,terminal)
        for start_day in START_DAYS:
            start=halving+pd.Timedelta(days=int(start_day))
            if start>=terminal:continue
            historical+=compare_modes(
                price,fx,start=start,terminal=terminal,
                cycle=cycle,startday=start_day)
        for label,startday,shockday in SHOCK_PREFIX:
            if label!=cycle:continue
            if terminal!=halving+pd.Timedelta(days=SCORE_DAYS):
                raise ValueError("Stress base requires completed observation")
            for drop in SHOCK_DROPS:
                for termratio in SHOCK_TERMINALS:
                    alternative=delayed_bottom_path(
                        price,halving,shock_start_day=shockday,
                        loss_fraction=drop,
                        terminal_price_fraction=termratio,
                        trough_day=1060)
                    stress+=compare_modes(
                        alternative,fx,
                        start=halving+pd.Timedelta(days=startday),
                        terminal=terminal,
                        cycle=cycle,startday=startday,
                        shock=(round(100*drop,3),round(100*termratio,3)))
    return {
        "research_only":True,
        "summary":"No actual historical IBIT quotes before 14-Nov-2025",
        "IBIT_listing":"2025-11-14",
        "model_includes_asx_holidays":False,
        "model_includes_real_ibit_spreads":False,
        "model_includes_real_ibit_market_prices":False,
        "IBIT_real_annual_management_fee_pct":.39,
        "side_spread_costs_are_ASSUMED_bps":[0,10,25,50],
        "no_production_or_live_trading_changes":True,
        "historical":historical,
        "synthetic_delayed_bottom":stress,
    }


def main(argv=None):
    p=argparse.ArgumentParser()
    p.add_argument("--out",type=Path,
                   default=Path("artifacts/cycle_asx_weekday_proxy"))
    args=p.parse_args(argv)
    result=audit(read_exported_history())
    args.out.mkdir(parents=True,exist_ok=True)
    (args.out/"audit.json").write_text(json.dumps(result,indent=2))
    for tag,rows in (("historical.csv",result["historical"]),
                     ("stress.csv",result["synthetic_delayed_bottom"])):
        with (args.out/tag).open("w",newline="") as f:
            cols=[k for k in rows[0] if k!="candidate_orders"]
            w=csv.DictWriter(f,fieldnames=cols)
            w.writeheader()
            w.writerows([{k:v for k,v in row.items()
                          if k!="candidate_orders"} for row in rows])
        for row in rows:
            print(json.dumps({k:row[k] for k in (
                "cycle","cash_start_day","synthetic","mode",
                "candidate_buy_fraction_pct","candidate_relative_aftertax_pct",
                "market_weekend_watch_dates","baseline_buy_count",
                "candidate_buy_count","baseline_cash_aud",
                "candidate_cash_aud","shock_decline_pct",
                "terminal_pct_prior_shock")},sort_keys=True))
    print("RESEARCH-ONLY weekday BTC/AUD execution PROXY; no actual ASX:IBIT fills")


if __name__=="__main__":
    main()
