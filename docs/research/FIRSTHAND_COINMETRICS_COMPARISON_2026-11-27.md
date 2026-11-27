# Firsthand vs Coin Metrics — first matched-date comparison

Date: 2026-11-27  
Branch: `research/firsthand-api-validation`  
Comparison workflow run: `45967307751` (success)  
Artifact: `firsthand-cross-source-comparison` (ID `15182853419`)

## Method

Fetched Firsthand's public daily series and Coin Metrics Community BTC asset metrics in GitHub Actions. Compared observations on identical UTC calendar dates. Error is absolute percentage difference relative to Coin Metrics. No time-zone/close-hour adjustment has yet been applied. This is a source diagnostic, not an endorsement of either provider.

## Results

| Comparison | Matched observations | Mean APE | Median APE | 95th percentile | Maximum APE |
|---|---:|---:|---:|---:|---:|
| Firsthand BTC price vs Coin Metrics PriceUSD | 5,078 | 2.235% | 1.236% | 7.929% | 92.855% |
| Firsthand BTC price vs Explore21 Bitstamp close | 5,078 | 2.253% | 1.243% | 7.904% | 91.703% |
| Coin Metrics PriceUSD vs Explore21 Bitstamp close | 5,078 | 0.252% | 0.125% | 0.893% | 9.290% |
| Daily fees BTC | 5,075 | 1.570% | 1.141% | 4.023% | 95.380% |
| MVRV | 5,078 | 0.0000013% | 0.0000011% | 0.0000031% | 0.0000048% |
| Realised price vs Coin Metrics PriceUSD / CapMVRVCur | 5,078 | 1.740% | 0.927% | 5.863% | 92.855% |

Recent 90-day mean APE: BTC price 0.818%, daily fees 1.854%, MVRV 0.0000017%, realised-price proxy 0.855%.

## Interpretation

- **MVRV is not an independent cross-check.** Its values are effectively identical to Coin Metrics CapMVRVCur at near floating-point precision. Treat this as evidence of shared upstream data or methodology until proven otherwise.
- **Firsthand's BTC price series has a material data-quality problem, not merely a daily-boundary mismatch.** We added a third source: Explore21's published Bitstamp UTC daily close. Coin Metrics and Explore21 agree closely (mean APE 0.252%, median 0.125%, p95 0.893%). Firsthand differs from both similarly (vs Explore21 mean APE 2.253%, median 1.243%, p95 7.904%). On 2020-03-12, Firsthand is USD 6,770.48 versus Explore21 USD 4,841.67 and Coin Metrics USD 4,959.31. On 2013-04-11, Firsthand is USD 159.88 versus Explore21 USD 83.40 and Coin Metrics USD 82.90. These are not plausibly explained by a small UTC close convention difference. Do not use Firsthand BTC price as a model input unless provider explains and corrects the affected history. Fee outliers include 2014-09-07 (95.38%), 2024-04-19 (34.99%) and 2024-10-17 (22.03%); fee methodology and aggregation remain unresolved.
- **Recent agreement is materially better than full-history agreement**, but a 90-day average does not establish long-term suitability.
- The realised-price comparison is a proxy: Coin Metrics' PriceUSD divided by CapMVRVCur. It assumes compatible supply basis and is not a direct Coin Metrics realised-price observation. Its outliers largely mirror the price comparison.
- Firsthand BTC price has a repeated value of USD 59,171.86 on 25 and 26 Nov 2026 in the inspected snapshot. This requires freshness/market-close explanation before using as a live price source.

## Next validation

The corrected follow-up workflow run `45967697247` passed and its artifact (`15183821578`) was downloaded and inspected. Firsthand 200WMA vs a 1,400-observation rolling simple mean of Coin Metrics PriceUSD: 3,679 overlaps from 2016-10-31 to 2026-11-26; mean APE 0.274%, median 0.224%, p95 0.669%, maximum 1.773%; recent 90-day mean 0.0130%. This is a strong independent consistency result, although it still depends on the Coin Metrics price daily boundary and a matched 1,400-observation SMA.

Then investigate worst price/fee dates against timestamped provider observations and another independent public source. Keep missing dates unfilled. Do not adopt Firsthand as a production or V6.0 input based on these results.


## 200WMA comparison correction

The first version of the cross-source workflow (runs 45967448045 / 45967577757) completed successfully but its JSON artifact did not contain the 200WMA comparison despite fetching the Firsthand series. This was a reporting-code omission, not a data failure. The comparison builder was corrected, and the follow-up run `45967697247` passed with the 200WMA metric present in artifact `15183821578`. Results are recorded above; do not use the earlier runs as evidence for the independent 200WMA calculation.


## Three-way price comparison — 27 Nov 2026

Workflow run `45968107990` passed; artifact `15183034026` was downloaded and inspected. Added Explore21's `bitcoin-price.csv`, which documents Bitstamp last trade of each UTC day.

| Same-date price comparison | Mean APE | Median APE | P95 APE | Maximum APE |
|---|---:|---:|---:|---:|
| Firsthand vs Coin Metrics PriceUSD | 2.235% | 1.236% | 7.929% | 92.855% |
| Firsthand vs Explore21 Bitstamp close | 2.253% | 1.243% | 7.904% | 91.703% |
| Coin Metrics PriceUSD vs Explore21 Bitstamp close | 0.252% | 0.125% | 0.893% | 9.290% |

At the 2020-03-12 outlier, Firsthand is USD 6,770.48; Explore21 Bitstamp close is USD 4,841.67; Coin Metrics is USD 4,959.31. At 2013-04-11, Firsthand is USD 159.88; Explore21 is USD 83.40; Coin Metrics is USD 82.90. Firsthand is the clear outlier on both dates. This materially weakens the case for using its BTC price series. A minor UTC daily-boundary mismatch cannot reasonably explain these differences.

**Decision:** exclude Firsthand BTC price from model-input consideration unless Firsthand explains and corrects the historical observations. Its 200WMA can still be cross-checked as a derived series, but the independently computed Coin Metrics 1,400-day SMA is preferable as the reference. This is still research-only.
