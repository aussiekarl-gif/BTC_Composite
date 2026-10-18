# BTC Cycle: 24 / 52 weekly buyback schedule AFTER first strict 200WMA gate

18 October 2026. **RESEARCH ONLY, opt-in candidate, not current Cycle Trading rules.** Do not change Streamlit BUY/SELL, Production V5.8.2, Research V5.9, personal BTC/ASX:IBIT portfolio, Google Sheets or one ntfy daily message.

## Reason

Merged PR #151 demonstrated a major *cash-rich, BTC-poor* failure of the current post-sale buyback in the 2017 historical proxy: with BTC initial purchases made hypothetically at the 2016 halving and the historical 90%-original BTC staged SELL rule, actual BTC after buyback at day1150 was **62.2096 BTC + A$9.606m uninvested cash**, vs buy-and-hold **580.0424 BTC**. Despite attractive hypothetical +29.116% aftertax AUD account returns, most SALE proceeds were not reinvested: current 2.5%-of-remaining cash requires prior close below 200 WEEK MA ON EVERY new weekly purchase, and 2018 just one Sunday eligible date.

Goal for new in-sample experiment: keep EXACT same prior-data, date-accurate, illustrative FIFO/AUD tax seller and prior-WMA FIRST buy gate; once a BUY is actually executed, precommit to up to **24 or 52 weekly at-least-7-calendar-day-spaced BUYs** from then-available aftertax AUD cash, **even if BTC has recovered above the 200WMA**. No purchase before original WMA gate. No future bottom knowledge. A dynamic `remaining cash / remaining scheduled purchase tranches` fraction deploys the cash in a predetermined number of purchases; in the 24-tranche policy a last remaining balance may be large if few planned tranches are left, and a sharp price recovery can make chasing price very expensive.

## Exact three matched buyback policies

1. **Original live 2.5%** remaining aftertax available AUD cash only WHEN the prior BTC/USD completed close is strictly below prior 200 spaced WEEKLY closes, 7-day executed BUY/SELL ledger cooldown. NO change.
2. **24 executed-weekly-order candidate**, first actual fill must satisfy original live BUY WATCH; from then on up to 24 real purchases, at least seven calendar days apart, spending remaining available cash in equal *remaining-tranche denominator* increments, possibly after BTC has recovered and original shared market recommendation is HOLD. If original live SELL WATCH appears on a planned buy date, suppress BUY; use one ledger transaction max per 7 days.
3. **52 order candidate** identical, with 52 scheduled purchases. Smaller average order, slower market re-entry, leaves more cash at short as-of horizons.

Each entire SELL strategy is simulated independently with all 3 buyback policies: (a) unchanged live scheduled-and-experimental recurring rollover; (b) live scheduled-only, experimental rollover suppressed; (c/d) unchanged historical original BTC-denominator staged 90% / pre560 20%-holdback exits; (e) buy & hold. **Same hypothetical A$500k entire BTC position purchased at HISTORICAL halving, NOT user's actual 2026 account.** No invented cash, initial SALE at 2025 peak or new outside capital. Same strict prior completed BTC data, USD/AUD date prior, A$3 per fill, illustrative FIFO SMSF accumulation gain taxes charged from each SELL, 7 day ledger gap for BUY and SELL, and hypothetical end liquidation taxes. All instruments are BTC/USD AUD-price closing proxies, NOT actual pre-Nov2025 ASX:IBIT exchange prices.

Two execution contexts: every calendar day BTC close (2017 included Sunday gate) and weekday-only BTC close proxy. In weekday-only **a Sunday-only gate does not activate any planned buyback** because no actual ETF order can fill without a separately tested carry-forward policy; do not silently use a weekend quote as executable IBIT fill. No ASX public holidays, quoted bid/ask, tracking errors, intraday broker orders or exact SMSF pension phase modelled.

Evaluate 2017 / 2021 completed through day1150 and 2025/26 right-censored through archived Oct5 2026. Artificial prefix-preserving stresses for 2017 and 2021: rising BTC 2x/4x between halving+600 and day1150; after day900 another 50%/70% drawdown reaching low at day1060 and ending at 55% of pre-stress BTC price. **All histories reused and candidates selected after looking at original outcomes; NEVER claim out-of-sample improvement or causal effectiveness for unobserved market.**

Metrics required: actually held BTC, BTC-equivalent of unspent cash at terminal (clearly different), unspent cash AUD, terminal hypothetical liquidated aftertax AUD, absolute and relative to unchanged 2.5%-only-below-WMA policy within same historical SELL strategy, actual BUY/SELL count and first market trigger, additional exposure downside and real weekday execution gap.


## Verified results 18 October 2026 — research only

[GitHub Actions run 39121651323: SUCCESS, 26 tests passing](https://github.com/aussiekarl-gif/BTC_Composite/actions/runs/39121651323): 8 new strictly causal 24/52 tranche tests, 8 unchanged self-financing full-cycle parity tests and 10 unchanged live Cycle percent allocation tests. [All exact per-order USD/AUD proxy, FIFO tax/cash, BTC units, day730/1150 observations and 140 scenario-comparison rows (artifact 12134901064)](https://github.com/aussiekarl-gif/BTC_Composite/actions/runs/39121651323/artifacts/12134901064). (140 printed candidate rows; original live control rows also in full `full_ledgers.json`.)

All results are hypothetical 2017/2021 historic BTC-close proxy purchases with AUD500k at each prior halving and the same **historical ORIGINAL-BTC-denominator staged 90%-core SELL policy** for the first table. Finite BUYback means 24/52 at least-seven-day-separated successfully executed purchases from real net after-sale AUD cash after the *first* original strict 200 WEEK MA BUY WATCH; no wallet ever receives outside deposits and the existing shared live BUY signal remains unchanged.

### Historic complete: actual BTC held is substantially different from cash equivalent

| Original90%-staged SELL + buyback | 2017 actual BTC @day1150 | Unspent AUD | 2021 actual BTC @day1150 | Unspent AUD |
|---|---:|---:|---:|---:|
| **CURRENT live 2.5% remaining cash**, only on each fresh below-WMA BUY WATCH | **62.209629 BTC**, 1 BUY | **A$9,606,265** | **60.813748 BTC**, 39 BUYs | **A$1,064,397** |
| **24 executed weekly purchases after first qualifying WMA BUY** | **1,648.496815 BTC**, 24 BUYs | **A$0** | **96.047697 BTC**, 24 BUYs | **A$0** |
| **52 executed weekly purchases after first qualifying WMA BUY** | **922.165059 BTC**, only 36 BUYs observed by scoring terminal | **A$3,031,563** | **90.196017 BTC**, 52 BUYs | **A$0** |

Compared with matching ORIGINAL90%-SELL+existing strict live 2.5%-cash BUYback:
- 2017 24 weekly: **+2,549.906% actually held BTC** (small original BTC denominator because most funds remain cash), +140.738% BTC-equivalent including remaining cash, **+120.783% after-tax terminal AUD account value**. 2017 52 weekly: +1,382.351% actually held BTC, +63.359% BTC-equivalent incl cash, +54.376% aftertax AUD.
- 2021 24 weekly: **+57.937% actually held BTC**, +14.126% BTC-equivalent including cash, **+12.566% aftertax AUD**. 2021 52 weekly: +48.315% actually held BTC, +7.173% BTC equivalent, +6.297% aftertax AUD.
- Very important: completed 2017 historic fresh below-200WMA gate opened only on **Sunday 16 December 2018**. Under the optional weekday-only ASX reference, all 2017 ORIGINAL90 staged SELL+BUYback policies had **0 eligible BUYs**; finite24/52 both stayed inactive, EXACT same cash/BTC and 0% improvement. The research does not pretend Sunday BTC closing prices were 2018 ASX:IBIT executable.
- 2021 weekday-only remained similar because original 200WMA fresh gate happened on Wednesday 15 June 2022: original60.854666 BTC, 24week 96.047697 BTC (+57.831% actually held), 52week90.196017 BTC (+48.215%). Staged original90 24week +12.518% terminal aftertax AUD compared with unchanged 2.5; 52week +6.252%.
- 2025/26 latest archived 5 Oct 2026 is **RIGHT-CENSORED at day898**, with too little time for 24/52 entire plans and unknown future bottom: original daily staged90 1.320200 BTC, 24week 6.127830 BTC (18 fills, cash A$197,954), 52week2.859792 BTC (18 fills, cash A$517,727). Weekday staged90 original4.067386 BTC, 24week5.015733 BTC (17 fills), 52week4.362828 BTC (17 fills). These figures are only intermediate marks and NOT a historical full-cycle victory.

### Risk test: deeper future bear path after the first WMA activation

Original90 staged seller, **weekday-only BTC/AUD price execution proxy**, preserve real historical prices through day900, then force additional 50%/70% decline by day1060, score day1150. Since this future scenario declines after the buyback gate, aggressive 24week redeployment can use much cash too early:

| Artificial cycle prefix/extra future drop | 24week vs existing strict live 2.5% BUYback: **aftertax AUD** | 52week vs existing strict live 2.5% BUYback: **aftertax AUD** |
|---|---:|---:|
| 2017 +50% drop | **−1.014%** | +0.581% |
| 2017 +70% drop | +5.699% | +1.802% |
| 2021 +50% drop | **−29.293%** | **−4.204%** |
| 2021 +70% drop | **−36.960%** | +6.704% |

Crucially, **more actually held BTC does NOT automatically mean higher aftertax AUD or lower risk**. In the synthetic 2021 +70% extra decline, 24week buyer had 94.930141 BTC versus existing live-style BUYback ~106.5 BTC (−10.859% actually-held BTC), despite spending sale proceeds much earlier; it suffered **−36.960%** terminal AUD against the baseline. The slower 52week approach had 160.684066 BTC (+50.885%) and +6.704% terminal AUD in that exact artificial path. Different future BTC paths could easily reverse this result.

### Strong continuing-bull negative control

If price instead rises uninterrupted by 2x/4x AFTER halving+600 and NEVER reopens the strict 200WMA BUY gate, **all three buyback modes are IDENTICAL (zero executed BUYs)** and retain the original SELL opportunity cost relative to buy-and-hold. The finite-plan candidates do not magically buy before market eligibility or manufacture a future cycle bottom. The original sell-risk may be severe even if buyback plan is well-designed.

### Decision and engineering risk

**Do not promote any of these finite 24/52 buyback policies to live Cycle Trading yet.** They were proposed **after observing the same 2017/2021 cycles** and strong gain in actual BTC ownership hinges on the initial below-200WMA gate, including the Sunday 2018 close that was NOT tradable as an ASX ETF. The backtest's 2017 24week +120.783% hypothetical aftertax AUD gain is an in-sample scenario with fill-date and tax assumptions, NOT independent validated alpha.

The robust engineering findings:
1. Current live BUYback 2.5%-of-remaining cash and strict same-day below-WMA rule can leave a large amount of sale cash permanently stranded even after apparent successful SELL timing.
2. Finite buyback after **first causal eligible WMA BUY** can acquire many more actual BTC; but 24week frontloading can catastrophically underperform if bear markets extend (observed artificial −36.96%).
3. 52week slower redeployment meaningfully changes cash reserve/drawdown trade-offs and sometimes outperforms 24week in deep stress, but no universally superior winner and possible stale cash if market appreciates quickly.
4. Weekend-to-first-real-ASX-session carry (#148) is an independent unverified hypothesis; DO NOT couple it automatically to a finite schedule or sell the 2018 hypothetical winner as real IBIT performance. Real ASX holiday calendar and IBIT post-2025 actual bid/ask/ETF price/NAV provenance are required.
5. Track `BTC held`, `BTC equivalent including cash`, `AUD cash available`, `hypothetical liquidation after-tax AUD`, `uncertain tax and future volatility` as **separate indicators** in any proposal. Long-run user goal depends on actual BTC repurchases, not cash re-valued into BTC at the end.

The tested research-only function retains EXACT original LIVE behaviour as default, verified by direct parity test. The full new research path and all 26 test results are preserved; **Streamlit, one daily ntfy, broker orders, Google Sheets, Production V5.8.2, and all current BUY and SELL recommendations remain unchanged**.

**Suggested next work**: avoid further overfitting the 2017/2021 two-cycle sample by searching more independent market periods with real point-in-time data, plus affordable reliable post-listing ASX:IBIT closes/official sessions and measuring actual spread/tax. Only THEN consider a separately approved live change; trial weekly WATCH shadow candidate alongside actual daily recorder rather than notifying the user every day about hypothetical additional trades.

