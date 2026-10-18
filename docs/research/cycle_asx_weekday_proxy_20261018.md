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

Result: to be filled with CI exact outcomes.
