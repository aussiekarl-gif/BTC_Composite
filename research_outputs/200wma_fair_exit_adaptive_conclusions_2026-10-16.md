# AUD after-tax fair exit and adaptive BTC 200WMA challengers — 16 October 2026

**Research-only. Production V5.8.2 and frozen prospective VBTC paper v1 are unchanged. No trade or promotion recommended by these tests.**

**Verified:** [GitHub Actions run 38822949971](https://github.com/aussiekarl-gif/BTC_Composite/actions/runs/38822949971), passed all checks, produced three retained artifacts:
- `aud-btc-causal-fx-input-fair-exit` — source-derived BTC/AUD weekly input matched to archived completed-week BTC/USD 200WMA source;
- `aud-btc-fully-liquidated-fair-exit` — 2-, 3-, and 4-year DCA vs tier tax-corrected comparison;
- `aud-btc-adaptive-sell-reentry-challengers` — six scenario backtests on exactly the same dates and prices.

## 1. Corrected after-tax measurement

The prior accumulation SMSF backtests subtracted capital-gains tax on **trading strategy sales** but divided by the DCA portfolio's gross mark-to-market wealth, without including tax on a final disposal of DCA's remaining ETF holdings. Those results mixed accounting treatments and should no longer be used as the headline 'after-tax vs DCA' metric.

**Corrected:** For every shared AUD exit date, fully sell **both** models' remaining hypothetical ETF units at the identical weekly BTC/AUD reference price, apply identical A$20 disposal brokerage, 0.1% dealing fee, 0.5% slippage, and FIFO complying-SMSF **15% accumulation-phase CGT** with a one-third discount on eligible held-over-12-month lots. Already-paid modelled early-July annual CGT is deducted from strategy cash at the time of payment and is **not charged twice** upon exit. Buys, cash budgets, valuation history and terminal dates are identical across all candidates and DCA.

| Fixed exit horizon | Overlapping cohorts | Prior *unmatched-tax* tier median | Corrected tier median vs after-tax DCA | Corrected wins | Corrected worst |
|---|---:|---:|---:|---:|---:|
| 2 years | 89 | +2.402% | **+4.257%** | 57/89 | **−55.288%** |
| 3 years | 76 | +26.304% | **+30.070%** | 48/76 | **−47.953%** |
| 4 years | 63 | +33.099% | **+38.414%** | 55/63 | **−23.718%** |

The matched DCA model's median **additional CGT triggered by final liquidation** was approximately **A$58,103 / A$85,139 / A$128,731** for 2 / 3 / 4-year cohorts respectively. These are cross-cohort medians, **not an individual SMSF forecast**. Model inputs are historical BTC/AUD synthetic ETF-equivalent prices with hypothetical management-fee drag, **not actual VBTC issuer prices before 2024**.

## 2. Exploratory causal sell/reentry challengers

**No hyperparameter optimisation was run in this experiment.** Six specified policies were applied to the same 89, 76 and 63 overlapping fixed-horizon cohorts. Decisions use only BTC/USD data through the **previous completed weekly close** with next-week AUD execution prices:

- **Current baseline:** 10 buy and 10 sell 200WMA deviation thresholds; 12-week bell buys, 16-week bell sells; overlapping orders per tier blocked; no reverse cancellation.
- **Trend-weakness sells:** keep the original upward sell-tier trigger but only execute its 16-week sell schedule if BTC's last completed weekly close is **at least 5% below its recent eight-week high**. A sell job may expire unfilled.
- **Breakout reentry:** keep original sells. After any tier sale, use up to **25% of free cash** if the prior completed close breaks the preceding **eight-week high** and is **over 3% higher than four weeks earlier**, provided cash exceeds **40%** of marked holdings; twelve-week reentry cooldown; no active tier buys.
- **Both:** trend-weakness sell gate plus the breakout reentry.
- **40% exposure cap plus breakout reentry:** restrict the amount sold so total cash/funding/reserved cash does not exceed 40% of marked holdings, combined with momentum reentry.
- **26-week idle-cash rule:** the existing exploratory reentry control, buying 25% of excess cash after 26 weeks without buys if cash exceeds 50% of marked holdings.

**Median fully liquidated wealth advantage over identical DCA (percentage):**

| Research variant | 2-year | 3-year | 4-year |
|:--|--:|--:|--:|
| Original tiers | **+4.257** | **+30.070** | **+38.414** |
| Sell only on 5% weakness | +4.038 | +28.111 | **+46.372** |
| Eight-week breakout reentry | +3.679 | +23.631 | +34.565 |
| Sell weakness + breakout reentry | +2.588 | +16.978 | +37.909 |
| Cash ceiling 40% + breakout reentry | +1.822 | +10.105 | +12.712 |
| 26-week idle cash recycle | +5.119 | +25.086 | +40.377 |

**Worst outcome versus DCA in the same matched historical sets:**

| Research variant | 2-year | 3-year | 4-year |
|:--|--:|--:|--:|
| Original tiers | −55.288% | −47.953% | −23.718% |
| Sell only on 5% weakness | −47.545% | −42.463% | −19.204% |
| Eight-week breakout reentry | −44.883% | −41.689% | −18.524% |
| Sell weakness + breakout reentry | −38.350% | −38.584% | −15.913% |
| Cash ceiling 40% + breakout reentry | **−26.827%** | **−26.008%** | **−13.083%** |
| 26-week idle cash recycle | −44.142% | −38.254% | −13.426% |

**Winning starts against matched liquidated DCA:**

| Research variant | 2-year (of 89) | 3-year (of 76) | 4-year (of 63) |
|:--|--:|--:|--:|
| Original tiers | 57 | 48 | 55 |
| Weakness sells | 56 | 47 | 57 |
| Breakout reentry | 55 | 49 | 57 |
| Combined weakness + reentry | 53 | 45 | 58 |
| 40% exposure cap + reentry | 51 | 47 | 57 |
| Existing 26-week recycle | 56 | **52** | **61** |

## 3. What we learned

- **Sell confirmation does not dominate.** An eight-week 5% pullback gate **raised four-year median advantage** from +38.4% to +46.4%, while **lowering two- and three-year median advantages** and reducing median four-year sell fills from **186 to 88**. It improved the lower tail in each horizon but still suffered a **−47.5%** worst two-year relative outcome.
- **Momentum reentry is not a free improvement.** Uncapped breakout reentries can reduce idle cash, but four-year median was **+34.6%**, below the existing +38.4% tiers; combined sell-and-reentry median was +37.9% over four years, but only +17.0% over three.
- **Exposure caps act like downside insurance.** The 40%-cash-plus-reentry strategy reduced the two-year worst case to **−26.8%**, but four-year median dropped to **+12.7%**—a large opportunity cost.
- **The existing 26-week cash-recycling hypothesis remains competitive on this in-sample evidence:** two-year +5.1% median and −44.1% worst; four-year +40.4% median, **61/63** winning overlapping cohorts, worst −13.4%. Nevertheless it is derived from inspected periods and remains unproven.
- **Poor historical timing remains unresolved.** In two-year starts during 2019, the original model's median was −26.164% versus DCA and the sell-weakness challenger −17.843%; only **1 of 13** such starts won. In 2023, original median −9.547% and weakness challenger **−10.656%** (2/13 wins). Thus the new rules do not reliably repair the already-known failure periods.
- The **three-year test is decisive against overconfident selection**: no adaptive variant increased the three-year median over the original, though several reduced worst-case losses.

## 4. Methodological limits and hard decisions

1. The same 2018–2024 historical periods have already influenced the candidate choices; 89/76/63 overlapping starts are **not independent trials**. These results are **hypothesis-generation**, not out-of-sample validation or an expected future return.
2. Every series is a hypothetical synthetic AUD BTC ETF proxy based on archival USD price and public USD/AUD FX, with a 0.45% annual notional management-fee decay. Historical **actual** VanEck VBTC traded-price history begins only in June 2024; it cannot retroactively validate 2019/2023 cohorts.
3. VBTC's reported last trade is not an executable quote. These tests assume 0.1% fees, 0.5% slippage, and A$20 brokerage on all fills, including final disposal. No live ASX spreads, liquidity impact, actual ETF income/distribution attribution, actuarial ECPI, pension-phase exemptions, real ATO due-date financing, ETF unit lot selection or other SMSF assets.
4. The reconstructed FX input is archived as the run's own artifact to preserve what the live public providers supplied. Historical updates can revise those providers; do not mix price vintages across independent reports without reconciliation.
5. **Do not promote** any challenger to Production V5.8.2, Research V5.9 default trading rules or frozen prospective [paper v1](https://github.com/aussiekarl-gif/BTC_Composite/blob/research/cycle-strategy-optimization/research_forward/200wma_v1/README.md). All adaptive features were added as **opt-in and default-off** controls in the Research simulator.
6. Next gates: reproduce against issuer VBTC price/NAV within real history, stress alternate spread/brokerage assumptions, check trade/lot tax constraints and collect **untouched prospective weekly evidence**. Only then consider pre-registering a paper v2—not retrospectively altering paper v1.

## Code changes and validation

- [`terminal_liquidation.py`](../engines/research/terminal_liquidation.py): side-by-side final ETF disposition with FIFO SMSF CGT for **both** models, no tax double count and no ledger mutation.
- [`test_200wma_fair_liquidation.py`](../engines/research/test_200wma_fair_liquidation.py): independent cash-only DCA reference and 2/3/4-year common dated exit.
- [`test_200wma_adaptive_challengers.py`](../engines/research/test_200wma_adaptive_challengers.py): controlled sell confirmation, breakout reentry and exposure-aware comparisons.
- [`test_terminal_liquidation_checks.py`](../engines/research/test_terminal_liquidation_checks.py) and [`test_adaptive_200wma_checks.py`](../engines/research/test_adaptive_200wma_checks.py): FIFO tax discount, paid-tax reconciliation, exit dealing costs, opt-in default parity and no use of future prices.
- [`research_fair_exit_challengers.yml`](../.github/workflows/research_fair_exit_challengers.yml) runs all tests and archives the BTC/AUD provider snapshot and full per-cohort JSON.

**Decision:** **Keep all three currently frozen paper models unchanged.** Retain weakness-gated selling and the other variants only as experimental challengers. The return-risk tradeoff and poor 2/3-year tails mean none is a verified improvement suitable for money deployment.
