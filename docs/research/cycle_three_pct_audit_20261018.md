# Cycle Trading 3% remaining-cash weekly DCA — next test after prior 3.5% evidence

**18 October 2026, Research only. No change to live Cycle Trading, ntfy, Production V5.8.2, Research V5.9, Streamlit, Google Sheets or broker holdings.**

## Hypothesis

The earlier PR #144 established a **measurable observed aftertax benefit** from raising a hypothetical fresh-cash account's real 7-day-cooldown 200WMA BUY from 2.5% to 3.5% of *remaining cash* in both completed historical cycles with eligible buys (relative total account improvement +1.988% to +5.061%). However, deeper delayed BTC declines in the adversarial paths cost up to −6.924% terminal aftertax AUD, with 5% costs up to −15.130%. The objective of this explicit **exploratory parameter choice made AFTER seeing those results** is to assess whether 3.0% preserves some benefit but reduces downside losses. We make no assertion of independent untouched evidence.

Freeze **2.5%, 3.0%, 3.5%** per eligible executed weekly BUY from the *then-remaining AUD cash*, using exactly the same date-exact `replay_exact_live_market_buy` that calls existing `calculate_allocation_signal` and prohibits transactions closer than 7 days. Strictly yesterday's completed BTC close below prior 200-WEEK moving average, not a lagged 200 DAY average. All accounts initially AUD400k fresh cash with no already-owned BTC, no retrospective peak SELL cash. No buying outside eligible WATCH dates, and no invented prior ledger. No modifications to existing live BUY or SELL percentages.

Same completed historic 2017/2021 cash starts +650/+750/+850/+900, incomplete 2025/26 starts observed through Oct 5 2026, same matched AUD USD FX from preceding dated source, A$3 per fill, illustrative FIFO SMSF accumulation final hypothetical CGT, true net BTC and AUD cash carried forward. The same **8 synthetic** 2017/2021 prefix-preserving further 50/70% crashes and two recovery terminal states reused from PR #144 to assess how 3% changes both return and terminal cash reserves. Real IBIT weekends/bid-ask, ETF expenses and tax phase are NOT modelled. These synthetic paths aren't probability forecasts.

**Decision criteria:** show benefit/loss versus *actual current 2.5% rule*, and 3.5% neighbor, across every eligible historical cash cohort and all matched adverse stress cases. Do not assume best 3% score is out-of-sample proof or prefer a version simply because it has a smaller loss than 3.5%. Warn if the major no-fresh-200WMA-crossing failure is not corrected.

CI evidence/results: pending.
