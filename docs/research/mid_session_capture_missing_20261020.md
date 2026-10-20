# 20 October 2026: mid-session BTC research tape missing — visibility hardening

At approximately 16:08 Brisbane / 17:08 Sydney on Tuesday 20 October, the project main branch did **NOT** yet contain `data/research_forward_validation/cycle_mid_session_market_watch.csv`. The workflow had been configured for 01:30 and 02:30 UTC Tuesday, within the strict 11:00–15:00 Sydney research capture window. The original nightly BTC market tape had three rows through Oct18; prospective ASX:IBIT AUD completed daily-candle tape held Oct19 only.

**Do NOT infer that the collector definitely ran or definitely failed its provider** from the absence of the final GitHub CSV; both a missed workflow schedule, upstream source rejection, or publication/push failure are possible. At 17:08 Sydney, the permitted Oct20 capture window was already over. Do not retroactively create the first Tuesday mid-session observation, even using a valid current price later in the afternoon.

This update adds observable evidence to the existing scheduled/read-only workflow:
- on each actual scheduled or manually dispatched run, after the capture stage (even if earlier steps failed but the job is not cancelled), verify whether **the specific current Sydney date** has a real SHA256-linked mid-session row. Print a visible GitHub Actions warning if missing; existing older records do not count as today's success.
- run the unchanged passive `--probe-only` source bundle check after source-capture attempts, reporting public BTC, Kraken, previous completed UTC date, dated AUD FX and verified halving availability. It never writes a purported mid-session record, portfolio data, broker order, ntfy or notification reservation.
- the existing PR smoke workflow already performs a real provider `--probe-only` check when the workflow file changes, which supplies an independent live as-of-now reproduction if the private GitHub scheduled-run logs are not accessible through a given connector.
- no backfill, revised trading rule, new schedule or added market data subscription. One daily ntfy remains separate and unchanged.

If future scheduled runs still produce no mid-session record despite valid public source probes, inspect GitHub Actions schedule enablement and repository `contents: write` permission / `git push origin HEAD:main` failures via exact run job logs. Do not claim any specific root cause until supported by those actual logs. If the collector executes outside its restricted window, treat the day as missing rather than widening the window after observing data.
