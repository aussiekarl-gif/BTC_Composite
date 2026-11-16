"""Shared portfolio purchase editor and calculated-transactions table.

Production and Research deliberately share this UI implementation. Strategy
signals, risk calculations and model state remain owned by their respective apps.
BTC/USD is a historical display reference only; it is never a trade fill.
"""
from __future__ import annotations
import datetime as dt
import numpy as np
import pandas as pd


def parse_portfolio_date(value):
    """Parse supported portfolio dates into a Python date, or None."""
    if pd.isna(value):
        return None
    text = str(value).strip()
    for fmt in ("%d/%m/%y", "%d/%m/%Y", "%Y-%m-%d"):
        try:
            return dt.datetime.strptime(text, fmt).date()
        except (TypeError, ValueError):
            continue
    parsed = pd.to_datetime(text, dayfirst=True, errors="coerce")
    return parsed.date() if pd.notna(parsed) else None


def add_btc_usd_reference(portfolio_df, fetch_btc_history, today=None):
    """Return a display copy with purchase-date BTC/USD references."""
    today = today or dt.date.today()
    display = portfolio_df.copy()
    display["BTC Price (USD)"] = pd.Series(np.nan, index=display.index, dtype=float)
    if display.empty or "Date" not in display.columns:
        return display

    purchase_dates = display["Date"].map(parse_portfolio_date)
    valid_dates = [d for d in purchase_dates if d is not None and d <= today]
    if not valid_dates:
        return display
    try:
        history = fetch_btc_history(min(valid_dates) - dt.timedelta(days=7), max(valid_dates))
        if history is None or history.empty or "price" not in history.columns:
            return display
        dated = history[["price"]].copy()
        dated.index = pd.to_datetime(dated.index, utc=True).tz_convert(None).normalize()
        daily_usd = (
            pd.to_numeric(dated["price"], errors="coerce")
            .groupby(level=0).last().dropna().sort_index()
        )
        for idx, purchase_date in purchase_dates.items():
            if purchase_date is None or purchase_date > today:
                continue
            prior = daily_usd.loc[:pd.Timestamp(purchase_date)]
            if not prior.empty:
                display.at[idx, "BTC Price (USD)"] = float(prior.iloc[-1])
    except Exception:
        # Optional reference data must never block access to the actual ledger.
        pass
    return display


def render_purchase_editor(st, portfolio_df, portfolio_cols):
    """Render the one shared editable Purchases table."""
    st.subheader("Purchases")
    st.caption(
        "For ASX:IBIT enter the purchase date as DD/MM/YY, units bought and total AUD trade value. "
        "Brokerage defaults to A$3. The app automatically looks up BTC/AUD for the purchase date "
        "and calculates BTC-equivalent exposure. For Direct BTC, enter the actual BTC received."
    )
    if portfolio_df.empty:
        portfolio_df = pd.DataFrame([
            {"Date":"19/06/26","Asset":"ASX:IBIT","AUD Spent":1700.0,"Brokerage / Fee AUD":3.0,"Units / BTC Received":100.0,"BTC AUD Price":0.0},
            {"Date":"26/08/26","Asset":"ASX:IBIT","AUD Spent":2092.0,"Brokerage / Fee AUD":3.0,"Units / BTC Received":100.0,"BTC AUD Price":0.0},
            {"Date":"31/08/26","Asset":"ASX:IBIT","AUD Spent":2061.0,"Brokerage / Fee AUD":3.0,"Units / BTC Received":100.0,"BTC AUD Price":0.0},
            {"Date":"01/09/26","Asset":"ASX:IBIT","AUD Spent":2087.0,"Brokerage / Fee AUD":3.0,"Units / BTC Received":100.0,"BTC AUD Price":0.0},
            {"Date":"02/09/26","Asset":"ASX:IBIT","AUD Spent":2050.0,"Brokerage / Fee AUD":3.0,"Units / BTC Received":100.0,"BTC AUD Price":0.0},
        ])
        st.session_state["portfolio_live_rows"] = portfolio_df.to_dict(orient="records")

    editor_df = portfolio_df.copy()
    if "BTC Price (USD)" not in editor_df.columns:
        editor_df["BTC Price (USD)"] = np.nan
    with st.form("portfolio_edit_form", clear_on_submit=False):
        starting_capital = st.number_input(
            "Starting Deployment Capital (AUD)", min_value=0.0,
            value=float(st.session_state["portfolio_live_starting_capital"]),
            step=10000.0, format="%.2f", key="portfolio_starting_capital_form",
        )
        edited = st.data_editor(
            editor_df, num_rows="dynamic", width="stretch", hide_index=True,
            column_config={
                "Date": st.column_config.TextColumn("Date (DD/MM/YY)", help="Australian date format, e.g. 02/09/26"),
                "Asset": st.column_config.SelectboxColumn("Asset", options=["ASX:IBIT","Direct BTC"], required=True),
                "AUD Spent": st.column_config.NumberColumn("AUD Spent", min_value=0.0, format="A$%.2f"),
                "Brokerage / Fee AUD": st.column_config.NumberColumn("Brokerage / Fee AUD", min_value=0.0, default=3.0, format="A$%.2f"),
                "Units / BTC Received": st.column_config.NumberColumn("Units / BTC Received", min_value=0.0, format="%.8f"),
                "BTC Price (USD)": st.column_config.NumberColumn(
                    "BTC Price (USD)", format="US$%.2f", disabled=True,
                    help="Historical BTC/USD reference on or before the purchase date; not an executed trade price.",
                ),
            },
            column_order=["Date","Asset","AUD Spent","Brokerage / Fee AUD","Units / BTC Received","BTC Price (USD)"],
            key="portfolio_editor_form",
        )
        submitted = st.form_submit_button("Save Portfolio Changes", type="primary", use_container_width=True)
    if submitted:
        st.session_state["portfolio_live_rows"] = edited[portfolio_cols].to_dict(orient="records")
        st.session_state["portfolio_live_starting_capital"] = float(starting_capital)
        st.session_state["portfolio_starting_capital"] = float(starting_capital)
        st.session_state["portfolio_save_pending"] = True
    else:
        edited = pd.DataFrame(st.session_state["portfolio_live_rows"])
        for col in portfolio_cols:
            if col not in edited.columns:
                edited[col] = "" if col in ("Date","Asset") else 0.0
        edited = edited[portfolio_cols]
        starting_capital = float(st.session_state["portfolio_live_starting_capital"])
    return edited, starting_capital, submitted


def render_calculated_transactions(st, clean, portfolio_accuracy):
    """Render the one shared read-only Calculated Transactions table."""
    clean = clean.copy()
    clean["Date"] = clean["_purchase_date"].apply(lambda x: x.strftime("%d/%m/%y") if pd.notna(x) else "")
    clean["Entry Error vs Bottom %"] = portfolio_accuracy["per_transaction_error_pct"]
    columns = [
        "Date","Asset","AUD Spent","Brokerage / Fee AUD","Units / BTC Received",
        "ETF Unit Price AUD","BTC AUD Price","BTC Price (USD)","BTC Eq / ETF Unit",
        "BTC Equivalent","Entry Error vs Bottom %",
    ]
    config = {
        "AUD Spent": st.column_config.NumberColumn(format="dollar"),
        "Brokerage / Fee AUD": st.column_config.NumberColumn(format="dollar"),
        "Units / BTC Received": st.column_config.NumberColumn(format="%.8g"),
        "ETF Unit Price AUD": st.column_config.NumberColumn(format="dollar"),
        "BTC AUD Price": st.column_config.NumberColumn(format="dollar"),
        "BTC Price (USD)": st.column_config.NumberColumn(format="US$%.2f", help="Historical BTC/USD daily reference on or before purchase date; not an ETF execution price."),
        "BTC Eq / ETF Unit": st.column_config.NumberColumn(format="%.4f"),
        "BTC Equivalent": st.column_config.NumberColumn(format="%.4f"),
        "Entry Error vs Bottom %": st.column_config.NumberColumn(
            "Entry Error vs Bottom (%)", format="%.2f%%",
            help="Fee-inclusive purchase price error relative to the editable provisional bottom, in the selected currency.",
        ),
    }
    st.subheader("Calculated Transactions")
    st.dataframe(clean[columns], width="stretch", hide_index=True, column_config=config)
    st.caption(
        "For ASX:IBIT, the app calculates the ETF unit price from AUD spent ÷ units, automatically "
        "looks up BTC/AUD for the purchase date, then estimates BTC-equivalent exposure as AUD trade "
        "value ÷ BTC/AUD. This is an economic exposure estimate, not the exact bitcoin legally held "
        "for each ETF unit."
    )
    return clean
