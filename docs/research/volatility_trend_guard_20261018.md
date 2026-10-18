# BTC 200WMA BUY guard: 30-day realised volatility and 50DMA downtrend (18 October 2026)

**Research-only, predeclared test — no new trade or alert. Do not change Production V5.8.2, Research V5.9, Cycle Streamlit, ntfy, portfolio Google Sheets or actual holdings.**

## Why this is different from earlier unsuccessful models

The previous 10% first-buy frontload and 1%-per-week pre-WMA starter both introduced extra exposure before a confirmed low, and the 50%-reserve until 0.85×200WMA withheld substantial cash until a new *price level*. This test keeps **the exact original first 200WMA gate and weekly eligibility**, but uses real-time volatility and an already familiar falling 50-day price trend to reduce only those weekly purchases associated with unusually violent declines. It is not claimed to identify an exact eventual low.

## Frozen rule

- Initial account: hypothetical **A$400,000 fresh cash** at same history-available halving-relative start day +650 / +750 / +850 / +900. **No earlier BTC lots, fictitious 2025 BTC sales, proceeds or historical personal cash**.
- First eligible signal: prior completed BTC/USD daily close T−1 **strictly below** strictly previous **200 spaced weekly closes**, with gate only eligible after the cash-start. Identical independent original 200WMA engine and dates.
- For each original 7-day BUY review after gate, determine the original fixed-budget BUY percentage **2.5%, 15%, 4.5% or 1% of original AUD cash** from the unchanged recovery policy.
- Compute with no T information: **30 preceding daily BTC log returns**, annualised sample standard deviation ×sqrt(365). **High volatility** if >=80% annualised. Concurrent **falling trend** if T−1 BTC close is BELOW preceding 50-day SMA AND preceding 50-day SMA is below its value exactly 14 days earlier. All 64 prior daily closes required; fail closed otherwise.
- If both high vol AND declining trend hold, multiply the weekly original-budget purchase by **0.5**; if not, use **100% original weekly amount**. Never backfill skipped fractions; gross purchases cannot exceed actual available cash. The next-day execution close is used only for audit fills.
- Compare to original unchanged 200WMA adaptive weekly BUY, currently simplified daily remaining-cash below-200WMA BUY, ordinary fixed 52-week DCA and first-day lump sum. Identical initial cash, FX strictly before the simulated execution close, AUD 3 brokerage and simplified immediate FIFO SMSF CGT upon hypothetical final liquidation.
- Historical 2017/2021 day1150 complete, 2025/26 **right-censored at 5 Oct 2026**. All have been studied; no untouched validation sample.
- Deep-bottom stress (not forecast probabilities): preserve historic prior cash-start and price path through halving day960 for 2017, day900 for 2021; impose artificial 50/70% further BTC declines to day1060 and day1150 terminal at 55%/105% of last original shock-close. Must report number of actually-guarded buys, BTC units, remaining cash, terminal post-liquidation-tax AUD, drawdown and exact first-gate parity.
- Unit tests: signal uses only T−1 and earlier (future repaint invariant), volatility trend actually activates and halves a purchase on known synthetic price path, original independent wallet parity, unchanged original signal and weekly dates, missing daily price and FX fail closed, no-cross no trade.

## Decision before seeing results

Do **not** promote just because a few historical starts improve; 2017 immediate recovery can punish protective sizing and 2021 delayed bottom can reward caution, but two completed cohorts cannot establish a stable future threshold. If volatile downtrends historically improve entry only at the cost of substantial missed post-low accumulation, the experiment should be rejected. Also this rule **cannot solve no-new-200WMA-crossing cash drag**; that is a separate structural policy question.

Real IBIT on ASX cannot be filled at BTC USD daily close on weekends/holidays, tax rates and FX can differ, and this has no independent future holdout.
