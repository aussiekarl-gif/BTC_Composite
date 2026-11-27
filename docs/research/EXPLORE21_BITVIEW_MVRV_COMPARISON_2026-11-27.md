# Explore21 vs Bitview MVRV cross-source diagnostic — 27 Nov 2026

## Scope and method

Research-only comparison of Explore21's public daily `bitcoin-mvrv-ratio.csv` and Bitview's `mvrv` `day1` series. This is a matched-date diagnostic, not model approval.

- Explore21 capture: 5,551 rows, 2011-09-16 through 2026-11-26; no duplicate dates or missing cells in the captured MVRV ratio.
- Bitview capture: 6,540 daily slots; 5,948 non-null and 592 null.
- Bitview date alignment was verified using a date-addressed API query: `start=2020-01-01&end=2020-01-04` returned start index 4017, end-exclusive 4020 and 3 values. The full daily array at positions 4017:4020 exactly matched the date-range response. This verifies the calendar mapping for the probe; the mapping is consistent with day1 index 0 = 2009-01-01.
- MVRV APE calculated as absolute(Bitview − Explore21) / Explore21 × 100, using matched non-null dates.

## Matched-date comparison

| Period | Dates matched | Mean APE | Median APE | 95th percentile | Max |
|---|---:|---:|---:|---:|---:|
| Full overlap | 5,551 | 4.848% | 0.320% | 45.035% | 83.400% |
| From 2013-01-01 | 5,078 | 0.787% | 0.286% | 2.528% | 21.484% |
| From 2014-01-01 | 4,713 | 0.448% | 0.259% | 1.352% | 20.658% |
| From 2017-01-01 | 3,617 | 0.447% | 0.254% | 1.413% | 20.658% |
| From 2020-01-01 | 2,522 | 0.334% | 0.224% | 0.964% | 13.905% |

## Interpretation

- Very large differences concentrate in the earliest history (2011–2012): 2011 mean APE 73.03%, 2012 mean APE 41.26%. Do not assume the source series are comparable for this period.
- From 2013 onward, typical agreement is strong: median APE 0.286%, p95 2.528%, but an isolated 21.48% maximum remains.
- From 2017 onward, median APE is 0.254%, p95 1.413%, with the same 20.66% maximum on 2017-05-27.
- After 2020, median APE 0.224%, p95 0.964%, maximum 13.905% (2020-03-12).
- Firsthand's MVRV was previously found to match Coin Metrics CapMVRVCur extremely closely; Explore21 and Bitview therefore provide useful additional metric cross-checks, but do not assume fully independent methodology or upstream price/cap inputs without provenance review.

## Decision

**Candidate cross-check only; not approved as a model input.** The good typical agreement from 2013 onward is encouraging. Investigate the early-history mismatch and isolated stress-period outliers, and compare realized price and supply-in-profit separately. Preserve source data and dates; no date shifting or silent correction.

## Source notes

- Explore21 states that it computes on-chain metrics from its own Bitcoin Core node, uses Bitstamp daily close as its external price input, and publishes MVRV method v2 with CC BY 4.0 attribution.
- Bitview documents its daily/time series API and date-range access. Its hosted service computes on-chain data itself; methodology and historical price-source caveats remain relevant.

No Production, dashboard, live signal, or notification changes.


## NUPL cross-source comparison (derived from Explore21 MVRV)

Explore21 does not currently have a captured NUPL CSV in this diagnostic. For a definition-aligned check, NUPL was derived as `1 - 1/MVRV` from Explore21's MVRV series and compared with Bitview's NUPL day1 series on calendar-matched dates. Bitview's own MVRV and NUPL satisfy this identity within floating-point tolerance (mean abs residual ~2.51e-7; max ~5.64e-7).

| Period | n | Mean abs difference | Median abs difference | P95 abs difference | Max abs difference | Correlation |
|---|---:|---:|---:|---:|---:|---:|
| Full overlap | 5,551 | 0.04889 | 0.001951 | 0.34414 | 2.14954 | 0.75251 |
| 2013+ | 5,078 | 0.004257 | 0.001721 | 0.012819 | 0.218907 | 0.998900 |
| 2017+ | 3,617 | 0.002594 | 0.001492 | 0.007592 | 0.146886 | 0.999636 |
| 2020+ | 2,522 | 0.002003 | 0.001299 | 0.005398 | 0.142206 | 0.999775 |

Difference is in NUPL ratio units (e.g. 0.01 = one percentage point). Full-history comparison is heavily dominated by 2011 anomalous data. Modern correlation is extremely high and median absolute difference is ~0.13 percentage points since 2020, but large stress-period outliers (e.g. 2020-03-12, 2018-11-20) remain. This is a derived cross-check, not a direct two-provider NUPL series comparison, and it inherits Explore21 MVRV source/methodology differences. Candidate metric corroboration only.


## NUPL threshold-regime agreement (derived comparison)

For threshold tests, compare Explore21-derived NUPL and Bitview NUPL classifications on matched dates; not a signal test, and thresholds are illustrative only.

| Period | Threshold | E21 dates below | Bitview dates below | Classification agreement | Jaccard (below set) |
|---|---:|---:|---:|---:|---:|
| 2017+ | 0.00 | 319 | 318 | 99.92% | 0.991 |
| 2017+ | -0.10 | 219 | 215 | 99.67% | 0.946 |
| 2017+ | -0.20 | 86 | 85 | 99.92% | 0.966 |
| 2020+ | 0.00 | 185 | 186 | 99.96% | 0.995 |
| 2020+ | -0.10 | 103 | 103 | 99.68% | 0.925 |
| 2020+ | -0.20 | 22 | 23 | 99.96% | 0.957 |

Agreement is high overall, but the severe threshold (-0.10) has lower Jaccard due to small, decision-relevant stress-date divergences. 12 Mar 2020: E21-derived -0.1649 vs Bitview -0.0227; 20 Nov 2018: -0.1088 vs +0.0381. Several 2022–23 dates sit near the -0.10 boundary, so small metric offsets flip classifications. This reinforces that reliability is not interchangeable at extreme stress and boundary dates. No thresholds recommended for strategy from this audit.
