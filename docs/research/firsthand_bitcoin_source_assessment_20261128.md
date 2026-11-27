# Firsthand Bitcoin source assessment

Date: 2026-11-28  
Scope: research-only alternative candidate while Aethereal's Bitcoin Network Daily source is unavailable.

## Catalogue and access

The public catalogue at https://firsthandbitcoin.com/data/api/series.json is accessible without API key/signup. It lists series and JSON/CSV URLs, updates several times/day, and requires attribution **Data: Firsthand Bitcoin** linked to the provider's data page wherever data is shown. Provider terms caution that data may be delayed, incomplete, or incorrect and prohibit republishing/reselling pricing or profitability data as one's own. Keep attribution and check terms before public distribution.

Selected datasets were captured from a GitHub Actions runner, not committed as raw files. Point-in-time validation observed:
- BTC price: 5,079 rows, 2013-01-01 to 2026-11-27
- Fees (raw series): 5,075 rows, 2013-01-01 to 2026-11-26
- Miner revenue: 5,079 rows, 2013-01-01 to 2026-11-27
- tx7: 5,066 rows, 2013-01-07 to 2026-11-27
- fees7 and revenue components were captured and checked as part of follow-up validation
- Date integrity checks passed for all selected series (valid dates, no duplicates, sorted)

## Matched-date quantitative results

Comparison is descriptive over exact overlapping daily dates. Median absolute percentage error (median APE) excludes zero-valued reference observations. Results below are from the existing Coin Metrics Community and Aethereal repository snapshots; source definitions/day boundaries may differ.

| Firsthand series | Reference | Matched days | Median APE | Correlation |
|---|---|---:|---:|---:|
| BTC price | Aethereal price | 5,075 | 0.31% | 0.99976 |
| BTC price | Coin Metrics PriceUSD | 5,078 | 1.24% | 0.99971 |
| BTC fees | Coin Metrics FeeTotNtv | 5,075 | 1.14% | 0.99980 |
| BTC fees | Aethereal fees_btc | 5,072 | 0.000078% | ~1.00000 |
| Miner revenue | Aethereal miner revenue | 5,075 | 8.97% | 0.98632 |
| Miner revenue | Coin Metrics derived revenue | 5,078 | 7.66% | 0.98700 |

Coin Metrics derived total revenue is `IssTotUSD + FeeTotNtv × PriceUSD`; it is a constructed comparison, not a provider-published total-revenue field.

## Metric semantics: smoothing and assumptions found

The exact matched-date checks establish:
- Firsthand `fees7` is a trailing 7-calendar-day mean of its daily fees series (correlation 1.0; median APE about 0.0000011%).
- Firsthand `tx7` matches Aethereal's trailing 7-day transaction mean extremely closely (correlation about 1.0; median APE below 0.000001%). It is not raw daily transaction count.
- Firsthand `revFees` is `fees7 × BTC price` (correlation effectively 1; median APE about 0.0000015%). It is not raw daily fee revenue.
- Firsthand total `revenue` is arithmetically consistent with its subsidy + fee-revenue components (median APE below 0.000002%).
- Firsthand `revSubsidy` uses a 144-block/day assumption rather than actual `blocksDay`. Across halving eras, its subsidy BTC/day is fixed at 3,600 (25 BTC reward era), 1,800 (12.5 era), 900 (6.25 era), and 450 (3.125 era). Actual Firsthand `blocksDay` values vary (58–260; median 149), so daily subsidy/revenue estimates can deviate from actual block issuance. Median absolute error against `blocksDay × block reward × price` is about 7.46%.
- Miner-revenue comparisons show sizeable event-day discrepancies, including dates around the 2021 hashrate disruption and the 2024 halving/fee spike. Do not treat Firsthand's miner revenue as actual unsmoothed daily miner revenue.

The near-exact fees parity with Aethereal and tx7 parity with a rolling mean indicate likely shared or derived data lineage for those metrics. Independent provenance has not been established.

## Decision / recommendation

**Do not accept Firsthand Bitcoin as an independent drop-in fallback for raw daily fees, transactions, or actual daily miner revenue.** Its fees7, tx7 and revenue series are explicitly/empirically smoothed or assumption-based, and fees are almost identical to the Aethereal snapshot. This may still be useful for clearly labelled smoothed descriptive/research metrics. BTC price shows high concordance but differing price conventions; no integration or automatic substitution is approved.

Keep Aethereal recovery and independent existing sources intact. No Production, strategy, sizing, dashboard, or notification changes. No raw datasets are committed.