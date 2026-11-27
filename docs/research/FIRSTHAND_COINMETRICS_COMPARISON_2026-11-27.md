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


## Exact V6.0 weekly threshold sensitivity — 27 Nov 2026

- Added `compare_200wma_distance` to the cross-source diagnostic and corrected it to call the same `weekly_prior_200wma_signals` function used by V6.0. This uses each completed Sunday close divided by the mean of the previous 200 completed Sunday closes; the signal Sunday is excluded.
- Workflow run **45969244125** passed; artifact **15183528981** downloaded and inspected. Comparison covers 517 matched weekly signals from 2017-01-01 to 2026-11-22.
- Absolute difference in discount-to-200WMA: mean **0.093 percentage points**, median **0.000 pp**, p95 **0.570 pp**, max **5.221 pp**.
- Threshold classification disagreements:
  - 5% below: 2 weeks (0.387%)
  - 10% below: 1 week (0.193%)
  - 15% below: 2 weeks (0.387%)
  - 20%, 25% and 30% below: **zero disagreements** across all 517 weeks.
- This is much more relevant than the earlier daily 1,400-day approximation; use the exact weekly result above. It indicates that, despite historical daily spot-price outliers, the weekly V6.0 20/25/30% discount-tier classifications agree on this sample.
- Important limitation: this is still a signal-classification comparison, **not a portfolio backtest**. It does not quantify the effect of provider-specific next-Monday execution prices on BTC accumulated or terminal AUD equity. That is the next required test before deciding whether Firsthand spot prices are acceptable for research execution modelling.
- Latest branch head after the correction: `ba460760ade389f7b8bab4c00dac57e3a70d9d97`. Regression run **45969036789** passed (including the regression test job); V5.9 Research Risk Validation **45969036778** passed; Firsthand raw diagnostic **45969036779** passed. Public-data smoke's Aethereal fetch step failed as already known; it is not evidence of Firsthand failure.


## Matched V6.0 portfolio price-source sensitivity — 27 Nov 2026

- Added a separate research-only replay comparing Firsthand BTC daily prices with Coin Metrics Community PriceUSD. The only changed input is BTC/USD price source. Both use identical Frankfurter USD/AUD FX, the exact V6.0 prior-200-Sunday-close signal, next-Monday BTC/AUD spot proxy, A$510,000 capital, 41% initial BTC allocation, 0% and 5% gross cash-yield scenarios, 0% and 20% initial-cash floors, 5% original-capital weekly cap, 0.25% annual BTC drag, 0.3% buy friction and A$3 fee.
- Workflow run **45970024219** passed; artifact **15184761303** downloaded and inspected. It contains 414 matched overlapping 104-week cohorts for each policy/floor/yield combination. These cohorts overlap and are not independent.
- For the measured 20/25/30% policy, 5% cash yield and no cash floor: median final-equity difference (Firsthand vs Coin Metrics) **+0.009%**, mean **+0.027%**, p95 absolute difference **6.98%**, maximum absolute difference **11.64%**. Median BTC-held difference **+0.162%**, p95 absolute difference **3.61%**, maximum **7.51%**. Buy counts matched in the median cohort (median difference zero).
- With a 20% initial-cash floor and 5% yield, measured-policy median equity difference was +0.013%; p95 absolute difference 6.59%; maximum 11.02%. Zero-yield stress produced a similarly small median and a maximum absolute difference 11.64%.
- The strategy-era daily price comparison (2017-01-01 onward) shows why the average is incomplete: Firsthand vs Coin Metrics mean APE 1.936%, median 1.139%, p95 6.593%, max 36.521%. On the 517 Sunday signal closes, mean APE 1.665%, median 1.077%, p95 5.450%, max 11.615%. On the 517 next-Monday execution closes, mean APE 1.949%, median 1.217%, p95 6.410%, max 19.746%. Largest Monday discrepancies include 2018-02-05 (Firsthand USD 8,202.06 vs CM USD 6,849.54; 19.75%) and 2021-06-21 (USD 35,592.35 vs USD 31,715.16; 12.23%).
- Worst measured-policy equity cohort at 5% yield/no floor: 2019-07-01 to 2021-06-21, Firsthand final equity 11.64% higher relative to the Coin Metrics replay. Another extreme cohort was 2018-02-05 to 2020-01-27, where Firsthand final equity was about 10.65% lower. Differences reflect provider-specific execution prices as well as signal inputs; they are not caused by materially different 20/25/30% weekly tier classifications.
- **Interpretation:** the user's intuition is broadly supported for the median outcome: average/typical differences do not materially change most 104-week results, and exact V6.0 20/25/30% weekly signal tiers matched on all 517 weeks. But tail cohort outcomes can differ by roughly 10–12%, so the Firsthand spot-price history is not safe to substitute wholesale. Keep it as a research cross-check only; Coin Metrics remains the comparison reference pending explanation/correction from Firsthand.
- This is a BTC/AUD spot proxy, not ASX:IBIT execution; no IBIT premium/discount, tax, or actual cash-flow effects. No Production or live signals changed.
- Latest code head at this replay: `bda2c0c85b910e2d12391957415eddaa20205b00`; workflow run **45970024219** succeeded.


## Price provenance and date-alignment investigation — 27 Nov 2026

- Firsthand's public Bitcoin price page describes the series as the "daily closing price" in USD, but the page and API catalogue do not specify the exchange/venue, aggregation method, exact UTC cut-off, or whether historical observations are revised. The API catalogue states that answers update a few times a day. This is insufficient provenance for an execution-price input.
- The API series payload identifies its source as "Firsthand Bitcoin", contains daily date/value pairs, and reports generation time and coverage. It does not expose an underlying venue/source field for the BTC price.
- The raw diagnostic snapshot generated at 2026-11-27T08:29:14Z contains 5,079 points from 2013-01-01 to 2026-11-27. Notably, 2026-11-25 and 2026-11-26 both show USD 59,171.86 in that snapshot. This may be a stale/unchanged value, not evidence of two genuine equal daily closes; we need the provider's update/finality convention.
- Added a date-lag sensitivity diagnostic to the cross-source validator. It compares Firsthand against Coin Metrics and Explore21 Bitstamp with offsets from -2 to +2 days, reporting mean/median/p95/max APE at each offset. Positive offset compares Firsthand date D with the comparator date D+offset. This is diagnostic only; no automatic date shifting or data repair is allowed.
- New cross-source workflow run 45970588864 and matched portfolio workflow run 45970588827 were queued on commit 5a045ba0c6a06332b6418cffac6e022eca1e38be; results pending at this checkpoint.
- Provider contact page publishes a direct email address for the person running Firsthand. We have not contacted them. Key questions for a provider response: underlying BTC/USD venue(s); exact daily UTC boundary/time; close/last/average/VWAP definition; whether historical data is backfilled or revised; and explanation of the 2017–2021 and 2020-03-12 outliers.
- Until these are answered and the lag diagnostic is reviewed, Firsthand spot prices remain research-only and unapproved for model inputs.


### Date-lag diagnostic results — completed 27 Nov 2026

- Workflow run **45970691684** passed; artifact **15184802112** downloaded and inspected. Date offsets tested -2 to +2 days, without altering the source series.
- Best mean alignment is a comparator offset of -1 day (Firsthand date D compared with Coin Metrics/Bitstamp date D-1). On 3,617 strategy-era observations:
  - Coin Metrics mean APE improves from 1.936% to 1.591%; median 1.139% to 0.886%; p95 6.593% to 5.634%. Maximum falls from 36.52% to 24.81%.
  - Explore21 Bitstamp mean APE improves from 1.954% to 1.573%; median 1.141% to 0.852%; p95 6.695% to 5.616%. Maximum falls from 39.84% to 27.84%.
- This indicates that a one-day date-label/close-time mismatch may explain part of the price differences. It does not explain the major outliers. At offset -1, the largest Coin Metrics discrepancy is Firsthand 2020-03-13 USD 6,189.76 vs Coin Metrics 2020-03-12 USD 4,959.31 (24.81%); Bitstamp 2020-03-12 close USD 4,841.67 (27.84%). Next largest include Firsthand 2018-02-06 USD 8,212.81 vs Coin Metrics 2018-02-05 USD 6,849.54 (19.90%).
- The same-date 2020-03-12 Firsthand value was USD 6,770.48 vs Coin Metrics USD 4,959.31 (36.52%) and Bitstamp USD 4,841.67 (39.84%). A one-day alignment improves but does not remove the crash-day anomaly.
- Interpretation: date convention mismatch is plausible, but provider close methodology and source venue remain undisclosed. Do not relabel or shift Firsthand data to force a match; obtain the exact UTC boundary and underlying source from Firsthand first.
- Follow-up matched V6.0 price-source replay run **45970691675** passed. Research DCA regression run **45970639038** passed. The lag diagnostic is comparison-only and does not change any strategy input.


### Raw Firsthand price-series plateau finding — 27 Nov 2026

- Latest raw diagnostic run **45970824915** passed; artifact **15185031194** downloaded and inspected. The BTC price series payload was generated **2026-11-27T08:28:00.683Z**, with 5,079 daily observations.
- Found **33 consecutive dates (2025-07-29 through 2025-08-30 inclusive)** with the exact same BTC price **USD 116,666.67**. This is a serious data-quality defect/stale-value indicator; it is not credible as a market-price series over a month-long interval.
- Additional consecutive exact-repeat pairs exist elsewhere, including **2026-11-25 and 2026-11-26 at USD 59,171.86** in this snapshot. Some one-day repeated closes may be legitimate; the 33-day plateau is not.
- This raw observation strengthens the decision: **Firsthand BTC spot price remains rejected for model inputs and research execution-price simulation** until provider explains/corrects the plateau and historical outliers. No automatic date shifting or value repair.
- CI at head **ae9e5de5ed80229f30fef163be96da44c100149b**: cross-source validation **45970824823**, API diagnostic **45970824915**, V6.0 price-source sensitivity **45970825031**, V5.9 risk validation **45970824836**, and Research DCA regression **45970824825** all passed. PR #409 remains open/draft; no production, dashboard, live signal, or notification changes.
- Next: retain Firsthand 200WMA as cross-check only; seek exact price venue/time-boundary/finality and explanation for plateau and outliers. No provider contact sent.
