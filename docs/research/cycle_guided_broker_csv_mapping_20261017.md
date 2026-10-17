# Native broker CSV → BTC Cycle Portfolio comparison — guided, read-only field mapping

17 October 2026 · Research only, no trading or portfolio writes

## Goal

After PR #130 introduced two strict neutral CSV templates for comparing saved Google Sheets My Portfolio trades and dated broker positions, using real broker CSVs still required manually copying all their columns into those templates.

This update adds an OPTIONAL **Map source broker columns** workflow directly inside the existing **Cycle Trading → My Portfolio → Compare broker CSV statements with My Portfolio (read-only)** interface. The original **Already matches standard template** route continues to work.

The mapper deliberately does **not** pretend that it knows the layout of a particular broker's exported statements. Instead, you select which source columns represent the actual **execution date, BUY/SELL, source symbol, quantity, gross AUD consideration, brokerage fees, optional currency and order reference**. You then explicitly assign each distinct broker action value to BUY or SELL and each source symbol to the Australian-listed **ASX:IBIT** or **Direct BTC**. For holdings CSVs, select the broker asset/quantity columns and an **as-of date**, and map the distinct source symbols to **ASX:IBIT**, **Direct BTC** or **AUD Cash**.

An example input from one *hypothetical* broker:

```csv
Trade Date,Action,Ticker,Amount,Consideration,Commission,CCY,Order No
2026-10-15,Acquired,IBIT,10,250.00,3.00,AUD,ORDER-123
2026-10-16,Disposed,IBIT,2,60.00,3.00,AUD,ORDER-124
```

The user would map **Trade Date → Date**, **Action → Side**, **Ticker → Asset**, **Amount → Units**, **Consideration → Gross AUD**, **Commission → Fee AUD**, **CCY → Currency**, **Order No → Reference**, and confirm Acquired=BUY / Disposed=SELL. The unqualified symbol `IBIT` is intentionally **not presumed Australian**: the user must independently confirm the instrument is the ASX-listed ETF before mapping it to ASX:IBIT. A NASDAQ/US-listed IBIT exposure is not represented by this portfolio schema and MUST NOT be included.

## Safe behaviour

- **No currency conversions or guessed broker formats.** Execution money in USD or a non-AUD currency is rejected. If no currency column exists, the user must expressly confirm money/fees are in AUD, and that the selected amount is **gross consideration BEFORE fees**, not net settlement.
- **No imaginary fee assumptions.** A fee column is required unless the user expressly certifies that the statement has genuinely zero execution fees. There is no default A$3 fee in the mapper.
- **No silently omitted rows.** Every BUY/SELL code and every source asset/symbol must have a valid explicit classification or the entire file fails closed. No trade is marked as filled because a broker row is pending, and only real executions should be uploaded.
- **No unconstrained source columns.** A source field cannot be assigned two different meanings, missing/gibberish/extra row contents are rejected, duplicate or economically identical fills are still reported as *ambiguous* by the subsequent original one-to-one reconciliation, not auto-added to the portfolio.
- **Exact original units.** Australian ETF quantities must be whole units; direct BTC can be recorded to eight decimal places. Price/quantity/fee validation then uses the same tested strict neutral parser as PR #130.
- **Balancing differences stay informational.** Broker AUD cash—even when equal to ledger cash—is **NOT proven free after unpaid SMSF taxes, open settlement commitments or other liabilities**, and cannot automatically increase Cycle Trading's BUY order sizing.
- **User privacy.** The uploaded original CSV is read by the user's configured Streamlit server during use. Its contents are processed in memory and not persisted to GitHub, Google Sheets or an extra NAS by this code. Per-file mapping controls are distinct for each uploaded source fingerprint to avoid accidentally applying old choices to a different broker file.
- **Size constraints:** at most 512 KiB and 1,500 data rows per source, UTF-8 CSV, and no silently discarded unknown account values.

## Before trying this on your brokerage exports

First inspect an actual original executed-trades statement and determine:
- Which exchange/ETF was traded (do not confuse US IBIT with ASX:IBIT);
- What time/date an execution occurred, not just when it settled;
- Whether the amount is the **gross AUD trade consideration** and the broker fee is a separate AUD field;
- Whether the statement includes the same brokerage account and entire date range being compared.

If a report contains only account balances or aggregate P&L instead of completed executions, use the **balance** mode or request the broker's executions export rather than inventing trades.

## Scope

Files:
- `engines/research/cycle_broker_csv_mapping.py` — strict pure mapper
- `engines/research/cycle_broker_csv_mapper_ui.py` — explicit Streamlit field mapping
- `engines/research/cycle_portfolio_editor.py` — existing read-only reconciliation integration
- `tests/test_cycle_broker_csv_mapping.py` — no silent USD, no US IBIT mapping, no implicit fees, duplicate execution handling, dated balances and statement safety
- `.github/workflows/research_cycle_trading_dashboard.yml`

**No changes** to Production V5.8.2, Research V5.9, original 200WMA historical/backtested model, Cycle Trading live current BUY/HOLD/SELL signal, existing single daily ntfy schedule, user's recorded Google Sheets transactions or actual broker trades.
