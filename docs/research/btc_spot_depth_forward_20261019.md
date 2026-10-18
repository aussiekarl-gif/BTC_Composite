# BTC independent market-flow research — prospective Kraken spot liquidity
19 October 2026. **Paper-only, not a trading model.**

## What this adds

- A public REST read-only Kraken **XBT/USD** order-book adapter, requiring no exchange account or API key: `engines/research/btc_spot_depth_forward.py`.
- Four possible **prospective six-hour UTC snapshots per day** (01:17/07:17/13:17/19:17 UTC) via `.github/workflows/research_btc_spot_depth_forward.yml`. This schedule is dormant on the draft PR; it only operates on default `main` after a reviewed merge. Pull requests run mock offline tests AND one read-only live Kraken API parse smoke test, with no data persistence and no market signal. If Kraken is unavailable, the smoke check fails visibly.
- An append-only, date-ordered, SHA256-chained CSV at `data/research_forward_validation/kraken_spot_depth_forward.csv`. No backfill, retrospective fabricated order book, historical rewrites, portfolio calls or alerts.
- Per capture: pair/provider, client response-receipt UTC time, best bid/ask, spread in basis points, BTC and USD quantities **visible within 0.25% either side of midpoint**, and share of displayed near-mid bid liquidity.
- If the returned 500 levels fail to span BOTH 0.25% price ranges, coverage is flagged incomplete and share remains **UNKNOWN**, not zero or a tradable estimate.
- All captures are labeled `OBSERVATION_ONLY_NO_TRADE`: **no BUY/SELL signal, AI model vote, execution quantity, wallet-following claim, streaming data, broker connection, new ntfy, or Streamlit changes**.

## Freshness, data quality and limitations

Kraken order-book REST levels have per-level LAST UPDATE timestamps. They do **not** provide one authoritative exchange snapshot timestamp. The stored observation is the **client receipt instant**, not the top level's time; top bid/ask levels with no update for more than 15 minutes are rejected as potentially stale, but long-lived far-away resting orders are allowed. Duplicate prices, nonsensical spreads, locked/crossed books, future updates, NaNs, negative quantities, wrong pair, unexpected schema, tampered history and a request crossing an assigned six-hour capture slot fail closed.

Displayed depth is **not** net whale buying, market buy/sell volume, order fill probability or directional alpha. It is vulnerable to order cancellation/spoofing and is one venue only. The complete full-book payload is hashed, **not archived**, so exact re-derivation of old aggregates would require additional point-in-time full-depth storage. Prospective observations start only on first real provider response; existing historic tapes are not rewritten.

Data parser format is grounded in Kraken's public endpoint examples:
https://support.kraken.com/hc/articles/360000919986-public-endpoint-examples-you-can-try-them-directly-in-a-web-browser-
and https://docs.kraken.com/api/docs/rest-api/get-order-book

## Verification

Offline local tests: `python -m unittest discover -s tests -p 'test_btc_spot_depth_forward.py' -v` — **21 passed**, using mocked venue payloads. Live read-only GitHub PR probe is pending. No stored real observation or scheduled runner operation is yet verified; no data feed is declared operational until a subsequent main workflow captures an authentic dated row. Failure must be visible in Actions, not silently substituted by a synthetic observation.

## Next independent acceptance gates

1. Check PR live provider smoke check, then first real GitHub Actions Kraken capture and provenance, including correct symbol, slot UTC time, spread and depth coverage.
2. Establish independent spot-executed-trade flow and/or a second venue so one Kraken order-book snapshot is not misrepresented as independent market consensus.
3. Freeze candidate evidence rules before forward scoring. Evaluate 7, 30 and 90-day out-of-sample BTC returns and false BUY/SELL rates with no survivor bias.
4. Before proposing any live change, replay the actual Cycle Trading buy/sell state machine exactly, accounting for fees, costs, weekday ASX:IBIT order constraints, AUD FX, inventory, CGT reserve and execution delays. Compare buy-and-hold and equal DCA, including drawdown.
5. Expose at most an optional **read-only** Streamlit research panel once there is useful observed data. Keep the existing one daily ntfy and Production 5.8.2, Research 5.9, holdings and operational Cycle Trading rules unchanged.

## Running cost

The collector uses existing repository Python/GitHub Action infrastructure and `requests`, already installed for research. There are no AI API calls or provider subscriptions. GitHub Actions usage, request throttling, source changes and archival storage still require oversight.
