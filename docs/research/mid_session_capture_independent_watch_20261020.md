# BTC Cycle mid-session capture incident: independent detection and forensic evidence

**20 October 2026 (Brisbane/Sydney).** The separate hash-linked `data/research_forward_validation/cycle_mid_session_market_watch.csv` was still absent on `main` after the 01:30 and 02:30 UTC research capture slots. A later public-data probe at 06:20 UTC was healthy, but **does not establish what happened at either scheduled attempt**. The connector currently exposes GitHub Actions jobs only for known run IDs, not a full searchable list of scheduled runs. We cannot honestly attribute the absence to GitHub scheduling, provider failure, a failed unit test or push protection without the **actual attempted-run logs**.

## Two independent, strictly read-only/research improvements

**1. Capture-time forensic logs in the existing mid-session workflow.**

`.github/workflows/research_cycle_mid_session_watch.yml` keeps the same strict Sydney 11:00–15:00 capture window, 01:30/02:30 UTC primary and backup attempts, and append-only one-row-per-date BTC source. On an actual scheduled start, it now records `artifacts/mid_session_capture/run_context.json` (actual UTC/Sydney start time and GitHub run ID/attempt), a *verbatim* `capture_transcript.txt` and numeric `capture_exit.json`. These diagnostics are uploaded to the EXISTING 30-day Actions artifact even when the source check fails. Source failures remain hard failures, never transmuted into HOLD or fabricated BUY. Publication still requires verified source and correct hash chain. No new market API or workflow schedule was added.

**2. Independent nightly missing-capture detection.**

`engines/research/cycle_mid_session_capture_health.py` is a read-only verifier run from the **already scheduled 12:25 UTC nightly BTC research workflow**. That workflow checks the original mid-session SHA256-linked CSV, then emits `artifacts/research_mid_session_capture_health.json`. If the **current Sydney date** is an eligible weekday, it is AFTER the strictly frozen 15:00 local collection window, and there is no actual verified source row, the workflow prints a visible Actions warning `MISSING_AFTER_WINDOW_ENDED_DO_NOT_BACKFILL`. A Friday source row cannot count as a valid Tuesday row. A missed scheduled job is now detectable as long as the independently scheduled nightly job runs—even if the mid-session workflow never started. The late nightly monitor is **not a backfill collector** and cannot create/modify a BTC/ASX signal, prospective timestamp or ntfy notification.

If both GitHub schedules fail to trigger, neither can report automatically; a further external scheduler would be needed. No outcome can establish the true cause of the original Tuesday miss retrospectively. GitHub job logs of actual future scheduled attempts can now differentiate: start delay/out-of-window, failed upstream public data, failing regression tests, or blocked `git push origin HEAD:main` (job state and exception).

### Requirements and boundaries

- No new daily notifications or edits to the existing once-per-day ntfy, Streamlit, Cycle Trading 2.5% BUY, SELL stages, Production 5.8.2, Research 5.9 or user balances.
- No mandatory November or 2027 cash deployment date.
- No new cron, paid sources, broker access or immutable tape rewrites.
- Unit tests must verify missing-after-window, pre-close pending, weekend/pre-enrolment absence, prior-day rows not satisfying today's check, invalid timestamps, duplicate rows and no-write semantics.
- PR checks are **read-only**: they cannot retroactively populate missing Tuesday's source.
- Promotion requires both updated GitHub workflows and new tests to pass CI. The next genuinely scheduled source date, not this repair PR, must establish data availability.

**Remaining limitation:** The monitor proves only whether the CSV was visible in its checked-out repository revision at the nightly run. It does NOT prove broker execution, ntfy delivery, the state of a remote GitHub scheduler, or whether a valid intermediate capture artifact existed but failed to publish. Compare the original run-specific uploaded log to distinguish those cases.
