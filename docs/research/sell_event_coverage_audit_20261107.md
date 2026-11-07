# Sell-event coverage audit — 2026-11-07

Research only. No changes to Production, portfolio or notifications.

## Verified execution

GitHub Actions run [42358846866](https://github.com/aussiekarl-gif/BTC_Composite/actions/runs/42358846866) and associated PR tests passed. The artifact `causal-sell-threshold-comparison` contains the full 505 matched weekly-observation comparison (2017-01-02 to 2026-08-31).

Five disjoint walk-forward holdouts, each independently initialized with A$500,000; per-side execution cost 0.3%. The fixed threshold comparisons used identical holdout windows for each score variant.

| Sell threshold | Stored-risk sell events | Reconstructed-risk sell events |
|---|---:|---:|
| 0.55 | 35 | 14 |
| 0.60 | 24 | 10 |
| 0.65 | 13 | 4 |
| 0.70 | 8 | 1 |
| 0.75 | 3 | 0 |

At the train-selected 0.75 threshold, stored risk generated sales in only **one of five** folds (three events), reconstructed risk in **zero** folds. Both variants selected 0.75 in all five folds, but zero-event folds provide no identification of an optimal exit threshold.

## Interpretation and blockers

- Earlier exits at 0.55–0.70 cannot be evaluated as reliable improvements from this small number of realized exit events. Reconstructed scores systematically produce fewer sales.
- The reconstructed score is a **causal-fit Power Law approximation only**, not the frozen multi-component Production risk score. Its historical price publication and revision provenance remain unverified.
- Five fresh-capital holdouts are not one continuously compounded strategy. These results do not establish superiority to buy-and-hold or predict future performance.
- A defensible next test requires full-cycle windows spanning bull-market exits, pre-registered thresholds, consistent AUD prices, actual signal publication lag, per-side costs, spread/slippage, no hindsight tuning, and fold-by-fold sell counts. If sell opportunities remain insufficient, report **INSUFFICIENT_SELL_EVENTS** rather than a winner.

**Decision:** Keep PRs #76, #89 and #238 research-only and draft. Do not change Production, live Cycle Trading, sell thresholds, Streamlit recommendations or ntfy.
