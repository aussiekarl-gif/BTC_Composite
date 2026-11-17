# BTC risk-band ladder comparison — 17 November 2026

**RESEARCH ONLY. No Production V5.8.2, live Research V5.9, Cycle Trading, dashboard signal, portfolio, Google Sheet, Stake order or notification changes.**

## Policies compared

All external multiplier ladders are applied to the same project-generated **V5.9 Research WF Power Law** risk score. This is a controlled comparison of multiplier schedules, **not a replication of Benjamin Cowen's proprietary Total Indicator Risk metric**.

| Risk score | User screenshot | Cowen historical (2023 explanation) | Cowen 2026 reported |
|---|---:|---:|---:|
| 0.00–0.09 | 16× | 5× | 4× |
| 0.10–0.19 | 8× | 4× | 3× |
| 0.20–0.29 | 4× | 3× | 2× |
| 0.30–0.39 | 2× | 2× | 0× |
| 0.40–0.49 | 1× | 1× | 0× |
| 0.50+ | 0× | 0× | 0× |

The Cowen historical ladder is transcribed from his 8 February 2023 Total Indicator Risk video transcript. The 2026 ladder is from a secondary summary of his 14 June 2026 video; it is not an official machine-readable specification. The user's screenshot is the source for the 16× ladder. All multiplier definitions are explicitly research hypotheses when applied to this project's score.

## Source attribution note: Digital Asset News

The public Digital Asset News transcript indexed for its dynamic-DCA explanation describes a different example: ordinary 1x at risk 0.50–0.59, 2x at 0.40–0.49, then 4x / 8x / 16x as risk falls further. It does not give a precise numeric multiplier for the 0.00–0.09 band in the available transcript. That is **not identical to the supplied screenshot**, which labels 0.50+ as 0x and 0.00–0.09 as 16x. Accordingly, this report treats the screenshot ladder as a separate image-transcribed research hypothesis and does not attribute it as an exact official Digital Asset News rule.

Transcript reference: https://podprose.org/post/1572/digital-asset-news-bitcoin-dead-cat-bounce-why-i-doubled-transcript

## Backtest and execution assumptions

GitHub Actions run: https://github.com/aussiekarl-gif/BTC_Composite/actions/runs/44032627044

- 516 matched weekly rows, 2017–2026; 16 completed 104-week Jan/July cohorts: 7 TRAIN, 3 BRIDGE excluded from selection, 6 historical holdouts.
- Signal: prior Sunday UTC close and prior-Sunday reconstructed risk. Proxy execution: following Monday BTC/AUD spot reference using lagged AUD/USD FX.
- A$510,000 initial portfolio; comparison includes both 100% new AUD and a separate 41% virtual existing-BTC / 59% AUD cash sensitivity.
- Cash earns illustrative 5% annual pretax; A$3 fixed cost, 0.30% variable buy friction, 0.25% annual ETF-like holding drag.
- Maximum ordinary weekly purchase remains 5% of initial capital = A$25,500. Multipliers above the cap are clipped by the budget constraint. No leverage, no sales.
- Six holdout cohorts overlap and are not independent market cycles. The risk series is recalculated retrospectively from public prices; historical as-published provider vintages are not independently verified. Execution is a BTC/AUD spot proxy, not an executable ASX:IBIT fill.

## Results — six historical holdout cohorts, 5% cash yield, no separately protected reserve

Relative to the same risk-gated 1× benchmark. Values are median cohort results; BTC-equivalent and total-equity uplifts coincide in this configuration.

| Policy | Median uplift vs risk 1× | Positive cohorts | Worst cohort | Median drawdown change |
|---|---:|---:|---:|---:|
| Existing V5.9 risk 3× | +20.63% | 5/6 | −3.25% | −3.92 pp |
| Existing V5.9 3× only at risk ≤0.20 | +19.66% | 6/6 | +3.16% | −1.84 pp |
| Screenshot 16× ladder | **+36.26%** | **6/6** | **+4.95%** | **−7.98 pp** |
| Cowen historical 5× ladder | +30.81% | 6/6 | +0.36% | −5.32 pp |
| Cowen 2026 reported ladder | +27.14% | 6/6 | +2.06% | −4.52 pp |

## Existing BTC exposure sensitivity — 41% virtual BTC / 59% AUD cash

This approximates the user's broad current asset split, but is not a reconstruction of actual Stake holdings or fills. Results are relative to the risk-gated 1× benchmark on the same cohort.

| Policy | Median total portfolio uplift | Positive cohorts | Worst cohort | Median drawdown change |
|---|---:|---:|---:|---:|
| Existing V5.9 risk 3× | +11.05% | 5/6 | −1.82% | −3.26 pp |
| Existing V5.9 3× only at risk ≤0.20 | +11.22% | 5/6 | −0.29% | −1.81 pp |
| Screenshot 16× ladder | **+18.87%** | **6/6** | **+1.92%** | **−6.00 pp** |
| Cowen historical 5× ladder | +14.73% | 6/6 | +0.20% | −5.02 pp |
| Cowen 2026 reported ladder | +12.95% | 6/6 | +0.51% | −3.12 pp |

The 16× screenshot policy's median relative uplift was about 7.82 percentage points above the current 3× policy in this existing-exposure sensitivity. It deployed a median 59.7% of initial capital as new cash purchases, versus 60.8% for Cowen's historical ladder, 60.5% for the 2026 reported ladder, and 60.8% for the current 3× policy.

## Interpretation

The screenshot ladder is the strongest retrospective candidate in this specific matched sample. It also front-loads spending: in the 100%-new-cash holdout, its median first-26-week spend was 81.7% of initial capital, compared with 45.6% for the existing 3× policy. This is consistent with the high multipliers frequently hitting the A$25,500 weekly cap. The results therefore reflect both timing and faster capital deployment; they do not isolate superior bottom prediction.

These are overlapping, retrospectively reconstructed cohorts and a risk series that is not Cowen's own. They do not prove prospective alpha, actual ASX:IBIT execution returns, or that the screenshot ladder will work in a future bear market. A 30–50% continued BTC decline after early purchases could materially change the result. No strategy promotion is justified.

## Research decision

Keep all three external ladders as **paper-only comparisons**. Extend the test with:
1. Same-policy comparisons under a protected cash reserve and 0% / 5% cash yield.
2. Severe false-bottom paths after the first low-risk signal, including another 30%, 40% and 50% decline.
3. Entry price, BTC units, remaining AUD, portfolio equity and drawdown reported separately.
4. Prospective forward observations using the existing immutable tape; do not backfill missing risk-score vintages.
5. After-cost ASX:IBIT matched quotes once adequate genuine prospective observations exist.

No live model, risk threshold, buy size, notification or portfolio setting is changed by these findings.
