# BTC Cycle mid-session data acquisition: GitHub delay hedge + capture-before-CI — 22 Oct 2026

## Observed problem

The original 11:30 / 12:30 Brisbane weekday research captures are **scheduled GitHub times, not guarantees**. The actual 21 Oct GitHub workflow ran at ~17:19 Sydney, well after the verified 15:00 Sydney cut-off; the script correctly failed closed. The nightly ASX forward collector likewise sometimes started at 04:24 the **following** Sydney calendar date, losing that trading day's close. Neither missing record can be reconstructed as valid prospective evidence.

The previously merged existing Kraken/Coinbase fallback and after-close ASX fallback mitigate some gaps but cannot overcome arbitrary GitHub queue delays. We retain the strict rules, SHA256 tapes and no-overwrite/no-backfill constraints.

## Narrow improvements to existing dedicated Cycle workflow

File: `.github/workflows/research_cycle_mid_session_watch.yml`. **No new workflow, no ntfy, no trades.**

1. **One earlier cron hedge on the SAME existing workflow**, `15 23 * * 0-4`. Sunday–Thursday at 23:15 UTC is the **next Sydney weekday**, at **10:15 AM AEDT** (09:15 AEST). This is *deliberately before* the eligible 11:00–15:00 Sydney capture window. On-time GitHub runs MUST return a success/skip diagnostic without installing market dependencies, fetching public BTC prices or producing a fake row. If GitHub starts one to four hours late, the actual capture may land inside the permitted window. Original weekday 01:30/02:30 UTC slots remain. This increases total scheduled attempts from **two to three per Sydney weekday**, using the existing job/concurrency group. It adds GitHub Actions usage but no notifications or market data subscriptions.
2. **Guard first, with Python standard library only**: `python -m engines.research.cycle_microstructure_mid_session_backup --is-window`, which explicitly checks actual Australia/Sydney weekday/local wall-clock. Record actual time result in a diagnostic artifact. Never infer eligibility from the UTC cron definition.
3. If the actual time is eligible, install only `numpy`, `pandas` and `requests` for the original verified shared BTC/FX/halving source chain, then **capture immediately** with the unchanged `cycle_mid_session_signal_tape`. The original capture module rechecks the real UTC *after* public feed receipt, verifies completed BTC day + prior 200WMA + prior FX and independently cross-verified Kraken/Blockchain sources, enforces source-row code hash and refuses cross-window records, duplicates or backfill.
4. **Only AFTER a successful candidate capture**, install the full old regression requirements and execute all the same original model/allocation/source/notification-parity test suites. Maintain a new explicit `full_validation` step ID. The ONLY publishing step requires **both** `steps.prospective_capture.outcome == 'success'` **and** `steps.full_validation.outcome == 'success'` together with `success()`, existing tape self-check and GitHub SHA-chain-safe commit/rebase/push. Capturing first does NOT mean publishing before tests; if any validation fails, the candidate row stays ephemeral in the existing CI artifact, not in `main`.
5. **PR/push checks remain before any market capture**: full original unit suites, plus quick minimal-dependencies import smoke, and the original *read-only* real public BTC provider probe. PRs never write research tapes or send ntfy. Missing/too-early/too-late scheduled captures upload a timestamped skip artifact. Original one valid row per Sydney day and irreversible provider-date validation are unchanged.

## Safety and limitations

- No Production 5.8.2, Research 5.9, Streamlit Cycle 2.5%-remaining-cash BUY/SELL rule, executed 7-day cooldown, actual portfolio/Google Sheets, real ASX order or single daily ntfy changes.
- No backdating Oct20 or Oct21 source rows; no assumption early/late scheduled clocks are market facts. Need a **genuine new 22 Oct or later mid-session** record before scoring any prospective in-session vs ASX-close comparison.
- The early additional slot *could* improve yield under delayed GitHub jobs, but cannot fix GitHub queue lateness altogether. Only an independently dependable scheduler would address that fundamentally, requiring explicitly configured external infrastructure and secure GitHub authorisation.
- 9 new offline workflow invariants test early cron/date correctness, actual-time gate first, minimal source dependencies, original full tests before publication, immutable first source, no ntfy/portfolio, and strict self-check/dual-success gate. The PR CI must pass with existing public-source probe before merging.

### Evaluation

Measure the next actual *scheduled* run outcomes from their GitHub Actions logs plus signed source tapes. Success criterion is NOT fewer red runs; it is **a genuine, source-validated market snapshot with receipt timestamp inside Sydney 11:00–15:00**, published only after full regressions pass. If future runs remain delayed beyond 15:00 despite the hedge, stop further cron tweaking and consider an independently operated scheduling service rather than weakening the data-integrity window.
