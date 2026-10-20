# BTC mid-session signal: nightly observation must survive independent BTC test failures

20 October 2026, before the 12:25 UTC / 23:25 Sydney nightly forward run.

Following PR #186 (new independent watcher) and PR #187 (Sydney midnight/date rollover fix), inspection of the existing `.github/workflows/research_forward_cycle_tape.yml` revealed that the monitoring step still had a hidden dependency: it was guarded by `steps.capture_validation.outcome == 'success'`. A failed BTC market/data regression would therefore *skip the supposedly independent missing-source audit*, and the late combined artifact could be absent.

## Research-only change

Move the read-only `python -m engines.research.cycle_mid_session_capture_health` immediately after installation of existing research dependencies and **before the BTC model tests, live nightly capture, ASX upload and immutable publishing**.

The independent audit step requires only `!cancelled()`, an invocation on `main`, and a non-PR event. It no longer depends on BTC capture tests, public market feed success or the later `steps.readiness`. Its JSON is retained in a **separate 30-day GitHub Actions artifact** `cycle-independent-mid-session-capture-health`, so a later test error cannot hide the monitoring result. Missing actual completed Sydney weekdays remain missing; no data repair/backfill is performed.

This step reads existing SHA256-linked mid-session source tape with the PR #187 completed-Sydney-weekday time semantics. As before, even this watcher cannot run if the **entire nightly workflow is not scheduled**, repository checkout fails, the job is cancelled, or Python dependencies cannot install. It proves availability/absence of committed source data at checkout time, not the root cause of a missed scheduled mid-session run. The 20 October missing signal is **not recovered**.

The actual nightly source **publication** remains STRICTLY GATED on the unchanged existing BTC market validation and `readiness` success. The daily ntfy is completely separate and unchanged. No new schedule or market model, Streamlit, portfolio/broker, paid data, Research 5.9, Production 5.8.2, 2.5% BUY, seven-day cooldown or SELL setting is changed.

Five source-level tests protect these workflow invariants in `tests/test_cycle_independent_nightly_workflow.py`, alongside all prior BTC/ASX/capture tests. No live signal or money-performance improvement is claimed.
