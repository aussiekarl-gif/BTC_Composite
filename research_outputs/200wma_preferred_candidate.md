# Preferred 200WMA research candidate — 2026-10-15

**Research only. Production must remain unchanged.**

## Selected configuration
- Buy execution window: **12 weeks**, bell-shaped tranche weights.
- Sell execution window: **16 weeks**, bell-shaped tranche weights.
- Trading fee: **0.1% per fill**.
- Each tier is triggered by a completed weekly 200WMA deviation crossing; fills start the next week.
- Allow pending schedules to complete despite reversal (**cancel=False**) for the current candidate.
- **Block new concurrent schedules for the same trading tier** while an earlier one remains active. This conservative policy is preferred after the overlap audit.
- Use **0.5% additional slippage** (on top of the 0.1% fee) as the conservative sensitivity reference, not a calibrated execution forecast.
- Compare against immediate execution and buy-and-hold.

## Verified initial rolling-start benchmark
GitHub Actions run [38738305322](https://github.com/aussiekarl-gif/BTC_Composite/actions/runs/38738305322), artifact `200wma-12week-execution`:
- 92/92 overlapping 2018–2024 starts beat buy-and-hold.
- Median advantage: **+85.273%**.
- Worst advantage: **+21.137%**.
- Immediate execution median: +60.168%; worst: +27.693%.

## Additional completed execution robustness audit
- [GitHub Actions run 38802836578](https://github.com/aussiekarl-gif/BTC_Composite/actions/runs/38802836578), artifact `200wma-overlap-slippage`.
- Same-tier overlap allowed, 0% slippage: 92/92 wins, +85.273% median, 938 median weekly fills.
- Same-tier overlap **blocked**, 0% slippage: 92/92 wins, +73.754% median, 663 median weekly fills.
- Same-tier overlap **blocked**, 0.5% additional slippage: 92/92 wins, **+70.454% median**, worst **+20.930%**.
- Same-tier overlap **blocked**, 1.0% additional slippage: 92/92 wins, +67.187% median, worst +20.338%.
- These estimates remain shared-endpoint overlapping cohorts and must not be used alone for promotion.

## Validation gates before any promotion
1. Audit cash reservations, open orders at backtest end, fee charging and simultaneous-tier signals; reconcile conservation of BTC and cash.
2. Add realistic spread/slippage and fees, including sensitivity to missed fills.
3. Compare fixed 10x10 tiers with lower selling thresholds (+50% to +200%), without optimizing on the final test period.
4. Evaluate 2018–2021 calibration and 2022–2026 forward holdout, independent cycle windows, plus adverse stress cases.
5. Assess BTC-equivalent holdings, cash drag, drawdowns, turnover, and AUD/tax considerations.
6. Ensure any new thresholds or schedule are promoted only after independent verification and explicit approval.

**Caution:** The 92 start dates overlap and share the same end date. The 2025–2026 cycle may be incomplete. These are not independent trials or forward performance guarantees.
