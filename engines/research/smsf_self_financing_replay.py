"""Research-only self-financing trade-size comparison with illustrative SMSF tax.

All replay variants use the *same signal-derived transaction opportunities* from
the previous causal 10%-confirmation adaptive experiment. This freezes when
BUY/SELL opportunities arise, comparing independent capital/btc accounts for:
  - adaptive: existing variable fraction of holdings,
  - constant_rate: 10% of remaining cash or 20% of BTC at each opportunity,
  - trend_reserve: causal previous-week drawdown-weighted buying and price-rank
    weighted selling, exploratory and NOT prevalidated.

All accounts recycle ONLY net sale proceeds, allocate A$3 fee PER executed
order, and apply conservative immediate estimated CGT cash withholding with
FIFO BTC parcels. Long-term gains held STRICTLY >12 calendar months receive
the simplified effective SMSF rate 10% in accumulation; shorter gains 15%.
Losses offset short gains then discounted long gains, carried forward if unused.
This model is a sensitivity only: ATO rules are more detailed, tax is usually
calculated for a financial year, fund/pension circumstances vary, and nothing
here constitutes individual tax advice.

Risk inputs from historical master do not yet have verified point-in-time
data vintages. No future BTC price used for position decisions. No production
or user portfolio writes.
"""
import argparse
import copy
import json
import math

import numpy as np
import pandas as pd

from engines.research.adaptive_dca_execution import simulate_adaptive
from engines.research.full_cycle_reinvestment import CAPITAL, validate_history

FEE_AUD=3.0
DUST_AUD=100.0
SELL_CONFIRMED_DROP=.10
VARIANTS=("adaptive","constant_rate","trend_reserve")


class AuditSmsfAccount:
    """Cash + FIFO BTC tax lots; immediate tax cash escrow approximation."""
    def __init__(self, starting_cash=CAPITAL, *, fee=FEE_AUD, tax=True):
        if not math.isfinite(starting_cash) or starting_cash <= 0:
            raise ValueError("Starting cash must be positive")
        if fee < 0 or not math.isfinite(fee):
            raise ValueError("Invalid fee")
        self.cash=float(starting_cash)
        self.lots=[]
        self.fee=float(fee)
        self.tax_enabled=bool(tax)
        self.loss_carry=0.
        self.total_fees=0.
        self.total_tax=0.
        self.gains_short=0.
        self.gains_long=0.
        self.realised_losses=0.
        self.orders=[]
        self.equity_peak=self.cash
        self.drawdown=0.

    @property
    def btc(self):
        return sum(l["qty"] for l in self.lots)

    def buy(self, date, price, pct):
        if not (0 <= pct <= 1):
            raise ValueError("Invalid buy percentage")
        gross=min(self.cash,self.cash*pct)
        if gross <= max(DUST_AUD,self.fee*2):
            return False
        qty=(gross-self.fee)/price
        if qty <= 0:
            return False
        self.cash-=gross
        self.lots.append({"date":pd.Timestamp(date),"qty":qty,
                          "cost":gross})
        self.total_fees+=self.fee
        self.orders.append({"date":str(date),"side":"BUY","btc":qty,
                            "gross_aud":gross,"tax_aud":0.,
                            "price_aud":price})
        return True

    def sell(self, date, price, pct):
        if not (0 <= pct <= 1):
            raise ValueError("Invalid sell percentage")
        qty=self.btc*pct
        gross=qty*price
        if qty <= 1e-12 or gross <= max(DUST_AUD,self.fee*2):
            return False
        now=pd.Timestamp(date)
        remaining=qty
        short_gain=long_gain=realised_loss=0.
        while remaining > 1e-10:
            if not self.lots:
                raise ArithmeticError("Selling unowned BTC")
            lot=self.lots[0]
            lotqty=lot["qty"]
            sold=min(lotqty,remaining)
            basis=lot["cost"]*sold/lotqty
            proceeds=sold*price-self.fee*sold/qty
            gain=proceeds-basis
            if gain < 0:
                realised_loss+=-gain
            elif now>lot["date"]+pd.DateOffset(years=1):
                long_gain+=gain
            else:
                short_gain+=gain
            lot["qty"]-=sold
            lot["cost"]-=basis
            remaining-=sold
            if lot["qty"] <= 1e-10:
                self.lots.pop(0)
        if not self.tax_enabled:
            tax=0.
        else:
            available_losses=self.loss_carry+realised_loss
            offset_short=min(available_losses,short_gain)
            available_losses-=offset_short
            offset_long=min(available_losses,long_gain)
            available_losses-=offset_long
            tax=.15*(short_gain-offset_short)+.10*(long_gain-offset_long)
            self.loss_carry=available_losses
        self.cash+=gross-self.fee-tax
        if self.cash < -1e-6:
            raise ArithmeticError("Negative proceeds after tax")
        self.total_fees+=self.fee
        self.total_tax+=tax
        self.gains_short+=short_gain
        self.gains_long+=long_gain
        self.realised_losses+=realised_loss
        self.orders.append({"date":str(date),"side":"SELL","btc":qty,
                            "gross_aud":gross,"tax_aud":tax,
                            "price_aud":price})
        return True

    def mark(self, price):
        eq=self.cash+self.btc*price
        self.equity_peak=max(self.equity_peak,eq)
        self.drawdown=min(self.drawdown,eq/self.equity_peak-1)
        return eq

    def liquidation_value(self,date,price):
        hypothetical=copy.deepcopy(self)
        if hypothetical.btc*price <= max(DUST_AUD,self.fee*2):
            return hypothetical.cash+hypothetical.btc*price
        hypothetical.sell(date,price,1.0)
        return hypothetical.cash


def sizing(policy, event, prices, risks, event_index):
    if policy=="adaptive":
        return float(event["fraction_of_available_at_trade"])
    if policy=="constant_rate":
        return .10 if event["side"]=="BUY" else .20
    if policy!="trend_reserve":
        raise ValueError("Unknown sizing policy")
    j=event_index-1
    if j<0:
        raise ValueError("No prior observation for signal")
    p=float(prices[j])
    r=float(risks[j])
    if event["side"]=="BUY":
        trailing_high=float(np.max(prices[max(0,j-51):j+1]))
        dd=max(0.,1-p/trailing_high)
        cheap=min(1.,max(0.,(.35-r)/.35))
        # Hold more cash until the last-observed drawdown is deeper.
        return max(.025,min(.24,.025+.20*max(0.,dd-.30)+.07*cheap))
    if event["side"]=="SELL":
        look=np.asarray(prices[max(0,j-25):j+1],dtype=float)
        hi,lo=float(look.max()),float(look.min())
        rank=(p-lo)/(hi-lo) if hi>lo else .5
        # Sell more when price is closer to its observed recent high.
        return max(.03,min(.32,.04+.27*rank))
    raise ValueError("Unknown opportunity side")


def replay(history, events, *, policy="adaptive", tax=True, starting_cash=CAPITAL):
    d=validate_history(history)
    if not isinstance(d.index,pd.DatetimeIndex):
        raise ValueError("DatetimeIndex required")
    prices=d["btc_price_aud"].to_numpy(float)
    risk=d["risk_score"].to_numpy(float)
    index_map={str(timestamp):i for i,timestamp in enumerate(d.index)}
    acc=AuditSmsfAccount(starting_cash,tax=tax)
    used_dates=set()
    for event in events:
        stamp=event["date"]
        if stamp in used_dates:
            raise ValueError("Duplicate execution date")
        used_dates.add(stamp)
        j=index_map[stamp]
        if j<1:
            raise ValueError("Future/past execution mismatch")
        pct=sizing(policy,event,prices,risk,j)
        cur=float(prices[j])
        if event["side"]=="BUY":
            acc.buy(d.index[j],cur,pct)
        elif event["side"]=="SELL":
            acc.sell(d.index[j],cur,pct)
        else:
            raise ValueError("Invalid event side")
    for i in range(1,len(d)):
        acc.mark(float(prices[i]))
    terminal_price=float(prices[-1])
    return {
        "policy":policy,
        "fee_per_order_aud":acc.fee,
        "tax_assumed":tax,
        "execution_opportunity_dates":len(events),
        "actual_orders":len(acc.orders),
        "buy_orders":sum(x["side"]=="BUY" for x in acc.orders),
        "sell_orders":sum(x["side"]=="SELL" for x in acc.orders),
        "btc":round(acc.btc,8),
        "cash_aud":round(acc.cash,2),
        "ending_marked_equity_aud":round(acc.cash+acc.btc*terminal_price,2),
        "hypothetical_final_liquidation_after_cgt_aud":
            round(acc.liquidation_value(d.index[-1],terminal_price),2),
        "total_realized_cgt_estimate_aud":round(acc.total_tax,2),
        "total_brokerage_aud":round(acc.total_fees,2),
        "capital_losses_carried_aud":round(acc.loss_carry,2),
        "max_account_drawdown_pct":round(acc.drawdown*100,2),
        "orders":acc.orders,
    }


def matched_buy_and_hold(data, *, tax=True, capital=CAPITAL):
    d=validate_history(data)
    prices=d["btc_price_aud"].to_numpy(float)
    acc=AuditSmsfAccount(capital,tax=tax)
    acc.buy(d.index[1],float(prices[1]),1.)
    for j in range(1,len(d)):
        acc.mark(float(prices[j]))
    return {
        "capital_aud":capital,
        "ending_marked_equity_aud":round(acc.cash+acc.btc*prices[-1],2),
        "hypothetical_final_liquidation_after_cgt_aud":
            round(acc.liquidation_value(d.index[-1],float(prices[-1])),2),
        "fee_initial_aud":FEE_AUD,
        "final_btc":round(acc.btc,8),
    }


def evaluate(data):
    history=validate_history(data)
    reference=simulate_adaptive(history,confirm_drawdown=SELL_CONFIRMED_DROP)
    events=reference["trades"]
    baseline=replay(history,events,policy="adaptive",tax=False)
    original=reference["ending_equity_aud"]
    # The fraction is rounded to 7 decimals in the originating execution
    # log, so the same self-financing replay may differ by small roundoff.
    if abs(baseline["ending_marked_equity_aud"]/original-1)>2e-5:
        raise AssertionError("Failed to reproduce no-tax adaptive research account")
    models=[]
    for tax in (False,True):
        for policy in VARIANTS:
            x=replay(history,events,policy=policy,tax=tax)
            x.pop("orders")  # historical raw orders remain internal / no PII
            models.append(x)
    return {
        "research_only":True,
        "observations":len(history),
        "start":str(history.index[0]),
        "end":str(history.index[-1]),
        "starting_capital_aud":CAPITAL,
        "original_signal_opportunities":len(events),
        "benchmark_no_rebalancing":matched_buy_and_hold(history,tax=True),
        "replayed_portfolios":models,
        "warnings":[
            "Same signal-derived trade-opportunity calendar across all policies, sourced from the original adaptive model.",
            "Each variant is self-financing: after-tax sale proceeds only; no external capital.",
            "The hypothetical trend_reserve challenger is an IN-SAMPLE exploratory hypothesis, not verified forward.",
            "FIFO purchase parcels, simplified 15% short/10% discounted long SMSF accumulation CGT.",
            "CGT on proceeds is escrowed immediately; actual SMSF tax settled per financial year and other capital losses/gains can change tax.",
            "Tax rates/discounts assume a complying fund in accumulation and exclude pension phase; not tailored tax advice.",
            "No dividends, ETF tracking fees, spreads, price impact, pension limits, cash return or terminal market impact.",
            "Terminal hypothetical liquidation includes CGT; holding-period and capital-loss treatment estimated.",
            "Entire full-cycle account starts with AUD 500,000 in 2016, NOT an AUD 500,000 forecast from 2026.",
            "Risk score historical source-vintage may be retrospectively constructed; still unverified.",
            "Unit-tested code only; no untouched holdout and no changes to Production/master/portfolio.",
        ],
    }


def main():
    p=argparse.ArgumentParser()
    p.add_argument("--output",default="")
    args=p.parse_args()
    from engines.shared.central_data import load_master
    raw=load_master(columns=["btc_price_aud","risk_score"])
    frame=raw[["btc_price_aud","risk_score"]].apply(pd.to_numeric,errors="coerce")
    mask=np.isfinite(frame["btc_price_aud"])&frame["btc_price_aud"].gt(0)&frame["risk_score"].between(0,1)
    result=evaluate(frame.loc[mask])
    result["source_valid_rows"]=int(mask.sum())
    out=json.dumps(result,indent=2,allow_nan=False,
                   default=lambda x:x.item() if isinstance(x,np.generic) else str(x))
    if args.output:
        from pathlib import Path
        Path(args.output).write_text(out+"\n",encoding="utf-8")
    print(out)


if __name__=="__main__":
    main()
