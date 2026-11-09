# V5.9 1x / 1.5x / 2x ordinary-runway study: chronology input gate (2026-11-09)

**Scope: research-only, not trading validation. No Production, Cycle Trading, Streamlit, or ntfy changes.**

## Identified issue

The `v59_runway_cap_backtest.py` CSV loader previously accepted only
`date,btc_price_aud,raw_risk_weight`. Its narrative said weights must be
point-in-time/lagged but neither the loader nor `replay_runway_cap()` could
check whether the hypothetical signal predated its simulated buy. A same-day
or future-dated research signal could silently enter cap comparisons.

## Contained correction

- Require `signal_date` in the CSV and every direct replay row.
- Reject any `signal_date >= date`, including missing fields, with strictly
  increasing execution dates; record both dates on each returned order.
- Fail closed on nonfinite cap, initial capital, reserve, fee, and slippage
  inputs instead of allowing NaN/Infinity to contaminate hypothetical results.
- Extend deterministic regression tests to exercise rejection and valid
  previous-day signals; existing 1x/1.5x/2x capital and reserve rules remain
  unchanged.

## What this does NOT establish

An earlier user-supplied signal date does not prove the risk score was
actually published and ingested before the order; source revision/vintage
proofs are still absent. In particular, there is no independent point-in-time
history for the full composite risk and no matched, costed ASX:IBIT fills
through all BTC cycles.

Existing unverified result tables should not be upgraded to deployable
trade signals. Re-run matched chronological tests using dated, verified
source vintages, consistent cash, risk, fees and next-tradable prices.
Historical BTC plus AUD residual equity, BTC units, drawdown and
uninvested cash must all be reported, including losing windows.

**Release decision:** test-only safety improvement; still NOT a
Production or live Research sizing promotion. Keep frozen V5.8.2 and
Cycle Trading notification schedule unchanged.
