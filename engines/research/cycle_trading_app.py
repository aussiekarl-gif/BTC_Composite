"""User-facing read-only cycle trading Research page for the existing app.py."""
from __future__ import annotations

import datetime as dt
from zoneinfo import ZoneInfo
import math
import pandas as pd
import streamlit as st

from engines.research.cycle_trading_dashboard_model import (
    build_dashboard_market, historical_one_scenario,
    planned_buy_order,portfolio_snapshot,portfolio_buy_error_from_reported_low,
)
from engines.research.day500_aftertax_reinvestment import fetch_fx_for_cycle
from engines.research.top_signal_horse_race import HALVINGS,read_exported_history
from engines.research.verified_recent_price_bridge import fetch_public_series
from engines.shared.portfolio_store import load_portfolio
from engines.research.cycle_portfolio_editor import show_portfolio_editor
from engines.research.cycle_trade_decision import make_current_decision
from engines.research.ibit_quote import fetch_ibit_quote
from engines.research.cycle_aud_price_levels import observed_aud_cycle_levels


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


@st.cache_data(ttl=60*15,show_spinner=False)
def cached_ibit_quote():
    return fetch_ibit_quote()


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
        fallback,fallback_error=stored_portfolio()
        show_portfolio_editor(fallback if not fallback_error else None,
            today=dt.datetime.now(ZoneInfo('Australia/Brisbane')).date(),
            store_error=fallback_error)
        st.stop()

today=dt.datetime.now(dt.timezone.utc).date()
trade_today=dt.datetime.now(ZoneInfo('Australia/Brisbane')).date()
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
    fallback,fallback_error=stored_portfolio()
    show_portfolio_editor(fallback if not fallback_error else None,
        today=dt.datetime.now(dt.timezone.utc).date(),
        store_error=fallback_error)
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

st.subheader("Current cycle top and bottom (A$ BTC)")
st.caption("Observed Bitcoin prices in Australian dollars; percentages compare the latest available close with each level.")
try:
    # Historic 2025 peak MUST be converted with FX from 2025,
    # not today's AUD/USD. The standard public fetch only
    # includes FX from December 2025 onwards.
    cycle_historic_fx=cycle_fx_source("2024-04-20",market["asof_date"])
    cycle_aud=observed_aud_cycle_levels(
        market["price_history"],cycle_historic_fx,
        asof=market["asof_date"])
except Exception as exc:
    cycle_aud=None
    st.warning("Historical cycle BTC/AUD extremes unavailable: "
               f"{type(exc).__name__}: {exc}. "
               "No unverified AUD prices are substituted.")
if cycle_aud is not None:
    high_col,low_col,range_col=st.columns(3)
    high_col.metric(
        "Cycle TOP (BTC/AUD)",
        f"A${cycle_aud['cycle_top_aud']:,.0f}",
        delta=f"{cycle_aud['pct_change_from_top']:+.1f}% from top",
        help=f"Observed high daily BTC/AUD close on {cycle_aud['cycle_top_date']}")
    low_col.metric(
        "Post-top BOTTOM (BTC/AUD)",
        f"A${cycle_aud['cycle_bottom_aud']:,.0f}",
        delta=f"{cycle_aud['pct_change_from_bottom']:+.1f}% from bottom",
        help=f"Observed lowest daily BTC/AUD close after top on {cycle_aud['cycle_bottom_date']}")
    range_col.metric(
        "Position between bottom and top",
        f"{cycle_aud['position_between_low_high_pct']:.1f}%",
        help="0% = observed post-top bottom; 100% = observed cycle top.")
    st.caption(
        f"Bottom A${cycle_aud['cycle_bottom_aud']:,.0f} "
        f"({cycle_aud['cycle_bottom_date']}) → "
        f"Top A${cycle_aud['cycle_top_aud']:,.0f} "
        f"({cycle_aud['cycle_top_date']}). "
        f"Latest BTC/AUD daily close A${cycle_aud['last_price_aud']:,.0f} "
        f"({cycle_aud['asof_date']}). "
        "Range is since the 20 Apr 2024 halving, with the bottom "
        "defined AFTER the observed top. Same-date historical FX; "
        "daily closes, not intraday extremes or a prediction."
    )

st.caption(
    f"Confirmed halving 20 Apr 2024 • day 500: {market['day500_date']} "
    f"• day 560: {market['day560_date']}. Both are **in the past**. "
    "No rule should retroactively sell your BTC/ETF bought in 2026."
)

if st.button("Refresh market feed and My Portfolio",key="cycle_research_refresh"):
    public_source.clear()
    cycle_fx_source.clear()
    stored_portfolio.clear()
    cached_ibit_quote.clear()
    st.rerun()

with st.spinner("Reading saved Portfolio for optional cash default..."):
    saved_live_portfolio, saved_live_error=stored_portfolio()
saved_cash=portfolio_snapshot(saved_live_portfolio) if not saved_live_error else {"valid":False}
starting_cash_default=(
    float(saved_cash["cash_remaining_aud"])
    if saved_cash.get("valid") and saved_cash.get("rows",0)>0
    else 50000.
)

try:
    automatic_ibit=cached_ibit_quote()
    automatic_ibit_error=None
except Exception as exc:
    automatic_ibit=None
    automatic_ibit_error=f"{type(exc).__name__}: {exc}"

tabs=st.tabs(["Current signals", "My Portfolio — Buy & Sell", "Historical sell & buyback"])

with tabs[0]:
    st.subheader("Current trading decision — Research")
    st.caption(
        "Uses verified previous BTC close, strictly prior 200WMA and your saved purchases. "
        "Action is a rules-based research illustration, not a live broker order. "
        "Reconcile recorded holdings with your broker before any transaction."
    )
    left,right=st.columns(2)
    with left:
        chosen_style=st.selectbox(
            "Dynamic DCA-in sizing",
            ["adaptive_recovery","adaptive_value"],
            format_func=lambda x:("Recovery confirmation" if x=="adaptive_recovery"
                                  else "Value weighted below 200WMA"),
            key="cycle_decision_buy_style",
        )
        cash_input=st.number_input(
            "AUD cash available for research buying",
            min_value=0.0,value=float(starting_cash_default),
            step=1000.0,format="%.2f",key="cycle_decision_cash",
            help="Prefilled from saved 2026 portfolio, never from hypothetical historic cycle accounts. "
                 "Do not enter more than cash actually available in My Portfolio."
        )
        if automatic_ibit is not None:
            st.metric("ASX:IBIT automatic indicative quote",
                      f"A${automatic_ibit['price_aud']:,.2f}")
            st.caption(
                f"{automatic_ibit['provider']} • observed "
                f"{automatic_ibit['timestamp_utc']} UTC • "
                f"{automatic_ibit['age_hours']:.1f} hours old • delayed/not executable"
            )
        else:
            st.warning("ASX:IBIT quote unavailable: "+str(automatic_ibit_error))
        manual_quote=st.checkbox(
            "Override automatically sourced quote with broker price",
            value=False,key="cycle_ibit_manual_override")
        quote_default=(automatic_ibit["price_aud"] if automatic_ibit else 0.)
        ibit_quote=st.number_input(
            "ASX:IBIT unit price for illustrative sizing, A$",
            min_value=0.0,value=float(quote_default),step=0.10,format="%.2f",
            disabled=not manual_quote,key="cycle_decision_ibit_quote",
            help="Normally the recent ASX:IBIT indicative quote is used automatically. "
                 "Tick override and enter a live broker quote when needed."
        )
        ibit_quote=(ibit_quote if manual_quote else quote_default)
    with right:
        confirm_units=st.checkbox(
            "I have verified my currently held ASX:IBIT units in my broker",
            value=False,key="cycle_decision_confirm_units"
        )
        recorded_units=float(saved_cash.get("ibit_units",0.) or 0.) if saved_cash.get("valid") else 0.
        st.metric("Recorded net ASX:IBIT units",f"{recorded_units:,.0f}")
        st.caption("Verify that recorded unsold quantity matches the broker before confirming.")
        current_units=(recorded_units if confirm_units else None)
        already_traded=st.checkbox(
            "Already executed a BTC/IBIT transaction for this signal today",
            value=False,key="cycle_decision_already_traded",
            help="Prevents repeated suggestions during this visit. This is NOT persisted as a trade ledger."
        )

    decision=make_current_decision(
        market,saved_live_portfolio if not saved_live_error else None,
        today=today,usable_cash_aud=cash_input,buy_style=chosen_style,
        ibit_price_aud=ibit_quote if ibit_quote>0 else None,
        verified_current_ibit_units=current_units,
        already_traded_today=already_traded,
        feed_verified=(provider_error is None and verification is not None
                       and staleness<=3),
    )
    d1,d2,d3=st.columns(3)
    d1.metric("Research action",decision["action"])
    d2.metric("Illustrative trade amount",
              f"A${decision['action_aud']:,.2f}" if decision["action"]!="HOLD" else "A$0")
    d3.metric("ASX:IBIT whole units",
              f"{decision['estimated_ibit_units']:,}"
              if decision["estimated_ibit_units"] is not None else "Quote needed")
    for reason in decision["why"]:
        st.write("• "+reason)
    if decision.get("sell_signal") and decision["action"]=="HOLD":
        st.warning("Potential SELL watch, but no sell sizing until valid broker holdings and quote are confirmed.")
    if decision["action"]=="BUY" and decision.get("quote_aud") is None:
        st.warning("Research BUY signal only. Automatic quote is missing; tick override and enter the broker's ASX:IBIT unit price.")
    if decision["action"]=="SELL":
        st.warning(
            "Before selling, check FIFO tax lots, 12-month CGT discount eligibility, "
            "actual broker holdings, your SMSF phase and potential CGT. "
            "Check your recorded sales ledger and actual SMSF tax lots before trading."
        )
        if "estimated_net_sale_aud_before_cgt" in decision:
            st.caption(
                f"Gross A${decision['action_aud']:,.2f}; net of A$3 brokerage "
                f"A${decision['estimated_net_sale_aud_before_cgt']:,.2f}, before CGT."
            )
    if decision["action"]=="BUY" and decision["estimated_ibit_units"] is not None:
        st.caption(
            f"At your manual broker quote, {decision['estimated_ibit_units']} whole units "
            f"cost approximately A${decision.get('estimated_gross_ibit_aud',0):,.2f} "
            "including an assumed A$3 fee; reconfirm bid/ask and available cash."
        )
    with st.expander("How to use the action safely"):
        st.write(
            "BUY: check your broker's ASX:IBIT live quote, manually place a suitable "
            "limit order and record only executed purchases in Cycle Trading → My Portfolio. "
            "SELL: confirm unsold units in your broker and assess actual SMSF capital gains "
            "before placing any manual order. Now record completed SELL transactions within Cycle Trading → My Portfolio. "
            "HOLD means these experimental price/cycle rules did not support a trade "
            "or data/portfolio safeguards prevented reliable sizing. "
            "Model confidence has NOT been calibrated from prospective market-top tests."
        )
    st.caption(
        "Late-cycle SELL rollover is an experimental price-only safeguard, not the "
        "validated day-500 sell-backtest. The previous 2024 halving's day-500 window "
        "passed in 2025 before your actual purchases. No order is ever submitted."
    )
    st.divider()
    st.subheader("Underlying market signals")
    current_signal=("Prior close below the 200WMA — buyback gate observed"
                    if market["previous_close_below_200wma"] else
                    "Prior close above the 200WMA — initial buyback gate not observed")
    st.info(current_signal)
    st.caption("This is an entry-gate observation, not an assertion that the bear-market low is in.")

    st.subheader("Market history")
    hist=market["price_history"]
    st.line_chart(hist.tail(420).rename("BTC/USD daily price"))
    st.caption("Chart is price only; all buy/sell decisions remain manual.")

with tabs[1]:
    st.subheader("Your saved My Portfolio — net holdings")
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
            b.metric("Available cash incl. sales",f"A${snap['cash_remaining_aud']:,.0f}")
            c.metric("Estimated BTC exposure",f"{snap['btc_equivalent']:.6f} BTC-eq" if snap["btc_equivalent"] is not None else "Unknown")
            d.metric("ASX:IBIT net units",f"{snap['ibit_units']:,.0f}")
            st.metric("Direct BTC net held",f"{snap['direct_btc']:.8f} BTC")
            st.caption(f"{snap['rows']} recorded BUYs, {snap['sales']} recorded SELLs.")
            if snap["unpriced_or_unknown_rows"]:
                st.warning(
                    f"{snap['unpriced_or_unknown_rows']} purchase rows lack reliable historical "
                    "BTC/AUD prices or an accepted asset label. BTC exposure is incomplete; "
                    "missing positions are not guessed."
                )
            if snap["approx_average_cost_aud_per_btc"] is not None:
                st.metric("Average recorded cost including fees",
                          f"A${snap['approx_average_cost_aud_per_btc']:,.0f} / BTC-eq")
            buy_error=portfolio_buy_error_from_reported_low(
                portfolio,fx)
            if buy_error["available"]:
                k1,k2=st.columns(2)
                k1.metric(
                    "Average cost error vs reported 2026 low",
                    f"{buy_error['error_above_user_reported_low_pct']:+.2f}%")
                k2.metric(
                    "AUD/FX-adjusted USD entry price",
                    f"US${buy_error['effective_avg_usd_per_btc']:,.0f} / BTC-eq")
                st.caption(
                    f"Benchmark: user-reported BTC bottom US$"
                    f"{buy_error['reference_low_usd']:,.0f} on 30 Jun 2026 "
                    "(intraday, not independently certified). "
                    "Purchase-weighted costs include recorded A$ fees and "
                    "the preceding known AUD/USD rate. BTC-equivalent ETF "
                    "exposure may differ from actual holdings."
                )
            else:
                st.caption(
                    "Purchase price error unavailable: "+buy_error["reason"]+
                    ". No incomplete transaction average is displayed."
                )
            st.caption(
                "ASX:IBIT BTC-equivalent is estimated from recorded AUD paid / historic BTC/AUD. "
                "It is NOT direct BTC, the ETF's exact redemption entitlement, or a tax-lot ledger. "
                "Recorded sales now reduce net holdings. Actual broker custody must be reconciled separately."
            )
            rows=portfolio.get("rows",[])
            cols=["Date","Asset","AUD Spent","Brokerage / Fee AUD",
                  "Units / BTC Received","BTC AUD Price"]
            st.dataframe(pd.DataFrame(rows).reindex(columns=cols),
                         hide_index=True,use_container_width=True)
    st.divider()
    show_portfolio_editor(
        portfolio if not store_error else None,
        today=trade_today,
        ibit_quote=(automatic_ibit["price_aud"] if automatic_ibit else None),
        btc_aud_quote=market.get("btc_price_aud_estimate"),
        store_error=store_error
    )

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
