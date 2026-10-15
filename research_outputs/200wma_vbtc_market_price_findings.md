# Official VBTC ETF market-price/NAV historical research — 2026-10-15

**Research only. Production V5.8.2 and master branch unchanged.**

[Verified GitHub run 38813587696](https://github.com/aussiekarl-gif/BTC_Composite/actions/runs/38813587696), artifact `200wma-vbtc-real-market-nav`.

## What improved in the data
- The official [VanEck Australia VBTC historical market and NAV XLSX](https://www.vaneck.com.au/etf/alternatives/vbtc/downloads/fundhistoprices/) is accessible from GitHub Actions and provides issuer-reported **daily last traded ASX price, NAV, premium/discount, and volume**. The reader reconciles the premium against NAV and fails closed if workbook headings, dates or calculations change.
- 589 trading-day records: **21 Jun 2024 to 14 Oct 2026**, with **no zero-volume days** in that export.
- The median market premium to NAV was **+0.272%**. The 90th percentile was **+2.680%**; extreme reported premiums/discounts reached **+9.979% / −7.609%**. Among days with positive reported volume, **10** had a premium above +5% and **5** had a discount below −5%.
- These large gaps are **NOT bid–ask spreads** and might reflect NAV valuation timestamps, especially when Bitcoin moves during ASX closures. Reported *last traded* price is **not** a guaranteed executable entry or exit quote. Actual ETF units/market price execution should be monitored prospectively.

## First issuer-market execution proxy test
Only real fund history is used. BTC/USD completed-week deviations are calculated from the frozen archived 200WMA source; 0.1% dealing fee, 0.5% slippage and A$20 brokerage are added to ETF issuer trade references, with illustrative early-July SMSF accumulation CGT. Issuer NAV already includes management fees: **do not apply the separate 0.45% management fee a second time**.

| Matched time from entry | Model at issuer last trade | Model at issuer NAV | Number of overlapping starts |
|:--|--:|--:|--:|
| 52-week median advantage over identically funded DCA | +5.506% | +5.272% | 17 |
| 52-week winning starts (market fills) | 11/17 | 11/17 | 17 |
| 52-week worst market-fill advantage | −9.019% | −8.970% | 17 |
| 104-week median advantage over DCA | +42.825% | +42.165% | **4 only** |
| 104-week winning starts (market fills) | 4/4 | 4/4 | **4 only** |
| 104-week 26-week idle-recycling median (market fill) | +31.540% | +29.149% | **4 only** |

The **26-week idle-recycling rule underperformed the base tier strategy in the four 104-week starts** from VBTC's short history. This is not sufficient to reject or promote it, but undermines confidence in the apparent four-year synthetic-price improvement.

## Required before promotion
- VBTC did not exist before June 2024. **Do not label 2018–2023 simulated ETF results as actual VBTC backtests**.
- Real market price vs NAV differs for structural/timezone reasons; examine premium at each prospective order, bid–ask spreads and realistic volume constraints.
- 104-week test has only four correlated starts and no independent cycle history. It cannot establish a 90% success rate or a reliable trading edge.
- Use the frozen [forward-only VBTC paper experiment](https://github.com/aussiekarl-gif/BTC_Composite/blob/research/cycle-strategy-optimization/research_forward/200wma_v1/README.md), beginning no earlier than completed Monday 19 October 2026, to build evidence prospectively without rewriting earlier weeks.
