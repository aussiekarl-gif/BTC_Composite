# BTC 200WMA BUY guard: 30-day realised volatility and 50DMA downtrend (18 October 2026)

**Research-only, predeclared test — no new trade or alert. Do not change Production V5.8.2, Research V5.9, Cycle Streamlit, ntfy, portfolio Google Sheets or actual holdings.**

## Why this is different from earlier unsuccessful models

The previous 10% first-buy frontload and 1%-per-week pre-WMA starter both introduced extra exposure before a confirmed low, and the 50%-reserve until 0.85×200WMA withheld substantial cash until a new *price level*. This test keeps **the exact original first 200WMA gate and weekly eligibility**, but uses real-time volatility and an already familiar falling 50-day price trend to reduce only those weekly purchases associated with unusually violent declines. It is not claimed to identify an exact eventual low.

## Frozen rule

- Initial account: hypothetical **A$400,000 fresh cash** at same history-available halving-relative start day +650 / +750 / +850 / +900. **No earlier BTC lots, fictitious 2025 BTC sales, proceeds or historical personal cash**.
- First eligible signal: prior completed BTC/USD daily close T−1 **strictly below** strictly previous **200 spaced weekly closes**, with gate only eligible after the cash-start. Identical independent original 200WMA engine and dates.
- For each original 7-day BUY review after gate, determine the original fixed-budget BUY percentage **2.5%, 15%, 4.5% or 1% of original AUD cash** from the unchanged recovery policy.
- Compute with no T information: **30 preceding daily BTC log returns**, annualised sample standard deviation ×sqrt(365). **High volatility** if >=80% annualised. Concurrent **falling trend** if T−1 BTC close is BELOW preceding 50-day SMA AND preceding 50-day SMA is below its value exactly 14 days earlier. All 64 prior daily closes required; fail closed otherwise.
- If both high vol AND declining trend hold, multiply the weekly original-budget purchase by **0.5**; if not, use **100% original weekly amount**. Never backfill skipped fractions; gross purchases cannot exceed actual available cash. The next-day execution close is used only for audit fills.
- Compare to original unchanged 200WMA adaptive weekly BUY, currently simplified daily remaining-cash below-200WMA BUY, ordinary fixed 52-week DCA and first-day lump sum. Identical initial cash, FX strictly before the simulated execution close, AUD 3 brokerage and simplified immediate FIFO SMSF CGT upon hypothetical final liquidation.
- Historical 2017/2021 day1150 complete, 2025/26 **right-censored at 5 Oct 2026**. All have been studied; no untouched validation sample.
- Deep-bottom stress (not forecast probabilities): preserve historic prior cash-start and price path through halving day960 for 2017, day900 for 2021; impose artificial 50/70% further BTC declines to day1060 and day1150 terminal at 55%/105% of last original shock-close. Must report number of actually-guarded buys, BTC units, remaining cash, terminal post-liquidation-tax AUD, drawdown and exact first-gate parity.
- Unit tests: signal uses only T−1 and earlier (future repaint invariant), volatility trend actually activates and halves a purchase on known synthetic price path, original independent wallet parity, unchanged original signal and weekly dates, missing daily price and FX fail closed, no-cross no trade.

## Decision before seeing results

Do **not** promote just because a few historical starts improve; 2017 immediate recovery can punish protective sizing and 2021 delayed bottom can reward caution, but two completed cohorts cannot establish a stable future threshold. If volatile downtrends historically improve entry only at the cost of substantial missed post-low accumulation, the experiment should be rejected. Also this rule **cannot solve no-new-200WMA-crossing cash drag**; that is a separate structural policy question.

Real IBIT on ASX cannot be filled at BTC USD daily close on weekends/holidays, tax rates and FX can differ, and this has no independent future holdout.


## Actual numerical verdict — REJECT for live trading (18 Oct 2026)

**[GitHub Actions run 39106936104](https://github.com/aussiekarl-gif/BTC_Composite/actions/runs/39106936104): SUCCESS. 24 tests passed (8 new frozen guard tests, 8 independent fresh-cash original model tests, 8 shared-policy tests).** Original 2.5/15/4.5/1%-of-fixed-original-cash recovery simulation matched the independent existing wallet in every test cohort, including the exact initial prior-200WMA trigger date, BTC quantity, remaining cash, fees and illustrative AUD after-tax liquidation value. [Archived original/guarded orders, full JSON and CSV historical/stress comparisons](https://github.com/aussiekarl-gif/BTC_Composite/actions/runs/39106936104/artifacts/12128693401).

### Dated historical observation (already inspected / no untouched holdout)

All outcomes are percentage **RELATIVE CHANGE IN FINAL HYPOTHETICAL AFTER-TAX AUD**, guarded/original-1, not annual returns or realised gains. Starts with AUD 400k entirely fresh cash and no 2025 sale proceeds.

| BTC cycle | Fresh-cash start day after halving | Guarded weekly purchases | Relative final AUD | BTC held original → guard | Final guarded cash AUD |
|---|---:|---:|---:|---|---:|
| 2017 complete | 650/750/850 | 5 | **−0.683%** | 75.34735010 → 74.80130900 | 0 |
| 2017 complete | 900 | 0: no fresh 200WMA gate | 0.000% | 0 → 0 | 400,000 |
| 2021 complete | 650/750 | 9 | **−2.137%** | 13.51431835 → 13.20196458 | 0 |
| 2021 complete | 850 | 4 | **−2.234%** | 12.42306296 → 12.11096987 | 0 |
| 2021 complete | 900 | 4 | **−2.456%** | 11.79962708 → 11.47173976 | 0 |
| 2025/26 **RIGHT-CENSORED** | 650/750 | 0 | 0.000%* | 4.03240947 → same | 0 |
| 2025/26 **RIGHT-CENSORED** | 850 | 0: no fresh gate | 0.000%* | 0 → 0 | 400,000 |

*Incomplete observation stops 5 Oct 2026; later future drawdown and low are not known.* The guard **cannot improve no-cross opportunity cost**.

### Adversarial deeper-bottom prices — counterfactual only

Keep actual historical price prefix to shock day960 (2017-based starts +750) or day900 (2021-based starts +650). Thereafter simulate 50%/70% declines to day1060 and recovery to 55%/105% of pre-shock USD BTC price at day1150. **NOT actual history, forecasts, or independent probability samples.**

| Synthetic observed prefix | Four forced-shock outcomes, guard vs original after-tax AUD | Worst / best |
|---|---|---|
| 2017-based, cash start +750 | +6.624%, +1.833%, +7.053%, +2.516% | +1.833% / +7.053% |
| 2021-based, cash start +650 | +3.366%, +2.891%, +6.430%, +5.581% | +2.891% / +6.430% |

**All 8** synthetic guard paths increased hypothetical final after-tax AUD versus original, and guarded genuine earlier weekly buys (5 affected purchases per synthetic path). That is protective cash deployment sensitivity **only**. **All non-vacuous completed historical starts produced lower BTC quantities and after-tax terminal value** when the safeguard was actually activated; returns were −0.683% to −2.456%.

### Interpretation and repository decision

- **REJECT as a new default or live 2026 trading rule.** The volatility condition improves deliberate extended selloff counterfactuals but reduces original effectiveness in the two completed observed bear-market recoveries. Just looking at 30d volatility and the declining 50DMA does NOT establish when the actual BTC bear-market low has arrived.
- Do not cherry-pick the profitable shock scenarios or retrospectively select a new volatility threshold. Original policy remains benchmark; no purchased IBIT units, recorded cash, tax escrow or actual trade were affected.
- As future research, **freeze indicators and track their forward alerts/outcomes** over incoming completed data, including no-trigger markets, rather than repeatedly fitting another threshold to only two completed modern cycles. Live execution parity, IBIT ASX market hours/spread and individual SMSF tax lot reconciliation remain separate necessities.
- Document this **negative observed / positive stress trade-off** as a research-only rejected PR, close draft without merging its unused new trading rule. All production, Streamlit, daily ntfy and user Google Sheets data unchanged.
