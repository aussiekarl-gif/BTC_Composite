"""Research-only realistic A$500,000 BTC deployment cohorts beginning in 2026.

Uses validated historical prices/risk *before* the cohort date solely to
warm up trailing indicators and the risk-armed state. Account transactions
cannot occur until the deployment date. NEVER silently starts in 2016.

Compares independent, self-financing accounts starting with A$500,000:
  - immediately buy at the first available weekly close after start;
  - risk-weighted DCA (10% confirmed exit; 10/15/25% sensitivity);
  - an explicitly labeled 12-observation equal cash deployment baseline;
  - hold the AUD cash (opportunity cost control).
This is NOT the user's actual portfolio. Their real purchases are only
in the My Portfolio persistent ledger, not the historic research master.

A$3 brokerage per executed order, FIFO estimated SMSF tax (10% eligible
long-held gains; 15% short-held), and terminal hypothetical CGT. Assumes
weekly close fills, no spread, no ETF fee, no cash interest, and immediate
tax escrow. Historical risk-score vintage remains unverified.

The source master currently has weekly paired AUD BTC prices/risk, and
may lag today's 2026-10-16 date. Always display the actual observed end
date and explicitly avoid extrapolating any return beyond it.
"""
from __future__ import annotations

import argparse
import json

import numpy as np
import pandas as pd

from engines.research.adaptive_dca_execution import simulate_adaptive
from engines.research.full_cycle_reinvestment import CAPITAL, validate_history
from engines.research.smsf_self_financing_replay import AuditSmsfAccount, replay

COHORTS = ("2026-01-01", "2026-06-19")
SELL_CONFIRMATIONS = (0.10, 0.15, 0.25)
BROKERAGE_AUD = 3.0
# Fixed calendar benchmark, never applied as a limit to adaptive models.
EQUAL_DCA_WEEKS = 12


def _start_index(history, start_date):
    first = pd.Timestamp(start_date)
    if history.index.tz is not None:
        first = first.tz_localize(history.index.tz) if first.tzinfo is None else first.tz_convert(history.index.tz)
    elif first.tzinfo is not None:
        first = first.tz_localize(None)
    found = np.flatnonzero(history.index >= first)
    if not len(found):
        raise ValueError("No observed BTC week on or after deployment start")
    if found[0] < 1:
        raise ValueError("Need at least one prior observation to execute without same-day lookahead")
    return int(found[0])


def _snapshot(account, date, last_price, label, start, order_dates, terminal_date):
    remaining = account.btc
    marked = account.cash + remaining * last_price
    return {
        "model": label,
        "requested_deployment_date": start,
        "first_weekly_execution": str(date),
        "last_observed_date": str(terminal_date),
        "actual_orders": len(account.orders),
        "buy_orders": sum(x["side"] == "BUY" for x in account.orders),
        "sell_orders": sum(x["side"] == "SELL" for x in account.orders),
        "btc_equivalent_held": round(remaining, 8),
        "cash_left_aud": round(account.cash, 2),
        "account_marked_value_aud": round(marked, 2),
        "hypothetical_liquidation_value_after_cgt_aud": round(
            account.liquidation_value(terminal_date, last_price), 2),
        "realised_smsf_cgt_paid_est_aud": round(account.total_tax, 2),
        "brokerage_aud": round(account.total_fees, 2),
        "max_drawdown_from_2026_deployment_pct": round(account.drawdown * 100, 2),
        "first_order_date": order_dates[0] if order_dates else None,
        "last_order_date": order_dates[-1] if order_dates else None,
    }


def benchmark_account(history, start_date, mode, *, initial_cash=CAPITAL):
    """No signals/future-peeking: immediate BTC, 12-slice equal DCA or cash."""
    d=validate_history(history)
    start=_start_index(d, start_date)
    acct=AuditSmsfAccount(initial_cash, fee=BROKERAGE_AUD, tax=True)
    prices=d["btc_price_aud"].to_numpy(dtype=float)
    first=d.index[start]
    for j in range(start, len(d)):
        cur=float(prices[j])
        if mode == "immediate_buy" and j == start:
            acct.buy(d.index[j],cur,1.0)
        elif mode == "equal_12week_buy" and j-start < EQUAL_DCA_WEEKS:
            # Predefined AUD budget, not a fraction of leftover cash.
            left_tranches=EQUAL_DCA_WEEKS-(j-start)
            pct=min(1.0,initial_cash/EQUAL_DCA_WEEKS/max(acct.cash,1e-9))
            if left_tranches == 1:
                pct=1.0
            acct.buy(d.index[j],cur,pct)
        elif mode != "cash_only" and mode not in ("equal_12week_buy", "immediate_buy"):
            raise ValueError("Unsupported benchmark mode")
        acct.mark(cur)
    orders=[x["date"] for x in acct.orders]
    return _snapshot(acct, first, float(prices[-1]), mode,
                     str(pd.Timestamp(start_date).date()), orders, d.index[-1])


def adaptive_account(history, start_date, *, confirm_drawdown=0.10,
                     policy="adaptive", initial_cash=CAPITAL):
    d=validate_history(history)
    start=_start_index(d,start_date)
    source=simulate_adaptive(d, confirm_drawdown=confirm_drawdown,
                             initial_cash=initial_cash,
                             fee_aud=BROKERAGE_AUD,
                             deployment_start=start_date)
    if any(pd.Timestamp(x["date"]) < d.index[start] for x in source["trades"]):
        raise AssertionError("2026 deployment leaked older trades")
    simulated=replay(d,source["trades"],policy=policy,tax=True,
                     starting_cash=initial_cash)
    # The tax-aware model reruns transaction sizes with the actual net cash.
    order_dates=[x["date"] for x in simulated["orders"]]
    return {
        "model":f"{policy}_adaptive_exit_{int(100*confirm_drawdown)}pct",
        "requested_deployment_date":str(pd.Timestamp(start_date).date()),
        "first_weekly_execution":str(d.index[start]),
        "last_observed_date":str(d.index[-1]),
        "actual_orders":simulated["actual_orders"],
        "buy_orders":simulated["buy_orders"],
        "sell_orders":simulated["sell_orders"],
        "btc_equivalent_held":simulated["btc"],
        "cash_left_aud":simulated["cash_aud"],
        "account_marked_value_aud":simulated["ending_marked_equity_aud"],
        "hypothetical_liquidation_value_after_cgt_aud":
            simulated["hypothetical_final_liquidation_after_cgt_aud"],
        "realised_smsf_cgt_paid_est_aud":simulated["total_realized_cgt_estimate_aud"],
        "brokerage_aud":simulated["total_brokerage_aud"],
        "max_drawdown_from_2026_deployment_pct":
            simulated["max_account_drawdown_pct"],
        "first_order_date":order_dates[0] if order_dates else None,
        "last_order_date":order_dates[-1] if order_dates else None,
        "signal_opportunities":len(source["trades"]),
    }


def evaluate_cohorts(history, *, dates=COHORTS, initial_cash=CAPITAL):
    d=validate_history(history)
    out=[]
    for start in dates:
        i=_start_index(d,start)
        results=[
            benchmark_account(d,start,"immediate_buy",initial_cash=initial_cash),
            benchmark_account(d,start,"equal_12week_buy",initial_cash=initial_cash),
            benchmark_account(d,start,"cash_only",initial_cash=initial_cash),
        ]
        results.extend(
            adaptive_account(d,start,confirm_drawdown=confirmation,
                             policy="adaptive",initial_cash=initial_cash)
            for confirmation in SELL_CONFIRMATIONS
        )
        # Fixed opportunity dates but distinct self-financing size strategies.
        results.append(adaptive_account(d,start,confirm_drawdown=.10,
                                        policy="trend_reserve",
                                        initial_cash=initial_cash))
        buy_and_hold=results[0]["account_marked_value_aud"]
        for x in results:
            x["vs_immediate_buy_marked_pct"]=round(
                100*(x["account_marked_value_aud"]/buy_and_hold-1),3)
        out.append({
            "deployment_date":start,
            "first_observed_executable_week":str(d.index[i]),
            "weeks_in_observed_forward_period":len(d)-i,
            "results":results,
        })
    return {
        "research_only":True,
        "starting_capital_aud":initial_cash,
        "source_start":str(d.index[0]),
        "source_last_observed_week":str(d.index[-1]),
        "cohorts":out,
        "warnings":[
            "2026 cohort is hypothetical fresh capital, NOT the user's personal purchases.",
            "Real trades remain in persistent My Portfolio and are never imported by this research job.",
            "Old pre-2026 price/risk is only for moving-average and risk signal warm-up.",
            "At the requested 2026 deployment date the account starts with full AUD 500,000 cash.",
            "Data ends on the displayed final week; NO post-master price forecasts.",
            "Only a partial 2026 cycle is observed, so 25%-from-final-cycle-bottom and completed sell/rebuy success cannot be scored honestly.",
            "USD 57,717 on 2026-06-30 is a provisional user-reported intraday low, not a USD execution-price comparator in these AUD weekly simulations.",
            "AUD 3 per filled order; FIFO estimated short/long SMSF accumulation-phase CGT escrow and hypothetical terminal sale tax.",
            "No annual SMSF tax reconciliation, ETF fee, bid/ask spread, tracking deviation or guaranteed fill at weekly close.",
            "Stored historical risk score may not be a vintage point-in-time series; NOT verified for Production promotion.",
            "Adaptive trading duration is unbounded; 12 weeks applies ONLY to the passive equal-DCA baseline.",
            "All selected rules in-sample exploratory; not a live strategy recommendation.",
        ],
    }


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--output",default="")
    args=parser.parse_args()
    from engines.shared.central_data import load_master
    master=load_master(columns=["btc_price_aud","risk_score"])
    cols=master[["btc_price_aud","risk_score"]].apply(pd.to_numeric,errors="coerce")
    mask=cols["btc_price_aud"].gt(0) & cols["risk_score"].between(0,1)
    result=evaluate_cohorts(cols.loc[mask])
    result["valid_paired_rows"]=int(mask.sum())
    content=json.dumps(result,indent=2,allow_nan=False,
                       default=lambda x:x.item() if isinstance(x,np.generic) else str(x))
    if args.output:
        from pathlib import Path
        Path(args.output).write_text(content+"\n",encoding="utf-8")
    print(content)


if __name__ == "__main__":
    main()
