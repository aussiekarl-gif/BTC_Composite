# BTC DCA Project Handover

Last updated: 2026-11-27 (Brisbane; session update 08:30 UTC)

This file is the durable starting point for future ChatGPT sessions and human contributors. Update it when material decisions, validation results, or project status change. The repository and committed evidence are authoritative; chat summaries are secondary.

## Mission

Improve BTC accumulation timing and total portfolio outcomes through reproducible research, historical backtests, walk-forward validation, and reliable daily research data. Compare BTC accumulated and final AUD portfolio value against buy-and-hold and fixed-DCA baselines.

## Non-negotiable operating rules

- **Production is frozen.** Do not change Production signals, sizing, execution, or dashboard behaviour unless the user explicitly authorizes a separately validated production change.
- Research changes must remain clearly labelled research-only until validated.
- Do not merge code that has not passed relevant automated tests and review.
- Do not invent data, fill missing observations with zero, or silently publish stale/corrupt snapshots.
- Preserve source provenance, units, date conventions, and missingness.
- Notifications are currently **disabled**. Do not re-enable ntfy or add new notification routes.
- Streamlit is the intended UI. No NAS deployment.
- User prefers autonomous, sensible low-risk project improvements without approval requests for every routine change.

## Portfolio and policy context

User-provided portfolio context (12 Nov 2026; reconfirm before any live execution calculation):
- Original capital: A$510,000.
- Holdings: 10,250 ASX shares and 5,829 AAA shares.
- Approximate AAA reserve market value: A$292,383.
- Approximate IBIT market value: A$209,305.
- AAA variable distributions were estimated at about 5% annualised at that time.
- Ordinary weekly buy allocation cap: 5% of original capital (A$25,500).
- No leverage.
- Stop buying when risk exceeds 0.50 under the aggressive research policy.

These are historical user-supplied figures, not live account data. Never imply current holdings, cash, or prices have been refreshed unless verified.

## Research preferences and constraints

- Prioritise timing research over unnecessary cash-accounting complexity.
- Test buying near/below the 200-week moving average, including recovery confirmation and the historically observed period below the 200WMA.
- Include relevant pre-2018 cycles; ignore 2013 and pre-2017 test periods as previously requested.
- Include BTC realised price where relevant.
- Target average cycle timing error is approximately 25%, not 40%.
- Compare BTC accumulated and final AUD value, not only signal accuracy.
- Keep the actual BTC USD price visible as a single clear value where relevant.
- Where IBIT execution is modelled, show IBIT quantity and price per IBIT as well as BTC reference price.
- User-supplied cycle bottom reference: USD 57,717 on 30 Jun 2026. Treat as a user input, not independently verified market data.

## Daily research data reliability

The user needs daily data early enough to make decisions. External cron-job.org dispatch is configured for 9:00am Brisbane time. GitHub scheduled backup windows are UTC 23:17, 00:17, and 01:17 (approximately 9:17am, 10:17am, and 11:17am Brisbane time).

External dispatch endpoint is the GitHub Actions workflow-dispatch API for:
`aussiekarl-gif/BTC_Composite/actions/workflows/cowen_onchain_daily_refresh.yml`

A GitHub API response of HTTP 204 / "No content" means the dispatch request was accepted; it does not prove the workflow completed successfully. Verify the resulting Actions run and each source outcome.

A fine-grained token renewal reminder is scheduled for 11 Feb 2027 at 9:00am Brisbane time. Token expiry was 25 Feb 2027. Never put token values in this repository or ask the user to share them.

## Data-source handling decisions

- Aethereal is the preferred transaction-fee source when valid and fresh.
- Coin Metrics Community FeeTotNtv is a fallback/cross-check for missing Aethereal fee observations. Keep source series and provenance distinct; do not splice them invisibly.
- The six-day comparison (18–23 Nov 2026) showed about 2.04% mean absolute percentage difference between Aethereal and Coin Metrics fees. This is a short sample, not evidence of long-run equivalence.
- Open Bitcoin Metrics CDD was last observed current through 22 Nov 2026 as of 27 Nov.
- Aethereal local snapshot was last observed through 23 Nov 2026 as of 27 Nov.
- Do not integrate restricted CDD APIs without confirming licence and permitted use. In particular, avoid providers whose terms prohibit trading/investment-decision use or whose API terms do not permit the intended GitHub Actions + Streamlit deployment.

## Current open work (27 Nov 2026)

### PR #407 — Aethereal Google DoH fallback

URL: https://github.com/aussiekarl-gif/BTC_Composite/pull/407

- State: open, not merged.
- Branch: `research/aethereal-google-doh-fallback`
- Head at last review: `e9cdbd592380f0ba3a11f9b2f0795acb7d7d403c`
- Adds a separately testable Python DoH helper used by the scheduled refresh after normal DNS retries.
- Tries Cloudflare then Google DoH, validates IPv4 A records, and uses curl `--resolve` for the original Aethereal hostname, preserving HTTPS hostname/TLS verification.
- Adds unit coverage for resolver failover, empty answers, IPv4 validation, pinned HTTPS hostname, and parsing the downloaded CSV.
- Regression run 45965169468: `test` and `v60-public-data-smoke` jobs both completed successfully. The test job passed fallback unit tests, matched 200WMA research, and V6.0 path/cost sensitivity report. V5.9 validation run 45965169446 passed.
- Important: the smoke job is green because the direct Aethereal and DoH steps are explicitly `continue-on-error`. Direct Aethereal fetch failed normal DNS; DoH received DNS status 3 (NXDOMAIN) from both Cloudflare and Google. No CSV was downloaded.
- Explore21 and Coin Metrics returned observations through 26 Nov. Open Bitcoin Metrics CDD returned 6,533 rows through 22 Nov.
- Search-indexed Aethereal pages advertise the Bitcoin Network Daily CSV through 24 Nov, but web page retrieval returned 502 and runner DoH checks returned NXDOMAIN. Treat search-indexed pages as unverified cache, not live availability.
- Firsthand Bitcoin is a possible replacement/cross-check: its public API lists daily hashrate, difficulty, fees, transactions, miner revenue, Puell, realised price and MVRV, free with attribution. It remains a candidate pending methodology and historical comparison.
- **Keep PR #407 open and unmerged.** The helper tests pass, but Aethereal itself is not recovered. No Production changes.


### Firsthand Bitcoin API candidate review (27 Nov 2026)

Official API catalogue: https://firsthandbitcoin.com/data/api

- The series catalogue is live and was generated at 2026-11-27T08:23:56Z. It exposes public JSON/CSV endpoints without an API key and says free use is permitted with attribution/link to https://firsthandbitcoin.com/data; it reports updates a few times daily.
- Candidate series include daily hashrate, difficulty, BTC fees, transactions, miner revenue, realised price, MVRV, UTXO count, 200WMA and 200DMA.
- GitHub Actions end-to-end JSON retrieval is now verified: run 45965988733 completed successfully and uploaded artifact `firsthand-api-raw-diagnostic` (artifact ID 15182219026; expires 11 Dec 2026). It fetched catalogue, summary and 19 candidate series. Raw files were inspected from the downloaded artifact.
- Payloads use objects with metadata fields `source`, `url`, `license`, `generated`, `key`, `label`, `unit`, `from`, `to`, `points`, and `data`; data rows are [ISO date, numeric value] pairs. BTC price covers 2013-01-01 to 2026-11-27 (5,079 rows); daily hashrate 2013-03-18 to 2026-11-27 (4,999); difficulty 2013-01-01 to 2026-11-27 (5,079); daily fees 2013-01-01 to 2026-11-26 (5,075); realised price and MVRV 2013-01-01 to 2026-11-26 (5,078 each); 200WMA 2016-10-31 to 2026-11-27 (3,680).
- Initial structural checks on the fetched payloads found no duplicate dates or non-numeric values in the inspected daily series. Some series have missing dates: daily hashrate omits four dates (19, 20, 26 and 28 Mar 2013); daily fees omit 13–15 Nov 2025; and fee-derived/transaction series omit 14–20 Nov 2025. These exact missing dates were confirmed from the downloaded raw artifact. Difficulty is stepwise and naturally repeats values. Do not fill gaps.
- Preliminary matched comparison against Coin Metrics Community data through 26 Nov 2026: Firsthand MVRV is effectively identical to Coin Metrics CapMVRVCur (mean absolute percentage difference ~0.0000013%), suggesting shared upstream data or methodology rather than an independent cross-check. Firsthand daily fees vs FeeTotNtv mean absolute percentage difference ~1.57%. Firsthand BTC price vs PriceUSD mean absolute percentage difference ~2.24%, with historical outliers up to ~92.9%; the recent 25/26 Nov Firsthand BTC price repeats 59,171.86 while Coin Metrics values differ. Investigate daily close conventions, repeated values, outliers and date alignment before considering use.
- These comparisons are exploratory calculations on one downloaded snapshot, not a full validation. Firsthand is proven machine-retrievable, but data correctness, independence, full historical completeness, and metric formulas remain unapproved.
- Published methodology evidence: Firsthand describes hashrate as a block-arrival-based estimate and explicitly notes high daily noise; its chart line is a 7-day average. Difficulty is consensus retarget data. Fee series is presented as daily BTC fees paid to miners and commonly charted as a 7-day average. Realised price is described as average BTC cost basis from the price at which each BTC last moved; MVRV is market value divided by realised value.
- Independence caution: Firsthand is operated by NMine LLC, a mining hardware sales/hosting business. This is not a reason to reject its public on-chain series, but its incentive context should be recorded and its values independently cross-checked.
- Preliminary suitability: promising independent research cross-check for hashrate, difficulty, fees and realised price; NOT yet approved as a production/research pipeline replacement. Need direct API retrieval in GitHub Actions, schema/units/date checks, historic overlap against Coin Metrics/Explore21/OBM/Aethereal snapshots where available, and formula validation before integration.
- Avoid using Firsthand's 200WMA as a model input until verified against the project's own canonical price series and rolling-window calculation; it can be compared as an external cross-check only.


### PR #409 — Firsthand public API diagnostic (27 Nov 2026)

URL: https://github.com/aussiekarl-gif/BTC_Composite/pull/409

- Draft PR, branch `research/firsthand-api-validation`, latest head `2b2f1198236350af1bfe4605e60a7e565177e309`.
- Adds `engines/research/firsthand_api_diagnostic.py` to fetch and preserve raw JSON for the catalogue, summary, BTC price, daily hashrate, fees, difficulty, realised price and MVRV.
- Adds a dedicated Actions workflow and 14-day raw-payload artifact. No data is normalised or integrated.
- Dedicated diagnostic workflow run 45965988733 passed, and its raw artifact was downloaded and inspected. The workflow now runs on push and pull_request. A dated validation report was added at `docs/research/FIRSTHAND_API_INITIAL_VALIDATION_2026-11-27.md` on the PR branch. Retrieval is validated; the series are not yet approved for model use.
- Keep PR draft and do not integrate until price/fee differences, missing dates, upstream independence, realised-price formula, and source methodology are validated. Firsthand's 200WMA matches a 1,400-calendar-day rolling mean of its own BTC price series over 3,680 dates (max relative difference ~0.0000048%); this is an internal consistency check, not independent corroboration. Its hashrate 7/30/60-day averages similarly reproduce from its daily hashrate series (~0.000005% max relative difference). Daily hashrate omits 2013-03-19, 2013-03-20, 2013-03-26 and 2013-03-28; daily fees omit 2025-11-13 to 2025-11-15. Fee7 has a ~3.75% discrepancy on 2025-11-21 under a seven-observation rolling comparison, immediately after the fee-data gap. Research-only; Production and notifications unchanged.
- Latest related research regression run 45965988723: regression tests, matched 200WMA research and V6.0 path/cost report passed; public-data smoke failed at Aethereal after Explore21 and Coin Metrics succeeded. CDD/snapshot summary steps were skipped.

## Session continuation protocol

At the end of each substantial work session, update this file or add a dated checkpoint recording:
1. PRs/branches and exact head SHAs.
2. Files changed and purpose.
3. Tests/workflow run IDs and actual outcomes.
4. What was not tested or remains uncertain.
5. The next concrete task.
6. Any user decision that changes project constraints.

In a new ChatGPT conversation, begin with: "Continue BTC DCA project. Read docs/BTC_DCA_PROJECT_HANDOVER.md and inspect the current GitHub state before making changes."

### Firsthand cross-source comparison (27 Nov 2026)

- Added research-only comparator `engines/research/firsthand_cross_source_validation.py` and workflow `.github/workflows/firsthand_cross_source_validation.yml` on PR #409.
- First completed comparison workflow run 45967307751 passed; artifact 15182853419 downloaded and inspected. Full results in `docs/research/FIRSTHAND_COINMETRICS_COMPARISON_2026-11-27.md` on the PR branch.
- Same-UTC-date comparison 2013-01-01 to 2026-11-26: BTC price Firsthand vs Coin Metrics PriceUSD mean absolute percentage error 2.235% (median 1.236%, p95 7.929%, max 92.855%); recent 90-day mean 0.818%. Daily fees vs FeeTotNtv mean 1.570% (median 1.141%, p95 4.023%, max 95.380%).
- Firsthand MVRV is effectively identical to Coin Metrics CapMVRVCur (mean difference ~0.0000013%), so it is not an independent MVRV check and likely shares upstream data or methodology. Firsthand realised price vs Coin Metrics PriceUSD / CapMVRVCur proxy mean difference 1.740%; this proxy assumes compatible supply basis and is not a direct CM realised-price series.
- Historical price outliers: 2013-04-11 ~92.86%, 2020-03-12 ~36.52%; fee outliers: 2014-09-07 ~95.38%, 2024-04-19 ~34.99%. Need investigate date/close conventions and possible source errors. Firsthand BTC price repeated USD 59,171.86 on 25 and 26 Nov 2026 in this snapshot; investigate freshness.
- A follow-up comparator now tests Firsthand 200WMA against a 1,400-calendar-day SMA from Coin Metrics PriceUSD. Run 45967448045 was in progress at last check; latest head then 9f28e3eb81702ef2f9c93ca64a71525af5433a94. Do not approve Firsthand for any model input until this check and outlier/freshness analysis are complete.
- PR #409 remains draft; no Production/V6.0 model inputs or notifications changed.


#### Independent 200WMA cross-check — completed 27 Nov 2026

- The first comparator workflow artifacts omitted the 200WMA metric due to a report-builder omission. The script was corrected; do not treat runs 45967448045 or 45967577757 as 200WMA validation.
- Corrected cross-source run 45967697247 passed; artifact 15183821578 was downloaded and inspected. Firsthand `ma200w` vs 1,400-observation rolling SMA of Coin Metrics `PriceUSD`: 3,679 overlapping daily dates (2016-10-31 to 2026-11-26), mean APE 0.2735%, median 0.2239%, p95 0.6690%, maximum 1.7734%; latest 90-day mean APE 0.0130%.
- This is a strong independent cross-source consistency check for the 200WMA calculation. It does not approve Firsthand's daily spot-price series, fees, or other indicators. Daily price/fee outliers, close-time conventions, and data update/finality still require investigation.
- Latest PR #409 branch head at this checkpoint: `b0fc5e591901e75b7a313f73d12fd9be664c29b8`. PR remains draft. Production and notifications unchanged.


#### Three-way Firsthand BTC price validation — 27 Nov 2026

- Added Explore21 Bitstamp daily OHLC CSV to the Firsthand comparator. Workflow run 45968107990 passed; artifact 15183034026 downloaded and inspected.
- Coin Metrics vs Explore21 price agreement is strong: 5,078 overlaps, mean APE 0.252%, median 0.125%, p95 0.893%, max 9.290%.
- Firsthand vs Explore21 is materially worse: 5,078 overlaps, mean APE 2.253%, median 1.243%, p95 7.904%, max 91.703%. On 2020-03-12 Firsthand = USD 6,770.48 vs Explore21 = USD 4,841.67 and Coin Metrics = USD 4,959.31. On 2013-04-11 Firsthand = USD 159.88 vs Explore21 = USD 83.40 and Coin Metrics = USD 82.90. These discrepancies are too large to attribute to small UTC close-boundary differences.
- **Decision: Firsthand BTC price and fees are not eligible for model inputs** unless source methodology is explained and data defects are resolved. Keep fee outliers under investigation. 200WMA still validates closely against Coin Metrics' independent 1,400-observation SMA; this does not validate the Firsthand price input itself. MVRV is effectively identical to Coin Metrics CapMVRVCur and is not an independent signal.
- Report updated at `docs/research/FIRSTHAND_COINMETRICS_COMPARISON_2026-11-27.md` on PR #409. Latest branch head `ebf68fa94c191b7232e294050d88f9bceb99bdd0`. PR remains draft; no Production or notification changes.


### Firsthand price vs exact V6.0 weekly signal sensitivity (27 Nov 2026)

- On PR #409, added an exact V6.0 weekly signal comparison using the same v60_200wma_policy.py weekly_prior_200wma_signals function. Signal = completed Sunday BTC/USD close divided by the mean of the previous 200 completed Sunday closes; signal Sunday excluded.
- Workflow run 45969244125 passed; artifact 15183528981 inspected. 517 matched weekly signals from 2017-01-01 to 2026-11-22.
- Absolute discount-to-200WMA difference: mean 0.093 percentage points, median 0.000 pp, p95 0.570 pp, max 5.221 pp.
- Threshold disagreements: 5% below 2 weeks (0.387%); 10% below 1 week (0.193%); 15% below 2 weeks (0.387%); 20%, 25%, and 30% below: zero disagreements across all 517 weeks.
- This exact weekly result supersedes the earlier daily 1,400-day threshold approximation. It suggests Firsthand vs Coin Metrics price differences do not change the current V6.0 20/25/30% weekly signal tiers over this sample.
- This is not yet a full portfolio backtest. It does not measure provider-specific next-Monday execution-price impact on BTC units accumulated or terminal AUD equity. Next task: run matched V6.0 cohort simulations with identical FX, capital, cash-yield, friction, weekly cap and policy settings, changing only the BTC price source (Firsthand vs Coin Metrics). Compare BTC accumulated, final AUD equity, buy counts and per-cohort differences. Keep Firsthand unapproved until that is completed.
- PR #409 remains draft/open/unmerged. Branch latest code head at this checkpoint ba460760ade389f7b8bab4c00dac57e3a70d9d97; report documentation commit b0746a2816ff1b505ba74b90396ba85b4546d145. CI: cross-source run 45969244125 success; earlier cross-source run 45969036803 success; regression run 45969036789 success; V5.9 validation run 45969036778 success; Firsthand diagnostic run 45969036779 success. Public-data smoke still reports the known Aethereal fetch failure; do not describe the entire smoke workflow as green.
- No Production or live-signal changes; notifications remain disabled.


### Firsthand vs Coin Metrics V6.0 matched portfolio replay (27 Nov 2026)

- Added engines/research/firsthand_v60_price_sensitivity.py and .github/workflows/firsthand_v60_price_sensitivity.yml on PR #409. Research-only matched replay changes only BTC/USD price source (Firsthand vs Coin Metrics PriceUSD); both use identical Frankfurter USD/AUD FX, exact V6.0 weekly prior-200-Sunday-close signals, next-Monday BTC/AUD spot proxy, A$510k capital, 41% initial BTC, 0%/5% gross cash yield, 0%/20% cash floors, 5% original-capital weekly cap, 0.25% annual BTC drag, 0.3% buy friction and A$3 fee.
- Workflow run 45970024219 passed; artifact 15184761303 downloaded and inspected. 414 matched overlapping 104-week cohorts per policy/floor/yield; overlapping windows are not independent.
- Measured 20/25/30% policy, 5% cash yield, no cash floor: median final-equity difference Firsthand vs Coin Metrics +0.009%, mean +0.027%, p95 absolute difference 6.98%, max absolute difference 11.64%. Median BTC-held difference +0.162%, p95 absolute difference 3.61%, max 7.51%. Median buy-count difference zero.
- With 20% initial-cash floor and 5% yield, measured-policy median equity difference +0.013%, p95 absolute difference 6.59%, max 11.02%. Zero-yield stress similar; maximum absolute equity difference 11.64%.
- From 2017 onward, Firsthand vs Coin Metrics daily-price mean APE 1.936%, median 1.139%, p95 6.593%, max 36.521%. Across 517 Sunday signal closes: mean 1.665%, median 1.077%, p95 5.450%, max 11.615%. Across 517 next-Monday execution closes: mean 1.949%, median 1.217%, p95 6.410%, max 19.746%. Notable Monday outliers: 2018-02-05 Firsthand USD 8,202.06 vs CM USD 6,849.54 (19.75%); 2021-06-21 USD 35,592.35 vs USD 31,715.16 (12.23%).
- Exact V6.0 20/25/30% weekly signal tier classifications matched on all 517 weeks, but provider-specific execution-price differences produced occasional 10–12% terminal equity differences in some overlapping cohorts. Median outcomes are similar; tail results are not. Keep Firsthand spot price as a research cross-check only, not a replacement model/execution input pending provider explanation/correction.
- Report updated on PR #409 at documentation commit a668f88fd9b35e3edf3a10f49ac2ba7b05c879fd; code replay at bda2c0c85b910e2d12391957415eddaa20205b00. PR remains draft/unmerged. No Production/live signal/notification changes.


### Firsthand price date-alignment diagnostic (27 Nov 2026)

- Firsthand's public BTC price page describes the series only as the daily closing price in USD. The API catalogue and payload do not state the exchange/venue, aggregation method, UTC cut-off, or historical revision/finality policy. API catalogue says series update a few times daily. The raw snapshot generated 2026-11-27T08:29:14Z contains 5,079 daily points from 2013-01-01 through 2026-11-27; 25 and 26 Nov both show USD 59,171.86 in that snapshot. This may be stale or unchanged data; provider convention must be clarified.
- Added a date-lag sensitivity diagnostic to PR #409. On strategy-period dates from 2017-01-01, Firsthand vs Coin Metrics mean APE falls from 1.936% same-date to 1.591% when comparing Firsthand date D with Coin Metrics date D-1. Firsthand vs Explore21 Bitstamp falls from 1.954% to 1.573% under the same offset. Median/p95 also improve, but maximum error worsens (Coin Metrics 36.52% same-date vs 24.81% at -1; Explore21 39.84% vs 27.84%). This indicates date-label/time-boundary effects may explain part, but not all, of the discrepancy. Do not shift series automatically.
- First lag diagnostic workflow run 45970588864 passed; artifact 15184264136 inspected. Added worst-date details per lag in follow-up commit a0d8ad5c059a32d4798737659c915ea52ad3d1c9; follow-up run 45970691684 queued at checkpoint.
- Matched V6.0 replay after this diagnostic was run 45970639184 (pending at checkpoint). Keep Firsthand spot price unapproved pending exact provider close convention, date-lag outlier review and portfolio sensitivity.
- Contact page lists provider operator email but no contact has been sent. Questions to ask: underlying BTC/USD venue(s); exact UTC day boundary and close/last/average/VWAP definition; historical revision/backfill policy; explanation of the 2017–2021 and 2020-03-12 discrepancies.
- PR #409 remains draft/open/unmerged. Production and live signals unchanged; notifications disabled.


### Firsthand date-lag outlier review — completed 27 Nov 2026

- Follow-up date-lag workflow run 45970691684 passed; artifact 15184802112 inspected. Offsets -2 to +2 tested for 3,617 strategy-era daily observations; no source data was shifted.
- Comparing Firsthand date D to comparator date D-1 gives the best mean alignment: Coin Metrics mean APE 1.936% -> 1.591% (median 1.139% -> 0.886%; p95 6.593% -> 5.634%); Explore21 Bitstamp 1.954% -> 1.573% (median 1.141% -> 0.852%; p95 6.695% -> 5.616%). This suggests a one-day date-label/close-time mismatch explains part, but not all, of the disagreement.
- Major outliers persist after the one-day comparison: Firsthand 2020-03-13 USD 6,189.76 vs Coin Metrics 2020-03-12 USD 4,959.31 (24.81%) and Bitstamp 2020-03-12 USD 4,841.67 (27.84%). Same-date 2020-03-12 Firsthand USD 6,770.48 vs CM USD 4,959.31 (36.52%) and Bitstamp USD 4,841.67 (39.84%). Firsthand 2018-02-06 USD 8,212.81 vs CM 2018-02-05 USD 6,849.54 (19.90%) is another large shifted-date difference.
- Conclusion: close-time/date convention may explain some of the average 2% difference, but it does not explain crash-day outliers. Do not shift data automatically. Obtain Firsthand's exact UTC boundary, venue/aggregation and history revision policy before any use.
- Matched V6.0 price-source replay run 45970691675 passed; research DCA regression run 45970639038 passed. The diagnostic is comparison-only.
- Report on PR #409 updated at ae9e5de5ed80229f30fef163be96da44c100149b. PR remains draft/unmerged. No Production/live signal/notification changes.


## Continuation checkpoint — 27 Nov 2026 (Firsthand price plateau)
- PR #409 branch `research/firsthand-api-validation`; head at checkpoint `ae9e5de5ed80229f30fef163be96da44c100149b` before latest report-only commit. PR remains open/draft; latest report-only commit is `7cc2f6b6391d3a29c35c87918dff88f63ee39d91`.
- Latest CI five checks all passed at prior head: cross-source `45970824823`, raw diagnostic `45970824915`, V6.0 sensitivity `45970825031`, V5.9 risk `45970824836`, regression `45970824825`.
- Raw Firsthand BTC series: 33 consecutive identical daily prices USD 116,666.67 from 2025-07-29 to 2025-08-30 inclusive; repeated value also 2026-11-25/26 at USD 59,171.86. Strong data defect/stale-series indicator; Firsthand spot price remains rejected for model inputs/execution replay.
- Added raw plateau finding to `docs/research/FIRSTHAND_COINMETRICS_COMPARISON_2026-11-27.md` on PR branch in commit `7cc2f6b6391d3a29c35c87918dff88f63ee39d91`. No Production, dashboard, live signals, or notifications changed.
- Next task: inspect checks triggered by report update; continue independent source investigation/provider methodology questions. Do not contact provider without user authorization. PR #409 stays draft/unmerged.


## Continuation checkpoint — 27 Nov 2026 (next data-source candidates)
- All five PR #409 workflows triggered by report checkpoint commit `7cc2f6b6391d3a29c35c87918dff88f63ee39d91` completed successfully: V5.9 risk `45971267919`, Research DCA regression `45971268047`, Firsthand raw diagnostic `45971267980`, V6.0 price sensitivity `45971267940`, cross-source comparison `45971268023`.
- Candidate source exploration: Explore21 public CSV/API has price history, realized price (method v2), MVRV, realized cap, 200WMA, hashrate 7d avg, HODL waves and point-in-time vintages. CC BY 4.0 attribution; API no key with 30 req/min. Prior price data cross-check exists; expand only research diagnostics to other metrics, with method/changelog/provenance validation.
- Bitview is another candidate: open-source Bitcoin data server, public API/OpenAPI docs, CSV/JSON, historical series and mining/network metrics; investigate endpoints, coverage, and whether source-independent. Not approved or integrated.
- No production changes, notifications remain off, PR #409 draft/unmerged. Next: build candidate comparison diagnostics for Explore21 and Bitview, inspect vintage/as-published support, then validate overlapping metrics independently against Coin Metrics and Firsthand.


## Continuation checkpoint — 27 Nov 2026 (Explore21 and Bitview candidate source research)

- Explore21 public API/catalogue reviewed. It publishes daily UTC-date CSVs and JSON endpoints, with metric descriptions and method changelogs; data is CC BY 4.0 with attribution, no-key API at 30 requests/minute (free developer key advertised at 120/minute). It states its on-chain metrics are computed from its own Bitcoin Core node and its price source is Bitstamp daily close.
- Explore21 includes BTC price, realized price (method v2), MVRV (method v2), realized cap, 200WMA, hashrate 7-day average, Puell, supply-in-profit, HODL waves and other series. Metric changelog and point-in-time as_published vintages are available; vintage retention currently begins 2026-11-18. Vintage snapshots are fingerprinted and OpenTimestamps-proven. Useful future bias-control, but only recent vintage coverage so far.
- Explore21 has a meaningful provenance advantage: the stated on-chain computation is local Bitcoin Core; its BTC/USD price is explicitly Bitstamp daily close; it uses a six-block confirmation buffer and does not roll back published values. Price has already shown strong agreement with Coin Metrics in earlier validation. Candidate next comparison: realized price, MVRV, hashrate, HODL waves and supply-in-profit, including metric changelog/method version, missingness and vintage snapshots. No pipeline integration yet.
- Bitview/Bitcoin Research Kit candidate reviewed. Public API and series catalogue are broad (thousands of historical series; API supports JSON/CSV; MIT software and CC BY 4.0 data). The hosted instance computes most data from its own Bitcoin Core node. BTC price provenance is mixed and time-varying: historical exchange records before 2015, then a chain-derived price estimate from block 340,000 (Jan 2015) onward. Its terms disclose this methodology and price estimates may be revised. This makes it an interesting independent on-chain research source, but not a suitable price/execution proxy without further validation.
- Bitview source independence is potentially high for chain-derived metrics because it runs its own node and derives metrics locally. However, it may share the Bitcoin Research Kit/BRK computation code ecosystem across the hosted service and self-hostable implementation; distinguish independent raw chain calculation from independent metric methodology. Validate catalog series IDs, units, indexes, date coverage, revisions and methods before use.
- This web/documentation review is not an API retrieval or quantitative validation. Next concrete task: implement a research-only GitHub Actions diagnostic that fetches Explore21 candidate series and Bitview catalog/selected series, captures raw snapshots and metadata, and reports date coverage, missingness, stale/repeated values, units/method versions, and matched-date comparisons against Coin Metrics/Firsthand where comparable. No Production, dashboard, live signal, or notifications changes. PR #409 remains draft/unmerged.
- Sources reviewed 27 Nov 2026: Explore21 data/API catalogue and metric docs (https://charts.explore21.com/data, https://charts.explore21.com/about, https://charts.explore21.com/faq); Bitview API docs and Terms (https://bitview.space/api/, https://bitview.space/terms/, https://bitview.space/support/); Bitcoin Research Kit/BRK overview (https://opensats.org/projects/bitcoinresearchkit).


## Continuation checkpoint — 27 Nov 2026 (PR #410 diagnostic created)

- PR #410 opened as draft: https://github.com/aussiekarl-gif/BTC_Composite/pull/410 (`research/explore21-bitview-diagnostic`).
- Adds `engines/research/explore21_bitview_diagnostic.py` and a manual + pull-request GitHub Actions workflow.
- Scope: raw Explore21 MVRV/Puell/MVRV-Z CSV snapshots and Bitview metric discovery/search/info/daily-series endpoint probes. Raw files, retrieval metadata, HTTP failures and SHA-256 hashes are retained in a 14-day Actions artifact.
- No normalization, metric merge, Production input, dashboard, signal, or notification changes. Diagnostic workflow was triggered by PR; status was queued at checkpoint and requires a follow-up check before conclusions.
- Bitview's official API docs identify series search and metadata/data endpoints. Official Terms state that the hosted data is computed from its own node, while price history has mixed sources and is chain-derived from block 340,000 onward. Do not use its price for execution modeling without further validation.
- Next: inspect PR #410 Actions result and artifact; verify endpoint shapes/series IDs, coverage and missingness. PR #409 remains draft/unmerged; PR #407 remains open/unmerged. Production stays frozen.


## Continuation checkpoint — 27 Nov 2026 (PR #410 first artifact review)

- PR #410 diagnostic run **45971970344** completed successfully and uploaded artifact **15184374814** (908,011 bytes; expires 11 Dec 2026). The diagnostic job succeeded; separate V6.0 smoke check failed at Aethereal retrieval, consistent with known Aethereal DNS/NXDOMAIN issue; regression tests and V5.9 validation passed.
- First raw artifact confirms Explore21 CSV endpoints are retrievable. MVRV ratio and MVRV Z-score each contain 5,551 daily rows from 2011-09-16 through 2026-11-26, no duplicate dates or missing values in captured rows. Puell Multiple contains 5,216 rows from 2012-08-16 through 2026-11-26, also no duplicate dates/missing cells in the capture. These are source snapshot diagnostics only, not metric validation; repeated BTC close values occur in these metric CSVs, and Puell issuance BTC is stepwise (35.81% repeated observations), expected for block subsidy issuance.
- Initial Bitview candidate-selection flaw found and fixed: initial diagnostic sorted broad search matches alphabetically and selected 20 cohort-specific series, missing global candidates. It fetched metadata and day1 data successfully for 19 selected cohort series, but this does not satisfy the planned global metric diagnostic. Script now selects explicit priority global IDs (realized_price, mvrv, hashrate, supply_in_profit, supply_in_profit_share, nupl) only when returned by search, and summarizes metadata/unit/index/null counts/ranges/repeated adjacent values. Updated run on commit d1e505e952a7829da03d0bb8c6e446a982d899d1 is queued/in progress as of 09:16 UTC.
- No metric approval, model integration, or Production changes. Continue checking the corrected artifact and actual endpoint payloads before making source-quality conclusions.


## Continuation checkpoint — 27 Nov 2026 (corrected Bitview global metrics)

- Corrected PR #410 diagnostic run **45972321989** succeeded; artifact **15185856717** captured. It found six primary global metric IDs via API search and fetched metadata plus daily-index data successfully for all six.
- Bitview series metadata/payload diagnostic: `realized_price` unit USD, 6,532 non-null/6,540 slots, 8 nulls; `mvrv` 5,948 non-null, 592 null; `hashrate` 6,533 non-null, 7 null (value range ~49,710 to 1.31e21, which needs unit/method review); `supply_in_profit` 6,533 non-null, 7 null; `supply_in_profit_share` 6,532 non-null, 8 null; `nupl` 5,948 non-null, 592 null. These counts and ranges describe the raw API response, not a verified date-mapped history or approval. Series version IDs preserved in artifact.
- Current diagnostic code now also probes date-addressed ranges for MVRV and realized price to verify calendar-date mapping. Commit `d3e079fe4d89d4e3af1594e2f92b071c7a546430`; all four PR checks queued as of this checkpoint. Await this run and inspect date-range probe before cross-source statistical comparisons.
- First artifact's E21 raw observations remain as reported in previous checkpoint. No Production changes.


## Continuation checkpoint — 27 Nov 2026 (Explore21/Bitview MVRV comparison)

- Bitview date-range probe confirmed calendar alignment: query for 2020-01-01 to 2020-01-04 returned start index 4017/end-exclusive 4020; its 3 values exactly matched the full daily array at positions 4017:4020. The day1 index maps consistently to calendar dates from 2009-01-01.
- Matched-date MVRV diagnostic with Explore21 MVRV CSV (5,551 matched dates 2011-09-16 to 2026-11-26): full-period mean APE 4.848%, median 0.320%, p95 45.035%, max 83.400%. Early divergence dominates: 2011 mean APE 73.03%, 2012 41.26%. From 2013 onward mean APE 0.787%, median 0.286%, p95 2.528%, max 21.484%; from 2017 onward 3,617 matches mean 0.447%, median 0.254%, p95 1.413%, max 20.658%; 2020 onward 2,522 matches mean 0.334%, median 0.224%, p95 0.964%, max 13.905%.
- Comparison report added to PR #410: `docs/research/EXPLORE21_BITVIEW_MVRV_COMPARISON_2026-11-27.md`. Candidate cross-check only; no input approval. Methodology and early historical divergence need investigation, including outliers around 2017-05-27, 2018-02-02, 2018-11-20 and 2020-03-12.
- PR #410 updated with report summary. Latest commit `b59c00bb3c12af05864d3131e5a1b2161b897093`; validation runs 45972702941 (diagnostic), 45972702933 (V5.9), 45972702895 (regression) were in progress as of 09:19 UTC. Draft/open/unmerged.
- Production remains unchanged; no notifications or dashboard changes.


## Continuation checkpoint — 27 Nov 2026 (additional cross-source metric comparisons)

- PR #410 expanded Explore21 captures to include `bitcoin-realized-price.csv`, `bitcoin-percent-supply-in-profit.csv`, and `bitcoin-hashrate.csv`. Diagnostic run **45972922447** succeeded, artifact **15185263956** reviewed from ZIP.
- Realized Price matched-date comparisons (Explore21 vs Bitview, APE): from 2017 mean 0.163%, median 0.123%, p95 0.510%, max 2.857%; from 2020 median 0.106%, p95 0.300%, max 0.997%. Early-history mismatches (2011) huge and inflate full-history mean; not date-shifted. Candidate corroboration only.
- Supply in Profit (percentage points absolute difference): from 2020 mean 0.759 pp, median 0.627 pp, p95 1.891 pp, max 4.608 pp. Some historical divergence remains; not approved.
- Hashrate: Explore21 series is a 7-day average; Bitview metadata describes trailing-24h block/difficulty-derived estimate. Matched 6,526 dates; median Bitview/Explore21 ratio ~1.018 overall, ~1.009 from 2020; median absolute percentage difference ~5.23% since 2020 and p95 ~16.35%, likely partly due smoothing mismatch. Need like-for-like smoothing before validation.
- New report committed to PR #410: `docs/research/EXPLORE21_BITVIEW_REALIZED_PRICE_SUPPLY_HASHRATE_2026-11-27.md`. PR body updated. Latest head **bc35a4cd1c192cf2f2afedeba34ad97e68ebcb27**, draft/open/unmerged. Awaiting CI for this new report/body update.
- No metric approved; no Production, dashboard, model, signal or notification changes.
- Next: inspect CI for latest PR head; continue investigating supply-in-profit discrepancies and earliest-history realized price/MVRV divergences. Hashrate should be compared after consistent averaging windows.


## Continuation checkpoint — 27 Nov 2026 (outlier dates reviewed)

- Follow-up date inspection added to the PR #410 comparison report. Supply-in-profit largest post-2013 disagreements: 2015-08-24 (15.42 pp), 2015-08-18 (9.40 pp), 2017-03-10 (7.26 pp), 2013-01-14 (7.10 pp), and 2015-09-05 (6.77 pp). These are notable volatility/early-history periods; source-specific price/UTXO/supply methods are hypotheses only.
- Realized Price largest post-2013 relative differences cluster 2013-01-01 through 2013-01-10 (~26.7% APE, ~USD 1.57 absolute gap), indicating sustained early-period offset rather than a calendar alignment problem. No date shifting applied.
- PR #410 comparison report extended with outlier-date review, latest head **ad2aa76b47e1903ec6a0de5dbdb6c281991540c1**, draft/open/unmerged. Checks were in progress on prior head bc35a4cd1c192cf2f2afedeba34ad97e68ebcb27; check latest status before reporting CI complete.
- Next: validate latest checks; investigate source price input provenance and formula/version history for 2013 RP and 2015/2017 supply-profit discrepancies. Production remains untouched.


## Continuation checkpoint — 27 Nov 2026 (Hashrate smoothing and latest CI)

- Latest PR #410 head **ad2aa76b47e1903ec6a0de5dbdb6c281991540c1** checks all succeeded: Explore21/Bitview diagnostic run **45973457803**, V5.9 Research Risk Validation **45973457884**, regression tests **45973457850**. Artifact **15185758640** inspected.
- Hashrate apples-to-apples test: Bitview day1 is trailing-24h estimate; Explore21 is 7-day average. Applying a 7-observation rolling mean to Bitview daily values yields, from 2020: median ratio Bitview/E21 **1.00640**, median APE **0.640%**, p95 **1.188%**, max **2.908%** (n=2,522), versus unsmoothed median APE 5.235%, p95 16.35%. This supports close metric-level corroboration once smoothing is matched; still not approved.
- Realized Price Jan 1–10 2013 offset confirmed with raw values: Explore21 ~USD 5.88–5.95 vs Bitview ~USD 7.45–7.50, while Explore21 BTC close ~USD 13.1–13.6. Sustained offset, not calendar mapping; exact upstream cause unknown.
- PR #410 report updated at latest commit **201b39014372fba904c303e2dc164798e84eb5c1**, draft/open/unmerged; check new CI statuses.
- No Production/dashboard/signal/notification changes. Continue research on discrepancy provenance and validation; keep candidates unapproved.


## Continuation checkpoint — 27 Nov 2026 (price-source provenance)

- Official source docs reviewed. Explore21 uses Bitstamp daily BTC/USD closes from Aug 2011. Bitview: older exchange-price history of undocumented original source through Jan 2015 (later followed Bitstamp); Bitfinex minute closes from Jan 5 2015 until block 340,000; from block 340,000 it uses a chain-derived transaction-output price estimate. This makes price-input differences a plausible source of early RP/MVRV and profitability metric mismatches, but not a proven explanation for each outlier.
- PR #410 diagnostic expanded to capture Explore21 `bitcoin-price.csv` and search Bitview price-series candidates. Latest head **5504c5c8e8666b16faecaa8cd2d021191ba9a851**, draft/open/unmerged; report updated with provenance. Check latest CI.
- References: Explore21 FAQ/about and Bitview Terms/Support (public official source pages). Continue quantitative source-price comparison from diagnostic artifact, then investigate remaining discrepancies. Production remains unchanged.


## Continuation checkpoint — 27 Nov 2026 (source metrics expanded)

- PR #410 diagnostic scope further expanded to fetch Explore21 price and realized-cap CSVs and search Bitview price, realized-cap, and Puell Multiple global series. New head **66b956727dca109511a394ad7e716545041ea745**. Await next artifact for candidate series selection, source coverage and matched comparisons.
- Current price provenance conclusion unchanged: price-history regime differences plausibly explain some metric discrepancies; exact outlier attribution remains unresolved. Production unchanged.


## Continuation checkpoint — 27 Nov 2026 (price, realized cap, Puell quantitative cross-check)

- Diagnostic artifact run **45973887035**, artifact **15186690700**, extracted and calendar matched.
- BTC price: correlation **0.999986**; median APE **0.220%** since 2020, p95 **0.934%**. Price-series broadly corroborate modern history.
- Realized Cap: correlation **0.9999994**; median APE **0.107%** since 2020, p95 **0.302%**; very strong modern agreement.
- Puell Multiple: correlation **0.996677**; median APE **1.115%** since 2020, p95 **4.604%**, persistent ~1.1–1.2% median offset. Investigate precise denominator window, issuance/subsidy conventions, and timing before candidate approval. Report expanded with full periods.
- PR #410 latest report update commit **217251ad8e34ab0f185b53c53ec4f07022cf49f3**; still draft/unmerged. CI statuses should be checked at latest PR head.
- No Production input or dashboard changes.


## Continuation checkpoint — 27 Nov 2026 (Puell method audit)

- Explore21 Puell component columns reproduce its multiple (max absolute residual ~3.76e-7). It uses observed daily new coin supply change valued at daily close and 365d average of same. Bitview describes trailing-24h subsidy/USD, trailing 365d claimed subsidy USD, sampled at the daily final block and monotonic block time.
- Median Bitview/E21 Puell ratio ~1.00509 overall/~1.00552 since 2020; price ratio median ~1.0. Puell ratio vs price ratio correlation ~0.39; after normalizing by price ratio median residual +0.51% overall/+0.55% since 2020. Price source mismatch alone insufficient; window/timing/issuance conventions are plausible but not confirmed.
- Puell cross-source candidate remains provisional; source methodology notes added. PR #410 latest head **3aaefaf579740a0385550f1af49886234a6e4610**. Diagnostic success; regression and risk validation pending.


## Continuation checkpoint — 27 Nov 2026 (NUPL cross-check)

- Derived Explore21 NUPL from its MVRV (`1 - 1/MVRV`) because no direct E21 NUPL capture available; compare with Bitview NUPL. Bitview internal MVRV/NUPL identity matches within max residual ~5.64e-7.
- Since 2020: correlation **0.999775**; median abs diff **0.001299** (NUPL ratio units, ~0.13 percentage points), p95 **0.005398**, max **0.142206**. Modern typical agreement is strong; stress-date outliers (e.g., 12 Mar 2020) remain. Full history skewed by anomalous early data. Candidate only, derived, not direct E21 NUPL validation.
- Report update commit **38af8b725441e22bd612ea6f2a6eb4aafac17566**; PR #410 head **38af8b725441e22bd612ea6f2a6eb4aafac17566**. Keep unmerged.


## Continuation checkpoint — 27 Nov 2026 (MVRV Z-Score cross-source discovery)

- Diagnostic discovery expanded to search Bitview for MVRV Z-Score and Z-score variants, with candidate global IDs added to selection priority, to compare against Explore21's existing Z-score CSV. Latest diagnostic code commit **d2b401ba6cae71f1c36ea8837c06889f5f51c8bd**, PR head **d2b401ba6cae71f1c36ea8837c06889f5f51c8bd**. Await discovery output before deciding if comparison possible.


## Continuation checkpoint — 27 Nov 2026 (metric-validation gates)

- Created cross-source validation standard **docs/research/CROSS_SOURCE_METRIC_VALIDATION_STANDARD_2026-11-27.md** at research branch commit **3eeaf75437cf10dd85be710e31bd8b187831b1a0**. It codifies source capture, formula alignment, calendar mapping, central/tail errors, stress-date review, reproducibility, causal walk-forward, incremental-value/ablation and forward-validation gates. Reliability status explicitly does not equal signal approval.
- Latest PR #410 head **3eeaf75437cf10dd85be710e31bd8b187831b1a0**. Workflows 849 regression, 17 diagnostic, 552 research validation queued; check after run. Previous run 16 diagnostic was still in progress at last poll.


## Continuation checkpoint — 27 Nov 2026 (MVRV Z-score status)

- Latest successful diagnostic artifact run 16 (head d2b401ba…) searched Bitview MVRV Z-score variants; all returned empty. No independent Bitview matching series available. Explore21 has MVRV Z-score CSV, but exploratory reconstruction via market cap minus realized cap over rolling market-cap standard deviation windows 2–10 years did not exactly match E21; no formula assumptions. Status: not comparable/formula unverified.
- Validation standard appended with this result; PR #410 update **d3847b411ad52eac72d73321dc123eadac6863c6**, current PR head **d3847b411ad52eac72d73321dc123eadac6863c6**. Latest CI should be polled. Production unchanged.


## Continuation checkpoint — 27 Nov 2026 (NUPL threshold disagreement)

- Audited derived E21 NUPL vs Bitview classification on threshold sets (not strategy test). Below 0 agreement 99.92% from 2017 / 99.96% from 2020. Below -0.10: Jaccard 0.946 (2017+) / 0.925 (2020+); daily agreement still >99.6%. Outliers: 2018-11-20 E21 -0.1088 vs Bitview +0.0381; 2020-03-12 E21 -0.1649 vs Bitview -0.0227. 2022-23 dates straddle -0.10 boundary. This matters for extreme stress classification; thresholds not recommended.
- Updated comparison report commit **66da4ddf9a61bdeb101a646be84f2dfa87568601**, PR #410 head **66da4ddf9a61bdeb101a646be84f2dfa87568601**. Check CI.


## Continuation checkpoint — 27 Nov 2026 (stress-date price-provenance audit)

- PR #410 diagnostic run **45977576799** succeeded on code head **66da4ddf9a61bdeb101a646be84f2dfa87568601**; artifact **15187148686** inspected. All three code-level checks on that head passed: Explore21/Bitview diagnostic, Research DCA regression, and V5.9 Research Risk Validation.
- Raw source-price comparisons quantified stress-date mismatches: 2017-05-27 Bitview +23.02% vs E21; 2018-02-02 -18.94%; 2018-11-20 +15.48%; 2020-03-12 +14.82%. On 2018-11-20 and 2020-03-12 these co-occur with large NUPL differences (E21-derived -0.1088 vs Bitview +0.0381; and -0.1649 vs -0.0227 respectively). Price-source mismatch is a plausible confounder, not proven sole cause; MVRV/NUPL also depend on realized-cap/UTXO methodology.
- Jan 2013 realized-price gap is not explained by contemporaneous spot-price mismatch: Explore21 price and Bitview price were close, while RP remained ~26% different. Cost-basis/UTXO/source history remains unresolved.
- Updated PR #410 report with this diagnostic at commit **b7c45c6742055a4b770544e6540440b2c14d310a**. Documentation-only commit; no CI rerun required by configured path filters. PR #410 remains draft/open/unmerged. No Production/model/dashboard/signal/notification changes.
- Next: investigate supply-in-profit outliers and methodology/version history; consider another independent source if a documented direct NUPL/Z-score match becomes available. Do not normalize raw data or approve candidate metrics without causal walk-forward/ablation/forward validation.


## Continuation checkpoint — 27 Nov 2026 (Supply-in-profit price-context audit)

- Compared supply-in-profit outlier gaps with matched Explore21/Bitview spot-price differences from PR #410 run-19 artifact. Correlation between absolute price mismatch and supply-in-profit gap is modest (Pearson 0.355 from 2013, 0.351 from 2017, 0.235 from 2020; rank correlations weak). Price-source mismatch likely contributes to some large outliers, but not all; 2013 outliers exist with close spot-price agreement.
- Largest outlier 2015-08-24: E21 36.04% vs Bitview 51.4625% (15.4225 pp), price mismatch +19.72%. 2017-03-10 gap 7.2631 pp, price mismatch +11.67%. 2013-01-14 gap 7.104 pp despite spot prices only -0.92% apart. Causes remain unresolved hypotheses (price assignment, UTXO cohorts/exclusions, supply-accounting or provenance).
- PR #410 report updated at **30c6375ba35ae45364029f533bf9d70e9f41ac03**; draft/open/unmerged. Documentation-only commit, no new tests triggered by configured path filters. Supply-in-profit remains provisional/unapproved.
- Next: review metric definition and methodology version/source for supply-in-profit and investigate if independent direct NUPL/Z-score series exist; no strategy or Production integration.


## Continuation checkpoint — 27 Nov 2026 (Supply-in-profit definitions reconciled at high level)

- Official documentation indicates Explore21 and Bitview supply-in-profit-share are broadly aligned concepts: all-UTXO, BTC-weighted profit share. Explore21 method v2 uses last-move daily close below current close and zero basis for pre-price-history coins; Bitview metadata says all UTXOs, creation price at or below sampled spot, and share of cohort supply. Both percent variants weight by BTC amount (not output count).
- Remaining exact differences: strict < vs <= at break-even, daily-close vs final-block/day sample, differing price-source regimes, six-block confirmation vs sample depth, and possible denominator/supply conventions. This is a tighter comparability diagnosis, not validation or approval.
- PR #410 report updated at **9f935aa1a19e0acc691d4e2706cfc5b44bfdc108**; still draft/open/unmerged. Documentation-only update; no CI rerun under current workflow path filters. Supply-in-profit remains provisional.
- Next: examine source price/close/sampling conventions and historical UTXO cohort details if documented; then decide if residual discrepancy is acceptable for metric reliability only. No Production changes.


## Continuation checkpoint — 27 Nov 2026 (direct Coin Metrics NUPL availability probe)

- PR #410 diagnostic code now makes a raw no-key Coin Metrics Community API probe for direct BTC daily NUPL, retaining status/body excerpt and a summary if available. Commit **7ad93dce9898a1fe9c04841246e22f08bc157b61**.
- Diagnostic run **45978508682** succeeded; artifact **15187578852** reviewed. Coin Metrics direct NUPL endpoint returned **403**: NUPL at daily frequency for BTC is not available with the supplied community credentials. No data file was saved. Community MVRV-based derived NUPL would not be independent from the MVRV input; Bitview remains the independent cross-source comparison. The raw probe remains as a low-risk availability test, not a dependency.
- PR #410 report updated at **e911ff457432bcd1df013b831b8ff015a487a889**. CI on code head: diagnostic success (run 23), V5.9 risk validation success (run 558); regression run **45978508708** still in progress at checkpoint. Check final status. PR remains draft/unmerged; no Production/model/dashboard/signal/notification changes.
- Next: await regression completion; continue metric provenance review only, keep candidate metrics provisional and avoid direct signal experimentation until data validation gates are met.


## Continuation checkpoint — 27 Nov 2026 (MVRV Z-Score formula reconstruction)

- Explore21 official method v1 confirms the MVRV Z-Score formula: (market cap - realized cap) / expanding sample standard deviation of market cap, starting 18 Aug 2011; first displayed observation after 30 days. This supersedes earlier rolling 2–10-year reconstruction attempts.
- Reconstructed from Explore21 captured realized-cap CSV with sample expanding std (ddof=1). Full 5,551 overlap: mean absolute Z difference 0.008913, median 0.004492, p95 0.032303, max 0.472238. 2024+: mean 0.004021, median 0.004508, p95 0.007297, max 0.008448. First published observations and latest 26 Nov 2026 value match near floating-point precision, but notable historical residuals remain around 2013/2017 (e.g., 30 Nov 2013 calculated 7.5503 vs published 7.0781). Formula identified; source-input/version alignment unresolved. No independent Bitview series; not approved.
- PR #410 report and validation standard updated; latest branch head **f9a9aa1e179144f730a66431d0e207886691bd3a**, draft/open/unmerged, mergeable true. Code head **7ad93dce9898a1fe9c04841246e22f08bc157b61**: diagnostic run 23 **45978508682** success, V5.9 validation run 558 **45978509158** success, regression run 855 **45978508708** success. Direct Coin Metrics daily NUPL probe returned 403; documented.
- All cross-source work remains diagnostic/research only. No Production/model/dashboard/signal/notification changes.
- Next: continue method/source alignment for Z-score residuals or shift to the next validated metric candidate; keep raw source values unadjusted and candidates unapproved until full signal validation gates are met.


## Continuation checkpoint — 27 Nov 2026 (Z-Score method changelog probe and final CI)

- Explore21 Z-score method changelog captured raw (run 27 artifact **15187998679**, HTTP 200): method v1, first published 2026-07-15, no subsequent method-change entries. This does not rule out data revisions. E21 MVRV ratio reconstructed from its cap CSV matches published ratio within ~5e-7; Z-score denominator residual is still unexplained, do not label source error.
- PR #410 code head **ca6c4c24ca5146430d9aa74120db9fa7a0b8e0b5**, latest PR head **0bb806e4bfd1aff23dd10248735c0c2b03d1689d** (documentation commits after code). Diagnostic run 27 **45979050729** success, Research DCA regression run 859 **45979050701** success, V5.9 Research Risk Validation run 562 **45979050815** success.
- PR #410 remains draft/open/unmerged, mergeable true at last metadata poll. No Production/model/dashboard/signal/notification changes.
- MVRV Z-score remains candidate-only; formula identified, reconstruction partial, no independent cross-source series, historical denominator/input alignment unresolved. Continue investigating only with raw data and transparent methods; do not promote or tune thresholds.


## Continuation checkpoint — 27 Nov 2026 (Z-Score residual isolated to denominator)

- Additional checks: Explore21 Z-score CSV and separate BTC Price CSV are exactly identical on all 5,551 matched dates; MVRV ratio reconstructed as market_cap_usd/realized_cap_usd from Explore21 Realized Cap CSV matches published MVRV within ~5e-7 throughout. Remaining Z-score reconstruction residual is isolated to the standard-deviation denominator calculation/input series; no attribution (our reconstruction implementation vs historical input/version mismatch) is proven.
- Report and validation standard updated; PR #410 body updated. Latest branch head **d5e2bfb851ec16f7a401d170a48ff411813a4c24**, draft/open/unmerged, mergeable true. Docs-only commits since code head ca6c4c24; CI code head all green: diagnostic run 27, DCA regression 859, V5.9 validation 562.
- All diagnostic metrics remain unapproved. No Production/model/dashboard/signal/notification changes. Next: only further denominator reconstruction tests with clear assumptions; otherwise move to the next reliability-qualified metric, keeping PR #410 diagnostics separate from strategy research.


## Continuation checkpoint — 27 Nov 2026 (MVRV Z-Score cycle-anchor check)

- Added cycle anchor table for the expanding-sample-std reconstruction. Absolute differences: 2013 top 0.29260, 2015 low 0.00440, 2017 top 0.08074, 2018 low 0.00323, 2021 top 0.01632, 2022 low 0.00116, 2025 top 0.00637, 2026-06-30 low 0.00039, latest 26 Nov 2026 ~0.0000004. Most later cycle anchors close; largest discrepancy remains 2013, 2017 smaller. This is partial reconstruction, not independent validation.
- Report and PR #410 body updated at **5dd2fc08069f09ad05b352c152c12c6b7ee2c91f**. Latest PR branch mergeable true, draft/open/unmerged; code head ca6c4c24 CI green (diagnostic 27, DCA regression 859, risk validation 562). Docs-only updates do not trigger tests.
- No Production/model/dashboard/signal/notification changes. Continue to keep Z-score provisional/unapproved.


## Continuation checkpoint — 27 Nov 2026 (BlockHorizon vs Explore21 price/Z-score)

- PR #410 diagnostic captures the user-confirmed BlockHorizon MVRV Z-score CSV at immutable commit; artifact **15188303737** inspected. Matched with Explore21 on 5,499 dates (2011-09-16–2026-10-05).
- BH Price column exactly matches Explore21 from 2013-01-01 onward (5,026 dates), including V6.0's entire 2017+ price input period. Earlier 2011–12 prices differ (max APE 42.09%). Important: V6.0 historical accumulation backtest uses the export's Price column only, not its MVRV Z-score column; its 2017+ price source is strongly corroborated. No backtest changes.
- BH MVRV Z-Score is generally higher than E21; 2017+ MAE 0.1263, median abs diff 0.0838, p95 0.4432, max 1.3140; 2020+ median 0.07925, p95 0.30496. High-threshold overlap weak: Z>=7 Jaccard 0.636 from 2017 and 0.000 from 2020+ (BH has 3 days, E21 none). BH formula not reconciled; thresholds are provider-specific, no Z-score signal approval.
- Report and validation standard updated; PR #410 body updated at latest head **3cbd445e94c502eea8b00d51f5861f3aa3b5766e**, draft/open/unmerged, mergeable true. Code head **3cca1d07501613a98dfff4a4b2c53a12af75d283** all CI green: diagnostic 34, DCA regression 866, V5.9 validation 569.
- No Production/model/dashboard/signal/notification changes. Continue reliability research; all Z-score threshold candidates remain unapproved.


## Continuation checkpoint — 27 Nov 2026 (V6.0 Firsthand/Coin Metrics portfolio-source sensitivity)

- PR #409 run **45971267940** passed; artifact **15184698285** downloaded and inspected. 414 overlapping 104-week cohorts per policy/floor/yield, matched Firsthand vs Coin Metrics price source; cohorts are not independent. The full paired-source report is now in `docs/research/FIRSTHAND_V60_PRICE_SOURCE_SENSITIVITY_2026-11-27.md` on PR #409 branch.
- Price errors on execution dates: Sunday signal closes 517 obs median APE 1.077%, p95 5.45%; Monday execution closes median 1.217%, p95 6.41%, max 19.75%.
- At 5% cash yield/20% initial cash floor, measured policy: train (158 cohorts) median equity source delta ~0.0002%, mean -0.0288%, p95 abs 7.94%, max 11.02%; BTC held median +0.1667%, mean +0.2659%, p95 abs 4.83%, max 8.32%. Holdout (153 cohorts): median equity +0.0541%, mean +0.0293%, p95 abs 3.81%, max 7.65%; BTC held median +0.1679%, mean +0.2713%, p95 abs 2.65%, max 4.26%. Buy counts remain identical across paired 20/25/30-threshold rows.
- Source effects are very small in median but material in tails. This is a source sensitivity audit, not a strategy win or approval. Firsthand price remains not approved; V6.0 current BlockHorizon price source is separately cross-validated exact against Explore21 from 2013 onward.
- PR #409 latest head **6db361f9f134ce22ed95b68cdbd218956063328a**, draft/open/unmerged, mergeable true. Code head **7cc2f6b6391d3a29c35c87918dff88f63ee39d91** had all five CI checks green. Docs-only update; no new tests needed.
- PR #410 remains a separate diagnostics-only draft/open/unmerged PR; latest known head **5dd2fc08069f09ad05b352c152c12c6b7ee2c91f** mergeable true. No Production/model/dashboard/signal/notification changes.


## Continuation checkpoint — 27 Nov 2026 (V6.0 timing diagnostic audit; corrected rerun pending)

- PR #411 V6.0 ranking workflow run 19 produced a preliminary 104-week policy ranking artifact, but review found the old `same_spend_same_count_btc_timing_uplift_pct_hindsight` counterfactual equalized gross buy amounts and uniformly spaced dates. It mixes buy-amount distribution/deployment pace with dates; it is not pure timing. Example: baseline buys every week at the same dates as its benchmark yet old metric shows +18.85% train / +22.56% holdout at reference settings, solely from unequal actual buy amounts.
- Research-only correction: added `same_actual_spend_distribution_uniform_dates_btc_timing_only_pct`, preserving actual gross buy amounts and count and shifting only dates uniformly. It isolates execution-price timing but ignores cash feasibility at shifted dates. Legacy equal-buy-amount benchmark retained and renamed in summaries to avoid confusion. Tests added: weekly baseline timing-only effect must be zero; capped early buys on a rising price path should have positive timing-only effect.
- Workflow now runs simulator/ranking tests before the full ranking and path filters include the affected report/tests. Initial CI caught a syntax error in the new output dictionary; fixed. Latest head **394c6f482b805c77a4aa083148aa639a800b5ef0**, PR #411 draft/open/mergeable true. Latest ranking run **45981630288** queued; regression run **45981630099** queued; other V6.0 reports/risk tests triggered. Await full rerun; preliminary leaderboard is not to be interpreted.
- No Production/model/dashboard/signal/notification changes. All strategy ranking and timing claims remain research-only pending corrected artifact and validation.


## Continuation checkpoint — 27 Nov 2026 (corrected V6.0 timing/allocation audit complete)

- Corrected V6.0 accumulation ranking run **31** workflow **45981630288** succeeded; artifact **15190071431** analyzed. 407 overlapping 104-week cohorts: 158 train, 146 holdout, 103 bridge. Reference: 5% cash yield, 0% floor, uncapped, 5% original-capital weekly cap.
- At reference settings, all scale-1 baseline/measured/stepped/aggressive policies and fixed weekly DCA buy 104/104 weeks. Pure buy-date timing-only diagnostic is zero for these. V6.0 current 20/25/30 ladder is **dynamic amount allocation, not buy-date selection**.
- Allocation-weighting uplift vs equal buy amount uniform weekly buys: measured20/25/30 train/holdout median 18.85%/26.58%; train tiers inactive. Holdout measured10/15/20 27.32%, but paired median BTC difference vs20/25/30 0%, mean +0.714%, win43.2%; no robust threshold superiority. Stepped/aggressive20/25/30 also paired median0 and wins below 50%.
- Aggressive1.25x/1.5x policies have median paired BTC gains vs scale1 of +4.13%/+6.61% holdout, but spend more (deployment speed). Aggressive1.5x has fewer-than-weekly buys in 46 holdout cohorts from cash exhaustion; timing-only median0, mean0.883%, p95 3.869%, max4.538%. No signal-based timing edge demonstrated.
- Report: `docs/research/V60_ALLOCATION_WEIGHTING_TIMING_AUDIT_2026-11-27.md` on PR #411 branch. PR #411 latest head **14c8f0dddbeedba73a09cd5138be3c311f20c37f**, draft/open/unmerged, mergeable true. Corrected ranking, simulator tests, DCA regression, V6.0 historical, pacing, scale, cap, synthetic stress and V5.9 risk validation all passed. Public-data smoke job fails only due Aethereal dataset DNS resolution; unrelated to simulator/ranking.
- Next research candidate: a true conditional buy-date strategy—zero base buys above 200WMA, buys only at/below selected discount tiers, optionally with recovery confirmation—run in a separate PR and matched train/holdout. No Production/model/dashboard/signal/notification changes.


## Continuation checkpoint — 27 Nov 2026 (next DCA timing candidate already exists)

- Avoid duplicating a new V6.0 "conditional buys below 200WMA/recovery confirmation" policy: Cycle Trading already contains `cycle_forward_cash_dca.py` and `adaptive_recovery`, which gates on strict prior 200WMA and uses weekly recovery sizing against an anchored original AUD cash budget. It is explicitly prospective, research-only, and historical/live parity unverified.
- Next research task should replay that exact prospective fixed-cash policy from predeclared calendar enrolment dates (not cycle lows), compare fixed weekly DCA and the current remaining-cash 2.5%-below-200WMA rule, with 5% cash yield and 5% original-capital weekly cap. Report BTC units, AUD VWAP, cash remaining, timing errors, and censoring. This should be a separate research PR, not live/Production integration.
- PR #411 V6.0 audit report now links to this existing policy and corrects its next-step recommendation. Latest PR #411 head **c6807e2e4a1886b18fd0d482c9f2a8d1ec809c1a**, draft/open/unmerged, mergeable true. Corrected ranking/tests are green; public-data smoke job's DNS failure is unrelated.


## Continuation checkpoint — 27 Nov 2026 (prospective adaptive recovery calendar replay)

- PR #412 draft: `research/prospective-adaptive-recovery-replay`. Calendar-entry cohorts (first Monday quarterly; 104 weeks) compare fixed weekly DCA, 2.5% of remaining cash only below strict prior 200WMA, and existing `adaptive_recovery` sizing. Fresh-cash scenario A$292,383; capital A$510k; 5% annual effective cash yield; A$25,500 weekly cap; 0.3% friction; A$3 fee. BTC/USD export through 5 Oct 2026 plus Frankfurter FX; spot BTC/AUD proxy, not ASX:IBIT.
- 32 complete quarterly cohorts (20 pre-2022 entry, 12 2022+ entry; overlapping, not independent). Earlier runs 907/908 generated identical cohort CSV and summary artifacts. Main DCA regression and synthetic replay tests passed; new conditional summary metrics are being rerun on current head (run 915 pending).
- Unconditional fixed weekly DCA median BTC: pre-2022 18.277 vs adaptive0 and below-WMA2.5%0; 2022+ fixed3.827 vs adaptive1.736 and below-WMA2.5%0.596. Adaptive trigger rate: 30% pre-2022 and 58.33% 2022+; median trigger delays 69.07 and 10.57 weeks.
- Conditional on adaptive trigger, paired BTC uplift median +37.64% pre-2022 (4/6 wins) and +37.03% 2022+ (6/7 wins); paired final-equity uplift +41.81% (6/6) and +42.19% (7/7). No-trigger cohorts typically lag fixed weekly DCA in final equity (median paired -38.60% pre-2022, -37.19% 2022+). Conditional upside is not an unconditional replacement result.
- Adaptive median VWAP premium to the future cohort low, conditional on buying, ~25.70% pre-2022 / 25.09% 2022+. Retrospective timing score only, not forecast accuracy. 
- Report `docs/research/prospective_adaptive_recovery_replay_20261127.md` on PR #412. Current recommendation: no Production change. For BTC accumulation, fixed weekly remains the stronger unconditional baseline in this sample; next research test a hybrid fixed calendar DCA plus adaptive reserve (25/50/75% base allocation), predeclared cohort dates and same cap/cash assumptions.
- No Production/dashboard/live signal/notifications/portfolio changes. PR #412 remains draft/unmerged; summary-enhancement CI rerun pending.


## Continuation checkpoint — 27 Nov 2026 (calendar replay final artifact and CI confirmation)

- Current PR #412 report: `docs/research/prospective_adaptive_recovery_replay_20261127.md` on branch. Final cohort CSV from workflow run **918** is byte-identical to earlier 907/908 artifacts. Research DCA test job run 918 passed including the 8 synthetic tests and 32-cohort historical runner. Documentation confirmation run **919** pending; Aethereal public-data smoke failure is upstream and separate.
- Additional paired results for the below-WMA-only 2.5% baseline: active in 6/20 pre-2022 and 7/12 2022+ cohorts, BTC wins vs fixed weekly 0/6 and 0/7 (conditional median paired BTC uplift −21.00% / −28.94%). Conditional final-equity wins 6/6 and 5/7 due idle cash/yield.
- Summary metric extension now reports conditional cohort win rates for triggered adaptive/below-WMA cohorts, not only unconditional medians. Final decision remains: fixed weekly DCA better for unconditional BTC accumulation; adaptive recovery adds conditional upside but is not a standalone robust replacement. Next research: hybrid fixed base + adaptive reserve, 25/50/75% base allocation.


## Continuation checkpoint — 27 Nov 2026 (hybrid calendar DCA + adaptive reserve research)

- Draft PR #413 `research/hybrid-calendar-dca-adaptive-reserve`: independent module (does not depend on PR #412) tested fixed base DCA 25/50/75% plus adaptive reserve; 32 complete overlapping quarterly cohorts, 104 weeks, shared A$25,500 weekly cap. Current-head CI run **937** passed main DCA regression, 5 hybrid synthetic tests, historical runner and artifact. Aethereal public-source smoke failure is upstream.
- Pre-2022 median BTC for hybrids 25/50/75 base: 7.961 / 9.349 / 13.708 vs fixed weekly18.277; paired median BTC −75/−50/−25%, paired final-equity −14.20/−9.47/−4.73%. 2022+ median BTC2.015/2.422/2.870 vs fixed3.827; paired median BTC −15.96/−10.81/−5.42%, final-equity +25.22/+16.57/+8.27% (66.67% equity wins).
- 75% fixed base/25% reserve is strongest hybrid for unconditional BTC accumulation, but does not beat fixed weekly median BTC. Adaptive trigger rate30% pre-2022,58.33% 2022+. Conditional triggered cohorts improve, but no-trigger opportunity cost remains. Report `docs/research/hybrid_calendar_adaptive_dca_20261127.md` on PR branch.
- Next: predeclared 80/90% base allocation variants to test a smaller reserve, keeping assumptions and cohorts unchanged. No Production/dashboard/live signal/notifications/portfolio changes.
