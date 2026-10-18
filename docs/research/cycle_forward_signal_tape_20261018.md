# Prospective Cycle Trading signal validation — first real snapshots from 18 October 2026

## What this does

The previous 2017/2021 BTC bottom, 200WMA, macro/halving experiments are retrospective and heavily inspected. Merely computing an indicator from historical data without a future data-vintage ledger **does not prove forward prediction ability**. This new research-only workflow starts a genuine prospective market-level daily record, with **no optimisation, live strategy change or new notification**.

Workflow: `.github/workflows/research_forward_cycle_tape.yml`. Every day at 12:25 UTC (= 22:25 Queensland), plus optional one-off manual dispatch, read the already available BTC USD research provider exports and query verified public Blockchain.com chart close and Frankfurter AUD FX. Verify the same recent overlapping provider prices via `merge_verified_cycle_prices` as the Streamlit app; exclude current unfinished UTC date; require exactly the immediately preceding completed UTC day's close for a genuine forward snapshot, corrupt provider overlap, missing dated FX or unknown halving-block event. Do not backfill an earlier missed day, change an existing row or silently overwrite a revised provider price.

Only record **market-level** `calculate_allocation_signal(market,buy_style="adaptive_recovery")` with its true denominators:
- BUY WATCH percentage of **remaining available personal AUD cash if verified in app**;
- SELL WATCH percentage of **currently held personal crypto-related assets if verified in app**;
- HOLD when no market-level BUY/SELL condition is present.

This standalone tape has **NO private cash or portfolio data**, no IBIT executable AUD quote, no SMSF lots and **NO broker orders**. It does not run `make_current_decision` or claim that a personal user would have received an executable BUY or SELL; that actual decision also depends on verified portfolio records, quote, broker cash, cool-down and data safety. Market-level model differs materially from the original historical staged SELL/BTC-original-denominator and weekly full recovery-BUY backtest. The tape captures the **actual current research market-level** signals, clearly versioned as a different model. No fresh tuning and no retroactive 2025 sales.

File `data/research_forward_validation/cycle_market_signals.csv` is created on the first successful scheduled capture. Each daily row freezes:
- observation-date BTC/USD provider close, prior completed close, 200 **WEEK** moving average, prior BTC/AUD FX date/value and provider crosscheck deviation;
- latest verified halving date, halving-day age, original Cycle market BUY WATCH / SELL WATCH / HOLD and percentage denominators;
- strictly prior 90-day drawdown and 50DMA trend context, lagged realised 30-day volatility, model source-code SHA256;
- an onchain point-in-time provenance marker `NOT_VERIFIED_NOT_INCLUDED` rather than pretend archived October-2026 exported MVRV/NUPL/SOPR are historical live values.

Every row has an ordered SHA256 hash chain. Duplicate observation dates never overwrite an earlier row; earlier missing dates cannot be backfilled to masquerade as historical forward evidence. If the public BTC source is late by 2+ calendar days, the workflow explicitly logs **SKIPPED: source close not yesterday** and writes no row; this planned data-publication delay is not treated as a CI failure or extra ntfy. Missing/unverified FX, confirmed halving, corrupted source overlap or other unexpected data failures still **fail closed**, leaving a visible GitHub Actions failure instead of recording a misleading signal.

Once the 7-, 30-, or 90-calendar-day observation after a frozen signal is **independently recorded in a later run**, `data/research_forward_validation/cycle_signal_outcomes.csv` records future BTC/USD price change, signed directional context for BUY/SELL, best/worst subsequent daily-close movement. It insists on every intermediate day's independently saved close, no interpolation/backfill, no newly fetched historical price used to rewrite outcomes, and a second hash chain linking original signal/future rows. HOLD signed return is intentionally absent. The metrics are observational, NOT actual net portfolio returns and do not imply market alpha, actual ASX ETF execution, or profit-after-tax.

The action deliberately calls no portfolio store, sends **no ntfy message** or other user notification, does not change existing daily Cycle Trading ntfy, Production V5.8.2, Research V5.9, Streamlit, My Portfolio, Google Sheets or brokerage trades. It may make one narrow GitHub commit when there is a newly captured verified date or newly matured forward outcome. You can audit all source rows, fingerprints, GitHub commit timestamps and exact horizon denominators in the repo.

## Data and limitations

- An observation date T in Streamlit's current market adapter uses T-1 for the strict WMA decision, and T's completed price as a reference *mark*, not an actual same-day executable trade. The tape stores both dates explicitly.
- Fresh 2026 forward samples will accumulate slowly. A seven-day outcome cannot exist before seven separately captured later BTC daily closes; 90-day score requires >=90 successful daily records.
- Onchain MVRV/NUPL/SOPR CSV history available today is NOT authenticated contemporaneous vintages and is deliberately excluded. Future independent verified provider snapshots could be added under a new model schema, never retroactively.
- This does not yet assess aftertax AUD returns, 20% future-low-buying-error or tradeable IBIT prices. Those require verified timestamped broker data and user portfolio data. No such data will be added to this public tape.
- GitHub Actions scheduled jobs are subject to service delays / outages; a missing day is not filled with hindsight data. If the repository token lacks write permissions or BTC/FX source fails, the run visibly fails, no false success.
- The model and data are public-market research only. Do not infer win rates from the first few days of scores or from repeated overlapping 7/30/90 horizons.

## Running and tests

`python -m unittest discover -s tests -p 'test_cycle_forward_signal_tape.py' -v` is fully mocked and network-free. Existing market-allocation and provider-crosscheck tests also run. A manual workflow dispatch on **main** may be used to capture the first genuine BTC daily-close observation. There is no requirement for the user to input any holdings or open Streamlit.

Operational commitment: initially **one daily GitHub research capture** only, **zero additional ntfy notices**.


## Operational evidence and freshness correction (18 October 2026)

The first post-merge GitHub Actions execution **did actually write one row**, committed in GitHub as `24715ed176eeb706727cf8c4dd40122d367cd6ac` under `data/research_forward_validation/cycle_market_signals.csv`. It captured the **15 October 2026** BTC USD reference close **81,566.64** at **18 October 2026 07:49:45 UTC**, which is **3 calendar days after the labelled observation**. The 200WMA was USD 66,908.60675; frozen market-level signal was **HOLD, 0% BUY, 0% SELL**. This row is **genuine recorded data** but **not a genuine prospectively timed 15 October decision** because it was collected three days late.

**Never erase or rewrite that existing row**: its hash chain and immutable captured-at date are important evidence. From the freshness quality-control change forward:
- A NEW research record can be written only if the public BTC source provides the **previous UTC calendar day's fully completed close**. Older data is logged as a named skip, with no new record or GitHub commit.
- The 15 October legacy row is deliberately excluded from 7/30/90-day forward signal scoring. A future outcome may be scored only if the base row **and EVERY subsequent daily observation** were each genuinely captured no more than a day after their labelled UTC daily close.
- This does NOT modify the less-strict max-three-day live Streamlit freshness logic, allocation percentages, prices, portfolio or user-facing ntfy workflow. The research recorder is held to a separate, stricter quality standard.
- The extra unit tests prove late source rejection, skip-without-write behavior and frozen existing historical record preservation. If Blockchain.com's public daily chart remains consistently 2–3 days delayed, this recorder will generate **no new scoring observations** until freshness improves. That is preferable to claiming invalid 'forward' success; if necessary, next investigate a genuinely timely, independently checked public price feed **without** silently switching the trading model's source.
