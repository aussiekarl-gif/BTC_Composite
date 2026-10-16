# BTC 200WMA: fair after-tax exit and adaptive execution cost research
**Verified:** 16 October 2026 (Australia/Brisbane)  
**Research only:** neither Production V5.8.2 nor frozen prospective VBTC v1 may be changed by these exploratory comparisons.

## Validation and source links
- [Matched final liquidation and adaptive BTC run](https://github.com/aussiekarl-gif/BTC_Composite/actions/runs/38822949971), success, artifacts `aud-btc-fully-liquidated-fair-exit`, `aud-btc-adaptive-sell-reentry-challengers` and verified 2015–2026 AUD/FX source snapshot.
- [Symmetric execution-cost stress](https://github.com/aussiekarl-gif/BTC_Composite/actions/runs/38829353001), success; `aud-btc-fair-exit-execution-cost-stress` artifact and the same matched final-liquidation tests.
- [Rapid Research invariant tests](https://github.com/aussiekarl-gif/BTC_Composite/actions/workflows/research_200wma_fast_safety.yml) cover the underlying paper simulation and frozen Research workflow.

## Accounting correction — important

Earlier results used a partly unfair comparison: the trading strategy paid estimated realised SMSF CGT, but the DCA comparator had no assumed final disposition of its still-unrealised BTC ETF holdings. We now **liquidate both at the same final BTC/AUD price and date** and charge:
- the same A$20 fixed brokerage, 0.1% proportional dealing fee and tested execution slippage to each final ETF sale;
- FIFO illustrative 15% accumulation-phase SMSF tax on each final disposal, including the one-third discount for qualifying long-held gains and carried capital losses;
- earlier first-week-of-July CGT settlements on gains realised by the trading strategy, as an intentionally conservative timing stress;
- identical hypothetical BTC/AUD ETF management-fee price drag of 0.45% annually.

These are modelling assumptions, **not actual Australian ETF tax returns or broker-confirmed fills**. No distributions, AMIT attribution, mixed accumulation/pension ECPI, actuarial tax, fund expenses beyond MER, or personal circumstances are included.

### Matched after-tax baseline: 4-week-spaced starting cohorts

| Fixed holding | Uncorrected median excess vs DCA | Corrected median | Corrected worst | Corrected winners |
|---|---:|---:|---:|---:|
| 2y (104 weeks), 89 correlated starts | +2.402% | **+4.257%** | −55.288% | 57/89 |
| 3y (156 weeks), 76 correlated starts | +26.304% | **+30.070%** | −47.953% | 48/76 |
| 4y (208 weeks), 63 correlated starts | +33.099% | **+38.414%** | −23.718% | 55/63 |

Comparing uncorrected to corrected medians is a **tax-accounting difference**, not newly generated economic alpha.

### Adaptive hypotheses, corrected final liquidation

| Model | 2y median | 2y worst | 3y median | 3y worst | 4y median | 4y worst |
|---|---:|---:|---:|---:|---:|---:|
| Original 12w buy / 16w sell | +4.257% | −55.288% | +30.070% | −47.953% | +38.414% | −23.718% |
| **Weakness-confirmed sell gate** (5% below trailing 8-week high) | +4.038% | −47.545% | +28.111% | −42.463% | **+46.372%** | −19.204% |
| 8-week momentum breakout cash reentry | +3.679% | −44.883% | +23.631% | −41.689% | +34.565% | −18.524% |
| Both weakness sell gate and breakout reentry | +2.588% | −38.350% | +16.978% | −38.584% | +37.909% | −15.913% |
| 40% cash cap plus breakout reentry | +1.822% | **−26.827%** | +10.105% | **−26.008%** | +12.712% | −13.083% |
| **26-week idle cash recycling** | **+5.119%** | −44.142% | +25.086% | **−38.254%** | +40.377% | **−13.426%** |

*Wins for the two most important four-year cases*: 55/63 original, 57/63 weakness gating, 61/63 idle recycling. All sample periods overlap; their counts are not independent economic cycles.

**What the weakness guard actually does:** a tier crossing schedules a 16-week sell order, but a fill only occurs when the *previous completed* weekly BTC close is 5% or more below that same completed-week trailing 8-week high. If that weakness never occurs within the order's 16-week life, the unfilled tier sell expires, rather than being forced later. Median completed four-year sell fills dropped from 186 to 88. This reduces fee-bearing turnover, but also creates the risk of selling later at lower prices during a sharp correction. It is **not** a mathematically validated top detector.

**The short-term problem remains:** 2019 two-year starts have −26.164% median versus DCA on the original model, −17.843% on the weakness guard, and −22.311% with idle recycling. For 2023 starts those values are −9.547%, −10.656%, and −7.894%. None shows reliable immunity to entire weak market periods.

## Higher execution slippage: independently matched 8-week-spaced cohorts

This is a **different, thinner subset**: 45 overlapping two-year starts and 32 overlapping four-year starts. Do not directly combine its medians with those above.

| Model | 2y median at 0.5% slippage | 2y median at 2% slippage | 2y worst at 2% | 4y median at 0.5% | 4y median at 2% | 4y worst at 2% |
|---|---:|---:|---:|---:|---:|---:|
| Original | +2.615% | +2.023% | −56.648% | +39.709% | +34.966% | −24.747% |
| Weakness-gated sells | +4.475% | **+4.234%** | −49.426% | **+45.770%** | **+42.059%** | −21.187% |
| Momentum reentry | +3.182% | +2.385% | −47.692% | +33.966% | +26.296% | −21.778% |
| 26-week cash recycling | **+4.985%** | +4.159% | **−43.092%** | +37.807% | +31.920% | **−16.000%** |

All fee/slippage scenarios charge **the same friction to the trading model and DCA**, including the terminal sale, using same FX and initial capital. The 2% assumption is a hypothetical stress, not measured VBTC bid–ask spread. Under 2% slippage, four-year winners were 26/32 original, 28/32 weakness-gated and 29/32 cash recycling.

## Current research decision

1. Keep **uncapped 12-week tier buys / 16-week tier sells** as the immutable comparison point.
2. Retain **weakness-gated selling** as a promising upside-oriented candidate (four-year median and sell-fill reduction) but do not overlook its weak three-year performance or its large two-year losses.
3. Retain **26-week partial cash recycling** as a downside-oriented candidate, with stronger four-year 10th-percentile and worst outcomes. It also still underperforms DCA in some periods.
4. Do not choose adaptive thresholds based on 2019/2023 (already inspected), or call the 2018–2024 overlapping historical cohorts a genuine out-of-sample test.
5. Require genuine prospective VBTC data, preserved observation timestamps, issuer market/NAV and actual order-execution assumptions before **any** promotion decision.
6. For next Research steps, test more realistic risk constraints: how much drawdown and missed upside the investor can accept, and decision stability under actual VBTC price/volume deviations. Avoid adding too many indicators.

## Production and paper-trading guardrails

**No edits** to `main`, `engines/production`, the Streamlit Production app, Google Sheets, BTC audit master or `research_forward/200wma_v1/config_frozen.json`. All adaptive rules are disabled by default and only enabled through explicit Research options. The Wednesday paper model still uses the original frozen options.

This report supersedes earlier relative comparisons only on **matched full liquidation** grounds. It does **not** invalidate the historical gross mark-to-market observations or claim a real after-tax rate of return.
