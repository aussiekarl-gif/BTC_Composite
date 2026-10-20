# Best-effort Cycle Trading mid-session capture from EXISTING paired BTC research schedule

Pre-registered 21 October 2026, 07:41 Brisbane, before the day's mid-session capture window. **No extra GitHub cron, ntfy, trading strategy revision, portfolio or broker transaction.** Original prospective source is `data/research_forward_validation/cycle_mid_session_market_watch.csv`, whose 20 October observation is missing and must **NEVER** be backfilled.

## Actual operational evidence, not guesses

The standalone Cycle mid-session GitHub workflow `.github/workflows/research_cycle_mid_session_watch.yml` nominally starts at **01:30 and 02:30 UTC** each weekday, but did not have a published Oct20 file. We cannot prove whether those actual jobs started or why they did not publish from the missing file alone. Later public BTC/USD source probes worked.

The **different, already-running paired Kraken/Coinbase microstructure research workflow** `.github/workflows/research_btc_paired_microstructure.yml` has a *single unchanged cron* at **01:17, 07:17, 13:17 and 19:17 UTC**. Its independent saved public-source tape proves it actually ran on Oct20, for example:
- intended 00:00-UTC slot: actual `2026-10-20T05:59:30+00:00` Kraken/Coinbase capture, i.e. **16:59:30 Sydney**. Its research record is a real late public-source receipt, NOT data available at the planned 12:17 Sydney slot.
- intended 12:00-UTC slot: actual `2026-10-20T12:42:50+00:00` public capture, committed to main at ~12:42:51 UTC.

**Important:** the microstructure data rows refer to six-hour study slots; their scheduled slot is NOT proof of actual execution time. Late starts must not be used to invent a pre-15:00 ASX trade decision. Both nightly forward BTC and independent mid-session tapes remain separate from real ntfy delivery.

## Additional, opportunistic source collection only

The EXISTING paired research workflow gains a small, **optional post-publication step**, with NO new schedule:
- At its ACTUAL wall-clock execution time, independently run a Python standard-library-only UTC -> Australia/Sydney guard. Eligible only **weekdays after 20 October 2026, between 11:00 inclusive and 15:00 exclusive Sydney time**. At other times it immediately writes a timing explanation artifact, without installing dependencies, fetching BTC prices or touching the source.
- If in the real window, install the already-used BTC research requirements and invoke the EXACT existing `engines.research.cycle_mid_session_signal_tape`. This original module independently RE-CHECKS the actual public-data receipt timestamp, confirmed completed prior UTC Bitcoin close, price providers, AUD FX, halving, frozen source hash chain and one-Sydney-date append-only policy. A slow HTTP request crossing 15:00 Sydney fails closed; no fallback timestamps or proxy BUYs.
- The paired BTC book/trade independent data capture and publish finish FIRST. If the extra Cycle source dependencies/API/date checks fail, print a warning, preserve the log, do not block/rewrite the Kraken/Coinbase tapes or return a fabricated Cycle HOLD/BUY.
- If the original dedicated Cycle mid-session collector published the same Sydney date meanwhile, the optional writer compares **HEAD baseline** with the now-fetched origin/main version of the source file. Any remote change makes the optional writer STOP and preserve only its ephemeral CI artifact. Otherwise append/commit only the new Cycle CSV; if remote GitHub changes between fetch and push, standard rebase/push fails without overwriting the original source.
- Store gate, provider and any git publish outcome in independent 30-day Actions artifact `optional-cycle-mid-session-from-paired-source-schedule`.

This adds a **best-effort second acquisition path**, not independent evidence that market advice was executable or a copy of a delivered ntfy. It will increase GitHub Actions dependencies/network use on days its actual wall-clock execution lands in the window, but does NOT add another scheduled job, public data product, paid subscription or ChatGPT automation. If all jobs are delayed until after 15:00 Sydney, **there will still be NO valid observation**; do not widen the frozen window after observing the outcome.

The frozen 20 Oct A$100k ASX benchmark uses PRE-OPEN genuine BTC source data and works independently. The companion mid-session-vs-next-ASX-close timing study remains wholly unscored until a genuinely captured in-session Cycle row and future matched AUD ETF closes exist.

## Review and tests

`python -m unittest discover -s tests -p 'test_cycle_microstructure_mid_session_backup.py' -v`. The existing paired-sources PR CI runs this small no-network module/CI safety suite *in addition to* all four established Kraken/Coinbase research tests and two genuine read-only public source probes. It cannot run the prospective-source collector on the PR branch or after ASX hours. No past BTC/ASX records are rewritten.

Use a **main scheduled run** and resulting timestamped microstructure+mid-session tape to establish whether the fallback ever actually succeeded. Do not claim it has recorded a new mid-session signal until the actual file exists on main and its hash chain validates.
