"""RESEARCH ONLY: selective larger BTC BUYs when PRIOR close is deeply below 200WMA.

User's real cash deployment can remain incomplete into 2027. This model
does NOT require a final buy or select a bottom. It preserves the actual
2.5%-of-REMAINING AUD cash Cycle market BUY and simulated 7-calendar-day
executed-trade cooldown as the control, using the unchanged shared live
market signal function. Conditional challengers spend more ONLY if the
strictly PRIOR completed BTC/USD close is deeply under the strictly PRIOR
200-WEEK average. Candidate thresholds are fixed here, before review of
this study's resulting audits, but older cycles are already researched
and cannot supply statistically independent validation.

Historical fills are optimistic same-day BTC/USD CLOSE converted at strictly
prior FX, not real ASX:IBIT AUD executions. Account starts in fresh AUD,
not the user's portfolio, and models ONLY the BUY-side (no cycle SELL).
Simplified FIFO SMSF accumulation CGT is sensitivity, not personal tax.
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
    BUDGET_AUD, FEE_AUD, START_DAYS, MIN_ORDER_AUD, _historical_wma,
)
from engines.research.live_weekly_buy_parity import (
    TRADE_COOLDOWN_DAYS, CUTOFF as FROZEN_HISTORY_CUTOFF,
)
from engines.research.smsf_self_financing_replay import AuditSmsfAccount
from engines.research.staged_dca_delayed_bottom_stress import delayed_bottom_path
from engines.research.top_signal_horse_race import read_exported_history

# First threshold met, never resize based on future candles. Values are
# fractions of REMAINING cash, not of the original A$500k or total equity.
# Two deep-value thresholds are illustrative, not fitted optimum cutoffs.
FROZEN_CANDIDATES = {
    "current_live_2p5_every_valid_BUY": ((1.0, .025),),
    "mild_3p0_only_if_10pct_below_WMA": ((.90, .030), (1.0, .025)),
    "selective_3p5_only_if_10pct_below_WMA": ((.90, .035), (1.0, .025)),
    "deep_5p0_only_if_20pct_below_WMA": ((.80, .050), (1.0, .025)),
    "tiered_3p5_at_10pct_and_5p0_at_20pct": (
        (.80, .050), (.90, .035), (1.0, .025)),
}
BASELINE = "current_live_2p5_every_valid_BUY"
FROZEN_2026_27_OBJECTIVE = "NO_MANDATORY_PURCHASE_BEFORE_OR_DURING_2027"
SHOCK_CASES = (("2017", 750, 960), ("2021", 650, 900))
SHOCK_DROPS = (.50, .70)
SHOCK_FINAL_LEVELS = (.55, 1.05)
SHOCK_TROUGH_DAY = 1060
OUTPUT = Path("artifacts/research_conditional_deep_value_weekly_buy")


def utcday(date):
    t = pd.Timestamp(date)
    return (t.tz_localize("UTC") if t.tzinfo is None
            else t.tz_convert("UTC")).normalize()


def _allocation(policy, ratio):
    """Choose percentage from PRIOR ratio; requires a below-WMA live BUY."""
    if policy not in FROZEN_CANDIDATES:
        raise ValueError("Unknown previously declared conditional policy")
    if not math.isfinite(float(ratio)) or ratio <= 0 or ratio >= 1.0:
        raise ValueError("Buy size only for verified previous close below 200WMA")
    for threshold, fraction in FROZEN_CANDIDATES[policy]:
        if ratio <= threshold:
            return float(fraction)
    raise AssertionError("Uncovered below-WMA price ratio")


def replay(prices: pd.Series, fx: pd.DataFrame, *, start, terminal,
           capital_aud=BUDGET_AUD, policies=tuple(FROZEN_CANDIDATES)):
    """Causal previous-date WMA and same market WATCH, 7-day ACCOUNT cooldown.

    Entry starts day AFTER user-like hypothetical fresh AUD date.
    No cash sweep at terminal even when all available capital is unspent.
    """
    begun, end = utcday(start), utcday(terminal)
    if (not isinstance(prices, pd.Series)
        or not isinstance(prices.index, pd.DatetimeIndex)
        or prices.index.tz is None or not prices.index.is_monotonic_increasing
        or prices.index.has_duplicates or begun not in prices.index
        or end not in prices.index or end <= begun):
        raise ValueError("Need observed ordered UTC BTC history and matched entry/end")
    required = pd.date_range(begun-pd.Timedelta(days=1394),end,freq="D",tz="UTC")
    if not required.isin(prices.index).all():
        raise ValueError("Strict prior 200-week BTC warmup and dates missing")
    values = prices.loc[required].to_numpy(dtype=float)
    if not np.isfinite(values).all() or (values<=0).any():
        raise ValueError("BTC close missing, negative or nonfinite")
    if (not math.isfinite(float(capital_aud)) or capital_aud<=MIN_ORDER_AUD
        or not policies or len(set(policies))!=len(policies)
        or any(p not in FROZEN_CANDIDATES for p in policies)):
        raise ValueError("Invalid common starting cash or research policy")
    if not isinstance(fx,pd.DataFrame) or not isinstance(fx.index,pd.DatetimeIndex):
        raise ValueError("Prior AUD FX dated DataFrame required")

    wallets={p:AuditSmsfAccount(float(capital_aud),fee=FEE_AUD,tax=True)
             for p in policies}
    orders={p:[] for p in policies}
    last_execution={p:None for p in policies}
    exposure_sum={p:0.0 for p in policies}
    exposure_count=0
    total_market_buy_days=0
    deep10_market_days=0
    deep20_market_days=0
    terminal_aud_spot=None
    for day in pd.date_range(begun+pd.Timedelta(days=1),end,freq="D",tz="UTC"):
        prev,wma=_historical_wma(prices,day)
        eligible=(prev<wma)
        market={
            "price_history":prices.loc[:day],
            "previous_close_usd":prev,
            "prior_200wma_usd":wma,
            "previous_close_below_200wma":eligible,
            "halving_day":9999, # suppress fictitious historical sale inventory
        }
        live=calculate_allocation_signal(market,buy_style="adaptive_recovery")
        if eligible and (live["signal"]!="BUY WATCH" or
                         live["buy_pct_cash"]!=2.5):
            raise AssertionError("Live 2.5% conditional market BUY rule drift")
        if not eligible and live["signal"]=="BUY WATCH":
            raise AssertionError("Live market BUY triggered above previous WMA")
        ratio=prev/wma
        if eligible:
            total_market_buy_days+=1
            if ratio <=.90:deep10_market_days+=1
            if ratio <=.80:deep20_market_days+=1
        current=float(prices.loc[day])*fx_before(fx,day)
        terminal_aud_spot=current
        for policy,wallet in wallets.items():
            gap=last_execution[policy]
            due=(gap is None or (day-gap).days>=TRADE_COOLDOWN_DAYS)
            if eligible and due:
                fraction=_allocation(policy,ratio)
                budget=wallet.cash*fraction
                if budget>MIN_ORDER_AUD and budget>2*FEE_AUD:
                    if wallet.buy(day,current,fraction):
                        saved=wallet.orders[-1]
                        orders[policy].append({
                            "date":str(day.date()),
                            "prior_BTCUSD_over_prior_200WMA":round(ratio,6),
                            "fraction_of_remaining_cash_pct":round(100*fraction,2),
                            "actual_shared_market_pct":live["buy_pct_cash"],
                            "gross_AUD":round(saved["gross_aud"],2),
                            "BTC_units":round(saved["btc"],10),
                            "price_USD_close_proxy":round(float(prices.loc[day]),2),
                        })
                        last_execution[policy]=day
            wallet.mark(current)
            wealth=wallet.cash+wallet.btc*current
            if not math.isfinite(wealth) or wealth<=0:
                raise ArithmeticError("Invalid account equity")
            exposure_sum[policy]+=100*wallet.btc*current/wealth
        exposure_count+=1

    data={}
    for name,wallet in wallets.items():
        fills=orders[name]
        if len(fills)>=2 and any((utcday(fills[i]["date"]) -
                                   utcday(fills[i-1]["date"])).days<TRADE_COOLDOWN_DAYS
                                 for i in range(1,len(fills))):
            raise AssertionError("Seven-day actual executed buy cooldown violated")
        if name==BASELINE and any(o["fraction_of_remaining_cash_pct"]!=2.5 for o in fills):
            raise AssertionError("Original model 2.5% baseline improperly modified")
        if any(o["actual_shared_market_pct"]!=2.5 for o in fills):
            raise AssertionError("Research candidate mislabeled live sizing signal")
        data[name]={
            "hypothetical_AUD_cash_at_entry":round(float(capital_aud),2),
            "fills":len(fills),
            "BTC_held":round(wallet.btc,8),
            "cash_left_AUD":round(wallet.cash,2),
            "cash_left_pct_initial":round(100*wallet.cash/capital_aud,4),
            "marked_account_AUD":round(wallet.cash+wallet.btc*terminal_aud_spot,2),
            "after_illustrative_FIFO_SMSF_liquidation_AUD":round(
                wallet.liquidation_value(end,terminal_aud_spot),2),
            "max_account_drawdown_pct":round(wallet.drawdown*100,4),
            "mean_daily_BTC_market_exposure_pct":round(
                exposure_sum[name]/exposure_count,4),
            "total_brokerage_AUD":round(wallet.total_fees,2),
            "paper_orders":fills,
        }
    return {
        "start_UTC":str(begun.date()),
        "terminal_observed_UTC":str(end.date()),
        "original_cash_only":True,
        "terminal_cash_forced_to_BTC":False,
        "actual_live_buy_rule_used_as_baseline":True,
        "current_weekly_trade_cooldown_days":TRADE_COOLDOWN_DAYS,
        "eligible_prior_BTC_below_200WMA_days":total_market_buy_days,
        "eligible_prior_BTC_at_least_10pct_below_200WMA_days":deep10_market_days,
        "eligible_prior_BTC_at_least_20pct_below_200WMA_days":deep20_market_days,
        "hypothetical_daily_USD_close_not_ASX_eligible_fill":True,
        "purchases_are_price_data_causal_but_not_executable_ASX_orders":True,
        "portfolios":data,
    }


def compare_run(run, *, cycle, entry_day, synthetic=False,
                stress_drop=None, terminal_fraction=None, completed=False):
    first=run["portfolios"][BASELINE]
    results=[]
    for policy,scenario in run["portfolios"].items():
        comparison=100*(scenario["after_illustrative_FIFO_SMSF_liquidation_AUD"]/
                        first["after_illustrative_FIFO_SMSF_liquidation_AUD"]-1)
        results.append({
            "cycle":cycle, "entry_halving_day_offset":entry_day,
            "complete_cycle_through_halving_plus_1150":completed,
            "synthetic_delayed_bottom":synthetic,
            "synthetic_extra_decline_fraction":stress_drop,
            "synthetic_terminal_fraction_of_pre_shock_level":terminal_fraction,
            "start":run["start_UTC"],
            "last_observed_date":run["terminal_observed_UTC"],
            "policy":policy,
            "after_illustrative_FIFO_SMSF_liquidation_AUD":
                scenario["after_illustrative_FIFO_SMSF_liquidation_AUD"],
            "vs_original_2p5_aftertax_pct":round(comparison,4),
            "max_account_drawdown_pct":scenario["max_account_drawdown_pct"],
            "BTC_held":scenario["BTC_held"],
            "AUD_cash_remaining":scenario["cash_left_AUD"],
            "AUD_cash_remaining_pct":scenario["cash_left_pct_initial"],
            "mean_daily_BTC_exposure_pct":scenario["mean_daily_BTC_market_exposure_pct"],
            "fills":scenario["fills"],
            "10pct_deep_market_days":run[
                "eligible_prior_BTC_at_least_10pct_below_200WMA_days"],
            "20pct_deep_market_days":run[
                "eligible_prior_BTC_at_least_20pct_below_200WMA_days"],
            "paper_order_detail":scenario["paper_orders"],
        })
    return results


def audit(history, *, fx_fetcher=fetch_fx_for_cycle):
    px=history["price_usd"].dropna().sort_index().loc[:FROZEN_HISTORY_CUTOFF]
    historic=[];synthetic=[]
    for cycle, spec in PRIMARY.items():
        halving=utcday(spec["halving"])
        terminal=min(halving+pd.Timedelta(days=SCORE_DAYS),px.index[-1])
        fx=fx_fetcher(halving,terminal)
        for day_offset in START_DAYS:
            start=halving+pd.Timedelta(days=int(day_offset))
            if start>=terminal:
                continue
            outcome=replay(px,fx,start=start,terminal=terminal)
            historic+=compare_run(
                outcome,cycle=cycle,entry_day=int(day_offset),
                completed=(terminal==halving+pd.Timedelta(days=SCORE_DAYS)))
        for shock_cycle,offset,shock_at in SHOCK_CASES:
            if shock_cycle!=cycle:continue
            if terminal!=halving+pd.Timedelta(days=SCORE_DAYS):
                raise ValueError("Historical shock requires completed BTC cycle")
            for drop in SHOCK_DROPS:
                for final in SHOCK_FINAL_LEVELS:
                    stressed=delayed_bottom_path(
                        px,halving,shock_start_day=shock_at,
                        loss_fraction=drop,
                        terminal_price_fraction=final,
                        trough_day=SHOCK_TROUGH_DAY,
                    )
                    record=replay(
                        stressed,fx,
                        start=halving+pd.Timedelta(days=offset),
                        terminal=terminal,
                    )
                    synthetic+=compare_run(
                        record,cycle=cycle,entry_day=offset,
                        synthetic=True,stress_drop=drop,
                        terminal_fraction=final,completed=True)
    if not historic or not synthetic:
        raise AssertionError("Historical and adverse counterfactual comparisons required")
    return {
        "kind":"RESEARCH_CONDITIONAL_DEEP_BTC_200WMA_7DAY_SIZE_NOT_TRADING",
        "user_deployment_deadline":"FLEXIBLE_INTO_2027_NO_FINAL_CASH_SWEEP",
        "cutoff_actual_historical_prices_UTC":str(FROZEN_HISTORY_CUTOFF.date()),
        "frozen_candidate_sizing_by_prior_BTCUSD_over_prior_200WMA":
            {k:[list(t) for t in v] for k,v in FROZEN_CANDIDATES.items()},
        "historical_cycles_not_independent_unseen_holdouts":True,
        "2025_2026_cohort_right_censored":True,
        "no_live_BTC_model_changes":True,
        "all_equal_original_AUD_capital":True,
        "no_future_cycle_bottom_signal":True,
        "no_compulsory_purchase_even_in_2027":True,
        "no_ASX_IBIT_execution_or_broker_bid_ask":True,
        "aftertax_figures_only_illustrative_SMSF_accumulation_phase":True,
        "no_live_trades_portfolio_writes_ntfy":True,
        "historical":historic,
        "synthetic_deeper_declines":synthetic,
        "winner_proven_or_approved":False,
        "caveats":[
            "Conditional thresholds selected after earlier historical tests; NOT out-of-sample.",
            "Model only simulates fresh cash BUY, not existing IBIT wallet or staged SELL.",
            "Daily BTC close (including weekends) is not executable as ASX:IBIT fill.",
            "No ETF tracking/spread, transaction FX spread, whole units or cash yield.",
            "AUD3 brokerage and hypothetical FIFO SMSF accumulation CGT only.",
            "Terminal after-tax is hypothetical full liquidation, not user realised income.",
            "Synthetic extra market decline/recovery paths are NOT probability forecasts.",
            "Retrospective cheapness gate uses prior BTC/USD/strictly prior 200WMA only.",
        ],
    }


def main(argv=None):
    p=argparse.ArgumentParser(description="Research conditional discount-based weekly BTC BUY sizes")
    p.add_argument("--out",type=Path,default=OUTPUT)
    args=p.parse_args(argv)
    result=audit(read_exported_history())
    args.out.mkdir(parents=True,exist_ok=True)
    (args.out/"full_research_audit.json").write_text(json.dumps(result,indent=2)+"\n")
    for filename,key in (("historical.csv","historical"),
                         ("adverse.csv","synthetic_deeper_declines")):
        rows=result[key]
        cols=[k for k in rows[0] if k!="paper_order_detail"]
        with (args.out/filename).open("w",newline="") as handle:
            w=csv.DictWriter(handle,fieldnames=cols)
            w.writeheader()
            for x in rows:w.writerow({k:v for k,v in x.items() if k in cols})
    for group in ("historical","synthetic_deeper_declines"):
        for x in result[group]:
            if x["policy"]==BASELINE:continue
            print(json.dumps({
                "group":group,"cycle":x["cycle"],
                "start_day":x["entry_halving_day_offset"],
                "policy":x["policy"],
                "aftertax_vs_live_2p5_pct":x["vs_original_2p5_aftertax_pct"],
                "cash_left_pct":x["AUD_cash_remaining_pct"],
                "mean_exposure_pct":x["mean_daily_BTC_exposure_pct"],
                "max_drawdown_pct":x["max_account_drawdown_pct"],
                "fills":x["fills"],"shock_drop":x["synthetic_extra_decline_fraction"],
                "shock_terminal_level":x["synthetic_terminal_fraction_of_pre_shock_level"],
                "is_proven_alpha":False,
            },sort_keys=True))
    print("NO LIVE MODEL, PORTFOLIO, NTFY OR BROKER CHANGES")


if __name__=="__main__":
    main()
