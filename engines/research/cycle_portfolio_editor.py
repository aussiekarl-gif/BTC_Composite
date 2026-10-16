"""Streamlit forms for actual, manually executed BUY and SELL transactions.

Use existing Google Sheets portfolio_state JSON, preserving original buys.
All execution fields are user-supplied confirmations, not automatic trades.
"""
from __future__ import annotations
import datetime as dt
import json

import pandas as pd
import streamlit as st

from engines.shared.portfolio_store import load_portfolio,save_portfolio
from engines.shared.portfolio_transactions import (
    portfolio_positions,append_with_stale_guard,
)


def show_portfolio_editor(portfolio,*,today,ibit_quote=None,btc_aud_quote=None,
                          store_error=None):
    st.subheader("Record executed BUY or SELL")
    st.caption(
        "Only record a transaction after it actually fills. "
        "The automatic IBIT quote is an indicative default; correct it to "
        "your broker's ACTUAL fill price. Your old purchases stay intact."
    )
    if store_error or not isinstance(portfolio,dict):
        st.error("Your saved Google Sheets portfolio must load successfully before editing.")
        return
    try:
        positions=portfolio_positions(portfolio)
    except ValueError as exc:
        st.error("Portfolio ledger needs correction: "+str(exc))
        return

    x,y,z=st.columns(3)
    x.metric("Net ASX:IBIT units",f"{positions['ibit_units']:,.0f}")
    y.metric("Direct BTC held",f"{positions['direct_btc']:.8f}")
    z.metric("Available recorded cash",f"A${positions['cash_remaining_aud']:,.2f}")
    st.caption(
        f"{positions['number_buys']} recorded buys and "
        f"{positions['number_sells']} recorded sells. "
        "These balances come from recorded executions; verify with your broker."
    )

    with st.form("cycle_portfolio_executed_trade_form",clear_on_submit=False):
        left,right=st.columns(2)
        with left:
            side=st.selectbox("Transaction",["BUY","SELL"],key="cycle_editor_side")
            asset=st.selectbox("Asset",["ASX:IBIT","Direct BTC"],key="cycle_editor_asset")
            day=st.date_input("Executed on",value=today,max_value=today,
                              key="cycle_editor_day")
            qty=st.number_input(
                "Quantity — whole ASX:IBIT units or direct BTC",
                min_value=0.0,value=0.0,step=1.0,format="%.8f",
                key="cycle_editor_qty")
        with right:
            suggest=(ibit_quote if asset=="ASX:IBIT" else btc_aud_quote) or 0.
            price=st.number_input(
                "Actual executed AUD price PER unit / BTC",
                min_value=0.0,value=float(suggest),
                step=0.01,format="%.4f",key="cycle_editor_fill_price",
                help="Use your broker's actual execution price, not the suggested delayed quote."
            )
            fee=st.number_input("Actual transaction fees (AUD)",
                min_value=0.,value=3.,step=1.,format="%.2f",
                key="cycle_editor_fee")
            btc_aud=st.number_input(
                "BTC/AUD reference on the BUY date (ASX:IBIT only)",
                min_value=0.,value=float(btc_aud_quote or 0.),
                step=100.,format="%.2f",key="cycle_editor_btc_aud",
                help="For historical buys enter the historical BTC/AUD price, "
                     "NOT the current price. Used for estimated ETF BTC exposure only."
            )
            notes=st.text_input("Order reference / notes (optional)",
                                 key="cycle_editor_notes")
        confirm=st.checkbox(
            "I confirm this transaction has actually executed at my broker",
            key="cycle_editor_confirm")
        submit=st.form_submit_button("Save executed transaction",
                 type="primary",use_container_width=True)
    if submit:
        if not confirm:
            st.error("Confirm the broker execution before saving.")
        else:
            latest,read_error=load_portfolio()
            if read_error:
                st.error("Could not reread Google Sheets before saving: "+read_error)
            else:
                try:
                    updated,after=append_with_stale_guard(
                        portfolio,latest,side=side,asset=asset,
                        trade_date=day,quantity=qty,trade_price_aud=price,
                        fee_aud=fee,btc_aud_price=btc_aud,note=notes)
                    ok,error=save_portfolio(updated)
                    if not ok:
                        st.error("Save failed; verify ledger before retrying: "+str(error))
                    else:
                        st.success(
                            f"Saved {side} {qty:.8f} {asset}. Recorded balance: "
                            f"{after['ibit_units']:,.0f} ASX:IBIT units; "
                            f"{after['direct_btc']:.8f} BTC; "
                            f"A${after['cash_remaining_aud']:,.2f} cash."
                        )
                        st.cache_data.clear()
                        st.rerun()
                except ValueError as exc:
                    st.error(str(exc)+" — no transaction was saved.")

    buys=portfolio.get("rows",[])
    sells=portfolio.get("sales",[])
    st.subheader("Recorded purchases")
    if buys:
        st.dataframe(pd.DataFrame(buys),hide_index=True,width="stretch")
    else:
        st.info("No recorded purchases yet.")
    st.subheader("Recorded sales")
    if sells:
        st.dataframe(pd.DataFrame(sells),hide_index=True,width="stretch")
    else:
        st.caption("No executed sales recorded yet.")
    st.download_button(
        "Download full portfolio BUY/SELL backup (JSON)",
        data=json.dumps(portfolio,indent=2,default=str),
        file_name="btc_portfolio_buy_sell_backup.json",
        mime="application/json",key="cycle_editor_full_backup"
    )
