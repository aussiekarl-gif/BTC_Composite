# Cycle Trading: independently verified broker cash and indicative SMSF tax check

17 October 2026 | Research UI only — PR #128

## What was actually missing

The My Portfolio ledger correctly totals recorded BUY and SELL transactions, so a previously sold BTC/ASX:IBIT position can return **gross net sale proceeds after selling fees** to recorded uninvested AUD cash. But this is **not automatically cash available for a new trade**, because the ledger cannot know what SMSF income/capital gains tax has been assessed or paid, what has been allocated to other liabilities, or the independently available account balance currently displayed at the user's broker. The existing daily Cycle Trading **BUY/HOLD/SELL engine and once-daily ntfy** were left untouched.

PR #128 adds a separate, optional **Broker cash and SMSF tax check — verify before any trade** directly below the main trading decision. This is an additional reconciliation and explanation, **not a new BTC market timing strategy**.

## What the Streamlit check displays

1. **Recorded cash BEFORE unpaid liabilities** from the same live executed trade ledger, with the user warned that this is NOT independently verified free cash.
2. **Indicative FIFO capital-gains tax on recorded past sales**, separately by Australian financial year. The educational scenario assumes an SMSF *accumulation-phase* capital gains tax on each *positive* recorded FIFO parcel gain: **10% after holding longer than 12 months**, otherwise **15%**, including acquisition and sale transaction fees in cost/proceeds. Negative parcel gains are NOT used as confirmed offsets, making this a conservative illustration. Actual ATO liability, pension-phase exemption, tax-loss offsets, fund income, dividends, ETF tax adjustments, future legislation and amounts already paid remain unknown. The displayed sum may include multiple financial years, and **is not the amount of unpaid tax**. No tax was silently deducted from the historical portfolio state.
3. An **optional verified broker check**, where the user manually enters a current **ASX:IBIT quote** and, for an existing BUY signal, independently confirms actual **broker cash available AFTER unpaid taxes and all other reserves**. The safe research budget is the **lesser of broker-confirmed free AUD and recorded uninvested AUD**, and the existing model BUY percentage is applied to that figure. The same whole ETF share rounding and A$3 brokerage assumption apply. This avoids double-deducting estimated capital gains tax from money the broker/free-cash number is already net of.
4. For an existing, current **SELL** decision, use the already calculated whole-unit quantity. With the independently checked IBIT broker quote, show gross AUD, estimated FIFO sale cost base, positive-only CGT scenario and resulting **illustrative net AUD after that tax provision**. No tax is credited for possible losses without a verified offset.
5. **HOLD can never become BUY/SELL** by entering a large cash amount. No price is silently taken from a delayed cached quote for verification. Unconfirmed broker cash/price produces NO verified AUD or units and no saved data.
6. All calculations are read-only, fail closed if the ledger contains invalid cost bases or oversold positions, and check as-of dates so future recorded transactions do not affect earlier snapshots. Actual fills, tax paid and SMSF fund phase still need user/broker/accountant review.

The actual buy/sell model remains free to show its previous **illustrative** daily decision, including default recorded-cash calculations, but the separate panel makes clear why that amount **is not a verified spendable order**. No automatic trades or ntfy messages are sent.

## Mechanical illustrative example — NOT actual user trades

Suppose a fund records 100 ASX:IBIT units purchased on 1 May 2024 for A$10,000 plus A$20 fees, then sells 50 units on 2 September 2025 for A$20,000 less A$10 selling fees.

| Item | Illustrative AUD |
|---|---:|
| Net sale proceeds | 19,990.00 |
| FIFO cost basis for sold 50 units | 5,010.00 |
| Positive long-term capital gain | 14,980.00 |
| 10% illustrative accumulation-phase gain provision | 1,498.00 |

The A$1,498 is **NOT verified currently unpaid tax**. If the broker confirms only **A$20,000 currently free after all outstanding taxes/expenses**, a BUY signal of **2.5% of cash** can be shown as an **A$500 maximum research amount**, not 2.5% of a potentially much larger, unreserved ledger balance. At a separately verified A$30 per IBIT unit, the illustrative whole-unit maximum is **16 units** with A$3 brokerage, leaving any fractional budget unspent. No broker orders or portfolio writes occur.

For a prospective SELL of 10 original units two years later at A$300 per unit, the illustrative pre-tax net proceeds are A$2,997, FIFO acquisition basis A$1,002, positive gain A$1,995, illustrative 10% CGT A$199.50 and net after **hypothetical** provision A$2,797.50. Pension-phase SMSF circumstances or loss offsets could make actual tax differ materially; never equate this figure with available broker proceeds or tax actually paid.

## Audit boundaries

- Tax calculations use **entered** executed-unit quantities, AUD consideration, dates and fees. They are not independently validated brokerage trade confirms, historical ETF split/distribution adjustments, corporate actions or ATO returns.
- Both **ASX:IBIT and Direct BTC** purchases/sales are traced in separate FIFO inventories. Selling one asset does not use another asset's units or basis.
- The model does not know current SMSF pension versus accumulation phase, the timing of cash settlement, broker custody or the actual AUD liquidity that may be earmarked to future expenses; users must confirm their own cash and fund taxation.
- Existing main Streamlit decision, BUY%/SELL% and once-daily ntfy are **not overwritten** by this check, and the UI never writes to the Google Sheets ledger from the confirmation form.
- Previous original 200WMA/day500 retrospective model results are unchanged. They do not make this manual real-account preview historically backtest-validated as an executable investment strategy.

## Test/CI

- Engine: `engines/research/cycle_broker_cash_review.py`
- Unit tests: `tests/test_cycle_broker_cash_review.py` — original FIFO gain/cost/fees, separate direct BTC tax lots, sale-loss non-offset conservatism, past vs future as-of-date, illustrative future sale, independent broker cash cap and quote, whole-unit minimum, HOLD preservation, no order.
- Streamlit: `engines/research/cycle_trading_app.py`
- GitHub Actions: `.github/workflows/research_cycle_trading_dashboard.yml` and existing main Cycle BUY/HOLD/SELL, My Portfolio integrity and ntfy regression checks.

**Research changes only.** Production V5.8.2, Research V5.9, Google Sheets portfolio transactions, ETF quote fetching, current daily allocation calculation and one daily ntfy schedule are unchanged.
