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

The existing daily V5.9 forward-tape automation now attempts one
BGeometrics realized-price last reading alongside its established
closed UTC BTC price. Each new immutable tape entry records:
provider, URL, numeric reading, **provider's own observation date**,
first-captured UTC time and raw response SHA-256. No past capture is
overwritten. If BGeometrics API is delayed, unavailable or more than
3 days stale, status is explicitly UNAVAILABLE / STALE_OR_DELAYED
and its conditional paper strategy **does not buy**. The original
research paper strategies and live notifications are unaffected.
The free API may withhold recent days: an unavailable reading is
not treated as evidence that BTC is cheap or expensive.

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
