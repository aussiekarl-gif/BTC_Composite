# Production V5.8.2 strategic review — 18 October 2026

**Status: Research only, no change to original engine/UI or live recommendation.**

User's complaint is substantive: Production V5.8.2 has not been comprehensively re-benchmarked since many later BTC Cycle, fee, audit-vintage and cash-only deployment experiments. Its historical allocation differs from the current "DCA Today" sizing.

## Verified code-level findings before running historical numerical test

1. `engines/production/production_app.py` historical "Simple DCA Backtest" calls `simulate_dca_backtest`, then `apply_equal_capital_allocator`. The latter **knows all weights through the chosen future backtest terminal** before sizing the earliest purchase: `weights / weights.sum() * entire_budget`. It is a *retrospective equal-capital* comparison, not a possible forward deployment of capital. Example two historical weights 1,2 on a A$1200 budget allocate first trade A$400, but append a later weight 3 and *the same old first trade is silently revised to A$200*. It is not a causal trading result. We directly test this exact code.
2. "DCA Today" instead computes `remaining_capital_aud / max(days_until_selected_target /7,1) * interpolate(SMART_DCA_POINTS, today's completed-day risk_score)`, capped by remaining cash. These are **different strategies**; 2017/2021 clever Smart DCA weights do not establish the live DCA Today strategy outperformance.
3. The historical backtest `simulate_dca_backtest` filters `df_full` to the selected trading start **BEFORE** calling `add_risk_indicators`, which may drop required calibration/indicator warmup even when `fetch_btc_history` had fetched a 300-day lookback. This can change early risk scores depending on the selected start range and temporarily revert to a neutral multiplier. Distinguish necessary existing indicator warmup from genuine future leakage.
4. `align_fx_to_dates` uses a **fixed USD0.70 per AUD fallback** if historical currency data are missing, and `.bfill()` can insert a currency observation **after** the BTC execution date for early dates. Both are unverified valuation; historical AUD results require dated preceding FX and must otherwise fail closed.
5. The Production composite uses fixed power-law slope/intercept 5.84 and −17.01, valuation + MVRV + price position + Mayer + Fear & Greed + RSI with rolling-percentile calibration. Long-term calibration and provider revisions need an independent vintage audit. `BTC_Composite` October-2026 archived MVRV values are not authenticated earlier-vintage observations; historical Fear & Greed unavailable in this replay.
6. The currently displayed risk “default walk-forward-tested V5.8.2 Smart DCA curve” uses a fixed interpolated 2.75 at risk zero, 0.05 at risk one. The curve's future utility is not established from two completed market cycles. Retrospective chart allocators may make these weights appear more optimal than they are.

## Frozen audit method (NOT claimed true 2017 production vintages)

Use unchanged `engines.production.production_model.add_risk_indicators` with same default Production valuation and calibration constants, BTC/USD daily archived prices and archived dated **MVRV-Z**; **unavailable Fear & Greed is kept missing**, not imputed. Strict daily observations through 5 Oct 2026. This creates a *Production composite proxy*, not exact historic complete Production risk scores. Portfolio cohorts start entirely in A$400,000 cash at halving+650/+750/+850/+900 in 2017/2021 complete to +1150, or latest archived close in 2025/26 right-censored; no historical owned BTC or 2025 SELL proceeds.

Each account executes once every **seven calendar days** starting start+1 at the BTC/USD close priced with strictly preceding-date AUD/USD FX; fees A$3 per fill; simplified FIFO accumulation SMSF tax on hypothetical terminal sale:
- **Live causal formula:** risk score **from T−1**, risk-weight curve unchanged; buy min(cash, remaining_cash / max(days_until_FIXED calendar end/7,1) × that prior-known weight), no future price/score, no pre-known sum of weights.
- **Production historical hindsight allocation:** exactly same dated multipliers normalised against their total over ALL future dates, sum contributions A$400,000. Explicitly **unavailable to actual investors on earliest buy dates**.
- **Ordinary calendar weekly DCA:** A$400,000 divided equally among known weekly scheduled dates; transparent opportunity-cost baseline.

No SELL strategy here because Production Smart DCA "Simple DCA Backtest" is accumulation only. Later compare full sell policies separately. Report BTC accumulated, cash left, aftertax AUD at fixed terminal, fees and drawdown, plus exact orders. This is more honest than claiming the retrospective original backtest is validated 2026 advice.

## Promotion requirements

Re-test true Production source-freshness and FX provenance, provide a **causal no-future-cash-allocation benchmark**, ensure first periods have full indicator warmup, compare actual 2026 cash cohorts and ASX:IBIT weekday pricing/spreads/tax. Fix any mechanical source errors under a distinct reviewed PR if needed; do not change V5.8.2 weights/percentages based on these already-inspected history windows alone.

Result: PENDING verified CI, recorded when complete.
