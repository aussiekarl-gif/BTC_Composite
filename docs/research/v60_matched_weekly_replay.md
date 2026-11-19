# V6.0 matched weekly replay design

This stage adds a standalone replay engine. It imports only the V6.0 policy module and pandas; it does not import V5.9 or Production code.

## Timing and data
- Signal: completed Sunday BTC/USD close.
- Valuation: mean of the previous 200 completed weekly Sunday closes, excluding the signal Sunday.
- Execution proxy: next Monday BTC/USD daily close converted using the latest USD/AUD observation dated on or before the signal Sunday (maximum five-day age).
- This is a BTC/AUD spot proxy, not an ASX:IBIT price or broker fill.

## Account and constraints
- Default hypothetical capital A$510,000, with 41% initial BTC exposure and 59% cash.
- Cash yield and BTC holding drag are separate assumptions.
- Candidate allocation is a percentage of deployable cash.
- Optional protected reserve is a percentage of initial cash.
- Maximum weekly buy is 5% of original capital.
- Fees and buy friction are modelled separately.
- Fixed weekly DCA and all V6.0 candidates use identical 104-week cohorts. The reference 20% / 25% / 30% discount thresholds are compared with a 10% / 15% / 20% sensitivity; fixed DCA and the base 2.5% policy are emitted once per cohort.

## Required reporting
- Final AUD equity, BTC held, cash remaining, total spend, buy count and drawdown.
- A same-spend/same-transaction-count uniform-buy diagnostic is reported separately and explicitly marked hindsight-only.
- Rolling 104-week windows overlap. Cohort results are not independent samples and must not be described as such.

The replay is research-only and cannot execute trades. No V6.0 candidate is approved by this stage.
