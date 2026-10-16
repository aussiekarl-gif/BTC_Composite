"""User-facing read-only cycle trading Research page for the existing app.py."""
from __future__ import annotations

import datetime as dt
import math
import pandas as pd
import streamlit as st

from engines.research.cycle_trading_dashboard_model import (
    build_dashboard_market, historical_one_scenario,
    planned_buy_order,portfolio_snapshot,
)
from engines.research.day500_aftertax_reinvestment import fetch_fx_for_cycle
from engines.research.top_signal_horse_race import HALVINGS,read_exported_history
from engines.research.verified_recent_price_bridge import fetch_public_series
from engines.shared.portfolio_store import load_portfolio


st.title("Cycle Trading — Research")
st.caption("Day-500 Dynamic DCA-out + 200WMA Dynamic DCA-in • Personal portfolio reference • Historical comparisons")
st.warning(
    "Research only — no broker integration, no automatic orders and no changes to Production "
    "or your saved My Portfolio. Backtests use hypothetical BTC positions at historical halvings, "
    "not your real A$500,000 that began deployment in 2026."
)


@st.cache_data(ttl=60*60*12,show_spinner=False)
def historical_source():
    return read_exported_history()


@st.cache_data(ttl=60*60*6,show_spinner=False)
def public_source(asof):
    return fetch_public_series(asof=asof)


@st.cache_data(ttl=60*60*24,show_spinner=False)
def cycle_fx_source(halving,terminal):
    return fetch_fx_for_cycle(pd.Timestamp(halving,tz="UTC"),
                              pd.Timestamp(terminal,tz="UTC"))


@st.cache_data(ttl=60*10,show_spinner=False)
def stored_portfolio():
    return load_portfolio()


def merge_verified_daily(archive,remote):
    """Do not replace archive history or use unsupported remote archives.

    Verify at least three exact-day overlap BTC/USD prices before adding
    any newly fetched, time-stamped public closes.
    """
    local=archive["price_usd"].copy().sort_index()
    remote=remote["btc_usd"].copy().sort_index()
    overlap=local.index.intersection(remote.index)
    relevant=overlap[overlap>=local.index[-1]-pd.Timedelta(days=30)]
    if len(relevant)<3:
        raise ValueError("Cannot verify at least 3 recent BTC/USD provider prices")
    dev=(remote.loc[relevant]/local.loc[relevant]-1).abs()
    if float(dev.median())>.06 or float(dev.max())>.15:
        raise ValueError("BTC/USD public data inconsistent with historical source")
    additions=remote.loc[remote.index>local.index[-1]]
    combined=pd.concat([local,additions]).sort_index()
    return combined,{"overlap_days":len(relevant),
                     "max_overlap_difference_pct":round(100*float(dev.max()),2),
                     "added_dates":len(additions)}


with st.spinner("Loading historical BTC observations..."):
    try:
        research_history=historical_source()
    except Exception as exc:
        st.error(f"Cannot load historical Research data: {type(exc).__name__}: {exc}")
        st.stop()

today=dt.datetime.now(dt.timezone.utc).date()
asof=today.isoformat()
daily=research_history["price_usd"].copy()
fx=pd.DataFrame()
source_label="October 2026 archived Research export (historical only)"
provider_error=None
verification=None
with st.spinner("Checking public BTC and AUD exchange-rate updates..."):
    try:
        public_prices,public_fx=public_source(asof)
        # Today's public quote may be intraday. Restrict historical
        # close decisions to completed UTC calendar days.
        public_prices=public_prices.loc[
            public_prices.index<pd.Timestamp(today,tz="UTC")]
        daily,verification=merge_verified_daily(research_history,public_prices)
        fx=public_fx
        source_label="BlockHorizon archive + cross-checked Blockchain.com public daily closes"
    except Exception as exc:
        provider_error=f"{type(exc).__name__}: {exc}"

try:
    market=build_dashboard_market(daily,fx,asof=asof)
except Exception as exc:
    st.error(f"Cannot calculate strictly prior BTC 200WMA: {type(exc).__name__}: {exc}")
    st.stop()

last_day=pd.Timestamp(market["asof_date"]).date()
staleness=(today-last_day).days
if provider_error:
    st.error("Current public BTC/FX refresh not verified: "+provider_error)
if staleness>3:
    st.error(f"Prices are {staleness} days old ({last_day}). Current trade suggestions are disabled. Historical research remains accessible.")
else:
    st.caption(f"BTC/USD source: {source_label}; last completed daily observation {last_day}. "
               "Signals use the previous daily close, never an uncompleted current trading day.")
if verification:
    st.caption(f"Cross-source verification: {verification['overlap_days']} overlapping daily closes; "
               f"maximum difference {verification['max_overlap_difference_pct']:.2f}%.")
with st.expander("Data safety and model assumptions"):
    st.write(
        "BTC prices are daily research provider observations and are NOT executable ASX:IBIT "
        "quotes. The 200WMA uses 200 weekly spaced BTC/USD closes ending before the latest observed day. "
        "200WMA eligibility is only a signal. Broker fills, spreads, ETF tracking, fund expenses "
        "and real SMSF tax positions are not included in an illustrative next DCA amount. "
        "A new buyback entry assumes proceeds from an earlier exit; your real portfolio may still be accumulating."
    )

c1,c2,c3,c4=st.columns(4)
c1.metric("BTC/USD historical close",f"US${market['btc_price_usd']:,.0f}")
c2.metric("Prior-observation 200WMA",f"US${market['prior_200wma_usd']:,.0f}")
c3.metric("Prior close / 200WMA",f"{market['prior_close_vs_200wma_pct']:+.1f}%")
c4.metric("Days from last confirmed halving",f"{market['halving_day']:,}")

st.caption(
    f"Confirmed halving 20 Apr 2024 • day 500: {market['day500_date']} "
    f"• day 560: {market['day560_date']}. Both are **in the past**. "
    "No rule should retroactively sell your BTC/ETF bought in 2026."
)

with st.spinner("Reading saved Portfolio for optional cash default..."):
    saved_live_portfolio, saved_live_error=stored_portfolio()
saved_cash=portfolio_snapshot(saved_live_portfolio) if not saved_live_error else {"valid":False}
starting_cash_default=(
    float(saved_cash["cash_remaining_aud"])
    if saved_cash.get("valid") and saved_cash.get("rows",0)>0
    else 50000.
)

tabs=st.tabs(["Current signals", "My Portfolio (read-only)", "Historical sell & buyback"])

with tabs[0]:
    st.subheader("Signal readiness")
    current_signal=("Prior close below the 200WMA — buyback gate observed"
                    if market["previous_close_below_200wma"] else
                    "Prior close above the 200WMA — initial buyback gate not observed")
    st.info(current_signal)
    st.caption("This is an entry-gate observation, not an assertion that the bear-market low is in.")

    chosen_style=st.selectbox(
        "Research buyback sizing approach",
        ["adaptive_recovery","adaptive_value"],
        format_func=lambda x:("Recovery confirmation (research preferred)"
                              if x=="adaptive_recovery" else
                              "Value weighting (deep-discount preference)"),
        key="cycle_research_buy_style"
    )
    st.markdown("**Illustrative order calculation**")
    cash_input=st.number_input(
        "Available AUD cash for *this hypothetical cycle-trading account*",
        min_value=0.,value=starting_cash_default,step=1000.,format="%.2f",
        help="Defaults to remaining AUD capital from the saved portfolio, when available. This is NOT a trade proposal or proof you sold BTC in 2025.",
        key="cycle_research_cash_input"
    )
    proposal=planned_buy_order(market,cash_available=cash_input,style=chosen_style)
    if staleness>3 or market["usd_aud_prior"] is None:
        st.error("Cannot produce a current AUD order: verified price and prior FX are required.")
    else:
        d1,d2=st.columns(2)
        d1.metric("Illustrative next buy",f"A${proposal['amount_aud']:,.2f}")
        btcval=proposal.get("btc_equivalent_estimate")
        d2.metric("Illustrative BTC equivalent",
                  f"{btcval:.7f} BTC-eq" if btcval is not None else "Unavailable")
        st.caption(proposal["reason"])
        if proposal["action"]=="ILLUSTRATIVE BUY":
            st.caption(
                f"Includes A$3 brokerage. Estimated AUD/BTC {market['btc_price_aud_estimate']:,.0f}; "
                "ASX:IBIT units and actual fee/spread require a current broker quote."
            )
    st.subheader("Market history")
    hist=market["price_history"]
    st.line_chart(hist.tail(420).rename("BTC/USD daily price"))
    st.caption("Chart is price only; all buy/sell decisions remain manual.")

with tabs[1]:
    st.subheader("Your saved My Portfolio")
    portfolio,store_error=saved_live_portfolio,saved_live_error
    if store_error:
        st.error("Could not load the persistent Portfolio: "+store_error)
        st.caption("No holdings are assumed when storage cannot be read.")
    else:
        snap=portfolio_snapshot(portfolio)
        if not snap["valid"]:
            st.warning(snap["reason"])
        elif snap["rows"]==0:
            st.info("No saved purchases found. Enter them under Research → My Portfolio.")
        else:
            a,b,c,d=st.columns(4)
            a.metric("Original deployment capital",f"A${snap['capital_aud']:,.0f}")
            b.metric("Cash remaining (recorded buys)",f"A${snap['cash_remaining_aud']:,.0f}")
            c.metric("Estimated BTC exposure",f"{snap['btc_equivalent']:.6f} BTC-eq")
            d.metric("ASX:IBIT units",f"{snap['ibit_units']:,.2f}")
            if snap["unpriced_or_unknown_rows"]:
                st.warning(
                    f"{snap['unpriced_or_unknown_rows']} purchase rows lack reliable historical "
                    "BTC/AUD prices or an accepted asset label. BTC exposure is incomplete; "
                    "missing positions are not guessed."
                )
            if snap["approx_average_cost_aud_per_btc"] is not None:
                st.metric("Average recorded cost including fees",
                          f"A${snap['approx_average_cost_aud_per_btc']:,.0f} / BTC-eq")
            st.caption(
                "ASX:IBIT BTC-equivalent is estimated from recorded AUD paid / historic BTC/AUD. "
                "It is NOT direct BTC, the ETF's exact redemption entitlement, or a tax-lot ledger. "
                "If some purchases were sold, update My Portfolio; this read-only view does not reconstruct sales."
            )
            rows=portfolio.get("rows",[])
            cols=["Date","Asset","AUD Spent","Brokerage / Fee AUD",
                  "Units / BTC Received","BTC AUD Price"]
            st.dataframe(pd.DataFrame(rows).reindex(columns=cols),
                         hide_index=True,use_container_width=True)
    st.caption("The Research dashboard never calls save_portfolio(). Change transactions only in the existing My Portfolio page.")

with tabs[2]:
    st.subheader("Historical whole-cycle comparison")
    st.info(
        "Historical research accounts each hypothetically invest A$500,000 at the selected *historical halving*, "
        "not your real 2026 starting portfolio. 2013 is excluded from primary selection. "
        "2025/26 remains incomplete."
    )
    l,r=st.columns(2)
    with l:
        cycle=st.selectbox("Historical cycle",["2021","2017","2025"],key="cycle_research_history_year")
        seller=st.selectbox(
            "DCA-out method",
            ["dynamic_90pct_holdback20pct","dynamic_90pct","fixed_525_to_560"],
            format_func=lambda x:{
                "dynamic_90pct_holdback20pct":"Day-500 Dynamic DCA-out + 20% trailing holdback",
                "dynamic_90pct":"Day-500 Dynamic DCA-out",
                "fixed_525_to_560":"Control: six fixed weekly sales from day 525",
            }[x],
            key="cycle_research_seller"
        )
    with r:
        buyer=st.selectbox(
            "DCA-in method",
            ["adaptive_recovery","adaptive_value"],
            format_func=lambda x:("200WMA + recovery Dynamic DCA"
                                  if x=="adaptive_recovery" else
                                  "200WMA + deep-value Dynamic DCA"),
            key="cycle_research_buyer"
        )
    if st.button("Run historical comparison",type="primary",
                 key="cycle_research_historical_run"):
        halving=str(dict(zip(("2013","2017","2021","2025"),HALVINGS))[cycle].date())
        cutoff=pd.Timestamp(halving,tz="UTC")+pd.Timedelta(days=1150)
        stop=min(cutoff,research_history.index[-1])
        with st.spinner("Running historical tax/FIFO replay with historical AUD FX..."):
            try:
                fx_hist=cycle_fx_source(halving,str(stop.date()))
                res=historical_one_scenario(
                    research_history["price_usd"],fx_hist,
                    cycle=cycle,seller=seller,style=buyer)
                st.session_state["cycle_research_historical_result"]=res
            except Exception as exc:
                st.error(f"Historical comparison failed: {type(exc).__name__}: {exc}")
    result=st.session_state.get("cycle_research_historical_result")
    if result and (result.get("cycle"),result.get("seller"),result.get("buyback_style"))!=(cycle,seller,buyer):
        st.info("Selection changed. Press Run historical comparison for updated results.")
        result=None
    if result:
        st.warning("Incomplete cycle — observation is right-censored." if not result["complete_cycle"]
                   else "Completed historical observation window; still an in-sample simulation.")
        x,y,z=st.columns(3)
        x.metric("BTC accumulated after rebuy",f"{result['btc_held_after_buyback']:,.4f}")
        y.metric("BTC-eq vs hold (includes cash)",
                 f"{result['btc_equivalent_relative_to_hold_pct']:+.1f}%")
        z.metric("Buyback error from ex-post low",
                 f"{result['buyback_error_above_post_sale_low_pct']:+.1f}%"
                 if result["buyback_error_above_post_sale_low_pct"] is not None else "No buyback")
        t1,t2,t3=st.columns(3)
        t1.metric("Illustrative SMSF CGT already escrowed",
                  f"A${result['realised_smsf_cgt_paid_est_aud']:,.0f}")
        t2.metric("Brokerage",f"A${result['brokerage_aud']:,.2f}")
        t3.metric("Cash not yet reinvested",f"A${result['cash_remaining_aud']:,.0f}")
        st.caption(
            f"Compared at {result['end_date']} with same historical-start hold. "
            f"Net theoretical liquidation A${result['hypothetical_liquidated_after_cgt_aud']:,.0f} "
            f"versus matched hold A${result['hold_hypothetical_liquidated_after_cgt_aud']:,.0f}. "
            "Tax is simplified and real ETF/FX spreads are excluded."
        )
        download={k:v for k,v in result.items() if k!="historical_only"}
        st.download_button(
            "Download this comparison (JSON)",
            data=pd.Series(download).to_json(indent=2),
            file_name=f"btc_cycle_{cycle}_{seller}_{buyer}_research.json",
            mime="application/json",
            key="cycle_research_historical_download"
        )
