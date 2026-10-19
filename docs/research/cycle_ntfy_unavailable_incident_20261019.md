# Cycle Trading ntfy 19 October 2026: DATA UNAVAILABLE investigation

User's ntfy mobile screenshot of 19 October 2026 at about 12:10 Brisbane showed:
- Cycle Trading: DATA UNAVAILABLE, no BUY/SELL suggestion;
- ASX:IBIT **indicative** delayed quote A$22.44 (a separate public Yahoo lookup);
- Production/Research: no data.

The last two messages do **not independently prove both models failed**: the current ntfy renderer skips cross-model references entirely when the primary Cycle market snapshot is missing. An IBIT quote also does **not** validate BTC/USD completed UTC daily close, prior 200WMA, dated USD/AUD FX or Bitcoin halving metadata.

The Cycle/Streamlit shared module at engines/research/cycle_live_completed_utc_prices.py already uses corrected Blockchain midnight D -> UTC completed close D-1 with independent Kraken OHLC verification. This release is ALREADY in main (docs/research/shared_live_btc_completed_close_release_20261018.md). Do not falsely diagnose the screenshot by blaming a not-yet-deployed correction.

## Immediate safe investigation

Read-only staged public source diagnostic: engines/research/cycle_daily_market_diagnostic.py. Separately validates archived BTC history, Blockchain.com public market price and historic AUD FX, completed Kraken OHLC, exact existing shared source assembly, halving epoch, Cycle market math and unchanged allocation. Reports only stage/error type and public source details and NEVER submits an order, reads a portfolio, posts to ntfy, or writes notification reservation state.

The existing PR-only / manual read-only workflow, cycle_daily_notification_readonly_preflight.yml, runs nine mocked fail-closed tests, then a live public source stage diagnostic and unchanged full-market message render. It DOES NOT change the scheduled production ntfy delivery workflow, daily alert count, Cycle buying/selling rules, Portfolio, Production, Research or authoritative data sources.

Public providers can fail transiently: a successful test later is not proof that the exact error observed at 12:10 no longer exists, nor does a failed diagnostic justify inventing prices to produce HOLD/BUY/SELL. Keep the original user's screenshot as incident evidence rather than fabricating the reason.

## Next response actions

Once actual public data diagnosis identifies the failed stage, fix only the verified root cause, with tests and explicit fail-closed behaviour; show dated BTC source provenance and genuine current completed close. User requires only one ntfy per Brisbane calendar day, so DO NOT send an unscheduled test push. A successful research preflight is not itself a second notification.

Production V5.8.2 and Research V5.9 remain frozen; their no-data labels should be reported accurately as unknown/not evaluated if the main Cycle input is unavailable.
