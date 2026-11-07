# V5.9 ordinary DCA runway-cap comparison — preregistered research plan

Status: RESEARCH ONLY. No production, Cycle Trading, notification, or trading-policy change.

## Verified code discrepancy
DCA Today computes raw risk_weight from the selected R2 curve, then sets paced_risk_weight = min(risk_weight, 1.0). Without a newly eligible Exceptional Bottom event, the displayed weekly purchase uses this capped weight. The existing DCA Backtest calls simulate_dca_backtest with the selected risk_curve; it is not evidence for the exact live runway-capped policy.

## Locked candidate policies
A. Control: existing ordinary multiplier min(raw_weight, 1.0), with existing exceptional event override.
B. Challenger: min(raw_weight, 1.5), with the same event rule.
C. Challenger: min(raw_weight, 2.0), with the same event rule.
D. Diagnostic only: uncapped raw curve, clearly separated from deployable recommendation.

Each policy spends min(deployable capital, base weekly allowance × effective multiplier), where base allowance = (remaining capital - preserved reserve) / max(weeks to selected review date, 1). Recompute after each simulated buy. Do not invent or backfill event signals. When point-in-time Exceptional Bottom evidence is unavailable, compare ordinary sizing alone and explicitly label the exclusion.

## Required validation
- Use identical initial AUD capital, actual starting deployment date, remaining capital, protected reserve, review date (flexible into 2027), execution weekday, BTC/AUD conversion, fees, slippage, and BTC price feed.
- Prevent future-data leakage: only closed observations available before the simulated order may affect the risk score; preserve historical data vintages where available.
- Run chronological historical periods including bear-market continuation, recovery, and prolonged expensive markets; report out-of-sample results and independent regime counts.
- Report total BTC acquired, ending AUD equity (BTC plus cash), unspent cash, worst drawdown, weekly orders, transaction costs, percentage of capital deployed, and the date capital is exhausted.
- Include matched plain DCA and frozen existing strategy baselines. No comparison may use a different capital schedule or date.
- Stress missing risk observations, price gaps, very low risk persisting for months, late target-date edits, and protected reserves.
- Explicitly test dashboard/backtest parity for the selected policy before making any live recommendation.

## Current evidence and decision
Screenshot example: base A$14,593, raw risk multiplier 2.00x, effective capped multiplier 1.00x. Illustrative weekly amounts: 1.0x A$14,593; 1.5x A$21,889.50; 2.0x A$29,186. These are not backtested returns or advice.

No matched numerical results have yet been produced by this plan. Do not claim 1.5x or 2.0x is superior. Keep current 1.0x policy unchanged until reproducible after-cost tests show durable benefit without unacceptable early cash exhaustion.