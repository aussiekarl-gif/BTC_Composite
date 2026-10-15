# Sell-side cash-exposure ceilings — BTC 200WMA AUD tax-aware study

**Research only; Production V5.8.2 and the frozen forward-paper v1 remain unchanged.**

Verified [GitHub Actions run 38816671039](https://github.com/aussiekarl-gif/BTC_Composite/actions/runs/38816671039), artifact `200wma-aud-cash-exposure-ceilings`.

## Method
Historical BTC/USD 200WMA prior-week signals with synthetic BTC/AUD ETF reference prices. Cash-first 20% BTC/80% cash A$500,000 notional, 12-week weighted initial funding, 12-week bell buy jobs, 16-week bell sell jobs; same-tier overlap blocked; A$20 brokerage per fill, 0.1% trading fee, 0.5% execution slippage, 0.45% simulated annual management drag and FIFO 15% accumulation SMSF CGT with conservatively early annual cash payments.

The optional ceiling stops a tier sell if it would increase **funding cash + free cash + reserved buy cash** above the selected percentage of current marked portfolio value; it does not force a buy. Prices used to cap quantities are observed at that hypothetical execution, with no future price information. Cap settings **25%/40%/60%** are after-the-fact exploratory choices made after inspecting the weak 2019/2023 cohorts, and **must not be promoted on these results**.

## Two-year fixed horizon, 89 overlapping starts

| Max total cash from sells | Median excess return vs identical DCA | Worst excess return | Wins | Median cash at exit |
|:--|--:|--:|--:|--:|
| Uncapped | **+2.402%** | −59.482% | 48/89 | A$418,305 |
| 60% | +0.515% | −42.296% | 47/89 | A$371,346 |
| 40% | +0.515% | −32.574% | 45/89 | A$297,298 |
| 25% | +0.515% | **−23.786%** | 45/89 | A$229,801 |

For 2019 starts (13 overlapping cohorts), median excess return improved from **−32.690% uncapped** to **−14.458% with 25% cap**, but **zero cohorts became winners**. In 2023 the same comparison changed from −12.872% (2/13 wins) to −10.389% (0/13 wins). Strong 2021 cohort median dropped sharply from +96.852% to +26.827%.

## Four-year fixed horizon, 63 overlapping starts

| Max total cash from sells | Median excess return vs identical DCA | Worst excess return | Wins |
|:--|--:|--:|--:|
| Uncapped | **+33.099%** | −30.502% | 53/63 |
| 60% | +20.263% | −24.833% | 55/63 |
| 40% | +13.958% | −21.140% | 56/63 |
| 25% | +8.524% | **−15.976%** | 57/63 |

## Research decision
A maximum-cash rule is **downside insurance paid for by giving up upside**; it does not consistently beat simple DCA. The 25% cap improves the worst outcomes but surrenders 74% of the four-year median advantage versus the uncapped model. These simulations are strongly correlated, in-sample, with historic threshold choices developed after inspecting the test data. Do not select the best-looking cap as if it were independently validated.

Continue the **uncapped 12-week buy / 16-week sell** baseline and separate **26-week cash recycling** frozen prospective VBTC test unchanged. Treat a dynamic cash ceiling only as a documented third research risk-management alternative. If pursuing it, pre-register a risk constraint and evaluate with independent future market observations and actual ETF bid/ask execution.
