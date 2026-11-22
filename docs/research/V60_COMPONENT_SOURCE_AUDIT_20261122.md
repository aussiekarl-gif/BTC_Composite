# V6.0 component source audit — 2026-11-22

## Scope and safety

This is a research-only source audit. It does not claim exact replication of Into The Cryptoverse's proprietary component transformations. No Production, V5.9, dashboard, portfolio, or DCA logic is changed.

The user has authorised progress on the six active components that do not require the outstanding miner-cap-to-ThermoCap (mCTC) miner-entity series. The seven active components remain equally weighted in the target reference; mCTC remains missing, so the seven-component composite must remain incomplete.

## Key finding: two free-first public sources now look promising

Coin Metrics' public Daily Network Metrics Availability page currently lists BTC with 1,194 / 1,194 daily network metrics completed through 2026-11-21. This makes the Coin Metrics Community API a strong independent source to test for standard daily series. The API and metric availability must still be tested directly; the availability page alone is not proof that every endpoint/metric is exposed under Community entitlements.

A second source, Explore21, publishes daily CSVs and a no-key JSON API under CC BY 4.0. Its public catalogue explicitly lists Puell Multiple (2012-08-16 onward), MVRV Ratio (2011-09-16 onward), and MVRV Z-Score (2011-09-16 onward), with method versions and changelog links. It also preserves daily point-in-time vintages from 2026-11-18 onward. That vintage history is too short to provide historical point-in-time data for old cycles, but it is useful for prospective shadow validation and method-change tracking. The earlier historical series remain current/reconstructed data, not frozen historical vintages.

References:
- Availability: https://availability.coinmetrics.io/
- Community API: https://community-api.coinmetrics.io/v4
- Explore21 data catalogue/API: https://charts.explore21.com/data
- Explore21 Puell: https://charts.explore21.com/bitcoin-puell-multiple
- Explore21 MVRV: https://charts.explore21.com/bitcoin-mvrv-ratio
- Explore21 MVRV Z-Score: https://charts.explore21.com/bitcoin-mvrv-z-score
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
| Terminal Price | Implement Cowen's formula from daily CDD, BTC price and circulating supply | Formula implemented; CDD source rights/access pending | Requires complete daily CDD/VDD history and aligned price/supply. OnChainLab publishes a free full-history CDD CSV/JSON, but I found no explicit data-reuse licence; treat it as a validation lead only until permission is clear. Do not substitute CVDD or Balanced Price. |
| MCTC | Existing uploaded Market Cap / ThermoCap ratio history | Data file exists in the current research context | Snapshot currently ends 2026-11-21. Provider, currency, exact ThermoCap definition, and point-in-time vintage still need validation. This component is not blocked by miner entity attribution. |
| mCTC | MinerCap / Thermocap | Blocked / missing | MinerCap needs mining-entity balances, not just coinbase payout addresses. Continue provider research separately. |

Zero-weight diagnostics RHODL Ratio and Supply P/L remain outside the default seven-component composite.

## Terminal Price formula and CDD source audit

Cowen's 2026 explanation gives the exact raw formula:

- Value Days Destroyed = CDD × BTC price at the spend date.
- Transferred Price = cumulative Value Days Destroyed / (market age in days × circulating supply).
- Terminal Price = 21 × Transferred Price.

The market age starts at the first price observation. The code treats that first observation as day 1, and requires consecutive complete daily CDD, price and supply inputs. A missing CDD day invalidates the cumulative series; it is never filled with zero. The raw ratio `price_to_terminal_price` is retained as the likely risk-direction candidate (higher means price is closer to/above the Terminal Price ceiling), but Cowen's exact 0–1 component transform remains unknown.

Potential CDD source: OnChainLab publishes daily CDD from 2009-01-12 to 2026-10-16, computed from its own full Bitcoin archive node, with a JSON endpoint and a full daily CSV. Its methodology page is useful and transparent, but no explicit data-reuse licence was found in the reviewed pages. It is therefore not yet accepted as an automated project data dependency or redistributed in this repository. Newhedge also offers a CDD API but requires an API token.

References: Cowen formula explanation https://www.youtube.com/watch?v=WUJwW3mf6to ; OnChainLab CDD methodology/data https://onchainlab.net/metrics/cdd ; OnChainLab project notes https://onchainlab.net/about ; Newhedge CDD API token requirement https://prod-docs.newhedge.io/api/coin-days-destroyed

## Explore21 source coverage and vintage caveat

Explore21's public catalogue reports:
- Puell Multiple: 2012-08-16 to 2026-11-21; method v1; columns include raw issuance BTC, issuance USD, 365-day issuance USD average and BTC close.
- MVRV Ratio: 2011-09-16 to 2026-11-21; method v2.
- MVRV Z-Score: 2011-09-16 to 2026-11-21; method v1.
- Realized Price and Realized Cap: 2011-08-18 to 2026-11-21.
- Point-in-time published vintages currently begin 2026-11-18. Do not mistake this recent archive for historical vintages back to 2011.

Explore21's data is CC BY 4.0 and requires attribution/linking to the relevant chart. Its catalogue does not currently list Cowen's Transaction Fees or Terminal Price series, so it does not complete the six non-mCTC components.

## Formula references

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

The loader does not fill missing dates, does not normalize values, and does not create a composite. It exists to make data reuse repeatable while the direct Coin Metrics feed is built.

`engines/research/coinmetrics_community.py` provides a no-key daily API client with 10,000-row pagination, UTC date handling, null preservation, metric-level fallback when a batch is rejected or omits a requested metric, and a JSON provenance sidecar (retrieval timestamp, metric IDs, coverage, missingness, CC BY-NC attribution and CSV SHA-256).

`calculate_terminal_price(inputs)` now implements the raw Cowen Terminal Price formula, including explicit first-price-observation market age and strict no-gap/no-null validation. It returns VDD, cumulative VDD, transferred price, terminal price and price/terminal ratio; it does not normalize the ratio into a risk score.

`engines/research/explore21_public_data.py` provides a whitelisted CSV downloader for Explore21 Puell, MVRV and MVRV Z-Score. It preserves source columns and gaps and writes method-version, chart-link, CC BY 4.0 attribution, vintage caveat and SHA-256 metadata. Tests cover source-column validation, missing values and provenance. Live retrieval is still pending; do not claim any metric was successfully retrieved until the PR's live-source smoke workflow runs.

## Next engineering actions

1. Add a small Explore21 CSV/API acquisition adapter for Puell, MVRV and MVRV Z, preserving method versions and CC BY 4.0 attribution; use Coin Metrics as an independent cross-check.
2. Add a free-first Coin Metrics Community API client for BTC daily `CapMVRVCur`, `CapMVRVZ`, `FeeTotUSD`, `IssTotUSD`, `PuellMulTot` (where supported), `PriceUSD`, and `SplyCur`. Record request timestamp, response metadata, source metric IDs, units, and missingness.
4. Cross-check Coin Metrics MVRV against PlanB price / realised-price proxy; cross-check Coin Metrics Puell against both `IssTotUSD` / 365-day SMA and `PuellMulTot`.
5. Preserve transaction fees in USD and native BTC; test raw level, ratio-to-issuance, and trailing-relative variants separately. Do not choose a transformation based on backtest performance before defining training/validation/test periods.
6. Secure a reusable daily CDD source for Terminal Price. OnChainLab is a methodology lead but has no clear reuse licence in the pages reviewed; do not automate/redistribute its data without resolving that. Prefer a clearly licensed source or our own automated UTXO-derived pipeline.
7. Verify MCTC source provenance and merge its CSV metadata into the V6.0 data manifest.
8. Continue mCTC independently. Until all seven components are valid, composite risk remains null and status remains `INCOMPLETE — NOT INVESTABLE`.

## Normalisation caution

Cowen's public descriptions establish that component metrics are normalised to 0–1 and then averaged, and that the final average may be re-normalised to 0–1. They do not, by themselves, disclose every metric's exact transform, direction, historical window, or final re-normalisation algorithm. The current prior-only percentile function is one transparent research candidate, not an exact replica. Maintain separate variants until chart parity can be checked.


## Live public-source smoke result — 2026-11-22 19:50 UTC

The PR's public-source smoke job completed successfully and uploaded a reproducible snapshot artifact. The exact raw files and provider sidecars were inspected after download.

Explore21 results (daily, latest date 2026-11-21):
- Puell Multiple: 5,211 rows, 2012-08-16 to 2026-11-21; latest 0.9114571567.
- MVRV ratio: 5,546 rows, 2011-09-16 to 2026-11-21; latest 1.129338.
- MVRV Z-Score: 5,546 rows, 2011-09-16 to 2026-11-21; latest 0.219062.
- All three downloaded series had no missing observations or duplicate daily dates in their published ranges.

Coin Metrics Community results:
- 6,532 daily rows, 2009-01-03 to 2026-11-21.
- Returned: CapMVRVCur, IssTotUSD, PriceUSD, SplyCur.
- Unavailable under Community access (HTTP 403): CapMVRVZ, FeeTotUSD, PuellMulTot.
- CapMVRVCur latest: 1.1299291147, versus Explore21 MVRV 1.129338 on the same date: +0.0523% relative difference.
- Coin Metrics PriceUSD latest: USD 60,122.61 versus Explore21 close USD 60,078.34: +0.0737%. This small difference is consistent with differing price-source/close conventions; retain source-specific prices rather than forcing a match.
- Coin Metrics SplyCur includes zero values in early history and should not be used without validity checks; MVRV/issuance/price first become populated after their 561 initial missing rows.

This supports Explore21 as the current primary candidate source for Puell, MVRV and MVRV Z, with Coin Metrics as an independent MVRV check. It does not prove exact Cowen parity or point-in-time historical availability. The snapshot workflow now has a separate daily refresh definition; data will be committed to the research data folder only after that workflow runs on the default branch following merge. Until then, the successful files remain in the CI artifact and are not yet checked into the repository.


## Transaction Fees candidate — Aethereal (added 2026-11-22)

Aethereal publishes a daily Bitcoin Network dataset from 2009 onward, refreshed daily, with a BTC-denominated total-fees field. Its stated terms are free for research and education; this is not treated as a blanket commercial redistribution licence. The adapter stores the raw BTC/day series, preserves nulls, validates unique UTC daily dates, and writes a source/licence/hash sidecar. No USD conversion uses Aethereal's own price field because its daily price convention differs from the Coin Metrics close used elsewhere.

Independent same-day cross-check: Black Almanak reports 3.247 BTC total fees on 2026-11-21 and documents its calculation as the sum of inputs minus outputs for every non-coinbase transaction in blocks assigned to that UTC day. It says its values are checked against coinbase collections, blockchain.com and Coin Metrics. Its methodology page explicitly says free viewing does not grant unrestricted reuse of third-party prices or derived data; therefore Black Almanak is used only as a displayed validation reference, not as a downloaded or redistributed project dependency.

The Research 10.0 dashboard now labels the Aethereal series as a transaction-fee candidate in BTC/day. Higher-fee percentile is provisionally treated as higher risk for comparison only; exact Cowen unit, smoothing and normalisation remain unknown.


## Terminal Price input source — Open Bitcoin Metrics CDD (added 2026-11-22)

A reusable CDD history is now available from Open Bitcoin Metrics (OBM), published under CC BY 4.0. Its daily series is derived from spent-output values and ages, with CDD measured in BTC-days; the source repository publishes the CSV, metric definition, generation code, release version and validation notes. The checked-in source file currently covers 2009-01-03 through 2026-11-17 (6,528 daily rows), so it is four days behind the 2026-11-21 market series.

The adapter preserves valid zero CDD days, rejects missing dates/duplicates/negative values, and records source URL, release version, unit, attribution and SHA-256. The daily refresh workflow now retrieves this file alongside Explore21, Coin Metrics and Aethereal.

The first positive Coin Metrics Community price and supply-aligned price series begins 2010-07-18. Therefore the current Terminal Price candidate:
- starts its VDD accumulation on 2010-07-18, when all required price/supply inputs are available;
- counts market age from 2009-01-03;
- does not invent or zero-fill pre-2010 USD price-weighted CDD;
- is explicitly a partial-history reconstruction, not a validated exact Cowen Terminal Price series.

The candidate is the raw price / Terminal Price ratio plus the implied Terminal Price USD value. Direction and Cowen's component normalisation remain unverified. It must not be promoted to an exact component or DCA input until its early-history treatment and formula parity are independently reconciled.


## MCTC candidate reconstruction — Coin Metrics ThermoCap definition

Coin Metrics defines All Time Miner Revenue (RevAllTimeUSD) as the cumulative sum of daily miner revenue in USD, including newly issued coins plus transaction fees, and explicitly notes that this metric is also known as ThermoCap. The current reconstruction therefore calculates daily miner revenue as Coin Metrics IssTotUSD plus Aethereal fees_btc multiplied by the Coin Metrics PriceUSD daily close, then cumulatively sums it. MCTC candidate = (Coin Metrics PriceUSD × SplyCur) / reconstructed cumulative miner revenue.

This is a transparent cross-provider reconstruction, not a claim that the Cowen dashboard uses exactly this provider or convention. It begins on 2010-07-18, the first date with positive Coin Metrics price and issuance values, and only calculates while all daily inputs are complete and contiguous. It does not fill missing data. The raw ThermoCap estimate is retained beside the MCTC ratio so it can be compared with the user's previously supplied ThermoCap history.

A second definition must remain distinct: Glassnode and Black Almanak describe ThermoCap as cumulative coinbase issuance valued at the contemporaneous price, excluding transaction fees. Coin Metrics' RevAllTimeUSD includes fees plus issuance. Those variants can differ materially over Bitcoin's history. The user's MCTC/ThermoCap file is the parity target; do not choose between variants solely on backtest performance.

References: Coin Metrics Revenue metric definition (RevAllTimeUSD = cumulative RevUSD, also known as ThermoCap); Glassnode Thermocap definition (coinbase transactions); Black Almanak Market Cap to Thermocap formula (issuance-only).


### MCTC reconstruction missing-fee handling

The successful public-source snapshot found three Aethereal fee-BTC observations missing after the common market-price start (2025-11-13 through 2025-11-15), while Aethereal's total miner-revenue USD and price fields were present. The reconstruction does not fill those fee rows with zero or carry adjacent values forward. For those dates only, it derives miner-revenue BTC from Aethereal total miner-revenue USD divided by Aethereal's own daily price, then revalues that BTC revenue at the Coin Metrics daily close. The dashboard exposes the cumulative number of these source-backed fallback days. This is an alternate source path, not a fabricated observation.


### MCTC parity check against the user's uploaded series (2026-11-21)

Using the successful public-source snapshot, the independent reconstruction starts 2010-07-18 and is continuous through 2026-11-21. It produced:
- Reconstructed ThermoCap: USD 100,598,150,055.
- Reconstructed MCTC: 12.02200.
- Three missing Aethereal fees_btc observations were handled by the documented Aethereal total-miner-revenue fallback; no missing values were zero-filled.

The user's previously uploaded 2026-11-21 series showed ThermoCap USD 100,566,384,572 and MCTC 12.017. The independent reconstruction differs by only +0.0316% in ThermoCap and +0.0416% in MCTC. This is a strong parity result for the fees-inclusive Coin Metrics-style ThermoCap variant. It is still a cross-source validation, not proof that the proprietary Cowen component uses exactly these source fields or transformations.

The five-year prior-only percentile for the reconstructed MCTC ratio on 2026-11-21 is 27.45%. It is a research candidate percentile, not a Cowen slider score or DCA instruction.


### Terminal Price candidate latest observation

Using the documented formula (Terminal Price = 21 × cumulative CDD × daily BTC price ÷ [market age in days × circulating supply]), the source intersection through 2026-11-17 gives:
- Terminal Price candidate: USD 306,009.
- Coin Metrics BTC close: USD 64,908.18.
- Price / Terminal Price: 0.2121.
- Five-year prior-only percentile of the ratio: 9.21%.

The CDD input is four days behind the other daily sources at this snapshot. The output is explicitly a partial-history candidate because its cumulative USD value-days history starts on 2010-07-18, when the first valid Coin Metrics market price is available, while market age is counted from 2009-01-03. No missing CDD days are filled.


## Current candidate percentile snapshot — 2026-11-21

Five-year prior-only empirical percentiles (1,825 calendar-day lookback; only valid prior observations counted) from the successful source snapshot:

| Candidate component | Latest date | Raw value | Prior-only percentile |
|---|---|---:|---:|
| Puell Multiple | 2026-11-21 | 0.91146 | 44.55% |
| MVRV | 2026-11-21 | 1.12934 | 13.21% |
| MVRV Z-Score | 2026-11-21 | 0.21906 | 13.75% |
| Transaction Fees | 2026-11-21 | 3.2467 BTC/day | 18.88% (1,822 valid prior days) |
| MCTC | 2026-11-21 | 12.0220 | 27.45% |
| Price / Terminal Price | 2026-11-17 | 0.21211 | 9.21% |

These are our own candidate percentiles, not the nine-item Cowen indicator output. The transaction-fee percentile uses only 1,822 available prior observations because three daily fee rows in its five-year window are missing. No missing value was filled. The Terminal Price source is four days stale in this snapshot. mCTC remains pending; therefore the seven-component composite remains disabled.
