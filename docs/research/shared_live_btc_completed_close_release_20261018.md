# BTC Cycle Trading — completed UTC close correctness release

**Scope: shared market-data date correction only. No change in BUY or SELL strategy, prices as broker orders, personal portfolio, Production, one daily notification cadence or ASX:IBIT positions.**

## Evidence

Research PR #157 independently established, across 41 matched price dates, that Blockchain.com chart points stamped UTC midnight of day D correspond to the BTC close of calendar day D-1. Without date alignment, archived-source crosscheck showed up to 6.29465% apparent discrepancy; corrected alignment matched archive and Kraken within ~0.053% maximum in the first overlap, and <=0.023% for newer public data.

## Code changes

One common live source module, engines/research/cycle_live_completed_utc_prices.py, is imported in both Cycle Trading Streamlit and daily ntfy. It dates Blockchain chart end-timestamp D to previous completed UTC date D-1 on an isolated copy, validates >=3 same-day Kraken completed closes from last 7 days with maximum <=1% disagreement, and may bridge only <=3 consecutive missing days with independently finished Kraken OHLC. Archived BlockHorizon dates and values are preserved. All dates through YESTERDAY's completed UTC close are required.

Never derive a signal from unfinished today candle, stale providers, uncertain halving dates, stale AUD FX, missing data or mismatched prices. The existing BUY allocation stays 2.5% of actual remaining cash below strictly prior200WMA, and the existing halving-gated SELL allocations stay unchanged. No weekend ASX fill or extra ntfy is invented.

The previously independent research-only forward signal recorder now uses the exact same newly verified completed source series for NEW observations; old append-only prospective signal rows retain original dates and content, and old provider labels remain evidence of old assumptions. No retrospective 2017/2021 ASX:IBIT quotes are inferred.

## Live provider acceptance — verified 18 Oct 2026 12:42 UTC

[GitHub Actions #39128372536](https://github.com/aussiekarl-gif/BTC_Composite/actions/runs/39128372536): **73 tests passed**, plus public BTC market HTTP smoke run. BTC close 17 Oct **US$81,382**, strictly prior price **US$81,500.80**, prior 200WMA **US$66,730.18**, source historical overlap max 0.05%, recent Blockchain/Kraken overlap max **0.0181%**, independently completed Kraken additions 15–17 October. Identical original market rule reported **HOLD, BUY 0%, SELL 0%**. No actual broker/ASX quote or portfolio write.

Other targeted workflows on original candidate revision #39128372525, #39128372511, #39128372507, #39128372541 and #39128372523 also passed. Added Streamlit explicit fail-closed gate on missing prior-dated AUD/USD FX after those checks: the safeguard makes market no-trade availability at least as strict as original ntfy. Re-run the current PR before merging.

## Remaining operational checks

The correction may change future observed signal timing because dates now represent the actual completed BTC close. It cannot prove historical alpha or assure profitable future trades. Market WATCH remains illustrative only, not an ASX executable price or a broker order; no weekend carry is enabled.

After merging, verify next scheduled research recording and next Brisbane daily ntfy have a fresh completed UTC date or safe DATA UNAVAILABLE without duplicated ntfy. No retroactive edits to archived hash-chain CSVs, production DCA Today or Google portfolio are permitted. Rollback is a code-only revert of the released pull request; do not silently revert to the old misdated provider.
