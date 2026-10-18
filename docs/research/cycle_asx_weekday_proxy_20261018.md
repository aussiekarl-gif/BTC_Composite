# Cycle Trading: correct weekday execution proxy and ETF cost sensitivity

Research date: **18 October 2026**. **NO** changes to Production V5.8.2, Research V5.9, Cycle Trading Streamlit, live ntfy, trading rules, actual ASX ETF units or personal portfolio. This follows merged #144 (live 7-day eligibility with 2.5% vs 3.5%) and merged #146 (2.5/3/3.5 with weekend BTC fills).

## Grounded IBIT facts and non-overclaim

Australian iShares Bitcoin ETF **ASX:IBIT was listed on 14 November 2025** (ASX issuer notice 1450.25.11 and BlackRock IBIT product page). **Historical IBIT bid/ask/close did not exist in the 2017 and 2021 BTC cycles.** BlackRock states an **annual management fee of 0.39%**, which is reflected in actual IBIT NAV. It would be wrong to manufacture pre-2025 ETF prices or add a 0.39% cost AGAIN to real IBIT market quotes where already reflected. Reference:
- https://www.asxonline.com/content/asxonline/public/notices/2025/november/1450.25.11.html
- https://www.blackrock.com/au/products/346455/ishares-bitcoin-etf

Our repository has no independently verified historical dated IBIT bid/ask executable quote series. **This is NOT a real ETF fill study**. A fairer but still incomplete hypothesis is a **weekday-only BTC/AUD next-close execution proxy**, with illustrative slippage cost and NAV drag. It excludes ASX holidays, morning-evening FX timing, fund premium/discount/tracking differences, stale open quotes, true IBIT lot taxes, SMSF pension phase and full transactions; do not call it 'realistic verified IBIT execution'.

## Freeze assumptions before numerical results

Identical initial A$400,000 cash, no invented sale at 2025 top; same historical prices/strictly prior dated USD/AUD FX, A$3 flat brokerage, illustrative FIFO accumulated SMSF terminal CGT, and same **7 calendar days between ACTUAL EXECUTED BUYs**. At date T, the market-level BUY decision is called from current shared `calculate_allocation_signal(market,buy_style="adaptive_recovery")`, using only T-1 close and its prior exact 200-WEEK MA; when it says BUY WATCH allocate frozen 2.5%, 3.0% or 3.5% of THEN REMAINING AUD cash. Never make BUY without underlying existing shared BUY WATCH. No actual SELL assumptions since fresh cash only. BTC/USD next day's close (dated T) is a **simulated execution reference, NOT a real intraday ASX quote**, known only after the order decision.

Five execution scenarios:
- **calendar_optimistic:** current every-calendar-day T BTC USD close execution proxy (independently reproduce PR #144's exact seven-day wallet accounting), A$3 brokerage, no further spread/NAV costs. Weekends executable here only as the obviously optimistic BTC proxy.
- **weekday_zero_cost:** purchase T only if Mon-Fri UTC, no public holiday closures, zero extra spread or ETF NAV drag.
- **weekday_10bps_fee039:** weekdays only, **10 basis points per trade side** (buy price +0.10%; hypothetical terminal sell price −0.10%), plus **0.39% per year** accrued ETF NAV erosion during hypothetical fund holdings. BTC market signal computed unaffected.
- **weekday_25bps_fee039:** same but 0.25% each side.
- **weekday_50bps_fee039:** same but 0.50% each side. *These are stress assumptions, NOT measured spread estimates for real IBIT.*

Historical starts halving+650/750/850/900, 2017 and 2021 complete through +1150, 2025/26 right-censored at Oct5, matching original PR #144 and PR #146. Reuse exactly eight historical-prefix-preserving fake further 50/70% deep crashes (two different terminal ratios 55%/105% of pre-crash reference), not stochastic likelihood samples. Summarise **3.0% vs live 2.5% relative terminal aftertax AUD and BTC quantity** by execution scenario, dates lost due to weekends, and adverse scenarios; compare 3.5% sensitivity. Account proportion improvement even with fee drag doesn't imply its risk exposure is justified.

Tests require unmodified original calendar proxy wallet parity, future price cannot create same-date signal, weekend BUY suppression, strict 7-day cooldown, worsening absolute simulated terminal aftertax under larger assumed trading costs when matched dates, and explicit warnings. No actual IBIT execution or broker access.

Decision: keep BUY percentages unchanged; if 3% remains favorable under all weekday/expense hypotheses but still fails deep crash stress, flag as a *calibrated risk/reward candidate* not a proven improvement. Next: run genuine post-2025 IBIT historical quote comparisons **only if** verifiable multi-date NAV/market bid/ask and FX are available, and evaluate current remaining-unit-based SELL plan against historical seller separately.


## Results and decision — 18 October 2026

**[GitHub Actions run 39117733548](https://github.com/aussiekarl-gif/BTC_Composite/actions/runs/39117733548) succeeded: 29 tests passed** (8 new weekday/parity tests, 3 3% tests, 8 prior live-weekly tests, 10 current allocation regressions). All 190 results (11 historic+8 synthetic cohorts ×5 scenario assumptions ×2 tested 3%/3.5% candidates) and the original vs weekday trade dates/FX/CSV are [archived in artifact 12132953270](https://github.com/aussiekarl-gif/BTC_Composite/actions/runs/39117733548/artifacts/12132953270). Every **calendar_optimistic** account exactly matched the original research weekly BUY engine on BUY count, BTC units, cash remaining and illustrative post-tax liquidation value.

### Historic 3.0% vs current 2.5% of remaining cash (total aftertax AUD account change)

| Historical cohort | Optimistic all-day | Weekday BTC-only 0 extra cost | Weekday + annual 0.39% NAV drag and 10bp per side | Weekday + 25bp per side | Weekday + 50bp per side |
|---|---:|---:|---:|---:|---:|
| 2017 complete +650/+750/+850 | +0.994% | **0.000% (ZERO BUYS)** | 0.000% | 0.000% | 0.000% |
| 2017 complete +900 | 0% | 0% (no WMA gate) | 0% | 0% | 0% |
| 2021 complete +650/+750 | +2.427% | +2.448% | +2.418% | +2.402% | +2.375% |
| 2021 complete +850 | +2.600% | +2.600% | +2.574% | +2.557% | +2.528% |
| 2021 complete +900 | +2.642% | +2.682% | +2.659% | +2.642% | +2.613% |
| 2025/26 censored +650/+750 | +0.843% | +0.827% | +0.819% | +0.810% | +0.796% |
| 2025/26 censored +850 | 0% | 0% | 0% | 0% | 0% |

These in-sample results are **after-tax total account deltas**, not annual returns or actual ASX:IBIT performance. Extra fees reduce the *relative improvement* because the alternative invests more BTC exposure. They never turn 2.5% into a strategy capable of buying with no valid original gate.

**Major new structural finding**: for 2017 +650/750/850 the one valid below-prior-200WMA fresh BUY opportunity was **a Sunday**. Original weekend-executable BTC proxy purchases ONE time, creating +0.994% extra aftertax portfolio value for 3.0% vs 2.5%; when weekday-only, the strict below-WMA gate clears before next weekday and **NEITHER model buys**. Identical 2017 completed historic baseline cash remains at A$400k. This is a missing-trade opportunity, not a sizing optimization problem. A weekday-only proxy also misses public market holidays (yet real IBIT has holiday exclusions) and may overstate actual execution opportunity.

### Eight deliberate deep-crash counterfactuals — 3.0% vs 2.5%

| Historic-prefix-and-crash stress | Optimistic every-day | Weekday BTC proxy no extra cost | Weekday + 0.39% NAV and 50bp/side |
|---|---:|---:|---:|
| Worst relative after-tax AUD of 8 paths | −3.689% | −3.669% | **−3.758%** |
| Best relative after-tax AUD of 8 paths | +3.991% | +4.172% | +4.111% |
| Number of losing scenarios | 3/8 | 3/8 | 3/8 |

These are adversarial fake bear regimes (not future probabilities), with reference original 2.5% percent BUY rule, no historical personal portfolio sales or ETF quotes. The small 3.0% increase retains its observed benefits in **2021** and incomplete 2025/26 even with the assumed cost range, but incurs approximately 3.8% lower whole-account result than 2.5% in selected severe delayed declines. That is not robust free alpha.

### Verdict and next specific research hypothesis (suggested AFTER seeing outcome)

1. **Do not change current 2.5% BUY percentage based on this**; it is not shown to dominate both rebound and extended crash paths. Keep market WATCH unchanged.
2. **PRIORITIZE weekend-to-next-ASX-day signal preservation with a no-chasing price cap** as a distinct, clearly *post-hoc* proposal. This addresses a demonstrated historical missed execution, unlike changing an amount that cannot trade on Sunday. Never automatically apply stale signals beyond a frozen maximum and retain weekday-only actual eligibility and 7-day executed-transaction cooldown.
3. Actual ASX:IBIT was not listed until Nov14 2025. This study **did not** validate earlier historic IBIT fills and does not prove future returns. Exact live ETF bid/ask, ASX official holiday calendars, realistic limit-order execution and true SMSF tax lots remain necessary before any live rule is promoted.
4. No live Portfolio, single ntfy alert, Production or Streamlit modification. Research-only data archived and merged if QA passes.

