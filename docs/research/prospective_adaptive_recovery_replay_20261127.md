# Prospective adaptive recovery replay — calendar enrolment research

**Date:** 27 November 2026  
**PR:** #412 (draft, research-only)  
**Historical run:** Research DCA workflow runs 907/908; artifact summaries and cohort CSVs are byte-identical  
**BTC price export last observation:** 5 October 2026 UTC  
**Source BTC CSV SHA256:** `6aa186226d765eb48da57364303f17bdbd7fcb96ada6314c096a547508862899`  
**FX payload SHA256:** `79e57b824573473c3f1f6195ff4795bca42028ad535c895e3f416ede86bc5f68`

## Question and cohort design

Does the existing prospective `adaptive_recovery` 200WMA buy policy improve BTC accumulated and final portfolio value when the investor starts with **new, fixed AUD cash on a calendar date**, rather than choosing a start date retrospectively around a cycle bottom?

- Entry: first Monday of each calendar quarter from 2017 through 2025; only complete 104-week cohorts are included.
- Completed cohorts: **32** (20 with pre-2022 entry dates, 12 with 2022-or-later entry dates); 96 policy/cohort rows.
- Cohorts overlap substantially. The two entry-period groups are descriptive only; this is not a strict holdout split and no policy parameters were fitted.
- BTC/USD price is the archived October-2026 export. AUD prices are daily BTC/USD divided by the latest available historical USD-per-AUD FX quote.
- Enrolment dates are calendar-defined, not chosen from subsequent bottoms.

## Assumptions

| Assumption | Value |
|---|---:|
| Fresh AUD budget | A$292,383 |
| Reference original capital | A$510,000 |
| Cash yield | 5% annual effective |
| Weekly maximum purchase | A$25,500 (5% original capital) |
| Purchase friction | 0.3% |
| Fixed brokerage per buy | A$3 |
| Horizon | 104 weeks |
| BTC proxy | Daily close converted to AUD; **not ASX:IBIT fills** |

Cash interest is earned on unspent cash, including the initial waiting period. No SMSF tax, pension-phase tax, ETF tracking, broker spread or ASX execution is modelled.

## Policies compared

1. **Fixed weekly DCA:** 1/104 of the starting budget every 7 days after enrolment.
2. **Remaining-cash 2.5% below 200WMA:** 2.5% of remaining cash on a weekly date only when the previous BTC close is strictly below its prior 200WMA.
3. **Adaptive recovery:** the existing `adaptive_recovery` percentage helper and below-prior-200WMA activation are unchanged. Each weekly review targets 2.5%, 15%, 4.5%, or 1% of the original fresh-cash budget, constrained by remaining cash and the A$25,500 weekly cap.

## Unconditional outcomes — all calendar cohorts in each entry group

Medians across cohorts; these are not independent observations.

### Pre-2022 calendar entries (20 cohorts)

| Policy | Median BTC | Median AUD VWAP | Median cash left | Median budget deployed | Median VWAP premium to cohort low | Median final equity |
|---|---:|---:|---:|---:|---:|---:|
| Fixed weekly | 18.277 | A$16,124 | A$14,989 | 100.11% | 136.32% | A$397,791 |
| Adaptive recovery | 0.000 | A$29,868* | A$322,245 | 0.00% | 25.70%* | A$322,245 |
| 2.5% below 200WMA | 0.000 | A$29,097* | A$322,245 | 0.00% | 22.22%* | A$322,245 |

`*` VWAP/premium are calculated only for cohorts with actual buys; medians are conditional and should not be read as the group-wide median timing result. No buys occurred in the median cohort for either signal policy.

### 2022-or-later calendar entries (12 cohorts)

| Policy | Median BTC | Median AUD VWAP | Median cash left | Median budget deployed | Median VWAP premium to cohort low | Median final equity |
|---|---:|---:|---:|---:|---:|---:|
| Fixed weekly | 3.827 | A$77,016 | A$14,989 | 100.11% | 85.77% | A$537,913 |
| Adaptive recovery | 1.736 | A$33,653* | A$151,003 | 58.17% | 25.09%* | A$356,227 |
| 2.5% below 200WMA | 0.596 | A$29,097* | A$277,167 | 14.51% | 21.86%* | A$335,455 |

Again, conditional VWAP/premium stats describe buy-executing cohorts only.

## Signal opportunity and paired comparison vs fixed weekly DCA

| Entry group | Adaptive trigger rate | Median trigger delay | BTC-unit win rate (all cohorts) | Median paired BTC uplift | Final-equity win rate | Median paired equity uplift |
|---|---:|---:|---:|---:|---:|---:|
| Pre-2022 | 30.0% (6/20) | 69.07 weeks | 20.0% | −100.00% | 35.0% | −18.85% |
| 2022+ | 58.33% (7/12) | 10.57 weeks | 50.0% | −24.21% | 66.67% | +32.43% |

**Conditional on a trigger**, the policy did much better in this sample:

| Entry group | Triggered cohorts | Median paired BTC uplift (triggered only) | BTC wins | Median paired equity uplift (triggered only) | Equity wins |
|---|---:|---:|---:|---:|---:|
| Pre-2022 | 6/20 | +37.64% | 4/6 | +41.81% | 6/6 |
| 2022+ | 7/12 | +37.03% | 6/7 | +42.19% | 7/7 |

This conditional result is not an unbiased replacement for the unconditional comparison: triggering selects cohorts where the strategy actually deploys, while **not triggering is itself a material outcome**. In no-trigger cohorts, adaptive cash earns the assumed 5% yield but generally lags the fixed weekly comparator's final equity; median paired-equity uplift in no-trigger cohorts was −38.60% pre-2022 and −37.19% in 2022+.

## Timing score (retrospective)

The reported `VWAP premium to cohort low` is effective purchase VWAP including the assumed friction/fee relative to the cohort's **future 104-week daily-close low**. This is a retrospective descriptive timing score, not an actionable forecast-error measurement.

Among cohorts that triggered, median premium was **25.70% pre-2022** and **25.09% in 2022+**. This happens to be near the user's approximate 25% timing-error preference, but it must not be interpreted as validated predictive accuracy: the future low is used only for scoring, cohorts overlap, and the BTC export is not point-in-time data vintage.

## Decision

- The adaptive policy is **not a robust unconditional DCA replacement** for the objective of accumulating the most BTC. Its median BTC accumulation is lower than fixed weekly DCA in both entry groups, and its signal does not activate in 70% of pre-2022 and 41.7% of 2022+ cohorts.
- When the strict below-200WMA/recovery signal activates, this sample shows substantially higher BTC accumulation and final-equity outcomes in most triggered cohorts. That conditional upside does not compensate reliably for the opportunity cost of waiting across all calendar starts.
- The 2.5%-of-remaining-cash below-200WMA-only comparator also has a low activation rate and does not beat fixed weekly BTC accumulation in any cohort in this sample.
- These results are descriptive, not independent statistical evidence. BTC historical data may be revised, and execution/tax/ETF assumptions are not verified.

### Next research candidate

Test a **hybrid calendar DCA + adaptive reserve** so a portion of the budget accumulates BTC on schedule while the rest waits for a strict prior-200WMA/recovery signal. Predeclare 25/50/75% base-DCA allocation variants and compare paired BTC units, final equity, cash remaining, timing premium, trigger delays and cap compliance. Keep all variants research-only; do not change Production, dashboard signals or notifications.

## CI

- Earlier Research DCA regression runs **907/908**: main regression suite, synthetic replay tests and historical cohort runner passed; artifact produced and repeated outputs were byte-identical.
- The subsequent summary-table enhancement added explicit triggered-cohort and final-equity win-rate columns; a fresh CI rerun on the current head is pending before this report is considered fully validated.
- Public-source smoke test: Aethereal upstream fetch failed; it is separate from the strategy tests and does not invalidate the earlier replay artifact.

