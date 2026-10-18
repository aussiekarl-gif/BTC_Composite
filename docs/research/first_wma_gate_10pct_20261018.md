# Frozen 10%-of-original fresh-cash BUY at first completed below-200WMA crossing (18 October 2026)

Research only. **Never trade, update Streamlit, ntfy, V5.8.2, V5.9, Google Sheets or actual holdings from this experiment.**

## One hypothesis predeclared before testing

Existing original fresh-cash rule (PR #126) invests **2.5% of ORIGINAL new AUD cash** on the *first* strictly prior-close below strict prior 200-WEEK moving average (200 spaced weekly samples), then every 7 days with unmodified prior-price adaptive-recovery tiers (2.5%, 15%, 4.5%, or 1% original). New candidate instead invests **10% of original AUD cash ON THAT FIRST GATE ONLY** and uses exactly those same existing subsequent weekly tiers, with no extra buy dates or WMA threshold shifts. It is *not* a 7.5% transfer from a known later scheduled tranche: faster cumulative deployment entails additional early downside risk.

- Start each hypothetical self-financing portfolio with exactly A$400,000 **fresh AUD cash**, no BTC held at prior halving, no 2025 sales or tax proceeds credited, no borrowings.
- Compare against unchanged original gate and current daily 2.5%-of-remaining-cash below-WMA, 52-week weekly DCA, and first-day lump sum. Same historical BTC closes and dated prior AUD FX, A$3 fee/fill, indicative FIFO immediate SMSF CGT and terminal liquidation.
- Previously inspected complete cycles: 2017 and 2021, start day+650/+750/+850/+900; right-censored 2025/26 to 5 October 2026. If the gate never fires, the candidate must buy zero.
- Explicit **exposed delayed-bottom synthetic shocks** from historically observed prefixes, beginning cycle 2017 cash +750 at shock day960 and 2021 cash +650 at shock day900, forced 50%/70% later drawdowns toward day1060 with terminal .55/1.05 of pre-shock spot. Synthetic scenarios are NOT price predictions or probabilities.
- Report aftertax AUD and relative % differences, bought BTC, cash left, average BTC/USD buy price over eventual retrospectively observed low, drawdown, dates and order ledger. A lower buy-error with 90% still in cash is not equivalent to a better portfolio.
- Compare candidate `first_wma_gate` to reference exactly. Confirm the *2.5% reference* is identical to independent existing `matched_fresh_cash_replay` on every scenario. Prefix invariant and missing price/FX tests.
- No post-result parameter re-tuning; reject as an unvalidated live strategy even if results favorable in only the previously observed cycles. Label incompleteness and price-close vs actual ASX IBIT execution.

Run `python -m engines.research.first_wma_gate_10pct --out artifacts/first_gate_10pct` and workflow `.github/workflows/first_wma_gate_10pct.yml`.

CI produces complete matched historical and shock summaries, but **the pass/fail of automated tests does NOT mean the investment hypothesis passed**. Review actual returns and adverse path first.


## Actual CI results and decision (18 October 2026)

**DECISION: REJECT AS LIVE RULE; close PR without merge.**
[GitHub Actions run 39104147775](https://github.com/aussiekarl-gif/BTC_Composite/actions/runs/39104147775) passed **7 candidate-specific + 8 baseline + 8 shared-policy tests**; the historical and eight-scenario synthetic audit passed exact independent original baseline parity. Full [CSV and JSON evidence artifact](https://github.com/aussiekarl-gif/BTC_Composite/actions/runs/39104147775/artifacts/12128230192). Results are **percentage difference of illustrated terminal post-liquidation-tax AUD** vs the original fresh-cash fixed-budget weekly gate, not BTC absolute returns.

| Previously observed cohort | Initial cash entry offset | Gate from strict previous-close-below-200WMA | 10% first-gate vs original aftertax AUD | Candidate BTC/USD buy VWAP error vs observed later trough | Original buy VWAP error |
|---|---:|---|---:|---:|---:|
| 2017 | +650,+750,+850 | 2018-12-16 | +1.709% | 16.57% | 18.60% |
| 2017 | +900 | NONE | 0.000% | no buy | no buy |
| 2021 | +650,+750 | 2022-06-15 | **-0.858%** | 28.75% | 27.39% |
| 2021 | +850 | 2022-09-09 | +1.736% | 34.24% | 36.77% |
| 2021 | +900 | 2022-10-29 | +1.582% | 41.54% | 44.52% |
| 2025/26 **INCOMPLETE** | +650,+750 | 2026-06-06 | +1.654%* | 18.05%* | 20.34%* |
| 2025/26 **INCOMPLETE** | +850 | NONE | 0.000%* | no buy | no buy |

*Right-censored at 2026-10-05, cannot infer a completed BTC cycle bottom or final return.*

**Deliberately adverse delayed bottoms**: original 2017 price prefix to day960, original 2021 prefix to day900, followed by invented 50/70%-drop-to-day1060 and .55/1.05 pre-shock terminal. ALL 8 exposed scenarios showed **negative aftertax terminal relative performance** versus the unchanged 2.5% first-gate reference: range **-1.976% to -6.572% for 2017 prefix**, and **-3.145% to -6.229% for 2021 prefix**. This is a deterministic stress not a statistical loss-frequency forecast.

The original remains more resilient to severely delayed/deeper bottoms; 10% improves 2017 but fails to hit the 20% average-buy-price-error stretch goal in most 2021 starts. **Do not promote**, do not redesign the threshold from these same already-seen cycles, do not add a second daily ntfy or touch actual holdings. Before recommending a changed investment amount, use the actual 2026 IBIT holdings, recorded trades, present available brokerage cash and tax escrow. Real ETF fills and SMSF financial-year tax are not proven by this BTC-close/FIFO proxy.
