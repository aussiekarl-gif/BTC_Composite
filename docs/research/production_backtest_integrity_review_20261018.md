# Production V5.8.2 historical backtest correction — DRAFT, NOT MERGED

Date 18 Oct 2026. Review-only change to `engines/production/production_model.py`, `engines/production/production_app.py` **DCA Backtest mode only**. The actual DCA Today allocation formula, live price, V5.8.2 multiplier, Production risk indicator weights, live ntfy and all portfolio records must remain unchanged. This patch must not merge automatically.

## Why

Research PR #145 proved two correctness issues:

1. Historical `simulate_dca_backtest` discards all older observations at selected portfolio-start date before calling `add_risk_indicators`. Consequently a 180-period expanding risk percentile, SMA200, rolling valuation and 365-day position score can be computed from a truncated sample, creating artificially different first-period trading multipliers even for the SAME price date if the user changes only the backtest start date.
2. Historical `align_fx_to_dates` can `.bfill()` a known future FX date into older Bitcoin date, or assign USD0.70/AUD when the source was offline. A backtest cannot show verified AUD values based on a future or fictional exchange rate.

**Fix under review**:
- Compute Production `add_risk_indicators` once on the full BTC and risk-provider history available before the user-selected END date, including BTC fetcher prior 300-day warmup; trim to user-selected investment START only after risk indicators and calibration are computed. Use unchanged risk score function, interpolation curve, and execution weekdays.
- New `align_historical_fx_strict` helper for historical mode alone: strictly PRIOR exchange-rate date, max age 7 calendar days, no quotes from same day or future, no unstated default, malformed or unavailable source raises clear error. Request 310 extra prior days of Frankfurter FX to cover the 300-day BTC indicator warmup. Existing `align_fx_to_dates` remains untouched because DCA Today is not modified in this specific PR.
- In DCA Backtest mode show `st.error` and `st.stop()` for unavailable historical USD/AUD instead of continuing with misleading numerical profit and cents. Add a visible caption that **the existing retrospective entire-budget allocator still uses the SUM OF FUTURE risk weights** and is NOT the executable DCA Today remaining-cash/weeks-left policy.
- Original `apply_equal_capital_allocator` calculation left **intentionally unchanged**, so existing chart percentages can change from warmup and FX corrections but the budget allocation remains hindsight-optimised. A true causal cash-funded backtest must be a separate subsequent UI mode, not quietly substituted.

## Verification

New tests must confirm exact prev-day FX rather than future-day fill, fail-closed missing data, warmed score equality to full time-prefix computed same date, no recalculation of earlier risk when later BTC/MVRV changes, initial-score invariance to shifting the backtest START date, and same execution dates for Plain vs Smart. Existing #145 cause/FX audit tests revised only to reflect newly corrected warmup behavior. No changes to market-level Cycle Trading shared allocation.

**Do not merge this draft without a review of the changed historical backtest outputs and a basic Streamlit DCA Today regression.** In particular, rolling percentile state before the backtest has been fixed, but external MVRV/Fear & Greed historical point-in-time vintages and the retrospective weighted-budget normalization remain unverified. It would be wrong to call any newly displayed Smart DCA gain a true causal backtest.

**GitHub Actions [run 39119046429](https://github.com/aussiekarl-gif/BTC_Composite/actions/runs/39119046429) SUCCESS: 30 tests passed** (8 new Production FX/rolling-warmup tests, 12 original Production regression audits including corrected warmup and archived MVRV data caveats, 10 unchanged live Cycle Trading allocation tests). Compilation of BOTH Production model and Streamlit app succeeded.

**A first earlier GitHub run exposed and prevented a real error in the proposed FX helper**: it assumed pandas datetime integers were always nanoseconds, and failed to reject stale one-month-old FX rates when stored at microsecond precision. The corrected helper explicitly aligns all timestamps to the same resolution and calculates staleness using real pandas `Timedelta` objects. Full tests now assert 31-day-old FX is correctly refused and same-day/forward FX is forbidden.

Status: **Technical test gate PASSED, but branch still DRAFT and UNMERGED.** No application, live Production DCA Today, stored portfolio or ntfy rules have changed. Changes affect Historical Backtest view on merge only, and must be reviewed for historical performance differences because fixing indicator warmup can materially change displayed Smart DCA metrics. The existing future-total-weights equal-budget allocator remains retrospective and must not be called an executable forecast. No verified full historical provider vintages or actual ASX:IBIT historic trade records.
