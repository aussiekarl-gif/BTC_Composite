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
| BTC price USD | 5,078 | 2.235% | 1.236% | 7.929% | 92.855% |
| Daily fees BTC | 5,075 | 1.570% | 1.141% | 4.023% | 95.380% |
| MVRV | 5,078 | 0.0000013% | 0.0000011% | 0.0000031% | 0.0000048% |
| Realised price vs Coin Metrics PriceUSD / CapMVRVCur | 5,078 | 1.740% | 0.927% | 5.863% | 92.855% |

Recent 90-day mean APE: BTC price 0.818%, daily fees 1.854%, MVRV 0.0000017%, realised-price proxy 0.855%.

## Interpretation

- **MVRV is not an independent cross-check.** Its values are effectively identical to Coin Metrics CapMVRVCur at near floating-point precision. Treat this as evidence of shared upstream data or methodology until proven otherwise.
- **Price and fee series are broadly close on average but have material historical outliers.** Price outliers include 2013-04-11 (92.86%) and 2020-03-12 (36.52%). Fee outliers include 2014-09-07 (95.38%), 2024-04-19 (34.99%) and 2024-10-17 (22.03%). These need investigation for daily close conventions, historical corrections, aggregation boundaries, or data errors.
- **Recent agreement is materially better than full-history agreement**, but a 90-day average does not establish long-term suitability.
- The realised-price comparison is a proxy: Coin Metrics' PriceUSD divided by CapMVRVCur. It assumes compatible supply basis and is not a direct Coin Metrics realised-price observation. Its outliers largely mirror the price comparison.
- Firsthand BTC price has a repeated value of USD 59,171.86 on 25 and 26 Nov 2026 in the inspected snapshot. This requires freshness/market-close explanation before using as a live price source.

## Next validation

A follow-up workflow now compares Firsthand's 200WMA to a 1,400-calendar-day simple moving average independently calculated from Coin Metrics PriceUSD. Run `45967448045` was in progress when this report was written. After it completes, inspect the artifact and add its results.

Then investigate worst price/fee dates against timestamped provider observations and another independent public source. Keep missing dates unfilled. Do not adopt Firsthand as a production or V6.0 input based on these results.


## 200WMA comparison correction

The first version of the cross-source workflow (runs 45967448045 / 45967577757) completed successfully but its JSON artifact did not contain the 200WMA comparison despite fetching the Firsthand series. This was a reporting-code omission, not a data failure. The comparison builder has now been corrected to compare Firsthand `ma200w` with a 1,400-observation rolling mean of Coin Metrics PriceUSD. A new workflow run is required before reporting any 200WMA result. Do not interpret the earlier workflow success as validation of the independent 200WMA calculation.
