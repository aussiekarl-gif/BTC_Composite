# Sell-threshold research decision — 2026-11-07

**Decision: RETAIN BASELINE 0.75. NO LIVE CHANGE.**

This decision covers sell-threshold research only, not validation of the entire BTC Cycle Trading strategy or any claim of superior returns to buy-and-hold.

## Decision evidence

- PR #238 research workflow and general test checks are green after the provenance documentation update.
- Paired stored/reconstructed risk scores span 505 weekly observations from 2017-01-02 to 2026-08-31; reconstructed Power Law is not the frozen Production composite.
- Five short disjoint walk-forward holdouts selected 0.75 in all folds for both score variants; baseline had very few sell events, so identification was weak.
- Full-window descriptive tests showed earlier 0.55 exits could improve ending equity, but this was in-sample.
- Fixed calendar eras at 0.3% costs per side: 0.55 vs 0.75 lost A$236,870 in 2020–22 on stored risk and A$58,099 on reconstructed risk; positive effects in 2023–26 did not generalize across eras.
- Two calendar-forward train-only selections per risk variant (train through 2019, test 2020–22; train through 2022, test 2023–26) chose 0.75 in all four cases.
- Historical shadow V5.8.2 arithmetic parity over 5,779 overlapping dates is documented in btc-audit-data validated manifest, but point-in-time publication and revision fidelity is not proven.

## Final disposition

1. **Reject 0.55–0.70 for promotion.** No reproducible out-of-sample advantage established.
2. **Retain 0.75 as unchanged reference.** Do not call it optimal or a proven live sell trigger.
3. **Keep #69 Puell independent-source validation blocked** pending independently published historical Puell observations and incremental-value gate.
4. **Keep #76 historical reconstruction and #89 threshold research isolated.** They are useful audit evidence but not substitutes for actual historically timestamped Production scores.
5. **#238 may be merged as a research-only audit artifact after CI review**, with no Production imports, dashboard changes, live portfolio writes, or notification changes. Research closure is acceptable without strategy promotion.
6. **Stop threshold tuning** until an independently timestamped source archive and meaningful sell-event OOS windows are available. Future experiments must report provenance and count actual sell events.

No claim is made about superior risk-adjusted performance versus BTC buy-and-hold. BTC volatility, deep drawdowns and sequence risk remain material.
