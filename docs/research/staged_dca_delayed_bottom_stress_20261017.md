# Research audit: staged DCA delayed Bitcoin bottom and false early BUY risk
17 October 2026 — RESEARCH ONLY, NOT deployed

## Result / decision

**DO NOT promote the uncapped 3–20% of remaining cash staged BUY challenger to live Cycle Trading.**

Matched, after-tax AUD **counterfactual** runs show the model can deploy nearly all post-sale cash before a *synthetically delayed* Bitcoin low and significantly underperform the conservative 2.5%-of-remaining-cash BUY policy. Strong in-sample historical returns in PR #115 did **not** establish robustness to further post-entry price falls.

The simulations explicitly **invent future BTC prices** beginning at halving days **780 or 900**, with **50% or 70% additional declines** from the price at that anchor to a day-1060 trough, followed by either a weak or stronger recovery to halving day 1150. BTC observations through each anchor are kept exactly historical. Actual daily USD/AUD FX observations are held at historical values for both legs. **These paths did not occur**; they are stress cases, not real history, forecasts or probability estimates.

Both arms: hypothetical A$500k Bitcoin at the historical halving; identical prior-only, original BTC staged SELL dates (fixed day525–560 or dynamic90% holdback20% through day730); same available after-tax sale proceeds, FIFO simplified immediate 10/15% SMSF CGT, AUD3 fees, execution-day close proxies; identical synthetic prices and original portfolio. BUY policy is either the live-matching conservative 2.5% strict prior-200WMA gate or the staged candidate buying up to 20% of remaining cash. No actual user trades or cost basis are used.

## Results: 8 paths per cycle and SELL schedule

| Historic pre-shock period | SELL schedule | Times staged underperformed conservative BUY | Worst staged after-tax wealth vs conservative BUY | Best staged after-tax wealth vs conservative BUY |
|:--|:--|--:|--:|--:|
| 2017-based | Fixed day525–560 | 3 of 8 | **−24.13%** | +48.02% |
| 2017-based | Dynamic90% holdback20% | 3 of 8 | **−24.13%** | +48.02% |
| 2021-based | Fixed day525–560 | **8 of 8** | **−37.58%** | −10.67% |
| 2021-based | Dynamic90% holdback20% | **8 of 8** | **−37.58%** | −10.68% |

These scenario counts are **not** win rates. The scenario family is deliberately adversarial and contains shared choices and paths. Eight paths per sell schedule are derived from 2 shock dates × 2 decline depths × 2 end-recovery assumptions; neither the shocks nor their weights are independently observed market probabilities.

The synthetic day1060 low was indeed the lowest observed entry-window close in **every tested scenario**. Terminal wealth is shown as hypothetical *after-liquidation AUD* accounting for a simplified SMSF tax escrow, not a realised result in the user's pension or broker portfolio.

## Cash depletion and price error

| Pre-shock historical cycle | Maximum staged cash spent *before forced low* | Worst staged BUY VWAP above realised scenario low |
|:--|--:|--:|
| 2017-based | **98.94% of net sale proceeds** | **+131.55%** |
| 2021-based | **99.66% of net sale proceeds** | **+234.49%** |

The reserve in the current staged research replay is **2% of original A$500k**, not a percentage of the far larger later BTC sale proceeds. This mechanically permits almost all sale proceeds to be deployed before a delayed low. The conventional baseline holds more cash and can benefit if prices subsequently collapse.

Crucially, even the worst staged variants were still positive in this test versus *the matched original buy-and-hold account*, due to the historically fitted SELL schedule. For example the lowest staged after-tax outperformance versus buy-and-hold was +190.20% (2017 fixed), +161.40% (2021 fixed), +166.76% (2017 dynamic), +149.02% (2021 dynamic). **This does not cancel its −24/−38% shortfall versus the conservative BUY policy**, nor establish the historical selling rule will work next cycle.

## What must change before new candidate goes live

1. Research protective reserve policies **as percentages of actually realised net sale proceeds**, not percentages of the initial A$500k. Compare residual cash, cumulative BTC and terminal AUD after tax on both the *unmodified historical cycles* and delayed-bottom shocks. An arbitrary reserve may hurt upside; freeze before measuring.
2. Test false rallies followed by fresh lower lows and long grinding bear markets; do not let "50DMA recovery" alone exhaust reserve.
3. Validate forward data vintages / actual market availability, realistic bid-ask FX/IBIT spreads, order sizes, fees and tax at different SMSF accumulation/pension phases.
4. Compare live deployability against realistic post-2026 purchase lots and remaining cash; don't impose a backdated 2025 historical sale on actual 2026 holdings.
5. Require genuinely independent out-of-sample evidence before promoting any candidate. Historical peak/bottom choices and cycle calendars have already been studied; two modern completed BTC cycles cannot prove a precise 20% average error goal.

## Reproduction

- Code: engines/research/staged_dca_delayed_bottom_stress.py
- Matched after-tax replay: engines/research/staged_tax_aware_roundtrip.py
- Safety tests: tests/test_staged_dca_delayed_bottom_stress.py
- Workflow: .github/workflows/staged_dca_delayed_bottom_stress.yml
- Complete scenario-level metrics and dated BTC BUY/SELL trade ledgers: GitHub Actions artifact **btc-staged-delayed-bottom-stress**.
- **Production V5.8.2, Research V5.9, Streamlit Cycle Trading, daily ntfy, Google Sheets and real holdings remain unchanged.**
