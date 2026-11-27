# Hybrid calendar DCA + adaptive 200WMA reserve — research replay

**Date:** 27 Nov 2026  
**Draft PR:** #413  
**Current-head workflow run:** Research DCA run **937** succeeded; artifact cohort/summary CSVs match run 936 byte-for-byte.  
**BTC export last observation:** 5 Oct 2026 UTC  
**BTC source SHA256:** `6aa186226d765eb48da57364303f17bdbd7fcb96ada6314c096a547508862899`  
**FX payload SHA256:** `79e57b824573473c3f1f6195ff4795bca42028ad535c895e3f416ede86bc5f68`

## Objective

PR #412 showed the pure adaptive-recovery policy has a trigger-opportunity problem: it can accumulate more BTC when triggered, but a calendar-start cohort that never triggers can spend two years buying nothing. This experiment keeps a fixed weekly DCA base and places only the remaining cash in the adaptive reserve.

## Cohorts and assumptions

- First Monday of each calendar quarter, 2017–2025; only full 104-week cohorts.
- **32** complete cohorts: 20 pre-2022 calendar entries, 12 2022+ entries. Cohorts overlap and are not independent. Entry groups are descriptive; no parameter fitting.
- Fresh budget **A$292,383**, reference capital **A$510,000**, cash yield **5% annual effective**, weekly cap **A$25,500**, buy friction **0.3%**, fee **A$3**.
- BTC/USD daily close converted to AUD using latest available historical USD-per-AUD FX quote. This is a BTC/AUD proxy, not ASX:IBIT execution.
- Fixed leg: allocated base budget /104 weekly buys. Adaptive reserve: existing `adaptive_recovery` sizing percentages, based on original reserve budget; trigger strictly below prior 200WMA.
- Base and reserve are separate cash subaccounts earning the same assumed yield. All buys within the same enrolment-anchored 7-day bucket share one weekly cap, with fixed-base purchases processed before adaptive reserve purchases on a shared day.

## Unconditional cohort results

Medians across calendar cohorts; paired medians compare each cohort to its matched 100% fixed weekly DCA reference.

### Pre-2022 calendar entry (20 cohorts)

| Strategy | Median BTC | Median paired BTC uplift | Median final equity | Median paired equity uplift | Equity wins | Median cash left | Cash budget deployed |
|---|---:|---:|---:|---:|---:|---:|---:|
| Fixed weekly 100% | 18.277 | baseline | A$397,791 | baseline | baseline | A$14,989 | 100.11% |
| Hybrid 25% base / 75% reserve | 7.961 | −75.00% | A$374,599 | −14.20% | 35.0% | A$245,185 | 25.11% |
| Hybrid 50% / 50% | 9.349 | −50.00% | A$382,436 | −9.47% | 35.0% | A$168,453 | 50.11% |
| Hybrid 75% base / 25% reserve | 13.708 | −25.00% | A$387,308 | −4.73% | 35.0% | A$91,721 | 75.11% |

### 2022+ calendar entry (12 cohorts)

| Strategy | Median BTC | Median paired BTC uplift | Median final equity | Median paired equity uplift | Equity wins | Median cash left | Cash budget deployed |
|---|---:|---:|---:|---:|---:|---:|---:|
| Fixed weekly 100% | 3.827 | baseline | A$537,913 | baseline | baseline | A$14,989 | 100.11% |
| Hybrid 25% base / 75% reserve | 2.015 | −15.96% | A$385,652 | +25.22% | 66.67% | A$106,759 | 69.02% |
| Hybrid 50% / 50% | 2.422 | −10.81% | A$449,388 | +16.57% | 66.67% | A$76,167 | 79.37% |
| Hybrid 75% base / 25% reserve | 2.870 | −5.42% | A$513,123 | +8.27% | 66.67% | A$45,575 | 89.74% |

Median absolute final equity and median paired uplift are different cohort statistics; overlapping/skewed cohorts can make them appear directionally different. The paired comparisons use each calendar cohort against its own fixed-weekly benchmark.

## Trigger frequency and conditional performance

The adaptive reserve trigger rate is the same across base allocations, because only budget split changes:

| Entry group | Triggered | Median delay |
|---|---:|---:|
| Pre-2022 | 6/20 (30.0%) | 69.07 weeks |
| 2022+ | 7/12 (58.33%) | 10.57 weeks |

When the adaptive reserve trigger actually occurred, the reserve leg improved paired outcomes in most triggered cohorts. A larger fixed base reduces the amount available for the reserve and therefore reduces the conditional adaptive upside:

| Entry group | Base allocation | Median paired BTC uplift, triggered only | BTC wins | Median paired equity uplift, triggered only | Equity wins |
|---|---:|---:|---:|---:|---:|
| Pre-2022 | 25% | +30.92% | 4/6 | +31.33% | 6/6 |
| Pre-2022 | 50% | +21.26% | 4/6 | +20.69% | 6/6 |
| Pre-2022 | 75% | +10.61% | 4/6 | +10.33% | 6/6 |
| 2022+ | 25% | +31.09% | 6/7 | +31.59% | 7/7 |
| 2022+ | 50% | +21.33% | 6/7 | +20.99% | 7/7 |
| 2022+ | 75% | +10.65% | 6/7 | +10.47% | 7/7 |

Across all cohorts, unconditional BTC win rate is 20% pre-2022 and 50% 2022+; final-equity win rate 35% and 66.67%, respectively. No-trigger cohorts remain the cost of waiting. At the 75%-base variant, no-trigger median paired final-equity uplift is −9.67% pre-2022 and −9.31% in 2022+; each group has one no-trigger equity win (1/14 and 1/5).

## Timing score and cap compliance

The timing score is the **all-purchase hybrid VWAP premium to the future 104-week BTC/AUD low**. It includes fixed-base buys, so larger base allocations naturally show a higher premium. It is a retrospective score, not a forecast.

| Entry group | 25% base | 50% base | 75% base |
|---|---:|---:|---:|
| Pre-2022 | 132.91% | 136.57% | 136.40% |
| 2022+ | 54.69% | 61.18% | 72.79% |

All 96 hybrid cohort/variant outputs report **weekly cap compliance**. The 5% original-capital cap is shared across base and reserve buys within each enrolment-anchored 7-day bucket, not applied separately to each leg.

## Interpretation

1. **75% fixed base / 25% adaptive reserve is the strongest of the tested hybrids for unconditional BTC accumulation.** Median BTC rises with base allocation in both entry groups; 75% base is closest to fixed weekly DCA.
2. It still does not beat fixed weekly DCA in median BTC accumulation: −25% paired median pre-2022 and −5.42% 2022+.
3. In the 2022+ group, 75% base/25% reserve has median paired final-equity uplift +8.27% and equity wins 66.67%, while accumulating less BTC than fixed weekly. This is not a universal result: pre-2022 median paired equity uplift is −4.73%.
4. Conditional reserve timing remains useful in triggered cohorts, but trigger rate is only 30% pre-2022 and 58.33% 2022+. The fixed base reduces no-trigger opportunity cost.
5. The strategy is not approved for Production. These are descriptive overlapping cohorts, archived/revisable BTC history, deterministic cash yield, assumed fees/friction, no SMSF tax and no ASX:IBIT execution.

## Next research

Test higher fixed-base allocations **80% and 90%** (20%/10% adaptive reserve) against 75% and 100% fixed weekly DCA. The current 75% hybrid closes most of the 2022+ BTC gap but still does not beat fixed weekly; the higher-base variants quantify whether retaining a small adaptive reserve improves final equity without materially sacrificing BTC accumulation. Keep predeclared calendar entry dates, 104-week horizon, shared cap and cash-yield assumptions unchanged.

## CI

- Existing Research DCA regression suite: passed.
- Five synthetic hybrid tests: passed.
- Historical 32-cohort hybrid replay: passed and artifact uploaded.
- Public-source smoke test: Aethereal upstream fetch failed; unrelated to the hybrid replay.
