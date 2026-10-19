# Cycle Trading live-feed acceptance and code-only rollback — 19 October 2026

## Already-live correction and incident context

The Blockchain.com midnight label D => completed UTC close D-1 correction has **already been deployed** in the shared Streamlit and daily ntfy code before this PR. A subsequent Oct19 ntfy DATA UNAVAILABLE was a *different* issue: the Blockchain chart was last available as completed Oct14 but verified completed Kraken OHLC included Oct18, requiring FOUR gap days while the original research bridge permitted only THREE. PR #173 already deployed a conservative live-only maximum seven-day gap, retaining the standalone research bridge's three-day default, all original data hash chains and unchanged BUY/SELL allocation parameters.

The read-only post-#173 public acceptance [GitHub run 39193543454](https://github.com/aussiekarl-gif/BTC_Composite/actions/runs/39193543454) validated last completed Oct18 BTC/USD close **82,001.70 USD**, previous 200-week MA **66,718.32 USD**, default market WATCH **HOLD**, BUY **0%**, SELL **0%**, and a separately rendered daily message with identical source/market values. No notification was sent.

## What this PR implements

An independently rerunnable, no-send acceptance harness `engines/research/cycle_live_feed_release_acceptance.py` and 12 offline regression/negative tests `tests/test_cycle_live_feed_release_acceptance.py`, integrated into the EXISTING manual/PR-only workflow `.github/workflows/cycle_daily_notification_readonly_preflight.yml`, with JSON artifact `artifacts/cycle_live_feed_acceptance_rollback.json`. There is NO new daily schedule, secrets, ntfy, portfolio access, broker connection or Production / Research model update.

### Positive actual-provider acceptance

1. Retrieve original BlockHorizon archive, raw public Blockchain BTC/USD chart, prior-dated AUD FX, completed public Kraken XBTUSD OHLC and verified chain halving metadata from exactly the same modules used by Streamlit and the single daily ntfy.
2. Verify Blockchain raw UTC-midnight D->D-1 mapping, original archive historical price preservation, genuine same-date independent Kraken overlap, contiguous completed missing days and the exact completed previous UTC day. A source fail means NO acceptance, never a synthetic BUY/HOLD/SELL.
3. Build the exact shared BTC/USD 200WMA / AUD FX / halving market dictionary and evaluate unchanged DEFAULT Cycle Trading market percentages.
4. Render `daily_message` with that same validated market snapshot and current indicative ASX quote, **without POST** or ntfy reservation. Compare WATCH, BUY and SELL market percentages, previous completed BTC close/date and prior 200WMA. Perform wiring assertions against Streamlit's true source loaders, market builder, feed verification and user-ledger decision gate.
5. Output completed-date references, overlap maximum discrepancy, sources SHA-256 fingerprints and no-write attestation as an optional downloadable Actions artifact.

The GitHub preflight **already** has a separate real double-fetch check `cycle_daily_notification_readonly_preflight.py`, which makes the notification independently re-fetch the same public provider data. This new harness supplements rather than replaces that check.

### Negative and code-only rollback rehearsal

- Temporarily REHEARSE changing the shared *live-only* maximum Kraken gap 7 -> original 3 **inside the current Python process**, then restore it unconditionally. The old cap MUST reject a genuinely four-day delay; if the delay is <=3, the original and new source prices must be identical. The correct Blockchain D-1 mapping is **never** reverted.
- With a missing interior required Kraken daily close, both current and rollback policies must refuse the incomplete price series. Public/archival inputs are fingerprinted before/after to detect accidental mutation.
- Synthetic tests verify valid four-day rescue, missing day, stale chart, conflicting independent exchange price, missing yesterday, unverifiable halving, missing FX, provider immutability, default BUY market parity and no broker/portfolio/ntfy controls.
- This is **not** an actual rollback of running Streamlit; if operational rollback ever becomes necessary, stage a separate code-only change reverting ONLY the gap allowance from 7 to 3. That restores DATA UNAVAILABLE when Blockchain delays exceed three days. Do NOT revert the corrected timestamp interpretation, original historical source files, ntfy daily reservation state, frozen model parameters or previously published provider tapes. Require read-only preflight pass before a separate approved rollback is merged.

### What a pass does NOT prove

A green test cannot guarantee all future API availability. Checks verify **shared default market WATCH and percentages**, not the user-selected alternative Streamlit buy style, broker-confirmed holdings, currently executable ASX:IBIT bid/ask, portfolio-driven whole ETF units, SMSF tax amounts or full browser-rendered UI. The user must still independently verify broker transactions. No historical Cycle Trading backtest returns are promoted.

### Acceptance conditions for this PR

PR may be merged only if:
- all 51 offline regressions pass: 12 release/rollback, 10 original market BUY/HOLD/SELL parity, 17 shared completed-close source, and 12 ntfy quote/schedule safety tests;
- real public daily preflight succeeds and reports latest verified completed BTC date, actual BTC price and 200WMA, default WATCH/pct parity;
- new rollback rehearsal reports correct previous 3-day behaviour without changing live source module or any provider records;
- original no-send workflow remains isolated from `secrets.NTFY_TOPIC`, scheduled notification code, portfolio and market master; and
- the actual changed-files list contains ONLY the research harness/test/doc and the existing read-only preflight workflow.

No new ntfy message should be sent today or as part of this PR.
