# BTC independent-evidence pilot — 19 October 2026

**Research-only, deliberately isolated. No automatic orders, additional ntfy alerts, portfolio writes, Production V5.8.2 changes, Research V5.9 changes, or changes to the live Cycle Trading dashboard.**

## Problem statement

The viral Polymarket screenshot/article is not authenticated performance evidence. Its $200-to-$14,300 claim is not a reasonable BTC expected-return assumption. On-chain BTC transfers are not the same as exchange buy/sell transactions. Without reliable dated exchange/entity wallet labels, one cannot rank all successful BTC traders or front-run their exits.

## Reuse instead of rebuilding

- The existing daily Cycle Trading market signal tape is a prospective immutable research recorder. Preserve its hash chain and data provenance.
- The existing archived BTC/USD series, Blockchain public-price overlap and verified Kraken fallback already supply a dated market baseline. The ASX:IBIT AUD quote is indicative/delayed, not a broker-executable price.
- October 2026 audit reports identify a significant mismatch between simplified live Cycle Trading buys/sells and the specific historical round-trip strategies. Fix model parity before any performance-based promotion.
- Production 5.8.2, Research 5.9 and Cycle Trading have correlated price/valuation inputs. Their agreement is not three independent votes.
- Current CryptoQuant/CoinGlass paid-plan restrictions are documented in the audit. Do not use restricted data without a verified entitlement.

## This narrow pull request

The new pure Python component, engines/research/btc_independent_evidence.py, accepts timestamped evidence families: cycle, valuation, onchain, spot_flow, derivatives. It forbids double counting families, rejects stale, future, malformed, unknown or unverified submissions, and refuses to grant consensus on cycle+valuation alone. An opposing live BUY/SELL vetoes a candidate recommendation. Two compatible votes including at least one non-cycle family yield only RESEARCH_WATCH (BUY or SELL); otherwise it says CONFLICT or INSUFFICIENT_EVIDENCE.

**It produces zero trade size in every scenario**. There is no current live evidence adapter, real wallet scanner, language model endpoint, broker order route, manual or automatic Streamlit integration, portfolio mutation, or new scheduled job. It is a small deterministic testable building block, not a validated trading strategy.

14 network-free unit tests cover independent support, correlation, disagreements, duplicate sources, source integrity and freshness, future/backdated values and guaranteed non-executable output.

## Actual roadmap and acceptance gates

1. Validate one *genuinely new* evidence provider (public spot order-book/print feed or independently labeled on-chain flow), record timestamps, symbol, cost, latency, source changes and permissions. Coinbase Exchange publishes public ticker/trade/level-2 channels; public live data alone provides neither long historical depth nor ASX:IBIT tradable bid/ask.
2. Build point-in-time, source-signed prospectively captured datasets. Never fabricate wallet P&L, reinterpret exchange internal transfers as whale sells, rewrite prior vintages, or use uncompleted BTC daily bars.
3. Treat market regime, exchange spot flow, derivative leverage and vetted entity flow as separate evidence groups. Treat all portfolio, fees, cash reconciliation, 7-day cooldown, stale price and tax reserve checks as mandatory risk vetoes rather than AI votes.
4. Before calculating any historical advantage, freeze the criteria and replay precise entry and exit orders causally (no future information), including real ETF weekday execution constraints, brokerage, currency conversion, bid/ask and SMSF taxes. Compare against exact live Cycle Trading, Production, Research, equal DCA and buy-and-hold.
5. Collect genuine prospective 7/30/90-day outcomes without retuning each time results disappoint. Only propose an optional read-only dashboard after it adds demonstrable out-of-sample, after-cost, risk-adjusted benefit. Do not promote to automated live execution without a later explicit decision and dedicated broker operational/security review.

## Running test

python -m unittest discover -s tests -p 'test_btc_independent_evidence.py' -v

## Cost

Deterministic tests run without paid inference. Real-time historical trade/order-book archives, provider licenses, always-on hosting and AI API calls might add ongoing cost. The anecdote's $25/month cost is not an estimate for this project.
