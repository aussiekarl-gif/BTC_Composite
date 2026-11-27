# Explore21 vs Bitview: Realized Price, Supply in Profit, Hashrate — 27 Nov 2026

## Scope and alignment
Research-only matched-date diagnostic from the raw PR #410 artifact. Explore21 daily CSV dates were joined to Bitview day1 arrays mapped from 2009-01-01. Metric definitions and smoothing differ; comparisons are not approvals.

## Realized Price
Explore21 `bitcoin-realized-price.csv`: 5,580 daily observations, 2011-08-18 to 2026-11-26. Bitview global `realized_price`: USD per BTC, day1 series 6,540 slots, 8 nulls. Compare absolute percentage error (APE) on matched non-null dates.

| Period | n | Mean APE | Median APE | P95 APE | Max APE |
|---|---:|---:|---:|---:|---:|
| Full overlap | 5,580 | 15.850% | 0.135% | 92.614% | 6,672.659% |
| 2013 onward | 5,078 | 0.563% | 0.119% | 2.050% | 26.736% |
| 2017 onward | 3,617 | 0.163% | 0.123% | 0.510% | 2.857% |
| 2020 onward | 2,522 | 0.126% | 0.106% | 0.300% | 0.997% |

The huge full-history mean is dominated by the earliest dates (2011), when Explore21's realized price is near cents while Bitview is around USD 6.8. Do not interpret as a date shift. From 2017, typical agreement is very close (median 0.123%, p95 0.510%). Investigate early history / cost-basis provenance. Both sources may share external price assumptions or comparable UTXO methodologies.

## Supply in Profit
Explore21 `bitcoin-percent-supply-in-profit.csv` and Bitview `supply_in_profit_share` are percentage units. Absolute difference reported in percentage points (pp).

| Period | n | Mean abs difference | Median | P95 | Max |
|---|---:|---:|---:|---:|---:|
| Full overlap | 5,580 | 2.165 pp | 0.861 pp | 11.967 pp | 38.037 pp |
| 2013 onward | 5,078 | 0.959 pp | 0.769 pp | 2.452 pp | 15.423 pp |
| 2017 onward | 3,617 | 0.860 pp | 0.705 pp | 2.112 pp | 7.263 pp |
| 2020 onward | 2,522 | 0.759 pp | 0.627 pp | 1.891 pp | 4.608 pp |

Largest differences are early-history and one 2015 observation. Even after 2020 the p95 difference is about 1.89 percentage points. Definitions, price source, and supply handling require further review before use.

## Hashrate
Explore21 `bitcoin-hashrate.csv` is explicitly a **7-day average**. Bitview's `hashrate` metadata describes a trailing-24-hour block/difficulty-derived estimate, sampled on day1. This is not a like-for-like smoothing comparison.

Matched overlap: 6,526 dates, 2009-01-14 to 2026-11-26. Bitview / Explore21 ratio:
- Median ratio: 1.018 overall; from 2017: 1.012; from 2020: 1.009.
- Median absolute percentage difference: 5.59% overall; from 2017: 5.34%; from 2020: 5.23%.
- P95 absolute percentage difference: 17.00% overall; from 2017: 16.67%; from 2020: 16.35%.
- Maximum difference 47.50% overall, likely driven by differing averaging windows / early low-network conditions.

The close median level agreement is promising, but variability is consistent with different averaging windows. For any future validation, compare Bitview with a similarly smoothed 7-day series or apply identical windows; do not normalize or adjust raw values silently.

## Candidate decisions
- **Realized Price:** strong typical agreement from 2017, candidate corroboration only; investigate earliest history and residual spikes.
- **Supply in Profit:** reasonable but not exact; compare definitions and inspect discrepancy dates. Not approved.
- **Hashrate:** level agreement is close, but smoothing mismatch makes this a methodological diagnostic only. Not approved.
- No metric is approved for production/model inputs. No date shifting or silent corrections. Keep raw snapshots and provenance.

## Outlier-date inspection (follow-up)

- Supply-in-profit largest post-2013 differences: 2015-08-24 (15.42 pp), 2015-08-18 (9.40 pp), 2017-03-10 (7.26 pp), 2013-01-14 (7.10 pp), 2015-09-05 (6.77 pp). The differences cluster around volatile early price history and cycle-transition periods; source-specific price and supply/UTXO methodology remain candidate causes, not established explanations.
- Realized-price largest post-2013 relative differences cluster on 2013-01-01 through 2013-01-10, with APE about 26.7% and absolute difference near USD 1.57. That sustained early-period offset suggests upstream price/cost-basis methodology differences rather than a one-day alignment issue. Calendar mapping has already been verified; no shift applied.
- Follow-up: capture and compare source spot-price inputs on discrepancy dates where possible, and document metric formula/version histories. Keep candidate metrics unapproved.

## Hashrate apples-to-apples smoothing follow-up

Bitview's day1 value is a trailing-24-hour estimate; Explore21 publishes a trailing 7-day average. I calculated a 7-observation rolling mean of Bitview day1 estimates (calendar daily points) and compared this with Explore21's 7-day average. This is a diagnostic smoothing operation only, not a model input.

| Period | Matched n | Median ratio (smoothed Bitview / E21) | Median abs % diff | P95 abs % diff | Max |
|---|---:|---:|---:|---:|---:|
| 2017 onward | 3,617 | 1.00636 | 0.636% | 1.177% | 2.908% |
| 2020 onward | 2,522 | 1.00640 | 0.640% | 1.188% | 2.908% |

This materially reduces disagreement versus the unsmoothed series (median APE ~5.23%, p95 ~16.35% since 2020). The remaining ~0.64% median level offset may be methodology/version differences; candidate cross-check only.

## Realized-price early-history detail

The first 10 days of January 2013 show a persistent offset: Explore21 realized price ~USD 5.88–5.95 while Bitview ~USD 7.45–7.50; Explore21 BTC daily close ~USD 13.1–13.6. A sustained multi-day offset is not a date-alignment issue. It likely reflects differing early price/cost-basis inputs or methodology, but exact cause is unconfirmed. No shifting/correction applied.
