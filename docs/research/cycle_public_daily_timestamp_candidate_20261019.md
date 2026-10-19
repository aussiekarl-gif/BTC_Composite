# Blockchain.com BTC completed-daily-close timestamp correction — shadow release candidate

19 October 2026. **Strictly research-only; no live source, portfolio, ntfy or model change.**

## Root cause

The independently run October 18 audit in docs/research/btc_close_timestamp_alignment_evidence_20261018.md showed that Blockchain.com chart point epoch at UTC midnight D matches the close of the preceding completed UTC day D−1, not the daily price close for calendar date D itself.

31 archive-overlapping dates showed 6.29465% worst raw same-labelled difference, but <0.053% worst after D−1 interpretation, corroborated independently by same-day Kraken completed spot daily closes. One especially clear example is 21 September 2026: BlockHorizon 86,586.52 USD, Kraken 86,593.80 USD, raw Blockchain.com chart label 81,136.20 USD. This is a date interpretation defect, not demonstrated current BTC-price error. The current shared live parser continues to label the epoch date as D; no live rule or stream has been revised in this PR.

## Safely testable candidate

- New pure research module engines/research/cycle_public_daily_timestamp_candidate.py parses the RAW public payload. It accepts only genuine integer UTC MIDNIGHT chart epochs, positive finite prices, monotonic unique data, and a time-zone-aware actual capture receipt; a chart point at midnight D becomes observed completed-close date D−1.
- It demands at least 3 recent corrected chart/unchanged BlockHorizon historical overlaps, max 2% disagreement. It also demands at least 3 independent recently completed Kraken spot daily closes overlapping the corrected chart, max 1% disagreement; the old generic 6%/15% archive thresholds alone are not acceptable as proof of a fixed source-date candidate.
- Kraken may append only a strictly contiguous gap of 1 to 3 newly completed days through yesterday using existing verified bridge. NO missing candles are interpolated, backfilled or taken from today's unfinished bar.
- Return an in-memory dated BTC/USD candidate history with original archived dates intact, source overlap statistics and appended dates, marked NOT APPROVED FOR LIVE USE. No BUY/SELL, Streamlit or ntfy import. The existing shared Cycle allocation module and historical master remain untouched.

## Verification scope

17 new synthetic tests plus original source disagreement and Kraken bridge regression tests run on PR and on merge. These are deterministic correctness tests, NOT evidence that a different market-price input produces more profit.

Before ANY approval to use corrected data in Streamlit or one daily ntfy:
1. Verify raw, live Blockchain.com provider epoch shape and last fully completed UTC date. Preserve one versioned exact real public response sample.
2. Confirm archive/Kraken 2026 real overlap and newest daily close on original dated sources, including provider outages and weekends; no future data contamination.
3. Compare identical existing Cycle Trading market allocation code before/after the new date interpretation at historical threshold-crossing fixtures and genuine current source data; output BUY/HOLD/SELL differences, not only HOLD parity.
4. Run unchanged live BTC and AUD FX/IBIT tests, broker quote safeguards and portfolio cooldown regressions.
5. Require a separate user-reviewed release plan, one rollback path, same Streamlit and single daily ntfy version, and frozen original forward source records with no rewriting.

The candidate has **zero ability to execute trades or edit any live model**.
