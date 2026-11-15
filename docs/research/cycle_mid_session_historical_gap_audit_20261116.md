# Cycle mid-session research tape: historical gap visibility — 16 November 2026

## Scope

Read-only reliability improvement to the existing
`cycle_mid_session_capture_health` audit. It runs inside the already scheduled
nightly Cycle research workflow and writes only its existing JSON artifact.
There is no new cron, data source, notification, signal, trade or portfolio
write.

## Finding

The append-only mid-session tape contains 14 verified observations from
22 October through 13 November 2026. Against the existing Monday–Friday
capture schedule from the declared 20 October enrolment date through the last
completed weekday (Friday 13 November), five expected weekdays have no row:

- 20 October
- 21 October
- 5 November
- 6 November
- 10 November

The latest completed weekday, 13 November, does have a verified row. The
previous health audit checked only that latest date, so a newer successful
capture could conceal earlier gaps from its status summary. Missing source
rows remain missing; this change does not infer why a workflow did not publish
and does not attempt backfill.

## Change

The existing read-only audit now enumerates every completed weekday from
`FIRST_ELIGIBLE_DATE` through the latest completed Sydney weekday, counts
verified rows, and lists the exact missing dates. It retains the existing
latest-day status, source hash, capture timestamp, and no-backfill flags. The
existing workflow emits a GitHub Actions warning when historical gaps exist
and retains the same 30-day artifact.

## Validation

Added offline tests proving:
- earlier gaps remain visible even when the latest completed weekday is present;
- a contiguous sequence reports zero gaps;
- the audit remains read-only and continues to prohibit backfill.

The existing `research_forward_cycle_tape` and
`research_cycle_mid_session_watch` PR workflows are the only CI paths used.
No new schedule or notification stream is introduced.

## Safety

Only the isolated research capture-health audit, its tests and this document
change. The mid-session source CSV and SHA chain are not modified. Production
V5.8.2, Research V5.9 live sizing, Cycle Trading signals/rules/dashboard,
portfolio, Google Sheets, ntfy, brokerage and authoritative market-data
master are untouched.
