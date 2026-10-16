"""Offline regression: DCA and no-tier staged simulator must be identical.

This catches asymmetric initial slippage, 12-week cash weighting and
terminal liquidation assumptions before expensive AUD backtests.
"""
import numpy as np
import pandas as pd

from engines.research.test_200wma_cash_deployment import run as dca
from engines.research.test_200wma_12week_execution import staged
from engines.research.smsf_cgt_ledger import FifoCgtLedger
from engines.research.terminal_liquidation import terminal_liquidation

def run():
    dates=pd.date_range("2022-01-03",periods=52,freq="W-MON",tz="UTC")
    t=np.arange(len(dates))
    px=pd.Series(25000.+4000.*np.sin(t/7.)+550.*t,index=dates)
    signal=px*1.4
    ma=pd.Series(35000.,index=dates)
    for slippage in (0.,.005,.02):
        a=FifoCgtLedger()
        b=FifoCgtLedger()
        kwargs={"signal_price":signal,"brokerage_fixed":20.,"slippage":slippage,
                "fee":.001}
        control=dca(px,ma,0,40,12,True,trade_callback=a,**kwargs)
        trial=staged(px,ma,0,end_index=40,shape="bell",
            buy_levels=[],sell_levels=[],initial_btc_fraction=.2,
            funding_weeks=12,funding_weighted=True,block_overlap=True,
            trade_callback=b,**kwargs)
        assert abs(control["value_usd"]-trial["value_usd"])<.03,(slippage,control,trial)
        assert abs(control["btc"]-trial["btc_held"])<1e-7
        assert abs(control["cash_usd"]-trial["cash_usd"])<.03
        close_a=terminal_liquidation(a,control["cash_usd"],a.bought_units-a.sold_units,
                dates[40],px.iloc[40],brokerage=20.,fee=.001,slippage=slippage)
        close_b=terminal_liquidation(b,trial["cash_usd"],b.bought_units-b.sold_units,
                dates[40],px.iloc[40],brokerage=20.,fee=.001,slippage=slippage)
        assert close_a==close_b,(slippage,close_a,close_b)
    print("PASS same-cost DCA and no-tier staged simulator match for 0%, 0.5%, 2% slippage")
if __name__=="__main__":run()
