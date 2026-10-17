# BTC Cycle Trading — read-only broker CSV reconciliation

17 October 2026 | Research + portfolio reconciliation only

## Why this work matters

The single existing Google Sheets My Portfolio contains manually recorded purchases, sales and original BTC/ASX:IBIT units. A recorded unit count or cash balance is not, by itself, proof that the independently held brokerage or SMSF custody account agrees. The previous Cycle Trading user-interface still required checking holdings, cash and executed transactions entirely manually.

This adds an **optional in-memory read-only CSV comparison**. It does NOT connect to or download from a broker without user permission, does NOT save broker documents in Google Sheets or GitHub, does NOT mutate existing trades, and does NOT submit brokerage instructions.

## Where to find it

Streamlit **Cycle Trading — Research → My Portfolio — Buy & Sell → Compare broker CSV statements with My Portfolio (read-only)**.

There are download buttons for **two standardised templates**:

**Executed trades:**

```csv
Date,Side,Asset,Units,Gross AUD,Fee AUD,Reference
2026-10-15,BUY,ASX:IBIT,10,250.00,3.00,ORDER-123
2026-10-16,SELL,Direct BTC,0.00500000,600.00,0.00,ORDER-124
```

**Dated holdings and account cash:**

```csv
As Of,Asset,Quantity
2026-10-17,ASX:IBIT,100
2026-10-17,Direct BTC,0.12500000
2026-10-17,AUD Cash,50000.00
```

Broker native export columns vary across Stake, IBKR, SelfWealth and others. **Do not simply upload arbitrary formats** and hope the script guesses. Transfer the relevant fields from the original broker statement into the provided CSV template and preserve the original confirmation. The portfolio records prices/costs in Australian dollars, IBIT is **ASX-listed IBIT.AX** rather than US NASDAQ:IBIT, and direct BTC units are separate from ETF shares. The parser deliberately refuses unknown and US-listed tickers and mixed-format unrecognised fields.

## Trade-by-trade reconciliation

Users select the precise date range covered by their broker execution CSV and **optionally attest** that this is a complete statement for all trades in that date range/account. The app compares exactly matched asset, side, date, units, gross AUD transaction consideration and fees (2 cent economic matching tolerance). A broker execution reference is matched to the corresponding saved execution note/ID when possible.

Results distinguish:

- **Matched executions** — a unique one-to-one economic match.
- **Broker-only to review** — an executed broker trade not matched to a recorded row. A missing Google Sheets trade is POSSIBLE but not proven; differences in price/fee/account/date can also cause this.
- **Portfolio-only to review** — a recorded trade not matched in the uploaded broker period. A broker omission cannot be inferred from an incomplete or different-account statement.
- **Ambiguous duplicate fills** — economically indistinguishable broker or portfolio rows not provably one-to-one. These never get silently matched based on row number; reference evidence is needed.

The results show dates, side, asset, quantity, gross consideration and fees; users can download the full discrepancy summary as CSV. No browser click to automatically append/delete/update trades is created. The original Google Sheets ledger remains the only persistent source for model holdings and cash.

## Dated balance reconciliation

A second optional CSV reports actual broker quantities for IBIT, Direct BTC and broker AUD cash on ONE `As Of` date. The app reconstructs portfolio holdings **only through that observed date**, compares reported and recorded balances and displays the difference for each asset. Missing balance rows are marked as **not supplied**, never assumed to be zero.

**Cash warning:** even if broker AUD cash and ledger AUD cash happen to match, neither proves actual *available after unpaid SMSF tax and other liabilities*. Other reasons for differences include unsettled orders, income, transfers, withdrawals and fees not modelled by a pure BUY/SELL ledger. Such differences NEVER increase the existing daily BUY allowance or alter the original 200WMA strategy.

## Data security / limits

- The uploads are processed in memory in Streamlit, **not persisted** in GitHub or the Google Sheets JSON portfolio. However, they are sent to the **user's configured Streamlit server** during upload; do not treat browser/cloud upload as never leaving the device.
- Each CSV is limited to 512 KiB and 1,500 data records to prevent accidental large/foreign file imports.
- UTF-8 with or without BOM, exact documented broker-neutral CSV headings and decimal dots are required. Duplicate headers/references, future-dated trades, malformed rows, non-ETF fractions, negative fees, missing positions or invalid saved ledger stop processing.
- The parser will not infer ASX:IBIT from unqualified `IBIT` or `NASDAQ:IBIT`, and will not guess conversions of US dollar consideration.
- Matching cannot prove original account ownership, tax lots, settlement, missing outside transfers, allocation provenance or trade fills from unauthenticated screenshots. Uploaded references remain user-provided evidence.
- CSV statements must be prepared for the same brokerage account and declared date range; results should always be checked against the original execution statements.
- This does **not** automatically import broker balances into the trading decision, give broker/API credentials to GitHub or perform real trades.

## Verification and source

- Engine: `engines/research/cycle_broker_csv_reconciliation.py`
- UI: `engines/research/cycle_portfolio_editor.py`
- Tests: `tests/test_cycle_broker_csv_reconciliation.py`
- GitHub CI: `.github/workflows/research_cycle_trading_dashboard.yml`, plus existing portfolio and notification regression suites.

**No change** to Production V5.8.2, Research V5.9, current Cycle BUY/HOLD/SELL percentages, one daily ntfy schedule, Google Sheets contents or broker custody.

## Next integration milestone

Only after actual broker document formats and balance semantics are confirmed should the CSV normalizer be broadened for individual providers; retaining source evidence and explicit exchange/currency labels is essential. Later, an authenticated read-only broker connector could eliminate manual CSV conversion, but it needs separate user permission and a supported secure API.
