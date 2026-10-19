# BTC Cycle Trading conditional deeper-value weekly BUY sizing study — 20 October 2026

## What changed in our objective

The user confirmed that November 2026 is **NOT a hard deployment deadline**. AUD cash may remain uninvested into 2027 if Bitcoin's verified valuation / risk signals remain unattractive. In particular, DO NOT add a 2027 capital sweep or force purchases on arbitrary dates. The unchanged current live Cycle BUY is **2.5% of remaining available AUD cash**, with a **7-calendar-day executed trade cooldown**, *only when the prior BTC/USD close is strictly below its prior exact 200-week moving average*. These live rules, staged SELLs, actual Streamlit portfolio, Production 5.8.2 and Research 5.9 are not modified.

Earlier exact-live-market weekly-size research showed that a constant 3.5% or 5% amount increased exposure and raised terminal AUD in some retrospectively observed recoveries, but could sharply reduce returns under a deliberately delayed or deeper bear bottom. The question here is: **Does limiting extra spending to significantly cheaper previous BTC prices improve the downside tradeoff?** This is a testable hypothesis, NOT a promise about the next Bitcoin bottom.

## Research-only, preregistered conditional candidates

Code: `engines/research/cycle_conditional_deep_value_buy_audit.py`

Only **prior completed** BTC/USD close over the **prior completed 200-week moving average** chooses a size for an already VALID market BUY WATCH. All fractions apply to REMAINING cash, not initial cash or original holding.

| Study case | If previous BTC / previous 200WMA | Remaining-cash BUY |
|---|---|---:|
| Unchanged exact-current baseline | Below 1.00 | 2.5% |
| Mild conditional size | <=0.90 | 3.0%, otherwise 2.5% |
| Moderate conditional size | <=0.90 | 3.5%, otherwise 2.5% |
| Deep-only size | <=0.80 | 5.0%, otherwise 2.5% |
| Two-tier size | <=0.80 / <=0.90 | 5.0% / 3.5%, otherwise 2.5% |

These are **candidate sensitivities**, not an AI recommendation. They are chosen after earlier historical research, and therefore cannot be independently validated by re-scoring the same 2017/2021 data. No model leader will be promoted by this test.

## Accounting and study design

- **Identical hypothetical fresh A$400,000 AUD cash-only account** at each previously defined halving+650, +750, +850, +900 start date. No backdated 2025 sale proceeds or any personal holdings imported. Track original cash remaining. Never force terminal deployment.
- Use the EXACT unchanged Cycle `calculate_allocation_signal(...,buy_style="adaptive_recovery")` on each date, with previous-day 200WMA gate and one minimum seven-day interval since each account's LAST EXECUTED purchase. No buys if previous close is above/at WMA, however deep the market may drop intraday.
- Price at execution on date T is BTC/USD **T CLOSE**, converted with strictly BEFORE-T USD/AUD historical FX. This is an optimistic research proxy, NOT an actual available mid-session ASX:IBIT bid/ask, and includes weekends. A$3 brokerage per simulated BTC order, FIFO SMSF accumulation-phase hypothetical immediate tax escrow and terminal full liquidation tax, without real fund parcel-specific or annual tax facts. No ETF fee, bid/ask spread, interest on cash or ETF tracking basis verified.
- **2017/2021** historical completed windows run only through halving+1150, and 2025/26 is right-censored at **5 October 2026** like original weekly BUY parity study. Reuse original stress architecture for 2017 +750 and 2021 +650: synthetic extra 50%/70% declines after previously frozen shock dates 960 / 900, bottom at +1060, terminal at +1150 with 55% or 105% of pre-shock price. These are **not probabilities or 2027 forecasts**.
- Quantify historical + stress: comparative terminal hypothetical AFTER FIFO liquidation tax AUD, remaining cash AUD/%, BTC units, average daily invested share of total marked equity, actual purchase count, worst account marked drawdown, and individual dated orders. A candidate with better terminal value because it owns more BTC must not be described as a superior market-timing indicator.
- Regression against original `live_weekly_buy_parity.replay_exact_live_market_buy` requires identical **2.5% reference fills, dates, remaining AUD, BTC and FIFO aftertax value** for the same synthetic data. Missing data, future price contamination, same-day crash signal leaks and invalid/missing prior FX must all fail closed.

## Decision criteria and next evidence

No changes to live BUY allocation unless a variant shows a meaningful improvement that survives realistic ASX:IBIT weekday/trade-time fills, FX/brokerage/spread/ETF tracking, SMSF tax assumptions, additional delayed-bottom/recovery conditions, multiple entry dates, and **genuine future**, version-frozen signals. The 2026/27 forward ASX research benchmark must remain independent and must not be retrospectively re-fitted.

GitHub research PR tests and archived JSON/CSV evidence. No scheduled workflow, new ntfy, Google Sheets/portfolio edits, Production/Research code changes, broker orders or existing immutable provider CSV writes.
