# V6.0 component source audit — 2026-11-22

## Scope and safety

This is a research-only source audit. It does not claim exact replication of Into The Cryptoverse's proprietary component transformations. No Production, V5.9, dashboard, portfolio, or DCA logic is changed.

The user has authorised progress on the six active components that do not require the outstanding miner-cap-to-ThermoCap (mCTC) miner-entity series. The seven active components remain equally weighted in the target reference; mCTC remains missing, so the seven-component composite must remain incomplete.

## Key finding: two free-first public sources now look promising

Coin Metrics' public Daily Network Metrics Availability page currently lists BTC with 1,194 / 1,194 daily network metrics completed through 2026-11-21. This makes the Coin Metrics Community API a strong independent source to test for standard daily series. The API and metric availability must still be tested directly; the availability page alone is not proof that every endpoint/metric is exposed under Community entitlements.\n\nA second source, Explore21, publishes daily CSVs and a no-key JSON API under CC BY 4.0. Its public catalogue explicitly lists Puell Multiple (2012-08-16 onward), MVRV Ratio (2011-09-16 onward), and MVRV Z-Score (2011-09-16 onward), with method versions and changelog links. It also preserves daily point-in-time vintages from 2026-11-18 onward. That vintage history is too short to provide historical point-in-time data for old cycles, but it is useful for prospective shadow validation and method-change tracking. The earlier historical series remain current/reconstructed data, not frozen historical vintages.

References:
- Availability: https://availability.coinmetrics.io/
- Community API: https://community-api.coinmetrics.io/v4\n- Explore21 data catalogue/API: https://charts.explore21.com/data\n- Explore21 Puell: https://charts.explore21.com/bitcoin-puell-multiple\n- Explore21 MVRV: https://charts.explore21.com/bitcoin-mvrv-ratio\n- Explore21 MVRV Z-Score: https://charts.explore21.com/bitcoin-mvrv-z-score
- Fees/revenue metric catalogue: https://docs.coinmetrics.io/network-data/network-data-overview/fees-and-revenue
- Supply metric catalogue: https://docs.coinmetrics.io/network-data/network-data-overview/supply

Coin Metrics Community data is licensed CC BY-NC 4.0. Preserve attribution and do not republish commercially without checking the licence.

## Component audit

| Active component | Best current route | Status | Important caveat |
|---|---|---|---|
| Puell Multiple | Explore21 `bitcoin-puell-multiple` primary candidate; Coin Metrics `IssTotUSD` / `PuellMulTot` independent cross-check | Public daily CSV/API listed from 2012-08-16 | Explore21 defines daily newly issued coin value / its 365-day average. Historical series is current/reconstructed before 2026-11-18; retain vintage limitation. Do not confuse issuance-only with total miner revenue including transaction fees. |
| MVRV | Explore21 `bitcoin-mvrv-ratio` primary candidate; Coin Metrics `CapMVRVCur` independent cross-check | Public daily CSV/API listed from 2011-09-16 | Coin Metrics defines it as current market cap / realised cap. Compare both providers and local PlanB price / realised-price proxy; do not treat PlanB as Cowen source. |
| MVRV Z-Score | Explore21 `bitcoin-mvrv-z-score` primary candidate; Coin Metrics `CapMVRVZ` and existing BlockHorizon export as cross-checks | Public daily CSV/API listed from 2011-09-16 | Standard definition is (market cap - realised cap) / standard deviation of market cap. The standard-deviation history/window and provider conventions must match before claiming parity. |
| Transaction Fees | Coin Metrics `FeeTotUSD` (and native-unit counterpart if available) | Direct daily metric identified | `FeeTotUSD` is total USD value of fees paid in the interval, using daily close price. Cowen's exact selected fee series, smoothing, transformation and risk direction remain unknown. Preserve USD and native series for comparison. |
| Terminal Price | Reconstruct from cumulative Value Days Destroyed / (market age × supply), then multiply Transferred Price by 21 | Formula identified; raw input acquisition pending | Requires complete daily CDD/VDD history and a precisely aligned price, supply, and genesis/first-price date. Do not substitute CVDD, Balanced Price or a different terminal-price chart. |
| MCTC | Existing uploaded Market Cap / ThermoCap ratio history | Data file exists in the current research context | Snapshot currently ends 2026-11-21. Provider, currency, exact ThermoCap definition, and point-in-time vintage still need validation. This component is not blocked by miner entity attribution. |
| mCTC | MinerCap / Thermocap | Blocked / missing | MinerCap needs mining-entity balances, not just coinbase payout addresses. Continue provider research separately. |

Zero-weight diagnostics RHODL Ratio and Supply P/L remain outside the default seven-component composite.

## Explore21 source coverage and vintage caveat\n\nExplore21's public catalogue reports:\n- Puell Multiple: 2012-08-16 to 2026-11-21; method v1; columns include raw issuance BTC, issuance USD, 365-day issuance USD average and BTC close.\n- MVRV Ratio: 2011-09-16 to 2026-11-21; method v2.\n- MVRV Z-Score: 2011-09-16 to 2026-11-21; method v1.\n- Realized Price and Realized Cap: 2011-08-18 to 2026-11-21.\n- Point-in-time published vintages currently begin 2026-11-18. Do not mistake this recent archive for historical vintages back to 2011.\n\nExplore21's data is CC BY 4.0 and requires attribution/linking to the relevant chart. Its catalogue does not currently list Cowen's Transaction Fees or Terminal Price series, so it does not complete the six non-mCTC components.\n\n## Formula references

- MVRV: Coin Metrics defines `CapMVRVCur` as market cap divided by realised market cap: https://github.com/coinmetrics/docs-website/blob/master/asset-metrics/market/capmvrvcur.md
- Total transaction fees: Coin Metrics defines `FeeTotUSD` as the sum USD value of all fees paid during the interval, computed from native fees multiplied by daily close price: https://github.com/coinmetrics/docs-website/blob/master/asset-metrics/fees-and-revenue/feetotusd.md
- Miner revenue / ThermoCap: Coin Metrics defines `RevUSD` as daily USD miner revenue (fees plus newly issued native units), and `RevAllTimeUSD` as cumulative revenue / ThermoCap: https://docs.coinmetrics.io/network-data/network-data-overview/fees-and-revenue/revenue
- Puell: daily issued-coin value divided by its 365-day moving average: https://userguide.cryptoquant.com/cryptoquant-metrics/network/puell-multiple
- Terminal Price: Cowen's public explanation defines Terminal Price as 21 × Transferred Price, where Transferred Price uses cumulative Value Days Destroyed divided by market age and supply: https://www.youtube.com/watch?v=WUJwW3mf6to
- MVRV Z-Score: standard formulation is (market cap − realised cap) / standard deviation of market cap: https://studio.glassnode.com/charts/market.MvrvZScore

## Existing local exports inspected

Repository data currently includes:
- `data/miner_revenue_total_daily__2026-10-07T21-26-46.csv` — daily miner-revenue export, 2009-01-09 to 2026-10-06. The earlier structural review found 6,480 continuous dates but unresolved denomination/scale. It is not accepted as Puell input.
- `data/planb_realized_prices_2026-10-07T21-19-48.csv` — includes Price and Realized Price from 2011-12-31 to 2026-10-06. Useful for an explicitly labelled MVRV proxy and parity check only.
- `data/mvrv_z_score_2026-10-06T21-46-14.csv` — daily provider export from 2010-11-01 to 2026-10-05. Structurally clean, but exact Cowen-source and calculation parity are not established.
- `data/nupl_net_unrealized_profit_loss__2026-10-06T08-54-39.csv` and `data/supply_in_profit_2026-10-07T21-21-51.csv` — useful cross-checks/diagnostics, not substitutes for active components.
- MCTC and ThermoCap daily CSVs supplied on 2026-11-22 are available in the current conversation's working context; import metadata exists in the separate MCTC research work.

## Code added in this PR

`engines/research/cowen_onchain_risk.py` now has `build_existing_raw_candidates(data_dir)`. It loads the existing three candidate series:
1. Puell candidate: daily exported miner-revenue value / trailing 365-observation mean. This remains exploratory because source units and whether the field is issuance-only or full miner revenue are unresolved.
2. MVRV proxy: PlanB exported BTC price / PlanB realised price. This is not the canonical Coin Metrics MVRV series.
3. MVRV Z-Score: saved provider export as-is.

The loader does not fill missing dates, does not normalize values, and does not create a composite. It exists to make data reuse repeatable while the direct Coin Metrics feed is built.\n\n`engines/research/coinmetrics_community.py` now provides a no-key daily API client with 10,000-row pagination, UTC date handling, null preservation, metric-level fallback when a batch is rejected, and a JSON provenance sidecar (retrieval timestamp, metric IDs, coverage, missingness, CC BY-NC attribution and CSV SHA-256). Tests cover pagination, untrusted next-page hosts, unavailable metric fallback and sidecar generation. The first live acquisition is still pending; do not claim that any metric was successfully retrieved until the script runs in CI or a controlled environment.

## Next engineering actions

1. Add a small Explore21 CSV/API acquisition adapter for Puell, MVRV and MVRV Z, preserving method versions and CC BY 4.0 attribution; use Coin Metrics as an independent cross-check.\n2. Add a free-first Coin Metrics Community API client for BTC daily `CapMVRVCur`, `CapMVRVZ`, `FeeTotUSD`, `IssTotUSD`, `PuellMulTot` (where supported), `PriceUSD`, and `SplyCur`. Record request timestamp, response metadata, source metric IDs, units, and missingness.
3. Cross-check Coin Metrics MVRV against PlanB price / realised-price proxy; cross-check Coin Metrics Puell against both `IssTotUSD` / 365-day SMA and `PuellMulTot`.
4. Preserve transaction fees in USD and native BTC; test raw level, ratio-to-issuance, and trailing-relative variants separately. Do not choose a transformation based on backtest performance before defining training/validation/test periods.
5. Acquire daily CDD/VDD for Terminal Price from a reproducible public source. If the source requires paid access, calculate from chain data in an automated pipeline rather than asking the user to perform manual BigQuery exports.
6. Verify MCTC source provenance and merge its CSV metadata into the V6.0 data manifest.
7. Continue mCTC independently. Until all seven components are valid, composite risk remains null and status remains `INCOMPLETE — NOT INVESTABLE`.

## Normalisation caution

Cowen's public descriptions establish that component metrics are normalised to 0–1 and then averaged, and that the final average may be re-normalised to 0–1. They do not, by themselves, disclose every metric's exact transform, direction, historical window, or final re-normalisation algorithm. The current prior-only percentile function is one transparent research candidate, not an exact replica. Maintain separate variants until chart parity can be checked.
