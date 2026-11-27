# Firsthand vs Coin Metrics — V6.0 matched portfolio source sensitivity

**Date:** 27 Nov 2026  
**Branch:** `research/firsthand-api-validation`  
**Workflow:** Firsthand V6.0 price-source portfolio sensitivity, run **45971267940** (success)  
**Artifact:** **15184698285** (downloaded and inspected)

## Objective

Measure how replacing only the BTC/USD price series (Firsthand vs Coin Metrics Community PriceUSD) changes the outcomes of the existing V6.0 weekly buy-only policy replay. This is source sensitivity—not a strategy evaluation or source approval.

## Identical simulation assumptions

- A$510,000 capital; 41% initial BTC fraction.
- V6.0 weekly signal: completed Sunday BTC close / mean of previous 200 completed Sunday closes; signal Sunday excluded.
- Next-Monday BTC/AUD spot-price execution proxy; latest USD/AUD FX on or before signal Sunday.
- Same Frankfurter USD/AUD FX series, 0% or 5% cash yield, 0% or 20% cash floor, 5% original-capital weekly cap, 0.25% annual BTC drag, 0.3% buy friction, A$3 fixed fee.
- Five policy variants: fixed weekly, baseline, measured, stepped, aggressive; 20/25/30% discount tiers.
- 104-week rolling cohorts. 414 overlapping cohorts per policy/floor/yield scenario. Overlapping cohorts are not independent trials.
- No taxes, sell/top-timing, personal cash movements, ASX:IBIT premium/discount or actual broker fills.

## Source-price error at the signal/execution dates

| Subset | n | Median APE | P95 APE | Max APE |
|---|---:|---:|---:|---:|
| Sunday signal closes, 2017+ | 517 | 1.077% | 5.450% | 11.615% |
| Monday execution closes, 2017+ | 517 | 1.217% | 6.410% | 19.746% |

The full daily price-series median error is 1.236%, p95 7.929%; it is larger on the specific signal and execution dates. These provider differences are material on some days.

## Train / holdout split

Cohorts are classified using the project’s existing 2022-01-01 holdout boundary:
- **Train:** cohort end before 2022-01-01 — 158 unique cohort starts.
- **Holdout:** cohort start on/after 2022-01-01 — 153 unique starts.
- **Bridge-excluded:** cohorts that overlap the boundary — 103 starts.
- For each source, policy, cash-floor and yield setting, the cohorts and cash flows are paired exactly. These are overlapping cohorts, not independent samples.

Representative scenario: **5% cash yield, 20% initial-cash floor**.

### Source outcome sensitivity — measured policy

| Split | n | Median final-equity delta (Firsthand−CM) | Mean | P95 absolute | Max absolute | Median BTC-held delta | Mean BTC-held delta | P95 absolute BTC | Max absolute BTC |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| Train | 158 | +0.0002% | −0.0288% | 7.9408% | 11.0178% | +0.1667% | +0.2659% | 4.8329% | 8.3175% |
| Holdout | 153 | +0.0541% | +0.0293% | 3.8057% | 7.6508% | +0.1679% | +0.2713% | 2.6487% | 4.2554% |

### Source outcome sensitivity — aggressive policy

| Split | Median final-equity delta | Mean | P95 absolute | Max absolute | Median BTC-held delta | Mean BTC-held delta | P95 absolute BTC | Max absolute BTC |
|---|---:|---:|---:|---:|---:|---:|---:|
| Train | +0.0002% | −0.0288% | 7.9408% | 11.0178% | +0.1667% | +0.2659% | 4.8329% | 8.3175% |
| Holdout | +0.0147% | +0.0159% | 3.8057% | 7.6508% | +0.1516% | +0.2586% | 2.6214% | 4.2554% |

For this 20/25/30 tier policy, Firsthand vs Coin Metrics produces **zero buy-count differences** across all paired cohort rows. This is consistent with the prior exact weekly signal-tier check: no disagreements at the 20/25/30% tiers.

## Main finding

**The source choice has very small median/mean effects in most paired cohorts, but material tail sensitivity remains.** For the measured 5% cash-yield/20%-floor setting, holdout median final-equity difference is only +0.054%, and median BTC-held difference +0.168%, while the p95 absolute terminal-equity difference is ~3.81% and the maximum is ~7.65%. Train-period tails are larger (maximum ~11.02% final equity difference). Buy counts remain identical; differences are mainly execution-price and resulting portfolio valuation/unit effects.

These results do **not** justify using Firsthand prices: Firsthand remains an outlier against Coin Metrics and Explore21 in its historical daily price comparison, and the exact 2017+ signal/execution date errors are nontrivial. The source-sensitivity test shows downstream impact but does not explain or validate the provider. V6.0 current source (BlockHorizon export Price column) is separately cross-validated against Explore21: prices match exactly from 2013 onward, covering the V6.0 2017+ strategy period.

## Decision

- Firsthand price remains **not approved** for model inputs.
- The matched V6.0 20/25/30 cohort replay shows stable buy counts and small median source effects, with tails still material.
- The current V6.0 BlockHorizon price source is corroborated by Explore21 over the full strategy start period; no source change is needed.
- This is a research diagnostic only. No Production/model/dashboard/signal/notification changes.
