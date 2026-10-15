# Cash recycling after stale BTC 200WMA sell orders — 2026-10-15

**Research only: do not promote to Production V5.8.2.**

Verified [GitHub Actions run 38811194137](https://github.com/aussiekarl-gif/BTC_Composite/actions/runs/38811194137), artifact `200wma-idle-cash-recycling-aud`.

## Purpose
Previous AUD after-tax backtests revealed cash drag after BTC tier sells. Median cash remaining at two-year exit for 2019 starting cohorts was approximately **A$1.98 million** and for 2023 starting cohorts **A$935,000**. Compare a simple causal re-entry safeguard.

## Locked scenario for this experiment
- Initial A$500,000, 20% synthetic BTC ETF exposure / 80% cash.
- Risk-weighted cash funding over 12 weeks, then 12-week bell-shaped buy orders and 16-week bell-shaped sell orders; same-tier overlap blocked.
- Prior completed BTC/USD weekly close compared with 200WMA, with next-week-close simulated fills at BTC/AUD reference prices.
- Flat A$20 commission **per fill**, 0.1% percentage fee, 0.5% slippage, 0.45% annual hypothetical management-fee drag.
- Indicative compliant SMSF 15% accumulation capital gains tax with FIFO acquisition parcels, Australian financial-year loss carry and **early-July annual tax settlement** (cash first, otherwise an ETF disposal).
- Recycling condition: if **over 50% of marked holdings are unreserved cash**, there is no active buy-tier job, and there has been no executed buy for a specified idle period, buy **25% of available unreserved cash** at the following completed weekly close. No forward-looking information.

## After-tax AUD findings
| Holding horizon | No recycling | 26-week idle trigger | 52-week idle trigger |
|:--|--:|--:|--:|
| 2-year median advantage over pure DCA | +2.402% | +2.402% | +2.799% |
| 2-year worst advantage | −59.482% | **−49.143%** | −59.482% |
| 2-year 10th percentile | −21.643% | **−18.734%** | −21.487% |
| 2-year winning overlapping cohorts | 48/89 | 47/89 | 50/89 |
| 4-year median advantage | +33.099% | +34.682% | +34.801% |
| 4-year worst advantage | −30.502% | **−21.260%** | −25.957% |
| 4-year 10th percentile | −11.543% | **+6.236%** | −9.052% |
| 4-year winning overlapping cohorts | 53/63 | **58/63** | 53/63 |
| 4-year median weekly fill count | 418 | 475 | 451 |

### Persistent failure years
For two-year investing horizons, the 26-week cash safeguard did **not** resolve the historically poor outcomes. All 13 rolling 2019 starts still lost versus DCA, median **−28.607%** (versus −32.690% without); all 13 rolling 2023 starts still lost versus DCA, median **−11.050%** (versus −12.872% without). 2021's median fell from +96.852% to +84.846%, illustrating the upside sacrifice.

**Decision:** keep 26-week idle cash recycling as a **potential research risk-control** because it improves four-year worst case and lower-tail results, but do **not** call it a verified optimal rule or apply in Production.

## Statistical caveats / required validations
- Parameters were suggested **after inspecting the same 2018–2024 outcomes** (risk of data snooping); overlapping starts overstate sample independence.
- ETF returns are simulated BTC/AUD prices with fee drag, not actual ETF historical prices, trades, spreads or distributions.
- Capital gains are calculated in a simplified SMSF model assuming full accumulation-phase taxation. An eligible pension-phase or mixed fund requires separate analysis.
- Independent rolling forward tests, sensitivity to signal noise / missed fills, and a clean test interval inaccessible during parameter selection are needed before promotion.
