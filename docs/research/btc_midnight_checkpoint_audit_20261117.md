# PR #267 midnight UTC capture checkpoint audit

**Research-only, read-only coverage measurement.** This audit supports existing
issue #205. It does not change the Kraken/Coinbase schedule or any trading rule.

## Fixed comparison

- PR #267 merged: **13 November 2026, 10:06:20 UTC**.
- Pre-change baseline: **3 actual midnight receipt-time paired observations
  among 68 paired source observations** (4.4118%).
- Seven-day checkpoint: **20 November 2026, 10:06:20 UTC**.
- Fourteen-day checkpoint: **27 November 2026, 10:06:20 UTC**.

## Measurement rules

The existing workflow fetches origin/main after the source-publication step;
the audit therefore reads only the remotely published immutable Kraken and
Coinbase tapes through their hash-chain validators. A local uncommitted capture
cannot enter a checkpoint result. A pair requires the same six-hour slot in both sources
and both actual HTTP receipt instants after the merge. Midnight coverage
requires both receipt instants to fall in **00:00:00 inclusive to 06:00:00
exclusive UTC**. The nominal slot label is checked against the actual receipt;
it cannot override it.

The comparison preserves the baseline definition (same-slot paired source
observations) and separately reports receipt skew above five minutes. It
reports the seven-day and fourteen-day cumulative windows using only rows
received before each fixed checkpoint. Rows after a checkpoint cannot change
that checkpoint's result.

Schedule launches, runner starts, and workflow successes are not captures.
A source row must actually exist in the immutable tape. Missing snapshots are
never backfilled or reconstructed. The audit writes only a disposable Actions
artifact; it does not write either source tape, send ntfy, place orders, access
the personal portfolio, or alter Production, Research V5.9, Cycle Trading,
Google Sheets, brokerage, or the authoritative market-data master.

## Current run

The implementation is prospective. Before 20 November the seven-day result
must remain CHECKPOINT_NOT_DUE; before 27 November the fourteen-day result
must remain CHECKPOINT_NOT_DUE. Interim counts are explicitly labelled
non-checkpoint diagnostics and are not an improvement claim.

Coverage is descriptive collection reliability only, not evidence of market
alpha, execution quality, or investment performance.
