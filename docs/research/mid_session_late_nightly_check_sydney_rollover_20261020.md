# Late-start nightly BTC mid-session health audit — Sydney date correctness

**20 October 2026: research-only CI hardening.** The independent nightly BTC Cycle source audit originally looked only for a prospective market signal on the **Sydney calendar day when the check happened to execute**. Its configured nightly start is 12:25 UTC / 23:25 Sydney (during daylight saving), leaving a narrow timing bug: if the GitHub job starts late, or its earlier BTC source validation takes longer than expected, the health check can execute shortly **after midnight Sydney on Wednesday 21 October**, look for a Wednesday capture that was never supposed to happen yet, and fail to detect a missing Tuesday 20 October observation.

PR #186 correctly provided an independent watcher and source-capture log artifacts, but did not handle delayed-night UTC/local-date rollover. The watcher now reports **both**:
- existing `audited_sydney_date` and `status` fields describing current local day (unchanged backward compatibility);
- `latest_completed_sydney_weekday_checked` and `latest_completed_weekday_status`, which refer to the most recent eligible Australia/Sydney weekday whose **15:00 local research capture window has actually ended**.

A Wednesday 00:30 Sydney audit must check **Tuesday**, Saturday 01:00 checks **Friday**, and Monday 08:00 still checks **Friday**. At 23:25 Sydney, it checks that **same weekday**. All previous immutable tape SHA256 source checks still run first. On a missing eligible complete weekday, print GitHub Actions `::warning::` identifying that exact target. No retrospective capture/price, failed provider reinterpretation, model/signal change or assumed broker fill is ever created.

The scheduled GitHub Actions job is unchanged; no extra ntfy, new cron, broker/portfolio writes or paid provider requests. Tests include 8 new DST/weekend/midnight cases plus the 10 existing watcher checks and pre-existing provider/Cycle regressions. A missing mid-session **20 October** record remains missing; the diagnostic code cannot establish whether the original collector ran or why it failed.

## Limits

This audit is a **read-only repository checkout** view. A valid source artifact not yet committed cannot be counted as safely published, and a missing GitHub schedule cannot be diagnosed directly from the absence of a row. Inspect original 11:30 / 12:30 Brisbane Actions logs and run-ID artifact evidence if available. Consecutive unavailable weekdays should be preserved as individually missing; the latest-completed-weekday monitor inspects only the most recent day, while the source tape continues to expose the full chronological absence.
