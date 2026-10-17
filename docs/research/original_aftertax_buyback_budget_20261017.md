# Original BTC Cycle Trading: reconciled sale cash and weekly buyback budget
17 October 2026 | **Research only — the actual trading signal is NOT changed**

## Purpose

This is an engineering bridge from the original historical **% of ORIGINAL BTC sold at day500** / **% of ORIGINAL after-tax sale cash used to buy after the strict 200WMA trigger** backtest, into the single existing Google Sheets *executed* BUY/SELL portfolio. It does NOT invent current 2026 holdings or infer a 2025 sale from 2026 buys.

## What the read-only Streamlit panel does

Open **Cycle Trading — Research → Trading decision → Original backtested strategy — portfolio status (read only)**.

When, and ONLY when, the ledger contains identifiable original BTC or IBIT lots acquired BEFORE the halving's day500, and executed SELLs of those lots during days500–730:

1. Match executed chronological transactions to actual unit inventory **separately for Direct BTC and ASX:IBIT**. A FIFO sale of mixed original/new lots assigns proceeds, seller fees and purchase cost to original lots in proportion to the units sold. Sale proceeds of newly bought post-day500 units are excluded from the original cycle budget.
2. Show **recorded net original-position sale proceeds after selling fees**, estimated unpaid SMSF tax provision, and illustrative remaining net proceeds. The tax provision is a deliberately conservative *positive gain only* 10%/15% FIFO approximation with no capital-loss benefits and NO knowledge of actual accumulation/pension status or ATO end-of-year tax computation. This is NOT verified tax advice or a true SMSF liability.
3. Record **all executed purchases on or after the earliest complete 200WMA-recovery monitoring date (halving day744)** as spending against that one original buyback cash pool, including purchases the ledger cannot identify as cycle-related. This intentionally *understates* remaining cash rather than falsely creating a second budget.
4. During an actual historical phase, show the previous fully observed weekly 200WMA adaptive-recovery percentage. Nothing is retroactively executed or dated in the broker or portfolio.
5. **Only after explicit user confirmation** and the manual entry of BOTH an **unpaid tax reserve** AND independently checked **available broker cash**, show a **read-only historical review AUD amount**. The amount is the minimum of (a) that percentage multiplied by original net sale cash after verified tax, (b) remaining budget after all purchases, and (c) the *lower* of broker-verified and dated ledger cash less the unpaid tax provision.
6. Any recorded BUY on the same weekly historical research review date forces that review's proposed amount to **zero** to avoid multiple repeated allocations; later subsequent reviews use previous-day observations only. No preview authorises an executable trade; no live IBIT fill or actual SMSF parcel data has been certified.

**No broker-verified cash entered means zero usable research order size.** Recorded balances never substitute for the entered broker balance.

## Illustrative mechanical example (fabricated, NOT actual portfolio)

An eligible original ASX:IBIT position of 100 units cost A$10,000 + A$20 fee; 50 of those units were sold during the day500–730 window for A$20,000 gross less A$10 sell fee.

| Component | Example A$ |
|---|---:|
| Net proceeds attributable to original units | 19,990.00 |
| FIFO acquisition basis of sold units | 5,010.00 |
| Illustrative long-hold positive gain | 14,980.00 |
| Illustrative 10% accumulation-phase CGT provision | 1,498.00 |
| Original net after-tax BUY budget (if user verifies) | 18,492.00 |
| Other later BUYs + fees, conservatively debited | 1,003.00 |
| Original budget remaining before cash cap | 17,489.00 |
| One historical 2.5% recovery tranche at same date | 462.30 |

An actual broker cash confirmation of only A$1,600 **before** A$1,498 unpaid tax would cap that illustration to **A$102**, NOT A$462.30. Any recorded trade on that same review date would block a second preview.

## Limitations and safety

- **Real 2026 IBIT/BTC purchases cannot generate SELL cash for a day500 event that occurred on 2 September 2025.** Such portfolios correctly show original proceeds **A$0**, and the historical BUY cash programme cannot be applied retroactively.
- No past ETF adjusted cost base, corporate action, distribution tax, real tax payments, CGT-discount eligibility or pension status can be verified from the basic Google Sheets ledger. The user must reconcile these outside the Research model.
- The ledger has no Buyback-versus-Other investment funding labels. Conservatively counting all purchases can hide valid cash, but prevents false multiple deployment; this is safer until a verified source-of-funds field is added with user consent.
- A dated BTC daily close may be older than the latest executed portfolio trade. Future-dated rows relative to that close are excluded from the as-of view, with a visible warning. Not every Friday/holiday has a broker market open for IBIT and the historical % alone is never an executable ASX price.
- This is **not** the 2017/2021 backtest engine. The original historical SELL and recovery BUY rules are preserved in shared_cycle_policy.py, and the chronological historical wallet is independently verified in PR #119.
- Existing public Streamlit BUY/HOLD/SELL amounts (2.5% cash / remaining holdings) and once-daily ntfy are STILL SIMPLIFIED and **NOT certified identical** to the successful historical day500→200WMA after-tax replay. Do not transfer historical ROI onto those notifications.

## Files and validations

- Engine: engines/research/cycle_real_sale_budget.py
- UI: engines/research/cycle_trading_app.py
- Tests: tests/test_cycle_real_sale_budget.py
- GitHub CI: .github/workflows/research_cycle_trading_dashboard.yml plus normal Cycle trading, portfolio integrity, IBIT quote & ntfy safety workflows.
- No modification to the Google Sheets portfolio data, real trades, Production V5.8.2 / Research V5.9 decision logic, or daily ntfy schedule.

### Next phase

Establish independently reconciled account tax lots, broker cash and provenance of BUYs specifically financed by original BTC sales. Then use the same persistent weekly wallet transition in both the historical replay and the portfolio-aware preview, with broker verification and explicit user consent **before replacing** the daily 2.5% live Research rule.
