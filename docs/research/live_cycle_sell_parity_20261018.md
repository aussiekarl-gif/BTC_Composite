# Cycle Trading SELL parity against staged original-BTC historical research

## Purpose / status

18 October 2026. **RESEARCH ONLY, UNMERGED UNTIL SUCCESSFUL NUMERICAL REVIEW**. This compares exactly existing `calculate_allocation_signal` used by Streamlit and one daily ntfy, with historically researched stage exits — because SELL percentage denominators and execution triggers differ materially. This is a **model validation** experiment, NOT a claim the current historical 2017/2021/2025 simulations represent the user's actual 2026 account.

Five matched hypothetical accounts start with the **same AUD500,000 direct BTC purchase ON EACH HISTORICAL HALVING DATE**, never claim actual 2026 owner holdings. **ASX:IBIT did not exist before 14 November 2025**; these are BTC/USD next-close A$ converted proxies, not actual ETF quotes, exchange holidays, tracking or spreads. Simplified upfront A$3 brokerage and illustrative FIFO SMSF accumulation-phase short/long realised CGT escrow, strictly PREVIOUS dated AUD/USD FX, same mark-to-market and hypothetical terminal liquidation for all accounts.

1. **Actual live market SELL**: strict prior-close / 200WMA market eligibility from `calculate_allocation_signal`: at halving days 500/525/532/539/546/553/560, only if prior BTC close is at least 1.25x 200WMA and within 5% of prior 90-day high; sells 5/24/20/16/12/8/5% of CURRENT REMAINING BTC. If after day560 and prior price is >=1.4x200WMA, at least 15% below prior 90-day high and below declining 50DMA, can sell an EXPERIMENTAL additional 5% CURRENT REMAINING holdings every 7 executed-trade days. Existing 7-day filled-order cooldown, no fabricated BUY when all starting cash is already deployed.
2. **Live scheduled-only diagnostic**: same shared prior-day market signal and seven-day cooldown, but ignore experimental late >560 SELL. This is NOT a current live toggle; it isolates the unverified tail's consequence.
3. **Research staged 90% ORIGINAL BTC**: unchanged historical pure `staged_day500_dynamic_exit` maturity_90pct, original-denominator distribution and price-regime/tail logic; same USD close/FX execution and SMSF assumptions.
4. **Research staged 90% with original pre560 20% holdback**: historical maturity_90pct_holdback20pct with actual post560 confirmed breakdown exit only.
5. **Buy and hold**: same initial BTC and exact final prices; no sales. Entire account is valued and hypothetical tax on terminal liquidation applies equally.

Score matched accounts on day730 and day1150 after confirmed 2016/2020 halving, and 2024 halving on day730 and latest archived Oct5 2026 before day1150 (RIGHT-CENSORED). Report all true live market SELL WATCHs, dated completed sales, ORIGINAL BTC fraction sold, current remaining units, AUD after actual cash/tax fees, hypothetical liquidation after tax, results vs identical buy and hold and live scheduled-only. Always label 2025/26 incomplete, and do not assume the user held at day500/2025 top.

Stress/evidence: live 7d cooldown, 90d/50DMA conditions, strict previous calendar close, fee/tax and ORIGINAL vs REMAINING BTC denominator invariants and missing prices/FX all tested. We do **NOT** cherry-pick historical staged policy based on terminal account return, or claim the 2025 cycle peak is absolutely known.

No live Cycle Trading BUY/SELL, Streamlit, Production V5.8.2, Research V5.9, Google Sheets portfolio, actual IBIT shares or ntfy changes. Promotion decision remains blocked until closed-market ETF times/actual broker units and genuinely prospective SELL evidence.


## Verified numerical outcome (18 October 2026)

**[GitHub Actions run 39119710423](https://github.com/aussiekarl-gif/BTC_Composite/actions/runs/39119710423) SUCCESS, 31 tests passing**: 8 new true shared-market SELL / conditional-calendar / experimental tail / FIFO invariance tests, 10 current Cycle market-percent tests and 13 existing Cycle Trading sensecheck tests. Full 30 historical account-horizon rows plus transaction-by-transaction BTC SELL details, strictly prior FX and hypothetical SMSF costs are preserved in [artifact 12133488596](https://github.com/aussiekarl-gif/BTC_Composite/actions/runs/39119710423/artifacts/12133488596). The first run caught a harmless unit test rounding error: exact fully-triggered remaining-holdings percentage is **62.6835% of original BTC**, not 62.6800% to 4 decimal places.

All gains below are the **percent change in the entire hypothetically liquidated after-tax AUD account relative to buy-and-hold**, both with the same A$500k BTC purchase at the historical halving date. NOT annualised returns; NOT comparative buyback profits; NOT the user's actual funds or broker inventory.

| Cycle | Evaluation day since halving | Full required window observed? | Current shared market SELL incl experimental rollover | Shared market scheduled-only (experimental late SELL disabled) | Historical staged 90% ORIGINAL BTC core | Historical staged 20% pre560 holdback | Buy & hold reference aftertax AUD |
|---|---:|---|---:|---:|---:|---:|---:|
| 2017 peak cycle / 2016 halving | 730 | yes | **+49.466%** | +41.128% | **+109.539%** | +106.713% | A$4,742,830.62 |
| 2017 | 1150 | yes | **−5.499%** | +12.534% | **+22.614%** | +20.960% | A$8,105,201.47 |
| 2021 peak cycle / 2020 halving | 730 | yes | **+54.460%** | +39.534% | **+95.692%** | +89.677% | A$1,477,495.29 |
| 2021 | 1150 | yes | **+43.646%** | +33.016% | **+79.341%** | +73.828% | A$1,612,205.14 |
| 2025 peak cycle / 2024 halving | 730 | yes | **+23.146%** | +13.629% | **+54.232%** | +53.423% | A$519,135.88 |
| 2025/26 **RIGHT-CENSORED** | requested 1150, only **898 observed** | **NO** | +13.176%* | +9.173%* | +33.798%* | +33.097%* | A$598,418.46 |

*The 2025/26 unfinished observation is strictly through archived **5 October 2026**; terminal at day898. It cannot establish the final low, 2025/26 SELL performance, or imply the real user's 2026-owned BTC existed on halving day2024.*

### Why they differ (measurable, no invented sells)

| Cycle and cutoff | Current shared market conditional scheduled WATCHs | Original seven scheduled review dates | Experimental late rollover market WATCH days | Current live incl rollover executed SELLs | Current live without experimental rollover executed SELLs | Original BTC position distributed by all current live SELLs |
|---|---:|---:|---:|---:|---:|---:|
| 2017 day730 | **2** | 7 | **107** | **19** | 2 | **69.8117%** |
| 2017 day1150 | 2 | 7 | **167** | **31** | 2 | **83.6875%** |
| 2021 day730 | **3** | 7 | **100** | **19** | 3 | **72.9192%** |
| 2021 day1150 | 3 | 7 | **104** | **22** | 3 | **76.7816%** |
| 2025 day730 | **1** | 7 | **61** | **11** | 1 | **52.1010%** |
| 2025 cutoff day898 | 1 | 7 | 61 | 11 | 1 | 52.1010% |

- With all seven calendar scheduled triggers the **current remaining-unit model** would sell 62.6835% of original BTC, but actual price-high and WMA conditions historically permitted only **2 of 7 (2017), 3 of 7 (2021), 1 of 7 (2025)**. The current LIVE scheduled-only portfolios sold respectively 27.8%, 38.4704% and 20% of original BTC at the cohort early evaluation; almost all the exposure remained.
- The existing **EXPERIMENTAL late-top rollover** (strict ratio>=1.4, prior90 high drawdown>=15%, below declining 50DMA, age>560) produces an actual SELL WATCH on many days (107/100/61 days through day730 for the respective cycles); when eligible, live seven-day executed SELL cooldown caps actual orders to 19/19/11 by day730. **This is a recurring SELL rule**, not just a single safety trade after a peak.
- By day1150, the live experimental tail's 31 2017 SELLs (83.6875% original BTC disposed) had **lower total hypothetical after-tax AUD than buy-and-hold (−5.499%)**, even though the live scheduled-only version scored **+12.534%**. This demonstrates the experimental tail is not unconditionally safe: repeated exits can cause significant rebound opportunity cost.
- Existing original-BTC historical staged `maturity_90pct` exited fully by day730 in 11/10/11 trades for 2017/2021/2025; the capped 20%-pre560 original-BTC variant also sold 100% by day730 in the completed or observed histories, after confirmed late breakdown. **Neither historic stage uses the same trigger conditions or same percentage denominator as live.** Claiming staged after-tax uplifts as results for Streamlit's SELL policy would be demonstrably false.

### What is and isn't actionable

1. **High-priority model discrepancy, not automatic proof of a better exit rule.** The original-BTC historical staged exits strongly beat the live market SELL policy in the two completed historical cycles at both endpoints, but the stages were designed with hindsight over these same cycles, are much more aggressive and can be devastating in a future uninterrupted BTC bull rally.
2. **Strong caution about repeated 5% experimental rollover**: changes cumulative BTC disposed, produces a 2017 day1150 underperformance vs hold, and lacks independent prospective confirmation. Before any live action, replay "once per distinct breakdown regime" vs repeated signals with the exact same current portfolio + ASX clock, all fees and SMSF tax-lot phase. A single experimental signal before a genuine 50% crash might still be protective; do not indiscriminately disable or expand it.
3. **Data/interpretation limits:** pre-2025 ETF prices cannot exist; user did NOT own BTC at historical halving dates; future FX not used; 2025 cycle right-censored; BTC close fill is non-executable proxy; tax assumption is illustrative; no actual user SELL quantities, broker confirmed units, calendar constraints or personal portfolio read. This SELL-only study does **not** model deploying sale proceeds to later BTC buys, so the historic "maximise BTC units" goal still needs a self-financing roundtrip parity experiment.
4. **Promotion gate:** only after a real same-person, same-start-cash, ASX-day-executable, current-portfolioparcel / after-tax BUY-BACK comparison and forward logs can the user judge whether the added transaction risk is worth changing model's live SELL tranche percentages.

**Decision: preserve untouched live Cycle Trading streamlit, single ntfy, saved portfolio, Production V5.8.2, Research V5.9; merge this numerical audit research-only and move next to full SELL+BUY-BACK parity and adverse trending market stress.**

