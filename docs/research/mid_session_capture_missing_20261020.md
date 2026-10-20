# 20 October 2026: mid-session BTC research tape missing — visibility hardening

At approximately 16:08 Brisbane / 17:08 Sydney on Tuesday 20 October, the project main branch did **NOT** yet contain `data/research_forward_validation/cycle_mid_session_market_watch.csv`. The workflow had been configured for 01:30 and 02:30 UTC Tuesday, within the strict 11:00–15:00 Sydney research capture window. The original nightly BTC market tape had three rows through Oct18; prospective ASX:IBIT AUD completed daily-candle tape held Oct19 only.

**Do NOT infer that the collector definitely ran or definitely failed its provider** from the absence of the final GitHub CSV; both a missed workflow schedule, upstream source rejection, or publication/push failure are possible. At 17:08 Sydney, the permitted Oct20 capture window was already over. Do not retroactively create the first Tuesday mid-session observation, even using a valid current price later in the afternoon.

This update adds observable evidence to the existing scheduled/read-only workflow:
- on each actual scheduled or manually dispatched run, after the capture stage (even if earlier steps failed but the job is not cancelled), verify whether **the specific current Sydney date** has a real SHA256-linked mid-session row. Print a visible GitHub Actions warning if missing; existing older records do not count as today's success.
- run the unchanged passive `--probe-only` source bundle check after source-capture attempts, reporting public BTC, Kraken, previous completed UTC date, dated AUD FX and verified halving availability. It never writes a purported mid-session record, portfolio data, broker order, ntfy or notification reservation.
- the existing PR smoke workflow already performs a real provider `--probe-only` check when the workflow file changes, which supplies an independent live as-of-now reproduction if the private GitHub scheduled-run logs are not accessible through a given connector.
- no backfill, revised trading rule, new schedule or added market data subscription. One daily ntfy remains separate and unchanged.

If future scheduled runs still produce no mid-session record despite valid public source probes, inspect GitHub Actions schedule enablement and repository `contents: write` permission / `git push origin HEAD:main` failures via exact run job logs. Do not claim any specific root cause until supported by those actual logs. If the collector executes outside its restricted window, treat the day as missing rather than widening the window after observing data.

## Live read-only verification on 20 October after the missed collection window

[PR #184 GitHub CI run 39379786756](https://github.com/aussiekarl-gif/BTC_Composite/actions/runs/39379786756) passed 51 original offline tests (24 mid-session, 10 Cycle, 17 verified BTC-source tests). At **2026-10-20T06:20:37Z** (17:20 Sydney / 16:20 Brisbane), the passive no-send/no-write provider probe independently returned:
- most recent verified completed UTC BTC close date **2026-10-19**, BTC/USD **81,843.70**;
- prior 200WMA **66,842.39** USD; independent Kraken/Blockchain maximum same-date discrepancy **0.0181%**;
- historical AUD FX on **2026-10-16**; original shared Cycle market WATCH **HOLD**, BUY/SELL **0%/0%**;
- unchanged Cycle market model SHA **0143723687ff676300734a4bcc9887cdc095c74b70b958852d9448412b7f08a7**;
- `mid_session_snapshot_recorded=false`, `ntfy_sent=0`, `orders_placed=0` and existing immutable tape still 0 records.

Therefore the CURRENT provider chain is healthy, but that does **not establish the provider chain's state at the 01:30 or 02:30 UTC scheduled capture times** or whether those GitHub jobs ran/pushed. Original capture is missing and must remain missing for October 20. Future scheduled runs have visible warnings and passive source status even on source-capture failures, enabling a more precise root-cause determination.
