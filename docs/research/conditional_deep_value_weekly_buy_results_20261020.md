# Results: conditional 200WMA deeper-value weekly BTC BUY sizing — 20 October 2026

**This is retrospective research, NOT a live strategy update, and NOT an out-of-sample improvement claim.** User's unspent AUD may remain in cash into 2027; no compulsory final purchases.

Source audit: [GitHub Actions run #39334491996](https://github.com/aussiekarl-gif/BTC_Composite/actions/runs/39334491996). **33 / 33 regressions passed** (12 new conditional replay checks; 8 existing exact 2.5%-remaining-cash weekly tests; 10 shared Cycle allocation tests; 3 prior 3%-challenger tests). The audit replayed 2017/2021 completed windows, 2025/26 price history **censored through 5 October 2026**, and 8 synthetic deeper-decline/recovery trajectories. Source outputs in GitHub Actions artifact `cycle-conditional-deep-value-200wma-weekly-buy-paper-only`: `full_research_audit.json` with all cash lots/orders, `historical.csv`, `adverse.csv`.

## Exact controlled experiment

All policies start with identical hypothetical fresh **A$400,000 uninvested cash**, never inherited Bitcoin holdings or invented sale proceeds. A market BUY is available only on a previous BTC close below the previous exact 200-week MA, and actual simulated purchase fills remain at least **seven calendar days** apart. At eligible fills only, conditional spending increases from existing **2.5% of REMAINING cash** to candidate 3%/3.5% when previous BTC close is at least 10% under previous WMA, or 5% when at least 20% under, or a tiered 3.5%/5% rule. All thresholds were selected after earlier research; the historical data have been repeatedly studied.

Fills use completed BTC/USD daily CLOSE, with strictly previous USD/AUD spot FX, A$3 per order and simplified FIFO accumulation-phase SMSF hypothetical terminal CGT. This is **NOT real ASX:IBIT broker execution**: weekends, ETF fees/tracking, whole units, bid-ask, taxes specific to this fund and FX execution costs are not represented. Neither actual personal purchases nor SELL stages were evaluated.

## Historical comparisons

The results below are percent change in the **whole illustrative terminal AUD portfolio after hypothetical full liquidation tax** versus the **unchanged 2.5% weekly BUY control**, NOT percentage change in Bitcoin itself. Each policy has 11 overlapping historical cohort starts: 4 from the 2017 window, 4 from 2021, and 3 right-censored 2025/26. These are **not independent holdouts**.

| Conditional purchase candidate | Historical maximum advantage | Historical average advantage across 11 overlapping cohorts | Worst tested synthetic terminal disadvantage |
|---|---:|---:|---:|
| 3.0% only when 10% below 200WMA | +2.276% | +0.761% | **−2.717%** |
| 3.5% only when 10% below 200WMA | +4.338% | +1.440% | **−5.183%** |
| 5.0% only when 20% below 200WMA | +8.262% | +2.299% | **−4.494%** |
| Tiered 3.5% below 90% WMA and 5.0% below 80% WMA | +8.901% | +2.635% | **−7.465%** |

**All 2017 and right-censored 2025/26 cohort candidate differences were exactly 0.000%**, because no increased-size condition actually occurred on eligible fills. Positive historical effects occurred only in the previously researched 2021 cohort (four overlapping enrolment-date scenarios). The averages should not be interpreted as statistical returns or future expected value.

Selected 2021 retrospective illustration:

| Fresh-cash entry after 2020 halving | 3% /10%-deep | 3.5% /10%-deep | 5% /20%-deep | Tiered 3.5%/5% |
|---|---:|---:|---:|---:|
| Halving +650 days | +1.923% | +3.602% | +5.046% | +6.116% |
| Halving +900 days | +2.246% | +4.338% | +8.262% | +8.901% |

The best terminal results reflect additional BTC held when the historic market eventually recovered. They do not establish a better prediction of the actual bottom; a cheap price can become much cheaper.

## Downside risk and why we are NOT deploying

Our existing synthetic bear tests extend actual 2017/2021 historical prefixes by further 50%/70% forced BTC/USD drops and different subsequent terminal recoveries. These are predeclared stress paths, not probability assignments.

For the 2021 +650 cash start with a subsequent **70% synthetic additional drop** ending at 55% of the pre-shock reference price:
- 3%/10%-deep candidate: **−2.015%** versus current aftertax terminal whole account; simulated maximum marked drawdown **−42.80%**
- 3.5%/10%-deep: **−4.133%**, drawdown **−46.01%**
- 5%/20%-deep: **−1.021%**, drawdown **−46.54%**
- Tiered 3.5%/5%: **−5.154%**, drawdown **−49.62%**, leaving only **9.55% original cash**.

Elsewhere the worst terminal relative disadvantage across all eight forced paths was **−7.465%** for tiered sizing. These figures illustrate that slightly higher portfolio terminal value in recoveries can come with extreme 40–50% account drawdowns and very low retained cash; no candidate reliably dominates unchanged 2.5% in both return and downside. The baseline's detailed lot-level outputs are preserved in the JSON.

## Decision

**Do not change live BUY percentages.** Do not force capital deployment by November 2026, a 2027 checkpoint or the end of a fixed 20-week DCA benchmark. Preserve all untouched Production V5.8.2, Research V5.9, Cycle Trading SELL percentages, live Streamlit BUY 2.5%, user portfolio and one daily ntfy.

Further work worthy of consideration:
- Count prospectively captured deep-value 200WMA events after 20 October 2026; the existing genuine forward ASX:IBIT daily-close benchmark and mid-session study start there. No post-hoc threshold selection from those future results.
- Only if genuine future evidence develops, test broker-executable ASX:IBIT AUD prices with spreads/fees, cash yield, whole units, Australian SMSF tax phases, and matched market exposure.
- Evaluate alternative capital-budget controls designed for multiple lower BTC lows, especially preventing excessive cash exhaustion in synthetic extended bear paths, before granting any live change.

**Model winner proved: NO. Live model or ntfy changes: NONE. New paid data or recurring schedule: NONE.**
