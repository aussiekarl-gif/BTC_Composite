# BTC Intelligence, phase 3: Coinbase BTC/USD executed-trade sample
Research-only pilot, 19 October 2026.

## Critical interpretation
Coinbase's Advanced public market-trades API provides a small RECENT sampled trade feed.
The API changelog (25 July 2025) explicitly says "side" is the MAKER side, not the aggressor. Accordingly a maker SELL trade was buyer initiated, and a maker BUY trade was seller initiated.

**Do not use a 100-trade sample to claim six hours of exchange flow, a whale's trades, entire market order imbalance, genuine volumes for that period, or forecasts of the next BTC move.** The sample may represent seconds. Each record includes actual oldest/newest trade timestamps, observed number of trades, sample duration, trade IDs, and client receipt time so misleading comparisons are evident.

Official references:
- https://docs.cdp.coinbase.com/coinbase-app/introduction/changelog
- https://coinbase.github.io/coinbase-advanced-py/coinbase.rest.html

## Components
- Read-only Python collector: \`engines/research/coinbase_trade_samples.py\`; \`GET https://api.coinbase.com/api/v3/brokerage/market/products/BTC-USD/ticker?limit=100\`; no API credentials.
- Tests: \`tests/test_coinbase_trade_samples.py\` (20 mocked validations, including correct inverted maker-side, stale/duplicate/future trades, abnormal inputs, no duplicate or backfill, immutability, fail-closed).
- GitHub workflow: \`.github/workflows/research_coinbase_trade_samples.yml\`; PR runs **mocked tests and read-only network probe, no writes**. After merge on main, attempts first actual sample and four UTC daily sampling slots (01:19/07:19/13:19/19:19), with a hash-chained append-only CSV at \`data/research_forward_validation/coinbase_trade_samples_forward.csv\`.

No orders, credentials, changes to Production 5.8.2, Research 5.9, Cycle Trading, Streamlit, IBIT, portfolio, audit master, Google Sheets or the existing single ntfy message.

## Caveats and scoring gate
- Source has to pass a genuine network probe before merge. Mock data does not establish live API access.
- This data is NOT independent of Bitcoin macro direction by mere virtue of coming from another exchange. Kraken book and Coinbase trades have different measurement processes and different venues, but both relate to contemporaneous spot microstructure. They must NOT be counted as separate independent "agent votes" until prospective independence/predictive lift is statistically demonstrated.
- The latest 100 trades are not time-complete and must **not** be treated as six-hour volume. Never extrapolate.
- A GitHub Runner can drift in exact cron start time; slot is determined from actual response receipt, not intended schedule.
- A tiny snapshot may be too noisy for reliable inference. Long-run continuous WebSocket capture or a provider delivering independently verified interval bars is needed before meaningful volume/trade-flow evidence.
- Next test: compare prospective observed sample to Kraken midpoint/depth with capture mismatch labels, and measure whether forward BTC return forecasts improve relative to Cycle Trading after realistic IBIT/AUD costs. Keep all paper-only until evidence supports promotion.
