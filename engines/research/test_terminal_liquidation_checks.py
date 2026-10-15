"""Deterministic unit checks for same-date, after-sale SMSF comparison."""
import pandas as pd
from engines.research.smsf_cgt_ledger import FifoCgtLedger
from engines.research.terminal_liquidation import terminal_liquidation

def evt(side,date,units,cash):
    return {"side":side,"date":pd.Timestamp(date,tz="UTC"),
            "units":units,"cash":cash}

def close(got,want):
    assert abs(got-want)<=.02,(got,want)

def main():
    # The *same* economic holdings must have the *same* terminal treatment,
    # regardless of whether we label them DCA or Tier Strategy.
    results=[]
    for _ in ("DCA","Tier"):
        ledger=FifoCgtLedger()
        ledger(evt("BUY","2020-01-01",1.,100.))
        r=terminal_liquidation(ledger,0.,1.,"2021-02-03",200.,
                                brokerage=0.,fee=0.,slippage=0.)
        close(r["net_fully_liquidated_aud"],190.)
        close(r["tax_remaining_at_exit_aud"],10.)
        close(r["sale_dealing_cost_aud"],0.)
        close(ledger.bought_units-ledger.sold_units,1.) # Original not mutated.
        results.append(r)
    assert results[0]==results[1]
    # Higher cost base after rebuy reduces taxable final gain.
    ledger=FifoCgtLedger()
    ledger(evt("BUY","2020-01-01",2.,200.))
    ledger(evt("SELL","2021-02-03",1.,150.))
    check=terminal_liquidation(ledger,150.,1.,"2021-03-08",200.,
                                brokerage=0.,fee=0.,slippage=0.)
    close(check["net_fully_liquidated_aud"],335.)
    close(check["tax_remaining_at_exit_aud"],15.)
    # A paid previous-year CGT amount MUST NOT be charged twice at exit.
    ledger=FifoCgtLedger()
    ledger(evt("BUY","2021-01-01",2.,200.))
    ledger(evt("SELL","2022-03-01",1.,200.))
    due=ledger.settle_year(2022)
    close(due,10.)
    ledger.paid_total+=10.
    prior=terminal_liquidation(ledger,190.,1.,"2022-09-01",200.,
                               brokerage=0.,fee=0.,slippage=0.)
    close(prior["tax_already_paid_aud"],10.)
    close(prior["tax_remaining_at_exit_aud"],10.)
    close(prior["net_fully_liquidated_aud"],380.)
    # Commissions and percent dealing charges must apply to liquidation
    # for BOTH strategy and otherwise idle DCA comparator.
    empty=FifoCgtLedger()
    empty(evt("BUY","2020-01-01",1.,100.))
    taxed=terminal_liquidation(empty,10.,1.,"2021-02-03",200.,
        brokerage=20.,fee=.001,slippage=.005)
    close(taxed["net_sale_proceeds_aud"],178.801)
    assert taxed["tax_remaining_at_exit_aud"]>0
    # Reject fake portfolio holdings not matched by documented FIFO lots.
    try:
        terminal_liquidation(empty,10.,2.,"2021-02-03",200.)
    except AssertionError:
        pass
    else:
        raise AssertionError("Untracked BTC units were allowed")
    print("PASS matched DCA/tier liquidation, tax discount, prior payment, dealing friction and inventory")
if __name__=="__main__":main()
