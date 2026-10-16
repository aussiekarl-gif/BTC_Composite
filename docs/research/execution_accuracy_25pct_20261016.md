# BTC cycle execution-quality audit: target <25% average price error

**16 October 2026 · RESEARCH ONLY · Do not promote to Production**

Sources:
- [Read-only successful GitHub run](https://github.com/aussiekarl-gif/BTC_Composite/actions/runs/38880854775)
- [Independent local-extrema audit engine](../../engines/research/execution_error_audit.py)
- [Cash-feasible round-trip audit engine](../../engines/research/post_sale_execution_audit.py)
- Regression tests: `tests/test_execution_error_audit.py` and
  `tests/test_post_sale_execution_audit.py`.
- Original full-cycle account simulator:
  `engines/research/full_cycle_reinvestment.py`.

## User objective

Target an executed average sale price no more than 25% below a cycle peak
and an executed average repurchase price no more than 25% above an achievable
cycle low. **No one can know future turning points:** score ex post only,
using truly point-in-time signals to place historical orders.

The old 25%-execution-error 2026–2038 scenario is an assumption, not an
achieved accuracy of the model. This audit now directly tests the historical
12/16-observation **equal-tranche** plans. The plans themselves are not yet
signal-strength-weighted dynamic DCA. Evaluation is fully read-only and
does not change the rules or master.

## Historical source / caveats

- 557 valid paired weekly BTC/AUD close and archival risk observations:
  2016-01-04–2026-08-31. First trade uses prior observation's risk.
- 0.3% research friction on each trade side inherited from the simulator.
  This is **NOT** the requested A$3 fixed brokerage/10% SMSF CGT model.
- Archived risk data still need a point-in-time audit; closing-price
  execution is idealised.
- Four scenarios: simple .35 buy/.60 sell with 12 or 16 equal weekly
  tranches, and analogous 12/16 scenarios with high-risk-armed 25%
  drawdown plus 20-week AUD moving-average sell confirmation.
- Price errors use BTC-volume-weighted average executions; buy
  `average_price / reference_low - 1`, sell
  `1 - average_price / reference_high`. Selling must precede buying.

## Audit A: fixed independent +/-52-week extrema around each plan

This deliberately demands local vicinity to extrema; it can include lows
before cash is available and is therefore **overly harsh for some buys**.
Censored +/-52-week windows excluded.

| Strategy | Buy <=25% | Sell <=25% | Both <=25% on complete pairs |
|---|---:|---:|---:|
| simple 12-week | 1 / 5 | 3 / 6 | 0 / 5 |
| simple 16-week | 1 / 5 | 2 / 5 | 0 / 5 |
| confirmed 12-week | 1 / 3 | 0 / 3 | 0 / 3 |
| confirmed 16-week | 1 / 3 | 0 / 3 | 0 / 3 |

## Audit B: cash-feasible, time-ordered reference pair

Reference high: maximum price from sale plan start through subsequent
buy plan start. Reference low: minimum from sale plan finish through
buy plan finish **plus 26 weeks**, to penalise buying before an extended
decline. Pair must have a high timestamp no later than its low timestamp.
Unobservable future extensions and chronologically impossible oracle
pairs are excluded. This changes the scoring metric but never the
trade logic.

| Strategy | Both <=25% on eligible sell->buy pairs | Buy <=25% | Sell <=25% |
|---|---:|---:|---:|
| simple 12-week | 2 / 5 | 2 / 5 | 4 / 5 |
| simple 16-week | 2 / 6 | 3 / 6 | 4 / 6 |
| confirmed 12-week | 1 / 3 | 1 / 3 | 2 / 3 |
| confirmed 16-week | 1 / 3 | 1 / 3 | 2 / 3 |

### Cash-feasible 16-week model, individual historical pair errors

| Sale started | Buy started | Sell below accessible high | Buy above accessible low | Both within 25% |
|---|---|---:|---:|---|
| 2017-05-22 | 2018-12-03 | 84.53% | 15.17% | NO |
| 2019-05-27 | 2019-10-07 | 14.99% | 33.37% | NO |
| 2020-11-30 | 2022-05-23 | 46.97% | 34.62% | NO |
| 2024-03-18 | 2024-07-08 | 8.20% | 11.07% | YES |
| 2024-11-25 | 2025-03-17 | 6.56% | 16.11% | YES |
| 2025-07-21 | 2025-11-17 | 6.33% | 40.55% | NO |

Early selling in 2017 and 2020 and insufficiently patient buying in
2022/2025 are prominent. The confirmed model avoids some early sales,
but can sell much later below the peak; its 2021 sale remained ~39%
below the reference high while its next buy was ~35% above the low.

## Critical interpretation

**The existing model has NOT demonstrated consistent 25% execution error.**
Small in-sample samples cannot establish a future hit rate. Large terminal
equity in a historically exponential BTC era does not prove a reproducible
trade execution edge. No new rule should be trained and then judged solely
on the same 2016–2026 observations repeatedly examined.

## Research to prioritise, not yet implemented/promoted

1. Test *risk arm* followed by earlier momentum deterioration (before a
   full 25% price drop), with a split staged exit rather than a 16-week
   commitment regardless of rebound.
2. Test **genuinely adaptive** tranche weights using **prior-observation**
   risk, 20/50-week momentum and/or USD 200WMA, plus retained buying
   reserves for further breakdowns and confirmation.
3. Pre-register thresholds on older periods, lock them, then run unseen
   chronological walk-forward. Historic 2016–2026 has been heavily
   inspected; prospective paper-trading is the cleanest test.
4. Always report: buy error, sell error, **both within25%**, failure to
   enter/exit, drawdown, BTC retained, terminal after-tax AUD capital,
   and benchmark with identical initial capital. Compare 12 vs 16
   weekly tranches at A$3/order and realistic SMSF parcel tax.
5. Production, audited master, portfolio storage remain unchanged.
