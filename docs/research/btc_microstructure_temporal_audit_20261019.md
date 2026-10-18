# BTC Intelligence: cross-venue BTC market-data comparison

## First real samples (18 Oct 2026 UTC)

Kraken captured at 23:30:53 UTC: XBTUSD resting-book midpoint USD 82,077.85; displayed resting bids 49.68% of 25bp-depth dollars.

Coinbase sampled at 23:38:20 UTC: last 100 BTC-USD trades cover only 18.961 seconds; inferred buyer-initiated sample USD share 11.63%, VWAP USD 81,989.47. An earlier 23:37:24 Coinbase probe had 87.83% buyer-initiated share across 21.596 seconds, illustrating instability of sparse samples.

**These Coinbase and Kraken snapshots were over seven minutes apart. They are NOT co-temporal executable quotes and must NOT be used to infer arbitrage, two independent AI consensus votes, six-hour volume or a trade decision.**

## Explicit source audit

A deterministic read-only module at engines/research/btc_crossvenue_timestamp_audit.py reads the original SHA256-verified records independently and compares only **identical six-hour UTC slots**, and only if:

- Both captures exist and are no more than 12 hours old as of evaluation.
- Actual HTTP response receipts are at most five minutes apart.
- The Kraken 25bp-band book coverage is complete.
- Coinbase sample is labeled bounded and both archive hashes are verified.
- Timestamps, quantities and reference prices are valid and finite.
- A cross-venue price difference exceeding 2% triggers an investigation status, never a trade.

The output is a read-only diagnostic, never a voting factor; it reports zero independent agent votes, no executable order size and no continuous executed-volume coverage.

No changes to Production or Research trading strategies, Cycle UI, IBIT quotes, Google Sheets, portfolios, schedules, daily ntfy, broker accounts or prior archived records.

Verification: 10 mocked offline tests and no-write CI on GitHub PR. Prospective return benefits remain untested; full flow intervals and more observations are needed.
