# V6.0 104-week ranking — allocation-weighting vs buy-date timing audit

**Run:** 31, workflow run **45981630288** (successful)  
**Artifact:** **15190071431** (downloaded and inspected)  
**Code head:** `394c6f482b805c77a4aa083148aa639a800b5ef0`  
**Research branch / PR:** `research/v60-accumulation-ranking` / draft PR #411

## Cohort design and settings

- 407 overlapping 104-week cohorts: **158 train** (cohort end before 2022-01-01), **146 holdout** (start on/after 2022-01-01), **103 bridge** (excluded).
- Cohorts overlap heavily and are not independent trials.
- Reference setting: A$510,000 capital, 41% initial BTC, 5% annual cash yield, 0% protected cash floor, no cumulative spend cap, 5% original-capital weekly hard buy cap, 0.25% annual BTC drag, 0.3% buy friction, A$3 fixed fee.
- Buy-only; no sell/tax/re-entry timing. Execution is BTC/AUD daily-close proxy, not ASX:IBIT fills.
- BTC source is the dated BlockHorizon export Price column; its price series matches Explore21 exactly from 2013 onward, covering the 2017+ test period.

## Important terminology correction

The old `same_spend_same_count_btc_timing_uplift_pct_hindsight` metric compared actual buy amounts/dates with an equal-gross-amount, uniformly spaced benchmark. It was not a pure date-timing metric.

Two diagnostics now separate:
1. **Allocation-weighting uplift:** same total spend and buy count, but equal gross buy amounts at uniformly spaced dates. For policies buying every week, this isolates the effect of varying the weekly amount (e.g., allocating more below the 200WMA) versus equal weekly purchases. It does not re-simulate cash feasibility.
2. **Buy-date timing-only:** preserves each actual gross purchase amount/count and shifts only dates to uniformly spaced dates. It isolates execution-price timing, but ignores cash feasibility at the shifted dates.

## Result: the current V6.0 policy buys every week

At the reference setting, all 20/25/30 threshold variants, measured 10/15/20, stepped and aggressive 20/25/30 variants buy **104 out of 104 weeks** in every train cohort and every holdout cohort. The pure buy-date timing-only uplift is exactly zero for these policies. The current V6.0 200WMA strategy therefore is **dynamic buy-amount allocation, not buy-date selection**.

The 1.5x aggressive policy is an exception in holdout: 46 of 146 cohorts buy fewer than 104 weeks due to accelerated cash deployment; its pure timing diagnostic is non-zero in those cohorts, but that reflects deployment/cash exhaustion rather than a 200WMA signal selecting dates. Median pure timing uplift is still zero; mean 0.883%, p95 3.869%, maximum 4.538%.

## Matched policy results vs fixed weekly DCA

Median cohort uplift at the reference setting (overlapping cohorts; descriptive):

| Policy | Train median BTC uplift | Train final equity uplift | Holdout median BTC uplift | Holdout final equity uplift | Allocation-weighting uplift vs equal buy amount (train / holdout) |
|---|---:|---:|---:|---:|---:|
| Fixed weekly | 0.00% | 0.00% | 0.00% | 0.00% | 0.00% / 0.00% |
| Baseline 2.5% cash | 6.17% | 6.60% | 8.01% | 8.58% | 18.85% / 22.56% |
| Measured 20/25/30 | 6.17% | 6.60% | 9.74% | 10.02% | 18.85% / 26.58% |
| Measured 10/15/20 | 6.17% | 6.60% | 10.28% | 10.59% | 18.85% / 27.32% |
| Stepped 20/25/30 | 6.17% | 6.60% | 9.85% | 10.26% | 18.85% / 28.19% |
| Aggressive 20/25/30 | 6.17% | 6.60% | 10.14% | 10.45% | 18.85% / 28.95% |
| Aggressive 1.25× 20/25/30 | 9.59% | 9.33% | 14.09% | 13.77% | 22.40% / 34.19% |
| Aggressive 1.5× 20/25/30 | 12.07% | 11.16% | 16.82% | 16.09% | 25.54% / 37.87% |
| Measured 0.5× 20/25/30 | −8.34% | −2.11% | −5.78% | +1.48% | 10.00% / 14.60% |

### What the train/holdout split tells us

- **Train (2017–2021):** 20/25/30 discount tiers are inactive. All base-scale-1 dynamic variants are identical to baseline 2.5% cash allocation. The 6.17% BTC / 6.60% final-equity uplift vs fixed weekly DCA is deployment pacing/amount schedule, not a discount signal.
- **Holdout (2022 onward):** tiers are active but still buy every week; allocation weighting changes purchase sizes. The 20/25/30 policy's allocation-weighting uplift vs equal weekly buys is 26.58%, compared with 27.32% for 10/15/20.
- Paired cohort comparison of measured 10/15/20 vs 20/25/30: median BTC difference **0.00%**, mean +0.714%, p10 0.00%, p90 +1.907%, wins 43.2%. The 10/15/20 threshold set does not show a robust median advantage.
- Stepped vs measured20/25/30: median paired BTC difference 0.00%, mean +1.087%, wins 37.0%. Aggressive20/25/30 vs measured: median 0.00%, mean +2.253%, wins 37.0%.
- The 1.25× and 1.5× scale variants have consistent median paired BTC gains vs scale-1 measured (holdout +4.13% and +6.61%, 100% cohort wins), but spend more cash and leave less reserve. This is **deployment speed**, not timing skill.

## Interpretation / decision

1. **Do not call V6.0 a buy-date timing strategy.** It buys every week and adjusts the amount. It is dynamic allocation.
2. The equal-buy-amount benchmark is a valid allocation-weighting diagnostic for weekly-buy policies, not pure timing. In train it mainly reflects the 2.5% cash-based deployment schedule; holdout includes 200WMA discount weighting.
3. No threshold ladder (10/15/20 vs 20/25/30) has robust holdout superiority; the paired median difference is zero and wins are below 50%.
4. Faster 1.25×/1.5× policies can accumulate more BTC but spend more capital. Keep deployment scale separate from timing/discount signal.
5. A conditional 200WMA/recovery-buy policy already exists in Cycle Trading research (`cycle_forward_cash_dca.py` / `adaptive_recovery`), but historical/live parity is unverified. Next research: replay that exact fixed-cash prospective policy from predeclared calendar entry dates (not cycle bottoms), compare with fixed weekly DCA and the current remaining-cash 2.5%-below-200WMA rule, and report BTC units, AUD VWAP, cash remaining, timing errors and 5% cash yield. This would test genuine buy-date selection without duplicating existing code.

Research only. No Production, dashboard, signals, notifications or live policy changes.
