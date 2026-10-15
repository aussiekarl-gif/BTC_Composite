"""Research-only 200WMA 10-buy / 10-sell tier dashboard.
No portfolio writes, no orders, no Production mutations.
"""
import pandas as pd
import numpy as np
import streamlit as st
from pathlib import Path

st.title("200WMA Trading Model — Research")
st.caption("10 buying tiers + 10 selling tiers | historical weekly USD data | read-only simulator")
st.warning("Experimental model. Signals are illustrative, not live AUD orders. No portfolio changes are made.")
source=Path(__file__).resolve().parents[2]/"data"/"price_200_week_moving_average_200wma__2026-10-07T21-20-24.csv"
if not source.exists():
    st.error("Historical 200WMA data missing")
    st.stop()
@st.cache_data
def load(path):
    d=pd.read_csv(path)
    d["date"]=pd.to_datetime(d["timestamp"],unit="ms",utc=True)
    d["Price"]=pd.to_numeric(d["Price"],errors="coerce")
    s=pd.Series(d["Price"].to_numpy(),index=d["date"]).sort_index().resample("W-MON").last().dropna()
    ma=s.shift(1).rolling(200,min_periods=200).mean()
    return pd.DataFrame({"BTC/USD":s,"200WMA (prior 200 weeks)":ma}).dropna()
data=load(str(source))
if data.empty:st.error("Insufficient historical data");st.stop()
current=data.iloc[-1]
price=float(current.iloc[0]);ma=float(current.iloc[1]);deviation=(price/ma-1)*100
c1,c2,c3=st.columns(3)
c1.metric("Last historical BTC/USD",f"${price:,.0f}")
c2.metric("Prior 200WMA",f"${ma:,.0f}")
c3.metric("Deviation from 200WMA",f"{deviation:+.1f}%")
st.caption(f"Latest historical week: {data.index[-1].date()}; prices are NOT live.")
st.subheader("Editable tier matrix")
buy_default=[25,20,15,10,5,0,-5,-10,-20,-30]
sell_default=[100,120,140,160,180,200,220,240,260,280]
col1,col2=st.columns(2)
with col1:
    st.markdown("**10 buying tiers (% from 200WMA)**")
    buys=[st.number_input(f"Buy tier {i+1} (%)",value=float(v),step=5.,key=f"wma_buy_{i}") for i,v in enumerate(buy_default)]
with col2:
    st.markdown("**10 selling tiers (% from 200WMA)**")
    sells=[st.number_input(f"Sell tier {i+1} (%)",value=float(v),step=5.,key=f"wma_sell_{i}") for i,v in enumerate(sell_default)]
if not all(buys[i]>buys[i+1] for i in range(9)):
    st.error("Buy tiers must be strictly descending.")
if not all(sells[i]<sells[i+1] for i in range(9)):
    st.error("Sell tiers must be strictly ascending.")
buy_alloc=st.slider("Cash allocation per triggered buy tier (% of initial cash reserve)",1,20,10)
sell_alloc=st.slider("BTC allocation per triggered sell tier (% of cycle-start BTC)",1,10,10)
rows=[]
for i,x in enumerate(buys):
    rows.append({"Action":"BUY","Tier":i+1,"Deviation":f"{x:+.0f}%","BTC/USD trigger":round(ma*(1+x/100),2),"Tranche":f"{buy_alloc}% initial cash"})
for i,x in enumerate(sells):
    rows.append({"Action":"SELL","Tier":i+1,"Deviation":f"{x:+.0f}%","BTC/USD trigger":round(ma*(1+x/100),2),"Tranche":f"{sell_alloc}% cycle-start BTC"})
st.dataframe(pd.DataFrame(rows),use_container_width=True,hide_index=True)
st.info("Tier execution must be crossing-based, next-week, and once per cycle. Cycle reset, cash reserve, and AUD portfolio integration require separate validation before any automated action.")
st.subheader("Historical price / 200WMA")
st.line_chart(data.tail(260))
