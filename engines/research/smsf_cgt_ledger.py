"""Illustrative SMSF capital-gains model using FIFO trade lots in AUD.

Assumes compliant fully taxable accumulation SMSF: 15% on the net gain
after allowed one-third long-held capital gains discount. Losses offset
short-term gains first, then discounted gains, with remaining losses
carried to future Australian financial years. No other fund income.
This is not tax advice or a complete annual SMSF tax return.
"""
from collections import defaultdict,deque
import pandas as pd

class FifoCgtLedger:
    def __init__(self):
        self.lots=deque()
        self.purchases=0
        self.bought_units=0.
        self.sold_units=0.
        self.years=defaultdict(lambda:{"short":0.,"long":0.,"loss":0.,"sells":0})
        self.loss_carry=0.
        self.settled={}
        self.paid_total=0.

    def __call__(self,trade):
        day=pd.Timestamp(trade["date"])
        units=float(trade["units"])
        cash=float(trade["cash"])
        if units<=1e-9:raise AssertionError("Nonpositive fill units")
        if trade["side"]=="BUY":
            self.purchases+=1
            self.bought_units+=units
            self.lots.append([day,units,cash/units])
            return
        if trade["side"]!="SELL":raise AssertionError("Unknown fill side")
        year=int(day.year+(day.month>=7))
        acc=self.years[year]
        acc["sells"]+=1
        self.sold_units+=units
        left=units
        while left>1e-9:
            if not self.lots:raise AssertionError("FIFO inventory exhausted")
            lot=self.lots[0]
            chunk=min(left,lot[1])
            gain=chunk*(cash/units-lot[2])
            if gain<0:acc["loss"]+=-gain
            else:
                qualifies=day>lot[0]+pd.DateOffset(years=1)
                acc["long" if qualifies else "short"]+=gain
            lot[1]-=chunk
            left-=chunk
            if lot[1]<=1e-9:self.lots.popleft()

    def settle_year(self,year):
        """Calculate tax for one elapsed Australian financial year only once."""
        if year in self.settled:return self.settled[year]["tax_15pct"]
        if self.settled and year<=max(self.settled):raise AssertionError("Tax years not chronological")
        acc=self.years[year]
        losses=self.loss_carry+acc["loss"]
        short=max(0.,acc["short"]-losses)
        losses=max(0.,losses-acc["short"])
        long=max(0.,acc["long"]-losses)
        self.loss_carry=max(0.,losses-acc["long"])
        taxable=short+long*2/3
        row={"fy_end":year,"tax_15pct":round(taxable*0.15,2),
             "gain_short":round(acc["short"],2),
             "gain_long":round(acc["long"],2),
             "capital_losses":round(acc["loss"],2),
             "loss_carry":round(self.loss_carry,2),"sells":acc["sells"]}
        self.settled[year]=row
        return row["tax_15pct"]

    def tax_summary(self):
        for year in sorted(self.years):
            if year not in self.settled:self.settle_year(year)
        taxes=[self.settled[year] for year in sorted(self.settled)]
        total=round(sum(x["tax_15pct"] for x in taxes),2)
        return {"estimated_total_tax":total,
                "tax_cash_paid":round(self.paid_total,2),
                "tax_outstanding":round(total-self.paid_total,2),
                "by_year":taxes,
                "purchases":self.purchases,
                "sell_fills":sum(x["sells"] for x in taxes),
                "net_units":self.bought_units-self.sold_units}


class AnnualSmsfTaxPayment:
    """Stress: settle preceding financial-year CGT at first weekly July close.

    This is earlier than the usual SMSF annual-return payment schedule, so
    it is deliberately conservative, not a literal ATO lodgement timetable.
    Cash is used first; if short, sell enough ETF units to pay tax plus
    brokerage and dealing friction, adding those new disposals to FIFO CGT.
    """
    def __init__(self,ledger,brokerage,fee,slippage):
        self.ledger=ledger
        self.brokerage=brokerage
        self.fee=fee
        self.slippage=slippage
        self.previous_fy=None
        self.financing_sales=0
        self.financing_units=0.

    def __call__(self,_index,date,price,cash,btc):
        day=pd.Timestamp(date)
        fy=int(day.year+(day.month>=7))
        previous=self.previous_fy
        self.previous_fy=fy
        if previous is None or previous==fy:return cash,btc
        if fy<previous:raise AssertionError("Nonchronological dates")
        for year in range(previous,fy):
            tax=self.ledger.settle_year(year)
            if tax<=0:continue
            if cash+1e-7<tax:
                per_unit=float(price)*(1-self.fee)*(1-self.slippage)
                quantity=(tax-cash+self.brokerage)/per_unit
                if quantity>btc+1e-7:
                    raise ArithmeticError("Not enough ETF holdings to fund annual CGT")
                quantity=min(quantity,btc)
                received=quantity*per_unit-self.brokerage
                cash+=received;btc-=quantity
                self.ledger({"side":"SELL","kind":"TAX_PAYMENT",
                             "date":day,"units":quantity,"cash":received,
                             "price":float(price),"brokerage":self.brokerage})
                self.financing_sales+=1
                self.financing_units+=quantity
            if tax>cash+1e-6:raise ArithmeticError("Unfunded tax cash payment")
            cash-=tax
            self.ledger.paid_total+=tax
        return cash,btc
