# A$500,000 fresh-capital BTC deployment: actual 2026 start cohorts

**16 October 2026 | research only | no live-portfolio transactions read or modified**

Validated by [Research Real 2026 A$500k DCA Start — GitHub Actions #38887205843](https://github.com/aussiekarl-gif/BTC_Composite/actions/runs/38887205843).

- Implementation: [real_2026_deployment_audit.py](../../engines/research/real_2026_deployment_audit.py)
- Tests: [test_real_2026_deployment_audit.py](../../tests/test_real_2026_deployment_audit.py)
- Adaptation: [adaptive_dca_execution.py](../../engines/research/adaptive_dca_execution.py) now accepts `deployment_start` and uses prestart observations as **indicator warm-up only**, not cash/BTC trades.
- Data source: 557 complete weekly BTC/AUD price and archived risk-score pairs, Jan 2016 – **31 August 2026**. No data available in this research master for Sep–Oct 2026; no extrapolation to 16 October.

## Real-user capital constraint

The live account has **A$500,000 available beginning in 2026**. No user money is assumed invested in 2016. The actual portfolio purchases reside in the separately persisted My Portfolio tab (including Australian ASX:IBIT and direct BTC), **not** in this numerical research input. These two hypothetical start dates bracket 2026 starting regimes; **2026-06-19 is an illustrative deployment date, not a claim that the full A$500k was available or invested on that exact date**.

Same money in each self-financing account; A$3 per order; FIFO simplified SMSF CGT as applicable to realised sales, with immediate tax escrow; terminal hypothetical all-BTC sale includes applicable tax. No ETF spreads, tracking, annual fund expenses, retirement pension exemptions, cash interest or actual execution impact. All 2026 cohort variants have **zero sale orders** through 31 August 2026, so realised CGT = A$0 by the data cutoff.

## Jan 2026 start — first executable weekly close 5 Jan, 35 observed weekly closes

| Policy | BTC held | AUD cash | 31-Aug-2026 marked AUD value | After hypothetical terminal liquidation CGT | Actual filled order count |
|---|---:|---:|---:|---:|---:|
| Immediate 100% buy | 3.644970 | $0 | $395,401 | $395,398 | 1 |
| **12-observation equal-size DCA baseline** | 4.627366 | $0 | $501,970 | $501,672 | 12 |
| Cash-only baseline | 0 | $500,000 | $500,000 | $500,000 | 0 |
| Existing adaptive DCA | 4.204715 | $330 | $456,452 | $456,449 | 29 |
| **Trend/reserve challenger** | **4.529463** | $11,554 | **$502,904** | **$502,465** | 29 |

The three adaptive exit confirmations of 10%, 15%, 25% are IDENTICAL to 31 Aug 2026 because there are **zero sells**. Do not attribute current cohort performance to superior selling confirmation.

## June 2026 start — first executable weekly close 22 Jun, 11 observed weekly closes

| Policy | BTC held | AUD cash | 31-Aug-2026 marked AUD value | After hypothetical terminal liquidation CGT | Filled order count |
|---|---:|---:|---:|---:|---:|
| **Immediate 100% buy** | **5.541386** | $0 | **$601,122** | **$585,951** | 1 |
| 12-week equal DCA | 4.905010 | $41,667 | $573,755 | $562,689 | 11 |
| Cash-only | 0 | $500,000 | $500,000 | $500,000 | 0 |
| Existing adaptive DCA | 5.167246 | $31,384 | $591,919 | $578,129 | 11 |
| Trend/reserve challenger | 4.364896 | $99,923 | $573,421 | $562,405 | 11 |

Only 11 observations occurred before the source cutoff. The 12-week baseline therefore retained its last A$41,667 planned slice, **not forcibly invested at the endpoint**.

## Interpret, do not optimise

1. The newer challenger wins among adaptive variants for Jan-start, but **loses substantially to immediate buy for June-start**. No one sizing policy dominates. Further optimisation against this known sample would overfit.
2. Very short 2026 exposure means this does **not** validate selling accuracy or complete full-cycle buy–sell behaviour. It is invalid to assert a 25% **final cycle bottom** error when the cycle is ongoing. User-reported observed low **US$57,717 on 30 June 2026** is already tracked in the separate My Portfolio purchasing-accuracy field, with proper AUD/USD conversion and actual trades.
3. The master lacks Sep–Oct observations in this test; to measure **today's account**, rely on current My Portfolio transaction records and live BTC prices instead of August-only research figures.
4. Stored historical `risk_score` provenance remains unverified. Historic signal inputs must be checked for real availability before Production can adopt the challenger.
5. The number of long-run cycles is tiny, and this is a limited **in-sample, model-only** forward-start comparison. Tests only establish code invariants, not trading effectiveness.
6. **Do not promote** challenger to Production solely because it beats Jan-start hold. Remain in Research. Keep existing Streamlit Production, portfolio storage and authoritative master unchanged.

## Next

- Evaluate anchored **actual current portfolio** performance once user authorises a direct Google Sheets read; never substitute sample starter rows or Jan/June model accounts.
- Verify earliest point-in-time historical composite risk availability; continue prospective tracking.
- Compare realistic buy-weight rules after the 2026 June low and examine whether the portfolio's 25% average-buy target is met, with actual saved IBIT/Direct BTC entry prices and A$3 brokerage.
- When enough observations exist, check causal 2026 partial-cycle buy performance; postpone selling-score claims until full sell-and-rebuy legs exist.
