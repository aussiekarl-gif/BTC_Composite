# Firsthand API diagnostic — initial validation

Date: 2026-11-27  
Repository branch: `research/firsthand-api-validation`  
Validated head: `85cdf6340a0b0cbee6a265a0d5f2ba9b11ab91d3`  
GitHub Actions run: `45965988733` (success)  
Artifact: `firsthand-api-raw-diagnostic` (artifact ID `15182219026`, SHA-256 `8407c04504f43e4aeb1104eb828cb85f87cd28d0dc578f63f74bbb6ea2e99860`)

## Scope

The diagnostic successfully fetched the published series catalogue, summary and 19 candidate JSON series. Raw provider responses were retained unchanged in the Actions artifact. This report is a research-only inspection; no values have been normalised, merged into project datasets, or adopted as model inputs.

## Confirmed schema

Series payloads are JSON objects containing provider metadata (`source`, `url`, `license`, `generated`), series metadata (`key`, `label`, `unit`, `from`, `to`, `points`) and a `data` array of [ISO date, numeric value] pairs.

The catalogue explicitly states: “Free to use with attribution and a link to firsthandbitcoin.com/data”.

## Coverage observed in this retrieval

| Series | Unit | First date | Last date | Rows |
|---|---:|---|---|---:|
| BTC price (`btc`) | USD | 2013-01-01 | 2026-11-27 | 5,079 |
| 200-week average (`ma200w`) | USD | 2016-10-31 | 2026-11-27 | 3,680 |
| Daily hashrate (`hashrate`) | EH/s | 2013-03-18 | 2026-11-27 | 4,999 |
| Difficulty (`difficulty`) | provider unit not specified | 2013-01-01 | 2026-11-27 | 5,079 |
| Daily fees (`fees`) | BTC/day | 2013-01-01 | 2026-11-26 | 5,075 |
| Realised price (`realized`) | USD | 2013-01-01 | 2026-11-26 | 5,078 |
| MVRV (`mvrv`) | × | 2013-01-01 | 2026-11-26 | 5,078 |

All inspected date arrays were strictly ascending, with no duplicate dates or null values in the reported rows. Important gaps: daily hashrate omits 2013-03-19, 2013-03-20, 2013-03-26 and 2013-03-28; daily fees omit 2025-11-13 through 2025-11-15. Do not forward-fill these silently.

## Independent calculation checks

### 200-week average

Recomputed a 1,400-calendar-day simple rolling mean from Firsthand's own daily BTC price series. On all 3,680 overlapping dates, Firsthand's `ma200w` matched the independently calculated mean to within approximately 0.0000048% maximum relative difference. This is a strong internal consistency check, not independent source corroboration because both series come from Firsthand.

### Hashrate moving averages

Firsthand's 7-, 30- and 60-day hashrate averages matched rolling calculations from its daily hashrate series to within approximately 0.000005% maximum relative difference on overlapping observations. The 7-day series has an early multi-day gap; preserve missingness.

### Fee moving average

The `fees7` series generally matches a rolling average of daily fees, but there is an apparent transition anomaly on 2025-11-21 (about 3.75% difference under a seven-observation rolling comparison). The daily-fee series also has a three-day gap immediately before this date, and the 7-day series has a longer gap. The averaging window and missing-day treatment must be clarified before using `fees7`.

## Assessment and restrictions

- **Promising candidate:** BTC price, 200-week average, difficulty, realised price, MVRV, hashrate and daily fees are now machine-retrievable from GitHub Actions.
- **Strong internal consistency:** the 200WMA and hashrate smoothing calculations reproduce very closely from the provider's own underlying series.
- **Not yet independently validated:** internal agreement does not prove accuracy against canonical Bitcoin data or existing project sources.
- **Needs follow-up:** explain the missing fee/hashrate dates, fee smoothing anomaly, difficulty unit/scale, realised-price methodology, MVRV methodology and each series' update/finality policy.
- **No integration:** do not change Production or V6.0 model inputs, dashboards or live signal calculations on the strength of this diagnostic alone. Next stage should compare overlapping daily observations against the project's existing independent sources, with source provenance retained and explicit tolerances.

