# Preferred 200WMA research candidate — 2026-10-15

**Research only. Production must remain unchanged.**

## Selected configuration
- Buy execution window: **12 weeks**, bell-shaped tranche weights.
- Sell execution window: **16 weeks**, bell-shaped tranche weights.
- Trading fee: **0.1% per fill**.
- Each tier is triggered by a completed weekly 200WMA deviation crossing; fills start the next week.
- Allow pending schedules to complete despite reversal (**cancel=False**) for the current candidate.
- Compare against immediate execution and buy-and-hold.

## Verified initial rolling-start benchmark
GitHub Actions run [38738305322](https://github.com/aussiekarl-gif/BTC_Composite/actions/runs/38738305322), artifact `200wma-12week-execution`:
- 92/92 overlapping 2018–2024 starts beat buy-and-hold.
- Median advantage: **+85.273%**.
- Worst advantage: **+21.137%**.
- Immediate execution median: +60.168%; worst: +27.693%.

## Validation gates before any promotion
1. Audit cash reservations, open orders at backtest end, fee charging and simultaneous-tier signals; reconcile conservation of BTC and cash.
2. Add realistic spread/slippage and fees, including sensitivity to missed fills.
3. Compare fixed 10x10 tiers with lower selling thresholds (+50% to +200%), without optimizing on the final test period.
4. Evaluate 2018–2021 calibration and 2022–2026 forward holdout, independent cycle windows, plus adverse stress cases.
5. Assess BTC-equivalent holdings, cash drag, drawdowns, turnover, and AUD/tax considerations.
6. Ensure any new thresholds or schedule are promoted only after independent verification and explicit approval.

**Caution:** The 92 start dates overlap and share the same end date. The 2025–2026 cycle may be incomplete. These are not independent trials or forward performance guarantees.
