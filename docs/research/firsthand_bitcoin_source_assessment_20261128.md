# Firsthand Bitcoin source assessment (initial desk review)

Date: 2026-11-28  
Scope: research-only alternative candidate while Aethereal's Bitcoin Network Daily source is unavailable.

## Verified from the provider's public catalogue

The API catalogue at https://firsthandbitcoin.com/data/api/series.json was accessible on 2026-11-28 through web retrieval. It identifies provider/source metadata, generated timestamp, an attribution record, and a list of series with JSON and CSV URLs. The page documents no API key or signup, updates several times a day, and requires credit text **"Data: Firsthand Bitcoin"** with a link to https://firsthandbitcoin.com/data wherever data appears.

Relevant catalogue entries:
- `fees`: daily fees (BTC/day)
- `fees7`: fees paid to miners (BTC/day; distinct smoothed series)
- `revenue`: miner revenue (USD/day)
- `tx7`: transactions/day
- `hashrate`: daily network hashrate (EH/s)
- `difficulty`: mining difficulty
- `realized`: realised price (USD)
- `mvrv`: MVRV ratio
- `puell`: Puell multiple

The catalogue also exposes many other market, mining, on-chain, ETF, derivatives, macro and fee-estimate series. Do not expand the scope without a research question.

## First-pass relevance to Aethereal

Aethereal's adapter currently requires `fees_btc`, `price_usd`, `miners_revenue_usd`, and `transactions`. Candidate Firsthand matches exist for fee, miner revenue, transaction count and price series. But series labels alone are not proof of identical metric definitions, aggregation windows, timestamps, or price conventions. The catalogue's `fees7` and `tx7` are explicitly different from daily `fees`; do not use smoothed series for daily parity checks.

## What this review does NOT establish

- Individual series data URLs were identified but their raw payloads could not be reliably extracted by this review's web retrieval, so schema, actual first/last observation dates, gaps, and freshness of each series remain unverified.
- No quantitative comparison with Coin Metrics, Explore21, OBM, or Aethereal was completed.
- No source substitution, code integration, or Production change is approved.

## Required validation before integration

1. Retrieve and archive raw JSON/CSV for the shortlisted daily series using a runner that can fetch them directly.
2. Validate schema, date range, timezone/day boundary, numeric units, nulls, duplicate dates, and update freshness.
3. Compare fees BTC/day, miner revenue USD/day, transactions/day and BTC price with existing independent series on exact matched dates. Report sample size, coverage, median absolute percentage error (guard against zero denominators), correlation, and outlier dates; inspect metric definitions before interpreting differences.
4. Determine if daily fees and transactions are unsmoothed. Explicitly avoid `fees7` and `tx7` for daily exact-match comparisons unless an averaging transform is intentionally part of the test.
5. Preserve provider and series-key provenance, raw source snapshots, and mandatory credit. Review terms/attribution requirements before distributing charts or data.
6. Add parser tests, fixture-based regression tests, and stale-source/failure behavior. Only then decide: accept for limited research use, reject, or keep as backup-only.

## Current recommendation

**Catalogue discovery: promising. Data-validation status: pending.** Firsthand is a candidate fallback source, not a validated replacement. Keep Aethereal recovery work and independent existing sources intact. No Production, sizing, dashboard, or notification changes.
