# Cycle Trading research — valuation-aware 52-week BUYBACK with protected cash reserve

**18 October 2026; research-only optional candidate.** Do not change the live Cycle Trading Streamlit, ntfy message, actual broker positions, Google Sheets portfolio, Production V5.8.2, or Research V5.9.

## Motivation and frozen idea

Previous verified matched research [#151](https://github.com/aussiekarl-gif/BTC_Composite/pull/151) established that SELL proceeds can remain almost entirely AUD cash if live BUYBACK only spends 2.5% remaining cash on eligible below-200WMA weeks. [#152](https://github.com/aussiekarl-gif/BTC_Composite/pull/152) demonstrated 24-week full cash deployment can accumulate significant *actual BTC* but suffered **−36.96%** hypothetical terminal aftertax AUD vs original BUYBACK in a deliberate further 70% price decline after the prior 2021 observation. Fixed 52 weeks was slower but also not universally safer.

To avoid cherry-picking 24 or 52 to in-sample BTC lows, this study freezes a **separate economic policy**: half available realised after-CGT AUD to a paced 52-week core, other half held in a deep-discount reserve. No future low or price used for a trade decision.

## Candidate logic, not live approved

1. Cannot activate until **first ACTUALLY EXECUTED** original shared Cycle BUY WATCH using a fully completed prior BTC close STRICTLY below exact 200 *WEEKLY* BTC SMA and an executed BUY meeting the same >=7-day since last portfolio fill rule. In weekday-only proxy, Sunday-only signal cannot activate it; no unverified ETF weekend fill or carry is manufactured.
2. On that first signal use then-existing after-tax realised AUD proceeds, **50%** reserved to a 52-purchase core budget and **50%** placed in a protected cash reserve. Order one core fifty-second (assuming no further net sales), never spend cash that has not actually been realised. Following weeks at least 7 calendar days apart, buy one of the remaining paced core tranches even if BTC recovers above 200WMA, except when shared market signal says SELL WATCH. This is new research-only BUY policy, NOT the existing live BUY percentage.
3. If prior close / prior 200WMA **<=0.85**, spend ADDITIONAL reserve cash capped at **2x that week's normal core order**, provided reserve actually exists. No deeper discount signal, no reserve expenditure. Both core and reserve budgets remain nonnegative.
4. If any additional SELL successfully executes AFTER the first BUY, add **50% of new net after-CGT cash** to scheduled core and 50% to protected reserve, counting only real funding.
5. Stop after at most 52 actual BUYs, no extra cash injections or pre-existing user 2016/2020/2024 BTC owned. An account may end with reserved cash deliberately uninvested. The full 52-buy count may extend beyond 52 calendar weeks if SELL/watch/cooldown interferes with execution.

## Controls and scoring

Compare **exact unchanged original live** 2.5% remaining AUD cash only below each strict 200WMA signal, exact research 24-week full deployment, exact research 52-week full deployment, plus this candidate. Each shares 5 identical isolated SELL portfolios: actual remaining-BTC scheduled + experimental repeated tail; live scheduled-only; two original-BTC staged historical research sellers; buy-and-hold. Every strategy begins with A$500k entirely hypothetical BTC acquired at the 2016/2020/2024 halvings. None of these represent the user's true held IBIT dates/units.

Score actually held BTC, unspent cash (AUD), remaining reserve, BTC equivalent of cash at terminal (separate), aftertax liquidated AUD (illustrative A$3 trade fee, FIFO accumulation SMSF gains and strict dated prior USD/AUD FX), cash-funded order/side dates and missed execution signals. 2017 and 2021 complete to halving+1150, 2025/26 RIGHT-CENSORED through archived 2026-10-05. Run calendar-day BTC/AUD close price proxy and weekday-only price proxy; **neither is true ASX:IBIT bid/ask or official holiday/session calendar**. IBIT only listed ASX 14 Nov 2025.

Adversarial futures freeze each historic prefix and test 2x/4x continuing bull after day600, 50%/70% further bear after day900 to day1060 and terminal at 55% prior price. These are test constructions, NOT independent realisations, probabilities or promised forecasts. 50/50, ratio <=0.85 and 2x extra are *chosen candidate assumptions following repeated inspections of 2017/2021*; never claim out-of-sample validity or optimisation.

**Implementation bar:** candidate must demonstrate robust improvement in both actual BTC and aftertax AUD without gross downside in adverse paths, be independently validated on prospective market snapshots and actual post-2025 ASX:IBIT execution cost/holiday data, and explicitly accepted by user. Existing live BUY/SELL code and production DCA untouched.

Status: CI numeric review pending.
