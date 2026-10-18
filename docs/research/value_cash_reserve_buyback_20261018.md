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


## Verified numerical outcome — 18 October 2026

[GitHub Actions run 39122742049](https://github.com/aussiekarl-gif/BTC_Composite/actions/runs/39122742049) **SUCCESS, 34/34 tests passing**: 8 new value-reserve gate/overspend/future-invariance tests, 8 unchanged fixed24/52 tests, 8 current full Cycle ledger tests, and 10 original shared market signal-percent tests. Matched original 2.5%, fixed24, fixed52 and new value-reserve exact dated order ledgers, real source price history and 8 synthetic future variants [artifact 12134399617](https://github.com/aussiekarl-gif/BTC_Composite/actions/runs/39122742049/artifacts/12134399617). Existing [full-cycle PR151](https://github.com/aussiekarl-gif/BTC_Composite/pull/151) and [fixed BUYback PR152](https://github.com/aussiekarl-gif/BTC_Composite/pull/152) workflows also reran with the candidate branch for regression assurance.

### Historical after-tax comparison: hypothetical ORIGINAL90%-BTC staged SELL, weekday-only BTC closing-price reference

| Observed historical period | Buyback | Actually owned BTC at cutoff | Unspent AUD | Value-reserve protected AUD left | After-tax terminal AUD vs UNCHANGED live-style 2.5% BUYback |
|---|---|---:|---:|---:|---:|
| 2017 COMPLETE | Strict LIVE 2.5% only below prior200WMA | 458.6478 | A$1,222,798 | n/a | BASE |
| 2017 | 24 finite | 458.6478 | 1,222,798 | n/a | 0% |
| 2017 | 52 finite | 458.6478 | 1,222,798 | n/a | 0% |
| 2017 | **Value 50/50 reserve** | 458.6478 | 1,222,798 | 0, never activated | 0% |
| 2021 COMPLETE | Strict LIVE 2.5% only below prior200WMA | 60.8547 | A$1,064,397 | n/a | BASE |
| 2021 | 24 finite | **96.0477** | A$0 | n/a | **+12.518%** |
| 2021 | 52 finite | **90.1960** | A$0 | n/a | **+6.252%** |
| 2021 | **Value 50/50 reserve** | **78.1851** | **A$549,440** | **A$549,440** | **+6.236%** |
| 2025/26 RIGHT-CENSORED Oct5 2026 | Strict LIVE 2.5% | 4.0674 | A$143,113 | n/a | BASE |
| 2025/26 censored | 24 finite | 5.0157 | A$48,589 | n/a | +3.031% |
| 2025/26 censored | 52 finite | 4.3628 | A$112,128 | n/a | +0.739% |
| 2025/26 censored | **Value 50/50 reserve** | **4.0830** | **A$139,360** | **A$83,295** | **−0.244%** |

All accounts begin at each BTC halving with A$500k BTC (hypothetically) and follow ORIGINAL90 staged SELL with the SAME FX, BTC close and approximate SMSF FIFO CGT. These are BTC quantities **actually owned**, not BTC-equivalent including cash. Prior to Nov2025 ASX:IBIT didn't trade; all prior weekday fills are counterfactual BTC/AUD proxies. The 2025/26 market is not confirmed at terminal; only observed 898 days of the current cycle in our archive.

### Price decision and stress trade-offs

For the same ORIGINAL90 SELL plus **weekday-only** execution scenario, artificial next-future paths frozen after historical prefixes and benchmarked against the unchanged live strict 2.5% BUYback:

| Adversarial future after completed cycle prefix | 24-week full allocation: aftertax AUD vs LIVE | 52-week full allocation: aftertax AUD vs LIVE | New 50/50 value reserve: aftertax AUD vs LIVE |
|---|---:|---:|---:|
| 2017 +50% extra drawdown after day900 | −1.014% | +0.581% | **+1.280%** |
| 2017 +70% extra drawdown | +5.699% | +1.802% | **+5.446%** |
| 2021 +50% extra drawdown | **−29.293%** | −4.204% | **−6.001%** |
| 2021 +70% extra drawdown | **−36.960%** | +6.704% | **+3.951%** |
| 2017 and 2021 sustained post-day600 2x/4x bulls | **no initial qualifying BUY**, same original SELL cost | same | **same** |

The reserve strategy materially reduces some adverse losses relative to 24week full deployment, but **does not dominate original strict 2.5% or fixed52**. Notably 2021 +50% delayed drop costs −6.001% vs original strict and fixed52 −4.204%. The recent (still incomplete) 2025/26 staged SELL weekday case is −0.244% against original live BUY; the user's actual independent holdings do not match these hypothetical pre-2025 accounts.

For CURRENT live conditional SELL + repeated late rollover (not historical original90), 2021 weekday-only: original live strict 2.5% had 49.8927 BTC and A$723,505 unspent; value50/50 had 61.6724 BTC (+23.61% actually held) and A$373,472 unspent, ending **+5.452% total hypothetical aftertax AUD** vs live strict. 2017 weekdays no actual first gate, same orders and net AUD. 2025/26 CURRENT live SELL with weekday-only value50/50 had 3.4053 BTC (+0.755% actual BTC) but **−0.388% aftertax AUD** vs unchanged live, with A$225,928 residual (A$135,038 still in reserve).

### Research decision

**Keep candidate for prospective tracking, do not activate in Streamlit/ntfy.** Half reserve protects uninvested cash but also creates meaningful opportunity cost in rising markets; drawdowns that continue after a first recovery can still cause underperformance despite using lower-risk initial deployment. The 52-week equal-remaining-tranche full allocation achieves more observed BTC in 2021, but has no reserve at terminal and does not universally dominate stress. Historical results are in-sample and the 2017 Sunday gate remains missed under real weekday-only policy. No 2017 results should be advertised as an actual ASX:IBIT execution.

Correct next priorities: run independent post-listing verified IBIT weekday price/spread + ASX holiday calendar, and **prospective shadow tracking** using existing current forward-only market signal tape rather than retuning reserve split or WMA discount thresholds to the same 2017/2021 completed cycles. **Do not increase user ntfy frequency**. A weekly conditional readiness monitor already exists, not a second alert. Don't edit live Cycle Trading, Research V5.9, Production, personal Google Sheet or broker until stronger evidence and user's explicit selection.

