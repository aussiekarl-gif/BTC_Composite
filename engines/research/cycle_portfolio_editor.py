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
from engines.research.cycle_trade_execution_safety import (
    historical_btc_aud_reference,
)


def show_portfolio_editor(portfolio,*,today,ibit_quote=None,btc_aud_quote=None,
                          price_history=None,historical_fx=None,store_error=None):
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

    # Outside the form so a past-date selection refreshes the historical
    # BTC/AUD reference immediately, without copying today's FX backwards.
    a,b,c=st.columns(3)
    with a:
        side=st.selectbox("Executed",["BUY","SELL"],key="cycle_editor_side")
    with b:
        asset=st.selectbox("Asset",["ASX:IBIT","Direct BTC"],key="cycle_editor_asset")
    with c:
        day=st.date_input("Trade date",value=today,max_value=today,
                          key="cycle_editor_day")
    historical_ref=historical_btc_aud_reference(
        price_history,historical_fx,trade_date=day)
    reference_default=(
        historical_ref["btc_aud_reference"] if historical_ref else 0.
    )
    if historical_ref:
        st.caption(
            f"BTC/AUD reference A${reference_default:,.0f} "
            f"(BTC close {historical_ref['price_date']}, "
            f"historical AUD FX {historical_ref['fx_date']}). "
            "Indicative only; not an IBIT fill."
        )
    else:
        st.warning("Historical BTC/AUD reference unavailable for this trade date. "
                   "Enter the observed BTC/AUD manually for any ASX:IBIT BUY.")
    quote_default=(
        float(ibit_quote or 0.) if asset=="ASX:IBIT" and day==today else
        reference_default if asset=="Direct BTC" else 0.
    )
    # Reset suggested values on trading-context change, but not
    # while typing a price/fee for the SAME execution.
    marker=(side,asset,str(day))
    if st.session_state.get("cycle_editor_context")!=marker:
        st.session_state["cycle_editor_context"]=marker
        st.session_state["cycle_editor_fill_price"]=float(quote_default)
        st.session_state["cycle_editor_btc_aud"]=float(reference_default)
        st.session_state["cycle_editor_confirm"]=False

    with st.form("cycle_portfolio_executed_trade_form",clear_on_submit=False):
        left,right=st.columns(2)
        with left:
            qty=st.number_input(
                "Executed quantity — whole ETF units or BTC",
                min_value=0.0,value=0.0,
                step=(1.0 if asset=="ASX:IBIT" else .00000001),
                format="%.8f",key="cycle_editor_qty"
            )
            price=st.number_input(
                "Actual AUD fill price per unit / BTC",
                min_value=0.0,value=float(quote_default),
                step=0.01,format="%.4f",key="cycle_editor_fill_price",
                help="Broker's actual executed price. Today only: an indicative quote is prefilled."
            )
        with right:
            fee=st.number_input("Actual transaction fees (AUD)",
                min_value=0.,value=3.,step=1.,format="%.2f",
                key="cycle_editor_fee")
            btc_aud=st.number_input(
                "BTC/AUD at purchase date (IBIT BUY only)",
                min_value=0.,value=float(reference_default),
                step=100.,format="%.2f",key="cycle_editor_btc_aud",
                help="Automatically dated BTC and FX close when available; "
                     "verify historical price, rather than using today's price."
            )
            notes=st.text_input("Broker execution reference / notes",
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
