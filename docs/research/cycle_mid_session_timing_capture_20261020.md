# Cycle Trading within-ASX-session timing research — initiated 20 October 2026

## What the current forward tape CANNOT tell us

The unchanged official Cycle Trading daily ntfy attempts delivery at 00:00, 00:15 and 00:35 UTC (10:00/10:15/10:35 Brisbane; during the ASX Sydney trading session). The research BTC Cycle forward tape runs at 12:25 UTC (22:25 Brisbane), after Sydney's ASX market closes. It therefore cannot by itself reproduce the information available at the time of the daily notification or fairly grade a same-session decision versus a next-session decision.

An ASX:IBIT **Yahoo daily close is not known when the notification arrives and is NOT a guaranteed broker order fill**. Even a same-date hypothetical closing-price return comparison is descriptive only and requires a genuinely pre-close signal capture. The delivered notification itself cannot be verified without its authenticated delivery payload and time; a scheduled job's claimed execution time is not evidence of ntfy delivery.

## Separate, prospective market-research source

Module: `engines/research/cycle_mid_session_signal_tape.py`
Independent append-only evidence: `data/research_forward_validation/cycle_mid_session_market_watch.csv`
Dedicated GitHub Actions: `.github/workflows/research_cycle_mid_session_watch.yml`

- Begins **Tuesday, 20 October 2026, Sydney**, before the first eligible forward ASX matched benchmark session.
- ONE weekday job at **01:30 UTC** (Brisbane 11:30 year-round, Sydney 12:30 daylight saving / 11:30 winter), but date and data quality are determined by the **actual successful public source receipt**, never by the intended cron schedule. If GitHub is early, delayed beyond 15:00 Sydney, or unable to reach a source, it fails closed without a snapshot.
- Valid local capture between **11:00 and 15:00 Australia/Sydney**, only on eligible weekdays; weekends/holidays cannot be treated as confirmed trading dates. Holidays will have no matched ASX daily close outcome; we do not infer one.
- Exact shared live Streamlit/daily ntfy public BTC sources: historical BlockHorizon, date-corrected public Blockchain.com (midnight D -> preceding UTC completed D-1 close), verified Kraken daily OHLC bridge, prior dated AUD FX and verified halving epoch.
- Exact unchanged `calculate_allocation_signal` at DEFAULT buy style; store market WATCH, BUY percentage of remaining AUD cash, SELL percentage of remaining BTC/IBIT units, verified BTC completed close date, prior 200WMA, prior FX date, cross-source difference and the market rule code SHA256. No user brokerage data is read.
- Strictly require **yesterday's completed UTC BTC daily close**, Kraken/Blockchain overlap <=1%, archived source preservation, valid prior FX, valid halving, finite inputs.
- One Sydney research observation/date; first captured value wins. Every row is SHA256-chain-linked, verified on read and rejected if re-ordered, modified, backdated or mislabeled as an executable trade/verified notification. No historical Oct 19 price or notification backfill.
- No output to daily ntfy, no Streamlit sidebar addition, no new ETF alerts, no daily notifications, no broker orders or portfolio/Google Sheets writes. The original official BTC research tape and its 20 October frozen original benchmark remain unchanged.

## Why this is not a new independent AI vote

Both nightly and mid-session market WATCH calculations use the SAME underlying Cycle Trading model, not independent evidence. Their difference is **when the public data was actually checked**, and occasional source revisions; do not count both as confirmation.

The mid-session runner is also a **research proxy**, not an authenticated copy of a delivered ntfy message. GitHub timing and public provider data at fetch time can diverge from a delayed ntfy message or private Streamlit portfolio state. Never assume BUY/HOLD/SELL became executable just because a research snapshot exists.

## Next gated experiment

After future source records are actually collected:
1. Retain the unchanged Oct 20 original benchmark, which admits pre-ASX-open observed Cycle signals only.
2. Build a DISTINCT, predeclared mid-session execution-timing comparison using the new source capture. Match each eligible Sydney day's *actual* post-close indicative ASX:IBIT candle, and the earliest actual following Sydney session close when available.
3. Keep the same A$100k cash, 25bps one-way spread, A$3 brokerage, whole ETF units and missing-source exclusions. Do not reassign observations in hindsight, predict intraday bid/ask, or pretend the daily close was available for mid-session execution.
4. Report timing/capture delay, ETF exposure, missing samples and assumptions separately. Never declare risk-adjusted live alpha or change any live trading rule from these paper-only prices.

## Testing and use

`python -m unittest discover -s tests -p 'test_cycle_mid_session_signal_tape.py' -v`

The workflow also runs existing Cycle allocation and shared completed UTC close regression suites. In PRs it performs no live source requests; only scheduled or explicitly manually dispatched main runs capture. A new scheduled weekday research job adds small GitHub Actions usage, but adds no paid provider subscription or ChatGPT prompt expense. It should be disabled if data evidence remains too sparse to justify continued collection.
