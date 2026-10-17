# Cycle Trading — consolidated recorded portfolio and broker-reconciled decision
17 October 2026 | Research only | PR #129

## Goal

**One screen for today's decision**, rather than another indicator or historical strategy. The dashboard now distinguishes (a) the existing simplified daily BTC BUY/HOLD/SELL WATCH; (b) the exact net quantity of recorded ASX:IBIT and direct Bitcoin, plus unreserved AUD cash from the existing Google Sheets executed-trade ledger; and (c) a separately manually verified quote/free-cash estimate, when requested. The original historical day500 SELL and weekly 200WMA BUY calculations remain intact and available inside the expandable historical policy details, but their denominators are NOT mixed with current live trading.

## New main view

Open **Streamlit → Cycle Trading — Research → Trading decision → Cycle Trading — quick view**. It appears immediately below the compact, normally collapsed **Broker cash and SMSF tax check — verify before any trade**.

The primary current market signal shows **BUY WATCH / SELL WATCH / HOLD / UNAVAILABLE** without changing the underlying existing research decision. Its allocation caption shows BUY % of *remaining AUD cash* and SELL % of *remaining BTC/IBIT*, not the original historical buy % of fixed after-tax original sale proceeds or historical sell % of original BTC holdings. A verified fresh-cash-200WMA experiment remains separate.

The recorded portfolio panel displays AUD cash **before unpaid taxes or other liabilities**, independently displays ASX:IBIT **whole units** and direct BTC **actual recorded units**, and never invents Bitcoin beneficial ownership backing the ETF units. FIFO-based historical realised capital-gains estimate is separate, by completed dated sale parcels, and **is not a verified amount of tax unpaid**.

The broker-checked trade panel shows **Not verified** until the user expands the broker check, types a fresh *actual* broker ASX:IBIT quote and (for BUY) **independently confirms cash free after all unpaid taxes and other reserves**, checks the box and submits the research-only calculation. No amount from an unverified automatically delayed ETF quote can be labelled *broker-verified*.

For the *same submitted view only* the BUY panel then shows: the existing model's currently allowed BUY amount **capped down** by the lesser of verified broker free cash and recorded net uninvested cash, plus estimated *whole ASX:IBIT units*, with A$3 brokerage. The screen distinguishes the **gross candidate budget** from the **smaller estimated executed whole-unit cost**, and preserves the remainder as cash. The previous implementation could increase the BUY amount when independently confirmed cash exceeded a user-reduced main-decision cash input. **Now that cannot happen:** `broker_gross_buy <= existing_decision.action_aud`, and a below-minimum broker check displays zero instead of an apparent trade. Confirmed cash that is **already net of taxes** is not reduced a second time by a modelled CGT provision.

For a SELL, quantity is exactly the model's already broker-unit-confirmed original SELL decision (no extra lots are manufactured). The separately supplied broker quote reprices that fixed quantity. Recorded FIFO lots supply an **illustrative** accumulation-phase CGT on gross positive gains, net sale proceeds after fee and illustrative provision; actual tax could differ depending on SMSF phase, discounts, losses and tax already paid.

A HOLD, stale/unavailable market or corrupt ledger **stays untradeable** even if a broker user enters a large cash value. A prior browser/session verification does not carry forward to a new Streamlit evaluation or different market signal/date; there is no persisted broker quote/cash or tax preference.

## Example (fabricated data only)

If the market engine already gives a **BUY** limited by manual main-decision cash to A$120, the portfolio ledger shows A$359,967 and the broker independently confirms A$100,000 available after liabilities, the checked calculation **stays limited to A$120**. With a fresh A$30 ASX:IBIT price and A$3 fee, the maximum is **3 whole ETF units costing about A$93**; the unspent A$27 of that research tranche remains as cash. The main decision's cap is never increased to 2.5% of A$100,000.

If the market engine gives HOLD, the checked dashboard gives **no verified order quantity**, regardless of cash. If the broker confirms only A$100 for a model BUY, the A$103 minimum including brokerage blocks any suggested whole-unit purchase.

## Original historical strategy

The details behind **Original historical cycle strategy — next review and eligibility** remain available in an expander. Its BUY denominator is the original after-tax sale proceeds and its SELL denominator is the original BTC holdings, rather than today's simplified remaining-cash/remaining-holdings model. It never retroactively sells BTC/IBIT first acquired in 2026 during the September 2025 historical SELL review. Historical backtested ROI cannot be attributed to today's simplified daily ntfy rule.

## Non-execution safety and test evidence

- No broker trades, tax filings, portfolio cash/holdings edits, Google Sheets writes, new ntfy messages, scheduling changes or new optimisation thresholds.
- One pure module: `engines/research/cycle_single_screen_brief.py`; separate from the unchanged existing `engines/research/cycle_trade_allocation.py`.
- Safety correction in `engines/research/cycle_broker_cash_review.py`.
- Tests in `tests/test_cycle_single_screen_brief.py` and additional broker cap tests in `tests/test_cycle_broker_cash_review.py`: actual ledger cash and IBIT/direct BTC units, illustrative historical tax, no HOLD escalation, verified BUY/SELL, no over-recommendation after manual cash input, whole-unit rounding and minimum trade, no future-date history leaks and invalid ledger fail closed.
- Streamlit/ntfy regression workflow: `.github/workflows/research_cycle_trading_dashboard.yml` plus existing Portfolio Integrity, BUY/HOLD/SELL and notification safety workflows.

**Current live trading percentages, Production V5.8.2, Research V5.9, single existing Google Sheets portfolio, original backtest benchmark and daily ntfy all remain unchanged.** This remains an independently broker-confirmed *read-only research preview*, not investment advice or an executable trading system.
