# BTC Cycle Trading forward ASX:IBIT equal-capital benchmark

**Research only — frozen on 19 October 2026, before eligible 20 October Sydney sessions.** No real buy/sell orders, no user holdings, no portfolio modifications, no ntfy, no paid data, no change to Cycle Trading/Production/Research rules.

## Why an additional test is needed

Existing research covers historical bitcoin-close BTC/AUD proxies, including an important exact-live 2.5%-of-REMAINING-cash weekly BUY test. These proxies are not actual ASX:IBIT buy/sell proceeds; ASX:IBIT did not exist during the 2017/2021 cycles. The existing ASX prospective close file was **still absent from main at 19 October, 14:15 Brisbane**, so there is currently no genuine matched ETF performance comparison.

The original frozen BTC Cycle forward tape has three stored HOLD observations, dated 15, 17, 18 October, of which the 15 October observation was captured too late for legitimate prospective grading. These cannot be interpreted as realised AUD gains.

## Frozen comparison, no hindsight funding

Entry/funding date: **20 October 2026, Australia/Sydney**. Initial **A$100,000 hypothetical CASH and zero ASX:IBIT shares per policy**. Any observation before that date is historical context, not an ETF execution. No pre-existing 2025 BTC sale proceeds, hidden BTC inventory, lending, shorting, after-the-fact cash top-up, or asset price proxy.

Predeclare exactly THREE equal-capital paper policies:

- **Existing Cycle market WATCH:** use actual frozen prospective `cycle_market_signals.csv` `BUY WATCH` / `SELL WATCH` / `HOLD` plus unchanged frozen market-level `buy_pct_of_remaining_available_cash` / `sell_pct_of_current_holdings`. Apply a seven-calendar-day combined executed paper BUY/SELL cooldown. BUY percentage of remaining AUD cash; SELL percentage of remaining whole ETF units. This is a paper-funded *market policy*, not Streamlit's individual broker-verified wallet engine.
- **Initial buy-and-hold:** hypothetical buy as many whole units as cash allows at the **first qualifying prospective ASX close** after the fixed date; no later rebalance.
- **20-week fixed AUD DCA:** allocate A$5,000 of original cash at the first available completed indicative ASX session in each of 20 **predeclared ISO calendar weeks**. Missing weeks are never backfilled/caught up. Market appreciation does not change the original cash allocation.

For all three accounts:
- Exactly same indicative **ASX:IBIT AUD closing price** on each observed market session, A$3 brokerage per simulated fill, and an explicitly **assumed 25 basis-point one-side spread** (not measured live). Whole units and exact remaining AUD balances; no negative cash or inventory.
- The ETF's actual fund expenses are already reflected in its market price; never add a second annual management-fee deduction. Do not calculate SMSF tax without actual taxable lots and fund phase.
- A Yahoo indicative **daily closing candle is NOT an executable broker bid/ask**, and was not known in advance at the simulated trade time. All fills are labelled **paper closing-price proxies**, NOT executable/live performance or a historical confirmed trading edge.
- The Cycle market signal can influence a hypothetical ASX trading session ONLY if it was **captured strictly before 10:00 Sydney** on that session date; if earlier capture is too stale (>3 calendar days from the signal observation date), hold. Use the most recent eligible signal only. This removes a common same-close/future-information trap.
- A signal row must itself have a one-day prospective recorded capture, the same frozen model ID **and the exact original Cycle implementation SHA-256 `0143723687ff676300734a4bcc9887cdc095c74b70b958852d9448412b7f08a7`**, a non-executable status, coherent BUY/SELL/HOLD percentages, and ≤1% cross-provider historical price disagreement. A late-captured, version-drifted or >1% divergent frozen row is excluded visibly, never silently repaired. The locked hash is the previously saved real forward Cycle model code fingerprint, not a hash of the benchmarking script.
- If a later pre-open market snapshot has a changed model implementation or an unreliable source, the Cycle paper account must HOLD/decline to act: it must **not** fall back to an older passing BUY/SELL snapshot. A genuinely improved later Cycle model can enter a separately declared new forward cohort after independent approval; never splice versions into the original 20 October benchmark.
- Independently verify the two original SHA256-linked source tapes before comparisons. Never interpolate missing ASX dates, backfill a missed BTC signal, or substitute BTC spot close for unavailable AUD ETF prices.
- Track matched before-tax terminal indicative account marks and maximum observed drawdown only as descriptive paper values. Also report ETF capital exposure as a **percentage of each account's same-session AUD mark**, averaged across genuinely recorded ASX sessions, with terminal exposure. A Cycle strategy sitting in cash must not appear to have a proven skill advantage merely because its drawdown is smaller than a fully invested buy-and-hold account. This is a descriptive exposure diagnostic, **not** risk-adjusted alpha, annualised return or tax-aware profit. **No winning live model is declared, even if 30 sessions are available**, until genuine executable ASX quote/fee/tax verification plus blinded forward evaluation.

## Automation

Pure research module: `engines/research/forward_ibit_matched_benchmark.py`.
Synthetic tests: `tests/test_forward_ibit_matched_benchmark.py`, including no-ASX-data stop, exact time gates, broker-hour embargo, existing 7-day cooldown, full AUD cash accounting, seller original-vs-remaining units, frozen source hashes, price/OHLC tampering, missing FX by omission, portfolio-no-touch and prefix invariance.

The existing `research_forward_cycle_tape.yml` daily GitHub run optionally calculates one JSON report after mandatory source tape validation, without a new scheduled workflow. The scorer runs read-only on each schedule and adds `artifacts/forward_ibit_matched_benchmark.json` to the same Actions artifact. Missing ASX file simply reports zero eligible ASX sessions; it does **not** fabricate a trading result or block genuine BTC tape recording.

A separate PR/manual test-only workflow validates the source readers, original Cycle allocation and the full three-policy simulator. It adds no ntfy or market-data API calls.

## Promotion constraints

Need (1) verified ASX:IBIT close capture on real completed Sydney sessions, (2) a material forward sample spanning distinct volatility regimes, (3) actual broker bid/ask/execution sensitivity, (4) personal SMSF after-tax lot calculations, (5) the same starting capital and opening BTC/IBIT units as each competitor, and (6) independent future out-of-sample dates. The source benchmark cannot replace the exact portfolio-specific shadow order replay and does not validate historic day500 ORIGINAL-holdings staged SELL experiments.
