"""Small deterministic FIFO CGT / July settlement checks, research only."""
import pandas as pd
from engines.research.smsf_cgt_ledger import FifoCgtLedger,AnnualSmsfTaxPayment

def event(side,date,units,cash):
    return {"side":side,"date":pd.Timestamp(date,tz="UTC"),
            "units":float(units),"cash":float(cash)}

def near(actual,expected):
    if abs(actual-expected)>0.01:raise AssertionError((actual,expected))

def main():
    # Complying fund held a unit more than 12 months, 1/3 discount.
    a=FifoCgtLedger()
    a(event("BUY","2020-01-01",1,100))
    a(event("SELL","2021-02-03",1,200))
    near(a.tax_summary()["estimated_total_tax"],10)
    # Loss from prior Australian financial year offsets later short gain.
    b=FifoCgtLedger()
    b(event("BUY","2022-01-01",1,100))
    b(event("SELL","2022-02-01",1,80))
    b(event("BUY","2022-08-01",1,100))
    b(event("SELL","2022-09-01",1,150))
    near(b.tax_summary()["estimated_total_tax"],4.5)
    # FIFO first parcel sold: second purchase stays in inventory.
    c=FifoCgtLedger()
    c(event("BUY","2020-01-01",1,100))
    c(event("BUY","2021-01-01",1,300))
    c(event("SELL","2021-03-01",1,200))
    near(c.tax_summary()["estimated_total_tax"],10.)
    near(c.tax_summary()["net_units"],1.)
    # Annual charge paid from cash (no financing disposal).
    d=FifoCgtLedger()
    d(event("BUY","2023-03-01",1,100))
    d(event("SELL","2023-06-26",1,200))
    hook=AnnualSmsfTaxPayment(d,brokerage=10.,fee=0.,slippage=0.)
    cash,btc=hook(0,pd.Timestamp("2023-06-26",tz="UTC"),200.,100.,0.)
    cash,btc=hook(1,pd.Timestamp("2023-07-03",tz="UTC"),200.,cash,btc)
    near(cash,85)
    near(d.tax_summary()["tax_cash_paid"],15)
    # If insufficient cash, sell ETF units, creating a new CGT event.
    e=FifoCgtLedger()
    e(event("BUY","2023-03-01",2,200))
    e(event("SELL","2023-06-26",1,200))
    hook=AnnualSmsfTaxPayment(e,brokerage=10.,fee=0.,slippage=0.)
    cash,btc=hook(0,pd.Timestamp("2023-06-26",tz="UTC"),200.,0.,1.)
    cash,btc=hook(1,pd.Timestamp("2023-07-03",tz="UTC"),200.,cash,btc)
    near(cash,0.)
    near(btc,0.875)
    if hook.financing_sales!=1:raise AssertionError("Expected financing disposal")
    near(e.tax_summary()["net_units"],0.875)
    print("PASS: FIFO, 12-month discount, loss carry, July cash settlement, tax-financing sale")

if __name__=="__main__":main()
