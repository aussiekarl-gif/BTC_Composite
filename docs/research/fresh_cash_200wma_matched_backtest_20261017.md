# Matched fresh-cash Bitcoin DCA — original 200WMA fixed budget vs today's simplified BUY

**17 October 2026 | PR #126 | Research only — do not promote into live Streamlit/ntfy**

## Main conclusion

**The 2026-style fresh-cash version of the original 200WMA recovery rule does not consistently beat today's 2.5%-of-remaining-cash daily BUY rule.** The fixed-budget policy has an exceptionally strong 2017-based retrospective result but nearly no incremental advantage in the earlier 2021-based starts, and **underperforms by 7.76% and 16.88%** at later 2021-based starts. The more fundamental danger: where no *fresh* close-below-200WMA occurs AFTER the start date, both gated policies can leave 100% AUD idle throughout a rising BTC market.

Do **not** replace current live 2.5% ntfy allocation or attribute the historical day500 SELL→200WMA BUY aftertax +217%/+154% to a cash-only 2026 portfolio. This report tests **ONLY buying** into an initially **cash-funded** account; NO original BTC was previously owned, and NO 2025 top SELL cash is fabricated.

## Exactly matched research design

Each scenario starts with **A$400,000 uninvested** on halving+650/+750/+850/+900 calendar days, no BTC and no simulated prior SELL. It ends on halving+1150 for the complete historic 2017 and 2021 cycles, and at last saved 5 Oct 2026 close for the incomplete 2025/26 cycle. Only future observation dates occurring strictly after the chosen start are eligible. Four independent portfolios share BTC/USD source, dated FX, an A$3 fee per fill, close-price BTC execution proxies, and hypothetical FIFO SMSF accumulation CGT at terminal liquidation. Price and moving average eligibility is based on exactly 200 seven-day-spaced **previous daily closes**, excluding the current day's execution close. No look-ahead in the decision mechanics. **FX always comes from the preceding dated USD/AUD record**, not a future rate.

BUY strategies:

1. **Original 200WMA recovery, fresh-cash adaptation:** First prior-completed daily BTC close strictly below prior 200WMA after start activates a weekly sequence: 2.5%, 15%, 4.5% or 1% of the **FIXED initial A$400k budget**, using original `recovery_buy_budget_fraction()` conditional tiers; continues when BTC rebounds, even above WMA, as original model intended.
2. **Current simplified daily BUY rule:** On **every daily** eligible previous-close-below-prior-200WMA signal, spend 2.5% of **REMAINING cash**. No continuing recovery buys when above 200WMA. This follows the existing live daily research BUY sizing; historical BUY-only simulation ignores future SELL signals (none of the portfolios starts with a BTC position).
3. **52-week fixed DCA:** Approximately A$7,692.31 each 7 days independent of BTC price, until budget exhausted or window ends.
4. **Lump sum:** Use all initial A$400k at the first observed close after the start. This is an **opportunity-cost comparator**, not a risk-free recommended portfolio.

For a prospective start, the follow-on conditional weekly percentages are unknown in advance. A strict no-gate start is a real risk. **Average fill price within 20% of the future bottom** is not equivalent to higher final wealth: buying only a tiny amount at the exact low could score an excellent average price while leaving 97.5% idle.

## Completed historical observation windows

All figures below are **after hypothetical SMSF liquidation CGT**, in **AUD**, on the same terminal date within each cohort. "Forward vs existing" is a RELATIVE portfolio value change `(forward/current-1)*100`, **not** an absolute investment return.

| BTC cycle | Cash begins | Forward fixed-budget A$ | Current remaining-cash A$ | Forward vs current | Forward BUY VWAP above hindsight low | Forward end cash | Current end cash |
|---|---|---:|---:|---:|---:|---:|---:|
| 2017 | 20 Apr 2018 (+650) | **1,048,235** | 420,908 | **+149.04%** | 18.60% | 0% | **97.50%** |
| 2017 | 29 Jul 2018 (+750) | **1,048,235** | 420,908 | **+149.04%** | 18.60% | 0% | **97.50%** |
| 2017 | 6 Nov 2018 (+850) | **1,048,235** | 420,908 | **+149.04%** | 18.60% | 0% | **97.50%** |
| 2017 | 26 Dec 2018 (+900) | 400,000 | 400,000 | 0% | No BUY | **100%** | **100%** |
| 2021 | 20 Feb 2022 (+650) | 584,508 | 580,866 | +0.63% | 27.39% | 0% | 1.00% |
| 2021 | 31 May 2022 (+750) | 584,508 | 580,866 | +0.63% | 27.39% | 0% | 1.00% |
| 2021 | 8 Sep 2022 (+850) | 541,440 | **587,000** | **−7.76%** | 36.77% | 0% | 1.00% |
| 2021 | 28 Oct 2022 (+900) | 517,280 | **622,337** | **−16.88%** | 44.52% | 0% | 2.24% |

Why 2017 is unusual: the simplified rule had one daily 2.5% BUY opportunity near the later observed bottom, and then BTC crossed back above 200WMA, leaving **97.5% cash**. The original activated weekly recovery model continued purchases and deployed its budget; that comparison is NOT a general prediction that fixed-budget always wins. Starts after the last below-WMA crossing, such as 26 Dec 2018, yielded **no purchases by either gated rule**. The immediate lump-sum comparator for that late 2018 start reached **A$1,089,506**, showing material missed upside — it also carried full downside exposure.

For the 2021-based **28 Oct 2022** start, 150 eligible daily buys invested the existing model over time, while the original weekly strategy deployed the budget in 24 fills at a higher VWAP and finished significantly behind. It is NOT accurate to say the original always wins because its percentage per tranche is larger.

## Incomplete 2025/26 observation, ending 5 October 2026

| Hypothetical new cash begins | Forward fixed-budget A$ | Existing remaining-cash A$ | Forward vs existing | Fixed weekly DCA A$ | Immediate lump A$ | Caution |
|---|---:|---:|---:|---:|---:|---|
| 30 Jan 2026 (+650) | **483,584** | 466,144 | +3.74% | 455,205 | 434,606 | Incomplete cycle |
| 10 May 2026 (+750) | **483,584** | 466,144 | +3.74% | 433,666 | 431,837 | Incomplete cycle |
| 18 Aug 2026 (+850) | 400,000 | 400,000 | 0% | 405,870 | **491,187** | Both gated strategies bought **zero BTC**, still 100% cash |

For the late August 2026 historical cash-start scenario, the immediate-buy hypothetical gained **22.8% after terminal liquidation CGT** to the cutoff, while waiting for a *new* prior-close-below-WMA gate held all A$400k in cash. Future BTC performance is **not** observed beyond 5 Oct 2026, and the scenario is **not** a statement about the user's actual holdings, their IBIT ETF or the current market close on 17 October 2026.

## What the original price-error target does and does not mean

On completed historical periods in which fixed-budget recovery buying was actually activated, its average BTC/USD purchase VWAP error above the ex-post low ranged **18.60%–44.52%**; the last 2021-based start missed the 25% central goal and 20% stretch target. Starts where it never bought have **no meaningful VWAP**, not a perfect 0% error. Outcomes cannot be promoted based only on historically favorable +149% scenarios. Both DCA and waiting can sacrifice gains when BTC appreciates.

The retrospective historical dataset has been inspected and thresholds discussed extensively; two complete cycle samples and three incomplete 2026 starts cannot establish prospective reliability, and initial dates were fixed for *comparison* but not untouched out-of-sample validation. No probability-weighted score or assured 20% execution error has been established.

## Important real-execution shortcomings

- Actual IBIT trades take place only in ASX sessions at ETF quotes with tracking error, whole units, brokerage, bid/ask spreads and AUD/FX movements. BTC trades 24/7. This simulator uses **BTC daily close** even on weekends and holidays. Results are **optimistic BTC-price proxies** for IBIT.
- The compared historical aftertax values use a simplified complying **accumulation** SMSF 10% long-term / 15% short-term gain liability if the portfolio is hypothetically liquidated at the end, not actual annual tax timing/pension qualification or real user's tax parcels.
- The A$400k capital is **hypothetical**, not the user's verified current free cash. Tax, liquidity, wallet holdings, ETF orders and declared expense reserves not independently checked.
- No trades from the 2025 prior halving cycle are assumed; **BUY-only** research cannot show effectiveness of original day500 staged SELL or predict the next top.

## What this changes

**Only new Research files + CI tests and report.** No updates to original strategy, forward enrolment #125, current live simplified Streamlit BUY/SELL recommendation, ntfy alerts, Production V5.8.2 / Research V5.9, user Google Sheets cash and trades, broker or real orders.

Recommended next action is **NOT to activate** the fixed-budget 200WMA candidate as the live replacement yet. Evaluate missed-opportunity/entry alternatives and verify the true 2026 portfolio cash position first; if new hypotheses are pursued, declare them explicitly as NEW and stress their false-entry downside rather than assuming the original historical full-cycle strategy proves them.

## Reproducibility

- Engine: `engines/research/fresh_cash_200wma_matched_backtest.py`
- Tests: `tests/test_fresh_cash_200wma_matched_backtest.py`
- CI: `.github/workflows/matched_cash_200wma_buy_backtest.yml`
- Dated full trade records: GitHub Actions artifact **matched-cash-200wma-buy-only-research**
