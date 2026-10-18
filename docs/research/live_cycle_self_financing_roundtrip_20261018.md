# Research — exact live SELL plus 200WMA dynamic BUYBACK full-cycle parity

Date 18 October 2026. New, research-only full-cycle audit: **NO** changes to Production V5.8.2, Research V5.9, Cycle Trading Streamlit allocations, ntfy daily alerts, any broker order or real portfolio.

## Motivation

Merged #150 proved the original historically tested day500 staged SELL engine and LIVE Streamlit/ntfy SELL model are different in original-BTC vs remaining-BTC denominators, price regime gates and endlessly repeating 5%-remaining late-rollover SELLs. SELL-only AUD endpoints cannot establish whether proceeds buy extra BTC later. This resolves that gap by **funding all later BUYs solely from realised SALE proceeds net of illustrative tax**, applying the SAME exact original 2.5%-of-remaining-AUD-cash shared market-level BUY WATCH policy in *every* account, and demanding strict completed prior BTC close below prior 200 WEEK moving average.

## Matched conditions

- Each hypothetical seller begins with AUD500k bought in BTC on the historical BTC halving date, **NOT the user's actual 2026 BTC or post-2025 ASX:IBIT holdings**. Same initial BTC amount for all five policies, no external cash after this entry.
- Five SELL policies: (a) live remaining-holdings scheduled gated + experimental repeated 5%-remaining rollover; (b) live scheduled-only diagnostic; (c) historic staged 90%-core ORIGINAL BTC; (d) historic staged original-BTC 20%-pre560 holdback and later-confirmed breakdown; (e) never SELL / buy-and-hold.
- Unlike #150's SELL-only study, at each date T SELLs are followed by possible BUYs if *and only if* actual shared `calculate_allocation_signal` says BUY WATCH from PREVIOUS BTC close below exact 200 weekly WMA and account has sufficiently large sale cash balance. Spend 2.5% of then-remaining AUD CASH, no special boosted early or recovery sizing, never backdate trades, never buy if no realised cash.
- First earlier planned staged SELL has priority over same-date shared BUY WATCH in the historical seller (explicit simulation choice); real shared market BUY overrides current shared SELL. 7 elapsed calendar days after last ACTUALLY EXECUTED BUY or SELL per account; no repeated signal on same day; no leverage or negative cash.
- Same dated BTC/USD daily close reference and strictly BEFORE-day USD/AUD FX, A$3 simulated brokerage, illustrative immediate SMSF FIFO acquisition-lot tax accrual on each executed SELL. Same hypothetical after-tax liquidation and cash-in-BTC-equivalents at evaluation horizon. Pension-phase and Australian SMSF fiscal-year tax nuances not verified.
- Two execution modes: BTC/AUD daily close proxy including weekends, and optimistic Monday–Friday close proxy excluding weekends but **NOT actual ASX holidays, intraday quotes, spreads, ETF NAV premiums, brokerage matching, whole ETF units or tracking costs**. ASX:IBIT only commenced listing 14 Nov 2025: 2017/2021 were not tradable through this ETF.
- 2017 and 2021 complete observed halving+1150; 2024 halving 2025/26 model cutoff archived 5 Oct 2026 right-censored at halving+898. The user did not have actual ownership on historic halving or day500.

## Independent counterfactual stress

Freeze last real daily close historical prefix through *halving+600*, then generate a strictly increasing hypothetical BTC path ending at 2x or 4x the prefix-date price on day1150. Such models punish early sale and often make buyback unattainable — essential to reject fragile SELL rules. Separately after a historical prefix through day900, simulate additional 50% or 70% BTC declines to day1060 with terminal price at 55% of day900 BTC level at day1150. These 8 scenarios (two completed cycles × two higher rally levels × two deeper declines) are **chosen stress scenarios, NOT market probability estimates or out-of-sample validation**. They are alternative futures from already-inspected historical price prefixes, not changed earlier prices.

## Essential falsification checks

New tests must establish no purchase before any realised SELL, all five accounts with equal initial BTC and separately funded cash, no external investment, EXACT shared market 200WMA gate and 2.5%-remaining sizing, one 7-day executed-trade cooldown per account, no current/next price used to create prior WATCH, stage fractions bounded by initial original BTC, prefix invariance to later prices, no weekend fills in weekday-only mode, stale FX and missing BTC observations fail closed, and no actual IBIT pricing representations. Original current SELL code and its percent rule are imported unchanged.

## Decision gate

Before suggesting implementation, inspect final BTC-equivalent INCLUDING retained cash, actually held BTC, and hypothetical liquidated after-tax AUD vs identical buy-and-hold. NEVER claim the historical staged seller's SELL-only gain as actual achieved BTC units. Check whether the **original live 2.5% residual cash buys back enough coins** before market recovers, and whether the experimental repeated SELL materially harms a sustained bull; evaluate controlled diversification/reserve, not merely past high-in-hindsight. This still does not reproduce actual IBIT fills or user's personal tax lots.

Final numeric evidence: Pending CI review.
