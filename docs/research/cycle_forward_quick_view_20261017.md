# Cycle Trading — next applicable original review and simplified daily decision
17 October 2026 | Research only, read-only UI

## Why this view exists

The original historical Bitcoin programme (BUY upon a strict previous-close below the previous 200WMA; thereafter weekly adaptive recovery percentages of **original after-tax sale proceeds**, with SELL stages around halving day500–730 measured as **percent of original BTC**) was extensively audited and replayed in PRs #118–123. The simpler current live Streamlit/ntfy WATCH (BUY as **2.5% of remaining account cash**, SELL as **percent of remaining holdings**) is **NOT historically equivalent**.

A more usable dashboard must NEVER quietly combine or confuse those percentages. The new view shows both separately; it does NOT create a new market-timing signal.

## What changes in Streamlit

In **Cycle Trading → Trading decision**, immediately after the existing broker cash / ETF quote / holdings confirmation controls, the panel **Cycle Trading — quick view** provides:

- **Daily simplified market signal** with BUY % of remaining AUD and SELL % of remaining BTC/IBIT. The same decision engine and its safety checks remain responsible for these; the panel does not issue or override trades.
- **Original strategy: next review**. Before a confirmed cycle day500, show that known date as a scheduled *research review*, not an executable sale. During day500–730, show only actual upcoming review dates and an original-position SELL percentage on the **current review date** when original holdings are recorded and the prior market feed is verified.
- **Original historical BUY/SELL allocation**: When genuine original-position sales exist and the earlier full review window has closed, the panel can show the **last completed weekly** % of original net after-tax budget and next dated *research* review. It NEVER pretends next week's 200WMA/regime-dependent percentage has already been observed, or that the user has broker-/tax-verified cash.
- **Recorded holdings and pre-CGT cash**, and, if applicable, **historical original-position sale receipts before tax**. These are explicitly not executable broker confirmations.
- A prominent eligibility / blocker explanation: missing historical original position, no actual sale proceeds, unknown first future 200WMA trigger, unverified feed, invalid ledger, or tax/cash not yet reconciled.

For a portfolio whose BTC/IBIT was first bought in **2026**, the **2 September 2025** day500 sale cannot be repeated or funded retroactively. The original cycle's next SELL window depends on a **future Bitcoin halving**; the future date is **not filled in until that halving's block event is verified**, at which point its day500 review can be calculated from the actual epoch. The current simplified market watch may still show HOLD/BUY WATCH/SELL WATCH independently, but is NOT the validated backtested strategy.

A future price-triggered 200WMA BUY has **no fixed calendar date**; displaying a definite date before the gate is observed would be misleading. Future weekly tranche sizes also depend on future observed price averages and are not pre-computed.

## Fail-closed and no-lookahead rules

- No saved portfolio or invalid ledger => no historical inventory, cash or allocation is invented.
- Unverified BTC market, FX provider or confirmed halving => simplified signal displayed as UNAVAILABLE and no original actionable percentage.
- A saved portfolio can include trades newer than the public BTC daily close. The overview **dates its portfolio snapshot to the latest observed BTC close**, ignores newer purchase/sale rows for that snapshot and explicitly warns about them.
- No guessed actual SMSF accumulation/pension phase, FIFO tax loss utilisation, broker unit confirmation, ETF trade prices or real tax-adjusted after-sale budget. The separate opt-in weekly Research panel remains the only place to confirm tax provision and broker available cash for an illustrative AUD review, with no order allowed.
- Future review dates are not trade signals or forecasts. Past review percentages are labelled **past**.
- No Google Sheets changes, portfolio label writes, broker orders, live model change, Production V5.8.2 / Research V5.9 change, daily ntfy message or schedule change.

## Test and reproduction

Files:
- `engines/research/cycle_forward_quick_view.py`
- `tests/test_cycle_forward_quick_view.py`
- `engines/research/cycle_trading_app.py`
- `.github/workflows/research_cycle_trading_dashboard.yml`

Tests include real 2026-only purchase vs historic 2025 day500, same-day recorded original-position SELL review, known historical buyback review and still-unknown future fraction, no qualifying sale proceeds, missing prices/feed, invalid inventory, new trades entered after an earlier as-of date, strict future market observation invariance, and next verified known date.

**Original 200WMA/day500 after-tax backtests remain historically inspected, not prospective performance guarantees.** Nothing here upgrades the simplified watch into backtest-verified parity.
