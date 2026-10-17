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
from engines.research.cycle_funding_provenance import (
    classify_with_stale_guard,UNREVIEWED,INDEPENDENT,CYCLE_SALE,FUNDING_LABELS,
)
from engines.research.cycle_broker_csv_reconciliation import (
    parse_broker_executions_csv,parse_broker_balances_csv,
    compare_broker_transactions,compare_broker_balances,
    TRANSACTION_TEMPLATE,BALANCE_TEMPLATE,
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

    with st.expander(
        "Compare broker CSV statements with My Portfolio (read-only)",
        expanded=False,
    ):
        st.caption(
            "Compare actual executed BUY/SELL records and dated account balances "
            "with the saved Google Sheets ledger. Upload files ONLY when you "
            "want to review them; the CSV is processed in this Streamlit session "
            "and never saved to Google Sheets or a GitHub repository. "
            "There is NO automatic import or broker order."
        )
        st.caption(
            "Different brokers export different columns. Download the simple "
            "standardised CSV examples below, transfer the columns from your "
            "broker's execution and balance statements, and keep the original "
            "broker exports separately for verification. Asset labels: ASX:IBIT "
            "(or IBIT.AX), Direct BTC (or BTC), AUD Cash (balances only). "
            "US-listed IBIT is deliberately NOT mapped to ASX:IBIT."
        )
        a1,a2=st.columns(2)
        a1.download_button(
            "CSV template — broker executions",
            data=TRANSACTION_TEMPLATE,file_name="broker_executions_template.csv",
            mime="text/csv",key="cycle_broker_execution_template")
        a2.download_button(
            "CSV template — dated holdings and cash",
            data=BALANCE_TEMPLATE,file_name="broker_balances_template.csv",
            mime="text/csv",key="cycle_broker_balances_template")
        file_broker_trades=st.file_uploader(
            "Upload normalised broker executions CSV",
            type=["csv"],key="cycle_broker_executions_upload",
            help="Date,Side,Asset,Units,Gross AUD,Fee AUD,Reference")
        file_broker_balance=st.file_uploader(
            "Upload broker balance snapshot CSV",
            type=["csv"],key="cycle_broker_balances_upload",
            help="As Of,Asset,Quantity; one date, distinct assets, optional AUD Cash")
        if file_broker_trades is not None:
            r1,r2=st.columns(2)
            with r1:
                period_start=st.date_input(
                    "Broker statement starts",
                    value=today-dt.timedelta(days=30),
                    max_value=today,key="cycle_broker_statement_start")
            with r2:
                period_end=st.date_input(
                    "Broker statement ends",value=today,max_value=today,
                    key="cycle_broker_statement_end")
            complete=st.checkbox(
                "This CSV contains ALL executions for the selected account "
                "and date range (not just selected trades)",
                value=False,key="cycle_broker_statement_complete")
            try:
                parsed_trades=parse_broker_executions_csv(
                    file_broker_trades.getvalue(),today=today)
                report=compare_broker_transactions(
                    portfolio,parsed_trades,start_date=period_start,
                    end_date=period_end,
                    complete_statement_confirmed=complete)
            except (ValueError,TypeError,KeyError) as exc:
                st.error(
                    "Transaction comparison stopped: "+str(exc)+
                    ". No portfolio changes were made.")
            else:
                k1,k2,k3,k4=st.columns(4)
                k1.metric("Matched executions",report["matched_executions"])
                k2.metric("Broker-only to review",report["broker_only"])
                k3.metric("Portfolio-only to review",report["portfolio_only"])
                k4.metric("Ambiguous rows",report["ambiguous_rows"])
                if report["all_rows_accounted_for"]:
                    st.success(
                        "Every execution in the declared date range matches "
                        "one recorded portfolio trade. This does NOT verify "
                        "tax, external cash balances or statement completeness.")
                else:
                    st.warning(
                        "Differences need manual review. Do not automatically "
                        "add a broker-only row or delete a portfolio-only row. "
                        "Check execution references, dates, fees and prices.")
                if not complete:
                    st.info(
                        "You have NOT confirmed this is a complete account "
                        "statement. A portfolio-only row might simply be "
                        "outside the selected broker export; it is NOT proof "
                        "of a missing broker execution.")
                st.dataframe(
                    pd.DataFrame(report["details"]).head(100),
                    hide_index=True,use_container_width=True)
                st.caption(
                    "First 100 comparison rows shown. Review all flagged "
                    "differences against original broker confirmations. "
                    "Duplicate indistinguishable fills remain ambiguous.")
                st.download_button(
                    "Download transaction reconciliation CSV (read-only)",
                    data=pd.DataFrame(report["details"]).to_csv(index=False),
                    file_name="cycle_broker_statement_differences.csv",
                    mime="text/csv",key="cycle_broker_reconciliation_export")
        if file_broker_balance is not None:
            try:
                statement=parse_broker_balances_csv(
                    file_broker_balance.getvalue(),today=today)
                balances=compare_broker_balances(portfolio,statement)
            except (ValueError,TypeError,KeyError) as exc:
                st.error(
                    "Balance comparison stopped: "+str(exc)+
                    ". No portfolio changes were made.")
            else:
                st.metric("Broker balance differences",
                          balances["discrepancy_count"])
                st.caption(
                    f"Broker snapshot dated {balances['as_of']}; portfolio "
                    "transactions are compared ONLY through that date.")
                st.dataframe(
                    pd.DataFrame(balances["rows"]),
                    hide_index=True,use_container_width=True)
                if balances["missing_assets_not_assumed_zero"]:
                    st.info(
                        "Assets omitted by the broker balance CSV were "
                        "NOT assumed to be zero: "+
                        ", ".join(balances["missing_assets_not_assumed_zero"]))
                st.warning(balances["cash_note"])
                st.caption(
                    "A cash difference can come from withdrawals, deposits, "
                    "tax, interest or settlement; it is not automatically "
                    "a missing transaction. The CSV does not establish "
                    "cash available AFTER SMSF tax or other reserves.")
                st.download_button(
                    "Download balance discrepancy CSV (read-only)",
                    data=pd.DataFrame(balances["rows"]).to_csv(index=False),
                    file_name="cycle_broker_balance_differences.csv",
                    mime="text/csv",key="cycle_broker_balance_export")

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
    with st.expander("Identify funding of recorded BUYs (optional)",expanded=False):
        st.caption(
            "Label an EXISTING executed purchase; this does not create, "
            "cancel or alter a broker trade. Old purchases are Unreviewed "
            "and remain fully deducted from historical buyback cash. "
            "'Independent cash' means YOU have checked that the purchase "
            "was not funded by original cycle BTC sale proceeds. "
            "Classification is not independently verified."
        )
        if buys:
            with st.form("cycle_buy_funding_source_form",clear_on_submit=False):
                selected=st.selectbox(
                    "Existing recorded BUY to classify",
                    options=list(range(len(buys))),
                    format_func=lambda i:(
                        f"#{i+1} {buys[i].get('Date','')} "
                        f"{buys[i].get('Asset','')} "
                        f"{buys[i].get('Units / BTC Received','')} units · "
                        f"A${float(buys[i].get('AUD Spent',0)):,.2f}"
                    ),key="cycle_buy_funding_row")
                current_source=buys[selected].get("Funding Source",UNREVIEWED)
                if current_source not in FUNDING_LABELS:
                    current_source=UNREVIEWED
                source=st.selectbox(
                    "Funding of this recorded purchase",
                    options=list(FUNDING_LABELS),
                    index=list(FUNDING_LABELS).index(current_source),
                    key="cycle_buy_funding_kind")
                cycle_date=None
                if source==CYCLE_SALE:
                    cycle_date=st.date_input(
                        "Halving that generated the original-sale proceeds",
                        value=dt.date(2024,4,20),
                        max_value=today,
                        key="cycle_buy_funding_halving")
                    st.warning(
                        "The original cycle sale must have occurred in the "
                        "recorded day500–730 exit window, and this BUY must "
                        "be after day744. 2026 purchases cannot be funded "
                        "by a fictitious September 2025 sale."
                    )
                assert_funding=st.checkbox(
                    "I have checked the BUY funding source against my "
                    "cash movements, sale records and broker confirmation.",
                    key="cycle_buy_funding_confirm")
                save_funding=st.form_submit_button(
                    "Save BUY funding label",use_container_width=True)
            if save_funding:
                latest,read_error=load_portfolio()
                if read_error:
                    st.error("Could not reread saved ledger: "+str(read_error))
                else:
                    try:
                        updated=classify_with_stale_guard(
                            portfolio,latest,
                            row_index=int(selected),funding_source=source,
                            halving=cycle_date,confirmed=assert_funding)
                        ok,error=save_portfolio(updated)
                        if not ok:
                            st.error("Could not save funding classification: "+str(error))
                        else:
                            st.success(
                                "Funding label saved. Actual trade quantities, "
                                "prices, cash and positions were NOT changed.")
                            st.cache_data.clear()
                            st.rerun()
                    except (ValueError,AssertionError,KeyError) as exc:
                        st.error(str(exc)+" — existing trade unchanged.")
        else:
            st.caption("No recorded purchases to classify.")
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
