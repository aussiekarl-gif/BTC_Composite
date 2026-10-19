# 19 October 2026 Cycle Trading daily ntfy DATA UNAVAILABLE: confirmed provider gap and bounded remedy

## Incident and independent reproduction
The user's 19 October Brisbane 12:10 mobile ntfy screenshot displayed **DATA UNAVAILABLE**, Production/Research 'no data', while a separate indicative ASX:IBIT AUD quote was present.

GitHub read-only live probe [run 39193163738](https://github.com/aussiekarl-gif/BTC_Composite/actions/runs/39193163738), recorded 19 October 2026 at 03:08 UTC, reproduced the failure without sending ntfy:
- Historical BlockHorizon BTC archive: available.
- Blockchain.com market-price chart last raw midnight point 2026-10-15 UTC, which represents the previous day 2026-10-14's completed BTC close under the already-implemented D→D-1 interpretation.
- Dated AUD FX last 2026-10-16 UTC, available and unchanged.
- Public Kraken spot XBTUSD independently completed daily OHLC through **2026-10-18**, the required previous completed UTC day.
- Shared Cycle source failed with: **Delayed public reference exceeds short safe Kraken bridge**.
- Between the last validated Blockchain close Oct14 and required Kraken close Oct18 are FOUR consecutive UTC closing dates, but the generic research bridge allowed only three.

No evidence Production V5.8.2 or Research V5.9 were independently broken: the daily notification's market-gated cross-model comparison never runs if primary Cycle market is unavailable.

## Narrow patch, no change in strategy parameters

The bridge function for the generic forward-tape research keeps DEFAULT **3 days**. Only the shared LIVE Cycle Streamlit/ntfy source passes a separately explicit **7-day maximum**. It additionally rejects a Blockchain last-verified close older than **7 calendar days**, demands at least THREE recently overlapping same-date Blockchain and Kraken completed closes with <=1% maximum deviation, enforces the original archive overlap, requires Kraken to have **every consecutive missing completed day** through yesterday (not today's live candle), forbids overwriting prior archives, and retains dated AUD FX and verified halving epoch requirements.

This is a controlled provider outage tolerance; it is NOT a different Cycle Trading allocation strategy, not buying on stale BTC data, not using the ASX indicative quote as an executable order and not automatic broker or portfolio access.

The change can alter the availability of the BTC completed close and therefore the resulting market WATCH. It is not safe to infer from today's screenshot that the resultant signal would be HOLD. Verify it with live read-only GitHub acceptance before merge and preserve one daily ntfy cadence: **no second ntfy sent today**.

## Tests and rollback
- Existing dedicated Cycle source, Kraken completed OHLC bridge and one-daily-ntfy tests must remain green.
- New checks require a genuine four-day source gap with independently completed Kraken OHLC to pass and bad/old sources, missing day, near-overlap conflict and forbidden future close to fail.
- Existing read-only daily preflight runs on changes to this source code so a REAL live provider test proves rendered message date, risk allocation and 200WMA match the existing shared Cycle engine. No ntfy credentials or sending workflow are used during PR tests.
- Legacy standalone forward research bridge remains limited to three days by default and its original tests must remain unchanged.
- GitHub revert of THIS PR is the rollback. Do not revert the already-correct UTC D-1 Blockchain label or rewrite immutable forward records.
