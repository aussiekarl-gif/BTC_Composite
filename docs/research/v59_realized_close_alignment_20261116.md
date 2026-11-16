# Realized-price forward ratio source-alignment audit — 16 November 2026

**RESEARCH ONLY — NOT A BUY/SELL SIGNAL. No Production, live Research V5.9, Cycle Trading, portfolio, Sheets, Stake or ntfy changes.**

## New data-integrity finding

The first-captured forward tape stored Explore21's ordinary realized price and its own `btc_close_usd`, but the ratio was calculated using the separate Blockchain.com `market-price` series. These are not the same price basis:

- Blockchain.com's official Market Price chart describes its daily value as the **average USD market price across major Bitcoin exchanges**, not an OHLC daily close: https://www.blockchain.com/explorer/docs
- Explore21 describes its Bitcoin price CSV as the **daily UTC close** and publishes `btc_close_usd` beside realized price in the same dated CSV row: https://charts.explore21.com/data and https://charts.explore21.com/bitcoin-realized-price

The prior forward ratio therefore mixed a daily-average spot proxy with a daily-close on-chain reference. This is not evidence of a realized-price disagreement between independent on-chain providers; it is a spot-price-basis mismatch. The historical tape is immutable and must not be rewritten.

### First-captured same-date comparison

The figures below are from the first-captured tape rows. “Blockchain average” is the BTC/USD price proxy used by the existing V5.9 snapshot; “Explore21 close” is the provider's own same-date close. Ratios are spot / Explore21 ordinary realized price.

| Provider observation date | Blockchain average (USD) | Explore21 close (USD) | Average above close | Old mixed-basis ratio | Same-provider close ratio |
|---|---:|---:|---:|---:|---:|
| 12 Nov 2026 | 73,930.74 | 71,374.07 | 3.58% | 1.3736 | 1.3261 |
| 13 Nov 2026 | 71,365.77 | 68,225.90 | 4.60% | 1.3275 | 1.2691 |
| 14 Nov 2026 | 68,232.31 | 64,113.69 | 6.42% | 1.2701 | 1.1934 |

The difference is large enough to flip the 1.25 threshold on 14 Nov: the mixed-basis ratio was 1.2701, while the same-provider close ratio was 1.1934. None of the 12–14 Nov observations passes 1.10 under either calculation. This is a price-basis classification error, not a realized-price alpha result.

## Independent realized-price parity

The earlier same-UTC-date public check remains reassuring: on 11 Nov, Explore21 showed ordinary realized price US$53,874, versus Glassnode US$53,930 and Axel Adler US$53,879. Differences were approximately 0.10% and 0.01%. The BGeometrics free endpoint was seven days delayed on 12 Nov and was correctly rejected; there is no comparably dated BGeometrics forward observation to substitute.

Explore21's public page now reports 15 Nov 2026 realized price US$53,671 and BTC close US$65,312 (ratio about 1.217). That public page value is **not yet a first-captured tape observation** and is not included in prospective scoring. Its page also labels the 30 Jun 2026 low (US$58,526) provisional and about 10% above realized price. This does not establish that BTC must revisit US$54k; realized price is a changing aggregate last-movement cost basis, not a fixed price target.

## Forward evidence status

The isolated `research/v59-forward-tape` branch contains four first-captured daily observations for 11–14 Nov. The latest is signal date 14 Nov, first captured 15 Nov 07:58 UTC. No exact 7-, 28- or 84-day outcomes have matured and there are zero complete prospective Sunday-to-Monday paper pairs. The 15 Nov Explore21 public row was available by this review, but no 15 Nov immutable capture had yet been recorded. A delayed capture may still record it prospectively; it must not be backfilled from revised history.

The realized-price source itself was date-stamped and captured after its observation date. The mismatch was in the ratio's spot-price basis, not a future-dated provider observation.

## Research-only correction

The isolated code change:

1. Calculates the realized-price ratio from Explore21's own BTC close in the same CSV row/date as ordinary realized price.
2. Keeps the Blockchain.com daily-average ratio and its percentage gap as diagnostics only.
3. Requires an exact provider-date / signal-date match and a provider BTC close; a stale date or BGeometrics value without a matching close fails closed.
4. Adds a ratio-method version. Existing immutable rows are preserved but legacy mixed-basis ratios are excluded from the realized-price paper gate; only new date-matched records can qualify.

This does not change the V5.9 risk input, historical horse-race results, any live recommendation, or a buy/sell signal. The daily BTC/AUD and Monday purchase references remain indicative daily-average proxies, not executable ASX:IBIT fills. All historical WMA/cycle results therefore retain their price-proxy and no-historical-IBIT-fill limitations.

## Reproduction

- Forward tape: `data/research_v59_forward/daily_observations.jsonl` on the isolated `research/v59-forward-tape` branch.
- Source pair: `engines/research/v59_realized_forward_reference.py`.
- Gate and scorecard: `engines/research/v59_forward_dca_tape.py`.
- Tests: `tests/test_v59_realized_forward_reference.py`.

**No historic tape row is rewritten. No live or production path is modified.**


## Post-review durable capture — 16 November 2026

The post-merge research-only push run [43815032047](https://github.com/aussiekarl-gif/BTC_Composite/actions/runs/43815032047) appended the 15 Nov UTC observation to the isolated forward tape at 2026-11-16 06:12:13 UTC. Provider observation date matched signal date (15 Nov); Explore21 ordinary realized price was US$53,671.2252 and its own BTC close was US$65,312.48, giving the date-matched ratio 1.21690. The Blockchain.com daily-average proxy was US$64,119.34, giving 1.19467 (1.83% below the provider close). The source was current, not delayed.

The durable scorecard now has five daily observations, one eligible v2 realized-price observation, and three older mixed-basis rows explicitly excluded from realized-gate scoring. No exact 7-, 28- or 84-day returns have matured; there are still zero complete prospective Sunday-to-Monday pairs and no broker fills. The push run was a research-only recovery capture, not the missing weekly horse-race run and not a trade signal.
