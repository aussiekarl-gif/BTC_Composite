# BTC halving-clock sell windows: extraordinary fit, poor independent validation

**16 October 2026 · Research only · Not Production**

- [Numerical selling-window engine](../../engines/research/halving_window_top_audit.py)
- [Strict-causality / schedule regression tests](../../tests/test_halving_window_top_audit.py)
- [Passing GitHub Actions run #38894648689](https://github.com/aussiekarl-gif/BTC_Composite/actions/runs/38894648689)
- [Seven-indicator top horse-race report](market_top_indicator_horse_race_20261016.md)
- Draft PR #90: https://github.com/aussiekarl-gif/BTC_Composite/pull/90

## Important overfitting warning

The retrospective major BTC/USD closing-price peaks in the three most
recent mature cycles fell **525, 546, and 534 days after halving**:
December 2017, November 2021 and October 2025.

A rule to liquidate a fixed hypothetical **one-BTC** stake from
halving-day **525 to 560 inclusive (36 daily sells)** was derived
AFTER seeing those peak dates. It is fully executable *if we choose
the rule before the next halving*, but the backtest is PURELY
in-sample. It is NOT evidence that the next cycle must obey a
35-day calendar window. The Dec 2013 peak came **371 days** after
its halving and is a clear structural counterexample.

## Gross BTC/USD effective selling-price error

One BTC exists before the halving. Sale plan divides the same
quantity across 36 observed daily BTC/USD closes. No date decisions
use future prices. The true peak is determined retrospectively
as max daily close in the stated cycle scoring windows; no 2013
exception may be hidden.

| Cycle | Peak days from halving | Gross price error 525–560 equal BTC | 525–560 front-loaded BTC | 525–560 dynamic previous-day trend | 500–575 equal BTC |
|---|---:|---:|---:|---:|---:|
| **2013** | 371 | 51.83% | 55.95% | 50.05% | 53.40% |
| **2017** | 525 | 23.34% | **19.15%** | 22.56% | 32.06% |
| **2021** | 546 | 8.22% | **7.76%** | 7.99% | 15.74% |
| **2025** | 534 | 8.77% | **7.42%** | 8.01% | 10.75% |

The **narrow equal, front-loaded and trend-weighted** variants
achieved within 25% *gross average sale price error* for
**3/3 modern cycles but only 3/4 including 2013**.
The broader 500–575 rule only passed **2/3 modern cycles**.

- Equal: sell 1/36 BTC on each prescribed daily close.
- Front-loaded: sell quantities proportional to 36,35,..1,
  deliberately selling more at the beginning of the window.
- Trend-weighted: determine each day's fraction from prior
  completed BTC/USD prices, selling 1.8× remaining/day if
  yesterday was within 2% of the 90-day observed high and above
  trailing 21-day mean, otherwise 0.75×. Sell remaining on final
  date. This is causal but **did not beat simple front-loading**.
- Broader control: equal BTC between halving day 500 and 575.

The front-loaded model generated gross USD/BTC VWAPs:
- **2017 $15,513.05** vs later observed cycle peak close $19,187.78.
- **2021 $62,319.80** vs $67,559.00.
- **2025 $115,474.84** vs $124,728.00.
- **2013 $498.69** vs $1,132.01 (**failure**).

## Reasons the impressive fit isn't yet enough

1. We looked at the dates of the target peaks before specifying
   day 525 and 560. There is no untouched mature top to score.
   Robustness failed when widening the window 25 days on each
   side (2017 missed target). Severe sensitivity to date choice.
2. The old 2013 halving-to-top gap is a direct counterexample. A
   macro cycle can change shape, extend, shorten, be double-topped,
   or disconnect from halving timing altogether. Exactly **three
   modern examples** cannot establish a dependable error rate.
3. One BTC was assumed already owned; the user's actual A$500k
   only starts deploying in 2026. No fund tax-lot holdings,
   transaction costs, FX, minimum parcel size, slippage,
   after-tax gains, dividends/ETF costs, or realistic portfolio
   cash management were modelled.
4. A 36-day total liquidation precludes riding a later break-out.
   Selling 100% in this window is a consequential all-or-nothing
   prediction even though purchases earlier were dynamic.
5. Our definition of major top is the ex-post BTC/USD closing
   max in 2013/2017/2021/2025 scoring windows. In actual trading,
   no one knows the final top has happened. No conditional proof
   of 25% execution-error ceiling on future cycles.
6. The same archived BlockHorizon 2026-exported prices used in
   the onchain study are retrospective. Price-date causality
   is testable; real historic publication vintages of
   onchain components are still unverified.

## Promotion decision

**Do not switch live Production to a fixed day-525–560 sell-all
model.** It is promising and belongs on our research priority list,
especially as a *valuation/maturity readiness* or phased
profit-taking overlay, alongside genuinely independent
price-trend and onchain reversal evidence.

Prefer a *risk-limited partial distribution test* rather than an
untested all-BTC sell commitment. Next simulation should use
actual AUD BTC-equivalent position sizes, A$3 orders, realistic
SMSF lot taxation and fee sensitivity plus a pre-registered
adaptive re-entry condition.

Given full 2026 historical inspection, the cleanest proof will be
prospective forward research on future BTC regimes, not another
100 parameter choices fitted to these same three tops.
Authoritative data master, user portfolio and Production unchanged.
