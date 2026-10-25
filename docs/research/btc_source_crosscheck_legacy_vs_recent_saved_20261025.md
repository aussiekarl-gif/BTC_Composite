# Read-only BTC source provenance: historical mismatch versus latest five saved observations — 25 October 2026

## Concrete issue audited

The frozen BTC prospective research tape currently has **8** dated observations, but **two early saved records from 15 and 17 October carry 6.29% source crosscheck dispersion**. The known historical Blockchain.com chart issue concerned midnight-dated values representing a **PRECEDING UTC close**, not necessarily an actual contemporary BTC market divergence. Prior external date-alignment corrections cannot be applied retroactively to overwrite their immutable hashes.

The last five dated observations of the saved tape (19–23 October) each have a **source-crosscheck diagnostic of 0.0500%**. The live Friday mid-session Kraken/Blockchain.com published probe also showed independent disagreement around **0.031%**, but those read-only provider probes are **NOT** silently substituted for the original forward-tape 0.0500% diagnostics. A source-crosscheck saved field is not an intraday broker quote.

Previously, the unified research report only exposed `max_historical_BTC_source_crosscheck_dispersion_pct = 6.29` and emitted a permanent `BTC_SOURCE_MAX_DISPERSION_GE_5PCT` REVIEW flag, despite a clean set of subsequent saved source diagnostics. The warning **must remain**, but should not be misunderstood as a present 6.29% BTC price mismatch.

## Small diagnostic-only code change

- In `engines/research/forward_market_readiness.py`, retain the all-time maximum and original review boolean *unchanged*, and add **new, explicitly named** read-only diagnostics: the latest saved source crosscheck, the maximum of the **last five saved** rows, those five source dates, whether all five pass original point-in-time prospective capture validation, and whether the historical maximum occurred outside this five-row subset.
- In `engines/research/btc_unified_research_readiness.py`, add a `source_health.btc_crosscheck_provenance` section that shows the all-time high **and** recent five saved rows side by side. The original historical REVIEW flag still appears (no evidence erasure), with an explanatory sentence **only if five fully prospective, new source diagnostics exist** and the five-row maximum is below the existing 5% threshold.
- Under fewer than five rows, stale/backfilled timestamps or a new provider discrepancy at or above 5%, the historical warning is not overwritten or falsely cleared. Neither an all-history nor a rolling diagnostic is classified as a confirmed broker fill, personal BUY/SELL permission or investable return.
- Preserve original hash-verified BTC and ASX tapes, immutable source integrity checks and all existing test fixtures. No changing `calculate_allocation_signal`, `make_current_decision`, Production V5.8.2, Research V5.9, 2.5% Cycle BUY, SELL timing, model code SHA, daily ntfy, streaming dashboard, schedules or brokerage.

## Verification

Extend the existing `tests/test_forward_market_readiness.py` and `tests/test_btc_unified_research_readiness.py` with synthetic add-only hash-chained observations that preserve early 6.29% records, then append exactly six genuine one-day-after source records at 0.05%. Assert the recent five-row diagnostic 0.05%, old 6.29% warning still open, fresh-vintage status, *no automatic model promotion*, no recommendations, ntfy or portfolio writes. Test missing/short cohorts, which must **not** claim a clean prospective recent-five quality cohort.

The regular prospective research nightly GitHub workflow already runs both suites and generates the read-only unified report. This is no new workflow, schedule or notification. It improves interpretation, not the Bitcoin model or observed market data.

### When revisiting the warning

The old immutable 6.29% historical diagnostic can remain marked for source audit forever. It must not force rewriting previous data. Recent dates, post-collection provider cross-checks and samples will continue to be assessed separately. Future true provider mismatches must still block verified source capture under the existing quality gates.
