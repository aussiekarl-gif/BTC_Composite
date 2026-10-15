# BTC 200WMA — Research paper-trading dashboard

**SIMULATED portfolios, not actual ETF holdings or executable trades.** Research only; Production V5.8.2 is unchanged.

**Initial notional capital:** A$500,000.00 per strategy. **First eligible completed signal:** 2026-10-19.

## Current status: awaiting first completed weekly observation

No forward-test trades or performance results exist yet. The earliest eligible BTC/USD weekly close is **19 October 2026 UTC**; data can be captured after the issuer releases the corresponding official VBTC market price.

The dashboard will populate only from completed, timestamped, append-only research observations. Historical optimisation results are **not** mixed into this forward test.

| Frozen portfolio | Status |
|:--|:--|
| Simple DCA control | Awaiting first paper entry |
| 12-week buys / 16-week sells | Awaiting first paper entry |
| 12/16-week + 26-week cash recycling | Awaiting first paper entry |

## Data integrity, limits and next run

- Frozen research settings: [paper-testing protocol](https://github.com/aussiekarl-gif/BTC_Composite/blob/research/cycle-strategy-optimization/research_forward/200wma_v1/README.md).
- Wednesday 9:17am Brisbane scheduled job: [GitHub Actions](https://github.com/aussiekarl-gif/BTC_Composite/actions/workflows/research_vbtc_wednesday_scheduler.yml). GitHub may delay scheduled runs.
- The weekly close and VBTC quoted price are **historical reference points**, not executable bid/ask prices. Simulated trading assumes A$20 per fill, 0.1% dealing fees, 0.5% slippage, and illustrative accumulation-phase SMSF tax.
- Existing weekly observations cannot be overwritten; missing or revised data fails closed. Returns over a few paper weeks do **not** establish a statistically reliable edge.
- If you want failure notifications, subscribe to the repository's GitHub Issues/Actions notifications; the workflow raises an issue for scheduler failures.
