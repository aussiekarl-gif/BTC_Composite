# Bitcoin selling exactly 500 days after halving — numerical audit

**16 October 2026 · Research only · All historical results in-sample**

[Successful GitHub Actions workflow #38897065331](https://github.com/aussiekarl-gif/BTC_Composite/actions/runs/38897065331) | [Engine](../../engines/research/halving_window_top_audit.py) | [Unit tests](../../tests/test_halving_window_top_audit.py)

## User question

Would selling BTC **500 days after a halving** be more reliable than the
previous day-525–560 staggered sell plan?

Use exact BTC/USD **daily CLOSES**, a hypothetical **one-BTC stake already
owned before the relevant halving**, and retrospective observed macro-peak
daily CLOSES, never a hindsight-picked execution date. All dates and
quantities are known before each sale. User actual BTC/ETF holdings in
2026 are **not** in this backtest.

| Halving | Day 500 | Day 525 | Day 560 |
|---|---|---|---|
| 28 Nov 2012 | 12 Apr 2014 | 7 May 2014 | 11 Jun 2014 |
| 9 Jul 2016 | 21 Nov 2017 | 16 Dec 2017 | 20 Jan 2018 |
| 11 May 2020 | 23 Sep 2021 | 18 Oct 2021 | 22 Nov 2021 |
| 20 Apr 2024 | **2 Sep 2025** | 27 Sep 2025 | 1 Nov 2025 |

**The user's real A$500,000 deployment starts in 2026**. The previous
halving's day 500 has already passed; do NOT suggest an automatic sale
today on the basis of a past trigger.

## Part A — all-BTC single sale on day 500

| Cycle | Macro peak close BTC/USD | Day-500 actual sell close | Error below macro peak | Meets 25% goal? |
|---|---:|---:|---:|---|
| 2013 | $1,132.01 | $423.42 | **62.60%** | No |
| 2017 | $19,187.78 | $8,095.23 | **57.81%** | No |
| 2021 | $67,559.00 | $44,903.50 | **33.53%** | No |
| 2025 | $124,728.00 | $111,238.00 | **10.82%** | Yes |

A **100% sale on day 500** met the desired peak proximity in only
**1 of 4** historical macro cycles, or **1 of 3 modern cycles**.
Single-date timing is fragile and distinctly too early in 2017 and
2021. 2013's peak came at post-halving day **371**, so day 500
was *too late* for that cycle.

### Part B — gradual daily sale controls

BTC-weighted effective average selling-price error (lower is better):

| Cycle | Sell equally days 500–525 | Sell equally days 500–560 | Front-loaded days 525–560 |
|---|---:|---:|---:|
| 2013 | 58.87% | 54.68% | 55.95% |
| 2017 | 35.09% | 28.73% | **19.15%** |
| 2021 | 24.04% | 14.96% | **7.76%** |
| 2025 | 9.17% | 8.89% | **7.42%** |

Earlier long sale windows reduce dependence on one price close,
but also dispose too much before the eventual 2017 peak.

### Part C — practical 6- or 7-order weekly alternatives

**Control:** six front-loaded weekly BTC sales on halving days
**525, 532, 539, 546, 553, 560**, with weights **6:5:4:3:2:1**
of the BTC available for this hypothetical sale.

**Day-500 insurance:** sell **10%, 15%, or 25%** of original BTC at
day 500, then distribute *all remaining BTC* in the same 6:5:4:3:2:1
ratio at those same six later pre-specified dates. No future price
is used for any decision; unit tests enforce time invariance and
BTC fractions summing to exactly 100%.

| Cycle | Six weekly sales, no day-500 tranche | 10% early | 15% early | 25% early |
|---|---:|---:|---:|---:|
| **2013** | 55.88% | 56.55% | 56.88% | 57.56% |
| **2017** | **17.76%** | 21.76% | 23.76% | **27.77% (fail)** |
| **2021** | **7.13%** | 9.77% | 11.09% | 13.73% |
| **2025** | **9.58%** | 9.70% | 9.77% | 9.89% |

All variants **miss the 2013 peak** by more than 25%.
For the modern 2017/2021/2025 cycles:
- No early tranche: **3/3** meet 25%; gross BTC/USD average-price
  errors 17.76% / 7.13% / 9.58%.
- 10% early: **3/3** meet 25%; errors 21.76% / 9.77% / 9.70%.
- 15% early: **3/3** meet 25%; errors 23.76% / 11.09% / 9.77%.
- 25% early: **2/3** meet 25%; 2017 error 27.77%.

All early-sale variants achieved a **WORSE gross average sale price
in every modern cycle** than six weekly sales alone. They
therefore buy potential early crash protection at the cost of
selling some BTC prematurely. None demonstrates superior historical
after-tax total wealth or Bitcoin repurchase.

A$3/order cash brokerage, **not netted from USD/BTC price**:
- Six orders = **A$18** total brokerage for this one-BTC illustration.
- Day-500 sale plus six weekly orders = **A$21**.
Do NOT subtract A$3 as if it were US$3 or as if BTC price were AUD.
ETF fees, spreads, real-world fills, CGT and FX require live position
size, tax parcel cost basis and full AUD conversion at each settlement.

## Main caution

Even the apparent **3/3 modern-cycle pattern** is from a tiny
retrospective selection: the day-525–560 band was proposed after
observing the 2017, 2021 and 2025 peak dates. The 2013 counterexample
and the failure of adjacent wider windows show that this is NOT a
universal market-top forecast. We have no untouched future top.

**Recommendation for Research only:** retain day 500 as a
possible *readiness/optional modest de-risking* milestone, but
reject automatic sell-100%-on-day-500. Do not promote a staged
100% sale rule to Production without prospective evidence. An
optional 10% day-500 sale is a risk-management hypothesis and
not proven to improve wealth; it would be retrospective timing
insurance, not an outcome guaranteed by history.

Next work needs a real-account starting-date-synchronised,
cost- and SMSF-tax-sensitive sale/rebuy model with true
BTC-equivalent holdings, and robust forward top detection.
**Production, the authoritative master and My Portfolio are unchanged.**
