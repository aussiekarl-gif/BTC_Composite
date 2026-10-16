# Cycle Trading: record and reconcile actual ASX:IBIT buys and sells

**Research-only portfolio editor · 17 October 2026**

Open Streamlit → sidebar Model → **Cycle Trading — Research** →
**My Portfolio — Buy & Sell**. This uses the existing Google Sheets
`portfolio_state` record used by Production and Research. No new
account, spreadsheet, NAS or secret is needed.

## Record an executed BUY

1. Confirm your purchase has filled at the broker (not a proposed order).
2. Select **BUY**, **ASX:IBIT** or **Direct BTC**, and the execution date.
3. Enter the **actual executed quantity** and **AUD price per ETF
   unit or per whole BTC**, not your total purchase amount.
4. Confirm actual trading fees. ASX:IBIT defaults to A$3 (editable).
5. For ASX:IBIT BUY, enter BTC/AUD at the actual purchase date for
   estimated BTC-equivalent exposure; today's quote is not a
   historical-date substitute. For direct BTC, the recorded BTC
   quantity itself is exact.
6. Enter a unique broker order reference in Notes. Tick the explicit
   executed-order confirmation and save.

The persisted existing `rows` purchase ledger remains compatible
with both earlier My Portfolio editors; no sample or synthetic
transaction is added.

## Record an executed SELL

Select **SELL** in the same form and enter the actual trade
date, ticker, quantity of units/BTC sold, executed AUD price **per
unit/BTC** and brokerage. Saved sales are appended to a separate
`sales` array alongside purchases in the **same shared Google
Sheets JSON**. All original purchases and their order chronology
are preserved. Quantity subtraction uses a strictly validated,
chronological asset-specific FIFO inventory replay. The model
rejects unsupported fractional ASX:IBIT units, future dates,
sale-before-purchase, sales beyond the owned quantity, and tiny
one-satoshi overdraws. Identical recorded executions need
different broker order references to avoid accidental duplication.

The portfolio automatically recomputes:
- **Net ASX:IBIT units** (original recorded buys − recorded sells),
  as a whole-unit quantity.
- **Net direct BTC** at 8 decimal places.
- **Cash** = initial AUD funding − recorded purchase consideration
  − all buy/sell fees + gross sale proceeds.
- Estimated **BTC-equivalent ETF exposure** from remaining FIFO
  purchase shares and historical BTC/AUD; unavailable historical
  BTC reference is displayed as UNKNOWN rather than a fabricated
  number.

These are **exact quantities as recorded in your transaction ledger**,
not automatically verified broker balances. Always reconcile with
the broker, especially if there were trades before portfolio
tracking began. These holdings are *not* the same as directly
owned Bitcoin backing the ETF. Cash is **before** any SMSF CGT
reserve or tax bill; discuss tax lots and fund phase with your
accountant before redeploying all sale proceeds.

## Current trading signal integration

The Cycle Trading → **Current signals** tab reads the newly
calculated *net* ASX:IBIT balance from the same Sheet rather
than summing lifetime purchases. For any SELL signal, you
still tick **I have verified my currently held ASX:IBIT
units in my broker**. It then proposes an illustrative whole-unit
sale on the reconciled holdings and delayed automatic indicative
IBIT quote; it never directly places any trade.

Recorded BUY and SELL history is also downloadable in its
entirety as a JSON backup.

## Data safety

- Existing **Production and Research buying models** are unchanged;
  only their old portfolio saving routines now preserve any
  `sales` ledger in the shared JSON and reject stale edits.
- The older buy-only portfolio editors still display lifetime
  purchase costs. For **net** current units/cash, always consult
  **Cycle Trading → My Portfolio — Buy & Sell**.
- No automatic broker import, no guarantees of bid/ask fills, no
  guessed realised CGT; the user must enter actual executed trades.
- If BTC market data is down, Cycle Trading still lets you
  read/edit the saved portfolio using *manual executed* prices.
- Successful Google Sheets persistence is confirmed by existing
  `save_portfolio()` verification; the feature's tests also
  perform real SQLite save/load roundtrips.
- Concurrent edits are guarded by rereading the shared current
  BUY and SELL records immediately before each write. Google
  Sheets isn't an atomic transaction database, so avoid trading
  simultaneously from multiple open browser tabs and refresh first.
- The ntfy schedule and daily one-message policy are untouched.

**ChatGPT does not inherently have direct access to the private
Google Sheets service account or your live broker balances.**
Within Streamlit, the linked Google Sheets record is read directly
and holdings shown. To independently inspect them from a ChatGPT
conversation requires a separate authorized connected app or
the user sharing an export.
