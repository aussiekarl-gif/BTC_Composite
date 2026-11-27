# Cross-source Metric Validation Standard — 27 Nov 2026

Purpose: prevent a candidate on-chain metric from becoming a research or Production input merely because a chart looks persuasive. This standard is applied to BTC DCA research; it does not alter Production.

## Validation stages

1. **Source capture and integrity** — raw source snapshots, retrieval timestamps, response status, hashes, schema, and coverage. No undocumented transformations.
2. **Definition alignment** — record units, formula, source-price basis, time-window boundary, smoothing, issuance/UTXO methodology, cohort/global selection, and null rules. Differences must be explicitly reconciled or comparison labeled non-equivalent.
3. **Calendar alignment** — compare by date with verified mapping; never silently shift data. Keep timezone, daily close, sample time and lag rules explicit.
4. **Distribution comparison** — report matched n, coverage, correlation, median and mean absolute error, p95, max, bias, symmetric error where useful, and outlier dates. High correlation alone is insufficient.
5. **Stress-regime checks** — inspect bull peaks, bear lows, halving windows, extreme volatility, and the candidate's intended signal zones. Tail divergence in the dates that drive decisions is a critical failure even if overall statistics are good.
6. **Reproducibility** — raw data, code, report, test result and immutable commit are recorded. Pipeline changes rerun diagnostics.
7. **Candidate signal evaluation** — only after source definition reliability: causal/no-look-ahead signal, thresholds set without test-window tuning, rolling/walk-forward validation, full cycle coverage (prefer 2017+; test each cycle separately), and compare to fixed DCA/B&H baselines.
8. **Incremental value** — prove the metric improves BTC accumulated, final portfolio value, drawdown or buy-timing over existing policy, not just that it correlates with price or other indicators. Ablation and threshold sensitivity tests required.
9. **Forward validation** — paper-test prospectively; no Production promotion before results are stable, replicated and reviewed.

## Cross-source interpretation categories

- **Strong corroboration:** modern median errors small, tail manageable, matched definitions/coverage, and no systematic offset that affects decision thresholds.
- **Corroborated but provisional:** close central tendency or correlation but unresolved definition, smoothing, sample-time or stress-date discrepancies.
- **Not comparable:** different units/definitions or no matching series.
- **Rejected for signal use:** unreconciled source errors, poor stress-period reliability, non-causal input, data gaps, or no incremental benefit in controlled walk-forward tests.

## Current status snapshot (candidate-only)

| Metric | Current evidence | Status |
|---|---|---|
| BTC price | Modern cross-source median APE 0.22% since 2020 | Strong corroboration |
| Realized Price | 2017+ median APE 0.123%; p95 0.51% | Strong corroboration |
| Realized Cap | 2020+ median APE 0.107%; p95 0.302% | Strong corroboration |
| MVRV | 2020+ median APE 0.224%; p95 0.964% | Strong corroboration |
| Hashrate | 7-day smoothing matched; 2020+ median absolute difference 0.64% | Strong metric-level corroboration |
| NUPL | Derived from E21 MVRV vs Bitview NUPL; 2020+ median absolute diff 0.13 pp; stress outliers | Corroborated but provisional (derived comparison) |
| Puell Multiple | 2020+ median APE 1.115%, p95 4.604%, persistent ~0.5% residual after price normalization | Provisional, methodology differences unresolved |
| Supply in Profit | Modern typical differences modest but outliers significant | Provisional; outlier/source method work needed |
| MVRV Z-Score | BlockHorizon direct export vs Explore21; modern errors modest but positive bias; high-threshold set overlap weak; formula/input alignment unresolved | Corroborated but provisional; threshold-sensitive |

**Important:** These categories are metric reliability only, not evidence that a metric is profitable, predictive, or suitable for DCA signals. No Production inputs are approved by this report.


## MVRV Z-Score candidate status

Bitview discovery returned no global MVRV Z-Score series for queries `mvrv z score`, `mvrv-z-score`, or `z score` (empty search responses). Explore21's official method v1 is now documented: `(market cap - realized cap) / expanding sample standard deviation of market cap`, beginning 18 Aug 2011 and plotted after 30 days. A reconstruction from Explore21 realized-cap CSV using expanding sample standard deviation matches the first observations and latest 26 Nov 2026 value to floating-point tolerance, and is close in modern history (2024+ mean absolute Z difference 0.00402, median 0.00451, p95 0.00730, max 0.00845). However, material residuals remain in historical 2013 and 2017 periods (max 0.4722 on 30 Nov 2013). The published formula is identified, but historical source-input/version alignment is not fully reconciled. No independent matching Bitview series; status: **formula identified, partial reconstruction, input alignment unresolved**, candidate only and not approved. Earlier 2–10-year rolling-window tests were not the documented formula and are superseded by this expanding-window test. The captured E21 method changelog (HTTP 200) reports method_version 1, first published 2026-07-15, with no subsequent method-version changes. MVRV ratio inputs reconstructed from the same cap CSV match to ~5e-7; denominator remains unexplained, so this is a partial reconstruction rather than source validation.


## BlockHorizon MVRV Z-Score cross-source comparison

The user-confirmed BlockHorizon export has direct MVRV Z-Score values and a Price column. Matched dates with Explore21: 5,499 (2011-09-16–2026-10-05). BH Price matches E21 exactly from 2013-01-01 onward (5,026 dates), including all V6.0 price history from its 2017 start. Early 2011–2012 prices differ, with maximum APE 42.09%.

Z-Score BH−E21: 2017+ mean absolute difference 0.1263, median 0.0838, p95 0.4432, max 1.3140; 2020+ MAE 0.09782, median 0.07925, p95 0.30496, max 0.57479; 2024+ MAE/median 0.08203/0.08848, p95 0.13974, max 0.16143. BH is generally higher. Formula/realized-cap/denominator methodology for BH not reconciled.

Threshold overlap is weaker than daily agreement suggests: for Z>=7, Jaccard above-threshold overlap 0.468 from 2013 and 0.636 from 2017; from 2020 BH has 3 above-7 days while E21 has none (Jaccard 0). High thresholds must be source-specific; no Z-score signal approval. Note V6.0 accumulation backtest imports this export but reads its **Price** column only, not its Z-score column. Since its price history starts in 2017 and matches E21 exactly over that range, this improves price-source reliability for V6.0 but does not validate MVRV Z-score.
