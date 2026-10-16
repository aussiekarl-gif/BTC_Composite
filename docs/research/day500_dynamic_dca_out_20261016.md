# Dynamic Bitcoin DCA-out starting on halving day 500

**16 October 2026 · Research only · NEVER trade user assets automatically**

- [Numerical implementation](../../engines/research/day500_dynamic_dca_out.py)
- [Causal, cash/BTC conservation and stress regression tests](../../tests/test_day500_dynamic_dca_out.py)
- [Latest successful GitHub Actions: historical plus synthetic stress #38899499374](https://github.com/aussiekarl-gif/BTC_Composite/actions/runs/38899499374)
- [Earlier full-dynamic negative baseline #38898138127](https://github.com/aussiekarl-gif/BTC_Composite/actions/runs/38898138127)
- [Exact day500 sale comparison](day500_halving_sell_20261016.md)
- [Draft research PR #90](https://github.com/aussiekarl-gif/BTC_Composite/pull/90)

## User's proposition and critical timeline

Start selling Bitcoin **500 days after halving**, then DCA OUT
**dynamically**. Do not assume a single top date or a fixed deadline to
sell 100%. Optimize eventual after-tax money and BTC repurchases rather
than the visually best historical peak.

The prior **20 April 2024 halving** had day 500 on **2 September 2025**,
**before this user's actual A$500,000 deployment started in 2026**.
No implementation of this rule will liquidate the actual 2026
portfolio in retrospect. The research simulates ONE BTC ALREADY
OWNED before day500, a purely hypothetical unit stake.

All 2013/2017/2021/2025 numerical experiments use historical UTC
daily BTC/USD closes from exported BlockHorizon provider price history.
No original archived composite `risk_score` or potentially revised
on-chain indicators are traded in this model. Every daily risk
condition is computed exclusively from observations through the
previous day (90-day high, 50-day SMA and 14-day SMA slope), so the
algorithm is **computationally causal**. Parameters were proposed
AFTER reviewing known historical tops; the historical record is
**in-sample, not an honest untouched holdout**.

## First attempt: a slow general weekly DCA-out FAILS

Start with 5% of original BTC sold on day500. Each subsequent weekly
sale uses previous completed price behavior:
- Near recent observed highs: greater sale fraction.
- Neutral market: slower sale fraction.
- Confirmed 15% decline from trailing 90-day high and below
  a declining 50-day average: defensive sale acceleration.

Cautious, balanced and faster weekly dynamic schedules each
sold 100% of their simulated BTC by day730.

| Gross BTC/USD average sale price error vs later macro top | 2013 | 2017 | 2021 | 2025 |
|---|---:|---:|---:|---:|
| Fully fixed weekly BTC sale days 525–560 | 55.88% | **17.76%** | **7.13%** | **9.58%** |
| Day500 slow cautious dynamic | 57.45% | 49.44% | 30.71% | 28.76% |
| Day500 general balanced dynamic | 54.96% | 43.56% | 24.58% | 22.18% |
| Day500 faster dynamic | 54.14% | 40.06% | 19.75% | 19.36% |

**Conclusion:** slow flexible sales extending deep into a bear market
lose too much of the eventual peak. Doing more price-based sizing
is not automatically profitable.

## Second attempt: maturity-heavy Dynamic DCA-out

Predefined stage:
1. Small **5% BTC sale on day500**.
2. Bigger maturity tranches on halving days **525, 532, 539, 546, 553, 560**,
   front-loaded ratio **6:5:4:3:2:1** of a candidate 80% or 90% *original BTC*
   core sale budget, dynamically multiplied by prior-day observed high
   (1.20×), neutral market (0.75×), or independently confirmed
   deteriorating regime (1.30×).
3. If BTC remains after day560, continue weekly adaptive DCA-out.
   There is NO forced full liquidation on day730: it is only the
   observation/evaluation endpoint.
4. Third risk-management candidate: use a 90% maturity *desired*
   allocation, but **cap actual total sales to 80% through day560**.
   Release the remaining 20% BTC **only after** a confirmed
   trend breakdown. This is genuinely flexible and can retain coins
   if the BTC bull market extends.

The candidate share parameters are not retroactively changed by
individual prices. Real sales always use lagged prices; simulated
fills use that day's archived USD close.

### Validated gross peak-proximity price error

Lower is better. A success also requires at least 75% of initial BTC
actually sold, guarding against claiming victory by selling only one
perfectly timed small tranche.

| Scheme | 2013 | 2017 | 2021 | 2025 | Modern cycle <=25% success |
|---|---:|---:|---:|---:|---:|
| Six preplanned weekly sales from day525 | 55.88% | **17.76%** | **7.13%** | **9.58%** | **3/3** |
| 5% day500 + 80% maturity-weighted + tail | 57.04% | 26.54% | 11.40% | 12.91% | 2/3 |
| **5% day500 + 90% maturity-weighted + tail** | 58.41% | 23.34% | 9.16% | 11.21% | **3/3** |
| **5% day500 + cap sales at 80% through day560, trailing 20% on breakdown** | 59.40% | **24.45%** | **12.14%** | **11.74%** | **3/3** |

All candidates FAIL in 2013 (peak at day371, before day500).
The holdback rule sold all of its BTC eventually in the three
modern historical cycles, with 9, 8 and 10 actual sales respectively.
This is an IN-SAMPLE 3/3 achievement, not predictive evidence
with a reliable probability estimate.

### Daily price-only and same-horizon cash/BTC accounting

Assume exactly one BTC owned by day500 for every model.
Sale proceeds are summed as USD, residual BTC is marked to the
**identical day730 price**, and gross account wealth is compared with
holding that 1 BTC to day730 (no sales). Any remaining BTC is
explicitly included. No portfolio can create more BTC, borrow
cash, sell more than 1 BTC or use later prices to size earlier
orders. The unit tests reject missing prices and future leakage.

The simple fixed 525–560 schedule still generates higher historical
gross sale proceeds than *every* day500 dynamic variant in
2017, 2021 and 2025. The extra early sale is therefore not
validated as superior historical execution, merely possible
insurance against another early peak.

## Structural shift stress: explicitly FICTIONAL price paths

Because 3 recent cycles can simply have similar peak dates,
we tested three hypothetical future BTC/USD paths using a
deterministic continuous daily price curve, not fitted to a
past cycle. Values below are an arbitrary synthetic one-BTC
USD-denominated stake marked on day730; comparisons are
**gross before tax and brokerage**.

| Fictional regime | Hold BTC | Sell 100% on six maturity dates | 5% day500 + maturity-weighted, no holdback | 5% day500 + protected 20% tail |
|---|---:|---:|---:|---:|
| Early day510 peak, sharp crash | $170 | $230 | $238.52 | $236.20 |
| Delayed day680 peak and retracement | $900 | $355 | $348.53 | **$462.68** |
| Market continues rising through day730 | $980 | $391.67 | $380.88 | **$493.83** |

The 20% holdback improves performance **relative to the fixed
sell-all benchmark** under extended rallies but still loses
almost half of the hypothetical buy-and-hold value. On the
fictional unbroken bull it sold 80% and retained 20% at day730;
on the late peak it sold 94%, retaining 6%. This is NOT a
sufficiently protective rule if cycle timing changes substantially.

## Costs and tax remain unresolved

The weekly 525–560 benchmark uses **six AUD$3 brokerage orders = A$18**.
The modern-cycle 90% maturity-heavy staged model executed **10–11**
orders (**A$30–33**). The 20% holdback version executed **8–10**
orders (**A$24–30**). Brokerage values are AUD and **cannot be
subtracted from USD/BTC effective sale price** without spot historical
FX conversion. Backtests are strictly **gross USD/BTC**; ETF bid/ask
spreads, capital gains and lot IDs are not yet included.

The user previously specified simplified **10% effective SMSF CGT on
eligible long-held sales** and A$3 orders. Real CGT eligibility
depends on fund phase, lot acquisition date and annual SMSF tax
treatment (short-held taxable gains can incur 15% effective tax);
we must evaluate the *actual 2026 portfolio lot history* rather
than assume one BTC owned before every historical halving. We must
then test after-tax sell AND re-entry accumulation, comparing total
BTC/wealth against simply holding.

## Research decision

**Retain day500 dynamic DCA-out with a small initial hedge and
a capped flexible tail as a RESEARCH candidate. Do not switch
Production to any of these rules.** It meets a 25% ex-post gross
historical peak-error threshold in 3/3 recent cycles only because
we have seen the relevant market peak dates before designing
the maturity windows. It fails dramatically in 2013 and remains
vulnerable if the next top is late.

The most valuable next test is prospective event-by-event
**re-entry** after realised sales, AUD FX, per-transaction A$3
fee and true FIFO SMSF parcel taxation. Compare BTC and AUD
terminal values of a self-financing account starting with the
user's actual 2026 capital, not one fictional BTC owned since
2012/2016/2020.

**Everything here is in the draft Research PR. The existing
Production allocation model, archived audit master and
My Portfolio recorded transactions have NOT been changed.**
