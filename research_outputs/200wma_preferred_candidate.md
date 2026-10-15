# Preferred 200WMA research candidate — 2026-10-15

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
GitHub Actions run [38738305322](https://github.com/aussiekarl-gif/BTC_Composite/actions/runs/38738305322), artifact `200wma-12week-execution`:
- 92/92 overlapping 2018–2024 starts beat buy-and-hold.
- Median advantage: **+85.273%**.
- Worst advantage: **+21.137%**.
- Immediate execution median: +60.168%; worst: +27.693%.

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
- **Ledger reconciliation test** has been added to rerun the integrated engine with all tier trades disabled and require exact agreement with the independent pure-DCA baseline.

## Validation gates before any promotion
1. Audit cash reservations, open orders at backtest end, fee charging and simultaneous-tier signals; reconcile conservation of BTC and cash.
2. Add realistic spread/slippage and fees, including sensitivity to missed fills.
3. Compare fixed 10x10 tiers with lower selling thresholds (+50% to +200%), without optimizing on the final test period.
4. Evaluate 2018–2021 calibration and 2022–2026 forward holdout, independent cycle windows, plus adverse stress cases.
5. Assess BTC-equivalent holdings, cash drag, drawdowns, turnover, and AUD/tax considerations.
6. Ensure any new thresholds or schedule are promoted only after independent verification and explicit approval.

**Caution:** The 92 start dates overlap and share the same end date. The 2025–2026 cycle may be incomplete. These are not independent trials or forward performance guarantees.
