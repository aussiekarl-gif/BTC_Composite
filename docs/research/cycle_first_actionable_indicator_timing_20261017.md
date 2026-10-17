# Bitcoin Cycle indicator and execution timing: first actionable alerts, not hindsight picks
17 October 2026 | Research only | PR #132

## Reason for change in priority

Manual BTC/IBIT entries are adequate for now. The critical research question is whether our **existing entry/exit signals occur early enough and consistently enough to improve returns WITHOUT hindsight**. This audit freezes the historical original **halving-day500 staged SELL** and **post-day744, first strict previous-close below previous 200WMA / thereafter weekly adaptive-recovery BUY**. It separately audits the already-defined classic MVRV/NUPL, Pi Cycle Top, relative euphoria and price/maturity alerts.

**No new thresholds, parameter optimisation, broker imports, portfolio writes, Streamlit or ntfy trading rule changes.**

Earlier `top_signal_horse_race.evaluate_alerts()` reports the **retrospectively nearest** alert to each eventual peak for its peak-score diagnostic. That is a legitimate descriptive post-hoc metric, but not the alert an investor could prospectively choose. Our new audit instead reports the **FIRST** actual actionable alert within a fixed, known halving-age window, day350–800, even if that alert is far too early. It also reports the **absence** of a signal rather than filling a perfect hindsight alert.

## Original strategy historical SELL and BUY timing

The peak is the highest observed BTC/USD daily close between confirmed halving+350 and +800, chosen ONLY at retrospective score time. The low is the lowest observed BTC/USD daily close from halving+744 to the cohort's available terminal (day1150 in 2017/2021, last archived 5 Oct 2026 in 2025/26). The top and low are NEVER used to generate orders or pick alerts.

The % of peak is USD **original-BTC-weighted average SELL close divided by the eventual peak close** (100% of original BTC was sold by the day730 window in all three inspected synthetic initial-position scenarios). The buy-price error is USD **harmonic VWAP** weighted by portions of a fixed original aftertax cash budget; actual historic AUD/USD exchange rates, brokerage, SMSF CGT and ASX:IBIT spread/whole-unit effects are excluded from this TIMING-ONLY audit.

| Historic BTC cycle | Peak close and date in fixed +350–800d window | Original SELL VWAP vs peak close | % original BTC sold BEFORE eventual peak | Strict 200WMA BUY activation | First BUY vs hindsight low | USD BUY VWAP above eventual low |
|---|---|---:|---:|---|---:|---:|
| 2017 | US$19,187.78, 16 Dec 2017 | **75.55%** | **5.00%** | 16 Dec 2018 | 1 day **after** | **+18.63%** |
| 2021 | US$67,559.00, 8 Nov 2021 | **87.86%** | **64.79%** | 15 Jun 2022 | **159 days before** | **+27.09%** |
| 2025/26* | US$124,728.00, 6 Oct 2025 | **88.27%** | **50.00%** | 6 Jun 2026 | **24 days before** | **+20.17%*** |

*2025/26 after-halving day1150 BUY observation is **right-censored**. The observed price low through 5 Oct 2026 is not necessarily the eventual bear-market low. Earlier 2017/2021 cycles were already studied in model development, so even 2017's strikingly accurate low proximity is NOT evidence of expected future accuracy.*

The results identify two distinct issues:

1. **SELLs:** 2017 original staging sold only 5% before the eventual top and averaged 75.55% of top price despite selling 100% of its original position by the window close. The 2021 and 2025 sell schedules distributed more of the position before peak and reached 87.86% and 88.27% of observed peak respectively. Timing can differ sharply despite unchanged halving-based rules.
2. **BUYs:** 2017 buy activation followed the eventual low by one day, a particularly favorable observed case. In 2021 it triggered **159 days before** the eventual trough. The weekly adaptive BUY weights must therefore be evaluated as a *path* with residual cash and multiple fills, not just judged by first signal date. 2025/26 remains incomplete.

## First actionable TOP warnings: real-time usability

These are the FIRST alerts after halving+350 of the **original already-defined indicator families**, NOT whichever recorded alert was closest to the known peak. An early warning may have been contradicted by subsequent price action, and this table is not a verified predictive trade recommendation.

| Indicator family | 2017 first alert vs 16 Dec peak | 2021 first alert vs 8 Nov peak | 2025 first alert vs 6 Oct peak |
|---|---|---|---|
| **Classic euphoria (MVRV Z ≥7 or NUPL ≥0.75)** | 2 Dec 2017 (14 days early) | **None** | **None** |
| **Pi Cycle Top cross** | 17 Dec 2017 (1 day late) | **None** | **None** |
| **Relative MVRV/NUPL euphoria** | 24 Jun 2017 (175 days early) | **None** | **None** |
| **Halving-maturity warning / near 52-week high** | 24 Jun 2017 (175 days early) | 26 Apr 2021 (196 days early) | 5 Apr 2025 (184 days early) |
| **Price trend reversal** | 31 Jan 2018 (46 days late) | 13 May 2021 (179 days early) | 10 Apr 2025 (179 days early) |
| **Maturity warning followed by reversal** | 13 Jun 2018 (179 days late) | 8 Jan 2022 (61 days late) | 21 Nov 2025 (46 days late) |
| **Late trend break** | 2 Feb 2018 (48 days late) | 18 May 2021 (174 days early) | 21 Nov 2025 (46 days late) |

**Interpretation:** Day350 maturity warning is often very early, not a sufficient SELL trigger. Classic euphoria appears timely in 2017 but **does not alert** at all in 2021 or 2025. Pi-top cross likewise appears only in 2017 in these scored windows. A first trend-reversal alarm in 2021 was premature because BTC later made another high. Adding warning indicators without checking false early alerts and missed cycles can make SELL timing worse, not better.

Onchain historic MVRV/NUPL/SOPR values were downloaded in October 2026; their **original realtime publication vintages are not validated**. Calculation of T signals with T−1 closes avoids **arithmetic future leakage** but does not prove those specific indicator readings were known to historical traders in identical form, and parameter definitions were influenced by earlier inspected history.

**Important indicator terminology:** the historical `top_signal_horse_race.py` has a prior **200-DAY** average as one supporting top-indicator feature, which is NOT our original **200-WEEK** recovery-buy gate. We retain both under their intended names, not silently interchange them.

## Execution delay sensitivity of frozen original SELL decisions

Keeping EXACT same staged original-BTC fractions and date signals, reprice the sell executions at BTC close +0/+1/+3/+7 calendar days. **Do not use delayed close to reselect an event or hindsight-optimize dates**. It is price slippage sensitivity only, NOT a complete broker/FX/tax wallet rerun or forecast of real ASX trading hours.

| Cycle | Day0 original SELL USD VWAP | +1d | +3d | +7d |
|---|---:|---:|---:|---:|
| 2017 | $14,495.89 | $14,445.29 | $14,154.89 | **$13,133.94** |
| 2021 | $59,359.11 | $59,565.12 | $58,686.76 | $59,542.54 |
| 2025/26 | $110,091.68 | $111,761.15 | $110,107.52 | $108,491.07 |

In 2017, seven-day delayed execution reduces original weighted sale price approximately **9.4%** versus no delay. In 2021 and 2025/26 it did not have the same dramatic effect. Delays are NOT uniformly good or bad — they add uncertain slippage to an already uncertain signal. Weekend/holiday IBIT constraints can worsen practicality, so the original same-day daily-close execution assumption is optimistic.

## Conclusions and next experiments — in priority order

1. **Preserve immutable indicator definitions and inspect warning errors.** A signal that first fires six months early must not be relabelled a near-top SELL after selectively choosing a later alert. Missing classic euphoria / Pi alerts cannot be imputed from future prices.
2. **Evaluate multi-stage SELL confirmation as a separate frozen experiment.** Compare the original staged calendar SELL to first true contemporaneous trend-break confirmations, including false early reversals and 1/3/7-day delays, using the SAME matched original BTC/cash accounting, original units, fees and after-tax AUD ending wealth. Do not pick the best threshold or nearest historical peak.
3. **Investigate BUY amount/timing after initial 200WMA trigger**, especially 2021's 159-day early activation, residual cash, maximum drawdown and final BTC units. Any signal refinement should be tested prospectively and across adverse delayed-bottom conditions, not just lower average entry price.
4. **Prove data vintage, price/FX date and real ETF execution constraints** before changing Streamlit/ntfy. The live simplified BUY and SELL rules still differ from the original historically backtested policy. The user's personal 2026 acquisitions have no retrospective 2025 SELL cash.

Only two complete modern cycles and multiple historically selected thresholds mean no true external validation. A favorable past SELL-price/peak ratio or BUY-price/low ratio does not imply an achievable forward profit multiplier.

## Reproducibility

- Frozen timing-only engine: `engines/research/cycle_indicator_timing_audit.py`
- Synthetic first-alert and strict-prior-WMA tests: `tests/test_cycle_indicator_timing_audit.py` (10 tests)
- Unchanged original policy tests: `tests/test_shared_cycle_policy.py` (8 tests)
- CI: `.github/workflows/cycle_indicator_timing_audit.yml`
- GitHub Actions artifact `frozen-cycle-indicator-timing-audit` stores every original dated SELL/BUY event, each existing first top-indicator alert and execution-lag sensitivity.
- Live Production V5.8.2, Research V5.9, Streamlit, daily ntfy and Google Sheets trades **unchanged**.
