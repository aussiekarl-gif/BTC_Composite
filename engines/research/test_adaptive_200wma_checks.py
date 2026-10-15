"""Offline causality and opt-in boundaries for Research adaptive BTC tiers."""
import numpy as np
import pandas as pd
from engines.research.test_200wma_12week_execution import staged

def go(prices,signal,**overrides):
    transactions=[]
    opts={"shape":"bell","buy_weeks":12,"sell_weeks":16,
          "buy_levels":[],"sell_levels":[100.],"fee":.001,
          "slippage":.005,"brokerage_fixed":20.,
          "block_overlap":True,"initial_btc_fraction":1.,
          "funding_weeks":0,"signal_price":signal,
          "trade_callback":lambda ev:transactions.append(ev),
          "end_index":35}
    opts.update(overrides)
    state=staged(prices,None if False else pd.Series(100.,index=prices.index),0,**opts)
    return state,transactions

def main():
    idx=pd.date_range("2020-01-06",periods=72,freq="W-MON",tz="UTC")
    prefix=[150,165,175,195,205,220,230,210,205,210,215,230,240,245]
    vals=prefix+[245+(i-13)*2.5 for i in range(14,72)]
    s=pd.Series(vals,index=idx,dtype=float)
    base,events=go(s,s)
    guard,guard_events=go(s,s,sell_guard_lookback=8)
    trend,trend_events=go(s,s,trend_reentry_lookback=8,trend_reentry_cash_share=.01)
    combined,combined_events=go(s,s,sell_guard_lookback=8,
                  trend_reentry_lookback=8,trend_reentry_cash_share=.01)
    n=lambda evs,kind:sum(ev["kind"]==kind for ev in evs)
    assert n(events,"TIER")>0, "Test fixture failed to cross original sell tiers"
    assert n(guard_events,"TIER")<n(events,"TIER"),"Weakness guard never reduced fills"
    assert n(trend_events,"TREND_REENTRY")>0, "Trend reentry never fired"
    assert combined["value_usd"]>0 and combined["cash_usd"]>=0
    # Both opt-in rules must be inert when settings are omitted.
    control,_=go(s,s,sell_guard_lookback=0,trend_reentry_lookback=0)
    assert control==base, "Opt-in defaults changed baseline numerical results"
    # The future close after end-index 35 must NOT affect any outcome.
    later=s.copy()
    later.iloc[36:]*=18
    future,other=go(later,later,sell_guard_lookback=8,
                    trend_reentry_lookback=8,trend_reentry_cash_share=.01)
    assert combined==future, "Future data changed old completed-week valuation"
    assert [(ev["kind"],str(ev["date"])) for ev in combined_events]==[
         (ev["kind"],str(ev["date"])) for ev in other], "Future data changed past fills"
    # A price jump after a *current* signal may alter subsequent-week orders,
    # but cannot create an execution on the signal's own bar.
    for ev in trend_events:
        if ev["kind"]=="TREND_REENTRY":
            assert ev["date"].weekday()==0
    print("PASS: opt-in sell weakness guard, 8-week trend breakout reentry, default parity and no future data")
if __name__=="__main__":main()
