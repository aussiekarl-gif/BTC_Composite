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
