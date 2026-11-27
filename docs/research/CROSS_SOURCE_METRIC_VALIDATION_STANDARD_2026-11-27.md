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
| MVRV Z-Score | Independent Bitview candidate search underway | Await series discovery |

**Important:** These categories are metric reliability only, not evidence that a metric is profitable, predictive, or suitable for DCA signals. No Production inputs are approved by this report.
