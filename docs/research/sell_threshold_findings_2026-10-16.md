# Research-only: earlier Bitcoin sell threshold robustness

Date: 2026-10-16 (AEST). NOT PRODUCTION APPROVED.

## Verified execution
- Unit tests: [successful Research Cycle Backtest Tests run](https://github.com/aussiekarl-gif/BTC_Composite/actions/runs/38825448695).
- Real historical experiment: [successful read-only historical run](https://github.com/aussiekarl-gif/BTC_Composite/actions/runs/38825448728).
- Source: private `aussiekarl-gif/btc-audit-data` master `btc_audit_backup.csv`, observed blob SHA `e2976f508108ff1e89e95c252becad5cd79d9040`.
- Historical master has 6,332 date rows; 557 *weekly* valid BTC/AUD price-risk pairs, from 2016-01-04 through 2026-08-31. Latest master calendar rows may extend further but **do not provide paired risk scores**.
- All 557 usable rows are labelled `Walk-forward Power Law`. This label does **not** independently validate point-in-time signal publication or immunity from retrospective revisions.
- Model uses prior-observation risk signal and next-observation execution with fees; no future holdout data influences threshold selection.

## Design
Starting capital: AUD 500,000 per independent holdout period. Buy risk below 0.25, up to 5% starting capital per observation; sell when risk strictly exceeds tested threshold, up to 20% of current holdings, scaled with risk. AUD cash is held at zero interest. All-in per-side friction proxies: 0.1%, 0.3%, 0.6%. FIFO P&L in simulator; no CGT, financing, order-book impact or execution-limit model.

- Fixed thresholds: 0.55 / 0.60 / 0.65 / 0.70 / **0.75 baseline**.
- A separate training-only optimizer selects sell threshold using historical observations and an assumed 0.3% per-side friction.
- Five expanding-training / non-overlapping future holdout windows, approximately 55 weekly observations each. Each fold resets to fresh AUD 500,000; do NOT aggregate as a continuous portfolio return.
- Compare against original 0.75 sell threshold, immediate buy-and-hold, and equal-size weekly DCA in identical holdout periods.

## Main findings
1. The historical training-only selector chose **0.75 in every one of five folds**. No demonstrated advantage from earlier sell thresholds.
2. For the separate single 70/30 chronological split, train ended 2023-06-12; test ran from 2023-06-19 through 2026-08-31. At 0.3% per-side friction: selected cycle strategy ended at **AUD 1,262,621** versus buy-and-hold **AUD 1,404,795** (cycle strategy lagged by **AUD 142,174**). Selected threshold = 0.75.
3. The train-selected cycle model beat buy-and-hold in 3/5 and fixed DCA in 4/5 disjoint holdouts at 0.3% friction. These are independent fresh-capital comparisons; not compounded returns.
4. Fixed lower threshold performance against 0.75 across the **five disjoint folds** (AUD, 0.3% per-side costs):

| Fixed sell threshold | Wins | Losses | Ties | Mean ending-equity difference per fold |
|---|---:|---:|---:|---:|
| 0.55 | 1 | 1 | 3 | -1,641 |
| 0.60 | 1 | 1 | 3 | -2,172 |
| 0.65 | 0 | 1 | 4 | -1,736 |
| 0.70 | 0 | 1 | 4 | -872 |
| 0.75 | 0 | 0 | 5 | 0 |

Results are directionally consistent at 0.1% and 0.6% costs: each lower threshold still has negative mean relative performance to 0.75. Most ties occur because certain fold signals never entered the affected sell ranges.

**Interpretation:** Earlier exits occasionally help, but this evidence does not justify lowering the global sell threshold. Holding more BTC was advantageous in some rising windows; the 0.75 engine can underperform buy-and-hold for other reasons (notably gradual deployment). These tests do **not** establish that 0.75 is optimal for future cycles or that the existing overall buying model is optimal.

## Decision
**Do not change Production, the authoritative research master, or the live risk-model threshold.** Preserve as research-only. Do not merge the draft PR until point-in-time source validation and portfolio-level comparisons are complete.

## Next recommended research
1. Audit risk-score timestamp availability and historical data revisions; distinguish causal input from hindsight-rebuilt signal history.
2. Compare 12-week and 16-week 200WMA-based buy/sell distribution schedules, with strict signal lag, feasible fees/slippage, and identical starting cash.
3. Test missed bull markets, declining cycle amplitude, extended sideways regimes, and equity/cash drawdowns against fair fixed DCA, buy-and-hold, and the current Production approach.
4. Add Australia-relevant after-tax scenarios (including different account structures) separately; transaction costs are not tax costs.
5. Promote only after multiple genuinely untouched windows show improvements that survive costs and plausible data uncertainty.
