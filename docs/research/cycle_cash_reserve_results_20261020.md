# BTC 200WMA conditional cash-reserve audit — numerical results 20 October 2026

**No live trading recommendation change. No November 2026 forced deployment.** User can preserve unspent AUD into 2027.

Source: [GitHub Actions #39379568612](https://github.com/aussiekarl-gif/BTC_Composite/actions/runs/39379568612). After replacing a non-binding synthetic test fixture with a deliberately prolonged discount path, **all 43 tests passed** (13 direct new reserve/cash floor tests, 12 existing conditional deep-value tests, 8 exact weekly BUY baseline tests, 10 current shared Cycle allocation tests). Full numerical BTC/USD+AUD FX historical and synthetic replay completed; source report archived in artifact `cycle-200wma-cash-reserve-protection-paper-audit`: `audit.json`, `historical.csv`, `synthetic.csv`.

## Result — a progressively released reserve is not dependable tail-risk protection

Original account A$400k hypothetical fresh AUD, original 2.5% of remaining cash only on prior below-200WMA BUY and last-executed 7d cooldown. The tiered 3.5%/5% larger-buy control and three reserve schedules share SAME original market BUY dates, but a cash floor can block orders when it binds. Portfolio terminal after illustrative FIFO SMSF accumulation CGT and account maximum drawdown are the relevant outcomes. Historical 11 overlapping 2017/2021/2025-26 entry windows are **not 11 independent cycles**; one 2025/26 sample is right censored through October 5. Eight synthetic further 50/70% fall cases are NOT probabilities.

| Policy vs actual 2.5% current sizing | Best historical whole-account return advantage | Mean historical across 11 overlapping starts | Worst synthetic account performance disadvantage vs actual 2.5% |
|---|---:|---:|---:|
| Tiered 3.5%/5%, no reserve | +8.901% | +2.635% | −7.465% |
| Tiered, 25% initial original-AUD reserve progressively released at deeper WMA discounts | +8.901% | +2.635% | −7.465% |
| Tiered, 40%→25%→10%→0% reserve | +8.901% | +2.419% | −7.465% |
| Tiered, 50%→25%→0% reserve | +7.310% | +1.832% | −7.465% |

All reserve choices converged toward the no-reserve strategy in the worst simulated decline. In the worst 70% forced-fall path, a deep enough price decline crosses the WMA discount thresholds and **unlocks the supposedly protected money**. The same simulated account drawdown of about **−49.62%** remains possible, leaving roughly 9.55% of original cash. For example, 2021 +650 entry with forced extra −70% decline, terminal only 55% of the pre-shock price:

| Policy | Whole-account terminal vs baseline | Maximum marked account drawdown | Original AUD cash left |
|---|---:|---:|---:|
| Tiered no reserve | −5.154% | −49.624% | 9.55% |
| Tiered 25% initial cash floor | −5.154% | −49.624% | 9.55% |
| Tiered 40→25→10→0 floor | −5.154% | −49.624% | 9.55% |
| Tiered 50→25→0 floor | −5.154% | −49.624% | 9.55% |

These are all *hypothetical cash-funded BTC spot daily-close fills in AUD*, not actual ASX:IBIT whole-share broker fills or user portfolio risk, and the calculations assume simplified immediate FIFO accumulation-phase SMSF tax and A$3 fees. No measured spread, cash interest, ETF basis, personal pension tax or timing premium is included. Models do not execute SELLs from an actual existing Bitcoin portfolio.

## Interpretation and research consequence

A reserve that is guaranteed to disappear merely because BTC falls far enough is **not a true backstop**. The experiment has successfully disproved that this specific staged-release scheme is robust to the chosen extreme synthetic path. It does **not** prove that ALL types of permanent or portfolio-volatility-based reserve are useless, nor that the true next low will mirror the artificial path.

Suggested next separate, post-results hypothesis: keep an irreducible 15–25% original-AUD dry-powder floor even in the deepest discount scenario, unless an explicitly independent, prospectively versioned risk rule warrants lowering it. That would mechanically prevent using the final reserve but might underperform strongly recovering BTC; match exposure, drawdown and terminal after-cost AUD fairly. Because this idea is informed by results already observed, it needs a new preregistered future cohort to validate, not reuse these historical scenarios as proof.

**Decision: DO NOT promote any conditional cash-floor variant.** Live 2.5% BUY, 7d cooldown, SELL stages, Production/Research versions, personal portfolio, daily ntfy and data tapes unchanged.
