# Dated weekly original Bitcoin Cycle BUY audit
17 October 2026 · Research-only — **no change to live Streamlit/ntfy trading signal**

## Purpose

After establishing the original historical 200WMA/day500 policy in PRs #118–119 and reconciling executed historical original-BTC sale proceeds, tax reserves and purchase funding labels in PRs #120–122, this change makes the **weekly recovery-buy sequence independently auditable**.

The original strategy has **one-time BUY activation**, after all possible day500–730 original BTC SELL reviews have closed plus 14 days, when the previous completed BTC close falls *strictly below* the preceding 200 weekly moving-average closes. From that first trigger onward, the model uses a historical review exactly every seven calendar days and sizes each review from the **fixed ORIGINAL after-tax sale proceeds** rather than 2.5% of remaining cash. The percentage may increase or decrease based on the prior 200WMA ratio and 50DMA trend; it is NEVER based on the ex-post known bottom.

Code: `engines/research/cycle_weekly_buyback_audit.py`, reuses `causal_buyback_dates()` and `recovery_buy_budget_fraction()`. These were the pre-existing historical policy functions, **not a new set of indicator thresholds**.

## How the weekly ledger treats actual recorded purchases

| Purchase classification | Assigned to weekly original-budget research review? | Reduces original buyback cash budget? | Counts as proof of cycle-funded execution? |
|---|---|---|---|
| Recorded **Original cycle sale proceeds** for the same halving | Yes, to the preceding seven-day research review | Yes, full AUD paid plus fee | Only user-attested, not broker-verified |
| Recorded **Unreviewed** (legacy) BUY | Yes, grouped as unknown | **Yes** | **No** |
| Recorded original proceeds from a different halving | Yes, grouped as unknown/other-cycle | **Yes**, conservatively | No |
| Recorded **Independent cash** BUY | Tracked separately by review | No; still reduces actual broker/account cash | No |
| BUY dated after day744 but **before the first valid 200WMA trigger** | Separate prior-trigger spend tally | **Yes**, unless independently funded | No; cannot be backdated to future review |
| BUY after observed as-of BTC closing date | Excluded | Excluded until observed as-of catches up | No |

A purchase made a few days *after* an observed review is grouped into that previous review's seven-day calendar window for auditing. That does **not** retroactively create a recommended or filled order on the review date. The table shows its actual funding-tag evidence, not assumed trade fills.

Every AUD debited against the original budget is independently checked against the existing original-sale reconciliation. If totals do not match, the calculation fails closed. Neither the table nor the user label changes any asset, date, quantity, price, fee, buyback budget from genuine original sale proceeds, or broker balance.

## Streamlit display

Open **Cycle Trading — Research → Trading decision → Original backtested strategy — portfolio status (read only)**. For portfolios with ACTUAL qualifying original pre-day500 BTC/IBIT sales and a historical prior-200WMA buyback trigger, expand **Original weekly BUY audit — previous reviews only**.

It shows:

- Total observed historical weekly reviews, their first trigger, last completed date, elapsed days since the last, and next scheduled *research model* review date.
- Last eight dated research percentages of ORIGINAL after-tax buyback budget and confirmed/unknown/independent recorded purchase amounts and labels.
- Warnings that no previous review is a current broker instruction, that independent funding labels are user-attested only, and that unreviewed buys must still be budgeted.

This is a read-only history table, not an alert, broker order, price/ETF quote, SMSF tax assessment, or a reason to execute a late BUY.

## Test evidence and limitations

Regression tests in `tests/test_cycle_weekly_buyback_audit.py` include:

- Exact per-week parity with the pre-existing adaptive recovery policy, which uses strict previous-day observations.
- Exact reconciliation of AUD buys, fees, user-attested cycle labels, unknown and independent funding.
- Previously recorded purchases are never inferred from future price observations or future purchases.
- No original 2025 SELL budget exists for BTC/IBIT purchased only in 2026.
- Missing daily price references, unrecognised funding labels and impossible histories fail closed.

Historical 2017/2021 in-sample after-tax backtests are not rerun or altered by this presentation change. Their returns **do not validate** the simplified production 2.5%-of-remaining-cash ntfy BUY recommendation, which is still a different model. Historical review windows cannot be used to backdate a 2025 SELL on new 2026 investments.

## What still needs to happen before changing daily recommendations

The exact after-tax broker cash, actual FIFO tax parcels, fund phase and real broker order confirmations must be reconciled for an **actual future** completed original-position SELL cycle. This audit is a bridge that checks the historical percentages and recorded funding labels; it does not justify switching the current daily messages or issuing automatically tradeable quantities.

Production V5.8.2, Research V5.9, the existing Cycle Trading BUY/HOLD/SELL decision, ntfy formatting/schedule, Google Sheets content and real broker trades are all unchanged.
