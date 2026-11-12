# Bitcoin Realized Price: Research Protocol — 13 Nov 2026

**RESEARCH ONLY: no live buy/sell recommendation or Production changes.**

## Motivation and definition

Realized Price is realized capitalization divided by circulating BTC supply:
an aggregate estimate of each Bitcoin's last-movement cost basis. BTC spot
divided by Realized Price corresponds closely to MVRV under a consistent
provider's supply convention; this is **not an independent signal from MVRV**.
Do not double-count correlated indicators as separate bottom confirmations.

Benjamin Cowen's 30 October 2026 report names the realized price near
US$54,000 as an important potential downside area, while warning that
institutional/ETF ownership could let this cycle bottom without touching it.
Neither his price illustration nor anyone's prediction is coded as a
fixed trading target: the realized-price series moves with on-chain activity.

Source references:
- https://studio.glassnode.com/dashboards/introduction-realized-unrealized-value?a=BTC
- https://studio.glassnode.com/charts/market.PriceRealizedUsdPit?a=BTC
- https://benjamincowen.com/reports/bitcoin-and-the-cycle-clock-october-2026
- https://charts.bgeometrics.com/realized-price.html
- https://bitcoin-data.com/v1/realized-price/last
- https://charts.explore21.com/bitcoin-realized-price

## Historical source limitation

The pre-existing user-supplied BlockHorizon/PlanB CSV in data/ has 5,394
consecutive UTC rows dated 2011-12-31 through **2026-10-06**. Last ordinary
Realized Price is **US$53,761.98**, NOT today's live reading. Do NOT use
the different STS or 2-year Realized Price columns as ordinary cost basis.
The Aug 30 manual_metrics.json USD 58,200 value is stale.

Historical source formula parity and historical publication vintages remain
**unverified**. All retrospective results are exploratory, NOT proved
as-published on-chain backtests.

## Predeclared matched tests

Use strict previous-Sunday BTC/USD spot and same Sunday's ordinary
Realized Price, following Monday BTC/AUD execution proxy. Require exact
dated source; no fill-forward. 104-week Jan/Jul historical cohorts,
including six overlapping 2022–24 holdouts. Original capital A$510,000,
41% virtual existing BTC exposure, 5% annual uninvested cash return,
5%-of-original A$25,500 weekly limit, A$3 fixed order cost, 0.3% execution
friction, 0.25% annual BTC holding drag.

Compare original aggressive 3x and strict risk<=0.20, against new
R2-WF risk<=0.50 AND realized-ratio at <=1.00, <=1.10 or <=1.25,
plus the strict risk<=0.20 AND ratio<=1.10/1.25, and OR of
risk<=0.20 or ratio<=1.10 (always stop for risk >0.50).
Measure BTC units, AUD remaining, terminal AUD portfolio, worst
drawdown, buy count, same-event expenditure and same-net-spend
entry-price attribution. No leverage or sales.

Also compare 20-week A$25k fixed DCA after the first realized-price
ratio <=1.00, 1.10 or 1.25 in the 2015/2018/2022 major bear cycles,
against 20-week buying near 200WMA on a shared halving-relative
calendar. 2015 is PRICE/FX only: no fabricated V5.9 WF risk.
2020 COVID is a shock, not an extra independent 4-year cycle.
2026 cycle bottom is right-censored and not forecast as known.

## Prospective as-published series

The existing daily V5.9 forward-tape automation first retrieves the
dated **Explore21 Bitcoin Realized Price CSV** (published by a separate
Bitcoin Core node operator under CC BY 4.0), and uses BGeometrics
realized-price /last as a **secondary fallback**. On 12 November 2026,
the BGeometrics free endpoint was experimentally confirmed to be
**seven days delayed** with a provider delay flag; such a reading was
correctly rejected for the 11 November BTC closing signal.
Explore21 chart: https://charts.explore21.com/bitcoin-realized-price
Explore21 free dated CSV:
https://charts.explore21.com/data/bitcoin-realized-price.csv

Each new immutable tape entry records provider, URL, numeric reading,
**provider's own observation date**, first-captured UTC time and full
raw response SHA-256. No past capture is overwritten. If both public
sources are stale, unavailable, delayed or more than three days old,
status is explicitly UNAVAILABLE / STALE_OR_DELAYED and its conditional
paper strategy **does not buy**. The original paper strategies and
live notifications are unaffected. No source is treated as a valid
point-in-time record merely because its revised historical values
contain past dates. Neither source supplies actual ASX:IBIT fills.

Only source-valid prospectively recorded ratios with WF risk <=0.50
can score the new realized110 paper comparison after a **future**
independently recorded Monday close. Broker ASX:IBIT fills are not
validated by this research proxy.

## Promotion gate

No change to V5.8.2 Production, live V5.9, Cycle Trading, Streamlit,
single daily ntfy, broker, investment portfolio or master data.
Historical price-data matching and 2022–24 overlapping cohorts are
NOT independent prospective evidence. Require cross-provider metric
parity, original point-in-time data vintages, new real-time captures,
after-cost and cap-compliant ASX ETF comparisons, and convincing
forward risk-adjusted performance before any promotion.

Results are retained with the existing Monday weekly GitHub
historical report; daily recorded references stay on the isolated
research/v59-forward-tape branch.

## Verified numerical results — historical run, 13 Nov 2026 (Brisbane)

The first GitHub Actions run with the existing BlockHorizon realised-price
data completed its real BTC/USD and AUD/USD matched-history calculations and
historical causal tests successfully:
https://github.com/aussiekarl-gif/BTC_Composite/actions/runs/43306570788

### Six overlapping later historical holdouts: R2 portfolio outcome

Capital A$510,000, ~41% starting BTC, 59% AUD cash earning 5%,
5% original-capital weekly limit A$25,500, same dates and costs in
each policy. Compare **portfolio value**, not just the conditional
purchase-price selection. The realized-price metric's historical
provider publication vintages are **unverified**.

| Research-only DCA policy | Median portfolio return vs strict risk<=0.20 3x | Worst cohort | Positive cohorts | Median AUD uninvested at terminal |
|---|---:|---:|---:|---:|
| strict V5.9 WF risk<=0.20 3x | baseline | 0.00% | 0/6 | A$5,409 |
| aggressive V5.9 3x | +0.05% | -1.53% | 3/6 | A$1 |
| risk<=0.50 AND BTC spot<=100% of realized | **-10.31%** | -30.72% | 1/6 | A$321,844 |
| risk<=0.50 AND BTC spot<=110% of realized | **-8.88%** | -30.72% | 1/6 | A$312,399 |
| risk<=0.50 AND BTC spot<=125% of realized | **-7.22%** | -30.72% | 1/6 | A$180,763 |
| realized<=110% OR WF risk<=0.20, risk<=0.50 | 0.00% | 0.00% | 0/6 | A$5,409 |

Both narrower AND combinations (realized<=110% / <=125% with risk<=0.20)
matched the more restrictive respective realized-only rows on this
six-cohort sample. The permissive OR combination matched existing strict
risk<=0.20 throughout. **No new indicator produced an independently
verified improvement here**; false cost-basis precision would create
too much missed BTC exposure.

### One historical major bottom per cycle: A$500k 20-week paper DCA

Price/FX-only study with common halving-relative cycle dates, 5% idle
cash, A$25k/calendar week and same illustrative friction.
2015 has **no** V5.9 WF R2 comparison. The exact first realized
ratio signal is a historical *revised-data* proxy; not an archived
provider PiT observation.

| Complete bear cycle | 20-week after spot<=100% realized | 20-week after spot<=110% realized | 20-week after spot<=125% realized | Original 20-week 200WMA+5% |
|---|---:|---:|---:|---:|
| 2015 | 1,602.61 BTC | 1,602.61 BTC | 1,602.61 BTC | 1,616.13 BTC |
| 2018 | **92.82 BTC** | **92.82 BTC** | 54.44 BTC | 89.11 BTC |
| 2022 | 16.20 BTC | 16.20 BTC | 15.45 BTC | 16.20 BTC |

These are BTC holdings at the common halving-day-1300 terminal after
illustrative ETF drag. In 2018, the first <=1.00/1.10
realized-price paper entry was **2018-11-26** versus WMA+5% on
**2018-12-17**. The 1.25 threshold activated considerably earlier
(**2018-06-18**) and lost many BTC units. In 2022, the 1.00/1.10
realized-price and WMA+5% strategies first bought **2022-06-20**,
well before the November cycle low. In 2015 the first fully covered
weekly WMA of this project begins in January; do not infer that
2014 on-chain or WMA entry signals were retrospectively observed
or falsify unavailable risk scores.

### Interpretation and control

Realized price is worth **tracking as a bottom-watch valuation reference**
and testing against confirmed future prices, but this sample does not
justify either an absolute wait-until-realized requirement or automatically
raising live purchases on a realized-price touch. The core concern is
holding hundreds of thousands in cash while BTC can recover without
returning to the average cost basis.

The prospective BGeometrics reference is independently dated and
is marked **STALE_OR_DELAYED** rather than treated as a buy signal
whenever its observation does not meet a maximum three-day age and
the provider delay gate. No fresh forward result exists for this new
metric at the time of this first historical evaluation.

All existing live Production V5.8.2, V5.9 recommendation, Cycle Trading,
real portfolio, Stake and single daily ntfy remain unchanged.

### Independent public latest-value sanity check (not live broker quote)

The Explore21 site reported **US$53,874 realized price on 11 November
2026**, close to Glassnode's publicly displayed latest reading of
**US$53,930** and the Axel Adler chart value **US$53,879** for the
same day. The respective spot close from Explore21 was about
**US$73,915** (~1.37x realized price). These public displays
independently support the **order of magnitude** of the realized-price
scenario, but do not certify identical source methodology, a guaranteed
bottom, real-time API entitlement, or historical PiT revisions.
Compare the same UTC close and source each time.
