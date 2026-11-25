# V6.0 Cowen On-Chain Risk — Research Specification

## Objective

Build a research-only reconstruction of the Into The Cryptoverse / Benjamin Cowen On-Chain Metrics Historical Risk composite shown in the user-provided reference (2026-11-22). The objective is to evaluate whether this risk measure can improve BTC DCA timing and BTC accumulation without compromising cash preservation.

This is a research specification, not an assertion that the proprietary indicator has been exactly replicated. Do not connect it to Production, V5.8.2, V5.9, live purchase recommendations, or portfolio cash controls.

## Reference configuration

The screenshot describes nine component metrics. Match the shown weights initially:

| Metric | Initial weight | Required work |
|---|---:|---|
| Puell Multiple | 1.0 | Verify miner revenue/issuance definition, USD denomination, daily aggregation, and 365-day average |
| MVRV | 1.0 | Market cap / realized cap; verify provider definition and history |
| MVRV Z-Score | 1.0 | Verify exact numerator, denominator, standard-deviation window and source |
| Transaction Fees | 1.0 | Establish exact fee metric and historical normalization |
| Terminal Price | 1.0 | Verify transferred price / CDD definition and supply multiplier |
| MCTC | 1.0 | Market cap / ThermoCap; verify exact ThermoCap definition |
| mCTC | 1.0 | Verify miner-cap numerator and ThermoCap denominator; reconstruct using BGeometrics USD Miner Reserve where available |
| RHODL Ratio | 0.0 | Retain as optional diagnostic; excluded from default composite |
| Supply P/L | 0.0 | Retain as optional diagnostic; excluded from default composite |

The seven active metrics should be equally weighted initially. The screenshot's slider values are the target configuration, not proof that the platform's internal normalisation is known.

## Non-negotiable data integrity rules

1. Preserve raw metric values, source, units, timestamp convention, retrieval/export date, methodology version and coverage.
2. Never fill missing on-chain values with zero, silently forward-fill, interpolate, or backfill without an explicit research-only sensitivity test.
3. Every metric must have an explicit direction convention so higher component risk consistently means higher risk.
4. Do not calculate a composite for a date unless its required components meet a declared coverage threshold. Report component count and coverage on every date.
5. Distinguish exact source data, independently reconstructed data, provider exports, and proxies. Never label a proxy as an exact Cowen metric.
6. Avoid look-ahead: only use values that would have been available at the decision timestamp, including provider publication/revision lag where known.
7. Preserve full raw data and calculation lineage to make every daily composite reproducible.
8. Production V5.8.2, Research V5.9, original Cycle Trading / Day-500 research and existing dashboards must remain unchanged.

## Repository evidence / known limitations\n\n- The research-only Cowen Risk Matrix now has a source adapter for BGeometrics `miner-reserve-usd`. The raw USD series is divided by the selected USD ThermoCap series to derive mCTC. This is a provider-based reconstruction/proxy, not an exact Cowen series; miner-wallet labeling can differ across providers.\n- Do not treat a BTC-denominated `miner-reserve` value as USD Miner Cap. It must be price-converted on matching dates before dividing by USD ThermoCap. The current CryptoQuant reserve fallback is intentionally not labeled USD Miner Cap.

- `engines/audit/public_model_audit.py` already lists free-first candidates and Coin Metrics acquisition routes for Puell, MVRV, NUPL, NVT and ThermoCap-related calculations.
- `engines/audit/provider_source_matrix.py` documents that CoinGlass specialist on-chain endpoints are blocked by the current plan and tested CryptoQuant BTC on-chain endpoints return HTTP 403 under the current entitlement.
- `engines/audit/provider_access_summary.md` records those access limitations.
- `engines/audit/external_metric_csv_review_2026-10-09.md` records BlockHorizon export reviews and unresolved metric-specific provenance/units issues. In particular, miner revenue's displayed USD unit and magnitude still require reconciliation; the 200WMA export's first valid date is unresolved.
- Existing MVRV Z-score/NUPL exports were structurally reviewed, but that does not independently validate all Cowen transformations.
- Existing data should be inspected and reused where provenance supports it. Do not assume every metric is already available simply because it appears in an audit candidate list.

## Work stages and gates

### Stage 1 — source and formula audit
For each of the seven active metrics, document:
- canonical formula and exact variant;
- raw inputs and provider/source;
- earliest/latest dates and missingness;
- units, timezone, daily/weekly convention;
- revisions/publication lag and known survivorship/look-ahead risks;
- parity check against a second source or independently reproducible calculation.

Output: metric provenance matrix and formula notes. No composite until all seven have an explicit status.

### Stage 2 — metric-level reconstruction
Build isolated calculators/adapters. Each returns raw value, normalized risk score, source status, as-of timestamp, and quality flags. Test against known values and independently checked dates.

Where exact transformation is unknown, use clearly labelled candidate normalisations (e.g. rolling empirical percentile) as research variants, not as claims of Cowen parity. Fit/choose thresholds only inside training windows; never use full-sample future information to normalize historical dates.

### Stage 3 — composite and dashboard
Create a standalone research page / engine. Show:
- seven active component raw values and risk scores;
- component weights and contribution;
- total composite risk (0–1);
- data completeness and quality flags;
- date range and source status;
- exact-match vs reconstructed vs proxy classification.
Keep RHODL and Supply P/L at zero default weight, with optional diagnostic toggles only after provenance review.

### Stage 4 — investment-relevant testing
Compare on identical dates and capital constraints:
- fixed weekly DCA;
- existing V5.8.2 and V5.9 research baselines;
- existing V6.0 200WMA discount-tier policy;
- on-chain composite-only policies;
- combined on-chain + 200WMA policies only as a separate ablation.

Report BTC accumulated, final AUD-equivalent value, cash remaining, timing of deployment, drawdown, downside path performance and opportunity cost in rapid recoveries. Include fees/ETF implementation assumptions only where sourced; clearly separate BTC spot signal research from ASX:IBIT execution.

Use chronological train/validation/test splits and rolling walk-forward cohorts. Include multiple market regimes and delayed-bottom / V-shaped recovery stress cases. Avoid tuning on the test period.

### Stage 5 — prospective shadow validation
Record daily/weekly signals prospectively without changing live purchase instructions. Compare model output with contemporaneous frozen inputs and actual subsequent outcomes. Do not promote based solely on historical backtests.

## Promotion criteria

No promotion to any live DCA recommendation unless:
- seven-metric data lineage and formula status are transparent;
- no-look-ahead tests pass;
- metric-level parity is acceptable or each deviation is disclosed;
- rolling out-of-sample tests beat or provide a clearly justified trade-off versus fixed DCA and current research baselines;
- results are not dominated by one metric or one historical cycle;
- performance survives reasonable missing-data, normalization, cost and execution sensitivities;
- prospective shadow evidence supports the result.

Until then, the engine is research-only and cannot authorize purchases or sales.
