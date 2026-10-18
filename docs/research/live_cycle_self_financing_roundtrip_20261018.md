# Research — exact live SELL plus 200WMA dynamic BUYBACK full-cycle parity

Date 18 October 2026. New, research-only full-cycle audit: **NO** changes to Production V5.8.2, Research V5.9, Cycle Trading Streamlit allocations, ntfy daily alerts, any broker order or real portfolio.

## Motivation

Merged #150 proved the original historically tested day500 staged SELL engine and LIVE Streamlit/ntfy SELL model are different in original-BTC vs remaining-BTC denominators, price regime gates and endlessly repeating 5%-remaining late-rollover SELLs. SELL-only AUD endpoints cannot establish whether proceeds buy extra BTC later. This resolves that gap by **funding all later BUYs solely from realised SALE proceeds net of illustrative tax**, applying the SAME exact original 2.5%-of-remaining-AUD-cash shared market-level BUY WATCH policy in *every* account, and demanding strict completed prior BTC close below prior 200 WEEK moving average.

## Matched conditions

- Each hypothetical seller begins with AUD500k bought in BTC on the historical BTC halving date, **NOT the user's actual 2026 BTC or post-2025 ASX:IBIT holdings**. Same initial BTC amount for all five policies, no external cash after this entry.
- Five SELL policies: (a) live remaining-holdings scheduled gated + experimental repeated 5%-remaining rollover; (b) live scheduled-only diagnostic; (c) historic staged 90%-core ORIGINAL BTC; (d) historic staged original-BTC 20%-pre560 holdback and later-confirmed breakdown; (e) never SELL / buy-and-hold.
- Unlike #150's SELL-only study, at each date T SELLs are followed by possible BUYs if *and only if* actual shared `calculate_allocation_signal` says BUY WATCH from PREVIOUS BTC close below exact 200 weekly WMA and account has sufficiently large sale cash balance. Spend 2.5% of then-remaining AUD CASH, no special boosted early or recovery sizing, never backdate trades, never buy if no realised cash.
- First earlier planned staged SELL has priority over same-date shared BUY WATCH in the historical seller (explicit simulation choice); real shared market BUY overrides current shared SELL. 7 elapsed calendar days after last ACTUALLY EXECUTED BUY or SELL per account; no repeated signal on same day; no leverage or negative cash.
- Same dated BTC/USD daily close reference and strictly BEFORE-day USD/AUD FX, A$3 simulated brokerage, illustrative immediate SMSF FIFO acquisition-lot tax accrual on each executed SELL. Same hypothetical after-tax liquidation and cash-in-BTC-equivalents at evaluation horizon. Pension-phase and Australian SMSF fiscal-year tax nuances not verified.
- Two execution modes: BTC/AUD daily close proxy including weekends, and optimistic Monday–Friday close proxy excluding weekends but **NOT actual ASX holidays, intraday quotes, spreads, ETF NAV premiums, brokerage matching, whole ETF units or tracking costs**. ASX:IBIT only commenced listing 14 Nov 2025: 2017/2021 were not tradable through this ETF.
- 2017 and 2021 complete observed halving+1150; 2024 halving 2025/26 model cutoff archived 5 Oct 2026 right-censored at halving+898. The user did not have actual ownership on historic halving or day500.

## Independent counterfactual stress

Freeze last real daily close historical prefix through *halving+600*, then generate a strictly increasing hypothetical BTC path ending at 2x or 4x the prefix-date price on day1150. Such models punish early sale and often make buyback unattainable — essential to reject fragile SELL rules. Separately after a historical prefix through day900, simulate additional 50% or 70% BTC declines to day1060 with terminal price at 55% of day900 BTC level at day1150. These 8 scenarios (two completed cycles × two higher rally levels × two deeper declines) are **chosen stress scenarios, NOT market probability estimates or out-of-sample validation**. They are alternative futures from already-inspected historical price prefixes, not changed earlier prices.

## Essential falsification checks

New tests must establish no purchase before any realised SELL, all five accounts with equal initial BTC and separately funded cash, no external investment, EXACT shared market 200WMA gate and 2.5%-remaining sizing, one 7-day executed-trade cooldown per account, no current/next price used to create prior WATCH, stage fractions bounded by initial original BTC, prefix invariance to later prices, no weekend fills in weekday-only mode, stale FX and missing BTC observations fail closed, and no actual IBIT pricing representations. Original current SELL code and its percent rule are imported unchanged.

## Decision gate

Before suggesting implementation, inspect final BTC-equivalent INCLUDING retained cash, actually held BTC, and hypothetical liquidated after-tax AUD vs identical buy-and-hold. NEVER claim the historical staged seller's SELL-only gain as actual achieved BTC units. Check whether the **original live 2.5% residual cash buys back enough coins** before market recovers, and whether the experimental repeated SELL materially harms a sustained bull; evaluate controlled diversification/reserve, not merely past high-in-hindsight. This still does not reproduce actual IBIT fills or user's personal tax lots.


## Verified CI findings — 18 Oct 2026

[**GitHub Actions run 39120958535 SUCCESS**](https://github.com/aussiekarl-gif/BTC_Composite/actions/runs/39120958535): 8 new self-financing/prefix/FX/weekday tests, 8 existing shared Cycle SELL-parity tests, and 10 live market-percent tests passed (**26 total**). [Full exact dated portfolio cash, lot, SELLS and BUYBACK records with real historical and stress CSVs (artifact 12134585580)](https://github.com/aussiekarl-gif/BTC_Composite/actions/runs/39120958535/artifacts/12134585580).

The matched **CURRENT live BUY** is 2.5% of **then-remaining actual realised after-tax cash only if previous BTC/USD close below strict 200WMA**, with >=7 calendar days between actual fills. No forced 24-week drawdown recovery deployment, no front-run of BUY signal. This is a DIFFERENT POLICY from prior backtests where 24 weekly purchases forcibly redeployed ALL sell proceeds. Year-end liquidation is a scoring thought experiment only: cash shown below is **unspent original fund cash**, not BTC already repurchased.

### Completed historical day1150 — BTC daily close reference proxy INCLUDING WEEKENDS

All after-tax % = final hypothetical liquidated AUD total account vs equal-start historical BTC buy-and-hold, not annual rates, not true ETF broker fills or current user's 2026 assets.

| Historical cycle | Seller with common live BUYback | Actually held BTC after rebuy | Unspent AUD cash | BUYback fills | SELL fills | After-tax AUD vs hold | Marked BTC equivalent incl cash vs hold |
|---|---|---:|---:|---:|---:|---:|---:|
| 2017 | Live incl repeated late rollover | 126.012976 | 6,226,769 | 1 | 31 | −1.532% | −8.704% |
| 2017 | Live conditional scheduled-only | 437.122091 | 3,187,411 | 1 | 2 | +14.643% | +10.973% |
| 2017 | Historical staged 90% original BTC | **62.209629** | **9,606,265** | **1** | 10 | +29.116% | +18.055% |
| 2017 | Historical staged 20%-pre560 holdback | 54.976951 | 9,558,943 | 1 | 9 | +27.286% | +16.279% |
| 2017 | Buy and hold | 580.042354 | 0 | 0 | 0 | 0% | 0% |
| 2021 | Live incl repeated late rollover | 49.854083 | 723,315 | 39 | 22 | +78.235% | +72.620% |
| 2021 | Live conditional scheduled-only | 47.770013 | 429,363 | 39 | 3 | +53.545% | +50.211% |
| 2021 | Historical staged 90% original BTC | **60.813748** | **1,064,397** | **39** | 9 | **+129.320%** | +121.057% |
| 2021 | Historical staged 20%-pre560 holdback | 59.202819 | 1,044,046 | 39 | 8 | +123.759% | +115.653% |
| 2021 | Buy and hold | 38.071425 | 0 | 0 | 0 | 0% | 0% |

**Major correctness lesson:** BTC-equivalent *including retained cash* can be higher than hold while ACTUALLY OWNED BTC is dramatically lower. The research goal "maximise BTC quantity" requires separate measures of actual BTC, cash, after-tax AUD and opportunity cost. In 2017 the staged exit ends with 62 BTC actually held vs 580 BTC buy-hold, although its terminal AUD is +29% higher. **Do not represent the unused A$9.61m as BTC already bought**. Original 2.5% live BUY catches just ONE BTC/USD Sunday below200WMA opportunity in 2017, and never spends most of the exit cash.

### Weekday-only BTC/AUD reference sensitivity (still NOT actual ASX:IBIT historical prices)

| Cycle | Strategy | Weekday-only actual BUY fills | Weekday-only after-tax AUD vs hold | Weekday-only actual BTC held |
|---|---|---:|---:|---:|
| 2017 | Live incl experimental repeated rollover | **0** | **−25.208%** | 124.499574 |
| 2017 | Live scheduled-only | 0 | −1.519% | 551.040236 |
| 2017 | Historical staged original90 | 0 | −5.842% | 458.647776 |
| 2017 | Buy and hold | 0 | 0% | 580.042354 |
| 2021 | Live incl repeated rollover | 39 | +78.343% | 49.892676 |
| 2021 | Live scheduled-only | 39 | +53.584% | 47.786521 |
| 2021 | Historical staged original90 | 39 | +129.419% | 60.854666 |
| 2021 | Buy and hold | 0 | 0% | 38.071425 |
| 2025/26 incomplete | Live incl late rollover | 6 | +7.104%* | 3.379799 |
| 2025/26 incomplete | Live scheduled-only | 0 | 0%* | 4.930747 |
| 2025/26 incomplete | Historical staged original90 | 6 | +6.275%* | 4.067386 |
| 2025/26 incomplete | Buy and hold | 0 | 0%* | 4.930747 |

*Only through archived Oct5 2026, 898 days after 2024 halving. NOT final cycle; the user's 2026 portfolio has other actual acquisition dates and amounts.* 
Strict weekday-only execution can MISS both weekend BUY and weekend SELL stages because no actual ASX exchange holiday/calendar or queued-order logic is implemented; differences from everyday Bitcoin fills are not solely a 'market prediction' effect.

### Counterfactual (all weekday-only proxies, same single SELL+BUYBACK policy)

Freeze actual historical price through halving+600; generate **continuing 2x and 4x rallies** until halving+1150. No 200WMA BUY follows any sale, so all strategies with significant original-BTC SELL incur unrealised opportunity loss vs HOLD. Actual ACCOUNT aftertax delta:

- 2017 live incl repeated late rollover: −16.714% for 2x rally, **−21.595% for 4x**; historical staged 90%: −13.721% and −17.319%; scheduled-only: −3.337% / −4.167%.
- 2021 live incl late rollover: −24.774% for 2x, **−39.095% for 4x**; historical staged 90%: **−41.013% for 2x, −69.760% for 4x**; scheduled-only: −15.160% / −26.756%.

Conversely, synthetic additional BTC drawdowns after historical day900 to day1060 (50/70% lower followed by terminal at 55% of pre-shock):
- 2017 live incl late rollover: +163.767% / +197.934% entire AUD vs HOLD; staged original90: +49.850% / +59.927%, current strict scheduled-only +11.328% / +13.652%.
- 2021 live incl late rollover: +165.924% / +197.947%; staged original90: +257.513% / +304.626%; scheduled-only +106.651% / +125.653%.

**These are deliberately engineered futures with zero probability claim, not genuine validation.** They establish that more SELLs hedge deep drawdowns while also exposing investor to potentially enormous opportunity cost if Bitcoin continues rallying and BUY-WATCH never reopens. Pure past-cycle fitted staged exits DO NOT dominate.

### Immediate research conclusion

1. **Keep current live BUY+SELL unchanged** until real market-session, personal portfolio and tax-lot guardrails are validated. The 2017 sole below-200WMA BUY happened on a weekend, and a real ETF cannot transact in the model's historical simulated close; research PR #148's weekend->first-session order carries remain a separate unproven hypothesis.
2. **The PRIMARY current live BUYBACK bottleneck is documented**: 2.5%-of-remaining-cash with strict no-above-200WMA rule often leaves most sale proceeds unspent. In 2017 the full staged exit is cash-rich but BTC-poor at terminal. Compare an explicitly separately authorised and prospectively evaluable **finite recovery-phase buyback plan** (e.g. fixed 24 or 52 week redeployment AFTER the first below-WMA signal) against the exact existing BUY rule, with no earlier buy or hindsight low assumptions. This must include continued-bull opportunity cost and worst-case fresh drawdown, not merely replay past bottoms.
3. Include real ASX calendar/IBIT bid-ask and cash/yield/ETF fees for decision-quality after-tax AUD. The SELL model original-vs-current denomination gap cannot be hidden by optimistic cash-in-BTC-equivalent marking; show BTC ACTUALLY HELD as a separate top-line KPI.
4. Research source data through Oct5 2026 lacks verified contemporaneous MVRV vintages; the 2025/26 outcome right-censored. All conclusions should disclose small number of complete historical cycles, potential regime overfit and synthetic counterfactual fragility.

