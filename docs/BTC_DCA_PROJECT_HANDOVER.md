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
