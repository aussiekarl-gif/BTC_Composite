# Diminishing BTC cycles: 25% versus 40% execution-price error (16 October 2026)

**Research only. Not a forecast, causal strategy backtest, or Production trading recommendation.**

Reproducible code: `engines/research/price_error_sensitivity.py`.
Regressions: `tests/test_price_error_sensitivity.py`.
Parent model: `engines/research/diminishing_cycle_smsf_projection.py`.

## Controlled change
Identical A$500,000 starting capital, A$3/order, 16 synthetic
orders per leg, assumed 10% effective SMSF accumulation-phase CGT
on realised eligible gains, same three illustrative diminishing cycles.
Only change: sell at 75% of *subsequently known* peak and buy at 125%
of *subsequently known* trough instead of 60% / 140%.

**DCA caveat:** This is an *average executed price* assumption. The 16
synthetic orders all execute at one indicative price. Actual weekly
dynamic DCA, risk-dependent weights, changing tax-lot ages and spreads
have NOT been modelled. Future true peak and bottom prices are unknowable
when entering orders, and this result must never be labelled out-of-sample.

## Three-cycle terminal nominal AUD at third hypothetical bear-market bottom

| Scenario | Passive hold | 40%-error trade | 25%-error trade | 25%-error vs hold |
|---|---:|---:|---:|---:|
| Conservative | 1,154,889.12 | 560,147.44 | 1,453,941.44 | +25.89% |
| Middle | 989,904.96 | 1,079,610.56 | 2,792,670.12 | +182.11% |
| Strong | 1,181,136.60 | 2,064,841.10 | 5,402,232.60 | +357.38% |

| Scenario | 25%-error total realised CGT paid | Total trading brokerage |
|---|---:|---:|
| Conservative | A$146,386.09 | A$336 |
| Middle | A$332,320.63 | A$336 |
| Strong | A$694,759.86 | A$336 |

All terminal holdings remain marked to market and **no terminal sale CGT**
is charged. The passive benchmark never sells and incurs no realised CGT.

## Accumulated BTC from each trade at 25% error (after brokerage and realised-gain tax)

| Scenario | First cycle | Second | Third |
|---|---:|---:|---:|
| Conservative | 1.417x | 1.054x | 0.843x |
| Middle | 1.867x | 1.433x | 1.055x |
| Strong | 2.224x | 1.614x | 1.274x |

For price-error assumption `e`, round-trip gross BTC ratio is
`(1-e) / ((1+e)*(1-drawdown))`. At 25% error this requires drawdown
> 40% before tax; if 10% applies to nearly all gross sale proceeds,
roughly >46% to break even. Exact after-tax break-even depends on the
AUD purchase cost basis and realised gains/losses, and actual allocation
per execution interval.

## Next validation

1. Measure **volume-weighted execution error** of real point-in-time
   12-week and 16-week DCA schedules against cycle extrema, using data
   that would have been available at each date.
2. Use full AUD transaction-by-transaction accounting for the A$3
   brokerage fee; add spreads, annual ETF fees and realistic fills.
3. Record SMSF FIFO parcel cost base, 12-month holding eligibility,
   10% or 15% accumulation-phase treatment, and retirement-phase
   exemptions where applicable.
4. Evaluate untouched forward periods and drawdown/cash-risk compared
   with simple matched buy-and-hold. Keep Production and source master unchanged.
