# V6.0 clean-slate research protocol

**Status:** initial policy harness only; no candidate selected or approved.

## Separation
- V5.8.2 remains frozen Production.
- V5.9 engines, reports, prospective tapes and history remain archived and untouched.
- V6.0 imports no V5.9 or Production calculation module.
- V6.0 is research-only and cannot create orders or write to a portfolio.

## Signal definition
For each completed Sunday BTC/USD close, calculate the 200WMA as the mean of the **previous 200 completed Sunday closes**. Exclude the signal Sunday itself. Do not use a current incomplete week, a centred average, or a future observation.

## Candidate policy hypotheses
All buy recommendations are percentages, never fixed-dollar allocations:
- Baseline: 2.5% of deployable cash at every valuation.
- Measured: 2.5% / 3.5% / 5.0% / 7.5% at normal / 20% / 25% / 30% below 200WMA.
- Stepped: 2.5% / 5.0% / 7.5% / 10.0%.
- Aggressive: 2.5% / 7.5% / 10.0% / 15.0%.

These are test candidates, not approved settings. No strict below-200WMA entry gate is used: the base DCA remains active above and around the average.

## Cash reserve overlay
Test separately from the candidate ladder. A protected reserve is a percentage of initial cash; candidate buy percentages apply only to deployable cash above the reserve. The existing 5% of original capital weekly hard cap is independent of the cash percentage.

## Validation required before dashboard/live consideration
1. Historical matched-budget replay, 2017 onward for primary claims.
2. Fixed DCA and frozen V5.8.2 benchmarks.
3. Report BTC accumulated, final AUD equity, cash remaining, fees, drawdown, buys and deployment.
4. Separate same-spend/same-transaction-count timing diagnostics from deployment effects.
5. Walk-forward/holdout validation; disclose overlapping cohorts.
6. Stress false bottoms, 70% further declines, prolonged bear markets, missed rallies, and cash depletion.
7. Prospective V6.0 paper tape with its own cutoff, schema and model fingerprint. Never relabel V5.9 observations.

No strategy is eligible for Production merely because a historical backtest is favourable.
