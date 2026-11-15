# V5.9 research ASX:IBIT reference receipt-time correction — 16 November 2026

## Scope

Research-only provenance correction in `engines/research/v59_forward_dca_tape.py`.
It changes only the timestamp attached to the optional delayed Yahoo Finance
ASX:IBIT reference in the separate prospective V5.9 evidence tape.

## Defect and correction

Previously the daily runner passed the timestamp taken **before** the BTC, FX,
realized-price and IBIT HTTP work into `fetch_ibit_quote(now=...)`. The returned
quote age and its saved `captured_at_utc` were therefore measured against the
start of the whole run, not the receipt of the IBIT response. This slightly
understated the quote's age and mislabelled the local capture time.

The collector now calls the existing read-only quote reader without a
pre-request clock override, then records `datetime.now(timezone.utc)` only
after the request returns or fails. The source market timestamp remains
provider-dated. A missing or rejected quote remains explicitly unavailable;
the BTC observation still proceeds independently.

## Validation

- Added a deterministic clock-controlled test proving successful quote capture
  is timestamped after the provider call, not before it.
- Added the corresponding failure-path assertion: an unavailable quote records
  the post-request failure time and remains `UNAVAILABLE`.
- Existing tests continue to enforce correct ASX symbol/currency, finite price,
  dated provenance, stale-reference exclusion, no look-ahead, first-capture
  immutability, Monday-pair requirements, cash caps and paper-only accounting.
- The existing `v59_daily_forward_validation` pull-request workflow is the
  only validation workflow used; no new schedule, secrets, notifications,
  portfolio access, brokerage integration or data-branch write is introduced.

## Boundaries

The Yahoo reference is still a single-provider delayed daily-candle mark, not
an executable bid/ask, verified Stake fill or after-cost ASX:IBIT return.
No Production V5.8.2, live Research V5.9 sizing, Cycle Trading signal/rule,
dashboard, portfolio, Google Sheets, ntfy, broker or authoritative market-data
master is changed. No investment model is promoted.
