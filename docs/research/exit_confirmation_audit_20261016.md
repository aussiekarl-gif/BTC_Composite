# BTC cycle trading: risk-arm and price-confirmed exits (2026-10-16)

**Status: RESEARCH ONLY. DO NOT DEPLOY OR PROMOTE.**

- Independent read-only historical run: https://github.com/aussiekarl-gif/BTC_Composite/actions/runs/38877452561
- Parent draft research PR: https://github.com/aussiekarl-gif/BTC_Composite/pull/90
- Reproducible engine: `engines/research/exit_confirmation_audit.py`
- Regressions: `tests/test_exit_confirmation_audit.py`
- No modification to Production V5.8.2, authoritative audit data, portfolio data, or live signal policy.

## Hypothesis

A static high-risk threshold was selling far too early in prolonged bull markets, including
2017 and late 2020. A candidate correction is to *arm* a potential top at BTC risk >= 0.60
and sell only after a decline of 25% or 35% from the observed high since arming AND
weekly AUD price below its trailing 20-week moving average.

Buy logic stays risk <= 0.35. Trades execute from the signal on the **following week's**
observation. All buying/selling is equally staged over 16 observations, and all sale
proceeds remain in the same account for subsequent buys. The confirmation is an
**AUD-denominated 20-week average, NOT the USD 200-week average**.

## Accounting, data and comparators

- Paired validated 557 weekly AUD BTC prices and archived risk scores from 2016-01-04
  through 2026-08-31 (the master contains many earlier incomplete price/risk pairs).
- Initial AUD 500,000; first executable week matched to buy-and-hold; terminal
  mark-to-market equity equals BTC * ending AUD price plus AUD cash.
- All-in cost per trade side 0.3%; no tax, cash interest, or market impact.
- Stored historical `risk_score` point-in-time integrity NOT independently established.
  One-week execution lag cannot cure retrospective feature revision.
- Full-history and 2016–2021 / 2022–2026 restart cohorts are **in-sample diagnostics**.
  The latter cohorts are NOT an untouched holdout, and the same strategy was examined
  after earlier work on these periods.

## Historical results (pre-tax, in-sample)

| Strategy | 2016–2026 end AUD | vs matched hold | Worst account drawdown |
| :--- | ---: | ---: | ---: |
| Buy and hold | 84,619,254 | 1.00× | n/a |
| Prior 0.35 / 0.60, 16-week buy/sell | 200,173,772 | 2.37× | -42.58% |
| Confirm 25% decline + 20WMA, 16-week buy/sell | 393,651,611 | 4.65× | -58.47% |
| Confirm 35% decline + 20WMA, 16-week buy/sell | 352,113,013 | 4.16× | -58.47% |

25% confirmation ended with 3,628.84 BTC and zero AUD cash; the earlier strategy
ended with 1,845.28 BTC and zero AUD cash. Higher historical equity came with
*more* drawdown, not less.

### Separate cohort restart checks (relative to matched hold)

| Strategy | 2016–2021 | 2022–Aug 2026 |
| :--- | ---: | ---: |
| Prior 16-week | 0.68× | 2.87× |
| 25% confirmation | 1.83× | 2.15× |
| 35% confirmation | 1.83× | 1.89× |

Confirmation helps the early cohort but underperforms the prior model in the
later cohort. It must not be promoted based on the full-period 4.65× result.

### Historical example starts of 25% confirmed sell plans

2018-02-12; 2019-10-07; 2021-05-31; 2025-12-01.
The May 2021 exit still risks abandoning the late-2021 rebound: confirmation
does not guarantee catching a true final cycle peak.

## Predeclared higher-cost and signal-delay sensitivity

Vary total risk-signal-to-execution lag (1, 3, 5 weeks) and per-side cost
(0.3%, 1.0%), with the SAME starting capital and hold benchmark. The 16-week
execution plan follows the delayed signal.

| Full-history candidate | 1-week / 0.3% | 3-week / 0.3% | 5-week / 0.3% | 5-week / 1.0% |
| :--- | ---: | ---: | ---: | ---: |
| Prior 16-week vs hold | 2.37× | 2.75× | 2.84× | 2.61× |
| 25% confirmed vs hold | 4.65× | 4.68× | 4.54× | 4.29× |

For 2022–2026, the 25% confirmation variant spans **2.10×–2.16×** vs hold
under the above six stress combinations; the prior model spans **2.54×–2.87×**.
An apparent full-history benefit does not imply every regime benefits.

## Required checks before any Production promotion

1. Reconstruct the stored Power Law risk and all signal inputs from strict
   point-in-time observations; audit data availability and revisions.
2. Pre-register a small parameter set on history, then test on unexamined
   chronological data. Given repeated exploration of 2016–2026, genuine
   forward paper-trading is required for unambiguous out-of-sample evidence.
3. Compare against cash-recycled simple 200WMA USD rules and matched buy-and-hold,
   all with the same fees and execution constraints.
4. Apply Australian AUD FX execution, appropriate Australian tax / SMSF
   accumulation or pension-phase treatment, plus worst-case fills and missed
   reentry. Do not assume gross gains are realised tax-free.
5. Analyse drawdowns, share of years underperforming hold, balance liquidity,
   missed-cycle probability, and real-world capacity.

**Conclusion:** The original simulator's fixed-initial-capital buys were
inadequate for recycling realised proceeds. Continuous capital recycling plus
price-confirmed sells can materially outperform buy-and-hold *in this
retrospective dataset*, but 4.65× is neither an out-of-sample result nor a
verified strategy advantage under future market conditions.
