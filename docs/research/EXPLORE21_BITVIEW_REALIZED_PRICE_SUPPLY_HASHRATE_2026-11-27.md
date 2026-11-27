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

## Price-input provenance and interpretation

Official source documentation confirms a material upstream price-history difference:
- Explore21 uses daily BTC/USD closes from Bitstamp's public market data back to Aug 2011; its on-chain metrics are computed from its own Bitcoin Core node.
- Bitview price history: before block 74,641 (Aug 2010), no price; through Jan 5, 2015, an older exchange-price record of undocumented original source (later followed Bitstamp); Jan 5 to block 340,000, Bitfinex minute closes; from block 340,000 (later Jan 2015), price is estimated from transaction-output patterns on-chain rather than an exchange feed.

This provenance difference is a plausible explanation for some historical RP/MVRV and supply-in-profit differences, especially in early dates and after Bitview transitions to its on-chain price estimate. It is not proven as the sole cause of each outlier. To quantify this, the diagnostic now captures Explore21 `bitcoin-price.csv` and discovers Bitview price-series candidates. Compare exact date/series metadata before attributing discrepancies. Source citations: Explore21 FAQ/about; Bitview Terms/Support.

## Additional diagnostic expansion

Raw retrieval now also includes Explore21 Bitcoin price and realized-cap CSVs, and Bitview search queries for global price, realized-cap, and Puell Multiple series. This is for provenance and metric corroboration; no data is transformed into model inputs. Quantitative comparisons await the next successful artifact.

## Quantitative results: price, realized cap and Puell (artifact run 45973887035)

Matched daily comparisons use calendar date (no date shifting), and relative error is Explore21 value denominator; symmetric percentage difference is shown for metric interpretation where helpful.

### Price
| Period | n | Mean APE | Median APE | P95 APE | Max |
|---|---:|---:|---:|---:|---:|
| Full | 5,580 | 0.633% | 0.235% | 1.718% | 75.000% |
| 2013+ | 5,078 | 0.426% | 0.244% | 1.284% | 23.359% |
| 2017+ | 3,617 | 0.436% | 0.249% | 1.309% | 23.359% |
| 2020+ | 2,522 | 0.329% | 0.220% | 0.934% | 12.904% |

Correlation is 0.999986. Median symmetric difference full sample 0.235%, p95 1.713%. High early outliers are expected to be investigated by date/source-regime; broad modern agreement is strong.

### Realized Cap
| Period | n | Mean APE | Median APE | P95 APE | Max |
|---|---:|---:|---:|---:|---:|
| Full | 5,580 | 4.972% | 0.135% | 48.126% | 98.524% |
| 2013+ | 5,078 | 0.511% | 0.119% | 2.013% | 21.061% |
| 2017+ | 3,617 | 0.164% | 0.124% | 0.513% | 2.942% |
| 2020+ | 2,522 | 0.127% | 0.107% | 0.302% | 1.008% |

Correlation 0.9999994; symmetric difference median 0.135%, p95 63.377% (tail dominated by earliest history). Modern agreement is excellent.

### Puell Multiple
| Period | n | Mean APE | Median APE | P95 APE | Max |
|---|---:|---:|---:|---:|---:|
| Full | 5,216 | 1.778% | 1.186% | 5.456% | 41.038% |
| 2013+ | 5,078 | 1.779% | 1.188% | 5.465% | 41.038% |
| 2017+ | 3,617 | 1.739% | 1.193% | 5.188% | 29.136% |
| 2020+ | 2,522 | 1.580% | 1.115% | 4.604% | 29.136% |

Correlation 0.996677; symmetric median difference 1.191%, p95 5.558%. Unlike RP/realized cap, Puell's discrepancy remains consistently around 1.1–1.2% median through modern history, with tails around volatile periods (e.g. 2013 Apr, 2020-03-12, 2017 May). Candidate cross-source corroboration, but definition/window/smoothing and issuance conventions need closer review before acceptance.

### Preliminary research assessment
- BTC price: strong modern corroboration; price-source regimes likely explain outliers.
- Realized Cap: very strong from 2017 onward, matching Realized Price validation.
- Puell Multiple: highly correlated but systematically offset; must investigate precise denominator window, subsidy/issuance treatment, and sample timing before using as a research signal.
- No metric approved as a Production input. Raw source values and comparison tables are diagnostic only.

## Puell methodology investigation follow-up

Explore21's component columns validate its calculation: `issuance_usd / issuance_usd_365d_avg` reproduces `puell_multiple` to floating point tolerance (max absolute residual ~3.76e-7; median relative residual ~2.18e-10). Explore21 says it uses actual daily new coins from its own node (supply change, including unclaimed/burned fractions), valued at that day's close; denominator is the 365-day average of the same daily dollar issuance. Bitview describes a trailing-24h subsidy valuation and trailing-365-day claimed subsidy USD window, sampled at the final block of the daily period; window is based on monotonic block time and block price.

Ratio diagnostics (Bitview / Explore21): median Puell ratio ~1.00509 overall and ~1.00552 since 2020; median BTC-price ratio is near 1 (~0.99983 overall and ~0.99928 since 2020). Puell ratio and price ratio correlation only ~0.39 overall (~0.46 since 2020). After dividing Puell ratio by price ratio, the median residual is ~+0.51% overall, ~+0.55% since 2020. This indicates price-history mismatch alone cannot explain the stable Puell offset; likely differences in issuance window/block count timing and 365-day window conventions remain candidate causes, not proven. Keep Puell cross-source validation as provisional pending method-level test.

Source methodology references: Explore21 Puell chart https://charts.explore21.com/bitcoin-puell-multiple ; Bitview series metadata captured in artifact `bitview/series_info/puell_multiple.json`.


## Stress-date source-price diagnostic (run 19, 27 Nov 2026)

The latest raw artifact (diagnostic run 19; artifact 15187148686) includes Explore21 spot-price CSV and Bitview global price day1 data. Spot-price differences on the same dates are substantial and coincide with several NUPL/MVRV cross-source outliers:

| Date | Explore21 close (USD) | Bitview price (USD) | Bitview vs E21 | E21-derived NUPL | Bitview NUPL | NUPL difference |
|---|---:|---:|---:|---:|---:|---:|
| 2017-05-27 | 2,042.00 | 2,512.04 | +23.02% | — | — | — |
| 2018-02-02 | 8,838.83 | 7,165.13 | -18.94% | — | — | — |
| 2018-11-20 | 4,352.00 | 5,025.57 | +15.48% | -0.108758 | +0.038128 | -0.146886 |
| 2020-03-12 | 4,841.67 | 5,558.99 | +14.82% | -0.164934 | -0.022728 | -0.142206 |

This supports spot-price provenance/valuation as a plausible contributor to MVRV/NUPL stress divergence on 2018-11-20 and 2020-03-12. It does **not** prove causality: MVRV/NUPL also depend on realized-cap/cost-basis and supply/UTXO calculations, and the sources may differ in those methods. Spot-price mismatch is not sufficient explanation for the Jan 2013 realized-price offset: Explore21 and Bitview prices were close on the same dates, while realized price differed by about 26% (Explore21 ~USD 5.88–5.98 vs Bitview ~USD 7.45–7.53). Therefore the early RP discrepancy likely involves cost-basis/UTXO method or source history, but its exact cause remains unresolved.

**Research implication:** use source-price regime differences as a documented confounder when reviewing stress-date MVRV/NUPL divergence. Keep both series unadjusted, calendar-matched and candidate-only; no normalization or Production/model input approval.


## Supply-in-profit outliers vs spot-price divergence (run 19)

Using calendar-matched Explore21 spot close and Bitview price series alongside the supply-in-profit comparison, absolute price error and absolute supply-in-profit gap show only a modest association: Pearson correlation is 0.355 from 2013 (0.351 from 2017; 0.235 from 2020), while Spearman rank correlation is weak (0.097, 0.132, and 0.089 respectively). Therefore spot-price divergence may explain part of some outliers but does not establish a general cause.

Largest post-2013 gaps with price context:

| Date | E21 supply in profit | Bitview | Gap (pp) | E21 close USD | Bitview price USD | Price diff |
|---|---:|---:|---:|---:|---:|---:|
| 2015-08-24 | 36.04% | 51.4625% | 15.4225 | 209.72 | 251.08 | +19.72% |
| 2015-08-18 | 38.64% | 48.0417% | 9.4017 | 224.80 | 251.23 | +11.76% |
| 2017-03-10 | 90.03% | 97.2931% | 7.2631 | 1,116.97 | 1,247.29 | +11.67% |
| 2013-01-14 | 97.67% | 90.5660% | 7.1040 | 14.10 | 13.97 | -0.92% |
| 2015-09-05 | 47.80% | 54.5699% | 6.7699 | 235.60 | 251.26 | +6.65% |
| 2017-05-27 | 92.54% | 98.4366% | 5.8966 | 2,042.00 | 2,512.04 | +23.02% |
| 2013-01-02 | 85.40% | 78.7903% | 6.6097 | 13.09 | 13.02 | -0.53% |
| 2013-01-04 | 87.77% | 81.4346% | 6.3354 | 13.19 | 13.15 | -0.30% |

The largest 2015 and 2017 disagreements coincide with sizable spot-price differences; however, 2013 outliers occur with close spot-price agreement, showing price mismatch is not a universal explanation. Supply-in-profit calculation may differ in price assignment, UTXO cohorts, exclusions, supply accounting, or data provenance; these are hypotheses only. No adjustment or source ranking is recommended. Keep the metric provisional.


## Definition-level alignment: Supply in Profit (source documentation review)

Official definitions indicate that these two series are broadly the same BTC-weighted UTXO concept, rather than output-count profitability:
- Explore21 method v2: sum the BTC amount of unspent coins whose last-move daily close is below the current daily close, divided by all supply; pre-price-history coins (before 18 Aug 2011) have zero cost basis and count as profitable. Explore21 uses daily Bitstamp closes and six-block confirmation buffer.
- Bitview/BRK: all UTXOs; creation/last-move price at or below the sampled spot price; `supply_in_profit_share` is BTC supply in profit divided by total supply for the cohort, as percent. Its day1 uses final-block/day sampling; price history changes source regime and becomes chain-derived after block 340,000.

This resolves one potential comparability concern: both are coin-weighted, all-UTXO supply-profit shares. But several exact convention differences remain: strict < vs <= at break-even, daily-close vs final-block sample, price basis and history, safe-block cutoff vs sample depth, and potential denominator/supply handling. These can affect threshold-edge UTXOs and volatile dates. The modest price-error association with the supply-profit gap is evidence that source price matters sometimes, not proof that it explains the residuals. Metric remains provisional until conventions/data are reconciled and stress-date tests are satisfactory.

Official method references: Explore21 percent-supply-in-profit page https://charts.explore21.com/bitcoin-percent-supply-in-profit and FAQ https://charts.explore21.com/faq; Bitview series metadata captured in raw artifact `bitview/series_info/supply_in_profit_share.json` and Terms https://bitview.space/terms/.


## Direct Coin Metrics NUPL API availability test (27 Nov 2026)

A raw, no-key Community API request for BTC `NUPL` at daily frequency was tested by diagnostic run 23 (code head 7ad93dce9898a1fe9c04841246e22f08bc157b61). The endpoint returned HTTP 403 with the API message: metric `NUPL` at frequency `1d` for asset `btc` is not available with the supplied credentials. The failed response was preserved in the diagnostic report; no NUPL data file was created. Coin Metrics Community does expose MVRV-related inputs used for a derived NUPL, but the direct metric is unavailable on this tested entitlement. Therefore the derived Coin Metrics NUPL would not provide an independent metric input from MVRV; existing independent provider (Bitview) comparison remains the direct cross-check.

Run 23 diagnostic workflow passed and artifact **15187578852** was inspected. The new code keeps this endpoint test visible in future diagnostics so availability changes can be detected, but it is not a dependency and no signal or model input is created. Reference: Coin Metrics Community/API access documentation https://docs.coinmetrics.io/ and https://docs.coinmetrics.io/community-data.


## MVRV Z-Score formula reconstruction follow-up (27 Nov)

Official Explore21 documentation now explicitly states method v1: (Market Cap − Realized Cap) divided by the **expanding sample standard deviation** of daily Market Cap from 18 Aug 2011 through each observation; it starts after 30 days of history. Bitview has no independent matching series.

I reconstructed the formula from Explore21's captured realized-cap CSV (`market_cap_usd`, `realized_cap_usd`) using expanding standard deviation with sample denominator (ddof=1), calendar joined to the published Z-score. Results:

| Period | n | Mean absolute Z difference | Median | P95 | Max |
|---|---:|---:|---:|---:|---:|
| Full overlap | 5,551 | 0.008913 | 0.004492 | 0.032303 | 0.472238 |
| 2013+ | 5,078 | 0.008951 | 0.004411 | 0.034100 | 0.472238 |
| 2017+ | 3,617 | 0.007627 | 0.004607 | 0.029446 | 0.084872 |
| 2020+ | 2,522 | 0.005250 | 0.004306 | 0.017314 | 0.032713 |
| 2024+ | 1,061 | 0.004021 | 0.004508 | 0.007297 | 0.008448 |


The formula reconstruction matches the first published observations to floating-point precision and the latest observation (26 Nov 2026) within ~0.0000004. It is also close in recent history, but notable unexplained divergence remains around the 2013 cycle peak (largest discrepancy 0.472238 on 30 Nov 2013) and around 2017. Example 2013-11-30 reconstructed 7.5503 vs published 7.0781; 2017-12-17 reconstructed 8.2407 vs published 8.3180. This suggests the stated formula is correct but the captured market-cap/realized-cap inputs or historical revisions are not fully aligned with the published Z-score series. The earlier exploratory 2–10-year rolling-window attempts were not the correct documented formula; this expanding-window reconstruction supersedes that interpretation.

**Status:** formula identified and partially reproduced; historical input/version alignment unresolved; no independent cross-source; not approved as signal input. Official formula source: https://charts.explore21.com/bitcoin-mvrv-z-score and method comparison https://charts.explore21.com/mvrv-vs-mvrv-z-score.


## Explore21 Z-Score method changelog

The raw API changelog capture succeeded (HTTP 200) and reports: metric id `bitcoin-mvrv-z-score`, `method_version=1`, first published **2026-07-15**, with no subsequent method-change entries. This does not prove historical data inputs have never been revised, but it means the API changelog does not document a method-version change that explains the residuals. Captured raw JSON and SHA-256 in diagnostic run 27 artifact **15187998679**.

**Remaining question:** the MVRV ratio reconstructed from Explore21 realized-cap CSV (market cap ÷ realized cap) matches its published MVRV series within ~5e-7, so numerator inputs are internally consistent. The Z-Score denominator remains the unexplained part of the historical reconstruction. Do not assume this is an E21 error; it may be a mismatch in our reconstruction/input series or a historical data-version difference not represented in the changelog.
