"""Cycle Trading Research: read-only trade guidance + manually executed portfolio ledger."""
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
from engines.research.cycle_live_completed_utc_prices import (
    fetch_cycle_live_sources,merge_verified_live_cycle_prices,
)
from engines.shared.portfolio_store import load_portfolio,save_portfolio
from engines.research.cycle_portfolio_editor import show_portfolio_editor
from engines.research.cycle_trade_decision import make_current_decision
from engines.research.cycle_trade_allocation import DEFAULT_BUY_STYLE
from engines.research.cycle_broker_cash_review import (
    fifo_sales_and_inventory, broker_reconciled_trade_preview,
)
from engines.research.cycle_single_screen_brief import one_screen_cycle_brief
from engines.research.shared_cycle_policy import cycle_exit_stage_status
from engines.research.cycle_position_anchor import original_cycle_inventory
from engines.research.cycle_wallet_readonly_status import historical_cycle_wallet_status
from engines.research.cycle_real_sale_budget import (
    original_sale_cash_reconciliation, original_buyback_preview,
)
from engines.research.cycle_weekly_buyback_audit import weekly_original_buyback_ledger
from engines.research.cycle_forward_quick_view import cycle_forward_quick_view
from engines.research.cycle_forward_cash_dca import (
    CONFIG_KEY, enrol_with_stale_guard, forward_cash_dca_status,
)
from engines.research.ibit_quote import fetch_ibit_quote,format_ibit_units_for_display
from engines.research.cycle_halving_countdown import (
    fetch_halving_countdown, build_halving_timeline, build_halving_progress_bar,
    normalise_halving_epoch_metadata,
)
from engines.research.cycle_aud_price_levels import observed_aud_cycle_levels
from engines.research.cycle_model_redflags import (
    evaluate_major_red_flags, fetch_reference_model_risks,
)


st.title("Cycle Trading — Research")
st.caption("Day-500 Dynamic DCA-out + 200WMA Dynamic DCA-in • Personal portfolio reference • Historical comparisons")
st.warning(
    "Research only — no automatic broker orders or Production strategy changes. "
    "You can record actual executed buys/sells in My Portfolio below. "
    "Historical backtest accounts are hypothetical, not your 2026 holdings."
)


# Rerun the complete Streamlit view every 15 minutes while it is open.
# This refreshes dated calculations and caches; it never places broker orders.
if hasattr(st, "fragment"):
    @st.fragment(run_every="1m")
    def cycle_refresh_heartbeat():
        now_utc=dt.datetime.now(dt.timezone.utc)
        key="cycle_last_full_refresh_utc"
        previous=st.session_state.get(key)
        if previous is None:
            st.session_state[key]=now_utc
        elif (now_utc-previous).total_seconds()>=15*60:
            st.session_state[key]=now_utc
            st.rerun()
    cycle_refresh_heartbeat()
else:
    st.caption("Automatic refresh requires an updated Streamlit version; use Refresh manually.")


@st.cache_data(ttl=60*60*12,show_spinner=False)
def historical_source():
    return read_exported_history()


@st.cache_data(ttl=60*60,show_spinner=False)
def public_source(asof):
    return fetch_cycle_live_sources(asof=asof)


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


@st.cache_data(ttl=3*60*60,show_spinner=False)
def cached_cross_model_risks():
    # Expensive live 5.82/5.9 baselines only checked for nonzero DCA %.
    # Never recompute at every 15-minute Streamlit rerun.
    return fetch_reference_model_risks()


@st.cache_data(ttl=60*60,show_spinner=False)
def cached_halving_countdown_v2():
    # Renaming this cached function invalidates pre-upgrade Streamlit values.
    return fetch_halving_countdown()


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
        public_prices,public_fx,completed_kraken=public_source(asof)
        daily,verification=merge_verified_live_cycle_prices(
            research_history,public_prices,completed_kraken,utc_today=today)
        fx=public_fx
        source_label="BlockHorizon archive + UTC-date-corrected Blockchain.com + verified completed Kraken" 
    except Exception as exc:
        provider_error=f"{type(exc).__name__}: {exc}"

# Use verified Bitcoin epoch dates; never silently assume 2024 after 2028.
halving_countdown=normalise_halving_epoch_metadata(cached_halving_countdown_v2())
verified_halving_date=(halving_countdown.get("last_halving_date")
                       if halving_countdown.get("halving_date_verified") else None)
anchor_matches_close=bool(verified_halving_date and
    dt.date.fromisoformat(verified_halving_date)<=pd.Timestamp(daily.index[-1]).date())
cycle_feed_verified=bool(anchor_matches_close and
    provider_error is None and verification is not None and
    verification.get("strict_close_date_verified"))
try:
    market=build_dashboard_market(
        daily,fx,asof=asof,
        confirmed_halving_date=verified_halving_date if anchor_matches_close else None)
except Exception as exc:
    st.error(f"Cannot calculate strictly prior BTC 200WMA: {type(exc).__name__}: {exc}")
    fallback,fallback_error=stored_portfolio()
    show_portfolio_editor(fallback if not fallback_error else None,
        today=dt.datetime.now(dt.timezone.utc).date(),
        store_error=fallback_error)
    st.stop()

last_day=pd.Timestamp(market["asof_date"]).date()
staleness=(today-last_day).days
if market["usd_aud_prior"] is None or market["fx_source_date"] is None:
    cycle_feed_verified=False
    st.error("Prior-dated AUD/USD FX unavailable or stale. "
             "Cycle trade recommendations disabled until FX is verified.")
if provider_error:
    st.error("Current public BTC/FX close verification FAILED: "+provider_error+
             " — current trade recommendations are disabled.")
if not cycle_feed_verified:
    st.error("Last halving date not verified from the Bitcoin chain, or newer than "
             "the completed BTC price observation. Cycle-timed trade recommendations "
             "are disabled until automatic verification recovers.")
if staleness!=1:
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

if st.button("Refresh market feed and My Portfolio",key="cycle_research_refresh"):
    public_source.clear()
    cycle_fx_source.clear()
    stored_portfolio.clear()
    cached_ibit_quote.clear()
    cached_halving_countdown_v2.clear()
    st.rerun()

with st.spinner("Reading saved Portfolio for optional cash default..."):
    saved_live_portfolio, saved_live_error=stored_portfolio()
saved_cash=portfolio_snapshot(saved_live_portfolio) if not saved_live_error else {"valid":False}
starting_cash_default=(
    float(saved_cash["cash_remaining_aud"])
    if saved_cash.get("valid") and saved_cash.get("rows",0)>0
    else 0.
)

try:
    automatic_ibit=cached_ibit_quote()
    automatic_ibit_error=None
except Exception as exc:
    automatic_ibit=None
    automatic_ibit_error=f"{type(exc).__name__}: {exc}"

cycle_historic_fx=None

# The displayed halving date comes from confirmed blockchain history.
# At any future halving, suppress the chart until the epoch date is verified.
halving_timeline=(build_halving_timeline(
    last_halving_date=verified_halving_date,
    today=trade_today,
    countdown=halving_countdown,
) if verified_halving_date else None)
elapsed_col,chart_col,remaining_col=st.columns([1.25,2.5,1.5],gap="medium")
with elapsed_col:
    st.metric("Days from last BTC halving",
              f"{halving_timeline['elapsed_days']:,} days"
              if halving_timeline else "Unverified")
    st.caption(f"Confirmed: {verified_halving_date}" if verified_halving_date
               else "Waiting for verified block event")
with chart_col:
    if halving_timeline:
        st.caption(f"Halving cycle progress · {halving_timeline['progress_pct']:.1f}% elapsed")
        st.plotly_chart(
            build_halving_progress_bar(halving_timeline),
            use_container_width=True,
            config={"displayModeBar": False},
            key="cycle_halving_timeline_bar",
        )
    else:
        st.warning("Cycle timeline unavailable until blockchain verification.")
with remaining_col:
    st.metric("Approx. days until next BTC halving",
              f"~{halving_countdown['days_remaining']:,} days")
    st.caption(f"Estimated: {halving_countdown['estimated_date_utc']}")
st.caption(
    "Cycle bar: teal = elapsed, dark = projected remaining, orange = TODAY. "
    "Yellow D500, D560 and D730 markers are research review dates, not price forecasts. "
    "Halving date and price feeds automatically refresh while the page is open • "
    + halving_countdown["source"] + " • " + halving_countdown["estimate_basis"] + "."
)

tabs=st.tabs(["Trading decision", "My Portfolio — Buy & Sell", "Historical sell & buyback"])

with tabs[0]:
    st.subheader("Current trading decision — Research")
    st.caption(
        "Uses verified previous BTC close, strictly prior 200WMA and your recorded executed buys/sells. "
        "Action is a rules-based research illustration, not a live broker order. "
        "Reconcile recorded holdings with your broker before any transaction."
    )
    left,right=st.columns(2)
    with left:
        # The CURRENT decision must be identical to the single daily ntfy
        # market WATCH, which always uses DEFAULT_BUY_STYLE (2.5% cash BUY).
        # Alternative `adaptive_value` (3.5% / 10%) remains selectable ONLY
        # in the separate historical research comparison below.
        chosen_style=DEFAULT_BUY_STYLE
        st.caption(
            "Current Cycle Trading BUY sizing: 2.5% of remaining AUD cash "
            "when the prior-close 200WMA gate is eligible. This is the SAME "
            "market allocation as the one daily ntfy. Historical alternative "
            "sizing is available under Historical sell & buyback, not as "
            "today's Cycle Trading recommendation."
        )
        st.metric("Recorded AUD cash (including sale proceeds)",
                  f"A${starting_cash_default:,.2f}")
        auto_cash=st.checkbox(
            "Use recorded available cash automatically",
            value=True,key="cycle_decision_auto_cash",
            help="DCA % uses remaining AUD cash in the saved buy/sell ledger. "
                 "This balance is before any SMSF tax reserve; reconcile with broker.")
        if auto_cash:
            cash_input=starting_cash_default
        else:
            cash_input=st.number_input(
                "Available broker cash (no more than recorded balance)",
                min_value=0.0,max_value=float(starting_cash_default),
                value=0.0,step=1000.0,format="%.2f",
                key="cycle_decision_cash",
                help="Manual reduction if some cash is reserved for SMSF tax or other purposes."
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
            st.warning(
                "Automatic ASX:IBIT price feed is currently unavailable. "
                "Press Refresh to retry; if it still fails, use a current broker quote. "
                + str(automatic_ibit_error or "No dated Australian ETF quote returned.")
            )
        manual_quote=st.checkbox(
            "Use my broker's ASX:IBIT price instead (optional)",
            value=False,key="cycle_ibit_manual_override",
            help="The AUD quote is automatic when available. Only enter a manual quote if you wish to override it.")
        quote_default=(automatic_ibit["price_aud"] if automatic_ibit else 0.)
        if manual_quote:
            ibit_quote=st.number_input(
                "Broker's ASX:IBIT price in AUD per ETF unit",
                min_value=0.0,value=float(quote_default),step=0.10,format="%.2f",
                key="cycle_decision_ibit_quote",
                help="Manually verify this AUD per-unit price in your broker before trading.")
        else:
            ibit_quote=quote_default
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
        today=trade_today,usable_cash_aud=cash_input,buy_style=chosen_style,
        ibit_price_aud=ibit_quote if ibit_quote>0 else None,
        verified_current_ibit_units=current_units,
        already_traded_today=already_traded,
        feed_verified=(provider_error is None and verification is not None
                       and staleness==1 and cycle_feed_verified),
    )
    # The broker check is optional. Its confirmation is intentionally
    # ephemeral: changing the model or refreshing the page cannot retain
    # a previously verified broker quote/cash amount.
    broker_review_this_run=None
    with st.expander(
        "Broker cash and SMSF tax check — verify before any trade",
        expanded=False,
    ):
        st.caption(
            "Your saved portfolio cash can include sale proceeds BEFORE "
            "SMSF tax, withdrawals or other liabilities. Its automatic "
            "2.5%-of-remaining-cash suggestion is NOT a broker-verified "
            "spendable amount. Check the account balance independently."
        )
        if saved_live_error or not isinstance(saved_live_portfolio,dict):
            st.warning("Recorded trades unavailable. No verified cash or sale projection.")
        else:
            try:
                tax_view=fifo_sales_and_inventory(
                    saved_live_portfolio,asof=trade_today)
            except (ValueError,KeyError,TypeError) as exc:
                st.warning(
                    "Cannot reconcile the FIFO trade ledger: "
                    f"{type(exc).__name__}: {exc}. No trade confirmation."
                )
            else:
                a,b=st.columns(2)
                a.metric("Recorded cash BEFORE unpaid liabilities",
                         f"A${tax_view['recorded_cash_before_tax_aud']:,.2f}")
                b.metric("Illustrative CGT on recorded realised gains",
                         f"A${tax_view['gross_positive_only_tax_projection_aud']:,.2f}")
                st.caption(
                    "CGT is a conservative POSITIVE-parcel-gain-only "
                    "accumulation-phase illustration (10% over 12 months, "
                    "15% otherwise), using entered FIFO cost bases. "
                    "This is NOT an unpaid tax bill: payments, loss offsets, "
                    "SMSF pension phase and annual tax returns are unknown. "
                    "Do NOT subtract this estimate again from broker cash "
                    "you have already confirmed AFTER reserves."
                )
                if tax_view["by_financial_year"]:
                    st.dataframe(
                        pd.DataFrame(tax_view["by_financial_year"]),
                        hide_index=True,use_container_width=True)
                if tax_view["newer_ledger_trades_excluded"]:
                    st.info(
                        "Some saved portfolio transactions are after today's "
                        "dated research reference and are not included in "
                        "this historical cash/tax snapshot."
                    )
                if decision["action"] not in ("BUY","SELL"):
                    st.info(
                        "The existing trading engine currently says HOLD. "
                        "Broker cash checks cannot convert a HOLD into BUY or SELL."
                    )
                else:
                    st.markdown("**Optional independent broker confirmation**")
                    st.caption(
                        "Enter a broker-checked, current ASX:IBIT unit price, "
                        "not the delayed automatic indicative quote."
                    )
                    with st.form("cycle_broker_cash_and_tax_preview"):
                        if decision["action"]=="BUY":
                            broker_free_after=st.number_input(
                                "Broker AUD cash available AFTER unpaid taxes, "
                                "expenses and other reserves",
                                min_value=0.,value=0.,step=1000.,format="%.2f",
                                key="cycle_reconciled_broker_cash")
                        else:
                            broker_free_after=None
                        real_broker_quote=st.number_input(
                            "Manually verified ASX:IBIT broker quote (AUD/unit)",
                            min_value=0.,value=0.,step=0.10,format="%.2f",
                            key="cycle_reconciled_broker_price")
                        acknowledged=st.checkbox(
                            "I verified this broker quote and, if BUYing, "
                            "the spendable cash AFTER liabilities.",
                            value=False,key="cycle_reconciled_cash_confirm")
                        preview_button=st.form_submit_button(
                            "Calculate read-only broker reconciliation")
                    if preview_button:
                        try:
                            review=broker_reconciled_trade_preview(
                                saved_live_portfolio,decision,
                                asof=trade_today,
                                confirmed_broker_cash_after_reserves_aud=(
                                    broker_free_after
                                    if decision["action"]=="BUY" else None),
                                verified_broker_ibit_price_aud=real_broker_quote,
                                confirmed=acknowledged,
                            )
                        except (ValueError,KeyError,TypeError,AssertionError) as exc:
                            st.warning(
                                "Broker-reconciled preview unavailable: "
                                f"{exc}. No order or portfolio change."
                            )
                        else:
                            broker_review_this_run=review
                            if review["phase"]=="BUY_RESEARCH_PREVIEW":
                                st.metric(
                                    "BUY — max verified cash-based research tranche",
                                    f"A${review['reconciled_research_gross_aud']:,.2f}")
                                st.metric(
                                    "BUY — estimated whole ASX:IBIT units",
                                    f"{review['reconciled_whole_ibit_units']:,}")
                                st.caption(
                                    "Existing BUY percentage applied to the "
                                    "LESSER of recorded cash and broker-confirmed "
                                    "free cash after tax/expenses. Whole-unit "
                                    "brokerage, slippage and execution must be "
                                    "rechecked before any manual transaction."
                                )
                            elif review["phase"]=="SELL_RESEARCH_PREVIEW":
                                projection=review["projected_sale"]
                                st.metric(
                                    "SELL — existing model's whole ASX:IBIT units",
                                    f"{review['reconciled_whole_ibit_units']:,}")
                                st.metric(
                                    "Indicative net AUD after illustrative CGT",
                                    f"A${review['reconciled_research_net_sale_aud_after_illustrative_tax']:,.2f}")
                                st.caption(
                                    f"Estimated FIFO gross A${projection['illustrative_sell_gross_aud']:,.2f}; "
                                    f"pre-CGT net A${projection['illustrative_net_before_cgt_aud']:,.2f}; "
                                    f"illustrative accumulation-phase positive-gains "
                                    f"tax A${projection['illustrative_positive_only_cgt_provision_aud']:,.2f}. "
                                    "Check actual SMSF tax lots, phase and broker "
                                    "filled price before manually selling."
                                )
                            elif review["phase"]=="BROKER_CASH_TOO_SMALL":
                                st.warning(
                                    "Verified free cash cannot support the model's "
                                    "minimum whole-unit ASX:IBIT BUY at this quote."
                                )
                            else:
                                st.info("No reconciled order preview; original HOLD applies.")
                            st.caption(
                                "This verification does not change the underlying "
                                "DCA model, place an order, save a transaction, "
                                "or send an ntfy alert."
                            )
    # ONE primary briefing: current recorded account, current model and
    # a broker-verified research value ONLY when checked this very rerun.
    # Do not turn an unverified existing model suggestion into spendable AUD.
    brief=one_screen_cycle_brief(
        saved_live_portfolio if not saved_live_error else None,
        decision,asof=trade_today,
        confirmed_broker_preview=broker_review_this_run,
    )
    st.subheader("Cycle Trading — quick view")
    p1,p2,p3=st.columns(3)
    p1.metric("Current research market signal",brief["market_signal"])
    p1.caption(
        f"Model decision: {brief['action']} (read-only). "
        "This is the simplified current market watch, NOT confirmed "
        "historical original-strategy execution parity."
    )
    if brief["recorded_cash_aud"] is not None:
        p2.metric("Recorded AUD cash BEFORE liabilities",
                  f"A${brief['recorded_cash_aud']:,.2f}")
        p2.caption(
            f"{brief['recorded_ibit_units']:,.0f} IBIT units; "
            f"{brief['recorded_direct_btc']:.8f} direct BTC recorded. "
            "Confirm broker holdings and cash independently."
        )
    else:
        p2.metric("Recorded portfolio","Unavailable")
        p2.caption("Missing or inconsistent executed BUY/SELL ledger.")
    if brief["broker_verification"]:
        if brief["action"]=="BUY":
            p3.metric("Verified BUY research budget",
                      f"A${brief['confirmed_research_gross_aud']:,.2f}")
            p3.caption(
                f"{brief['confirmed_whole_ibit_units']} whole IBIT units, "
                f"approx. A${brief['estimated_whole_unit_cost_aud']:,.2f} "
                "including A$3 assumed fee; quote and cash were manually "
                "confirmed for THIS read-only calculation."
            )
        elif brief["action"]=="SELL":
            p3.metric("Verified SELL research units",
                      f"{brief['confirmed_whole_ibit_units']:,}")
            p3.caption(
                f"Repriced gross A${brief['confirmed_research_gross_aud']:,.2f}; "
                f"illustrative net A${brief['estimated_net_after_cgt_aud']:,.2f} "
                "after unverified SMSF tax assumptions."
            )
    else:
        p3.metric("Spendable trade amount","Not verified")
        p3.caption(
            "Open 'Broker cash and SMSF tax check' above and confirm "
            "actual broker cash AFTER liabilities and/or a current ETF "
            "quote. No broker order is suggested here."
        )
    if brief["signal_pct_cash"] is not None and brief["signal_pct_holdings"] is not None:
        st.caption(
            f"Daily model: BUY {brief['signal_pct_cash']:.2f}% of REMAINING "
            f"cash; SELL {brief['signal_pct_holdings']:.2f}% of REMAINING "
            "BTC/IBIT. These are not the original historical fixed-budget "
            "or original-position fractions."
        )
    if brief["illustrative_realized_gains_cgt_aud"] is not None:
        st.caption(
            f"Previously recorded realised-gain CGT illustration: "
            f"A${brief['illustrative_realized_gains_cgt_aud']:,.2f} "
            "(positive FIFO parcel gains, accumulation-phase example; "
            "NOT the amount of tax currently unpaid)."
        )
    if brief["next_eligible_review"]:
        st.caption(
            f"Next account cooldown-eligible DCA review: "
            f"{brief['next_eligible_review']} — a review, not a predicted BUY."
        )
    if brief["status"]=="PORTFOLIO_UNAVAILABLE":
        st.warning(brief["message"])
    elif brief["status"] in (
            "BROKER_VERIFICATION_REQUIRED","BROKER_PREVIEW_MISMATCH",
            "BROKER_CASH_INSUFFICIENT"):
        st.info(brief["message"])
    else:
        st.caption(brief["message"])
    st.caption(
        "Nothing on this screen places an order, updates Google Sheets, "
        "or changes daily ntfy. Broker-confirmed values are temporary "
        "and do not carry over to another visit."
    )

    # Historical original SELL/day500 and 200WMA reinvestment are
    # deliberately separate from the CURRENT simplified live signal.
    with st.expander(
        "Original historical cycle strategy — next review and eligibility",
        expanded=False,
    ):
        st.caption(
            "This original backtested policy uses % of ORIGINAL BTC for "
            "SELL and % of ORIGINAL after-tax sale proceeds for weekly BUY. "
            "These bases are not the simplified daily percentages above."
        )
        try:
            quick=cycle_forward_quick_view(
                market,
                saved_live_portfolio if not saved_live_error else None,
                decision,
                feed_verified=(provider_error is None and verification is not None
                               and staleness==1 and cycle_feed_verified),
            )
        except (ValueError,KeyError,TypeError,AssertionError) as exc:
            quick=None
            st.warning(
                "Original cycle status cannot be reconciled: "
                f"{type(exc).__name__}: {exc}."
            )
        if quick is not None:
            h1,h2=st.columns(2)
            h1.metric(
                "Original strategy — next research review",
                quick["original_next_review_date"]
                if quick["original_next_review_date"]
                else "Date not yet known",
            )
            h1.caption(quick["original_next_review_label"])
            if quick["original_next_pct_original_holdings"] is not None:
                caption="Current original SELL review (% original position)"
                amount=f"{quick['original_next_pct_original_holdings']:.2f}%"
            elif quick["last_completed_recovery_pct_original_budget"] is not None:
                caption="Last historical BUY review (% original after-tax cash)"
                amount=f"{quick['last_completed_recovery_pct_original_budget']:.2f}%"
            else:
                caption="Original BUY/SELL percentage"
                amount="Not established"
            h2.metric(caption,amount)
            if quick["last_completed_recovery_review_date"]:
                h2.caption(
                    f"Historical review {quick['last_completed_recovery_review_date']}; "
                    "future weekly percentages are not known in advance."
                )
            if quick["future_ledger_transactions_excluded"]:
                st.caption(
                    "Transactions newer than the latest observed BTC close "
                    "were excluded from this dated original-strategy review."
                )
            if quick["recorded_original_sale_cash_before_cgt_aud"] is not None:
                st.caption(
                    f"Original-position sale proceeds before CGT: "
                    f"A${quick['recorded_original_sale_cash_before_cgt_aud']:,.2f}. "
                    "These are not verified spendable proceeds."
                )
            st.info(quick["original_readiness"]+" "+quick["original_blocker"])
            st.caption(
                "2026 purchases cannot receive 2025 backdated sale proceeds. "
                "Original-to-live parity is NOT certified."
            )
    # This is a prospective adaptation of the ORIGINAL weekly 200WMA
    # fractions to independently verified *fresh* AUD cash. Never fake
    # a 2025 SELL. It stays separate from the live simplified decision.
    with st.expander("2026 onward — forward cash-funded 200WMA DCA (Research)",
                     expanded=False):
        st.caption(
            "The original historical cycle buys used after-tax proceeds "
            "from an earlier day500 SELL. New 2026 purchases have no "
            "such backdated sale. This opt-in research path uses the SAME "
            "strict prior-200WMA trigger and weekly adaptive recovery "
            "percentage, but against a FIXED newly-confirmed AUD cash "
            "budget instead. Its prospective performance is NOT backtested "
            "as equivalent to the earlier after-tax historical roundtrip."
        )
        if saved_live_error or not isinstance(saved_live_portfolio,dict):
            st.warning("Cannot read My Portfolio. No fresh cash budget or order.")
        elif not saved_live_portfolio.get(CONFIG_KEY):
            st.write("**Optional: start a new dated accumulation research budget**")
            st.caption(
                "Start today only; no retroactive cycle trades or automatic "
                "use of your full A$500,000. The broker amount must be cash "
                "available AFTER unpaid tax and other commitments. "
                "This stores only research metadata alongside the existing "
                "portfolio; it does not buy BTC or alter old trades."
            )
            with st.form("forward_cash_budget_enrolment"):
                broker_free=st.number_input(
                    "Verified broker AUD cash AFTER tax and reserves",
                    min_value=0.0,value=0.0,step=1000.,format="%.2f",
                    key="forward_cash_broker_start")
                starting_budget=st.number_input(
                    "Amount of that cash allocated to 200WMA research",
                    min_value=0.0,value=0.0,step=1000.,format="%.2f",
                    key="forward_cash_budget_start")
                approved=st.checkbox(
                    "I verified the broker cash and agree to start this "
                    "research budget TODAY (not an actual trade)",
                    value=False,key="forward_cash_confirm_start")
                submitted=st.form_submit_button(
                    "Save prospective research budget",use_container_width=True)
            if submitted:
                fresh,err=load_portfolio()
                if err:
                    st.error("Unable to recheck saved portfolio: "+err)
                else:
                    try:
                        state=enrol_with_stale_guard(
                            saved_live_portfolio,fresh,
                            start_date=dt.datetime.now(
                                ZoneInfo("Australia/Brisbane")).date(),
                            budget_aud=starting_budget,
                            broker_available_after_reserves_aud=broker_free,
                            confirmed=approved,
                        )
                        saved,error=save_portfolio(state)
                    except (ValueError,AssertionError,KeyError,TypeError) as exc:
                        st.error(
                            "Research enrolment rejected; old trades unchanged: "
                            f"{exc}")
                    else:
                        if not saved:
                            st.error("Research budget was not saved: "+str(error))
                        else:
                            st.success(
                                "Prospective budget saved; no broker order "
                                "or historical sale was created.")
                            stored_portfolio.clear()
                            st.rerun()
        else:
            details=saved_live_portfolio[CONFIG_KEY]
            st.caption(
                f"Fixed starting budget: A${float(details['initial_budget_aud']):,.2f} "
                f"from {details['start_date']}. This is confirmed NEW cash "
                "for the research model, NOT earlier cycle-sale proceeds. "
                "Historical portfolio rows are protected by an anchor fingerprint."
            )
            broker_checked=st.checkbox(
                "I have checked broker cash available AFTER all taxes/reserves",
                value=False,key="forward_cash_broker_confirm_now")
            broker_current=st.number_input(
                "Broker-verified available AUD cash for this review",
                min_value=0.0,value=0.,step=1000.,format="%.2f",
                key="forward_cash_broker_current")
            try:
                forward=forward_cash_dca_status(
                    market["price_history"],
                    saved_live_portfolio,
                    asof=market["asof_date"],
                    broker_cash_after_reserves_aud=(
                        broker_current if broker_checked else None),
                    feed_verified=(
                        provider_error is None and verification is not None
                        and staleness==1 and cycle_feed_verified),
                )
            except (ValueError,KeyError,TypeError,AssertionError) as exc:
                st.error(
                    "Prospective research state cannot be reconciled: "
                    f"{exc}. No amount or order is proposed."
                )
            else:
                a1,a2,a3=st.columns(3)
                a1.metric("Original research cash budget",
                          f"A${forward['original_fresh_cash_budget_aud']:,.2f}")
                a2.metric("Available unspent research budget",
                          f"A${forward['remaining_unspent_budget_aud']:,.2f}")
                a3.metric("Research state",
                          forward["phase"].replace("_"," ").title())
                st.caption(forward["message"])
                if forward["trigger_date"]:
                    st.write(
                        f"Observed 200WMA activation: {forward['trigger_date']}; "
                        f"last weekly review: {forward['last_completed_review_date']}; "
                        f"next research review: {forward['next_review_date']}."
                    )
                if forward["last_review_pct_original_budget"] is not None:
                    st.caption(
                        f"Last observed weekly allocation: "
                        f"{forward['last_review_pct_original_budget']:.2f}% "
                        "of ORIGINAL confirmed cash budget. It is not a "
                        "percentage of remaining cash."
                    )
                if forward["research_review_aud"] is not None:
                    st.metric(
                        "Today's cash-funded research BUY preview (AUD)",
                        f"A${forward['research_review_aud']:,.2f}")
                    st.warning(
                        "Informational only. Check exact ASX:IBIT broker quote, "
                        "minimum whole-unit order, SMSF tax and recorded "
                        "transactions; no broker order is placed."
                    )
                st.caption(
                    "Recorded post-enrolment purchases consume the fixed "
                    f"budget: A${forward['spent_since_enrolment_aud']:,.2f} "
                    "debited; independent-cash purchases still reduce "
                    "actual available broker cash. New funding is never "
                    "silently added. Existing daily ntfy remains a DIFFERENT "
                    "simplified rule."
                )
    st.divider()

    # Percentage is the primary allocation signal; show BOTH cash-buy
    # and holdings-sell bases so the user never mistakes dollars for BTC.
    buy_percent=decision["buy_pct_total_cash"]
    sell_percent=decision["sell_pct_total_holdings"]
    signal_valid=decision["market_signal"]!="UNAVAILABLE"
    st.subheader("Dynamic DCA allocation — % of what you hold")
    pct1,pct2,pct3=st.columns(3)
    pct1.metric("BUY — % of available AUD cash",
                f"{buy_percent:.2f}%" if signal_valid else "Unavailable",
                help="Percentage of UNINVESTED cash remaining in saved My Portfolio, not A$500k original capital.")
    pct2.metric("SELL — % of current BTC/IBIT holdings",
                f"{sell_percent:.2f}%" if signal_valid else "Unavailable",
                help="Percentage of currently held IBIT ETF units and direct BTC, separately; whole ETF units are rounded down.")
    pct3.metric("Cycle market signal",
                decision["market_signal"],
                help="Market-only watch can exist without verified broker units or available cash; not permission to trade.")
    d1,d2,d3=st.columns(3)
    d1.metric("Research action",decision["action"])
    d2.metric("Illustrative transaction",
              f"A${decision['action_aud']:,.2f}" if decision["action"]!="HOLD" else "A$0")
    d3.metric("ASX:IBIT whole units",
              format_ibit_units_for_display(
                  decision,quote_available=ibit_quote>0))

    # QUIET reference check: compare actual 5.82/5.9 risk scores, NOT
    # their budget multipliers to Cycle's % of cash or remaining holdings.
    # Only an exceptional contradiction is surfaced. A failed reference
    # lookup is unknown, NEVER falsely reported as 'all clear'.
    if (signal_valid and (buy_percent>0 or sell_percent>0)
            and provider_error is None and verification is not None
            and staleness==1 and cycle_feed_verified):
        reference_risks=cached_cross_model_risks()
        major_flags=evaluate_major_red_flags(
            buy_pct_cash=buy_percent,sell_pct_held=sell_percent,
            snapshots=reference_risks,market_asof=market["asof_date"],
            today=trade_today,confirmed_halving_date=market["halving_date"],
        )
        for major in major_flags["warnings"]:
            st.error(major)
    if decision["action"]=="BUY":
        st.caption(
            f"{buy_percent:.2f}% × your selected available A$ cash "
            f"= A${decision['action_aud']:,.2f} planned gross buy. "
            "Whole ETF unit rounding may leave part of that amount unused."
        )
    if decision["action"]=="SELL":
        st.caption(
            f"{sell_percent:.2f}% × recorded/confirmed net ASX:IBIT holdings "
            f"= {decision['suggested_ibit_units']:,} whole ETF units (rounding down). "
            f"Actual units sold equal {decision['effective_ibit_pct_held_after_rounding']:.2f}% "
            "of confirmed IBIT units."
        )
        if decision.get("recorded_direct_btc_net",0)>0:
            st.caption(
                f"Separately, {sell_percent:.2f}% of your recorded direct BTC holding "
                f"would be approximately {decision['direct_btc_sale_quantity_estimate']:.8f} BTC. "
                "This informational amount is NOT included in IBIT sale proceeds."
            )
    if decision["market_signal"]=="SELL WATCH" and decision["action"]!="SELL":
        st.caption(
            f"Market-only SELL WATCH is {sell_percent:.2f}% of remaining BTC/IBIT holdings. "
            "The portfolio-specific action remains HOLD until broker quantities and an ETF quote are confirmed."
        )
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
            f"At the indicative/entered IBIT quote, {decision['estimated_ibit_units']} whole units "
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
    full_research_cycle=cycle_exit_stage_status(
        market["halving_date"],market["asof_date"])
    if full_research_cycle["exit_window_expired"]:
        st.caption(
            "Full historical day-500/730 SELL policy: the last confirmed cycle's "
            "distribution window has passed. It cannot trigger a "
            "retroactive sale of holdings bought afterward."
        )
        if saved_cash.get("valid") and isinstance(saved_live_portfolio,dict):
            try:
                anchored=original_cycle_inventory(
                    saved_live_portfolio,market["halving_date"],
                    asof=market["asof_date"])
                if not anchored["eligible"]:
                    st.caption(
                        "Portfolio reconciliation: no recorded BTC/IBIT "
                        f"held before this cycle's day-500 review ({market['day500_date']}). "
                        "Do not backdate holdings purchased after the review."
                    )
            except (ValueError,KeyError,TypeError):
                st.caption("Historical position anchor unavailable: check recorded transactions.")
    elif full_research_cycle["next_exit_review_date"]:
        st.caption(
            f"Full historical SELL policy next review: "
            f"{full_research_cycle['next_exit_review_date']} "
            "(not an instruction to sell; original-BTC holdings and "
            "prior executions must be reconciled)."
        )
    # Original historical research model shown as a portfolio-aware,
    # strictly read-only SHADOW. It NEVER replaces the live % signals above,
    # because actual SMSF after-tax buyback cash has not been reconciled.
    with st.expander("Original backtested strategy — portfolio status (read only)",
                     expanded=False):
        st.caption(
            "Original strategy: day-500 staged SELL as % of original BTC/IBIT "
            "held before the review; following the full review window, "
            "weekly 200WMA recovery BUY as % of ORIGINAL after-tax sale cash. "
            "This panel cannot initiate an order or change the daily ntfy."
        )
        if saved_live_error or not isinstance(saved_live_portfolio,dict):
            st.info(
                "Saved executed-trade portfolio is unavailable. "
                "No original-position or after-tax buyback amount is inferred."
            )
        else:
            try:
                historic_wallet=historical_cycle_wallet_status(
                    market["price_history"],market["halving_date"],
                    saved_live_portfolio,asof=market["asof_date"])
            except (ValueError,KeyError,TypeError) as exc:
                st.warning("Original-strategy ledger cannot be reconciled: "
                           f"{type(exc).__name__}: {exc}")
            else:
                st.write("**Research phase:** "+
                         historic_wallet["phase"].replace("_"," ").title())
                st.write(historic_wallet["reason"])
                a,b=st.columns(2)
                a.metric("Original pre-day500 ASX:IBIT units",
                    (f"{historic_wallet['original_ibit_units']:,.0f}"
                     if historic_wallet["original_ibit_units"] is not None
                     else "Not fixed yet"))
                b.metric("Original pre-day500 direct BTC",
                    (f"{historic_wallet['original_direct_btc']:.8f}"
                     if historic_wallet["original_direct_btc"] is not None
                     else "Not fixed yet"))
                if historic_wallet["action"]=="SELL REVIEW — VERIFY":
                    st.info(
                        f"Historical research SELL review: "
                        f"{historic_wallet['sale_review_ibit_units']:,.0f} "
                        f"recorded ASX:IBIT units and "
                        f"{historic_wallet['sale_review_direct_btc']:.8f} direct BTC. "
                        "These are NOT broker orders; verify actual holdings, "
                        "original tax parcels and SMSF CGT before any trade."
                    )
                if historic_wallet["buyback_trigger_date"] is not None:
                    st.caption(
                        "Historical prior-200WMA recovery phase observed from "
                        f"{historic_wallet['buyback_trigger_date']}. Latest research "
                        "weekly sizing would be "
                        f"{historic_wallet['buyback_pct_original_budget']:.2f}% "
                        "of ORIGINAL after-tax buyback cash. Your verified budget "
                        "is unavailable, so no amount or trade is proposed."
                    )
                # Reconcile the ORIGINAL sale proceeds with dated FIFO lots,
                # but never infer tax paid, unrelated purchases, or an order.
                if historic_wallet["halving_day"]>=500:
                    try:
                        net_sale=original_sale_cash_reconciliation(
                            saved_live_portfolio,market["halving_date"],
                            asof=market["asof_date"])
                    except (ValueError,KeyError,TypeError) as exc:
                        st.warning(
                            "Original after-tax budget unavailable: "
                            f"{type(exc).__name__}: {exc}. "
                            "No BUY budget or dollar recommendation is inferred."
                        )
                    else:
                        if net_sale["qualifying_sale_count"]>0:
                            st.markdown("**Original sale-cash reconciliation (research)**")
                            p1,p2,p3=st.columns(3)
                            p1.metric("Recorded ORIGINAL sale proceeds after fees",
                                      f"A${net_sale['original_net_sale_proceeds_before_cgt_aud']:,.2f}")
                            p2.metric("Illustrative unpaid SMSF CGT reserve",
                                      f"A${net_sale['illustrative_unpaid_smsf_cgt_reserve_aud']:,.2f}")
                            p3.metric("Provisional original buyback budget",
                                      f"A${net_sale['illustrative_aftertax_sale_cash_aud']:,.2f}")
                            st.caption(
                                "FIFO estimate only (10% long-term / 15% short-term "
                                "positive gains without tax-loss offsets), not an "
                                "ATO assessment. Broker fees and all recorded BUYs "
                                "after day744 are conservatively deducted from "
                                "the original buyback cash. Actual SMSF status "
                                "and tax liabilities require confirmation."
                            )
                            if net_sale["unrecorded_future_transactions_ignored"]:
                                st.info(
                                    "Some trades are newer than the last verified BTC "
                                    "daily close; those trades are not included in this "
                                    "as-of-date historical calculation."
                                )
                            if historic_wallet["buyback_trigger_date"]:
                                with st.expander(
                                    "Original weekly BUY audit — previous reviews only",
                                    expanded=False):
                                    try:
                                        ledger=weekly_original_buyback_ledger(
                                            market["price_history"],
                                            market["halving_date"],
                                            saved_live_portfolio,
                                            asof=market["asof_date"])
                                    except (ValueError,TypeError,KeyError,
                                            AssertionError) as exc:
                                        st.warning(
                                            "Cannot reconcile historical weekly "
                                            f"BUY ledger: {exc}")
                                    else:
                                        st.caption(
                                            f"{ledger['review_count']} dated research "
                                            "reviews since first prior-200WMA "
                                            "trigger. Each percentage uses strictly "
                                            "prior market closes and the ORIGINAL "
                                            "after-tax buyback budget, not remaining "
                                            "account cash. These are completed "
                                            "historical reviews, NOT pending orders."
                                        )
                                        if ledger["review_count"]:
                                            w1,w2=st.columns(2)
                                            w1.metric(
                                                "Latest completed research review",
                                                ledger["current_review_date"])
                                            w2.metric(
                                                "Next scheduled model review",
                                                ledger["next_review_date"])
                                            st.caption(
                                                f"Latest completed research review is "
                                                f"{ledger['days_since_current_review']} "
                                                "calendar days old; do not place "
                                                "a retroactive BUY."
                                            )
                                            recent=[
                                                {
                                                    "Review date":item["review_date"],
                                                    "% original budget":item[
                                                        "pct_original_aftertax_buyback_budget"],
                                                    "Recorded cycle buys A$":item[
                                                        "recorded_this_cycle_aud"],
                                                    "Unreviewed/other A$":item[
                                                        "recorded_unreviewed_or_other_cycle_aud"],
                                                    "Independent A$":item[
                                                        "recorded_independent_aud"],
                                                    "Funding evidence":item[
                                                        "recorded_cycle_funding_provenance"],
                                                }
                                                for item in ledger["review_history"][-8:]
                                            ]
                                            st.dataframe(
                                                pd.DataFrame(recent),
                                                hide_index=True,
                                                use_container_width=True)
                                            st.caption(
                                                "Recorded cycle-funded values are "
                                                "user-labelled, NOT confirmed by "
                                                "a broker. Unreviewed buys always "
                                                "reduce the buyback budget; "
                                                "independent-cash buys still "
                                                "consume real account cash. "
                                                "No automatic BUY is created."
                                            )
                            if historic_wallet["buyback_trigger_date"]:
                                signature=net_sale["ledger_fingerprint"]
                                tax_entered=st.number_input(
                                    "Unpaid original-sale SMSF tax to reserve (AUD)",
                                    min_value=0.0,
                                    max_value=float(net_sale[
                                        "original_net_sale_proceeds_before_cgt_aud"]),
                                    value=float(net_sale[
                                        "illustrative_unpaid_smsf_cgt_reserve_aud"]),
                                    step=100.,format="%.2f",
                                    key=f"cycle_verified_tax_{signature}",
                                    help=(
                                        "You must reconcile this unpaid tax reserve "
                                        "and recorded sale proceeds with your SMSF "
                                        "records; the prefilled number is only an estimate."
                                    ))
                                broker_cash=st.number_input(
                                    "Available cash shown at broker before unpaid CGT (AUD)",
                                    min_value=0.0,
                                    value=0.0,
                                    step=1000.,format="%.2f",
                                    key=f"cycle_verified_broker_cash_{signature}",
                                    help=(
                                        "Enter independently verified broker cash, "
                                        "not a value copied from the Google Sheets ledger. "
                                        "Other unpaid liabilities must also be considered."
                                    ))
                                verified=st.checkbox(
                                    "I have reconciled the recorded sale proceeds, "
                                    "unpaid tax reserve and buyback spending.",
                                    value=False,
                                    key=f"cycle_verified_budget_{signature}")
                                try:
                                    preview=original_buyback_preview(
                                        saved_live_portfolio,
                                        market["price_history"],
                                        market["halving_date"],
                                        asof=market["asof_date"],
                                        verified_unpaid_tax_reserve_aud=(
                                            tax_entered if verified else None),
                                        verified_broker_cash_before_tax_aud=(
                                            broker_cash if verified else None),
                                        confirmation=verified)
                                except (ValueError,TypeError,KeyError) as exc:
                                    st.warning("Research budget preview unavailable: "+str(exc))
                                else:
                                    if preview["read_only_historical_review_aud"] is not None:
                                        st.metric(
                                            "Last scheduled research BUY tranche",
                                            f"A${preview['read_only_historical_review_aud']:,.2f}",
                                            help=(
                                                "Hypothetical sizing from ORIGINAL net "
                                                "sale cash, capped by recorded unspent "
                                                "budget and available AUD after unpaid CGT. "
                                                "This is NOT a current broker order."
                                            ))
                                        st.caption(
                                            f"Historical weekly review "
                                            f"{preview['last_weekly_research_review_date']}: "
                                            f"{preview['last_review_buy_pct_of_original_budget']:.2f}% "
                                            "of the fixed original after-tax proceeds "
                                            f"(A${preview['reconciled_original_aftertax_budget_aud']:,.2f}); "
                                            f"cash budget still unspent "
                                            f"A${preview['reconciled_unused_buyback_budget_aud']:,.2f}. "
                                            "All recorded later purchases reduce the available "
                                            "budget to prevent double-spending. "
                                            "Do not retroactively execute a missed review."
                                        )
                                    else:
                                        st.info(
                                            "No reconciled original after-tax BUY amount. "
                                            "The historical percentage alone is not "
                                            "a cash-available trading instruction."
                                        )
                        else:
                            st.caption(
                                "No executed sales of the ORIGINAL pre-day500 position "
                                "during day500–730 are recorded; no original after-tax "
                                "buyback budget can be established."
                            )
                st.caption(
                    "Cash recorded in the portfolio is before SMSF tax escrow. "
                    "Historical research-to-live trade quantities are not "
                    "validated as equivalent. Nothing here writes to Google "
                    "Sheets, your broker or ntfy."
                )
    st.caption(
        "MODEL VALIDATION: The live SELL percentages are applied to REMAINING units "
        "(37.32% remains if all seven stages execute); the historical exit test "
        "uses ORIGINAL BTC and dynamic regime factors, including a different 20% "
        "holdback policy. The live recovery BUY is also an initial 200WMA gate "
        "rather than the complete backtested recovery phase. The earlier historical "
        "BTC multipliers do not validate these live allocation rules."
    )
    st.caption(
        "The recovered-cash calculation uses recorded sale proceeds but does not "
        "automatically escrow real SMSF taxes. Consider tax reserves before trading."
    )
    st.caption(
        "A BUY percentage is measured against AVAILABLE AUD CASH; a SELL percentage "
        "is measured against CURRENT HOLDINGS, not the original A$500k. "
        "Both percentages are the same research market rules reported by the daily ntfy message. "
        "These are per eligible DCA tranche, not instructions to repeat a trade every day. "
        "Check your executed trade ledger and broker before acting."
    )
    st.caption(
        "Late-cycle SELL rollover is an experimental price-only safeguard, not the "
        "validated day-500 sell-backtest. Historical review windows "
        "cannot retroactively apply to newer purchases. No order is ever submitted."
    )
    st.divider()
    st.subheader("Underlying market signals")
    current_signal=("Prior close below the 200WMA — buyback gate observed"
                    if market["previous_close_below_200wma"] else
                    "Prior close above the 200WMA — initial buyback gate not observed")
    st.info(current_signal)
    st.caption("This is an entry-gate observation, not an assertion that the bear-market low is in.")
    st.subheader("Current cycle top and bottom (A$ BTC)")
    st.caption("Observed Bitcoin prices in Australian dollars; percentages compare the latest available close with each level.")
    try:
        # Historic 2025 peak MUST be converted with FX from 2025,
        # not today's AUD/USD. The standard public fetch only
        # includes FX from December 2025 onwards.
        cycle_historic_fx=cycle_fx_source(market["halving_date"],market["asof_date"])
        cycle_aud=observed_aud_cycle_levels(
            market["price_history"],cycle_historic_fx,
            start=market["halving_date"],
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
            f"Range is since the last confirmed halving ({market['halving_date']}), with the bottom "
            "defined AFTER the observed top. Same-date historical FX; "
            "daily closes, not intraday extremes or a prediction."
        )

    with st.expander("200WMA, halving dates and BTC price chart",
                     expanded=False):
        c1,c2,c3,c4=st.columns(4)
        c1.metric("BTC/USD historical close",f"US${market['btc_price_usd']:,.0f}")
        c2.metric("Prior-observation 200WMA",f"US${market['prior_200wma_usd']:,.0f}")
        c3.metric("Prior close / 200WMA",f"{market['prior_close_vs_200wma_pct']:+.1f}%")
        c4.metric("Days from last confirmed halving",f"{market['halving_day']:,}")

        st.caption(
            f"Confirmed halving {market['halving_date']} • day 500: {market['day500_date']} "
            f"• day 560: {market['day560_date']}. "
            "Timeline milestones are not retroactive broker instructions."
        )
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
            st.info("No saved purchases found. Record an executed BUY using the form below.")
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
        price_history=market["price_history"],
        historical_fx=cycle_historic_fx,
        store_error=store_error
    )

with tabs[2]:
    st.subheader("Historical whole-cycle comparison")
    st.info(
        "Historical research accounts each hypothetically invest A$500,000 at the selected *historical halving*, "
        "not your real 2026 starting portfolio. 2013 is excluded from primary selection. "
        "Each cycle's completeness is calculated from available observed data, "
        "not a fixed 2026 calendar assumption."
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
