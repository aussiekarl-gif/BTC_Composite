# Puell incremental decision-value research gate (2026-11-07)

Status: **NOT VALIDATED FOR TRADING; DO NOT PROMOTE TO PRODUCTION**.

## What has actually been verified
- Coin Metrics Community IssTotUSD, IssTotNtv and PriceUSD yielded 439 aligned observations (2025-08-24 through 2026-11-05); direct USD issuance matches IssTotNtv * PriceUSD to floating-point precision.
- Trailing 365-calendar-day total-issuance Puell = 0.9100471246366543 on 2026-11-05.
- RevNtv, RevUSD and IssContUSD return HTTP 403 on the public endpoint. Their availability must not be fabricated or interpreted as zero.
- The direct-source check is **not** an independent published Puell-series comparison, and it does **not** demonstrate trading alpha.

## Pre-registered experiment, not an after-the-fact optimisation
1. **Data provenance:** Acquire point-in-time historical IssTotUSD, BTC/USD, AUD/USD and ASX:IBIT executable-price history. Identify earliest date each metric could actually have been observed; lag decisions at least one complete UTC daily close. Record source, timestamp, missingness and revisions. Do not use retrospectively revised risk or Puell scores as if they were contemporaneously available.
2. **Sufficient independent history:** 439 daily observations give only 75 non-overlapping post-warmup days after the 365-day mean, before other data losses. This is insufficient to demonstrate robust multi-cycle Puell value. Obtain several complete BTC cycles or mark the study INSUFFICIENT_HISTORY. Exclude the immature 2013 cycle from headline claims.
3. **Matched baselines:** (A) frozen Production V5.8.2, (B) frozen Cycle Trading research baseline, (C) each baseline plus a strictly pre-specified Puell gate. Do not substitute a new optimised baseline for the frozen reference. Use identical starting A$500,000, deposit schedule, AUD FX, capital reserve, decision times, broker fees, slippage, ASX:IBIT trading calendar and tax assumption in each pair. Respect user's flexible deployment into 2027; no forced investment solely to improve a backtest.
4. **Candidate policies:** Evaluate *filter-only* (Puell cannot force a buy or sell, only veto one), and *sizing-only* (pre-specified bounded multiplier). Fix candidates and their parameters using training data only. No price-specific curve-fitting on held-out dates. Puell < 1 is a potential valuation clue, **not** an automatic bottom or buy recommendation.
5. **Chronological walk-forward:** Tune in expanding historical training folds; evaluate untouched subsequent blocks, with embargo sufficient for signal availability and no train/test leakage. Preserve all losing folds and report independent test sample counts. Avoid treating overlapping folds as independent evidence.
6. **Metrics:** Report ending BTC, after-cost ending AUD equity, worst drawdown, idle cash and capital deployment, number of orders, fees, turnover, false-positive trades, and downside stress. Include buy-and-hold and matched fresh-cash baselines. Show absolute differences and uncertainty across cycles, not just percentage uplift.
7. **Release gates:** No Production change unless independent matching-variant data check, causal provenance, meaningful multiple-cycle holdouts, positive after-cost incremental improvement across several regimes, no material tail-risk or cash-runway deterioration, full Streamlit/ntfy parity and rollback tests all pass. Record actual numbers and links. Failure/insufficient evidence means research-only.

## Current blocking evidence
- Only 439 observed daily rows in current live-source audit; not enough for multi-cycle inference.
- No verified independent same-definition total-issuance Puell publication.
- No completed matched chronological backtest of Puell versus frozen baseline.
- No verified historical ASX:IBIT executable-price/FX point-in-time coverage across BTC cycles.

**Decision:** Keep PR #69 draft and unmerged. The indicator may be useful, but its incremental strategy value is not established.
