# Preferred 200WMA research candidate — 2026-10-15

## 16 October 2026 update: matched execution-cost robustness and selection gate

The [completed Research cost-stress workflow](https://github.com/aussiekarl-gif/BTC_Composite/actions/runs/38829353001) (**passed**) applies identical 0.1% dealing fees, A$20-per-fill brokerage, and **0.5%, 1%, or 2% execution slippage** to trading, DCA entry, and both terminal disposals. See [the detailed fair-exit and execution-cost sensitivity report](https://github.com/aussiekarl-gif/BTC_Composite/blob/research/cycle-strategy-optimization/research_outputs/200wma_adaptive_fair_exit_and_stress_findings_2026-10-16.md).

For **32 overlapping four-year** starting dates (every eight weeks), median fully-liquidated excess return over identically-taxed DCA at **2% slippage** was +34.966% original tier strategy, **+42.059% weakness-gated sells**, +26.296% breakout reentry, and +31.920% 26-week idle recycling. At that cost assumption, the respective worst four-year outcomes were −24.747%, −21.187%, −21.778%, and **−16.000%**. But **45 overlapping two-year** starts still produced worst-case underperformance of −56.648%, −49.426%, −47.692% and −43.092%.

- The weakness gate offers the strongest longer-horizon median in this stress subset and reduces sell fills; idle recycling offers stronger four-year lower-tail protection. These are competing risk-return trade-offs, not proof of dominance.
- The alternative 8-week breakout reentry loses more median advantage at higher trading friction, and none of the rules fixes every bad short-horizon cohort.
- **Not independent validation:** the variants and sample years were already studied; moving from 4-week to 8-week-spaced starts reduces sample size but **does not create independent cycles**.
- **Decision remains unchanged:** no automatic Research or Production promotion; frozen VBTC forward paper v1 continues unchanged. No portfolio actions or live trading integrations.

## 16 October 2026 update: corrected fully-liquidated tax comparison supersedes prior after-tax rankings

[**Full matched-AUD exit and adaptive trading report**](https://github.com/aussiekarl-gif/BTC_Composite/blob/research/cycle-strategy-optimization/research_outputs/200wma_fair_exit_adaptive_conclusions_2026-10-16.md). Numerical tests and 2/3/4-year results verified in [GitHub run 38822949971](https://github.com/aussiekarl-gif/BTC_Composite/actions/runs/38822949971).

**Important correction:** Older accumulation-phase tax sensitivity compared a realised-CGT trading portfolio to a **not-yet-liquidated DCA baseline**. The newly matched benchmark applies **the same disposal price, brokerage, slippage, and FIFO SMSF CGT** on each portfolio's remaining ETF units at the **same exit date**, netting already-paid annual CGT once.

| Matched holding horizon | Existing tier strategy median vs after-tax DCA | Worst outcome | Distinct entry samples? |
|:--|--:|--:|:--|
| 2 years | **+4.257%** | **−55.288%** | No — 89 overlapping starts |
| 3 years | **+30.070%** | **−47.953%** | No — 76 overlapping starts |
| 4 years | **+38.414%** | **−23.718%** | No — 63 overlapping starts |

A 5%-pullback weakness-gated sell challenger increased four-year median advantage to +46.372% with fewer fills, but did **not** improve the median over 2 or 3 years. Reentry and exposure-capping rules protected some bad tails by sacrificing upside; none consistently dominates existing tiers. Even under the matched-tax comparison, the strategy frequently underperformed simple DCA in 2019 and 2023 two-year starts.

**Interpretation:** The original "after-tax +33.099% four-year" numbers below remain a record of the earlier *unmatched tax* experiment, **not the currently correct terminal liquidation benchmark**. Do not compare the old and new statistics as if they describe identical accounting.

**Promotion decision unchanged:** Production V5.8.2 and frozen VBTC prospective paper v1 are unchanged. New features are disabled by default; no rule has earned promotion.



**Research only. Production must remain unchanged.**

## Selected configuration
- Buy execution window: **12 weeks**, bell-shaped tranche weights.
- Sell execution window: **16 weeks**, bell-shaped tranche weights.
- Trading fee: **0.1% per fill**.
- Each tier is triggered by a completed weekly 200WMA deviation crossing; fills start the next week.
- Allow pending schedules to complete despite reversal (**cancel=False**) for the current candidate.
- **Block new concurrent schedules for the same trading tier** while an earlier one remains active. This conservative policy is preferred after the overlap audit.
- Use **0.5% additional slippage** (on top of the 0.1% fee) as the conservative sensitivity reference, not a calibrated execution forecast.
- Compare against immediate execution and buy-and-hold.

## Verified initial rolling-start benchmark
GitHub Actions run [38808097501](https://github.com/aussiekarl-gif/BTC_Composite/actions/runs/38808097501), artifact `200wma-12week-execution`:
- 92/92 overlapping 2018–2024 starts beat buy-and-hold.
- Median advantage: **+85.198%**.
- Worst advantage: **+21.086%**.
- Immediate execution median: +60.104%; worst: +27.642%.

## Additional completed execution robustness audit
- [GitHub Actions run 38802836578](https://github.com/aussiekarl-gif/BTC_Composite/actions/runs/38802836578), artifact `200wma-overlap-slippage`.
- Same-tier overlap allowed, 0% slippage: 92/92 wins, +85.273% median, 938 median weekly fills.
- Same-tier overlap **blocked**, 0% slippage: 92/92 wins, +73.754% median, 663 median weekly fills.
- Same-tier overlap **blocked**, 0.5% additional slippage: 92/92 wins, **+70.454% median**, worst **+20.930%**.
- Same-tier overlap **blocked**, 1.0% additional slippage: 92/92 wins, +67.187% median, worst +20.338%.
- These estimates remain shared-endpoint overlapping cohorts and must not be used alone for promotion.

## Fixed-horizon challenge (verified 2026-10-15)
[Completed run 38803550782](https://github.com/aussiekarl-gif/BTC_Composite/actions/runs/38803550782), artifact `200wma-fixed-horizon`. For the **overlap-blocked**, bell-shaped 12-week buys / 16-week sells, 0.1% fee + 0.5% slippage:
- **2 years** (104 weeks): 61/89 winning rolling starts; median **+8.304%** vs buy-and-hold; worst **−36.651%**.
- **3 years** (156 weeks): 50/76 wins; median **+25.512%**; worst **−42.087%**.
- **4 years** (208 weeks): 60/63 wins; median **+67.958%**; worst **−24.478%**.
- Earlier 92/92 performance reflected common Oct 2026 exits. It **does not generalize** to a 2–3 year holding period. Fixed horizons still have *overlapping start dates* and are not independent trials.
- No strategy is approved for Production.

## Cash-first entry benchmark (verified 2026-10-15)
[Completed run 38803990298](https://github.com/aussiekarl-gif/BTC_Composite/actions/runs/38803990298), artifact `200wma-cash-deployment`. **Illustrative** 20% BTC / 80% cash initial holdings, 0.1% fee + 0.5% slippage; all cash invested after the selected window, **no sell ladder**; compare to 100% immediate BTC purchase:
- 12-week equal DCA: 41/89 wins, median **−3.115%**.
- 12-week 200WMA risk-weighted DCA: 42/89 wins, median **−0.897%**.
- 26-week risk-weighted DCA: 43/89 wins, median **−0.393%**.
- 52-week risk-weighted DCA: 38/89 wins, median **−5.277%**.
- These 2-year comparisons do **not** validate the sell/repurchase model for a cash-heavy investor. No model has shown a robust advantage in the cash-first test.
- When fully invested by week 52, the buy-only strategy has unchanged relative BTC units thereafter. Differences in aggregate medians between 2- and 4-year horizons stem from **different eligible start cohorts**, not additional timing gains after deployment.

## Strict below-200WMA buy-only test (verified 2026-10-15)
[GitHub Actions run 38804595514](https://github.com/aussiekarl-gif/BTC_Composite/actions/runs/38804595514), artifact `200wma-cash-deployment`:
- 20% initial BTC / 80% cash; no selling. Two-year fixed horizons; compare with full immediate BTC purchase.
- 12-week risk-weighted DCA (buy at all ratios, higher purchases below 200WMA): median **−0.897%**, 42/89 wins, **all cash deployed**.
- Strict below-200WMA buys over 12 weeks: median **−12.710%**, 34/89 wins; **74/89** cohorts left cash uninvested, median **$400k** cash remaining.
- Strict below-200WMA buys over 26 weeks: median **−8.837%**, 36/89 wins; **73/89** cohorts left cash uninvested, median **$400k** cash remaining.
- Strict below-200WMA buys over 52 weeks: median **−18.279%**, 31/89 wins; **74/89** cohorts left cash uninvested, median **$400k** cash remaining.
- **Do not adopt an absolute below-200WMA-only purchase gate for cash-heavy holdings** based on this evidence. Prefer a fully funded schedule that uses completed historical price/200WMA deviation to adjust purchase *size*, subject to risk and time horizon.
- This does not prove a particular DCA rule can consistently beat immediate investment.

## Integrated cash entry plus tier trading (verified 2026-10-15)
[GitHub Actions run 38805159522](https://github.com/aussiekarl-gif/BTC_Composite/actions/runs/38805159522), artifact `200wma-integrated-cash-trading`.
- Same illustrative 20% BTC / 80% cash starting portfolio, 0.1% trading fee, 0.5% execution slippage; 12-week weighted cash deployment, 12-week bell-shaped rebuys, 16-week bell-shaped sells, same-tier overlap blocked, no reverse cancellations.
- **2-year holding period:** 60/89 wins versus independently implemented risk-weighted cash-only DCA, median **+7.428%** vs DCA, worst **−51.031%** vs DCA.
- **4-year holding period:** 59/63 wins versus the same cash-only DCA, median **+66.962%**, worst **−14.609%**.
- Cash-only benchmark has no tier sells or rebuys; both start at identical initial cash/BTC proportions and use identical funding schedules.
- The strategy does **not** provide a reliable 2-year advantage: some historical outcomes substantially underperform simple buying, and the cohorts overlap.
- **Ledger reconciliation passed** in [research quick-regression run 38805836580](https://github.com/aussiekarl-gif/BTC_Composite/actions/runs/38805836580). With tier trading disabled, integrated backtest agreed with independent pure-DCA portfolio accounting to within $0.05 across representative 2- and 4-year starts, 12- and 26-week cash schedules, and equal/risk-weighted funding.

## BTC core retention and signal direction checks (verified 2026-10-15)
- [BTC core test, run 38806220836](https://github.com/aussiekarl-gif/BTC_Composite/actions/runs/38806220836). Baseline: illustrative 20% BTC / 80% cash, 12-week risk-weighted cash funding, 12-week buy / 16-week sell schedule, 0.1% fee plus 0.5% slippage, matched pure-DCA comparison.
- Keeping 0% / 25% / 50% / 75% of the *initial BTC-equivalent units* permanently unsold lowered worst two-year advantage from **−51.03%** / **−36.21%** / **−22.32%** / **−15.50%**, but reduced four-year median advantage from **+66.96%** / **+35.11%** / **+14.35%** / **+2.77%**. A core is a downside-control option, **not a free improvement**.
- [Sell-crossing test, run 38806511311](https://github.com/aussiekarl-gif/BTC_Composite/actions/runs/38806511311). Upward sell-tier crossings with no core: 2-year median +7.43%, worst −51.03%, 4-year median +66.96%. Downward crossings: 2-year median +2.96%, worst −32.84%, 4-year median +47.53%; the four-year worst was **−27.30%** versus upward-crossing **−14.61%**. Do not claim downward selling dominates the original rule.
- **Decision for research only:** retain upward-crossing sell tiers as the leading high-return variant; do not enable a permanent BTC core automatically. Any selection should specify a downside tolerance, and all comparisons remain in-sample.

## Historical AUD currency impact (verified 2026-10-15)
- [AUD paired-cohort backtest, run 38807188747](https://github.com/aussiekarl-gif/BTC_Composite/actions/runs/38807188747), artifact `200wma-aud-currency-impact`.
- Risk signals derive from completed weekly BTC/USD prices and USD 200WMA, while actual simulated fills use historical BTC/AUD prices from a separately sourced series (Blockchain.com USD spot × Frankfurter historical USD/AUD reference rates). The USD and AUD comparisons use exactly matched entry/exit dates and same parameters.
- Protected core **0%**, 20% BTC / 80% cash initial holdings, risk-weighted 12-week cash funding, 12-week bell buy / 16-week bell sell, blocked same-tier overlap, 0.1% trade fee plus 0.5% slippage:
  - **2 years:** USD median **+7.428%** vs cash-only DCA; AUD median **+5.406%**, 57/89 wins, worst AUD **−54.204%**.
  - **3 years:** USD median **+25.814%**; AUD median **+33.117%**, 48/76 wins, worst AUD **−46.927%**. Different median ordering from median cohort-level FX change is expected: medians are not linear.
  - **4 years:** USD median **+66.962%**; AUD median **+49.200%**, 56/63 wins, worst AUD **−21.130%**.
- AUD 2-year cohorts by start year include **2019 median −24.662%** (1/13 wins), **2023 median −9.767%** (3/13 wins), **2024 median +48.655%** (10/10 wins). Even if aggregate positive, performance is strongly cycle dependent.
- Historical AUD/USD rate is a **reference**, not a guaranteed exchange-traded BTC ETF price. Actual Australian ETF tracking differences, spreads, trading hours, portfolio currency, tax and SMSF pension/accumulation rules remain unmodeled.
- A **shared completed-week loader** is now used in the USD research backtests too, and the causal BTC/AUD data builder excludes future-labelled incomplete final weeks. Recheck all headline results from new clean-week runs before any promotion.

## Completed-week backtest reconciliation (verified 2026-10-15)
- [Full research run 38808097501](https://github.com/aussiekarl-gif/BTC_Composite/actions/runs/38808097501) **passed** after switching the USD research scripts to the shared completed-week history loader. The incomplete final 2026-10-12 bucket was excluded because the archived price series ended on 2026-10-07.
- Shared-end-date original immediate execution: **+60.104% median**, **+27.642% worst**; preferred 12-week buy / 16-week sell bell: **+85.198% median**, **+21.086% worst**, 92/92 correlated starts versus hold.
- Fixed two- and four-year integrated cash-first comparisons remained at **+7.428%** and **+66.962%** USD median versus cash-only DCA; AUD comparisons also unchanged (+5.406% and +49.200%).
- The shared-end-date results remain unsuitable for choosing a trading strategy despite their positive numbers.

## Australian BTC ETF costs and annual SMSF CGT (verified 2026-10-15)

Detailed [cost and tax stress report](https://github.com/aussiekarl-gif/BTC_Composite/blob/research/cycle-strategy-optimization/research_outputs/200wma_smsf_cost_tax_summary.md). [GitHub Actions 38810383990](https://github.com/aussiekarl-gif/BTC_Composite/actions/runs/38810383990) **passed**, with USD ledger regression and deterministic FIFO unit tests passed in [run 38810383986](https://github.com/aussiekarl-gif/BTC_Composite/actions/runs/38810383986).

- Illustrative research costs: A$20 brokerage on **every fill**, 0.45% ETF annual management drag, 0.1% dealing fee plus 0.5% slippage; the DCA benchmark pays matching initial-purchase and DCA fees.
- **2-year AUD fixed holding** (89 overlapping starts): gross **+4.567%** median vs DCA, **+2.402%** after 15% compliant SMSF accumulation CGT and July cash settlement; **48/89 wins**, **−59.482% worst**.
- **4-year AUD fixed holding** (63 overlapping starts): gross **+48.984%**, **+33.099%** after annual CGT; **53/63 wins**, **−30.502% worst**. Terminal-only tax estimate was +38.470%, which materially overstated this tax-payment cashflow scenario.
- Median modelled cumulative CGT liability roughly **A$39,041** (2 years) and **A$168,372** (4 years). These are **not predictions of an individual's tax bill**, and no cohort required a forced sale specifically to pay the early-July tax charge.
- Gross (0% CGT) results represent only assets **actually eligible** for exempt retirement-phase income. Actual SMSFs may have a mixed ECPI percentage, distributions, actuarial apportionment and pension restrictions.
- **Decision:** Stay in Research. The strategy has poor short-horizon tails and in-sample fitting concerns despite attractive historical long-horizon medians. Production V5.8.2 is untouched.

## Idle-cash redeployment safeguard sensitivity (verified 2026-10-15)

Detailed [AUD after-tax comparison](https://github.com/aussiekarl-gif/BTC_Composite/blob/research/cycle-strategy-optimization/research_outputs/200wma_idle_cash_recycling_findings.md), [completed GitHub run 38811194137](https://github.com/aussiekarl-gif/BTC_Composite/actions/runs/38811194137).

- Research test, no changes to default candidate: if >50% of marked portfolio value is freely held in cash and no tier buy has filled for 26 weeks, buy 25% of remaining cash at next weekly execution price. Trigger uses completed prior weekly data and respects brokerage, ETF fee proxy and annual SMSF CGT accounting.
- **2-year after-tax AUD**: no safeguard +2.402% median vs DCA / −59.482% worst / 48 of 89 correlated starts win; 26-week safeguard +2.402% median / −49.143% worst / 47 of 89 wins.
- **4-year after-tax AUD**: no safeguard +33.099% median / −30.502% worst / 53 of 63 wins; 26-week safeguard **+34.682%** median / **−21.260%** worst / **58 of 63 wins**. Four-year 10th-percentile advantage improved from −11.543% to +6.236%.
- **Warning:** The guard did not fix short-horizon cohort-wide underperformance: **0/13 winning starts in 2019 and 0/13 in 2023** even with the safeguard. 2021 median fell materially.
- **Do not promote:** The rule was invented after investigating those years. It is now contaminated as an in-sample selection and requires independent validation.

## Actual Australian VBTC issuer market-price validation (verified 2026-10-15)

[Issuer-market historical test](https://github.com/aussiekarl-gif/BTC_Composite/blob/research/cycle-strategy-optimization/research_outputs/200wma_vbtc_market_price_findings.md), [GitHub run 38813587696](https://github.com/aussiekarl-gif/BTC_Composite/actions/runs/38813587696) **passed**.

- Real VanEck VBTC data covers **21 June 2024 to 14 October 2026**, with 589 positive-volume observations and 120 matched completed weekly dates against the archived BTC/USD 200WMA signals (signals end 5 October 2026).
- Issuer-reported last trade versus NAV: **+0.272% median premium**, 90th percentile **+2.680%**, extrema **+9.979% / −7.609%**. These differences are **not** executable bid–ask spreads; issuer NAV timing may differ from the ASX trade time.
- 52-week AUD after-tax model at **actual issuer last traded market references**: 17 overlapping entry cohorts, **11/17 beat simple DCA**, **+5.506% median**, **−9.019% worst**. The matching NAV hypothetical had +5.272% median.
- 104-week issuer market test had only **four correlated starts**, all winners with +42.825% median; the cash-recycling candidate returned +31.540% median over those same starts. **Too few to infer superiority**, but it challenges the synthetic four-year recycling result.
- VanEck issuer NAV and market price already reflect management fees, so historical ETF-price scenarios do not impose the 0.45% MER again. A$20 brokerage and simulated dealing/slippage remain sensitivity assumptions.

## Prospective frozen ETF paper journal (first possible close 19 October 2026)
- [Paper-trading protocol and integrity rules](https://github.com/aussiekarl-gif/BTC_Composite/blob/research/cycle-strategy-optimization/research_forward/200wma_v1/README.md); [initial verification run 38813226526](https://github.com/aussiekarl-gif/BTC_Composite/actions/runs/38813226526) **passed** the no-lookahead self-test and correctly recorded **zero paper actions** before the first eligible completed week.
- Frozen independent A$500,000 hypothetical portfolios: simple 12-week DCA; 12-week buy/16-week sell; the same with the 26-week cash-recycling safeguard. Uses BTC/USD completed-week 200WMA signals and the **following completed week's** official VBTC market reference for paper fills. Keeps NAV and traded price separate.
- Observation journal and earlier weekly scores are append-only and must reconcile exactly on reruns; data source revisions or missing prospective weeks fail closed.
- **Unattended weekly Research scheduling is enabled by explicit approval:** the Wednesday 09:17 Brisbane `main` launcher checks out and writes only to Research. Production trading calculations remain separate.

## AUD SMSF root cause and exposure-limit tests (verified 2026-10-15)

- [2019/2023 root-cause analysis](https://github.com/aussiekarl-gif/BTC_Composite/blob/research/cycle-strategy-optimization/research_outputs/200wma_failure_attribution_findings.md), completed [GitHub run 38815941285](https://github.com/aussiekarl-gif/BTC_Composite/actions/runs/38815941285): 2019 median **180 sell fills / 84 rebuy fills**, with A$1.90m cash at exit and −32.690% median vs DCA; 2023 median **97 sell fills / 0 tier rebuy fills**, A$894k cash at exit and −12.872% vs DCA; 2021 winning control had **134 sell / 192 rebuy fills** and +96.852% median. Early selling without timely re-entry is the central failure.
- [Sell-side total-cash ceiling study](https://github.com/aussiekarl-gif/BTC_Composite/blob/research/cycle-strategy-optimization/research_outputs/200wma_cash_exposure_ceiling_findings.md), [GitHub run 38816671039](https://github.com/aussiekarl-gif/BTC_Composite/actions/runs/38816671039): a 25% cash ceiling reduces worst two-year deficit from −59.482% to **−23.786%**, but cuts four-year median advantage vs cash-only DCA from +33.099% to **+8.524%**. All 2019 starts still failed to beat DCA, and 2021 upside weakened sharply.
- **Decision:** do not choose a 25%/40%/60% cap retrospectively as a Production rule. The frozen uncapped forward-paper baseline and separate 26-week idle-cash alternative remain locked and unchanged.
- [Weekly GitHub Research dashboard](https://github.com/aussiekarl-gif/BTC_Composite/blob/research/cycle-strategy-optimization/research_forward/200wma_v1/DASHBOARD.md) is generated from only timestamped prospective observations. Wednesday's main-branch scheduler runs at 09:17 Brisbane time; errors open an issue assigned to GitHub user `aussiekarl-gif`, subject to GitHub notification preferences. No actual forward observation exists before Monday 19 October 2026.

## Validation gates before any promotion
1. Audit cash reservations, open orders at backtest end, fee charging and simultaneous-tier signals; reconcile conservation of BTC and cash.
2. Add realistic spread/slippage and fees, including sensitivity to missed fills.
3. Compare fixed 10x10 tiers with lower selling thresholds (+50% to +200%), without optimizing on the final test period.
4. Evaluate 2018–2021 calibration and 2022–2026 forward holdout, independent cycle windows, plus adverse stress cases.
5. Assess BTC-equivalent holdings, cash drag, drawdowns, turnover, and AUD/tax considerations.
6. Ensure any new thresholds or schedule are promoted only after independent verification and explicit approval.

**Caution:** The 92 start dates overlap and share the same end date. The 2025–2026 cycle may be incomplete. These are not independent trials or forward performance guarantees.
