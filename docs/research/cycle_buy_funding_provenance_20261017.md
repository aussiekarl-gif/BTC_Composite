# Cycle Trading: optional funding provenance for recorded BTC/IBIT BUYs
17 October 2026 | **Research only, no new trade suggestions or broker orders**

## Why

The original backtested cycle programme buys only with original *after-tax cycle-sale proceeds*, not with an undifferentiated account balance. Before this change, the live Google Sheets portfolio has no evidence which executed later BUYs were paid from those proceeds. The research reconciliation therefore debited **every** later BUY against the original historical buyback budget, potentially understating genuinely available cash but avoiding double counting.

PR #122 adds **optional USER-ATTESTED metadata** to existing saved BUY records. It does not change asset, price, date, unit count, brokerage, AUD spent, SELLs, portfolio holdings or account cash. No metadata is written without the user explicitly submitting/confirming the classification from their saved portfolio.

## Streamlit flow

Open **Cycle Trading — Research → Record executed BUY or SELL → Identify funding of recorded BUYs (optional)**.

Pick an existing, actually executed purchase. Choose:

- **Unreviewed** (the default for all old purchases): conservatively subtract its full AUD consideration **plus fee** from the original sale-funded budget if the purchase occurred after the buyback review gate. No assumptions about where the money came from.
- **Independent cash**: user asserts that independent cash, not the original day500 BTC sale proceeds, funded this particular purchase. For the *original-sale budget ledger* only, the purchase can be excluded from the amount already spent. It still reduces actual portfolio and broker cash normally; it cannot conjure cash or authorise an order.
- **Original cycle sale proceeds**: user asserts purchase was financed by that specific halving cycle's original BTC/IBIT day500–730 sales. Requires confirming the halving date; code refuses classification unless the recorded ledger actually contains *eligible original-position sales* for that cycle and the purchase date is at least day744. Its cost + fees are always subtracted from the original-sale budget.

A confirmation checkbox requires checking the purchase's cash movements and broker statement. Source tags are NOT independently verified; Streamlit applies a transaction-level stale guard before saving to Google Sheets, and refuses to overwrite purchases/sales added by another session. The old legacy portfolio editor preserves tags on unaltered purchase rows instead of silently deleting them.

## Safety and modelling boundaries

1. Old or untagged purchases are NEVER silently reclassified. They continue to reduce the original sale budget.
2. Labels classified as **Original cycle sale proceeds**, whether matching the current research cycle or not, are still deducted conservatively when reconciling that cycle until separate-account cash source segregation can be demonstrated; the user cannot cause double counting by shifting the halving tag.
3. Only a user-confirmed **Independent cash** label can make that budget's historical spending estimate smaller. This does NOT increase the verified broker cash, and the original aftertax BUY preview from #121 still requires **both** the user-verified unpaid SMSF tax provision and the independently entered available broker cash, and caps the displayed historical amount by the *lesser* of budget remaining and verified cash less unpaid taxes.
4. The model remains a *read-only last-weekly-review research preview*, not a current executable trade. Repeated recorded buys on the same review date still suppress duplicate previews. Invalid or missing halving tags fail closed.
5. No recorded original BTC/IBIT holdings before 2 September 2025 means **no** historical 2025 exit proceeds. BTC/IBIT bought in 2026 cannot be given an imaginary 2025 sale. The 2024 halving cycle's original strategy is thus usually INAPPLICABLE to a 2026-only investor; future cycles must use future, actually recorded position anchors and trades.
6. Cost-basis, SMSF accumulation/pension status, actual yearly CGT, ETF distributions, ASX spread and custody statements remain unverified by this simple executed-trade ledger. A funding label is not proof of SMSF tax treatment or bank segregation.

## Testing / evidence

- Source metadata: engines/research/cycle_funding_provenance.py
- Updated budget reconciliation: engines/research/cycle_real_sale_budget.py
- Optional Streamlit label UI: engines/research/cycle_portfolio_editor.py
- Legacy editor metadata retention: engines/shared/portfolio_transactions.py
- Tests: tests/test_cycle_funding_provenance.py, tests/test_cycle_real_sale_budget.py
- GitHub CI: Research Cycle Trading Streamlit Dashboard and Cycle Trading Buy/Sell Portfolio Integrity workflows.

**Original historical buy/sell rules, Production V5.8.2, Research V5.9, current simplified Streamlit trading decision, live ntfy content and schedule, actual broker orders and all previously saved Google Sheets transactions were NOT changed by this PR.**

## Next milestone before live strategy parity

Review portfolio funding labels together with real broker statements, tax lots, unpaid tax provision, verified cash and true original BTC position. Then run the **same weekly account state machine** for both original historical after-tax replay and user-confirmed portfolio shadow. Only if dated position/cash/CGT transitions agree should replacing the current simplified 2.5%-of-remaining-cash live rule even be considered.
