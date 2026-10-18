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

Result: Initial matched audit completed; follow-up source-safety regression run below.


## Numerical matched evidence — initial CI success 18 October 2026

**[GitHub Actions run 39116666689](https://github.com/aussiekarl-gif/BTC_Composite/actions/runs/39116666689) passed** (10 new Production research tests and 10 existing Cycle percent-allocation tests). Full dated per-BUY account transactions and cohort scores: [artifact 12133045686](https://github.com/aussiekarl-gif/BTC_Composite/actions/runs/39116666689/artifacts/12133045686). Final new FX/backfill and indicator-warmup regressions follow in next run.

**Figures below are differences in hypothetical terminal after-tax AUD value**, not realised investor gains, annual percentage returns or probabilities of future success. The 'causal' model is the DCA Today **remaining AUD cash / weeks to a FIXED calendar end × current multiplier** formula replayed with **strict prior-date risk**, not necessarily the user's existing target date or actual SMSF ledger. The legacy chart strategy is hindsight-normalised against future total weights, not a comparable executable strategy.

| Full or incomplete cycle | Cash start halving+day | Causal production-style vs equal weekly | Hindsight chart vs equal weekly | Causal vs hindsight chart | Causal BTC held | Causal cash left |
|---|---:|---:|---:|---:|---:|---:|
| 2017 COMPLETE | 650 | **+9.739%** | +15.620% | −5.086% | 54.15235875 | 0% |
| 2017 COMPLETE | 750 | **+13.509%** | +16.904% | −2.904% | 58.61190885 | 0% |
| 2017 COMPLETE | 850 | **+22.643%** | +20.310% | **+1.940%** | 66.78535058 | 0.46% |
| 2017 COMPLETE | 900 | **+27.670%** | +23.921% | **+3.025%** | 67.21894862 | 0% |
| 2021 COMPLETE | 650 | **+0.886%** | +4.404% | −3.370% | 11.44524878 | 0.01% |
| 2021 COMPLETE | 750 | **+5.382%** | +2.955% | **+2.357%** | 12.95565292 | 0% |
| 2021 COMPLETE | 850 | **+9.207%** | +3.475% | **+5.539%** | 13.46881359 | 0% |
| 2021 COMPLETE | 900 | **+12.121%** | +4.135% | **+7.669%** | 13.64083202 | 0% |
| 2025/26 RIGHT-CENSORED | 650 | +0.965%* | +0.872%* | +0.092%* | 4.04037360 | 0% |
| 2025/26 RIGHT-CENSORED | 750 | +3.142%* | +1.297%* | +1.821%* | 4.13864585 | 0% |
| 2025/26 RIGHT-CENSORED | 850 | +3.459%* | +0.598%* | +2.844%* | 3.79935816 | 0% |

*Only through Oct 5 2026, with no observed future low/end-of-cycle. Multiple cohorts in the same cycle heavily overlap and cannot be construed as 8 independent samples.*

**Main result:** Causal Production-like weighting BEAT equal weekly cash DCA in ALL 8 retrospectively scored completed modern starts using this **partial Production composite proxy**, by +0.886% to +27.670% final aftertax AUD. The original omniscient chart comparator beat ordinary equal weekly by +2.955% to +23.921%; however, it beat the actual causal calculation in just 3 of 8 completed starts and LOST in 5 of 8. That shows the Production risk weighting has plausible value, while its existing advertised chart performance does not directly represent DCA Today trades.

**Evidence limitation is material**: onchain MVRV-Z exported in Oct 2026 may have retrospective revisions, historic Fear & Greed was excluded, and the fixed deployment-end date is chosen here solely to match test horizons. Future live full-input score, next ASX:IBIT fills, safe FX handling and future-cycle robustness are not established. Do NOT retune Production weights or overclaim validated DCA Today 'alpha' from these rows.

### Findings by priority

- **High: Historical budget normalisation uses unknown future weights.** Need a separate labelled causal historical backtest with cash balance and fixed selected deployment target; never rewrite past funding based on a later data point.
- **High: Historical FX interpolation / fallback allows unverifiable AUD results.** Future FX can be used for dates preceding the earliest quote via `.bfill()`, and missing FX defaults to USD0.70/AUD. For official backtests, fail closed instead, and for UI choose explicit stale/unavailable rather than present as verified result.
- **Medium-high: Backtest selected start truncates indicator warmup before recomputation**; a long older series is fetched but thrown out before computing risk. An honest historical risk backtest must fully warm rolling features and prior percentile state before trimming to BUY dates.
- **High: Retrospective indicator data vintage.** MVRV etc may have changed since each date. Prospective version-stamped provider input tapes (like new Cycle signal recorder) are necessary before a model revision claim.
- **Medium: DCA Today shows a live spot price for display but uses prior completed UTC close for risk; keep this distinction and do not backfill weekend ASX orders at BTC closes.**
- **Future: Revisit curve 2.75x at risk0, 0.05x at risk1 with independent cohorts, but only after apples-to-apples corrected causal backtest and live-executable AUD/IBIT fees/tax.** 3%/3.5% Cycle market BUY sizing result is a SEPARATE strategy and cannot be transplanted directly into Production's risk-weight multiplier.

**Decision: preserve Production V5.8.2, data, ntfy and Streamlit unchanged; retain numerical audit and prioritise separate, narrowly scoped safety/parity fixes before optimizing weights.**
