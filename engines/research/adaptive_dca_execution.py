"""Research only: causal, variable-duration BTC/AUD accumulation/distribution.

Each trade at t is decided using observed prices and risk through t-1.
There is deliberately NO 12/16-week execution window. The strategy can pause
and later resume, with trade sizes depending on risk and trailing momentum.
Trailing-window maxima and 20/50-week simple MAs are past observations.
This is an exploratory comparison, NOT a deployable trading algorithm.

The flat A$3 per-order brokerage is applied; no CGT, ETF spread, or fund charges.
Historical master risk-score point-in-time provenance is NOT independently verified.
"""
import argparse
import json
import math

import numpy as np
import pandas as pd

from engines.research.full_cycle_reinvestment import (
    CAPITAL, validate_history,
)

FLAT_FEE_AUD = 3.0
BULL_ARM_RISK = .60
BUY_RISK = .35
DUST_AUD = 100.0
# Predeclared diagnostic, not selected on this history.
CONFIRMATIONS = (.10, .15, .25)


def simulate_adaptive(
    data, *,
    confirm_drawdown=.15,
    initial_cash=CAPITAL,
    fee_aud=FLAT_FEE_AUD,
    risk_arm=BULL_ARM_RISK,
    buy_risk=BUY_RISK,
    deployment_start=None,
):
    history = validate_history(data)
    if not isinstance(history.index, pd.DatetimeIndex):
        raise ValueError("Require dated weekly observations")
    if not (0 < confirm_drawdown < .60):
        raise ValueError("Invalid drawdown threshold")
    if not 0 <= buy_risk < risk_arm <= 1:
        raise ValueError("Invalid risk zone")
    if not (math.isfinite(initial_cash) and initial_cash > 0):
        raise ValueError("Invalid capital")
    if not (math.isfinite(fee_aud) and fee_aud >= 0):
        raise ValueError("Invalid brokerage")

    if deployment_start is not None:
        first_trade = pd.Timestamp(deployment_start)
        if history.index.tz is not None:
            first_trade = (first_trade.tz_localize(history.index.tz)
                           if first_trade.tzinfo is None
                           else first_trade.tz_convert(history.index.tz))
        elif first_trade.tzinfo is not None:
            first_trade = first_trade.tz_localize(None)
        if first_trade > history.index[-1]:
            raise ValueError("Deployment starts after available history")
    else:
        first_trade = None

    price = history["btc_price_aud"].to_numpy(dtype=float)
    risk = history["risk_score"].to_numpy(dtype=float)

    cash, btc, paid_fees = float(initial_cash), 0., 0.
    high_since_arm, is_armed = None, False
    history_peaks = []
    trades = []
    equity = []
    for i in range(1, len(price)):
        # i-1 is the FINAL observation available for deciding a trade
        # executed at i's next weekly close. Do not use price[i] in a signal.
        observed = i-1
        p_prev, r_prev = float(price[observed]), float(risk[observed])
        ma20 = (float(np.mean(price[observed-19:observed+1]))
                if observed >= 19 else None)
        ma50 = (float(np.mean(price[observed-49:observed+1]))
                if observed >= 49 else None)
        two_month_low = float(np.min(price[max(0,observed-7):observed+1]))
        two_month_high = float(np.max(price[max(0,observed-7):observed+1]))
        trade_side = None
        pct = 0.
        reason = ""

        if r_prev >= risk_arm:
            if not is_armed:
                is_armed = True
                high_since_arm = p_prev
            else:
                high_since_arm = max(high_since_arm,p_prev)
        elif is_armed:
            high_since_arm = max(high_since_arm,p_prev)

        below_ma20 = ma20 is not None and p_prev < ma20
        below_ma50 = ma50 is not None and p_prev < ma50
        above_ma20 = ma20 is not None and p_prev > ma20
        under_arm_high = (
            (1-p_prev/high_since_arm)
            if is_armed and high_since_arm is not None else 0.
        )
        # Sell only after risk has armed a possible high AND market shows
        # a downtrend. Sell rate adjusts week-by-week, does not commit
        # the position to a fixed window.
        if (is_armed and btc * p_prev > DUST_AUD
                and under_arm_high >= confirm_drawdown and below_ma20):
            urgency = min(1.0, under_arm_high/.40)
            pct = min(.35, .07 + .16*urgency + (.07 if below_ma50 else 0))
            trade_side, reason = "SELL", "armed_drawdown_and_trend"
        elif (r_prev <= buy_risk and cash > DUST_AUD):
            # Smaller starter buys with stronger adds at deeper relative
            # discounts. No future prices enter the sizing formula.
            intensity = min(1., max(0., (buy_risk-r_prev)/buy_risk))
            pct = .035 + .09*intensity
            if below_ma20:
                pct *= 1.35
            if below_ma50:
                pct *= 1.35
            if above_ma20:
                pct *= .75
            if p_prev <= two_month_low*1.03:
                pct *= 1.15
            pct = min(.24, max(.015, pct))
            trade_side, reason = "BUY", "low_risk_cash_weighted"

        # Signals and moving averages receive the full prior history.
        # Account execution remains flat cash until the chosen REAL 2026
        # investment date; no historical 2016 simulation fills leak in.
        if first_trade is not None and history.index[i] < first_trade:
            trade_side = None

        cur = float(price[i])
        qty = gross = charge = 0.
        if trade_side == "BUY":
            # Do not buy dust orders that would waste the flat fee.
            gross = min(cash, cash*pct)
            if gross <= max(DUST_AUD,fee_aud*2):
                trade_side = None
            else:
                charge = fee_aud
                qty = (gross-charge)/cur
                btc += qty
                cash -= gross
        elif trade_side == "SELL":
            qty = btc*pct
            gross = qty*cur
            if gross <= max(DUST_AUD,fee_aud*2):
                trade_side = None
            else:
                charge = fee_aud
                cash += gross-charge
                btc -= qty

        if trade_side:
            paid_fees += charge
            trades.append({
                "date": str(history.index[i]),
                "side": trade_side,
                "executed_price_aud": round(cur,7),
                "decision_price_aud": round(p_prev,7),
                "decision_risk": round(r_prev,7),
                "ma20_observed": ma20,
                "ma50_observed": ma50,
                "fraction_of_available_at_trade": round(pct,7),
                "btc_quantity": qty,
                "gross_notional_aud": gross,
                "fee_aud": charge,
                "reason": reason,
            })
        if is_armed and r_prev <= buy_risk:
            # Reset top watch after a low risk observation; can arm again.
            is_armed, high_since_arm = False, None

        eq = cash + btc*cur
        equity.append(eq)
        history_peaks.append((str(history.index[i]), p_prev,
                              high_since_arm if is_armed else None))
        if cash < -1e-7 or btc < -1e-10:
            raise ArithmeticError("Negative holdings")

    return {
        "ending_equity_aud": float(equity[-1]),
        "cash_aud": cash,
        "btc": btc,
        "fee_total_aud": paid_fees,
        "deployment_start": str(first_trade) if first_trade is not None else None,
        "trade_count": len(trades),
        "buy_orders": sum(x["side"]=="BUY" for x in trades),
        "sell_orders": sum(x["side"]=="SELL" for x in trades),
        "trades": trades,
        "equity_path": equity,
    }


def group_trade_legs(trades):
    """Merge consecutive same-direction orders, including weeks without fills.

    A leg has no preset duration; it ends only when the actual direction
    changes. Equal AUD buys correctly use total gross / total BTC; equal BTC
    sells correctly use gross proceeds / sold BTC.
    """
    legs=[]
    for t in trades:
        if not legs or t["side"] != legs[-1]["side"]:
            legs.append({
                "side":t["side"],
                "start":t["date"],
                "end":t["date"],
                "btc_quantity":0.,
                "gross_notional_aud":0.,
                "fees_aud":0.,
                "orders":0,
            })
        leg = legs[-1]
        leg["end"] = t["date"]
        leg["btc_quantity"] += t["btc_quantity"]
        leg["gross_notional_aud"] += t["gross_notional_aud"]
        leg["fees_aud"] += t["fee_aud"]
        leg["orders"] += 1
    for leg in legs:
        leg["vwap_price_aud"] = (leg["gross_notional_aud"] /
                                  leg["btc_quantity"])
        # Effective buy includes fixed brokerage; effective sell deducts it.
        # Gross VWAP retained separately for comparison with older audits.
        # BUY gross already includes brokerage cash outflow; bought BTC is
        # net of the fee. Do NOT add the fee a second time.
        leg["net_effective_price_aud"] = (
            leg["gross_notional_aud"] / leg["btc_quantity"]
            if leg["side"]=="BUY" else
            (leg["gross_notional_aud"] - leg["fees_aud"]) / leg["btc_quantity"]
        )
    return legs


def audit_error_rates(data, legs, lookahead_weeks=26):
    """Cash-feasible ex-post sell->next buy score; never enters signal generation.

    Use reference peak from sale leg beginning to next buy beginning. Compare
    against the lowest weekly AUD price from sale leg ending to 26 weeks after
    buy leg ending. Exclude chronologically impossible oracle (high after low)
    and incomplete future window. If a leg spans to the end it is censored.
    """
    history = validate_history(data)
    prices = history["btc_price_aud"].to_numpy(dtype=float)
    idx={str(d):i for i,d in enumerate(history.index)}
    pairs=[]
    for n in range(len(legs)-1):
        a,b=legs[n],legs[n+1]
        if a["side"]!="SELL" or b["side"]!="BUY":
            continue
        ai,ae,bi,be=(idx[a["start"]],idx[a["end"]],
                      idx[b["start"]],idx[b["end"]])
        if not (ai<=ae<bi<=be):
            raise ValueError("Invalid leg ordering")
        h_idx=ai+int(np.argmax(prices[ai:bi+1]))
        low_end=min(len(prices)-1,be+lookahead_weeks)
        l_idx=ae+int(np.argmin(prices[ae:low_end+1]))
        eligible=(be+lookahead_weeks<len(prices)
                  and h_idx<=l_idx)
        sell_error=1-a["net_effective_price_aud"]/prices[h_idx]
        buy_error=b["net_effective_price_aud"]/prices[l_idx]-1
        sell_error=max(0.,float(sell_error))
        buy_error=max(0.,float(buy_error))
        pairs.append({
            "sell_start":a["start"],"sell_end":a["end"],
            "buy_start":b["start"],"buy_end":b["end"],
            "sell_weeks_calendar":ae-ai+1,"buy_weeks_calendar":be-bi+1,
            "sell_orders":a["orders"],"buy_orders":b["orders"],
            "sell_error_pct":round(sell_error*100,3),
            "buy_error_pct":round(buy_error*100,3),
            "oracle_high_date":str(history.index[h_idx]),
            "oracle_low_date":str(history.index[l_idx]),
            "eligible":eligible,
            "both_within_25pct":bool(eligible and sell_error<=.25
                                      and buy_error<=.25),
        })
    good=[p for p in pairs if p["eligible"]]
    return {
        "pairs_total":len(pairs),
        "pairs_eligible":len(good),
        "both_within_25pct":sum(p["both_within_25pct"] for p in good),
        "sell_within_25pct":sum(p["sell_error_pct"]<=25 for p in good),
        "buy_within_25pct":sum(p["buy_error_pct"]<=25 for p in good),
        "pairs":pairs,
    }


def report_adaptive(data):
    history=validate_history(data)
    candidates=[]
    for threshold in CONFIRMATIONS:
        r=simulate_adaptive(history,confirm_drawdown=threshold)
        legs=group_trade_legs(r["trades"])
        scored=audit_error_rates(history,legs)
        candidates.append({
            "confirmation_drop_pct":round(threshold*100,1),
            "ending_equity_aud":round(r["ending_equity_aud"],2),
            "cash_aud":round(r["cash_aud"],2),
            "btc_units":round(r["btc"],7),
            "fee_total_aud":r["fee_total_aud"],
            "trade_count":r["trade_count"],
            "buy_orders":r["buy_orders"],
            "sell_orders":r["sell_orders"],
            "legs":[{"side":x["side"],"start":x["start"],
                     "end":x["end"],"orders":x["orders"],
                     "gross_notional_aud":round(x["gross_notional_aud"],2),
                     "effective_price_aud":round(x["net_effective_price_aud"],2),
                     "calendar_weeks":(history.index.get_loc(pd.Timestamp(x["end"]))
                                       -history.index.get_loc(pd.Timestamp(x["start"]))+1)}
                    for x in legs],
            "accuracy":scored,
        })
    return {
        "research_only":True,
        "observations":len(history),
        "start":str(history.index[0]),
        "end":str(history.index[-1]),
        "fee_per_filled_order_aud":FLAT_FEE_AUD,
        "buy_condition":"prior-risk <= 0.35 and cash available",
        "sell_arm_risk":BULL_ARM_RISK,
        "no_fixed_trade_duration":True,
        "candidates":candidates,
        "warnings":[
            "Strictly research: neither strategy validated out of sample.",
            "Risk source timestamp integrity remains to be audited.",
            "Weekly execution close idealised despite one-week signal lag.",
            "No CGT/ETF management fees/spreads; flat A$3 per actual fill.",
            "Hindsight high/low only used for retrospective scoring.",
            "Cash availability/market regime errors may be larger than VWAP error.",
            "Only a few BTC major market cycles exist; hit-rate uncertain.",
            "No future data enters trade decisions, but rules are in-sample hypotheses.",
        ],
    }


def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--output",default="")
    args=ap.parse_args()
    from engines.shared.central_data import load_master
    raw=load_master(columns=["btc_price_aud","risk_score"])
    numeric=raw[["btc_price_aud","risk_score"]].apply(pd.to_numeric,errors="coerce")
    valid=(np.isfinite(numeric["btc_price_aud"])
           & numeric["btc_price_aud"].gt(0)
           & np.isfinite(numeric["risk_score"])
           & numeric["risk_score"].between(0,1))
    r=report_adaptive(numeric.loc[valid])
    r["source_valid_rows"]=int(valid.sum())
    out=json.dumps(r,indent=2,allow_nan=False,
                   default=lambda x:x.item() if isinstance(x,np.generic) else str(x))
    if args.output:
        from pathlib import Path
        Path(args.output).write_text(out+"\n",encoding="utf-8")
    print(out)


if __name__=="__main__":
    main()
